import sys
if __name__ == "__main__":
    sys.path.append ('kudzu')
    sys.path.append ('isys')
import string
import iutil
import kudzu
import time
import os

def _(x):
    return x

class XF86Config:
    def __init__ (self, mouse = None):
        if mouse:
            (mouseProtocol, mouseEmulate, mouseDev) = mouse
            self.mouse = { "mouseDev" : "/dev/mouse",
                           "mouseProto" : mouseProtocol }
        else:
            self.mouse = { "mouseDev" : "/dev/mouse",
                           "mouseProto" : "PS/2" }

        self.server = None
        self.vidCards = []
        self.cardMan = None
        self.vidRam = None
        self.monEisa = None
        self.monName = None
        self.monHoriz = None
        self.monVert = None
        self.monID = None
        self.devID = None
        self.probed = 0
        self.skip = 0
        self.modes = { "8" :  ["640x480"] }

    def filterModesByMemory (self):
        if not self.vidRam:
            return
        if string.atoi(self.vidRam) >= 4096:
            self.modes["8"] = ["640x480", "800x600", "1024x768", "1152x864", "1280x1024", "1600x1200"]
            self.modes["16"] = ["640x480", "800x600", "1024x768", "1152x864", "1280x1024", "1600x1200"]
            self.modes["32"] = ["640x480", "800x600", "1024x768", "1152x864"]
        elif string.atoi(self.vidRam) >= 2048:
            self.modes["8"] = ["640x480", "800x600", "1024x768", "1152x864", "1280x1024"]
            self.modes["16"] = ["640x480", "800x600", "1024x768", "1152x864"]
            self.modes["32"] = ["640x480", "800x600"]
        elif string.atoi(self.vidRam) >= 2048:
            self.modes["8"] = ["640x480", "800x600", "1024x768", "1152x864"]
            self.modes["16"] = ["640x480", "800x600"]
            self.modes["32"] = ["640x480"]
        elif string.atoi(self.vidRam) >= 512:
            self.modes["8"] = ["640x480", "800x600"]
            self.modes["16"] = ["640x480"]
            self.modes["32"] = []
        elif string.atoi(self.vidRam) >= 256:
            self.modes["8"] = ["640x480"]

    def cards (self, thecard = None):
        cards = {}
        db = open ('/usr/X11R6/lib/X11/Cards')
        lines = db.readlines ()
        db.close ()
        card = {}
        name = None
        for line in lines:
            line = string.strip (line)
            if not line and name:
                cards[name] = card
                card = {}
                name = None
                continue
            
            if line and line[0] == '#':
                continue
            
            if len (line) > 4 and line[0:4] == 'NAME':
                name = line[5:]
                
            info = string.splitfields (line, ' ')
            if card.has_key (info[0]):
                card[info[0]] = card[info[0]] + '\n' + (string.joinfields (info[1:], ' '))
            else:
                card[info[0]] = string.joinfields (info[1:], ' ')

        if thecard:
            card = cards[thecard]
            if card.has_key ("SEE"):
                return cards[card["SEE"]]

            return cards[thecard]
        return cards

    def monitors (self, lines = None):
        monitors = []
        if not lines:
            db = open ('/usr/X11R6/share/Xconfigurator/MonitorsDB')
            lines = db.readlines ()
            db.close ()
        found = 0
        for line in lines:
            line = string.strip (line)
            if not line:
                continue
            if line and line[0] == '#':
                continue
            monitors.append (string.split (line, ';', 1)[0])
        return monitors

    def setVidcard (self, card):
        self.vidCards.append (card)

        if self.vidCards:
            self.devID = self.vidCards[0]["NAME"]
            self.server = self.vidCards[0]["SERVER"]

    def probe (self):
        if self.probed:
            return
        self.probed = 1
        # PCI probe for video cards
        sections = {}

        cards = kudzu.probe (kudzu.CLASS_VIDEO,
                             kudzu.BUS_UNSPEC,
                             kudzu.PROBE_ALL);
        for card in cards:
            section = ""
            (device, server, descr) = card
            if len (server) > 5 and server[0:5] == "Card:":
                self.vidCards.append (self.cards (server[5:]))
            if len (server) > 7 and server[0:7] == "Server:":
                info = { "NAME" : string.split (descr, '|')[1],
                         "SERVER" : server[7:] }
                self.vidCards.append (info)

        if self.vidCards:
            self.devID = self.vidCards[0]["NAME"]
            self.server = self.vidCards[0]["SERVER"]

        # VESA probe for monitor/videoram, etc.
        probe = string.split (iutil.execWithCapture ("/usr/sbin/ddcprobe", ['ddcprobe']), '\n')

        for line in probe:
            if line and line[:9] == "OEM Name:":
                self.cardMan = string.strip (line[10:])
                
            if line and line[:16] == "Memory installed":
                memory = string.split (line, '=')
                self.vidRam = string.strip (memory[2][:-2])

            if line and line[:8] == "EISA ID:":
                self.monEisa = line[9:]

            if line and line[:6] == "\tName:":
                if not self.monName or len (self.monName) < len (line[7:]):
                    self.monName = line[7:]

            if line and line[:15] == "\tTiming ranges:":
                ranges = string.split (line, ',')
                self.monHoriz = string.strip (string.split (ranges[0], '=')[1])
                self.monVert = string.strip (string.split (ranges[1], '=')[1])

        if self.vidCards and self.cardMan:
            self.vidCards[0]["VENDOR"] = self.cardMan

    def probeReport (self):
        probe = ""
        if self.vidCards:
            probe = probe + _("Video Card") + ": " + self.vidCards[0]["NAME"] + "\n"
            if self.vidRam:
                probe = probe + "\t" + _("Video Ram") + ": " + self.vidRam + " kb\n"
        if self.server:
            probe = probe + "\t" + _("X server") + ": " + self.server + "\n"
        if not self.server:
            probe = probe + "\t" + _("Unable to detect video card")

        probe = probe + "\n"

        if self.monName:
            probe = probe + _("Monitor") + ": " + self.monName + "\n"
        elif self.monEisa:
            probe = probe + _("Monitor") + ": " + _("Plug and Play Monitor") + "\n"
        if self.monHoriz:
            probe = probe + "\t" + _("Horizontal frequency range") + ": " + self.monHoriz + " kHz\n"
        if self.monHoriz:
            probe = probe + "\t" + _("Vertical frequency range") + ": " + self.monVert + " Hz\n"

        return probe

    def write (self, path):
        config = open (path, 'w')
        config.write (self.preludeSection ())
        config.write (self.inputSection ())
        config.write (self.mouseSection ())
        config.write (self.monitorSection ())
        config.write (self.deviceSection ())
        config.write (self.screenSection ())
        config.close ()

    def test (self):
        self.write ('/tmp/XF86Config.test')
        
        serverPath = "/usr/X11R6/bin/XF86_" + self.server

        server = os.fork()
        if (not server):
            os.execv(serverPath, ["XF86-test", ':9', '-xf86config', 
                                  '/tmp/XF86Config.test', 'vt6'])
            
        time.sleep (1)
##         pid, status = os.waitpid (server, os.WNOHANG)
##         if not pid:
##             raise RuntimeError, "X server failed to start"

        child = os.fork()
        if (not child):
            os.environ["DISPLAY"] = ":9"
            os.execv("/usr/X11R6/bin/Xtest", ["Xtest", "--nostart"])
        else:
            pid, status = os.waitpid(child, 0)
            os.kill (server, 15)
            os.waitpid(server, 0)
            if not os.WIFEXITED (status) or os.WEXITSTATUS (status):
                if os.WEXITSTATUS (status) not in [ 0, 1, 2 ]:
                    raise RuntimeError, "X test failed %d" % (status,)
            return

    def preludeSection (self):
        return """
# File generated by anaconda.

# **********************************************************************
# Refer to the XF86Config(4/5) man page for details about the format of 
# this file.
# **********************************************************************

# **********************************************************************
# Files section.  This allows default font and rgb paths to be set
# **********************************************************************

Section "Files"

# The location of the RGB database.  Note, this is the name of the
# file minus the extension (like ".txt" or ".db").  There is normally
# no need to change the default.

    RgbPath	"/usr/X11R6/lib/X11/rgb"

# Multiple FontPath entries are allowed (they are concatenated together)
# By default, Red Hat 6.0 and later now use a font server independent of
# the X server to render fonts.

    FontPath   "unix/:-1"

EndSection

# **********************************************************************
# Server flags section.
# **********************************************************************

Section "ServerFlags"
    # Uncomment this to cause a core dump at the spot where a signal is 
    # received.  This may leave the console in an unusable state, but may
    # provide a better stack trace in the core dump to aid in debugging

    # NoTrapSignals

    # Uncomment this to disable the <Crtl><Alt><BS> server abort sequence
    # This allows clients to receive this key event.

    # DontZap

    # Uncomment this to disable the <Crtl><Alt><KP_+>/<KP_-> mode switching
    # sequences.  This allows clients to receive these key events.

    # DontZoom
EndSection
"""

    def inputSection (self):
        return """
# **********************************************************************
# Keyboard section
# **********************************************************************

Section "Keyboard"
    Protocol    "Standard"

    # when using XQUEUE, comment out the above line, and uncomment the
    # following line
    # Protocol   "Xqueue"

    AutoRepeat  500 5

    # Let the server do the NumLock processing.  This should only be 
    # required when using pre-R6 clients
    # ServerNumLock

    # Specify which keyboard LEDs can be user-controlled (eg, with xset(1))
    # Xleds      1 2 3

    # To set the LeftAlt to Meta, RightAlt key to ModeShift, 
    # RightCtl key to Compose, and ScrollLock key to ModeLock:

    LeftAlt         Meta
    RightAlt        Meta
    ScrollLock      Compose
    RightCtl        Control

# To disable the XKEYBOARD extension, uncomment XkbDisable.
#    XkbDisable

# To customise the XKB settings to suit your keyboard, modify the
# lines below (which are the defaults).  For example, for a non-U.S.
# keyboard, you will probably want to use:
#    XkbModel    "pc102"
# If you have a US Microsoft Natural keyboard, you can use:
#    XkbModel    "microsoft"
#
# Then to change the language, change the Layout setting.
# For example, a german layout can be obtained with:
#    XkbLayout   "de"
# or:
#    XkbLayout   "de"
#    XkbVariant  "nodeadkeys"
#
# If you'd like to switch the positions of your capslock and
# control keys, use:
     XkbOptions  "ctrl:nocaps"

# These are the default XKB settings for XFree86
#    XkbRules    "xfree86"
#    XkbModel    "pc101"
#    XkbLayout   "us"
#    XkbVariant  ""
#    XkbOptions  ""

    XkbKeycodes     "xfree86"
    XkbTypes        "default"
    XkbCompat       "default"
    XkbSymbols      "us(pc101)"
    XkbGeometry     "pc"
    XkbRules        "xfree86"
    XkbModel        "pc101"
    XkbLayout       "us"
EndSection
"""

    def mouseSection (self):
        return """
# **********************************************************************
# Pointer section
# **********************************************************************

Section "Pointer"
    Protocol    "%(mouseProto)s"
    Device      "%(mouseDev)s"

# When using XQUEUE, comment out the above two lines, and uncomment
# the following line.
#    Protocol	"Xqueue"

# Baudrate and SampleRate are only for some Logitech mice
#    BaudRate	9600
#    SampleRate	150

# Emulate3Buttons is an option for 2-button Microsoft mice
# Emulate3Timeout is the timeout in milliseconds (default is 50ms)
    Emulate3Buttons
    Emulate3Timeout    50

# ChordMiddle is an option for some 3-button Logitech mice
#    ChordMiddle

EndSection
""" % self.mouse
        
    def monitorSection (self):
        info = {}
        
        if self.monEisa:
            info["EISA"] = self.monEisa
        else:
            info["EISA"] = "My Monitor"

        self.monID = info["EISA"]

        if self.monVert:
            info["VERT"] = self.monVert
        else:
            info["VERT"] = "50-100"

        if self.monHoriz:
            info["HORIZ"] = self.monHoriz
        else:
            info["HORIZ"] = "50-100"
        
        return """
# **********************************************************************
# Monitor section
# **********************************************************************

# Any number of monitor sections may be present
Section "Monitor"

    Identifier  "%(EISA)s"
    VendorName  "Unknown"
    ModelName   "Unknown"

# HorizSync is in kHz unless units are specified.
# HorizSync may be a comma separated list of discrete values, or a
# comma separated list of ranges of values.
# NOTE: THE VALUES HERE ARE EXAMPLES ONLY.  REFER TO YOUR MONITOR'S
# USER MANUAL FOR THE CORRECT NUMBERS.

    HorizSync   %(HORIZ)s

# VertRefresh is in Hz unless units are specified.
# VertRefresh may be a comma separated list of discrete values, or a
# comma separated list of ranges of values.
# NOTE: THE VALUES HERE ARE EXAMPLES ONLY.  REFER TO YOUR MONITOR'S
# USER MANUAL FOR THE CORRECT NUMBERS.

    VertRefresh %(VERT)s

# Modes can be specified in two formats.  A compact one-line format, or
# a multi-line format.

# These two are equivalent

#    ModeLine "1024x768i" 45 1024 1048 1208 1264 768 776 784 817 Interlace

#    Mode "1024x768i"
#        DotClock	45
#        HTimings	1024 1048 1208 1264
#        VTimings	768 776 784 817
#        Flags		"Interlace"
#    EndMode

# This is a set of standard mode timings. Modes that are out of monitor spec
# are automatically deleted by the server (provided the HorizSync and
# VertRefresh lines are correct), so there's no immediate need to
# delete mode timings (unless particular mode timings don't work on your
# monitor). With these modes, the best standard mode that your monitor
# and video card can support for a given resolution is automatically
# used.

# Low-res Doublescan modes
# If your chipset does not support doublescan, you get a 'squashed'
# resolution like 320x400.

# --320x200--
# 320x200 @ 70 Hz, 31.5 kHz hsync, 8:5 aspect ratio
    Modeline "320x200"     12.588 320  336  384  400
                                  200  204  205  225 Doublescan
# 320x240 @ 60 Hz, 31.5 kHz hsync, 4:3 aspect ratio
    Modeline "320x240"     12.588 320  336  384  400
                                  240  245  246  262 Doublescan
# 320x240 @ 72 Hz, 36.5 kHz hsync
    Modeline "320x240"     15.750 320  336  384  400
                                  240  244  246  262 Doublescan
# --400x300--
# 400x300 @ 56 Hz, 35.2 kHz hsync, 4:3 aspect ratio
    ModeLine "400x300"     18     400  416  448  512
                                  300  301  302  312 Doublescan
# 400x300 @ 60 Hz, 37.8 kHz hsync
    Modeline "400x300"     20     400  416  480  528
                                  300  301  303  314 Doublescan
# 400x300 @ 72 Hz, 48.0 kHz hsync
    Modeline "400x300"     25     400  424  488  520
                                  300  319  322  333 Doublescan
# 480x300 @ 56 Hz, 35.2 kHz hsync, 8:5 aspect ratio
    ModeLine "480x300"     21.656 480  496  536  616
                                  300  301  302  312 Doublescan
# 480x300 @ 60 Hz, 37.8 kHz hsync
    Modeline "480x300"     23.890 480  496  576  632
                                  300  301  303  314 Doublescan
# 480x300 @ 63 Hz, 39.6 kHz hsync
    Modeline "480x300"     25     480  496  576  632
                                  300  301  303  314 Doublescan
# 480x300 @ 72 Hz, 48.0 kHz hsync
    Modeline "480x300"     29.952 480  504  584  624
                                  300  319  322  333 Doublescan

# Normal video modes

# -- 512x384
# 512x384 @ 78 Hz, 31.50 kHz hsync
    Modeline "512x384"    20.160 512  528  592  640
                                 384  385  388  404 -HSync -VSync
# 512x384 @ 85 Hz, 34.38 kHz hsync
    Modeline "512x384"    22     512  528  592  640
                                 384  385  388  404 -HSync -VSync

# --- 640x480 ---
# 640x480 @ 60 Hz, 31.5 kHz hsync
    Modeline "640x480"     25.175 640  664  760  800
                                  480  491  493  525
# 640x400 @ 70 Hz, 31.5 kHz hsync
    Modeline "640x400"     25.175 640  664  760  800
                                  400  409  411  450
# 640x480 @ 72 Hz, 36.5 kHz hsync
    Modeline "640x480"     31.5   640  680  720  864
                                  480  488  491  521
# 640x480 @ 75 Hz, 37.50 kHz hsync
    ModeLine  "640x480"    31.5   640  656  720  840
                                  480  481  484  500 -HSync -VSync
# 640x400 @ 85 Hz, 37.86 kHz hsync
    Modeline "640x400"     31.5   640  672 736   832
                                  400  401  404  445 -HSync +VSync
# 640x480 @ 85 Hz, 43.27 kHz hsync
    Modeline "640x480"     36     640  696  752  832
                                  480  481  484  509 -HSync -VSync
# 640x480 @ 100 Hz, 53.01 kHz hsync
    Modeline "640x480"     45.8   640  672  768  864
                                  480  488  494  530 -HSync -VSync

# --- 800x600 ---
# 800x600 @ 56 Hz, 35.15 kHz hsync
    ModeLine "800x600"     36     800  824  896 1024
                                  600  601  603  625
# 800x600 @ 60 Hz, 37.8 kHz hsync
    Modeline "800x600"     40     800  840  968 1056
                                  600  601  605  628 +hsync +vsync
# 800x600 @ 72 Hz, 48.0 kHz hsync
    Modeline "800x600"     50     800  856  976 1040
                                  600  637  643  666 +hsync +vsync
# 800x600 @ 85 Hz, 55.84 kHz hsync
    Modeline  "800x600"    60.75  800  864  928 1088
                                  600  616  621  657 -HSync -VSync
# 800x600 @ 100 Hz, 64.02 kHz hsync
    Modeline  "800x600"    69.65  800  864  928 1088
                                  600  604  610  640 -HSync -VSync

# --- 1024x768 ---
# 1024x768 @ 60 Hz, 48.4 kHz hsync
    Modeline "1024x768"    65    1024 1032 1176 1344
                                 768  771  777  806 -hsync -vsync
# 1024x768 @ 87 Hz interlaced, 35.5 kHz hsync
    Modeline "1024x768"    44.9  1024 1048 1208 1264
                                 768  776  784  817 Interlace
# 1024x768 @ 70 Hz, 56.5 kHz hsync
    Modeline "1024x768"    75    1024 1048 1184 1328
                                 768  771  777  806 -hsync -vsync
# 1024x768 @ 76 Hz, 62.5 kHz hsync
    Modeline "1024x768"    85    1024 1032 1152 1360
                                 768  784  787  823
# 1024x768 @ 85 Hz, 70.24 kHz hsync
    Modeline "1024x768"   98.9  1024 1056 1216 1408
                                768 782 788 822 -HSync -VSync
# 1024x768 @ 100Hz, 80.21 kHz hsync
    Modeline "1024x768"   115.5  1024 1056 1248 1440
                                 768  771  781  802 -HSync -VSync

# --- 1152x864 ---
# 1152x864 @ 60 Hz, 53.5 kHz hsync
    Modeline  "1152x864"   89.9  1152 1216 1472 1680
                                 864  868  876  892 -HSync -VSync
# 1152x864 @ 70 Hz, 62.4 kHz hsync
    Modeline  "1152x864"   92    1152 1208 1368 1474
                                 864  865  875  895
# 1152x864 @ 78 Hz, 70.8 kHz hsync
    Modeline "1152x864"   110   1152 1240 1324 1552
                                864  864  876  908
# 1152x864 @ 84 Hz, 76.0 kHz hsync
    Modeline "1152x864"   135    1152 1464 1592 1776
                                 864  864  876  908
# 1152x864 @ 89 Hz interlaced, 44 kHz hsync
    ModeLine "1152x864"    65    1152 1168 1384 1480
                                 864  865  875  985 Interlace
# 1152x864 @ 100 Hz, 89.62 kHz hsync
    Modeline "1152x864"   137.65 1152 1184 1312 1536
                                 864  866  885  902 -HSync -VSync

# -- 1280x1024 --
# 1280x1024 @ 61 Hz, 64.2 kHz hsync
    Modeline "1280x1024"  110    1280 1328 1512 1712
                                 1024 1025 1028 1054
# 1280x1024 @ 70 Hz, 74.59 kHz hsync
    Modeline "1280x1024"  126.5 1280 1312 1472 1696
                                1024 1032 1040 1068 -HSync -VSync
# 1280x1024 @ 74 Hz, 78.85 kHz hsync
    Modeline "1280x1024"  135    1280 1312 1456 1712
                                 1024 1027 1030 1064
# 1280x1024 @ 76 Hz, 81.13 kHz hsync
    Modeline "1280x1024"  135    1280 1312 1416 1664
                                 1024 1027 1030 1064
# 1280x1024 @ 85 Hz, 91.15 kHz hsync
    Modeline "1280x1024"  157.5  1280 1344 1504 1728
                                 1024 1025 1028 1072 +HSync +VSync
# 1280x1024 @ 87 Hz interlaced, 51 kHz hsync
    Modeline "1280x1024"   80    1280 1296 1512 1568
                                 1024 1025 1037 1165 Interlace
# 1280x1024 @ 100 Hz, 107.16 kHz hsync
    Modeline "1280x1024"  181.75 1280 1312 1440 1696
                                 1024 1031 1046 1072 -HSync -VSync

# -- 1600x1200 --
# 1600x1200 @ 60Hz, 75.00 kHz hsync
    Modeline "1600x1200"  162   1600 1664 1856 2160
                                1200 1201 1204 1250 +HSync +VSync
# 1600x1200 @ 70 Hz, 87.50 kHz hsync
    Modeline "1600x1200"  189    1600 1664 1856 2160
                                 1200 1201 1204 1250 -HSync -VSync
# 1600x1200 @ 75 Hz, 93.75 kHz hsync
    Modeline "1600x1200"  202.5  1600 1664 1856 2160
                                 1200 1201 1204 1250 +HSync +VSync
# 1600x1200 @ 85 Hz, 105.77 kHz hsync
    Modeline "1600x1200"  220    1600 1616 1808 2080
                                 1200 1204 1207 1244 +HSync +VSync

# -- 1800x1400 -- 

# 1800x1440 @ 64Hz, 96.15 kHz hsync 
    ModeLine "1800X1440"  230    1800 1896 2088 2392
                                 1440 1441 1444 1490 +HSync +VSync
# 1800x1440 @ 70Hz, 104.52 kHz hsync 
    ModeLine "1800X1440"  250    1800 1896 2088 2392
                                 1440 1441 1444 1490 +HSync +VSync
EndSection
""" % info

    def deviceSection (self):
        section = """
# **********************************************************************
# Graphics device section
# **********************************************************************

Section "Device"
    Identifier        "Generic VGA Card"
    VendorName        "Unknown"
    BoardName         "Unknown"
    Chipset           "generic"
EndSection

"""
        for card in self.vidCards:
            section = section + """
Section "Device"
    Identifier         "%(NAME)s"
""" % card
            if card.has_key ("VENDOR"):
                section = section + '    VendorName         "%(VENDOR)s"\n' % card
            if card.has_key ("BOARDNAME"):
                section = section + '    BoardName          "%(BOARD)s"\n' % card
            if card.has_key ("RAMDAC"):
                section = section + '    Ramdac             "%(RAMDAC)s"\n' % card
            if card.has_key ("LINE"):
                section = section + card["LINE"] + "\n"
            if self.vidRam:
                section = section + '    VideoRam           %s\n' % (self.vidRam,) 
            section = section + "EndSection\n"
        return section

    def screenSection (self):
        info = { "DEVICE"  : self.devID,
                 "MONITOR" : self.monID }
        section = """
# **********************************************************************
# Screen section
# **********************************************************************

# The kernel framebuffer server
Section "Screen"
    Driver      "fbdev"
    Device      "Generic VGA Card"
    Monitor     "%(MONITOR)s"
    Subsection  "Display"
#        Depth       16
        Modes       "default"
    EndSubsection
EndSection

# The 16-color VGA server
Section "Screen"
    Driver      "vga16"
    Device      "Generic VGA Card"
    Monitor     "%(MONITOR)s"
    Subsection "Display"
        Modes       "640x480" "800x600"
        ViewPort    0 0
    EndSubsection
EndSection

# The Mono server
Section "Screen"
    Driver      "vga2"
    Device      "Generic VGA Card"
    Monitor     "%(MONITOR)s"
    Subsection "Display"
        Modes       "640x480" "800x600"
        ViewPort    0 0
    EndSubsection
EndSection
""" % info
        for driver in [ "svga", "accel" ]:
            info["DRIVER"] = driver
            section = section + """
# The %(DRIVER)s server
Section "Screen"
    Driver      "%(DRIVER)s"
    Device      "%(DEVICE)s"
    Monitor     "%(MONITOR)s"
""" % info
            for depth in self.modes.keys ():
		if not self.modes[depth]: continue
                section = section + """
    Subsection "Display"
        Depth       %s
        Modes       """ % depth
                for res in self.modes[depth]:
                    section = section + '"' + res + '" '
                section = section + """
        ViewPort    0 0
    EndSubsection
"""
            section = section + "EndSection\n"
        return section

if __name__ == "__main__":
    sys.path.append ("kudzu")
    x = XF86Config ()

    x.probe ()
    print x.preludeSection ()
    print x.inputSection ()
    print x.mouseSection ()
    print x.monitorSection ()
    print x.deviceSection ()
    x.modes["8"] = [ "640x480" ]
    x.modes["16"] = [ "640x480" ]
    x.modes["32"] = [ "640x480" ]
    print x.screenSection ()
