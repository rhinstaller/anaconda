import os
import string
import kudzu
import isys
import sys

def findCardInDB (needle, lines = None):
    if not lines:
        db = open ('/usr/X11R6/lib/X11/Cards')
        lines = db.readlines ()
        db.close ()

    found = 0

    card = {}

    for line in lines:
        line = string.strip (line)
        
        if not line and found:
            break

        if line and line[0] == '#':
            continue

        if len (line) > 4 and line[0:4] == 'NAME':
            haystack = line[5:]
            if needle == haystack:
                found = 1
                continue

        if found:
            info = string.splitfields (line, ' ')
            if card.has_key (info[0]):
                card[info[0]] = card[info[0]] + (string.joinfields (info[1:], ' ') + '\n')
            else:
                card[info[0]] = string.joinfields (info[1:], ' ')

    if card.has_key ("SEE"):
        see = findCardInDB (card["SEE"], lines)
        for key, item in see.items ():
            card[key] = item

    return card

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
        raise XServerError, "Unable to find a mouse!"

    device = None
    protocol = None
    (mouseDev, driver, descr) = mice[0]
    if mouseDev == 'psaux':
        protocol = "PS/2"
    else:
        protocol = "Microsoft"

    cards = kudzu.probe (kudzu.CLASS_VIDEO,
                         kudzu.BUS_UNSPEC,
                         kudzu.PROBE_ALL);

    if len (cards) > 1:
        print "Warning: multiple video chips detected."

    if not cards:
        try:
            f = open('/dev/fb0', 'r')
            f.close()
            serverPath = '/usr/X11R6/bin/XF86_FBDev'
        except:
            serverPath = '/usr/X11R6/bin/XF86_VGA16'

        print "PCI probe for video cards failed.  Falling back to", serverPath
    else:
        (device, driver, descr) = cards[0]
        if len (driver) > 5 and driver[0:5] == "Card:":
            card = findCardInDB (driver[5:])
            if card.has_key ("SERVER"):
                serverPath = '/usr/X11R6/bin/XF86_' + card["SERVER"]
            else:
                print ("CardDB missing SERVER for " + driver[5:] + ".\n"
                       "Falling back to VGA16")
                serverPath = '/usr/X11R6/bin/XF86_VGA16'                       
        else:
            if len (driver) > 7 and driver[0:7] == "Server:":
                serverPath = '/usr/X11R6/bin/XF86_' + driver[7:]

        if not serverPath:
            print "Unable to probe card.  Falling back to VGA16"
            serverPath = '/usr/X11R6/bin/XF86_VGA16'

    isys.makeDevInode(mouseDev, "/tmp/" + mouseDev)

    f = open ('/tmp/XF86Config', 'w')

    settings = { "mouseDev" : '/tmp/' + mouseDev ,
                 "mouseProto" : protocol }

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

Section "Monitor"
    Identifier  "Monitor"
    VendorName  "Vendor"
    ModelName   "Model"
    HorizSync   31.5 - 79.0
    VertRefresh 40-150

# XXX fix me descr
Modeline "640x480"     25.175 640  664  760  800   480  491  493  525
# 640x480 @ 72 Hz, 36.5 kHz hsync
Modeline "640x480"     31.5   640  680  720  864   480  488  491  521
# 640x480 @ 75 Hz, 37.50 kHz hsync
ModeLine  "640x480"    31.5   640  656  720  840   480  481  484  500 -HSync -VSync

EndSection

Section "Device"
    Identifier  "Device"
    VendorName  "Vendor"
    BoardName   "Board"
EndSection

Section "Screen"
    Driver      "vga16"
    Device      "Device"
    Monitor     "Monitor"
    Subsection  "Display"
        Modes       "640x480"
        ViewPort    0 0
    EndSubsection
EndSection

Section "Screen"
    Driver      "svga"
    Device      "Device"
    Monitor     "Monitor"
    Subsection  "Display"
        Depth       8
        Modes       "640x480"
        ViewPort    0 0
        Virtual     640 480
    EndSubsection
EndSection

Section "Screen"
    Driver      "accel"
    Device      "Device"
    Monitor     "Monitor"
    Subsection  "Display"
        Depth       8
        Modes       "640x480"
        ViewPort    0 0
        Virtual     640 480
    EndSubsection
EndSection

Section "Screen"
    Driver      "fbdev"
    Device      "Device"
    Monitor     "Monitor"
    Subsection  "Display"
	Depth 	    16
        Modes       "default"
    EndSubsection
EndSection
""" % settings)
    f.close ()

    server = os.fork()
    if (not server):
        print "starting", serverPath
        os.execv(serverPath, [serverPath, ':1', '-xf86config', 
                 '/tmp/XF86Config', 'vt5'])
    child = os.fork()
    if (child):
        os.waitpid(child, 0)
        os.kill(server, 15)
        sys.exit(0)
