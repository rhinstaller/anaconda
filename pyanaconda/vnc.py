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
# Author(s): Jeremy Katz <katzj@redhat.com>
#

import os, sys
import time
from pyanaconda import constants, network, product, iutil
import socket
import subprocess
import dbus

from pyanaconda.i18n import _, P_
from pyanaconda.ui.tui.simpleline import App
from pyanaconda.ui.tui.spokes.askvnc import VNCPassSpoke

import logging
log = logging.getLogger("anaconda")
stdoutLog = logging.getLogger("anaconda.stdout")

XVNC_BINARY_NAME = "Xvnc"


def shutdownServer():
    """Try to shutdown any running XVNC server

    Why is this function on the module level and not in the VncServer class ?

    As the server needs to be killed from the exit handler, it would have
    to somehow get to the VncServer instance. Like this, it can just kill
    it by calling a function of the vnc module.
    """
    try:
        iutil.execWithCapture("killall", [XVNC_BINARY_NAME])
        log.info("The XVNC server has been shut down.")
    except OSError as e:
        log.error("Shutdown of the XVNC server failed with exception:\n%s", e)


class VncServer:

    def __init__(self, root="/", ip=None, name=None,
                password="", vncconnecthost="",
                vncconnectport="", log_file="/tmp/vncserver.log",
                pw_file="/tmp/vncpassword"):
        self.root = root
        self.ip = ip
        self.name = name
        self.password = password
        self.vncconnecthost = vncconnecthost
        self.vncconnectport = vncconnectport
        self.log_file = log_file
        self.pw_file = pw_file
        self.connxinfo = None
        self.anaconda = None
        self.log = logging.getLogger("anaconda.stdout")

        self.desktop = _("%(productName)s %(productVersion)s installation")\
                       % {'productName': product.productName,
                          'productVersion': product.productVersion}

    def setVNCPassword(self):
        """Set the vnc server password. Output to file. """

        r, w = os.pipe()
        password_string = "%s\n" % self.password
        iutil.eintr_retry_call(os.write, w, password_string.encode("utf-8"))

        with open(self.pw_file, "wb") as pw_file:
            # the -f option makes sure vncpasswd does not ask for the password again
            rc = iutil.execWithRedirect("vncpasswd", ["-f"],
                    stdin=r, stdout=pw_file, binary_output=True, log_output=False)

            iutil.eintr_retry_call(os.close, r)
            iutil.eintr_retry_call(os.close, w)

        return rc

    def initialize(self):
        """Here is were all the relative vars get initialized. """

        # Network may be slow. Try for 5 seconds
        tries = 5
        while tries:
            self.ip = network.getFirstRealIP()
            if self.ip:
                break
            time.sleep(1)
            tries -= 1

        if not self.ip:
            return

        ipstr = self.ip
        try:
            hinfo = socket.gethostbyaddr(ipstr)
        except socket.herror as e:
            log.debug("Exception caught trying to get host name of %s: %s", ipstr, e)
            self.name = network.getHostname()
        else:
            if len(hinfo) == 3:
                self.name = hinfo[0]

        if self.ip.find(':') != -1:
            ipstr = "[%s]" % (self.ip,)

        name_ips = [i[4][0] for i in socket.getaddrinfo(self.name, 0)]
        if self.name is not None and not self.name.startswith('localhost') \
           and ipstr is not None and self.ip in name_ips:
            self.connxinfo = "%s:%s (%s:%s)" % \
                    (socket.getfqdn(name=self.name), constants.X_DISPLAY_NUMBER,
                     ipstr, constants.X_DISPLAY_NUMBER)
        elif ipstr is not None:
            self.connxinfo = "%s:%s" % (ipstr, constants.X_DISPLAY_NUMBER)
        else:
            self.connxinfo = None

        # figure out product info
        if self.name is not None:
            self.desktop = _("%(productName)s %(productVersion)s installation "
                             "on host %(name)s") \
                           % {'productName': product.productName,
                              'productVersion': product.productVersion,
                              'name': self.name}

    def openlogfile(self):
        try:
            fd = iutil.eintr_retry_call(os.open, self.log_file, os.O_RDWR | os.O_CREAT)
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

        vncconfigcommand = [self.root+"/usr/bin/vncconfig", "-display", ":%s" % constants.X_DISPLAY_NUMBER, "-connect", hostarg]

        for _i in range(maxTries):
            vncconfp = iutil.startProgram(vncconfigcommand, stdout=subprocess.PIPE, stderr=subprocess.PIPE) # vncconfig process
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
                iutil.ipmi_report(constants.IPMI_ABORTED)
                sys.exit(1)
        self.log.error(P_("Giving up attempting to connect after %d try!\n",
                          "Giving up attempting to connect after %d tries!\n",
                          maxTries), maxTries)
        return False

    def startVncConfig(self):
        """Attempt to start vncconfig"""

        self.log.info(_("Attempting to start vncconfig"))

        vncconfigcommand = [self.root+"/usr/bin/vncconfig", "-nowin", "-display", ":%s" % constants.X_DISPLAY_NUMBER]

        # Use startProgram to run vncconfig in the background
        iutil.startProgram(vncconfigcommand, stdout=self.openlogfile(), stderr=subprocess.STDOUT)

    def VNCListen(self):
        """Put the server in listening mode.

        We dont really have to do anything for the server to listen :)
        """
        if self.connxinfo != None:
            self.log.info(_("Please manually connect your vnc client to %s to begin the install."), self.connxinfo)
        else:
            self.log.info(_("Please manually connect your vnc client to <IP ADDRESS>:%s "
                            "to begin the install. Switch to the shell (Ctrl-B 2) and "
                            "run 'ip addr' to find the <IP ADDRESS>."), constants.X_DISPLAY_NUMBER)

    def startServer(self):
        self.log.info(_("Starting VNC..."))
        network.wait_for_connectivity()

        # Lets call it from here for now.
        try:
            self.initialize()
        except (socket.herror, dbus.DBusException, ValueError) as e:
            stdoutLog.critical("Could not initialize the VNC server: %s", e)
            iutil.ipmi_report(constants.IPMI_ABORTED)
            sys.exit(1)

        if self.password and (len(self.password) < 6 or len(self.password) > 8):
            self.changeVNCPasswdWindow()

        if not self.password:
            SecurityTypes = "None"
            rfbauth = "0"
        else:
            SecurityTypes = "VncAuth"
            rfbauth = self.pw_file
            # Create the password file.
            self.setVNCPassword()

        # Lets start the xvnc.
        xvnccommand = [XVNC_BINARY_NAME, ":%s" % constants.X_DISPLAY_NUMBER,
                       "-depth", "16", "-br",
                       "IdleTimeout=0", "-auth", "/dev/null", "-once",
                       "DisconnectClients=false", "desktop=%s" % (self.desktop,),
                       "SecurityTypes=%s" % SecurityTypes, "rfbauth=%s" % rfbauth]

        try:
            iutil.startX(xvnccommand, output_redirect=self.openlogfile())
        except OSError:
            stdoutLog.critical("Could not start the VNC server.  Aborting.")
            iutil.ipmi_report(constants.IPMI_ABORTED)
            sys.exit(1)

        self.log.info(_("The VNC server is now running."))

        # Lets tell the user what we are going to do.
        if self.vncconnecthost != "":
            self.log.warning(_("\n\nYou chose to connect to a listening vncviewer. \n"
                                "This does not require a password to be set.  If you \n"
                                "set a password, it will be used in case the connection \n"
                                "to the vncviewer is unsuccessful\n\n"))
        elif self.password == "":
            self.log.warning(_("\n\nWARNING!!! VNC server running with NO PASSWORD!\n"
                                "You can use the vncpassword=<password> boot option\n"
                                "if you would like to secure the server.\n\n"))
        elif self.password != "":
            self.log.warning(_("\n\nYou chose to execute vnc with a password. \n\n"))
        else:
            self.log.warning(_("\n\nUnknown Error.  Aborting. \n\n"))
            iutil.ipmi_report(constants.IPMI_ABORTED)
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
        app = App("VNC PASSWORD")
        spoke = VNCPassSpoke(app, self.anaconda.ksdata, None, None, None,
                             message)
        app.schedule_screen(spoke)
        app.run()

        self.password = self.anaconda.ksdata.vnc.password
