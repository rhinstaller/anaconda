#
# zfcp_text.py: mainframe FCP configuration dialog
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2004 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from snack import *
from constants import *
from constants_text import *
from rhpl.translate import _
from flags import flags
from rhpl.log import log
import isys,iutil
import copy

class ZFCPWindow:
    def editDevice(self, screen, fcpdev):
	buttons = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON])
        if fcpdev is None:
            dev = ("", "", "", "", "")
        else:
            dev = fcpdev

        devLabel = Label(_("Device number:"))
        devEntry = Entry(20, scroll = 1, text = dev[0])
        sidLabel = Label(_("SCSI ID:"))
        sidEntry = Entry(20, scroll = 1, text = dev[1])
        wwpnLabel = Label(_("WWPN:"))
        wwpnEntry = Entry(20, scroll = 1, text = dev[2])
        slunLabel = Label(_("SCSI LUN:"))
        slunEntry = Entry(20, scroll = 1, text = dev[3])
        fcplunLabel = Label(_("FCP LUN:"))
        fcplunEntry = Entry(20, scroll = 1, text = dev[4])

        subgrid = Grid(2, 5)
        idx = 0
        for (lab, ent) in ( (devLabel, devEntry), (sidLabel, sidEntry),
                            (wwpnLabel, wwpnEntry), (slunLabel, slunEntry),
                            (fcplunLabel, fcplunEntry) ):
            subgrid.setField(lab, 0, idx, anchorLeft = 1)
            subgrid.setField(ent, 1, idx, padding = (1, 0, 0, 0),
                             anchorLeft = 1)
            idx += 1

        g = GridFormHelp(screen, _("FCP Device"), "fcpdev", 1, 2)
	g.add(subgrid, 0, 0, padding = (0, 0, 0, 1))
	g.add(buttons, 0, 1, growx = 1)

	result = ""
        while (result != TEXT_OK_CHECK and result != TEXT_F12_CHECK):
	    result = g.run()

	    if (buttons.buttonPressed(result)):
		result = buttons.buttonPressed(result)

	    if (result == "cancel"):
		screen.popWindow ()
		res = fcpdev
                break
            
            elif (result  == TEXT_OK_CHECK or result == TEXT_F12_CHECK):
                # FIXME: do sanity checking here

                fcpdev = (devEntry.value(), sidEntry.value(), wwpnEntry.value(), slunEntry.value(), fcplunEntry.value())
                res = fcpdev
                break

        screen.popWindow()
        return fcpdev

    def formatDevice(self, dev, wwpn, lun):
        return "%-10s  %-25s  %-15s" %(dev, wwpn, lun)

    def fillListbox(self, listbox, fcpdevs):
        def sortFcpDevs(one, two):
            if one[0] < two[0]:
                return -1
            elif one[0] > two[0]:
                return 1
            return 0
        
        listbox.clear()
        fcpdevs.sort(sortFcpDevs)
        for dev in fcpdevs:
            listbox.append(self.formatDevice(dev[0], dev[2], dev[4]), dev[0])
        if len(fcpdevs) == 0:
            listbox.append(self.formatDevice("", "", ""), "")
        
    def __call__(self, screen, fcp, diskset, intf):
        fcp.cleanFcpSysfs(fcp.fcpdevices)

        fcpdevs = copy.copy(fcp.fcpdevices)
        
	listboxLabel = Label(     "%-10s  %-25s %-15s" % 
		( _("Device #"), _("WWPN"), _("FCP LUN")))
	listbox = Listbox(5, scroll = 1, returnExit = 0)

        self.fillListbox(listbox, fcpdevs)

        buttons = ButtonBar(screen, [ TEXT_OK_BUTTON,
                                      (_("Add"), "add"),
                                      (_("Edit"), "edit"),
                                      (_("Remove"), "remove"),
                                      TEXT_BACK_BUTTON ])

        text = TextboxReflowed(55,
                               ("Need some text here about zfcp"))

	g = GridFormHelp(screen, _("FCP Devices"), 
			 "zfcpconfig", 1, 4)
	g.add(text, 0, 0, anchorLeft = 1)
	g.add(listboxLabel, 0, 1, padding = (0, 1, 0, 0), anchorLeft = 1)
	g.add(listbox, 0, 2, padding = (0, 0, 0, 1), anchorLeft = 1)
	g.add(buttons, 0, 3, growx = 1)

        g.addHotKey("F2")
        g.addHotKey("F3")
        g.addHotKey("F4")        

        result = None
        while (result != TEXT_OK_CHECK and result != TEXT_BACK_CHECK and result != TEXT_F12_CHECK):
            result = g.run()
            if (buttons.buttonPressed(result)):
                result = buttons.buttonPressed(result)

            # edit
            if (result == "edit" or result == listbox or result == "F3"):
                item = listbox.current()
                if item == "":
                    continue
                for i in range(0, len(fcpdevs)):
                    if fcpdevs[i][0] == item:
                        break
                if (i >= len(fcpdevs)):
                    raise ValueError, "Unable to find item: %s" %(item,)
                dev = self.editDevice(screen, fcpdevs[i])
                fcpdevs[i] = dev
                self.fillListbox(listbox, fcpdevs)
                listbox.setCurrent(dev[0])

            elif (result == "add" or result == "F2"):
                dev = self.editDevice(screen, None)
                fcpdevs.append(dev)
                self.fillListbox(listbox, fcpdevs)
                listbox.setCurrent(dev[0])

            elif (result == "remove" or result == "F4"):
                item = listbox.current()
                if item == "":
                    continue
                for i in range(0, len(fcpdevs)):
                    if fcpdevs[i][0] == item:
                        break
                if (i >= len(fcpdevs)):
                    raise ValueError, "Unable to find item: %s" %(item,)
                fcpdevs.pop(i)
                self.fillListbox(listbox, fcpdevs)

        screen.popWindow()

        if (result == TEXT_BACK_CHECK):
            return INSTALL_BACK

        fcp.fcpdevices = fcpdevs

        # FIXME: this should be common between tui & gui
        fcp.writeFcpSysfs(fcp.fcpdevices)
        isys.flushDriveDict()
        self.diskset.refreshDevices(intf)
        try:
            iutil.makeDriveDeviceNodes()
        except:
            pass
        
        return INSTALL_OK
