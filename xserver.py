#
# xserver.py - initial xserver startup for GUI mode.
#
# Matt Wilson <msw@redhat.com>
# Brent Fox <bfox@redhat.com>
#
# Copyright 1999-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os
import string
import kudzu
import isys
import sys
import time

from flags import flags

from snack import *
from constants_text import *
from mouse_text import MouseWindow, MouseDeviceWindow

from rhpl.translate import _
from rhpl.xhwstate import *
from rhpl.log import log

def mouseWindow(mouse):
    screen = SnackScreen()

    STEP_MESSAGE = 0
    STEP_TYPE = 1
    STEP_DEVICE = 2
    STEP_DONE = 3
    step = 0
    while step < STEP_DONE:
        if step == STEP_MESSAGE:
            button = ButtonChoiceWindow(screen, _("Mouse Not Detected"),
                            _("Your mouse was not automatically "
                              "detected.  To proceed in the graphical "
                              "installation mode, please proceed to "
                              "the next screen and provide your mouse "
                              "information. You may also use text mode "
                              "installation which does not require a mouse."),
                              buttons = [ _("OK"), _("Use text mode") ])
            if button == string.lower (_("Use text mode")):
		screen.finish ()
                return 0
            else:
                step = STEP_TYPE
                continue

        if step == STEP_TYPE:
            rc = MouseWindow()(screen, mouse)
            if rc == INSTALL_BACK:
                step = STEP_MESSAGE
                continue
            else:
                step = STEP_DEVICE
                continue

        if step == STEP_DEVICE:
            rc = MouseDeviceWindow()(screen, mouse)
            if rc == INSTALL_BACK:
                step = STEP_TYPE
                continue
            else:
                step = STEP_DONE
                continue
    screen.finish()
    return 1

# start miniWM
def startMiniWM(root='/'):
    childpid = os.fork()
    if not childpid:
	args = [root + '/usr/bin/mini-wm', '--display', ':1']
	os.execv(args[0], args)
	sys.exit (1)

    return childpid
	

# start X server for install process ONLY
def startX(resolution, video, monitor, mouse, keyboard):
    os.environ['DISPLAY'] = ':1'
    serverPath = None

    attempt = 'PROBED'

    failed = 1
    next_attempt = None
    while next_attempt != 'END':
        card = None

        if attempt == 'PROBED':
            if video.primaryCard():
                print _("Attempting to start native X server")
                card = video.primaryCard().getDevID()
            else:
                card = None
            next_attempt = 'VESA'
	elif attempt == 'VESA':
            if video.primaryCard():
                print _("Attempting to start VESA driver X server")
		vram = video.primaryCard().getVideoRam()
		if vram:
                    card = "VESA driver (generic)"
		else:
		    card = None
            else:
                card = None
            next_attempt = 'END'
        else:
            print "Got off end somehow!"
            break

	if card:
	    #
	    # XXX - assuming 'XFree86' is the binary for server
	    #
	    servername = 'XFree86'
            serverPath = '/usr/X11R6/bin/' + servername

            if os.access (serverPath, os.X_OK):
                try:
		    hwstate = XF86HardwareState(defcard=video,
						defmon=monitor,
						probeflags=XF86HW_PROBE_NONE)
		    hwstate.set_resolution(resolution)
		    hwstate.set_videocard_card(card)
		    testx(hwstate, mouse, keyboard)

                    failed = 0
                    break
            
                except (RuntimeError, IOError):
                    pass

        attempt = next_attempt
        
    #--If original server isn't there...send them to text mode
    if failed:
        raise RuntimeError, "No X server binaries found to run"
    
    return hwstate


def testx(hwstate, mouse, keyboard):
    try:
	server = writeXConfigAndRunX(hwstate, mouse, keyboard,
			    serverflags = [':1', 'vt7', '-s', '1440',
					   '-terminate', '-dpms', '-v',
					   '-ac', '-nolisten', 'tcp'],
			    standalone = 1)
    except:
 	import traceback
	server = None
 	(type, value, tb) = sys.exc_info()
 	list = traceback.format_exception (type, value, tb)
 	text = string.joinfields (list, "")
 	print text

    # give time for the server to fail (if it is going to fail...)
    # FIXME: Should find out if X server is already running
    # otherwise with NFS installs the X server may be still being
    # fetched from the network while we already continue to run
    if not server:
        sys.stderr.write("X SERVER FAILED");
        raise RuntimeError, "X server failed to start"

    count = 0

    sys.stdout.write(_("Waiting for X server to start...log located in /tmp/X.log\n"))
    sys.stdout.flush()

    for i in range(5):
        time.sleep(1)
        sys.stdout.write("%s..." % (i+1))
        sys.stdout.flush()
        
    while count < 60:
	sys.stdout.write(".")
	sys.stdout.flush()
        pid = 0
        try:
            pid, status = os.waitpid (server, os.WNOHANG)
        except OSError, (errno, msg):
            print __name__, "waitpid:", msg
	if pid:
	    sys.stderr.write("X SERVER FAILED");
	    raise RuntimeError, "X server failed to start"
	try:
	    os.stat ("/tmp/.X11-unix/X1")
	    break
	except OSError:
	    pass
	time.sleep(1)
	count = count + 1

    print _(" X server started successfully.")

    # now start up mini-wm
    #
    # I think its ok to always try if we actually had to start an X server
    # 
    #    if not flags.test or 1:

    if 1:
        try:
            miniwm_pid = startMiniWM()
            log("Started mini-wm")
        except:
            miniwm_pid = None
            log("Unable to start mini-wm")
    else:
	miniwm_pid = None

    # test to setup dpi
    # cant do this if miniwm didnt run because otherwise when
    # we open and close an X connection in the xutils calls
    # the X server will exit since this is the first X
    # connection (if miniwm isnt running)
    if miniwm_pid is not None:
	import xutils

	try:
	    if xutils.screenWidth() > 640:
		dpi = "96"
	    else:
		dpi = "75"

	    xutils.setRootResource('Xft.antialias', '1')
	    xutils.setRootResource('Xft.dpi', dpi)
	    xutils.setRootResource('Xft.hinting', '1')
	    xutils.setRootResource('Xft.hintstyle', 'hintslight')
	    xutils.setRootResource('Xft.rgba', 'none')
	except:
	    sys.stderr.write("X SERVER STARTED, THEN FAILED");
	    raise RuntimeError, "X server failed to start"

    child = os.fork()
    if (child):
	# here we fork and wait on our child, which will contine
	# on being anaconda, to finish.  When the child finishes
	# we kill the X server and exit with the exit status set to
	# the same exit status of our child (which is now the main
	# anaconda process).
	try:
	    pid, status = os.waitpid(child, 0)
        except OSError, (errno, msg):
            print __name__, "waitpid:", msg
	    sys.exit (-1)

	# kill miniwm first
	if miniwm_pid is not None:
            try:
                os.kill(miniwm_pid, 15)
                os.waitpid(miniwm_pid, 0)
            except:
                pass

        # now the X server
	try:
	    os.kill(server, 15)
	    os.waitpid(server, 0)
	except:
	    pass

	if os.WIFEXITED(status) and not os.WEXITSTATUS(status):
	    sys.exit(0)

	sys.exit(-1)

#
# should probably be in rhpl
#
def writeXConfig(filename, hwstate, mouse, keyboard, standalone = 0):
    if hwstate.videocard == None:
	return None

    standalone_fontpaths = ["/usr/X11R6/lib/X11/fonts/misc:unscaled",
			    "/usr/X11R6/lib/X11/fonts/Type1/",
			    "/usr/X11R6/lib/X11/fonts/Speedo/",
			    "/usr/X11R6/lib/X11/fonts/75dpi:unscaled",
			    "/usr/X11R6/lib/X11/fonts/100dpi:unscaled",
			    "/usr/X11R6/lib/X11/fonts/korean:unscaled",
			    "/usr/X11R6/lib/X11/fonts/cyrillic:unscaled",
			    "/usr/share/fonts/ISO8859-2/misc:unscaled",
			    "/usr/share/fonts/ISO8859-2/75dpi:unscaled",
			    "/usr/share/fonts/ISO8859-2/100dpi:unscaled",
			    "/usr/share/fonts/ISO8859-9/misc:unscaled",
			    "/usr/share/fonts/ISO8859-9/75dpi:unscaled",
			    "/usr/share/fonts/ISO8859-9/100dpi:unscaled",
			    "/usr/share/fonts/KOI8-R/misc:unscaled",
			    "/usr/share/fonts/KOI8-R/75dpi:unscaled"
			    ]

    #
    # get an xg86config object that represents the config file we're going
    # to write out
    #
    xcfgdata = hwstate.generate_xconfig(mouse, keyboard)

    # add the font paths we need if desired
    if standalone:
	files = xcfgdata.files
	tmpfp = files.fontpath
	newfp = ""
	for fp in standalone_fontpaths:
	    newfp = newfp + fp + ","

	newfp = newfp + tmpfp

	files.fontpath = newfp
    
    xcfgdata.write(filename)

#
# should probably be in rhpl
#
#
# hwstate is a X hw state object from rhpl.xhwstate
# mouse is mouse object from rhpl.mouse
# keyboard is a keyboard object from rhpl.keyboard
# serverflags are extra flags to throw at X server command line
# root is top of hierarchy we look for X server in
# standalone = 1 means we're running without xfs (anaconda mode essentially)
#
def writeXConfigAndRunX(hwstate, mouse, keyboard, serverflags=None,
			root='/', standalone = 0):

    if hwstate.videocard == None:
	return None

    #
    #   XXX - Assuming X server binary is 'XFree86'
    #
    servername = 'XFree86'
    use_resolution = hwstate.get_resolution()

    #
    # make text fit on screen
    #
    if use_resolution == "640x480":
	forced_dpi = 75
    else:
	forced_dpi = 96

    # write X Config
    writeXConfig('%s/tmp/XF86Config.test' % (root,), hwstate, mouse, keyboard, standalone)

    # setup to run X server
    serverPath = "/usr/X11R6/bin/" + servername

    serverpid = os.fork()

    if (not serverpid):
	if (root and root != '/'): 
	    os.chroot (root)
	    os.chdir("/")

	args = [serverPath, '-xf86config', '/tmp/XF86Config.test' ]
	logFile = "/tmp/X.log"
	if servername == "XFree86":
	    args = args + [ "-logfile", "/dev/null" ]
	if serverflags:
	    args = args + serverflags
	else:
	    args = args +  [ ":9", "vt6" ]
	    logFile = "/tmp/X-Test.log"

	try:
	    err = os.open(logFile, os.O_RDWR | os.O_CREAT)
	    if err < 0:
		sys.stderr.write("error opening /tmp/X.log\n")
	    else:
		os.dup2(err, 2)
		os.close(err)
	except:
	    # oh well
	    pass

	os.execv(args[0], args)
	sys.exit (1)

    return serverpid


