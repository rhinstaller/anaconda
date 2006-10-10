#
# bootloader_main_gui.py: gui bootloader configuration dialog
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
import gobject
import iutil
import partedUtils
import gui
import bootloader
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

        if self.none_radio.get_active():
            # if we're not installing a boot loader, don't show the second
            # screen and don't worry about other options
            self.dispatch.skipStep("instbootloader", skip = 1)
            self.dispatch.skipStep("bootloaderadvanced", skip = 1)

            # kind of a hack...
            self.bl.defaultDevice = None
            return
        else:
            self.dispatch.skipStep("instbootloader", skip = 0)
            if self.blname == "GRUB":
                self.bl.setUseGrub(1)
            else:
                self.bl.setUseGrub(0)

        # set the password
        self.bl.setPassword(self.blpass.getPassword(), isCrypted = 0)

        # set the bootloader images based on what's in our list
        self.oslist.setBootloaderImages()

        if self.advanced.get_active():
            self.dispatch.skipStep("bootloaderadvanced", skip = 0)
        else:
            self.dispatch.skipStep("bootloaderadvanced", skip = 1)

    def bootloaderChanged(self, *args):
        active = self.grub_radio.get_active()

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

        if self.bl.useGrub():
            self.blname = "GRUB"
        else:
            self.blname = None

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

        vb = gtk.VBox(False, 6)
        self.grub_radio = gtk.RadioButton(None, _("The %s boot loader will be "
                                                  "installed on /dev/%s.") %
                                          ("GRUB", self.bldev))
        self.grub_radio.set_use_underline(False)
        vb.pack_start(self.grub_radio)
        self.none_radio = gtk.RadioButton(self.grub_radio,
                                      _("No boot loader will be installed."))
        vb.pack_start(self.none_radio)
        if self.blname is None:
            self.none_radio.set_active(True)
            self.grub_radio.set_active(False)
        else:
            self.grub_radio.set_active(True)
            self.none_radio.set_active(False)            
        self.grub_radio.connect("toggled", self.bootloaderChanged)
        self.none_radio.connect("toggled", self.bootloaderChanged)
        thebox.pack_start(vb, False)

        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        thebox.pack_start(spacer, False)

        # configure the systems available to boot from the boot loader
        self.oslist = OSBootWidget(anaconda, self.parent, self.blname)
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
