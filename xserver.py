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

def startX():
    global serverPath
    global mode
    
    os.environ['DISPLAY'] = ':1'
    serverPath = None

    print "Probing for mouse type..."

    mouse = Mouse()
    if not mouse.probe ():
        print "No mouse detected, GUI startup can not continue."
        time.sleep (1)
        print "Falling back to Text mode"

    x = XF86Config (mouse)
    x.probe ()
    if x.server and len (x.server) >= 3 and x.server[0:3] == 'Sun':
	serverPath = '/usr/X11R6/bin/Xs' + x.server[1:]
    elif x.server:
        serverPath = '/usr/X11R6/bin/' + x.server
    elif iutil.getArch() == "sparc":
  	raise RuntimeError, "Unknown card"
    else:
          print "Unknown card, falling back to VGA16"
    
    if not os.access (serverPath, os.X_OK):
	if iutil.getArch() == "sparc":
	    raise RuntimeError, "Missing X server"
        print serverPath, "missing.  Falling back to VGA16"
        serverPath = '/usr/X11R6/bin/XF86_VGA16'
        
    server = x.test ([':1', 'vt7', '-s', '1440', '-terminate'], spawn=1)

    # give time for the server to fail (if it is going to fail...)
    # FIXME: Should find out if X server is already running
    # otherwise with NFS installs the X server may be still being
    # fetched from the network while we already continue to run
    time.sleep (4)
    pid, status = os.waitpid (server, os.WNOHANG)
    if status:
        raise RuntimeError, "X server failed to start"
        
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

    return (mouse, x)

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
			"/usr/share/fonts/ISO8859-2/100dpi/")

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
