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
import sys
import time
from pyanaconda import network
from pyanaconda.core import util
from pyanaconda.core.util import execWithCapture, startProgram
import socket

from pyanaconda.core.i18n import _

from pyanaconda.anaconda_loggers import get_stdout_logger
stdoutLog = get_stdout_logger()

from pyanaconda.anaconda_loggers import get_module_logger
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


class GRDServer(object):

    def __init__(self, anaconda, root="/", ip=None, name=None,
                 rdp_username="", rdp_password=""):
        self.root = root
        self.ip = ip
        self.rdp_username = rdp_username
        self.name = name
        self.rdp_password = rdp_password
        self.anaconda = anaconda
        self.log = get_stdout_logger()

        # check if we the needed dependencies for using the GNOME remote desktop
        # & abort the installation if not

        # start by checking we have openssl available
        if not os.path.exists(OPENSSL_BINARY_PATH):
            stdoutLog.critical("No openssl binary found, can't generate certificates "
                               "for GNOME remote desktop. Aborting.")
            util.ipmi_abort(scripts=self.anaconda.ksdata.scripts)
            sys.exit(1)

        # start by checking we have GNOME remote desktop available
        if not os.path.exists(GRD_BINARY_PATH):
            # we assume there that the main binary being present implies grdctl is there as well
            stdoutLog.critical("GNOME remote desktop tooling is not available. Aborting.")
            util.ipmi_abort(scripts=self.anaconda.ksdata.scripts)
            sys.exit(1)

    def _handle_rdp_certificates(self):
        """Generate SSL certificate and use it for incoming RDP connection."""

        # then create folder for the certs
        os.makedirs(GRD_RDP_CERT_DIR)
        # generate the certs
        execWithCapture(OPENSSL_BINARY_PATH,
                        ["req", "-new",
                         "-newkey", "rsa:4096",
                         "-days", "720", "-nodes", "-x509",
                         "-subj", "/C=DE/ST=NONE/L=NONE/O=GNOME/CN=localhost",
                         "-out", GRD_RDP_CERT,
                         "-keyout", GRD_RDP_CERT_KEY]
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

        if not self.ip:
            return

        # FIXME: resolve this somehow,
        # so it does not get stuck for 2 minutes in some VMs

        if self.ip.find(':') != -1:
            ipstr = "[%s]" % (self.ip,)
        else:
            ipstr = self.ip

        try:
            hinfo = socket.gethostbyaddr(self.ip)
            self.log.info(hinfo)
            if len(hinfo) == 3:
                # Consider as coming from a valid DNS record only if single IP is returned
                if len(hinfo[2]) == 1:
                    self.name = hinfo[0]
        except socket.herror as e:
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
        execWithCapture("grdctl", combined_argv, env_prune=['HOME'])

    def _open_grd_log_file(self):
        # FIXME: redirect to journal ?
        try:
            fd = os.open(GRD_LOG_FILE, os.O_RDWR | os.O_CREAT)
        except OSError as e:
            sys.stderr.write("error opening %s: %s\n", (GRD_LOG_FILE, e))
            fd = None

        return fd

    def _start_grd_process(self):
        """Start the GNOME remote desktop process."""
        try:
            self.log.info("Starting GNOME remote desktop.")
            global grd_process
            grd_process = startProgram([GRD_BINARY_PATH, "--headless"],
                                       stdout=self._open_grd_log_file(),
                                       env_prune=['HOME'])
            self.log.info("GNOME remote desktop is now running.")
        except OSError:
            stdoutLog.critical("Could not start GNOME remote desktop. Aborting.")
            util.ipmi_abort(scripts=self.anaconda.ksdata.scripts)
            sys.exit(1)

    def start_grd_rdp(self):
        # check if RDP user name & password are set
        if not self.rdp_password or not self.rdp_username:
            stdoutLog.critical("RDP user name or password not set. Aborting.")
            util.ipmi_abort(scripts=self.anaconda.ksdata.scripts)
            sys.exit(1)

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
            self.log.info(_("GNOME remote desktop RDP IP: %s"), self.ip)
            self.log.info(_("GNOME remote desktop RDP host name: %s"), self.name)
        except (socket.herror, ValueError) as e:
            stdoutLog.critical("GNOME remote desktop RDP: Could not find network address: %s", e)
            util.ipmi_abort(scripts=self.anaconda.ksdata.scripts)
            sys.exit(1)

        # Lets start GRD.
        self._start_grd_process()
