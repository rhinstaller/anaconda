#
# mouse.py: mouse configuration data
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import kudzu
from simpleconfig import SimpleConfigFile
import os
from translate import _, N_

class Mouse (SimpleConfigFile):
    mice = {
        # (gpm protocol, X protocol, device, emulate3, shortname)
        N_("ALPS - GlidePoint (PS/2)"):
        ("ps/2", "GlidePointPS/2", "psaux", 1, "alpsps/2"),
	N_("ASCII - MieMouse (serial)"):
        ("ms3", "IntelliMouse", "ttyS", 0, "ascii"),
	N_("ASCII - MieMouse (PS/2)"):
        ("ps/2", "NetMousePS/2", "psaux", 1, "asciips/2"),
	N_("ATI - Bus Mouse"):
        ("Busmouse", "BusMouse", "atibm", 1, "atibm"),
	N_("Generic - 2 Button Mouse (serial)"):
        ("Microsoft", "Microsoft", "ttyS", 1, "generic"),
	N_("Generic - 3 Button Mouse (serial)"):
        ("Microsoft", "Microsoft", "ttyS", 0, "generic3"),
	N_("Generic - 2 Button Mouse (PS/2)"):
        ("ps/2", "PS/2", "psaux", 1, "genericps/2"),
	N_("Generic - 3 Button Mouse (PS/2)"):
        ("ps/2", "PS/2", "psaux", 0, "generic3ps/2"),
	N_("Generic - 2 Button Mouse (USB)"):
        ("imps2", "IMPS/2", "input/mice", 1, "genericusb"),
	N_("Generic - 3 Button Mouse (USB)"):
        ("imps2", "IMPS/2", "input/mice", 0, "generic3usb"),
	N_("Genius - NetMouse (serial)"):
        ("ms3", "IntelliMouse", "ttyS", 1, "geniusnm"),
	N_("Genius - NetMouse (PS/2)"):
        ("netmouse", "NetMousePS/2", "psaux", 1, "geniusnmps/2"),
	N_("Genius - NetMouse Pro (PS/2)"):
        ("netmouse", "NetMousePS/2", "psaux", 1, "geniusprops/2"),
	N_("Genius - NetScroll (PS/2)"):
        ("netmouse", "NetScrollPS/2", "psaux", 1, "geniusscrollps/2"),
	N_("Genius - NetScroll+ (PS/2)") :
        ("netmouse", "NetMousePS/2", "psaux", 1, "geniusscrollps/2+"),
	N_("Kensington - Thinking Mouse (serial)"):
        ("Microsoft", "ThinkingMouse", "ttyS", 1, "thinking"),
	N_("Kensington - Thinking Mouse (PS/2)"):
        ("ps/2", "ThinkingMousePS/2", "psaux", 1, "thinkingps/2"),
	N_("Logitech - C7 Mouse (serial, old C7 type)"):
        ("Logitech", "Logitech", "ttyS", 0, "logitech"),
	N_("Logitech - CC Series (serial)"):
        ("logim", "MouseMan", "ttyS", 0, "logitechcc"),
	N_("Logitech - Bus Mouse"):
        ("Busmouse", "BusMouse", "logibm", 0, "logibm"),
	N_("Logitech - MouseMan/FirstMouse (serial)"):
        ("MouseMan", "MouseMan", "ttyS", 0, "logimman"),
	N_("Logitech - MouseMan/FirstMouse (PS/2)"):
        ("ps/2", "PS/2", "psaux", 0, "logimmanps/2"),
	N_("Logitech - MouseMan+/FirstMouse+ (serial)"):
        ("pnp", "IntelliMouse", "ttyS", 0, "logimman+"),
        N_("Logitech - MouseMan+/FirstMouse+ (PS/2)"):
        ("ps/2", "MouseManPlusPS/2", "psaux", 0, "logimman+ps/2"),
	N_("Logitech - MouseMan Wheel (USB)"):
        ("ps/2", "IMPS/2", "input/mice", 0, "logimmusb"),
	N_("Microsoft - Compatible Mouse (serial)"):
        ("Microsoft", "Microsoft", "ttyS", 1, "microsoft"),
	N_("Microsoft - Rev 2.1A or higher (serial)"):
        ("pnp", "Auto", "ttyS", 1, "msnew"),
	N_("Microsoft - IntelliMouse (serial)"):
        ("ms3", "IntelliMouse", "ttyS", 0, "msintelli"),
	N_("Microsoft - IntelliMouse (PS/2)"):
        ("imps2", "IMPS/2", "psaux", 0, "msintellips/2"),
        
	N_("Microsoft - IntelliMouse (USB)"):
        ("ps/2", "IMPS/2", "input/mice", 0, "msintelliusb"),
        
	N_("Microsoft - Bus Mouse"):
        ("Busmouse", "BusMouse", "inportbm", 1, "msbm"),
	N_("Mouse Systems - Mouse (serial)"):
        ("MouseSystems", "MouseSystems", "ttyS", 1, "mousesystems"), 
	N_("MM - Series (serial)"):
        ("MMSeries", "MMSeries", "ttyS", 1, "mmseries"),
	N_("MM - HitTablet (serial)"):
        ("MMHitTab", "MMHittab", "ttyS", 1, "mmhittab"),
        "None - None" :
                ("none", "none", None, 0, "none"),
	N_("Sun - Mouse"): ("sun", "sun", "sunmouse", 0, "sun"),
	}
    
    
    def mouseToMouse(self):
        types = {}
        for mouse in self.mice.keys():
            mouseType = self.mice[mouse][4]
            types[mouseType] = mouse
        return types
        

    # XXX fixme - externalize
    def __init__ (self, skipProbe = 0):
        self.info = {}
        self.device = None
        self.emulate = 0
        self.set ("Generic - 3 Button Mouse (PS/2)")
	self.wasProbed = 0
	if not skipProbe:
	    self.probe()

        self.orig_mouse = self.get()

    def get_Orig(self):
        return self.orig_mouse
        
    def probed(self):
	return self.wasProbed

    def probe (self, frob = 0):

        list = kudzu.probe(kudzu.CLASS_MOUSE, kudzu.BUS_UNSPEC, 
                           kudzu.PROBE_ONE)

        if (list):
            (device, module, desc) = list[0]
            
            if frob and device == 'psaux':
            # jumpstart some ps/2 mice.  Blame the kernel
                try:
                    f = open ('/dev/psaux')
                    f.write ('1')
                    f.close()
                except:
                    pass

            if device == "sunmouse":
                self.set("Sun - Mouse", 0)
            elif device == "psaux":
                self.set("Generic - 3 Button Mouse (PS/2)", 0)
            elif device == "input/mice":
                if module == "generic3usb" or module == "mousedev":
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

    def shortDescription(self):
        if self.info.has_key("FULLNAME"):
            return self.info["FULLNAME"]
        else:
            return _("Unable to probe")

    def setDevice(self, device):
	self.device = device

    def set (self, mouse, emulateThreeButtons = -1, thedev = None):
        (gpm, x11, dev, em, shortname) = self.mice[mouse]
        self.info["MOUSETYPE"] = gpm
        self.info["XMOUSETYPE"] = x11
        self.info["FULLNAME"] = mouse
        if emulateThreeButtons != -1:
            self.emulate = emulateThreeButtons
        else:
            self.emu = em
        if thedev:
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
            and not self.info["XMOUSETYPE"] == "NetMousePS/2"
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

    def write(self, instPath):
        if self.info["FULLNAME"] == "None - None":
            return
	f = open(instPath + "/etc/sysconfig/mouse", "w")
	f.write(str (self))
	f.close()
	self.makeLink(instPath)


    def writeKS(self, f):
        f.write("mouse")

        for arg in self.getArgList():
            f.write(" " + arg)
        f.write("\n")


    def getArgList(self):
        args = []

        if self.info["FULLNAME"]:
            mouseName = self.info["FULLNAME"]
            args.append(self.mice[mouseName][4])
        if self.device:
            args.append("--device %s" %(self.device))
        if self.emulate:
            args.append("--emulthree")
        
        return args


# maybe doesnt belong here - just ask user what mouse they have on
# startup if kudzu didn't find one
def mouseWindow(mouse):
    from snack import ButtonChoiceWindow, SnackScreen
    from mouse_text import MouseWindow, MouseDeviceWindow
    from constants_text import INSTALL_BACK, INSTALL_OK
    import string
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
