#
# mouse_text.py: text mode mouse selection dialog
#
# Copyright 2000-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from snack import *
from constants_text import *
from rhpl.translate import _

class MouseDeviceWindow:
    def __call__(self, screen, mouse):
        choices = { _("/dev/ttyS0 (COM1 under DOS)") : "ttyS0",
                    _("/dev/ttyS1 (COM2 under DOS)") : "ttyS1",
                    _("/dev/ttyS2 (COM3 under DOS)") : "ttyS2",
                    _("/dev/ttyS3 (COM4 under DOS)") : "ttyS3" }

        i = 0
        default = 0
        mousedev = mouse.getDevice()
        if (not mousedev or mousedev[0:4] != "ttyS"): return INSTALL_NOOP

        l = choices.keys()
        l.sort()
        for choice in l:
            if choices[choice] == mousedev:
                default = i
                break
            i = i + 1

        (button, result) = ListboxChoiceWindow(screen, _("Device"),
                    _("What device is your mouse located on?"), l,
                    [ TEXT_OK_BUTTON, TEXT_BACK_BUTTON ], help = "mousedevice", default = default )
        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

        mouse.setDevice(choices[l[result]])

        return INSTALL_OK

class MouseWindow:
    def listcb(self):
        if self.mice[self.micenames[self.l.current()]][3]:
            self.c.setValue("*")
        else:
            self.c.setValue(" ")
            
    def __call__(self, screen, mouse):
#       XXX ewt changed this and we can't figure out why -- we always
#       want to display this dialog so that you can turn on 3 button emu
#	if mouse.probed(): return

        self.mice = mouse.available ()
        mice = self.mice.keys ()
        mice.sort ()
        self.micenames = mice
        (default, emulate) = mouse.get ()
        if default == "Sun - Mouse":
            return INSTALL_NOOP
        default = mice.index (default)

        bb = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON])
        t = TextboxReflowed(40, 
                _("Which model mouse is attached to this computer?"))
        l = Listbox(8, scroll = 1, returnExit = 0)
        self.l = l

        key = 0
        for amouse in mice:
            l.append(_(amouse), key)
            key = key + 1
        l.setCurrent(default)
        l.setCallback (self.listcb)

        c = Checkbox(_("Emulate 3 Buttons?"), isOn = emulate)
        self.c = c

        g = GridFormHelp(screen, _("Mouse Selection"), "mousetype", 1, 4)
        g.add(t, 0, 0)
        g.add(l, 0, 1, padding = (0, 1, 0, 1))
        g.add(c, 0, 2, padding = (0, 0, 0, 1))
        g.add(bb, 0, 3, growx = 1)

        rc = g.runOnce()

        button = bb.buttonPressed(rc)

        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

        choice = l.current()
        emulate = c.selected()

        mouse.set(mice[choice], emulate)

        oldDev = mouse.getDevice()
        if (oldDev):
            newDev = mouse.available()[mice[choice]][2]
            if ((oldDev[0:4] == "ttyS" and newDev[0:4] == "ttyS") or
                (oldDev == newDev)):
                pass
            else:
                mouse.setDevice(newDev)

        return INSTALL_OK
