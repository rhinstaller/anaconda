import os
import string
import kudzu
import isys
import sys
import time
from xf86config import *
from kbd import Keyboard
from mouse import Mouse
import time
from snack import *
from translate import _
from constants_text import *
from mouse_text import MouseWindow, MouseDeviceWindow


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
    
def startX(resolution, nofbmode):
    global serverPath
    global mode
    
    os.environ['DISPLAY'] = ':1'
    serverPath = None

    print "Probing for mouse type..."

    mouse = Mouse()
    if not mouse.probe (frob=1):
        if not mouseWindow(mouse):
            raise RuntimeError, "failed to get a mouse for X startup"
    else:
        (Xtype, Xtmp) = mouse.get()

    x = XF86Config (mouse, resolution)
    x.res = resolution    
    x.probe ()

    probedServer = x.server

    #--Run fb_check() and see if framebuffer works on this card
    if fb_check() == 0:
        x.server = "XF86_FBDev"

    if x.server:
        serverPath = '/usr/X11R6/bin/' + x.server
#        print "Using X server", serverPath
        
    elif iutil.getArch() == "sparc":
  	raise RuntimeError, "Unknown card"
    else:
          x.server = "XF86_VGA16"
          serverPath = '/usr/X11R6/bin/XF86_VGA16'

    if not os.access (serverPath, os.X_OK):    #--If framebuffer server isn't there...try original probed server
        x.server = probedServer
        serverPath = '/usr/X11R6/bin/' + x.server

        
        if not os.access (serverPath, os.X_OK):  #--If original server isn't there...send them to text mode
#            print serverPath, "missing.  Falling back to text mode"
            raise RuntimeError, "No X server binaries found to run"

#    try:
    if nofbmode == 0:
        try:
            fbdevice = open("/dev/fb0", "r")   #-- If can't access /dev/fb0, we're not in framebuffer mode
            fbdevice.close()

            testx(mouse, x)

        except (RuntimeError, IOError):
#            from log import log
#            log.open(0, 0, 0, 0)
#            log ("can't open /dev/fb0")
#            log.close()
    
            x.server = probedServer

            if not x.server:
                print "Unknown card"
                raise RuntimeError, "Unable to start X for unknown card"
                        
            # if this fails, we want the exception to go back to anaconda to
            # it knows that this didn't work
            testx(mouse, x)

    else:  #-We're in nofb mode
	x.server = probedServer

        if not x.server:
            print "Unknown card"
            raise RuntimeError, "Unable to start X for unknown card"
                        
	# if this fails, we want the exception to go back to anaconda to
	# it knows that this didn't work
	testx(mouse, x)

    return (mouse, x)

def fb_check ():
    result = None
    cards = kudzu.probe (kudzu.CLASS_VIDEO,
                         kudzu.BUS_UNSPEC,
                         kudzu.PROBE_ALL);
    
    if cards != []:
        for card in cards: 
            (junk, man, junk2) = card

        if man[:13] == "Card:NeoMagic":
            return 1
        else:
            return 0
    else:
        return 0

def testx(mouse, x):
#    print "going to test the x server"
    try:
	server = x.test ([':1', 'vt7', '-s', '1440', '-terminate'], spawn=1)
    except:
	import traceback
	from string import joinfields
	(type, value, tb) = sys.exc_info()
	list = traceback.format_exception (type, value, tb)
	text = joinfields (list, "")
	print text
#    print "tested the x server"

    # give time for the server to fail (if it is going to fail...)
    # FIXME: Should find out if X server is already running
    # otherwise with NFS installs the X server may be still being
    # fetched from the network while we already continue to run

#    print "in testx, server is  |%s| " %server
#    time.sleep (4)

    if not server:
        sys.stderr.write("X SERVER FAILED");
        raise RuntimeError, "X server failed to start"


    count = 0

    sys.stdout.write("Waiting for X server to start...log located in /tmp/X.log\n")
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
#                print
	    break
	except OSError:
	    pass
	time.sleep(1)
	count = count + 1

    print " X server started successfully."
    
    child = os.fork()
    if (child):
	try:
	    pid, status = os.waitpid(child, 0)
        except OSError, (errno, msg):
            print __name__, "waitpid:", msg
	    sys.exit (-1)

	try:
	    sys.kill(server, 15)
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
	args = [serverPath, ':1', 'vt7', '-s', '1440', '-terminate']
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
                    
#        print args
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
