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
from iw_gui import *
from rhpl.translate import _, N_

from osbootwidget import OSBootWidget
from blpasswidget import BootloaderPasswordWidget


class MainBootloaderWindow(InstallWindow):
    windowTitle = N_("Boot Loader Configuration")
    htmlTag = "bootloader"

    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        self.parent = ics.getICW().window


    def getPrev(self):
        pass


    def getNext(self):
        # go ahead and set the device even if we already knew it
        # since that won't change anything
        self.bl.setDevice(self.bldev)

        # set the password
        self.bl.setPassword(self.blpass.getPassword(), isCrypted = 0)

        # set the bootloader images based on what's in our list
        self.oslist.setBootloaderImages()

        if self.advanced.get_active():
            self.dispatch.skipStep("bootloaderadvanced", skip = 0)
        else:
            self.dispatch.skipStep("bootloaderadvanced", skip = 1)
            # avoid screwing ourselves -- if we're skipping the advanced
            # screen, always make sure to install the boot loader
            self.dispatch.skipStep("instbootloader", skip = 0)

    def getScreen(self, dispatch, bl, fsset, diskSet):
        self.dispatch = dispatch
        self.bl = bl
        self.intf = dispatch.intf

        if self.bl.getPassword():
            self.usePass = 1
            self.password = self.bl.getPassword()
        else:
            self.usePass = 0
            self.password = None

        thebox = gtk.VBox (gtk.FALSE, 10)
        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        thebox.pack_start(spacer, gtk.FALSE)

        if self.bl.useGrub():
            blname = "GRUB"
        else:
            blname = "LILO"

        # make sure we get a valid device to say we're installing to
        if bl.getDevice() is not None:
            self.bldev = bl.getDevice()
        else:
            # we don't know what it is yet... if mbr is possible, we want
            # it, else we want the boot dev
            choices = fsset.bootloaderChoices(diskSet, self.bl)
            if choices.has_key('mbr'):
                self.bldev = choices['mbr'][0]
            else:
                self.bldev = choices['boot'][0]

        label = gui.WrappingLabel(_("The %s boot loader will be installed "
                                    "on /dev/%s.") % (blname, self.bldev))
        label.set_alignment(0.0, 0.5)
        thebox.pack_start(label, gtk.FALSE)

        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        thebox.pack_start(spacer, gtk.FALSE)

        # configure the systems available to boot from the boot loader
        self.oslist = OSBootWidget(bl, fsset, diskSet, self.parent, self.intf)
        thebox.pack_start(self.oslist.getWidget(), gtk.FALSE)

        thebox.pack_start (gtk.HSeparator(), gtk.FALSE)

        # control whether or not there's a boot loader password and what it is
        self.blpass = BootloaderPasswordWidget(bl, self.parent, self.intf)
        thebox.pack_start(self.blpass.getWidget())

        thebox.pack_start (gtk.HSeparator(), gtk.FALSE)

        # check box to control showing the advanced screen
        self.advanced = gtk.CheckButton(_("Configure advanced boot loader options"))
        if dispatch.stepInSkipList("bootloaderadvanced"):
            self.advanced.set_active(gtk.FALSE)
        else:
            self.advanced.set_active(gtk.TRUE)
            
        thebox.pack_start(self.advanced, gtk.FALSE)

        return thebox
        

