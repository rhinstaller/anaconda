#
# xserver.py - initial xserver startup for GUI mode.
#
# Matt Wilson <msw@redhat.com>
# Brent Fox <bfox@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
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
from xf86config import *
from kbd import Keyboard
from mouse import Mouse
from snack import *
from translate import _
from constants_text import *
from mouse_text import MouseWindow, MouseDeviceWindow
from videocard import FrameBufferCard, VGA16Card

serverPath = ""

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

# start X server for install process ONLY
def startX(resolution, nofbmode, video, monitor, mouse):
    global serverPath
    global mode
    
    os.environ['DISPLAY'] = ':1'
    serverPath = None

    #--see if framebuffer works on this card
    fbavail = isys.fbinfo()

    if fbavail:
        attempt = 'FB'
    else:
        attempt = 'PROBED'

    failed = 1
    next_attempt = None
    while next_attempt != 'END':
        card = None
        if attempt == 'FB':
            if fbavail and nofbmode == 0 and canUseFrameBuffer(video.primaryCard()):
                print _("Attempting to start framebuffer based X server")
                card = FrameBufferCard()
            else:
                card = None

            next_attempt = 'PROBED'
        elif attempt == 'PROBED':
            if video.primaryCard():
                print _("Attempting to start native X server")
                card = video.primaryCard()
            else:
                card = None
            next_attempt = 'VGA16'
        elif attempt == 'VGA16':
            # if no xserver then try falling back to VGA16 in no fb
            card = VGA16Card()
            
            print _("Attempting to start VGA16 X server")
            next_attempt = 'END'
        else:
            print "Got off end somehow!"
            break

        if card and card.getXServer() != None:
            serverPath = '/usr/X11R6/bin/' + card.getXServer()

            if os.access (serverPath, os.X_OK):
                try:
                    x = XF86Config (card, monitor, mouse, resolution)
                    testx(x)
                    failed = 0
                    break
            
                except (RuntimeError, IOError):
                    pass

        attempt = next_attempt
        
    #--If original server isn't there...send them to text mode
    if failed:
        raise RuntimeError, "No X server binaries found to run"
    
    return x

def canUseFrameBuffer (videocard):
    if videocard:
        carddata = videocard.getProbedCard()

        if carddata:
            if carddata[:13] == "Card:NeoMagic":
                return 0

    return 1

def testx(x):
    try:
	server = x.test ([':1', 'vt7', '-s', '1440', '-terminate',
                          '-dpms', '-v', '-ac', '-nolisten', 'tcp'], spawn=1)
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
    
    child = os.fork()
    if (child):
	try:
	    pid, status = os.waitpid(child, 0)
        except OSError, (errno, msg):
            print __name__, "waitpid:", msg
	    sys.exit (-1)

	try:
	    os.kill(server, 15)
	    os.waitpid(server, 0)
	except:
	    pass

	if os.WIFEXITED(status) and not os.WEXITSTATUS(status):
	    sys.exit(0)

	sys.exit(-1)


#
# to start X server using existing XF86Config file (reconfig mode use only)
#
def start_existing_X():

    os.environ['DISPLAY'] = ':1'

    server = os.fork()
    serverPath = "/etc/X11/X"

    # override fontpath because xfs is not running yet!
    if (not server):
        print "Starting X using existing XF86Config"
	args = [serverPath, ':1', 'vt7', '-s', '1440', '-terminate', '-dpms',
                '-v']
	args.append("-fp")
	args.append("/usr/X11R6/lib/X11/fonts/misc/,"
                    "/usr/X11R6/lib/X11/fonts/75dpi/,"
                    "/usr/X11R6/lib/X11/fonts/100dpi/,"
                    "/usr/X11R6/lib/X11/fonts/cyrillic/,"
                    "/usr/share/fonts/ISO8859-2/misc/,"
                    "/usr/share/fonts/ISO8859-2/75dpi/,"
                    "/usr/share/fonts/ISO8859-2/100dpi/,"
                    "/usr/share/fonts/KOI8-R/misc/,"
                    "/usr/share/fonts/KOI8-R/75dpi/")
                    
	os.execv(serverPath, args)

    # give time for the server to fail (if it is going to fail...)
    # FIXME: Should find out if X server is already running
    # otherwise with NFS installs the X server may be still being
    # fetched from the network while we already continue to run
    time.sleep (4)
    status = 0
    try:
        pid, status = os.waitpid (server, os.WNOHANG)
    except OSError, (errno, msg):
        print __name__, "waitpid:", msg

    if status:
        raise RuntimeError, "X server failed to start"

    # startX() function above does a double-fork here, do we need to in
    # reconfig mode?
    
    return (None, None)
