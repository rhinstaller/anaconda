#
# Copyright (C) 2023  Red Hat, Inc.
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
import unittest
import pytest
import tempfile
import os

from meh.ui.text import TextIntf

from pyanaconda.ui.webui import CockpitUserInterface, FIREFOX_THEME_DEFAULT
from unittest.mock import Mock, patch
from pyanaconda.core.constants import PAYLOAD_TYPE_DNF, PAYLOAD_TYPE_LIVE_IMAGE


class SimpleWebUITestCase(unittest.TestCase):
    """Simple test case for Web UI.

    The goal of this test is to test execution of the UI behaves as desired.
    """
    def setUp(self):
        self.intf = CockpitUserInterface(None, None, 0)

    def _prepare_for_live_testing(self,
                                  pid_file,
                                  backend_file,
                                  pid_content="",
                                  remote=0):
        # prepare UI interface class
        self.intf = CockpitUserInterface(None, None, remote)
        self.intf._backend_ready_flag_file = backend_file

        open(backend_file, "wt").close()

        # Value could be None
        if pid_file:
            self.intf._viewer_pid_file = pid_file
            # wrote pid if requested
            if pid_content:
                with open(pid_file, "wt") as f:
                    f.write(pid_content)

    def test_webui_defaults(self):
        """Test that webui interface has correct defaults."""
        assert isinstance(self.intf.meh_interface, TextIntf)

        assert self.intf.tty_num == 6

        # Not implemented
        assert self.intf.showYesNoQuestion("Implemented by browser") is False

    @patch("pyanaconda.ui.webui.CockpitUserInterface._print_message")
    def test_error_propagation(self, mocked_print_message):
        """Test that webui prints erorr to the console.

        This gets then propagated by service to journal.
        """
        self.intf.showError("My Error")
        mocked_print_message.assert_called_once_with("My Error")

        mocked_print_message.reset_mock()
        self.intf.showDetailedError("My detailed error", "Such a detail!")
        mocked_print_message.assert_called_once_with("My detailed error\n\nSuch a detail!""")

    def test_setup(self):
        """Test webui setup call."""
        # test not DNF payload type works fine
        mocked_payload = Mock()
        mocked_payload.type = PAYLOAD_TYPE_LIVE_IMAGE

        self.intf = CockpitUserInterface(None, mocked_payload, 0)
        self.intf.setup(None)


        # test DNF payload raises error because it's not yet implemented
        mocked_payload.type = PAYLOAD_TYPE_DNF
        self.intf = CockpitUserInterface(None, mocked_payload, 0)
        with pytest.raises(ValueError):
            self.intf.setup(None)

    def test_backend_ready_file(self):
        """Test webui correctly create and remove beackend ready flag file."""

        with tempfile.TemporaryDirectory() as fd:
            backend_file = os.path.join(fd, "backend_ready")
            self._prepare_for_live_testing(None, backend_file, remote=1)

            def test_flag_file():
                assert os.path.exists(backend_file) is True

            self.intf._run_webui = test_flag_file
            self.intf.run()

            assert os.path.exists(backend_file) is False

    @patch("pyanaconda.ui.webui.startProgram")
    @patch("pyanaconda.ui.webui.conf")
    def test_run_not_on_live(self, mocked_conf, mocked_startProgram):
        """Test webui run call on boot iso."""
        # Execution is different for boot.iso then live environment
        mocked_conf.system.provides_liveuser = False
        mocked_process = Mock()
        mocked_process.pid = 12345
        mocked_startProgram.return_value = mocked_process

        with tempfile.TemporaryDirectory() as fd:
            pid_file = os.path.join(fd, "anaconda.pid")
            backend_file = os.path.join(fd, "backend_ready")
            self._prepare_for_live_testing(pid_file, backend_file, remote=1)
            self.intf.run()

            mocked_startProgram.assert_called_once_with(["/usr/libexec/webui-desktop",
                                                         "-t", FIREFOX_THEME_DEFAULT, "-r", "1",
                                                         "/cockpit/@localhost/anaconda-webui/index.html"],
                                                        reset_lang=False)
            # check if backend flag file was removed after finish of run method
            assert os.path.exists(backend_file) is False

            with open(pid_file, "rt") as f:
                assert f.readlines() == ["12345"]

            mocked_process.wait.assert_called_once()


        # test with disabled remote
        mocked_startProgram.reset_mock()
        mocked_process.reset_mock()
        mocked_startProgram.return_value = mocked_process
        with tempfile.TemporaryDirectory() as fd:
            pid_file = os.path.join(fd, "anaconda.pid")
            backend_file = os.path.join(fd, "backend_ready")
            self._prepare_for_live_testing(pid_file, backend_file)
            self.intf.run()

            mocked_startProgram.assert_called_once_with(["/usr/libexec/webui-desktop",
                                                         "-t", FIREFOX_THEME_DEFAULT, "-r", "0",
                                                         "/cockpit/@localhost/anaconda-webui/index.html"],
                                                        reset_lang=False)
            # check if backend flag file was removed after finish of run method
            assert os.path.exists(backend_file) is False

            with open(pid_file, "rt") as f:
                assert f.readlines() == ["12345"]

            mocked_process.wait.assert_called_once()

    @patch("pyanaconda.ui.webui.PidWatcher.watch_process")
    @patch("pyanaconda.ui.webui.create_main_loop")
    @patch("pyanaconda.ui.webui.conf")
    def test_run_on_live_success(self, mocked_conf, mocked_create_main_loop, mocked_watch_process):
        """Test webui run call on live environment."""
        # Execution is different for live because we need to start FF early as possible
        mocked_conf.system.provides_liveuser = True
        mocked_main_loop = Mock()

        # Test on Live media
        mocked_watch_process.reset_mock()
        mocked_create_main_loop.reset_mock()
        mocked_create_main_loop.return_value = mocked_main_loop
        mocked_main_loop.reset_mock()
        with tempfile.TemporaryDirectory() as fd:
            pid_file = os.path.join(fd, "anaconda.pid")
            backend_file = os.path.join(fd, "backend_ready")
            self._prepare_for_live_testing(pid_file, backend_file, pid_content="11111")
            self.intf.run()

            # check if backend flag file was removed after finish of run method
            assert os.path.exists(backend_file) is False

            # check that callback is correctly set
            mocked_watch_process.assert_called_once_with(11111, self.intf._webui_desktop_closed)
            mocked_create_main_loop.assert_called_once()
            mocked_main_loop.run.assert_called_once()

            # test quit callbacks by calling them (simple tests avoiding execution of the main loop)
            # test webui callback execution - simulates closing the viewer app
            self.intf._webui_desktop_closed(11111, 0)
            mocked_main_loop.quit.assert_called_once()

            # test webui callback bad status - simulates crash of the viewer app
            mocked_main_loop.reset_mock()
            self.intf._webui_desktop_closed(11111, 1)
            mocked_main_loop.quit.assert_called_once()

    @patch("pyanaconda.ui.webui.PidWatcher.watch_process")
    @patch("pyanaconda.ui.webui.create_main_loop")
    @patch("pyanaconda.ui.webui.conf")
    def test_run_on_live_failure(self, mocked_conf, mocked_create_main_loop, mocked_watch_process):
        """Test webui run call on live environment."""
        mocked_conf.system.provides_liveuser = True
        mocked_main_loop = Mock()

        # Test pid file doesn't exists
        mocked_watch_process.reset_mock()
        mocked_create_main_loop.reset_mock()
        mocked_create_main_loop.return_value = mocked_main_loop
        mocked_main_loop.reset_mock()
        with tempfile.TemporaryDirectory() as fd:
            pid_file = os.path.join(fd, "anaconda.pid")
            backend_file = os.path.join(fd, "backend_ready")
            self._prepare_for_live_testing(pid_file, backend_file)
            with pytest.raises(FileNotFoundError):
                self.intf.run()

            # check if backend flag file was removed after finish of run method
            assert os.path.exists(backend_file) is False

            mocked_watch_process.assert_not_called()
            mocked_create_main_loop.assert_not_called()

        # Test empty pid file
        mocked_watch_process.reset_mock()
        mocked_create_main_loop.reset_mock()
        mocked_create_main_loop.return_value = mocked_main_loop
        mocked_main_loop.reset_mock()
        with tempfile.TemporaryDirectory() as fd:
            pid_file = os.path.join(fd, "anaconda.pid")
            backend_file = os.path.join(fd, "backend_ready")
            open(pid_file, "wt").close()
            self._prepare_for_live_testing(pid_file, backend_file)
            with pytest.raises(ValueError):
                self.intf.run()

            # check if backend flag file was removed after finish of run method
            assert os.path.exists(backend_file) is False

            mocked_watch_process.assert_not_called()
            mocked_create_main_loop.assert_not_called()

        # Test negative pid
        mocked_watch_process.reset_mock()
        mocked_create_main_loop.reset_mock()
        mocked_create_main_loop.return_value = mocked_main_loop
        mocked_main_loop.reset_mock()
        with tempfile.TemporaryDirectory() as fd:
            pid_file = os.path.join(fd, "anaconda.pid")
            backend_file = os.path.join(fd, "backend_ready")
            self._prepare_for_live_testing(pid_file, backend_file, pid_content="-20")

            with pytest.raises(ValueError):
                self.intf.run()

            # check if backend flag file was removed after finish of run method
            assert os.path.exists(backend_file) is False

            mocked_watch_process.assert_not_called()
            mocked_create_main_loop.assert_not_called()

        # Test bad value pid
        mocked_watch_process.reset_mock()
        mocked_create_main_loop.reset_mock()
        mocked_create_main_loop.return_value = mocked_main_loop
        mocked_main_loop.reset_mock()
        with tempfile.TemporaryDirectory() as fd:
            pid_file = os.path.join(fd, "anaconda.pid")
            backend_file = os.path.join(fd, "backend_ready")
            self._prepare_for_live_testing(pid_file, backend_file, pid_content="not-a-number")

            with pytest.raises(ValueError):
                self.intf.run()

            # check if backend flag file was removed after finish of run method
            assert os.path.exists(backend_file) is False

            mocked_watch_process.assert_not_called()
            mocked_create_main_loop.assert_not_called()
