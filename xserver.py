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
    
def startX():
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
        print "Found a", Xtype
        time.sleep(2)

    x = XF86Config (mouse)
    x.probe ()
    print "Probed X server is " , x.server
    probedServer = x.server
    x.server = "XF86_FBDev"

    if x.server:
        serverPath = '/usr/X11R6/bin/' + x.server
#        serverPath = '/usr/X11R6/bin/XF86_FBDev'
        print "Using X server", serverPath
#        print "Sleeping 4 seconds"
#        time.sleep(4)

        
    elif iutil.getArch() == "sparc":
  	raise RuntimeError, "Unknown card"
    else:
          print "Unknown card, falling back to VGA16"
          x.server = "XF86_VGA16"
          serverPath = '/usr/X11R6/bin/XF86_VGA16'
    

    if not os.access (serverPath, os.X_OK):    #--If framebuffer server isn't there...try original probed server
        x.server = probedServer
        print "Frame buffer didn't work...trying ", x.server
        serverPath = '/usr/X11R6/bin/' + x.server
#        print "Sleeping 4 seconds"
#        time.sleep(4)
        
        if not os.access (serverPath, os.X_OK):  #--If original server isn't there...send them to text mode
            print serverPath, "missing.  Falling back to text mode"
            raise RuntimeError, "No X server binaries found to run"
#            print "Sleeping 4 seconds"
#            time.sleep(4)






#    if not os.access (serverPath, os.X_OK):
#	if iutil.getArch() == "sparc":
#	    raise RuntimeError, "Missing X server"
#        print serverPath, "missing.  Falling back to VGA16"
#        x.server = "XF86_VGA16"        
#        serverPath = '/usr/X11R6/bin/XF86_VGA16'

#        if not os.access (serverPath, os.X_OK):
#            print serverPath, "missing.  Falling back to text mode"
#            print "Sleeping 7 seconds"
#            time.sleep(7)
#            raise RuntimeError, "No X server binaries found to run"

#    print x.test
#    print "Sleeping 7 seconds"
#    time.sleep(7)

    
#    server = x.test ([':1', 'vt7', '-s', '1440', '-terminate'], spawn=1)



    try:        
        fbdevice = open("/dev/fb0", "r")   #-- If can't access /dev/fb0, we're not in framebuffer mode
        fbdevice.close()
        
#        print "About to test frame buffer mode"
#        print "Currently x.server is ", x.server
#        print "Sleeping 5 seconds"
#        time.sleep(5)        
        testx(mouse, x)
    except:
        try:            
#            print "Framebuffer test didn't work"
#            print "Trying original probed server ", probedServer
            x.server = probedServer

#            print "Currently x.server is ", x.server
#            print "Sleeping 5 seconds"
#            time.sleep(5)     

            testx(mouse, x)
#            print "Sleeping 10 seconds"
#            time.sleep(10)
        except:
            pass
#            try:
#                print "Skipping VGA16"

                #XXX - VGA16 can't do 800x600, so don't even try.  Fall back to text instead
#                print "Original probed server ", probedServer, " didn't work."
#                print "Trying XF86_VGA16"
#                x.server = "XF86_VGA16"
#                server = test(mouse, x)

#                print "Currently x.server is ", x.server
#                print "Sleeping 5 seconds"
#                time.sleep(5)
                
#                testx(mouse, x)
#                print "Sleeping 15 seconds"
#                time.sleep(15)
#            except:
#                pass
#                print x.server, "didn't work...falling back to text mode"
#                print "Sleeping 30 seconds"
#                time.sleep(30)



    # give time for the server to fail (if it is going to fail...)
    # FIXME: Should find out if X server is already running
    # otherwise with NFS installs the X server may be still being
    # fetched from the network while we already continue to run
#    time.sleep (4)
#    count = 0

#    print "Sleeping 3 seconds"
#    time.sleep(3)


#    sys.stdout.write("Waiting for X server to start")
#    sys.stdout.flush()
#    while count < 60:
#        sys.stdout.write(".")
#        sys.stdout.flush()
#        pid, status = os.waitpid (server, os.WNOHANG)
#        if status:
#            raise RuntimeError, "X server failed to start"
#        try:
#            os.stat ("/tmp/.X11-unix/X1")
#            print
#            break
#        except OSError:
#            pass
#        time.sleep(1)
#        count = count + 1
        
#    child = os.fork()
#    if (child):
#        try:
#            pid, status = os.waitpid(child, 0)
#        except:
#            sys.exit (-1)
#	try:
#	    sys.kill(server, 15)
#	    pid, status = os.waitpid(server, 0)
#	except:
#	    sys.exit(0)

#        sys.exit((status >> 8) & 0xf)

    return (mouse, x)


def testx(mouse, x):
    try:
#        print "Inisde testx...trying with server: ", x.server

#        print "Sleeping 5 seconds"
#        time.sleep(5)     

        server = x.test ([':1', 'vt7', '-s', '1440', '-terminate'], spawn=1)
#        return server

        # give time for the server to fail (if it is going to fail...)
        # FIXME: Should find out if X server is already running
        # otherwise with NFS installs the X server may be still being
        # fetched from the network while we already continue to run

        time.sleep (4)
        count = 0

#        print "Sleeping 3 seconds"
#        time.sleep(3)


        sys.stdout.write("Waiting for X server to start")
        sys.stdout.flush()
        while count < 60:
            sys.stdout.write(".")
            sys.stdout.flush()
            pid, status = os.waitpid (server, os.WNOHANG)
            if status:
                raise RuntimeError, "X server failed to start"
            try:
                os.stat ("/tmp/.X11-unix/X1")
                print
                break
            except OSError:
                pass
            time.sleep(1)
            count = count + 1
        
            child = os.fork()
            if (child):
                try:
                    pid, status = os.waitpid(child, 0)
                except:
                    sys.exit (-1)
                try:
                    sys.kill(server, 15)
                    pid, status = os.waitpid(server, 0)
                except:
                    sys.exit(0)

                sys.exit((status >> 8) & 0xf)


#        return (mouse, x)
    
    except:
        raise RuntimeError, "X server failed to start"




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
                    
        print args
	os.execv(serverPath, args)

    # give time for the server to fail (if it is going to fail...)
    # FIXME: Should find out if X server is already running
    # otherwise with NFS installs the X server may be still being
    # fetched from the network while we already continue to run
    time.sleep (4)
    pid, status = os.waitpid (server, os.WNOHANG)
    if status:
        raise RuntimeError, "X server failed to start"

    # startX() function above does a double-fork here, do we need to in
    # reconfig mode?
    
    return (None, None)














