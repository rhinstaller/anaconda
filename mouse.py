import kudzu
from simpleconfig import SimpleConfigFile
import os

class Mouse (SimpleConfigFile):
    mice = {
        # (gpm protocol, X protocol, emulate3)
	"ALPS - GlidePoint (PS/2)" :
		("ps/2", "GlidePointPS/2", "psaux", 1),
	"ASCII - MieMouse (serial)" :
		("ms3", "IntelliMouse", "ttyS", 0),
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
	"Generic - 2 Button Mouse (USB)" :
		("imps2", "IMPS/2", "input/mice", 1),
	"Generic - 3 Button Mouse (USB)" :
		("imps2", "IMPS/2", "input/mice", 0),
	"Genius - NetMouse (serial)" :
	       ("ms3", "IntelliMouse", "ttyS", 1),
	"Genius - NetMouse (PS/2)" :
		("netmouse", "NetMousePS/2", "psaux", 1),
	"Genius - NetMouse Pro (PS/2)" :
		("netmouse", "NetMousePS/2", "psaux", 1),
	"Genius - NetScroll (PS/2)" :
		("netmouse", "NetScrollPS/2", "psaux", 1),
	"Kensington - Thinking Mouse (serial)" :
		("Microsoft", "ThinkingMouse", "ttyS", 1),
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
	"Logitech - MouseMan/FirstMouse (PS/2)" :
		("ps/2", "PS/2", "psaux", 0),
	"Logitech - MouseMan+/FirstMouse+ (serial)" :
		("pnp", "IntelliMouse", "ttyS", 0),
	"Logitech - MouseMan+/FirstMouse+ (PS/2)" :
		("ps/2", "MouseManPlusPS/2", "psaux", 0),
	"Logitech - MouseMan Wheel (USB)" :
		("ps/2", "IMPS/2", "input/mice", 0),
	"Microsoft - Compatible Mouse (serial)" :
		("Microsoft",    "Microsoft", "ttyS", 1),
	"Microsoft - Rev 2.1A or higher (serial)" :
		("pnp", "Auto", "ttyS", 1),
	"Microsoft - IntelliMouse (serial)" :
		("ms3", "IntelliMouse", "ttyS", 0),
	"Microsoft - IntelliMouse (PS/2)" :
		("imps2", "IMPS/2", "psaux", 0),

	"Microsoft - IntelliMouse (USB)" :
		("ps/2", "IMPS/2", "input/mice", 0),
        
        
	"Microsoft - Bus Mouse" :
		("Busmouse", "BusMouse", "inportbm", 1),
	"Mouse Systems - Mouse (serial)" :
		("MouseSystems", "MouseSystems", "ttyS", 1), 
	"MM - Series (serial)" :
		("MMSeries", "MMSeries", "ttyS", 1),
	"MM - HitTablet (serial)" :
		("MMHitTab", "MMHittab", "ttyS", 1),
        "None - None" :
                ("none", "none", "null", 0),
	"Sun - Mouse":
		("sun", "sun", "sunmouse", 0),
	}

    # XXX fixme - externalize
    def __init__ (self, skipProbe = 0):
        self.info = {}
        self.device = None
        self.emulate = 0
        self.set ("Generic - 3 Button Mouse (PS/2)")
	self.wasProbed = 0
	if not skipProbe:
	    self.probe()

    def probed(self):
	return self.wasProbed

    def probe (self, frob = 0):
        list = kudzu.probe(kudzu.CLASS_MOUSE, kudzu.BUS_UNSPEC, 
                           kudzu.PROBE_ONE)

        if (list):
            (device, module, desc) = list[0]
            
            if frob and device == 'psaux':
            # kickstart some ps/2 mice.  Blame the kernel
                try:
                    f = open ('/dev/psaux')
                    f.write ('1')
                    f.close
                except:
                    pass

            if device == "sunmouse":
                self.set("Sun - Mouse", 0)
            elif device == "psaux":
                self.set("Generic - 3 Button Mouse (PS/2)", 0)
            elif device == "input/mice":
                if module == "generic3usb":
                    self.set("Generic - 3 Button Mouse (USB)", 0)
                elif module == "genericusb":
                    self.set("Generic - 2 Button Mouse (USB)", 1)
            else:
                self.set("Generic - 2 Button Mouse (serial)", 1)

            self.device = device
	    self.wasProbed = 1
            return 1
        else:
            self.set("None - None")
	    self.wasProbed = 0
            return 0
    
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
	if (self.device):
	    os.symlink(self.device, root + "/dev/mouse")

    def getDevice(self):
	return self.device

    def setDevice(self, device):
	self.device = device

    def set (self, mouse, emulateThreeButtons = -1, thedev = None):

        (gpm, x11, dev, em) = self.mice[mouse]
        self.info["MOUSETYPE"] = gpm
        self.info["XMOUSETYPE"] = x11
        self.info["FULLNAME"] = mouse
        if emulateThreeButtons != -1:
            self.emulate = emulateThreeButtons
        else:
            self.emu = em
        if not self.device and thedev:
            self.device = thedev
	if not self.device:
            self.device = dev

    def setXProtocol (self):
        import xmouse
        try:
            curmouse = xmouse.get()
        except RuntimeError:
            # ignore errors when switching mice
            return None
        curmouse[0] = "/dev/" + self.device
        # XXX
        # IntelliMouse requires a full mouse reinit - X does not
        # handle this properly from the mouse extention at this time
        # so leave it alone
        if (not self.info["XMOUSETYPE"] == "IMPS/2"
            and not self.info["XMOUSETYPE"] == "IntelliMouse"
            and not self.info["XMOUSETYPE"] == "None"
            and not self.info["XMOUSETYPE"] == "none"):
            curmouse[1] = self.info["XMOUSETYPE"]

        curmouse[6] = self.emulate
        try:
            apply (xmouse.set, curmouse)
        except RuntimeError:
            pass
        except TypeError:
            pass
