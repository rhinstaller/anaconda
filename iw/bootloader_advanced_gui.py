#
# bootloader_advanced.py: gui advanced bootloader configuration dialog
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

from bootlocwidget import BootloaderLocationWidget

class AdvancedBootloaderWindow(InstallWindow):
    windowTitle = N_("Advanced Boot Loader Configuration")
    htmlTag = "advbootloader"

    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        self.parent = ics.getICW().window


    def getPrev(self):
        pass


    def getNext(self):
        # forcing lba32 can be a bad idea.. make sure they really want to
        if (self.forceLBA.get_active() and not self.bl.forceLBA32 and
            not self.none_radio.get_active()):
            rc = self.intf.messageWindow(_("Warning"),
                    _("Forcing the use of LBA32 for your bootloader when "
                      "not supported by the BIOS can cause your machine "
                      "to be unable to boot.  We highly recommend you "
                      "create a boot disk when asked later in the "
                      "install process.\n\n"
                      "Would you like to continue and force LBA32 mode?"),
                                         type = "custom",
                                         custom_buttons = [_("Cancel"),
                                                           _("Force LBA32")])
            if rc != 1:
                raise gui.StayOnScreen

        # set the bootloader type
        if self.none_radio.get_active():
            self.dispatch.skipStep("instbootloader")
            return
        else:
            self.bl.setUseGrub(self.grub_radio.get_active())
            self.dispatch.skipStep("instbootloader", skip = 0)

        # set forcelba
        self.bl.setForceLBA(self.forceLBA.get_active())
        # set kernel args
        self.bl.args.set(self.appendEntry.get_text())

        # set the boot device
        self.bl.setDevice(self.blloc.getBootDevice())

        # set the drive order
        self.bl.drivelist = self.blloc.getDriveOrder()


    # enable the options if we're installing a boot loader
    def bootloaderChanged(self, widget, *args):
        if widget == self.grub_radio and self.grub_radio.get_active():
            # grub is the boot loader
            self.blloc.getWidget().set_sensitive(gtk.TRUE)
            self.blloc.setUsingGrub(1)
            self.options_vbox.set_sensitive(gtk.TRUE)
        elif widget == self.lilo_radio and self.lilo_radio.get_active():
            # lilo is the boot loader
            self.blloc.getWidget().set_sensitive(gtk.TRUE)
            self.blloc.setUsingGrub(0)            
            self.options_vbox.set_sensitive(gtk.TRUE)
        elif widget == self.none_radio and self.none_radio.get_active():
            # using no boot loader
            self.blloc.getWidget().set_sensitive(gtk.FALSE)
            self.options_vbox.set_sensitive(gtk.FALSE)
            

    # set up the vbox with force lba32 and kernel append
    def setupOptionsVbox(self):
        self.options_vbox = gtk.VBox(gtk.FALSE, 5)
        self.options_vbox.set_border_width(5)
        
        self.forceLBA = gtk.CheckButton(_("_Force LBA32 (Not normally required)"))
        self.options_vbox.pack_start(self.forceLBA, gtk.FALSE)
        self.forceLBA.set_active(self.bl.forceLBA32)

        label = gtk.Label(_("General kernel parameters"))
        self.appendEntry = gtk.Entry()
        args = self.bl.args.get()
        if args:
            self.appendEntry.set_text(args)
        box = gtk.HBox(gtk.FALSE, 5)
        box.pack_start(label)
        box.pack_start(self.appendEntry)
        self.options_vbox.pack_start(box, gtk.FALSE)


    # set up the vbox with the choose your bootloader bits
    def setupChooseBootloaderRadioBox(self):
        self.radio_vbox = gtk.VBox(gtk.FALSE, 2)
        self.radio_vbox.set_border_width(5)

        label = gui.WrappingLabel(_("Please select the boot loader that "
                                    "the computer will use.  GRUB is the "
                                    "default boot loader. However, if you "
                                    "do not wish to overwrite your current "
                                    "boot loader, select \"Do not install "
                                    "a boot loader.\"  "))
        label.set_alignment(0.0, 0.0)
                           
        self.grub_radio = gtk.RadioButton(None, (_("Use _GRUB as the "
                                                   "boot loader")))
        self.lilo_radio = gtk.RadioButton(self.grub_radio,
                                          (_("Use _LILO as the boot loader")))
        self.none_radio = gtk.RadioButton(self.grub_radio, (_("_Do not "
                                                              "install a "
                                                              "boot loader")))


        self.radio_vbox.pack_start(label, gtk.FALSE)
        self.radio_vbox.pack_start(self.grub_radio, gtk.FALSE)
        self.radio_vbox.pack_start(self.lilo_radio, gtk.FALSE)
        self.radio_vbox.pack_start(self.none_radio, gtk.FALSE)

        # XXX this is kind of ugly
        if self.dispatch.stepInSkipList("instbootloader"):
            self.none_radio.set_active(gtk.TRUE)
        elif not self.bl.useGrub():
            self.lilo_radio.set_active(gtk.TRUE)
        else:
            self.grub_radio.set_active(gtk.TRUE)

        self.grub_radio.connect("toggled", self.bootloaderChanged)
        self.lilo_radio.connect("toggled", self.bootloaderChanged)
        self.none_radio.connect("toggled", self.bootloaderChanged)


    def getScreen(self, dispatch, bl, fsset, diskset):
        self.dispatch = dispatch
        self.bl = bl
        self.intf = dispatch.intf

        thebox = gtk.VBox (gtk.FALSE, 10)

        # choose your boot loader type 
        self.setupChooseBootloaderRadioBox()
        thebox.pack_start(self.radio_vbox, gtk.FALSE)

        thebox.pack_start (gtk.HSeparator(), gtk.FALSE)

        # boot loader location bits (mbr vs boot, drive order)
        self.blloc = BootloaderLocationWidget(bl, fsset, diskset,
                                              self.parent, self.intf)
        thebox.pack_start(self.blloc.getWidget())

        thebox.pack_start (gtk.HSeparator(), gtk.FALSE)

        # some optional things
        self.setupOptionsVbox()
        thebox.pack_start(self.options_vbox, gtk.FALSE)


        # go ahead and set default sensitivities
        if self.none_radio.get_active():
            self.options_vbox.set_sensitive(gtk.FALSE)
            self.blloc.getWidget().set_sensitive(gtk.FALSE)
        

        return thebox
