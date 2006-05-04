#
# zipl_text.py: text mode z/IPL setup dialog
#
# Copyright 2001-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil
import isys
import string
from snack import *
from constants_text import *
from rhpl.translate import _

class ZiplWindow:
    def __call__(self, screen, anaconda):
        self.bl = anaconda.id.bootloader

        t = TextboxReflowed(53,
                         _("The z/IPL Boot Loader will be installed "
                           "on your system after installation is complete. "
                           "You can now enter any additional kernel and "
                           "chandev parameters which your machine or your "
                           "setup may require."))

        kernelparms = ""
        kernelentry = Entry(48, scroll = 1, returnExit = 1)
        chandeventry1 = Entry(48, scroll = 1, returnExit = 1)
        chandeventry2 = Entry(48, scroll = 1, returnExit = 1)

        if self.bl.args and self.bl.args.get():
            kernelparms = self.bl.args.get()
        if isys.getDasdPorts() and (kernelparms.find("dasd=") == -1):
            if len(kernelparms) > 0:
                kernelparms = "%s dasd=%s" %(kernelparms, isys.getDasdPorts())
            else:
                kernelparms = "dasd=%s" %(isys.getDasdPorts(),)
        kernelentry.set(kernelparms)

        if self.bl.args and self.bl.args.chandevget():
            cdevs = self.bl.args.chandevget()
            chandeventry1.set('')
            chandeventry2.set('')
            if len(cdevs) > 0:
                chandeventry1.set(cdevs[0])
            if len(cdevs) > 1:
                chandeventry2.set(string.join(cdevs[1:],';'))

        buttons = ButtonBar(screen, [TEXT_OK_BUTTON,
                            TEXT_BACK_BUTTON ] )

        grid = GridFormHelp(screen, _("z/IPL Configuration"), 
                            "zipl-s390", 1, 5)
        grid.add(t, 0, 0)
        sg = Grid(2, 1)
        sg.setField(Label(_("Kernel Parameters") + ": "), 0, 0, anchorLeft=1)
        sg.setField(kernelentry, 1, 0, anchorLeft=1)
        grid.add(sg, 0, 1, padding = (0, 1, 0, 1))
        sg = Grid(2, 1)
        sg.setField(Label(_("Chandev line ") + "1: "), 0, 0, anchorLeft=1)
        sg.setField(chandeventry1, 1, 0, anchorLeft=1)
        grid.add(sg, 0, 2, padding = (0, 1, 0, 1))
        sg = Grid(2, 1)
        sg.setField(Label(_("Chandev line ") + "2: "), 0, 0, anchorLeft=1)
        sg.setField(chandeventry2, 1, 0, anchorLeft=1)
        grid.add(sg, 0, 3, padding = (0, 1, 0, 1))
        grid.add(buttons, 0, 4, growx = 1)

        result = grid.runOnce ()
        button = buttons.buttonPressed(result)
        
        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK

        if kernelentry.value():
            self.bl.args.set(string.strip(kernelentry.value()))
        else:
            self.bl.args.set("")

        cdevs = []
        if chandeventry1.value():
            cdevs.append(string.strip(chandeventry1.value()))
        if chandeventry2.value():
            cdevs.append(string.strip(chandeventry2.value()))
        self.bl.args.chandevset(cdevs)
        return INSTALL_OK
