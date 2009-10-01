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

import os, sys, string
import time
from snack import *
from constants import *
from constants_text import *
import network
import isys
import product
import socket
import subprocess

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

import logging
log = logging.getLogger("anaconda")
stdoutLog = logging.getLogger("anaconda.stdout")

class VncServer:

    def __init__(self, display="1", root="/", ip=None, name=None,
                desktop="Desktop", password="", vncconnecthost="",
                vncconnectport="", log_file="/tmp/vncserver.log",
                pw_file="/tmp/vncpassword", pw_init_file="/tmp/vncpassword.dat"):
        self.display = display
        self.root = root
        self.ip = ip
        self.name = name
        self.desktop = desktop
        self.password = password
        self.vncconnecthost = vncconnecthost
        self.vncconnectport = vncconnectport
        self.log_file = log_file
        self.pw_file = pw_file
        self.pw_init_file = pw_init_file
        self.connxinfo = None
        self.anaconda = None
        self.log = logging.getLogger("anaconda.stdout")

    def recoverVNCPassword(self):
        """Rescue the vncpassword from where loader left it 

        We are not to check for validity yet, if there is a file
        pass it to the variable, if there is not, set the var 
        to ''. We will check valididty later.
        """
        # see if there is a vnc password file
        try:
            pfile = open(self.pw_init_file, "r")
            self.password=pfile.readline().strip()
            pfile.close()
            os.unlink(self.pw_init_file)
        except:
            self.password=""

    def setVNCPassword(self):
        """Change the vnc server password. Output to file. """

        if len(self.password) == 0:
            self.setVNCParam("SecurityTypes", "None")
            self.setVNCParam("rfbauth","0")
            return

        # If there is a password the SecurityTypes = VncAuth for all connections.
        self.setVNCParam("SecurityTypes", "VncAuth")
        self.setVNCParam("rfbauth",self.pw_file)

        # password input combination.
        pwinput = "%s\n%s\n" % (self.password, self.password)
        vnccommand = [self.root+"/usr/bin/vncpasswd", self.pw_file]
        vncpswdo = subprocess.Popen(vnccommand, stdin=subprocess.PIPE, stdout=subprocess.PIPE)# We pipe the output
                                                                                              # so the user does not see it.
        (out, err) = vncpswdo.communicate(input=pwinput)
        return vncpswdo.returncode

    def initialize(self):
        """Here is were all the relative vars get initialized. """

        # see if we can sniff out network info
        netinfo = network.Network()

        devices = netinfo.netdevices
        active_devs = network.getActiveNetDevs()

        if active_devs != []:
            dev = devices[active_devs[0]]

            try:
                self.ip = isys.getIPAddress(dev.get("DEVICE"))
                log.info("ip of %s is %s" % (dev.get("DEVICE"), self.ip))

                if self.ip == "127.0.0.1" or self.ip == "::1":
                    self.ip = None
            except Exception, e:
                log.warning("Got an exception trying to get the self.ip addr "
                            "of %s: %s" % (dev.get("DEVICE"), e))
        else:
            self.ip = None

        self.name = network.getDefaultHostname(self.anaconda)
        ipstr = self.ip

        if self.ip.find(':') != -1:
            ipstr = "[%s]" % (self.ip,)

        if (self.name is not None) and (not self.name.startswith('localhost')) and (ipstr is not None):
            self.connxinfo = "%s:%s (%s)" % (socket.getfqdn(name=self.name), self.display, ipstr,)
        elif ipstr is not None:
            self.connxinfo = "%s:%s" % (ipstr, self.display,)
        else:
            self.connxinfo = None

        # figure out product info
        if self.name is not None:
            self.desktop = _("%(productName)s %(productVersion)s installation "
                             "on host %(name)s") \
                           % {'productName': product.productName,
                              'productVersion': product.productVersion,
                              'name': self.name}
        else:
            self.desktop = _("%(productName)s %(productVersion)s installation")\
                           % {'productName': product.productName,
                              'productVersion': product.productVersion}

    def setVNCParam(self, param, value):
        """Set a parameter in the Xvnc server. 

        Possible values for param and value. param=(values)
        SecurityTypes=(VncAuth,None)
        """
        vncconfigcommand = [self.root+"/usr/bin/vncconfig", "-display", ":%s"%self.display , "-set" , "%s=%s" %(param, value)]
        vncconfo = subprocess.Popen(vncconfigcommand)# we dont want output
        return vncconfo.returncode

    def openlogfile(self):
        try:
            err = os.open(self.log_file, os.O_RDWR | os.O_CREAT)
            if err < 0:
                sys.stderr.write("error opening %s\n", log)
                return None
            else:
                return err
        except:
                return None

    def connectToView(self):
        """Attempt to connect to self.vncconnecthost"""

        maxTries = 10
        self.log.info(_("Attempting to connect to vnc client on host %s...") % (self.vncconnecthost,))

        if self.vncconnectport != "":
            hostarg = self.vncconnecthost + ":" + self.vncconnectport
        else:
            hostarg = self.vncconnecthost

        vncconfigcommand = [self.root+"/usr/bin/vncconfig", "-display", ":%s"%self.display, "-connect", hostarg]

        for i in range(maxTries):
            vncconfp = subprocess.Popen(vncconfigcommand, stdout=subprocess.PIPE, stderr=subprocess.PIPE) # vncconfig process
            (out, err) = vncconfp.communicate()

            if err == '':
                self.log.info(_("Connected!"))
                return True
            elif err.startswith("connecting") and err.endswith("failed\n"):
                self.log.info(_("Will try to connect again in 15 seconds..."))
                time.sleep(15)
                continue
            else:
                log.critical(err)
                sys.exit(1)
        self.log.error(P_("Giving up attempting to connect after %d try!\n",
                          "Giving up attempting to connect after %d tries!\n",
                          maxTries) % (maxTries,))
        return False

    def VNCListen(self):
        """Put the server in listening mode.

        We dont really have to do anything for the server to listen :)
        """
        if self.connxinfo != None:
            self.log.info(_("Please manually connect your vnc client to %s to begin the install.") % (self.connxinfo,))
        else:
            self.log.info(_("Please manually connect your vnc client to begin the install."))

    def startServer(self):
        self.log.info(_("Starting VNC..."))

        # Lets call it from here for now.
        self.initialize()

        # Lets start the xvnc regardless of vncconnecthost and password.
        # We can change the configuration on the fly later.
        xvnccommand =  [ self.root + "/usr/bin/Xvnc", ":%s" % self.display, "-nevershared",
                        "-depth", "16", "-geometry", "800x600", "-br",
                        "IdleTimeout=0", "-auth", "/dev/null", "-once",
                        "DisconnectClients=false", "desktop=%s" % (self.desktop,),
                        "SecurityTypes=None"]
        try:
            xvncp = subprocess.Popen(xvnccommand, stdout=self.openlogfile(), stderr=subprocess.STDOUT)
        except:
            stdoutLog.critical("Could not start the VNC server.  Aborting.")
            sys.exit(1)

        # Lets give the xvnc time to initialize
        time.sleep(1)

        # Make sure it hasn't blown up
        if xvncp.poll() != None:
            sys.exit(1)
        else:
            self.log.info(_("The VNC server is now running."))

        # Lets look at the password stuff
        if self.password == "":
            pass
        elif len(self.password) < 6:
            self.changeVNCPasswdWindow()

        # Create the password file.
        self.setVNCPassword()

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
             sys.exit(1)

        # Lets try to configure the vnc server to whatever the user specified
        if self.vncconnecthost != "":
            connected = self.connectToView()
            if not connected:
                self.VNCListen()
        else:
            self.VNCListen()

        os.environ["DISPLAY"]=":%s" % self.display

    def changeVNCPasswdWindow(self):
        """ Change the password to a sane parameter.

        We ask user to input a password that len(password) > 6
        or password == ''. Have to find a way to put askVncWindow
        and this method together.
        """

        screen = SnackScreen()
        grid = GridFormHelp(screen, _("VNC Configuration"),"vnc", 1, 10)

        bb = ButtonBar(screen, (TEXT_OK_BUTTON,
                                (_("No password"), "nopass")))

        text = _("A password will prevent unauthorized listeners "
                 "connecting and monitoring your installation progress.  "
                 "Please enter a password to be used for the installation")
        grid.add(TextboxReflowed(40, text), 0, 0, (0, 0, 0, 1))

        entry1 = Entry (16, password = 1)
        entry2 = Entry (16, password = 1)
        passgrid = Grid (2, 2)
        passgrid.setField (Label (_("Password:")), 0, 0, (0, 0, 1, 0), anchorLeft = 1)
        passgrid.setField (Label (_("Password (confirm):")), 0, 1, (0, 0, 1, 0), anchorLeft = 1)
        passgrid.setField (entry1, 1, 0)
        passgrid.setField (entry2, 1, 1)
        grid.add (passgrid, 0, 1, (0, 0, 0, 1))

        grid.add(bb, 0, 8, (0, 1, 1, 0), growx = 1)

        while 1:
            res = grid.run()
            rc = bb.buttonPressed(res)

            if rc == "nopass":
                screen.finish()
                return ""
            else:
                pw = entry1.value()
                cf = entry2.value()
                if pw != cf:
                    ButtonChoiceWindow(screen, _("Password Mismatch"),
                                       _("The passwords you entered were "
                                         "different. Please try again."),
                                       buttons = [ TEXT_OK_BUTTON ],
                                       width = 50)
                elif len(pw) < 6:
                    ButtonChoiceWindow(screen, _("Password Length"),
                                       _("The password must be at least "
                                         "six characters long."),
                                       buttons = [ TEXT_OK_BUTTON ],
                                       width = 50)
                else:
                    screen.finish()
                    self.password = pw
                    return 

                entry1.set("")
                entry2.set("")
                continue
            continue

def askVncWindow(title = None, message = None):
    if not os.access('/usr/bin/Xvnc', os.X_OK):
        return -1

    if not network.hasActiveNetDev():
        return -1

    if not title:
        title = _("Unable to Start X")
    if not message:
        message = _("X was unable to start on your "
                    "machine.  Would you like to "
                    "start VNC to connect to "
                    "this computer from another "
                    "computer and perform a "
                    "graphical install or continue "
                    "with a text mode install?")

    screen = SnackScreen()
    vncpass = None
    vncconnect = 0

    STEP_MESSAGE = 0
    STEP_PASS = 1
    STEP_DONE = 3
    step = 0
    while step < STEP_DONE:
        if step == STEP_MESSAGE:
            button = ButtonChoiceWindow(screen, title, message,
                                        buttons = [ _("Start VNC"),
                                                    _("Use text mode") ])

	    if button == string.lower (_("Use text mode")):
                screen.finish()
                return -1
            else:
                step = STEP_PASS
                continue

        if step == STEP_PASS:
            grid = GridFormHelp(screen, _("VNC Configuration"),
                                "vnc", 1, 10)

            bb = ButtonBar(screen, (TEXT_OK_BUTTON,
                                    (_("No password"), "nopass"),
                                    TEXT_BACK_BUTTON))

            text = _("A password will prevent unauthorized listeners "
                     "connecting and monitoring your installation progress.  "
                     "Please enter a password to be used for the installation")
            grid.add(TextboxReflowed(40, text), 0, 0, (0, 0, 0, 1))

            entry1 = Entry (16, password = 1)
            entry2 = Entry (16, password = 1)
            passgrid = Grid (2, 2)
            passgrid.setField (Label (_("Password:")), 0, 0, (0, 0, 1, 0), anchorLeft = 1)
            passgrid.setField (Label (_("Password (confirm):")), 0, 1, (0, 0, 1, 0), anchorLeft = 1)
            passgrid.setField (entry1, 1, 0)
            passgrid.setField (entry2, 1, 1)
            grid.add (passgrid, 0, 1, (0, 0, 0, 1))

            grid.add(bb, 0, 8, (0, 1, 1, 0), growx = 1)

            while 1:
                res = grid.run()
                rc = bb.buttonPressed(res)

                if rc == TEXT_BACK_CHECK:
                    screen.popWindow()
                    step = STEP_MESSAGE
                    break
                elif rc == "nopass":
                    screen.finish()
                    return None
                else:
                    pw = entry1.value()
                    cf = entry2.value()
                    if pw != cf:
                        ButtonChoiceWindow(screen, _("Password Mismatch"),
                                           _("The passwords you entered were "
                                             "different. Please try again."),
                                           buttons = [ TEXT_OK_BUTTON ],
                                           width = 50)
                    elif len(pw) < 6:
                        ButtonChoiceWindow(screen, _("Password Length"),
                                           _("The password must be at least "
                                             "six characters long."),
                                           buttons = [ TEXT_OK_BUTTON ],
                                           width = 50)
                    else:
                        screen.finish()
                        return pw

                    entry1.set("")
                    entry2.set("")
                    continue
                continue

    screen.finish()
    return -1

if __name__ == "__main__":
    askVncWindow()
