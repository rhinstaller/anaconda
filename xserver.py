import os
import string
import kudzu
import isys
import sys
import time
from xf86config import *

def startX():
    global serverPath
    global mode
    
    os.environ['DISPLAY'] = ':1'
    serverPath = None

    print "Probing for mouse type..."
    mice = kudzu.probe (kudzu.CLASS_MOUSE,
                        kudzu.BUS_UNSPEC,
                        kudzu.PROBE_ONE);
    if not mice:
        raise RuntimeError, "Unable to find a mouse!"

    device = None
    mouseProtocol = None
    (mouseDev, driver, descr) = mice[0]
    if mouseDev == 'psaux':
        mouseProtocol = "PS/2"
	mouseEmulate = 0
        # kickstart some ps/2 mice.  Blame the kernel
        try:
            f = open ('/dev/psaux')
            f.write ('1')
            f.close
        except:
            pass
    elif mouseDev == 'sunmouse':
	mouseProtocol = "sun"
	mouseEmulate = 0
    else:
        mouseProtocol = "Microsoft"
	mouseEmulate = 1

    x = XF86Config ((mouseProtocol, mouseEmulate, mouseDev))
    x.probe ()
    if x.server and len (x.server) >= 3 and x.server[0:3] == 'Sun':
	serverPath = '/usr/X11R6/bin/Xs' + x.server[1:]
    elif x.server:
        serverPath = '/usr/X11R6/bin/XF86_' + x.server
    else:
        print "Unknown card, falling back to VGA16"
        serverPath = '/usr/X11R6/bin/XF86_VGA16'

    if not os.access (serverPath, os.X_OK):
        print serverPath, "missing.  Falling back to VGA16"
        serverPath = '/usr/X11R6/bin/XF86_VGA16'
        
    settings = { "mouseDev" : '/dev/' + mouseDev ,
                 "mouseProto" : mouseProtocol }
    f = open ('/tmp/XF86Config', 'w')
    f.write ("""
Section "Files"
    RgbPath	"/usr/X11R6/lib/X11/rgb"
    FontPath	"/usr/X11R6/lib/X11/fonts/misc/"
    FontPath	"/usr/X11R6/lib/X11/fonts/Type1/"
    FontPath	"/usr/X11R6/lib/X11/fonts/Speedo/"
    FontPath	"/usr/X11R6/lib/X11/fonts/75dpi/"
    FontPath	"/usr/X11R6/lib/X11/fonts/100dpi/"
EndSection

Section "ServerFlags"
EndSection

Section "Keyboard"
    Protocol    "Standard"
    AutoRepeat  500 5
    LeftAlt     Meta
    RightAlt    Meta
    ScrollLock  Compose
    RightCtl    Control
    XkbKeymap       "xfree86(us)"
    XkbKeycodes     "xfree86"
    XkbTypes        "default"
    XkbCompat       "default"
    XkbSymbols      "us(pc101)"
    XkbGeometry     "pc"
    XkbRules        "xfree86"
    XkbModel        "pc101"
    XkbLayout       "us"
EndSection

Section "Pointer"
    Protocol    "%(mouseProto)s"
    Device      "%(mouseDev)s"
    Emulate3Buttons
    Emulate3Timeout    50
EndSection
""" % settings)
    f.write (x.monitorSection ())
    f.write (x.deviceSection ())
    x.modes["8"] = [ "640x480" ]
    x.modes["16"] = [ "640x480" ]
    x.modes["32"] = [ "640x480" ]
    f.write (x.screenSection ())
    f.close ()

    server = os.fork()
    if (not server):
        print "starting", serverPath
	args = [serverPath, ':1', 'vt7', '-s', '1440']
	if serverPath[0:19] == '/usr/X11R6/bin/Xsun':
	    try:
		os.unlink("/dev/mouse")
	    except:
		pass
	    os.symlink(mouseDev, "/dev/mouse")
	    if x.device:
		args.append ("-dev")
		args.append ('/dev/' + x.device)
	else:
	    args.append("-xf86config")
	    args.append("/tmp/XF86Config")
	os.execv(serverPath, args)

    # give time for the server to fail (if it is going to fail...)
    time.sleep (1)
    pid, status = os.waitpid (server, os.WNOHANG)
    if status:
        raise RuntimeError, "X server failed to start"
        
    child = os.fork()
    if (child):
        try:
            pid, status = os.waitpid(child, 0)
        except:
            sys.exit (-1)
        sys.exit((status >> 8) & 0xf)

    return ((mouseProtocol, mouseEmulate, mouseDev), x)
