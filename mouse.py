import kudzu
from simpleconfig import SimpleConfigFile
from snack import *

class Mouse (SimpleConfigFile):
    mice = {
	"ALPS - GlidePoint (PS/2)" :
		("ps/2", "GlidePointPS/2", "psaux", 1),
	"ASCII - MieMouse (serial)" :
		("ms3", "IntelliMouse", "ttyS", 1),
	"ASCII - MieMouse (PS/2)" : 
		("ps/2", "NetMousePS/2", "psaux", 1),
	"ATI - Bus Mouse" :
		("Busmouse", "BusMouse", "atibm", 1),
	"Generic - 2 Button Mouse (serial)" :
		("Microsoft", "Microsoft", "ttyS", 1),
	"Generic - 3 Button Mouse (serial)" :
		("Microsoft", "Microsoft", "ttyS", 0),
	"Generic - 2 Button Mouse (PS/2)" :
		("ps/2", "PS/2", "psaux", 1),
	"Generic - 3 Button Mouse (PS/2)" :
		("ps/2", "PS/2", "psaux", 0),
	"Genius - NetMouse (serial)" :
	       ("ms3", "IntelliMouse", "ttyS", 1),
	"Genius - NetMouse (PS/2)" :
		("netmouse", "NetMousePS/2", "psaux", 1),
	"Genius - NetMouse Pro (PS/2)" :
		("netmouse", "NetMousePS/2", "psaux", 1),
	"Genius - NetScroll (PS/2)" :
		("netmouse", "NetScrollPS/2", "psaux", 1),
	"Kensington - Thinking Mouse (PS/2)" :
		("ps/2", "ThinkingMousePS/2", "psaux", 1),
	"Logitech - C7 Mouse (serial, old C7 type)" :
		("Logitech", "Logitech", "ttyS", 0),
	"Logitech - CC Series (serial)" :
		("logim", "MouseMan", "ttyS", 0),
	"Logitech - Bus Mouse" :
		("Busmouse", "BusMouse", "logibm", 0),
	"Logitech - MouseMan/FirstMouse (serial)" :
		("MouseMan", "MouseMan", "ttyS", 0),
	"Logitech - MouseMan/FirstMouse (ps/2)" :
		("ps/2", "PS/2", "psaux", 0),
	"Logitech - MouseMan+/FirstMouse+ (serial)" :
		("pnp", "IntelliMouse", "ttyS", 0),
	"Logitech - MouseMan+/FirstMouse+ (PS/2)" :
		("ps/2", "MouseManPlusPS/2", "psaux", 0),
	"Microsoft - Compatible Mouse (serial)" :
		("Microsoft",    "Microsoft", "ttyS", 1),
	"Microsoft - Rev 2.1A or higher (serial)" :
		("pnp", "Auto", "ttyS", 1),
	"Microsoft - IntelliMouse (serial)" :
		("ms3", "IntelliMouse", "ttyS", 1),
	"Microsoft - IntelliMouse (PS/2)" :
		("imps2", "IMPS/2", "psaux", 1), 
	"Microsoft - Bus Mouse" :
		("Busmouse", "BusMouse", "inportbm", 1),
	"Mouse Systems - Mouse (serial)" :
		("MouseSystems", "MouseSystems", "ttyS", 1), 
	"MM - Series (serial)" :
		("MMSeries", "MMSeries", "ttyS", 1),
	"MM - HitTablet (serial)" :
		("MMHitTab", "MMHittab", "ttyS", 1),
	}

    # XXX fixme - externalize
    def __init__ (self, xmouseType = None, mouseType = None):
        self.info = {}
        self.device = None

	if (xmouseType):
	    (proto, emulate, device) = xmouseType
	    mouseType = None
	    mice = self.mice.keys()
	    mice.sort()
	    for desc in mice:
		(gpm, x11, dev, em) = self.mice[desc]
		print "trying %s: '%s', '%s'" % (desc, x11, proto)
		if (x11 == proto and desc[0:7] == "Generic" and emulate == em):
		    mouseType = (desc, emulate, device)
		    break
	    self.device = device
	    if not mouseType:
		raise KeyError, "unknown X11 mouse type %s" % proto

        if (mouseType):
	    if (len(mouseType) == 3):
		apply(self.set, mouseType)
	else:
	    list = kudzu.probe(kudzu.CLASS_MOUSE, kudzu.BUS_UNSPEC, 
			       kudzu.PROBE_ONE)
	    if (list):
		(device, module, desc) = list[0]

		if device == "psaux":
		    self.set("Generic - 3 Button Mouse (PS/2)", 0)
		else:
		    self.set("Generic - 2 Button Mouse (serial)", 1)

		self.device = device
	    else:
		self.set("Generic - 2 Button Mouse (serial)", 1, 'ttyS0')

    def available (self):
        return self.mice

    def get (self):
	return (self.info ["FULLNAME"], self.emulate)

    def __str__(self):
	if (self.emulate):
	    self.info["XEMU3"] = "yes"
	else:
	    self.info["XEMU3"] = "no"
	return SimpleConfigFile.__str__(self)

    def makeLink(self, root):
	try:
	    os.unlink(root + "/dev/mouse")
	except:
	    pass
	if (sel.device):
	    os.symlink(self.device, root + "/dev/mouse")

    def getDevice(self):
	return self.device

    def setDevice(self, device):
	self.device = device

    def set (self, mouse, emulateThreeButtons):
        (gpm, x11, dev, em) = self.mice[mouse]
        self.info["MOUSETYPE"] = gpm
        self.info["XMOUSETYPE"] = x11
        self.info["FULLNAME"] = mouse
	self.emulate = emulateThreeButtons
	if (not self.device): self.device = dev

