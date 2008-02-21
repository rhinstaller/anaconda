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
import partedUtils
import gui
from iw_gui import *
from rhpl.translate import _, N_

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

        if not self.grubCB.get_active():
            # if we're not installing a boot loader, don't show the second
            # screen and don't worry about other options
            self.dispatch.skipStep("instbootloader", skip = 1)
            self.dispatch.skipStep("bootloaderadvanced", skip = 1)

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

        if self.advanced.get_active():
            self.dispatch.skipStep("bootloaderadvanced", skip = 0)
        else:
            self.dispatch.skipStep("bootloaderadvanced", skip = 1)

    def bootloaderChanged(self, *args):
        active = self.grubCB.get_active()

        for widget in [ self.oslist.getWidget(), self.blpass.getWidget(),
                        self.advanced ]:
            widget.set_sensitive(active)
            
        
    def getScreen(self, anaconda):
        self.dispatch = anaconda.dispatch
        self.bl = anaconda.id.bootloader
        self.intf = anaconda.intf

        if self.bl.getPassword():
            self.usePass = 1
            self.password = self.bl.getPassword()
        else:
            self.usePass = 0
            self.password = None

        thebox = gtk.VBox (False, 5)
        thebox.set_border_width(10)
        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        thebox.pack_start(spacer, False)

        # make sure we get a valid device to say we're installing to
        if self.bl.getDevice() is not None:
            self.bldev = self.bl.getDevice()
        else:
            # we don't know what it is yet... if mbr is possible, we want
            # it, else we want the boot dev
            choices = anaconda.id.fsset.bootloaderChoices(anaconda.id.diskset, self.bl)
            if choices.has_key('mbr'):
                self.bldev = choices['mbr'][0]
            else:
                self.bldev = choices['boot'][0]

        self.grubCB = gtk.CheckButton(_("_Install bootloader on /dev/%s.") %
                                      (self.bldev,))
        self.grubCB.set_active(not self.dispatch.stepInSkipList("instbootloader"))
        self.grubCB.connect("toggled", self.bootloaderChanged)
        thebox.pack_start(self.grubCB, False)

        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        thebox.pack_start(spacer, False)

        # configure the systems available to boot from the boot loader
        self.oslist = OSBootWidget(anaconda, self.parent)
        thebox.pack_start(self.oslist.getWidget(), False)

        thebox.pack_start (gtk.HSeparator(), False)

        # control whether or not there's a boot loader password and what it is
        self.blpass = BootloaderPasswordWidget(anaconda, self.parent)
        thebox.pack_start(self.blpass.getWidget(), False)

        thebox.pack_start (gtk.HSeparator(), False)

        # check box to control showing the advanced screen
        self.advanced = gtk.CheckButton(_("Configure advanced boot loader "
                                          "_options"))
        if self.dispatch.stepInSkipList("bootloaderadvanced"):
            self.advanced.set_active(False)
        else:
            self.advanced.set_active(True)
            
        thebox.pack_start(self.advanced, False)

        self.bootloaderChanged()
        return thebox
