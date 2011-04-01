#
# bootloader_main_gui.py: gui bootloader configuration dialog
#
# Copyright (C) 2001, 2002  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Jeremy Katz <katzj@redhat.com>
#

import gtk
import gobject
from pyanaconda import gui, iutil
from iw_gui import *
from pyanaconda.constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

from osbootwidget import OSBootWidget
from blpasswidget import BootloaderPasswordWidget


class MainBootloaderWindow(InstallWindow):
    windowTitle = N_("Boot Loader Configuration")

    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        self.parent = ics.getICW().window


    def getPrev(self):
        pass


    def getNext(self):
        # go ahead and set the device even if we already knew it
        # since that won't change anything
        self.bl.stage1_device = self.bldev
        self.bl.drive_order = self.driveorder

        if not self.grubCB.get_active():
            # if we're not installing a boot loader, don't show the second
            # screen and don't worry about other options
            self.dispatch.skipStep("instbootloader", skip = 1)
            return
        else:
            self.dispatch.skipStep("instbootloader", skip = 0)

        # set the password
        self.bl.password = self.blpass.getPassword()

        # set the bootloader images based on what's in our list
        self.oslist.setBootloaderImages()

    def bootloaderChanged(self, *args):
        active = self.grubCB.get_active()

        for widget in [ self.oslist.getWidget(), self.blpass.getWidget(), self.deviceButton ]:
            if widget:
                widget.set_sensitive(active)

    def _deviceChange(self, b, anaconda, *args):
        def __genStore(combo, disks, active):
            model = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
            combo.set_model(model)
            cell = gtk.CellRendererText()
            combo.pack_start(cell, True)
            combo.set_attributes(cell, text = 0)

            for disk in disks:
                i = model.append(None)
                model[i] = ("%s %8.0f MB %s" %(disk.name, disk.size,
                                               disk.description),
                            disk)
                if disk.name == active:
                    combo.set_active_iter(i)

            return model

        (dxml, dialog) = gui.getGladeWidget("blwhere.glade",
                                            "blwhereDialog")
        gui.addFrame(dialog)
        dialog.set_transient_for(self.parent)
        dialog.show()

        # XXX for md stage1, should we show md, first member disk, or first
        #     disk?
        stage1 = anaconda.platform.bootLoaderDevice
        stage1_desc = anaconda.bootloader.device_description(stage1)
        choices = {"mbr": (stage1, stage1_desc)}

        stage2 = anaconda.platform.bootDevice
        try:
            stage2_desc = anaconda.bootloader.device_description(stage2)
        except ValueError:
            # stage2's type isn't valid as stage1, so don't offer "boot".
            pass
        else:
            choices["boot"] = (stage2, stage2_desc)

        for t in ("mbr", "boot"):
            if not choices.has_key(t):
                continue
            (device, desc) = choices[t]
            w = dxml.get_widget("%sRadio" %(t,))
            w.set_label("%s - %s" %(desc, device.path))
            w.show()
            w.set_active(self.bldev == device)
            w.set_data("bootDevice", device)

        bl_disks = anaconda.platform.bootloader.drives
        for i in range(1, 5):
            if len(self.driveorder) < i:
                break
            combo = dxml.get_widget("bd%dCombo" %(i,))
            lbl = dxml.get_widget("bd%dLabel" %(i,))
            combo.show()
            lbl.show()
            m = __genStore(combo, bl_disks, self.driveorder[i - 1])

        while True:
            rc = dialog.run()
            if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
                break

            # set the boot device based on what they chose
            if dxml.get_widget("bootRadio").get_active():
                self.bldev = dxml.get_widget("bootRadio").get_data("bootDevice")
            elif dxml.get_widget("mbrRadio").get_active():
                self.bldev = dxml.get_widget("mbrRadio").get_data("bootDevice")
            else:
                raise RuntimeError, "No radio button selected!"

            # and adjust the boot order
            neworder = []
            for i in range(1, 5):
                if len(self.driveorder) < i:
                    break

                combo = dxml.get_widget("bd%dCombo" %(i,))
                iter = combo.get_active_iter()
                if not iter:
                    continue

                act = combo.get_model()[iter][1].name
                if act not in neworder:
                    neworder.append(act)
            for d in self.driveorder:
                if d not in neworder:
                    neworder.append(d)
            self.driveorder = neworder
            break

        dialog.destroy()
        self.grubCB.set_label(_("_Install boot loader on %s.") %
                              (self.bldev.path,))
        return rc

    def getScreen(self, anaconda):
        self.dispatch = anaconda.dispatch
        self.bl = anaconda.bootloader
        self.intf = anaconda.intf
        self.driveorder = [d.name for d in self.bl.drives]

        thebox = gtk.VBox (False, 12)
        thebox.set_border_width(18)

        # make sure we get a valid device to say we're installing to
        self.bldev = self.bl.stage1_device

        hb = gtk.HBox(False, 12)
        self.grubCB = gtk.CheckButton(_("_Install boot loader on %s.") %
                                      (self.bldev.path,))
        self.grubCB.set_active(not self.dispatch.stepInSkipList("instbootloader"))
        self.grubCB.connect("toggled", self.bootloaderChanged)
        hb.pack_start(self.grubCB, False)

        # no "Change device" button on EFI systems, since there should only
        # be one EFI System Partition available/usable
        self.deviceButton = None
        if not iutil.isEfi():
            self.deviceButton = gtk.Button(_("_Change device"))
            self.deviceButton.connect("clicked", self._deviceChange, anaconda)
            hb.pack_start(self.deviceButton, False)

        thebox.pack_start(hb, False)

        # control whether or not there's a boot loader password and what it is
        self.blpass = BootloaderPasswordWidget(anaconda, self.parent)
        thebox.pack_start(self.blpass.getWidget(), False)

        # configure the systems available to boot from the boot loader
        self.oslist = OSBootWidget(anaconda, self.parent)
        thebox.pack_end(self.oslist.getWidget(), True)

        self.bootloaderChanged()
        return thebox
