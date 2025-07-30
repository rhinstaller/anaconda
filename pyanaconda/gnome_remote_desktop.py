#
# gnome_remote_desktop.py: GRD related installer functionality
#
# Copyright (C) 2024  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import socket
import sys
import time

from systemd import journal

from pyanaconda import network
from pyanaconda.anaconda_loggers import get_module_logger, get_stdout_logger
from pyanaconda.core import util
from pyanaconda.core.constants import THREAD_RDP_OBTAIN_HOSTNAME
from pyanaconda.core.i18n import _
from pyanaconda.core.threads import thread_manager
from pyanaconda.core.util import execWithRedirect, startProgram

stdoutLog = get_stdout_logger()
log = get_module_logger(__name__)

OPENSSL_BINARY_PATH = "/usr/bin/openssl"

GRD_RDP_CERT_DIR = "/root/.local/share/gnome-remote-desktop/"
GRD_RDP_CERT = "/root/.local/share/gnome-remote-desktop/rdp.crt"
GRD_RDP_CERT_KEY = "/root/.local/share/gnome-remote-desktop/rdp.key"

GRD_BINARY_PATH = "/usr/libexec/gnome-remote-desktop-daemon"
GRD_PID = None
GRD_LOG_FILE = "/tmp/gnome-remote-desktop.log"

grd_process = None

# partially based on: https://copr.fedorainfracloud.org/coprs/jadahl/headless-sessions/


def shutdown_server():
    """Try to shutdown running GNOME Remote Desktop instance

    Why is this function on the module level and not in the GRDServer class ?

    As the server needs to be killed from the exit handler, it would have
    to somehow get to the GRD instance. Like this, it can just kill
    it by calling a function of the GNOME Remote Desktop module, that
    has access to the GRD process.
    """

    if grd_process is None:
        log.error("Cannot shutdown GNOME Remote Desktop - process handle missing")
    else:
        try:
            grd_process.kill()
            log.info("The GNOME Remote Desktop session has been shut down.")
        except SystemError as e:
            log.error("Shutdown of the GNOME Remote Desktop session failed with exception:\n%s", e)


class GRDServer:

    def __init__(self, anaconda, root="/", ip=None,
                 rdp_username="", rdp_password=""):
        self.root = root
        self.ip = ip
        self.rdp_username = rdp_username
        self.rdp_password = rdp_password
        self.anaconda = anaconda
        self.log = get_stdout_logger()

        # check if we the needed dependencies for using the GNOME remote desktop
        # & abort the installation if not

        # start by checking we have openssl available
        if not os.path.exists(OPENSSL_BINARY_PATH):
            self._fail_with_error("No openssl binary found, can't generate certificates "
                                  "for GNOME remote desktop. Aborting.")

        # start by checking we have GNOME remote desktop available
        if not os.path.exists(GRD_BINARY_PATH):
            # we assume there that the main binary being present implies grdctl is there as well
            self._fail_with_error("GNOME remote desktop tooling is not available. Aborting.")

    def _fail_with_error(self, *args):
        """Kill Anaconda with with message for user.

        Send ipmi error message.
        """
        stdoutLog.critical(*args)
        util.ipmi_abort()
        sys.exit(1)

    def _handle_rdp_certificates(self):
        """Generate SSL certificate and use it for incoming RDP connection."""

        # then create folder for the certs
        os.makedirs(GRD_RDP_CERT_DIR)
        # generate the certs
        ret = execWithRedirect(OPENSSL_BINARY_PATH,
                               ["req", "-new",
                                "-newkey", "rsa:4096",
                                "-days", "720", "-nodes", "-x509",
                                "-subj", "/C=DE/ST=NONE/L=NONE/O=GNOME/CN=localhost",
                                "-out", GRD_RDP_CERT,
                                "-keyout", GRD_RDP_CERT_KEY]
                               )
        if ret != 0:
            self._fail_with_error(
                "Can't generate certificates for Gnome remote desktop. Aborting."
                )
        # tell GNOME remote desktop to use these certificates
        self._run_grdctl(["rdp", "set-tls-cert", GRD_RDP_CERT])
        self._run_grdctl(["rdp", "set-tls-key", GRD_RDP_CERT_KEY])

    def _set_rdp_username_and_password(self):
        """Set the RDP username and password."""
        self._run_grdctl(["rdp", "set-credentials", self.rdp_username, self.rdp_password])
        # disable view only mode
        self._run_grdctl(["rdp", "disable-view-only"])
        # also actually tell GNOME remote desktop that we (obviously) want to use RDP
        self._run_grdctl(["rdp", "enable"])

    def _find_network_address(self):
        """Find machine IP address, so we can show it to the user."""

        # Network may be slow. Try for 5 seconds
        tries = 5
        while tries:
            self.ip = network.get_first_ip_address()
            if self.ip:
                break
            time.sleep(1)
            tries -= 1

    def _get_hostname(self):
        """Start thread to obtain hostname from DNS server asynchronously.

        This can take a while so do not wait for the result just print it when available.
        """
        thread_manager.add_thread(name=THREAD_RDP_OBTAIN_HOSTNAME,
                                  target=self._get_hostname_in_thread,
                                  args=[self.ip, self.log]
                                  )

    @staticmethod
    def _get_hostname_in_thread(ip, stdout_log):
        """Obtain hostname from the DNS query.

        This call will be done from the thread to avoid situations where DNS is too slow or
        doesn't exists and we are waiting for the reply about 2 minutes.

        :raises: ValueError and socket.herror
        """
        try:
            hinfo = socket.gethostbyaddr(ip)
            if len(hinfo) == 3:
                # Consider as coming from a valid DNS record only if single IP is returned
                if len(hinfo[2]) == 1:
                    name = hinfo[0]
                    stdout_log.info(_("GNOME remote desktop RDP host name: %s"), name)

        except socket.herror as e:
            if ip.find(':') != -1:
                ipstr = "[%s]" % (ip,)
            else:
                ipstr = ip
            log.debug("Exception caught trying to get host name of %s: %s", ipstr, e)

    def _run_grdctl(self, argv):
        """Run grdctl in the correct environment.

        This is necessary, as grdctl requires $HOME to be pruned
        or else the call might not have the desired effect.
        """
        # we always run GRD in --headless mode
        base_argv = ["--headless"]
        # extend the base argv by the caller provided arguments
        combined_argv = base_argv + argv
        # make sure HOME is set to /root or else settings might not be saved
        if execWithRedirect("grdctl", combined_argv, env_add={"HOME": "/root"}) != 0:
            self._fail_with_error("Gnome remote desktop invocation failed!")

    def _start_grd_process(self):
        """Start the GNOME remote desktop process."""
        try:
            self.log.info("Starting GNOME remote desktop.")
            global grd_process
            # forward GRD stdout & stderr to Journal
            grd_stdout_stream = journal.stream("gnome-remote-desktop", priority=journal.LOG_INFO)
            grd_stderr_stream = journal.stream("gnome-remote-desktop", priority=journal.LOG_ERR)
            grd_process = startProgram([GRD_BINARY_PATH, "--headless"],
                                       stdout=grd_stdout_stream,
                                       stderr=grd_stderr_stream,
                                       env_add={"HOME": "/root"})
            self.log.info("GNOME remote desktop is now running.")
        except OSError:
            self._fail_with_error("Could not start GNOME remote desktop. Aborting.")

    def start_grd_rdp(self):
        # check if RDP user name & password are set
        if not self.rdp_password or not self.rdp_username:
            self._fail_with_error("RDP user name or password not set. Aborting.")

        self.log.info(_("Starting GNOME remote desktop in RDP mode..."))

        # looks like we have some valid credentials, lets generate certificates &
        # set the credentials
        self._handle_rdp_certificates()
        self.log.info(_("GNOME remote desktop RDP: SSL certificates generated & set"))
        self._set_rdp_username_and_password()
        self.log.info(_("GNOME remote desktop RDP: user name and password set"))

        # next try to find our IP address or even the hostname
        network.wait_for_connectivity()
        try:
            self._find_network_address()
        except (socket.herror, ValueError) as e:
            self._fail_with_error("GNOME remote desktop RDP: Could not find network address: %s",
                                  e)

        # Lets start GRD.
        self._start_grd_process()

        # Print connection information to user
        self.log.info(_("GNOME remote desktop RDP IP: %s"), self.ip)
        # Print hostname when available (run in separate thread to avoid blocking)
        self._get_hostname()
