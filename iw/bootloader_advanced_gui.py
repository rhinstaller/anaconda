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

    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        self.parent = ics.getICW().window


    def getPrev(self):
        pass


    def getNext(self):
        # forcing lba32 can be a bad idea.. make sure they really want to
        if (self.forceLBA.get_active() and not self.bl.forceLBA32):
            rc = self.intf.messageWindow(_("Warning"),
                    _("Forcing the use of LBA32 for your bootloader when "
                      "not supported by the BIOS can cause your machine "
                      "to be unable to boot.\n\n"
                      "Would you like to continue and force LBA32 mode?"),
                                         type = "custom",
                                         custom_buttons = [_("Cancel"),
                                                           _("Force LBA32")])
            if rc != 1:
                raise gui.StayOnScreen

        # set forcelba
        self.bl.setForceLBA(self.forceLBA.get_active())
        # set kernel args
        self.bl.args.set(self.appendEntry.get_text())

        # set the boot device
        self.bl.setDevice(self.blloc.getBootDevice())

        # set the drive order
        self.bl.drivelist = self.blloc.getDriveOrder()


    # set up the vbox with force lba32 and kernel append
    def setupOptionsVbox(self):
        self.options_vbox = gtk.VBox(False, 5)
        self.options_vbox.set_border_width(5)
        
        self.forceLBA = gtk.CheckButton(_("_Force LBA32 (not normally required)"))
        self.options_vbox.pack_start(self.forceLBA, False)
        self.forceLBA.set_active(self.bl.forceLBA32)

        label = gui.WrappingLabel(_("If you wish to add default options to the "
			    "boot command, enter them into "
			    "the 'General kernel parameters' field."))
	label.set_alignment(0.0, 0.0)
        self.options_vbox.pack_start(label, False)

        label = gui.MnemonicLabel(_("_General kernel parameters"))
        self.appendEntry = gtk.Entry()
        label.set_mnemonic_widget(self.appendEntry)
        args = self.bl.args.get()
        if args:
            self.appendEntry.set_text(args)
        box = gtk.HBox(False, 0)
        box.pack_start(label)
        box.pack_start(self.appendEntry)
	al = gtk.Alignment(0.0, 0.0)
	al.add(box)
        self.options_vbox.pack_start(al, False)


    def getScreen(self, anaconda):
        self.dispatch = anaconda.dispatch
        self.bl = anaconda.id.bootloader
        self.intf = anaconda.intf

        thebox = gtk.VBox (False, 10)

        # boot loader location bits (mbr vs boot, drive order)
        self.blloc = BootloaderLocationWidget(anaconda, self.parent)
        thebox.pack_start(self.blloc.getWidget(), False)

        thebox.pack_start (gtk.HSeparator(), False)

        # some optional things
        self.setupOptionsVbox()
        thebox.pack_start(self.options_vbox, False)


        return thebox
