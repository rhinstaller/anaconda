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
import gui
from iw_gui import *
from constants import *

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
        self.bl.setDevice(self.bldev)

        self.bl.drivelist = self.driveorder

        if not self.grubCB.get_active():
            # if we're not installing a boot loader, don't show the second
            # screen and don't worry about other options
            self.dispatch.skipStep("instbootloader", skip = 1)

            # kind of a hack...
            self.bl.defaultDevice = None
            return
        else:
            self.dispatch.skipStep("instbootloader", skip = 0)
            self.bl.setUseGrub(1)

        # set the password
        self.bl.setPassword(self.blpass.getPassword(), isCrypted = 0)

        # set the bootloader images based on what's in our list
        self.oslist.setBootloaderImages()

    def bootloaderChanged(self, *args):
        active = self.grubCB.get_active()

        for widget in [ self.oslist.getWidget(), self.blpass.getWidget(), self.deviceButton ]:
            widget.set_sensitive(active)


    def _deviceChange(self, b, anaconda, *args):
        def __driveChange(combo, dxml, choices):
            if not choices.has_key("mbr"):
                return

            iter = combo.get_active_iter()
            if not iter:
                return

            first = combo.get_model()[iter][1]
            desc = choices["mbr"][1]
            dxml.get_widget("mbrRadio").set_label("%s - /dev/%s" %(_(desc), first))
            dxml.get_widget("mbrRadio").set_data("bootDevice", first)

        def __genStore(combo, disks, active):
            model = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
            combo.set_model(model)
            cell = gtk.CellRendererText()
            combo.pack_start(cell, True)
            combo.set_attributes(cell, text = 0)

            for disk in disks:
                i = model.append(None)
                model[i] = ("%s %8.0f MB %s" %(disk.name, disk.size,
                                               disk.description),
                            "%s" %(disk.name,))
                if disk.name == active:
                    combo.set_active_iter(i)

            return model

        (dxml, dialog) = gui.getGladeWidget("blwhere.glade",
                                            "blwhereDialog")
        gui.addFrame(dialog)
        dialog.set_transient_for(self.parent)
        dialog.show()

        choices = anaconda.platform.bootloaderChoices(self.bl)
        for t in ("mbr", "boot"):
            if not choices.has_key(t):
                continue
            (device, desc) = choices[t]
            w = dxml.get_widget("%sRadio" %(t,))
            w.set_label("%s - /dev/%s" %(_(desc), device))
            w.show()
            if self.bldev == device:
                w.set_active(True)
            else:
                w.set_active(False)
            w.set_data("bootDevice", device)

        for i in range(1, 5):
            if len(self.driveorder) < i:
                break
            combo = dxml.get_widget("bd%dCombo" %(i,))
            lbl = dxml.get_widget("bd%dLabel" %(i,))
            combo.show()
            lbl.show()
            partitioned = anaconda.storage.partitioned
            disks = anaconda.storage.disks
            bl_disks = [d for d in disks if d in partitioned]
            m = __genStore(combo, bl_disks, self.driveorder[i - 1])

        dxml.get_widget("bd1Combo").connect("changed", __driveChange, dxml, choices)
        __driveChange(dxml.get_widget("bd1Combo"), dxml, choices)

        while 1:
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

                act = combo.get_model()[iter][1]
                if act not in neworder:
                    neworder.append(act)
            for d in self.driveorder:
                if d not in neworder:
                    neworder.append(d)
            self.driveorder = neworder

            break

        dialog.destroy()
        self.grubCB.set_label(_("_Install boot loader on /dev/%s.") %
                              (self.bldev,))
        return rc

    def _setBLCBText(self):
        self.grubCB.set_label(_("_Install boot loader on /dev/%s.") %
                              (self.bldev,))


    def getScreen(self, anaconda):
        self.dispatch = anaconda.dispatch
        self.bl = anaconda.bootloader
        self.intf = anaconda.intf

        self.driveorder = self.bl.drivelist
        if len(self.driveorder) == 0:
            partitioned = anaconda.storage.partitioned
            disks = anaconda.storage.disks
            self.driveorder = [d.name for d in disks if d in partitioned]

        if self.bl.getPassword():
            self.usePass = 1
            self.password = self.bl.getPassword()
        else:
            self.usePass = 0
            self.password = None

        thebox = gtk.VBox (False, 12)
        thebox.set_border_width(18)

        # make sure we get a valid device to say we're installing to
        if self.bl.getDevice() is not None:
            self.bldev = self.bl.getDevice()
        else:
            # we don't know what it is yet... if mbr is possible, we want
            # it, else we want the boot dev
            choices = anaconda.platform.bootloaderChoices(self.bl)
            if choices.has_key('mbr'):
                self.bldev = choices['mbr'][0]
            else:
                self.bldev = choices['boot'][0]

        hb = gtk.HBox(False, 12)
        self.grubCB = gtk.CheckButton(_("_Install boot loader on /dev/%s.") %
                                      (self.bldev,))
        self.grubCB.set_active(not self.dispatch.stepInSkipList("instbootloader"))
        self.grubCB.connect("toggled", self.bootloaderChanged)
        hb.pack_start(self.grubCB, False)

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
