import os
import string
import kudzu
import isys
import sys
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
    else:
        mouseProtocol = "Microsoft"
	mouseEmulate = 1

    x = XF86Config ()
    x.probe ()
    if x.server:
        serverPath = '/usr/X11R6/bin/XF86_' + x.server
    else:
        print "Unknown card, falling back to VGA16"
        serverPath = '/usr/X11R6/bin/XF86_VGA16'

    if not os.access (serverPath, os.X_OK):
        print serverpath, "missing.  Falling back to VGA16"
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
    f.write (x.screenSection ())
    f.close ()

    server = os.fork()
    if (not server):
        print "starting", serverPath
        os.execv(serverPath, [serverPath, ':1', '-xf86config', 
                 '/tmp/XF86Config', 'vt7'])
    child = os.fork()
    if (child):
        try:
            pid, status = os.waitpid(server, 0)
        except:
            sys.exit (-1)
        sys.exit(status)

    return ((mouseProtocol, mouseEmulate, mouseDev), x)
