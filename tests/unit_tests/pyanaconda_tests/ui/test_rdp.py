#
# Copyright (C) 2024  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import socket
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, call, patch

import pytest
from systemd import journal

from pyanaconda import gnome_remote_desktop


class RDPShutdownTestCase(unittest.TestCase):
    """Simple test case for starting RDP server."""

    def test_shutdown_server(self):
        """Test shutdown_server method."""
        # Do nothing when grd_process is None
        gnome_remote_desktop.grd_process = None
        gnome_remote_desktop.shutdown_server()
        assert gnome_remote_desktop.grd_process is None

        # Gracefully kill GRD process
        gnome_remote_desktop.grd_process = Mock()
        gnome_remote_desktop.shutdown_server()
        gnome_remote_desktop.grd_process.kill.assert_called_once_with()

        # Error during the GRD process kill
        gnome_remote_desktop.grd_process = Mock()
        gnome_remote_desktop.grd_process.kill.side_effect = SystemError
        gnome_remote_desktop.shutdown_server()


class RDPServerTestCase(unittest.TestCase):

    def setUp(self):
        self.grd_server = None
        self.mock_anaconda = Mock()

        patcher_os = patch("pyanaconda.gnome_remote_desktop.os")
        patcher_util = patch("pyanaconda.gnome_remote_desktop.util")
        patcher_execWithRedirect = patch("pyanaconda.gnome_remote_desktop.execWithRedirect")

        self.mock_os = patcher_os.start()
        self.mock_util = patcher_util.start()
        self.mock_execWithRedirect = patcher_execWithRedirect.start()

    def _create_grd_server(self):
        self.mock_os.path.exists.side_effect = [True, True]
        self.grd_server = gnome_remote_desktop.GRDServer(self.mock_anaconda)
        self.mock_os.mock_reset()

    def _reset_mocks(self):
        self.mock_anaconda.reset_mock()
        self.mock_util.reset_mock()
        self.mock_os.reset_mock()
        self.mock_execWithRedirect.reset_mock()

    @contextmanager
    def _check_for_failure(self):
        with pytest.raises(SystemExit):
            yield
        self.mock_util.ipmi_abort.assert_called_once()

    def test_grd_init(self):
        """Test creation of the GRDServer."""
        # Fail on missing openssl
        self.mock_os.path.exists.return_value = False
        with self._check_for_failure():
            gnome_remote_desktop.GRDServer(self.mock_anaconda)
        self.mock_os.path.exists.assert_called_once_with("/usr/bin/openssl")

        # Fail on missing GRD
        self._reset_mocks()
        self.mock_os.path.exists.side_effect = [True, False]
        with self._check_for_failure():
            gnome_remote_desktop.GRDServer(self.mock_anaconda)
        self.mock_os.path.exists.assert_has_calls([
            call("/usr/bin/openssl"),
            call("/usr/libexec/gnome-remote-desktop-daemon")])

        # Success on GRD creation
        self._reset_mocks()
        self.mock_os.path.exists.side_effect = [True, True]
        gnome_remote_desktop.GRDServer(self.mock_anaconda)
        self.mock_os.path.exists.assert_has_calls([
            call("/usr/bin/openssl"),
            call("/usr/libexec/gnome-remote-desktop-daemon")])
        self.mock_util.ipmi_abort.assert_not_called()

    def test_start_grp_rpd_missing_username_password(self):
        """Test running of GRD server with missing pass and username."""
        self._create_grd_server()

        # Missing username and password
        with self._check_for_failure():
            self.grd_server.start_grd_rdp()

        # Missing username
        self._reset_mocks()
        with self._check_for_failure():
            self.grd_server.rdp_password = "secret"
            self.grd_server.start_grd_rdp()

    def test_run_grctl(self):
        """Test GRD server grdctl call method abstraction."""
        self._create_grd_server()

        # failed call
        self.mock_execWithRedirect.return_value = 1
        with self._check_for_failure():
            self.grd_server._run_grdctl(["rdp", "failed-call"])
        self.mock_execWithRedirect.assert_called_once_with(
            "grdctl",
            [
                "--headless",
                "rdp",
                "failed-call"
            ],
            env_add={"HOME": "/root"}
        )

        # success call
        self._reset_mocks()
        self.mock_execWithRedirect.return_value = 0
        self.grd_server._run_grdctl(["rdp", "success-call"])
        self.mock_execWithRedirect.assert_called_once_with(
            "grdctl",
            [
                "--headless",
                "rdp",
                "success-call"
            ],
            env_add={"HOME": "/root"}
        )

    def test_grd_certificate_generation(self):
        """Test certificate generation for RDP."""
        self._create_grd_server()
        self.grd_server._run_grdctl = Mock()

        # check certificate creation failure
        self.mock_execWithRedirect.return_value = 1
        with self._check_for_failure():
            self.grd_server._handle_rdp_certificates()
        self.mock_os.makedirs.assert_called_once_with("/root/.local/share/gnome-remote-desktop/")
        self.mock_execWithRedirect.assert_called_once_with(
            "/usr/bin/openssl",
            ["req", "-new",
             "-newkey", "rsa:4096",
             "-days", "720", "-nodes", "-x509",
             "-subj", "/C=DE/ST=NONE/L=NONE/O=GNOME/CN=localhost",
             "-out", "/root/.local/share/gnome-remote-desktop/rdp.crt",
             "-keyout", "/root/.local/share/gnome-remote-desktop/rdp.key"]
        )
        self.grd_server._run_grdctl.assert_not_called()

        # check certificate creation success
        self._reset_mocks()
        self.mock_execWithRedirect.return_value = 0
        self.grd_server._handle_rdp_certificates()
        self.mock_os.makedirs.assert_called_once_with("/root/.local/share/gnome-remote-desktop/")
        self.mock_execWithRedirect.assert_called_once_with(
            "/usr/bin/openssl",
            ["req", "-new",
             "-newkey", "rsa:4096",
             "-days", "720", "-nodes", "-x509",
             "-subj", "/C=DE/ST=NONE/L=NONE/O=GNOME/CN=localhost",
             "-out", "/root/.local/share/gnome-remote-desktop/rdp.crt",
             "-keyout", "/root/.local/share/gnome-remote-desktop/rdp.key"]
        )
        self.grd_server._run_grdctl.assert_has_calls([
            call(["rdp", "set-tls-cert", "/root/.local/share/gnome-remote-desktop/rdp.crt"]),
            call(["rdp", "set-tls-key", "/root/.local/share/gnome-remote-desktop/rdp.key"])])

    @patch("pyanaconda.gnome_remote_desktop.time")
    @patch("pyanaconda.gnome_remote_desktop.network")
    def test_run_find_network_address(self, mock_network, mock_time):
        """Test GRD server is able to obtain IP address."""
        self._create_grd_server()

        # failed to get ip
        mock_network.get_first_ip_address.return_value = None
        self.grd_server._find_network_address()
        assert self.grd_server.ip is None
        mock_time.sleep.assert_has_calls(list(call(1) for _ in range(5)))

        # success to get ip
        mock_network.reset_mock()
        mock_time.sleep.reset_mock()
        mock_network.get_first_ip_address.return_value = "192.168.0.22"
        self.grd_server._find_network_address()
        assert self.grd_server.ip == "192.168.0.22"
        mock_time.sleep.assert_not_called()

    @patch("pyanaconda.gnome_remote_desktop.socket")
    @patch("pyanaconda.gnome_remote_desktop.log")
    def test_grd_rdp_hostname_retrieval(self, mock_log, mock_socket):
        """Test GRD code for hostname retrieval."""
        self._create_grd_server()
        mock_stdout_log = Mock()

        # check error raise
        mock_socket.gethostbyaddr.side_effect = socket.herror
        mock_socket.herror = socket.herror
        self.grd_server._get_hostname_in_thread("192.168.0.1", mock_stdout_log)
        mock_log.debug.assert_called_once()
        mock_stdout_log.info.assert_not_called()

        # check error raise with IPv6
        mock_log.debug.reset_mock()
        mock_stdout_log.info.reset_mock()
        self.grd_server._get_hostname_in_thread("[cafe::cafe]", mock_stdout_log)
        mock_log.debug.assert_called_once()
        mock_stdout_log.info.assert_not_called()

        # check failure returned tuple is broken
        mock_stdout_log.info.reset_mock()
        mock_socket.gethostbyaddr.side_effect = None
        mock_socket.gethostbyaddr.return_value = ["only one value"]
        self.grd_server._get_hostname_in_thread("192.168.0.1", mock_stdout_log)
        mock_stdout_log.assert_not_called()

        # check failure returned tuple contains multiple IPs
        mock_socket.gethostbyaddr.side_effect = None
        mock_socket.gethostbyaddr.return_value = ["super-best-hostname.xyz",
                                                  None,
                                                  ["1.1.1.1", "2.2.2.2"]]
        self.grd_server._get_hostname_in_thread("192.168.0.1", mock_stdout_log)
        mock_stdout_log.assert_not_called()

        # check success
        mock_log.debug.reset_mock()
        mock_socket.gethostbyaddr.side_effect = None
        mock_socket.gethostbyaddr.return_value = ["super-best-hostname.xyz", None, ["1.1.1.1"]]
        self.grd_server._get_hostname_in_thread("192.168.0.1", mock_stdout_log)
        mock_log.debug.assert_not_called()
        mock_stdout_log.info.call_args.args[0].endswith("super-best-hostname.xyz")

    @patch("pyanaconda.gnome_remote_desktop.startProgram")
    @patch("pyanaconda.gnome_remote_desktop.journal")
    @patch("pyanaconda.gnome_remote_desktop.thread_manager")
    @patch("pyanaconda.gnome_remote_desktop.network")
    def test_run_grp_rdp_start_server(self, mock_network, mock_thread_manager, mock_journal,
                                      mock_startProgram):
        """Test GRD server start of RDP."""
        self._create_grd_server()
        self.grd_server.rdp_username = "goofy"
        self.grd_server.rdp_password = "topsecret"
        # patch _run_grdctl method to make the testing easier (tested separately)
        self.grd_server._run_grdctl = Mock()
        self.grd_server._find_network_address = Mock()
        self.grd_server._handle_rdp_certificates = Mock()

        # failed to obtain IP
        self.grd_server._find_network_address.side_effect = ValueError
        with self._check_for_failure():
            self.grd_server.start_grd_rdp()
        mock_network.wait_for_connectivity.assert_called_once()

        # failed to start grd server
        self._reset_mocks()
        self.grd_server._find_network_address.side_effect = None
        mock_startProgram.side_effect = OSError
        with self._check_for_failure():
            self.grd_server.start_grd_rdp()

        # successful execution
        self._reset_mocks()
        mock_stdout_stream = Mock()
        mock_stderr_stream = Mock()
        mock_journal.reset_mock()
        mock_journal.stream.side_effect = [mock_stdout_stream, mock_stderr_stream]
        mock_journal.LOG_INFO = journal.LOG_INFO
        mock_journal.LOG_ERR = journal.LOG_ERR
        mock_network.reset_mock()
        mock_startProgram.reset_mock()
        mock_startProgram.side_effect = None
        mock_grd_process = Mock()
        mock_startProgram.return_value = mock_grd_process
        mock_thread_manager.reset_mock()
        self.grd_server._handle_rdp_certificates.reset_mock()
        self.grd_server._find_network_address.reset_mock()

        self.grd_server.start_grd_rdp()

        self.grd_server._handle_rdp_certificates.assert_called_once()
        mock_network.wait_for_connectivity.assert_called_once()
        self.grd_server._find_network_address.assert_called_once()

        mock_journal.stream.assert_has_calls([
            call("gnome-remote-desktop", priority=journal.LOG_INFO),
            call("gnome-remote-desktop", priority=journal.LOG_ERR)
        ])
        mock_startProgram.assert_called_once_with(
            ["/usr/libexec/gnome-remote-desktop-daemon", "--headless"],
            stdout=mock_stdout_stream,
            stderr=mock_stderr_stream,
            env_add={"HOME": "/root"}
        )
        assert gnome_remote_desktop.grd_process is mock_grd_process
