#
# vnc.py: VNC related installer functionality
#
# Copyright (C) 2004, 2007  Red Hat, Inc.  All rights reserved.
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
from pyanaconda.core import util, constants
from pyanaconda.core.product import get_product_name, get_product_version
import socket
import subprocess

from pyanaconda.core.i18n import _, P_
from pyanaconda.modules.common.constants.objects import USER_INTERFACE
from pyanaconda.modules.common.constants.services import RUNTIME
from pyanaconda.modules.common.structures.secret import SecretData
from pyanaconda.modules.common.structures.vnc import VncData
from pyanaconda.ui.tui import tui_quit_callback
from pyanaconda.ui.tui.spokes.askvnc import VNCPassSpoke

from simpleline import App
from simpleline.render.screen_handler import ScreenHandler

from pyanaconda.anaconda_loggers import get_stdout_logger
stdoutLog = get_stdout_logger()

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

XVNC_BINARY_NAME = "Xvnc"


def shutdownServer():
    """Try to shutdown any running XVNC server

    Why is this function on the module level and not in the VncServer class ?

    As the server needs to be killed from the exit handler, it would have
    to somehow get to the VncServer instance. Like this, it can just kill
    it by calling a function of the vnc module.
    """
    try:
        util.execWithCapture("killall", [XVNC_BINARY_NAME], do_preexec=False)
        log.info("The XVNC server has been shut down.")
    except OSError as e:
        log.error("Shutdown of the XVNC server failed with exception:\n%s", e)


class VncServer(object):

    def __init__(self, root="/", ip=None, name=None,
                 password=SecretData(), vncconnecthost="",
                 vncconnectport="", log_file="/tmp/vncserver.log",
                 pw_file="/tmp/vncpassword", timeout=constants.X_TIMEOUT):
        self.root = root
        self.ip = ip
        self.name = name
        self.password = password
        self.vncconnecthost = vncconnecthost
        self.vncconnectport = vncconnectport
        self.log_file = log_file
        self.pw_file = pw_file
        self.timeout = timeout
        self.connxinfo = None
        self.anaconda = None
        self.log = get_stdout_logger()

        self.desktop = _("%(productName)s %(productVersion)s installation")\
                       % {'productName': get_product_name(),
                          'productVersion': get_product_version()}

    def setVNCPassword(self):
        """Set the vnc server password. Output to file. """
        password_string = "%s\n" % self.password.value

        # the -f option makes sure vncpasswd does not ask for the password again
        proc = util.startProgram(
            ["vncpasswd", "-f"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        out, err = proc.communicate(password_string.encode("utf-8"))

        if proc.returncode != 0:
            log.error("vncpasswd has failed with %d: %s", proc.returncode, err.decode("utf-8"))
            raise OSError("Unable to set the VNC password.")

        with open(self.pw_file, "wb") as pw_file:
            pw_file.write(out)

    def initialize(self):
        """Here is were all the relative vars get initialized. """

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

        if self.ip.find(':') != -1:
            ipstr = "[%s]" % (self.ip,)
        else:
            ipstr = self.ip

        try:
            hinfo = socket.gethostbyaddr(self.ip)
            if len(hinfo) == 3:
                # Consider as coming from a valid DNS record only if single IP is returned
                if len(hinfo[2]) == 1:
                    self.name = hinfo[0]
        except socket.herror as e:
            log.debug("Exception caught trying to get host name of %s: %s", ipstr, e)

        if self.name is not None and not self.name.startswith('localhost'):
            self.connxinfo = "%s:%s (%s:%s)" % (socket.getfqdn(name=self.name),
                                                constants.X_DISPLAY_NUMBER,
                                                ipstr,
                                                constants.X_DISPLAY_NUMBER)
            host = self.name
        elif ipstr is not None:
            self.connxinfo = "%s:%s" % (ipstr, constants.X_DISPLAY_NUMBER)
            host = ipstr
        else:
            self.connxinfo = None
            host = ""

        # figure out product info
        if host:
            self.desktop = _("%(productName)s %(productVersion)s installation "
                             "on host %(name)s") \
                           % {'productName': get_product_name(),
                              'productVersion': get_product_version(),
                              'name': host}

    def openlogfile(self):
        try:
            fd = os.open(self.log_file, os.O_RDWR | os.O_CREAT)
        except OSError as e:
            sys.stderr.write("error opening %s: %s\n", (self.log_file, e))
            fd = None

        return fd

    def connectToView(self):
        """Attempt to connect to self.vncconnecthost"""

        maxTries = 10
        self.log.info(_("Attempting to connect to vnc client on host %s..."), self.vncconnecthost)

        if self.vncconnectport != "":
            hostarg = self.vncconnecthost + ":" + self.vncconnectport
        else:
            hostarg = self.vncconnecthost

        vncconfigcommand = [self.root + "/usr/bin/vncconfig", "-display", ":%s" % constants.X_DISPLAY_NUMBER, "-connect", hostarg]

        for _i in range(maxTries):
            vncconfp = util.startProgram(vncconfigcommand, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # vncconfig process
            err = vncconfp.communicate()[1].decode("utf-8")

            if err == '':
                self.log.info(_("Connected!"))
                return True
            elif err.startswith("connecting") and err.endswith("failed\n"):
                self.log.info(_("Will try to connect again in 15 seconds..."))
                time.sleep(15)
                continue
            else:
                log.critical(err)
                util.ipmi_abort(scripts=self.anaconda.ksdata.scripts)
                sys.exit(1)
        self.log.error(P_("Giving up attempting to connect after %d try!\n",
                          "Giving up attempting to connect after %d tries!\n",
                          maxTries), maxTries)
        return False

    def startVncConfig(self):
        """Attempt to start vncconfig"""

        self.log.info(_("Attempting to start vncconfig"))

        vncconfigcommand = [self.root + "/usr/bin/vncconfig", "-nowin", "-display", ":%s" % constants.X_DISPLAY_NUMBER]

        # Use startProgram to run vncconfig in the background
        util.startProgram(vncconfigcommand, stdout=self.openlogfile(), stderr=subprocess.STDOUT)

    def VNCListen(self):
        """Put the server in listening mode.

        We dont really have to do anything for the server to listen :)
        """
        if self.connxinfo is not None:
            self.log.info(_("Please manually connect your vnc client to %s to begin the install."), self.connxinfo)
        else:
            self.log.info(_("Please manually connect your vnc client to IP-ADDRESS:%s "
                            "to begin the install. Switch to the shell (Ctrl-B 2) and "
                            "run 'ip addr' to find the IP-ADDRESS."), constants.X_DISPLAY_NUMBER)

    def startServer(self):
        self.log.info(_("Starting VNC..."))
        network.wait_for_connectivity()

        # Lets call it from here for now.
        try:
            self.initialize()
        except (socket.herror, ValueError) as e:
            stdoutLog.critical("Could not initialize the VNC server: %s", e)
            util.ipmi_abort(scripts=self.anaconda.ksdata.scripts)
            sys.exit(1)

        if self.password.value and (len(self.password.value) < 6 or len(self.password.value) > 8):
            self.changeVNCPasswdWindow()

        if not self.password.value:
            SecurityTypes = "None"
            rfbauth = "0"
        else:
            SecurityTypes = "VncAuth"
            rfbauth = self.pw_file
            # Create the password file.
            self.setVNCPassword()

        # Lets start the xvnc.
        xvnccommand = [XVNC_BINARY_NAME, ":%s" % constants.X_DISPLAY_NUMBER,
                       "-depth", "24", "-br",
                       "IdleTimeout=0", "-auth", "/dev/null", "-once",
                       "DisconnectClients=false", "desktop=%s" % (self.desktop,),
                       "SecurityTypes=%s" % SecurityTypes, "rfbauth=%s" % rfbauth]

        try:
            util.startX(xvnccommand, output_redirect=self.openlogfile(), timeout=self.timeout)
        except OSError:
            stdoutLog.critical("Could not start the VNC server.  Aborting.")
            util.ipmi_abort(scripts=self.anaconda.ksdata.scripts)
            sys.exit(1)

        self.log.info(_("The VNC server is now running."))

        # Lets tell the user what we are going to do.
        if self.vncconnecthost != "":
            self.log.warning(_("\n\nYou chose to connect to a listening vncviewer. \n"
                               "This does not require a password to be set.  If you \n"
                               "set a password, it will be used in case the connection \n"
                               "to the vncviewer is unsuccessful\n\n"))
        elif self.password.value == "":
            self.log.warning(_("\n\nWARNING!!! VNC server running with NO PASSWORD!\n"
                               "You can use the inst.vncpassword=PASSWORD boot option\n"
                               "if you would like to secure the server.\n\n"))
        elif self.password.value != "":
            self.log.warning(_("\n\nYou chose to execute vnc with a password. \n\n"))
        else:
            self.log.warning(_("\n\nUnknown Error.  Aborting. \n\n"))
            util.ipmi_abort(scripts=self.anaconda.ksdata.scripts)
            sys.exit(1)

        # Lets try to configure the vnc server to whatever the user specified
        if self.vncconnecthost != "":
            connected = self.connectToView()
            if not connected:
                self.VNCListen()
        else:
            self.VNCListen()

        # Start vncconfig for copy/paste
        self.startVncConfig()

    def changeVNCPasswdWindow(self):
        """ Change the password to a sane parameter.

        We ask user to input a password that (len(password) > 6
        and len(password) <= 8) or password == ''.
        """

        message = _("VNC password must be six to eight characters long.\n"
                    "Please enter a new one, or leave blank for no password.")
        App.initialize()
        loop = App.get_event_loop()
        loop.set_quit_callback(tui_quit_callback)
        ui_proxy = RUNTIME.get_proxy(USER_INTERFACE)
        vnc_data = VncData.from_structure(ui_proxy.Vnc)
        spoke = VNCPassSpoke(self.anaconda.ksdata, None, None, message, vnc_data)
        ScreenHandler.schedule_screen(spoke)
        App.run()

        vnc_data = VncData.from_structure(ui_proxy.Vnc)
        self.password = vnc_data.password
