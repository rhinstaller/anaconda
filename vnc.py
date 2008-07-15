#
# vnc.py: VNC related installer functionality
#
# Copyright 2004,2007 Red Hat, Inc.
#
# Jeremy Katz <katzj@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os, sys, string
import time
from snack import *
from constants_text import *
from rhpl.translate import _, N_
import network
import isys
import product
import iutil

import logging
log = logging.getLogger("anaconda")

# return -1 to use text mode, None for no vncpass, or vncpass otherwise
def askVncWindow(title = None, message = None):
    if not os.access('/usr/bin/Xvnc', os.X_OK):
        return -1

    if network.hasActiveNetDev() == False:
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
                                        buttons = [ _("Use text mode"),
                                                    _("Start VNC") ])

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

def getVNCPassword():
    # see if there is a vnc password file
    try:
        pfile = open("/tmp/vncpassword.dat", "r")
        vncpassword=pfile.readline().strip()
        pfile.close()
        os.unlink("/tmp/vncpassword.dat")
    except:
        vncpassword=""
        pass

    # check length of vnc password
    if vncpassword != "" and len(vncpassword) < 6:
        screen = SnackScreen()
        ButtonChoiceWindow(screen, _('VNC Password Error'),
                           _('You need to specify a vnc password of at least 6 characters long.\n\n'
    		     'Press <return> to reboot your system.\n'),
    		   buttons = (_("OK"),))
        screen.finish()
        sys.exit(0)

    return vncpassword

# startup vnc X server
def startVNCServer(vncpassword="", root='/', vncconnecthost="",
		   vncconnectport="", vncStartedCB=None):

    stdoutLog = logging.getLogger("anaconda.stdout")
    
    def set_vnc_password(root, passwd, passwd_file):
	(pid, fd) = os.forkpty()

	if not pid:
	    os.execv(root + "/usr/bin/vncpasswd", [root + "/usr/bin/vncpasswd", passwd_file])
	    sys.exit(1)

	# read password prompt
	os.read(fd, 1000)

	# write password
	os.write(fd, passwd + "\n")

	# read challenge again, and newline
	os.read(fd, 1000)
	os.read(fd, 1000)

	# write password again
	os.write(fd, passwd + "\n")

	# read remaining output
	os.read(fd, 1000)

	# wait for status
	try:
	    (pid, status) = os.waitpid(pid, 0)
	except OSError, (errno, msg):
	    print __name__, "waitpid:", msg

	return status

    stdoutLog.info(_("Starting VNC..."))

    # figure out host info
    connxinfo = None
    srvname = None
    try:
	import network

	# try to load /tmp/netinfo and see if we can sniff out network info
	netinfo = network.Network()
	srvname = None

        # If we have a real hostname that resolves against configured DNS
        # servers, use that for the name to connect to.
        if netinfo.hostname != "localhost.localdomain" and netinfo.lookupHostname() is not None:
	    srvname = netinfo.hostname
	else:
            # Otherwise, look for the first configured interface and use its
            # IP address for the name to connect to.
            dev = netinfo.getFirstDeviceName()

            try:
                ip = isys.getIPAddress(dev)
                log.info("ip of %s is %s" % (dev, ip))
            except Exception, e:
                log.warning("Got an exception trying to get the ip addr "
                            "of %s: %s" % (dev, e))

            if ip != "127.0.0.1" and ip is not None:
                srvname = ip
            else:
                # If we get here and there's no valid IP address, just use the
                # hostname and hope for the best (better than displaying nothing)
                srvname = netinfo.hostname

	if srvname is not None:
	    connxinfo = "%s:1" % (srvname,)

    except:
	log.error("Unable to determine VNC server network info")
	
    # figure out product info
    if srvname is not None:
	desktopname = _("%s %s installation on host %s") % (product.productName, product.productVersion, srvname)
    else:
	desktopname = _("%s %s installation") % (product.productName, product.productVersion)

    vncpid = os.fork()

    if not vncpid:
	args = [ root + "/usr/bin/Xvnc", ":1", "-nevershared",
		 "-depth", "16", "-geometry", "800x600", "-br",
		 "IdleTimeout=0", "-auth", "/dev/null", "-once",
		 "DisconnectClients=false", "desktop=%s" % (desktopname,)]

	# set passwd if necessary
        if vncpassword != "":
	    try:
		rc = set_vnc_password(root, vncpassword, "/tmp/vncpasswd_file")
	    except Exception, e:
		stdoutLog.error("Unknown exception setting vnc password.")
		log.error("Exception was: %s" %(e,))
		rc = 1

	    if rc:
		stdoutLog.warning(_("Unable to set vnc password - using no password!"))
		stdoutLog.warning(_("Make sure your password is at least 6 characters in length."))
	    else:
		args = args + ["-rfbauth", "/tmp/vncpasswd_file"]
	else:
	    # needed if no password specified
	    args = args + ["SecurityTypes=None",]
			     
	tmplogFile = "/tmp/vncserver.log"
	try:
	    err = os.open(tmplogFile, os.O_RDWR | os.O_CREAT)
	    if err < 0:
		sys.stderr.write("error opening %s\n", tmplogFile)
	    else:
		os.dup2(err, 2)
		os.close(err)
	except:
	    # oh well
	    pass

	os.execv(args[0], args)
	sys.exit (1)

    if vncpassword == "":
	stdoutLog.warning(_("\n\nWARNING!!! VNC server running with NO PASSWORD!\n"
			 "You can use the vncpassword=<password> boot option\n"
			 "if you would like to secure the server.\n\n"))
	
    stdoutLog.info(_("The VNC server is now running."))

    if vncconnecthost != "":
	stdoutLog.info(_("Attempting to connect to vnc client on host %s...") % (vncconnecthost,))
	
	hostarg = vncconnecthost
        if vncconnectport != "":
	    hostarg = hostarg + ":" + vncconnectport
	    
	argv = ["-display", ":1", "-connect", hostarg]
	ntries = 0
	while 1:
            output = iutil.execWithCapture("/usr/bin/vncconfig", argv)

            if output == "":
                stdoutLog.info(_("Connected!"))
                break
            elif output.startswith("connecting") and output.endswith("failed\n"):
		ntries += 1
		if ntries > 50:
		    stdoutLog.error(_("Giving up attempting to connect after 50 tries!\n"))
		    if connxinfo is not None:
			stdoutLog.info(_("Please manually connect your vnc client to %s to begin the install.") % (connxinfo,))
		    else:	    
			stdoutLog.info(_("Please manually connect your vnc client to begin the install."))
		    break
		    
		stdoutLog.info(output)
		stdoutLog.info(_("Will try to connect again in 15 seconds..."))
		time.sleep(15)
		continue
	    else:
                stdoutLog.critical(output)
	        sys.exit(1)
    else:
	if connxinfo is not None:
	    stdoutLog.info(_("Please connect to %s to begin the install...") % (connxinfo,))
	else:
	    stdoutLog.info(_("Please connect to begin the install..."))

    os.environ["DISPLAY"]=":1"

    if vncStartedCB:
        vncStartedCB()

if __name__ == "__main__":
    askVncWindow()
