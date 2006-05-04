#
# zfcp_text.py: mainframe FCP configuration dialog
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2004-2006 Red Hat, Inc.
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
import copy

class ZFCPWindow:
    def editDevice(self, screen, fcpdev):
        buttons = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON])
        if fcpdev is None:
            dev = ("", "", "", "", "")
        else:
            dev = fcpdev

        subgrid = Grid(2, 5)
        idx = 0
        entrys = {}
        label = {}
        for t in range(len(self.options)):
            label[t] = Label("%s:" %(self.options[t][0],))
            entrys[t] = Entry(20, scroll = 1, text = dev[t])
            subgrid.setField(label[t], 0, idx, anchorLeft = 1)
            subgrid.setField(entrys[t], 1, idx, padding = (1, 0, 0, 0),
                             anchorLeft = 1)
            idx += 1

        g = GridFormHelp(screen, _("FCP Device"), "fcpdev", 1, 2)
        g.add(subgrid, 0, 0, padding = (0, 0, 0, 1))
        g.add(buttons, 0, 1, growx = 1)

        tmpvals = {}
        while 1:
            invalid = 0
            rc = g.run()
            result = buttons.buttonPressed(rc)
            if result == "cancel":
                screen.popWindow()
                break;
            if result == "ok" or rc == "F12":
                for t in range(len(self.options)):
                    tmpvals[t] = entrys[t].value()
                    tmpvals[t] = self.options[t][3](tmpvals[t])   # sanitize input
                    if tmpvals[t] is not None:                    # update text
                        entrys[t].set(tmpvals[t])
                    if self.options[t][4](tmpvals[t]) == -1:      # validate input
                        ButtonChoiceWindow (screen, _("Error With Data"),
                                            self.options[t][2])
                        invalid = 1
                        break

                if invalid == 0:
                    screen.popWindow()
                    return tmpvals
                    break
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
        if len(fcpdevs) == 0:
            listbox.append(self.formatDevice("", "", ""), "")
            return
        for dev in fcpdevs:
            if dev != None:
                listbox.append(self.formatDevice(dev[0], dev[2], dev[4]), dev[0])

    def __call__(self, screen, anaconda):
        anaconda.id.zfcp.cleanFcpSysfs(anaconda.id.zfcp.fcpdevices)

        fcpdevs = copy.copy(anaconda.id.zfcp.fcpdevices)

        self.options = anaconda.id.zfcp.options

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
                               (fcp.description))

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
                if dev is not None:
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

        anaconda.id.zfcp.fcpdevices = fcpdevs

        anaconda.id.zfcp.updateConfig(anaconda.id.zfcp.fcpdevices,
                                      anaconda.id.diskset, anadonda.intf)

        return INSTALL_OK

# vim:tw=78:ts=4:et:sw=4
