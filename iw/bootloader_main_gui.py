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

        if self.blname is None:
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

    def changeBootloaderCallback(self, *args):
        dialog = gtk.Dialog(_("Change Boot Loader"), self.parent)
        dialog.add_button('gtk-cancel', 2)
        dialog.add_button('gtk-ok', 1)
        dialog.set_position(gtk.WIN_POS_CENTER)
        gui.addFrame(dialog)
        radio_vbox = self.setupChooseBootloaderRadioBox()

        dialog.vbox.pack_start(radio_vbox)
        dialog.show_all()

        blname = self.blname
        while 1:
            rc = dialog.run()
            if rc == 2:
                break

            if self.none_radio.get_active() == gtk.TRUE:
                newrc = self.intf.messageWindow(_("Warning"),
                                                _("You have selected not to "
                                                  "install a boot loader on "
                                                  "your system.  You will "
                                                  "have to create a boot "
                                                  "disk to boot your system "
                                                  "with this option.\n\n"
                                                  "Would you like to "
                                                  "continue and not install "
                                                  "a boot loader?"),
                                                type = "custom",
                                                custom_buttons =
                                                [_("Cancel"),
                                                 _("C_ontinue with no boot "
                                                   "loader")])
                if newrc != 1:
                    continue
                blname = None
            elif ((self.lilo_radio is not None)
                  and (self.lilo_radio.get_active() == gtk.TRUE)):
                blname = "LILO"
            else:
                blname = "GRUB"
            break

        dialog.destroy()

        if rc !=2:
            self.blname = blname
        self.updateBootLoaderLabel()
        if blname is not None:
            self.oslist.changeBootLoader(blname)
        return rc
            

    def setupChooseBootloaderRadioBox(self):
        radio_vbox = gtk.VBox(gtk.FALSE, 2)
        radio_vbox.set_border_width(5)

        label = gui.WrappingLabel(_("Please select the boot loader that "
                                    "the computer will use.  GRUB is the "
                                    "default boot loader. However, if you "
                                    "do not wish to overwrite your current "
                                    "boot loader, select \"Do not install "
                                    "a boot loader.\"  "))
        label.set_alignment(0.0, 0.0)
                           
        self.grub_radio = gtk.RadioButton(None, (_("Use _GRUB as the "
                                                   "boot loader")))
        if bootloader.showLilo:
            self.lilo_radio = gtk.RadioButton(self.grub_radio,
                                              (_("Use _LILO as the boot "
                                                 "loader")))
        else:
            self.lilo_radio = None
        self.none_radio = gtk.RadioButton(self.grub_radio, (_("_Do not "
                                                              "install a "
                                                              "boot loader")))


        radio_vbox.pack_start(label, gtk.FALSE)
        radio_vbox.pack_start(self.grub_radio, gtk.FALSE)
        if self.lilo_radio:
            radio_vbox.pack_start(self.lilo_radio, gtk.FALSE)
        radio_vbox.pack_start(self.none_radio, gtk.FALSE)

        if self.blname is None:
            self.none_radio.set_active(gtk.TRUE)
        elif self.lilo_radio is not None and self.blname == "LILO" and iutil.getArch() == "i386":
            self.lilo_radio.set_active(gtk.TRUE)
        else:
            self.grub_radio.set_active(gtk.TRUE)

        return radio_vbox
        

    def updateBootLoaderLabel(self):
        if self.blname is not None:
            self.bllabel.set_text(_("The %s boot loader will be "
                                    "installed on /dev/%s.") %
                                  (self.blname, self.bldev))
            active = gtk.TRUE
        else:
            self.bllabel.set_text(_("No boot loader will be installed."))
            active = gtk.FALSE

        for widget in [ self.oslist.getWidget(), self.blpass.getWidget(),
                        self.advanced ]:
            widget.set_sensitive(active)
            
        
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
            self.blname = "GRUB"
        else:
            self.blname = "LILO"
        # XXX this is kind of ugly
        if self.dispatch.stepInSkipList("instbootloader"):
            self.blname = None

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

        self.bllabel = gui.WrappingLabel("")
        
        self.bllabel.set_alignment(0.0, 0.5)

        hbox = gtk.HBox(gtk.FALSE, 10)
        hbox.pack_start(self.bllabel, gtk.FALSE)

        button = gtk.Button(_("_Change boot loader"))
        hbox.pack_start(button, gtk.FALSE)
        button.connect("clicked", self.changeBootloaderCallback)

        alignment = gtk.Alignment()
        alignment.set(0.1, 0, 0, 0)
        alignment.add(hbox)
        
        thebox.pack_start(alignment, gtk.FALSE)

        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        thebox.pack_start(spacer, gtk.FALSE)

        # configure the systems available to boot from the boot loader
        self.oslist = OSBootWidget(bl, fsset, diskSet, self.parent,
                                   self.intf, self.blname)
        thebox.pack_start(self.oslist.getWidget(), gtk.FALSE)

        thebox.pack_start (gtk.HSeparator(), gtk.FALSE)

        # control whether or not there's a boot loader password and what it is
        self.blpass = BootloaderPasswordWidget(bl, self.parent, self.intf)
        thebox.pack_start(self.blpass.getWidget(), gtk.FALSE)

        thebox.pack_start (gtk.HSeparator(), gtk.FALSE)

        # check box to control showing the advanced screen
        self.advanced = gtk.CheckButton(_("Configure advanced boot loader "
                                          "_options"))
        if dispatch.stepInSkipList("bootloaderadvanced"):
            self.advanced.set_active(gtk.FALSE)
        else:
            self.advanced.set_active(gtk.TRUE)
            
        thebox.pack_start(self.advanced, gtk.FALSE)

        # finally, update the label and activate widgets appropriately
        self.updateBootLoaderLabel()

        return thebox
        

