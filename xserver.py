import os
import string
import kudzu
import isys
import sys
import time
from xf86config import *
from kbd import Keyboard

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
    elif iutil.getArch() == "sparc":
	raise RuntimeError, "Unknown card"
    else:
        print "Unknown card, falling back to VGA16"
        serverPath = '/usr/X11R6/bin/XF86_VGA16'

    if not os.access (serverPath, os.X_OK):
	if iutil.getArch() == "sparc":
	    raise RuntimeError, "Missing X server"
        print serverPath, "missing.  Falling back to VGA16"
        serverPath = '/usr/X11R6/bin/XF86_VGA16'
        
    keycodes = "xfree86"
    symbols = "us(pc101)"
    geometry = "pc"
    rules = "xfree86"
    model = "pc101"

    kbd = Keyboard()
    if kbd.type == 'Sun':
	rules = "sun"
	model = kbd.model
	keycodes = "sun(" + kbd.model + ")"
	if model == 'type4':
	    geometry = "sun(type4)"
	    symbols = "sun/us(sun4)"
	else:
	    if model == 'type5':
		geometry = "sun"
	    elif model == 'type5_euro':
		geometry = "sun(type5euro)"
	    else:
		geometry = "sun(type5unix)"
	    symbols = "sun/us(sun5)"
	if kbd.layout == 'en_US':
	    symbols = symbols + "+iso9995-3(basic)"
	elif kbd.layout != 'us':
	    symbols = symbols + "+" + kbd.layout
	    
    mouseEmulateStr="""
    Emulate3Buttons
    Emulate3Timeout    50
"""
    if not mouseEmulate:
	mouseEmulateStr=""
    settings = { "mouseDev" : '/dev/' + mouseDev ,
                 "mouseProto" : mouseProtocol,
		 "keycodes" : keycodes,
		 "symbols" : symbols,
		 "geometry" : geometry,
		 "rules" : rules,
		 "model" : model,
		 "emulate" : mouseEmulateStr }
    f = open ('/tmp/XF86Config', 'w')
    f.write ("""
Section "Files"
    RgbPath	"/usr/X11R6/lib/X11/rgb"
    FontPath	"/usr/X11R6/lib/X11/fonts/misc/"
    FontPath	"/usr/X11R6/lib/X11/fonts/Type1/"
    FontPath	"/usr/X11R6/lib/X11/fonts/Speedo/"
    FontPath	"/usr/X11R6/lib/X11/fonts/75dpi/"
    FontPath	"/usr/X11R6/lib/X11/fonts/100dpi/"
    FontPath    "/usr/X11R6/lib/X11/fonts/cyrillic/"
    FontPath    "/usr/share/fonts/ISO8859-2/misc/"
    FontPath    "/usr/share/fonts/ISO8859-2/75dpi/"
    FontPath    "/usr/share/fonts/ISO8859-2/100dpi/"
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
    XkbKeycodes     "%(keycodes)s"
    XkbTypes        "default"
    XkbCompat       "default"
    XkbSymbols      "%(symbols)s"
    XkbGeometry     "%(geometry)s"
    XkbRules        "%(rules)s"
    XkbModel        "%(model)s"
    XkbLayout       "us"
EndSection

Section "Pointer"
    Protocol    "%(mouseProto)s"
    Device      "%(mouseDev)s"
%(emulate)s
EndSection
""" % settings)
    f.write (x.monitorSection (1))
    f.write (x.deviceSection ())
    if x.monSect:
	bpp = x.bpp
    else:
        x.modes["32"] = [ "640x480" ]
        x.modes["16"] = [ "640x480" ]
        x.modes["8"] = [ "640x480" ]
	bpp = None
    f.write (x.screenSection (1))
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
	    try:
		f = open("/dev/tty5", "w")
		f.write("\n")
		f.close()
	    except:
		pass
	    os.symlink(mouseDev, "/dev/mouse")
	    if x.device:
		args.append ("-dev")
		args.append ('/dev/' + x.device)
	    args.append("-fp")
	    args.append("/usr/X11R6/lib/X11/fonts/misc/,"
			"/usr/X11R6/lib/X11/fonts/75dpi/,"
			"/usr/X11R6/lib/X11/fonts/100dpi/,"
			"/usr/X11R6/lib/X11/fonts/cyrillic/,"
			"/usr/share/fonts/ISO8859-2/misc/,"
			"/usr/share/fonts/ISO8859-2/75dpi/,"
			"/usr/share/fonts/ISO8859-2/100dpi/")
	else:
	    args.append("-xf86config")
	    args.append("/tmp/XF86Config")
	    if bpp:
		args.append("-bpp")
		args.append(bpp)
	os.execv(serverPath, args)

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
	    sys.exit(-1)

        sys.exit((status >> 8) & 0xf)

    return ((mouseProtocol, mouseEmulate, mouseDev), x)
