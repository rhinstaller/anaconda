#
# bootdisk_gui.py: gui bootdisk creation dialog
#
# Copyright 2000-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil
from iw_gui import *
import gtk
from rhpl.translate import _, N_
from constants import *

class BootdiskWindow (InstallWindow):

    htmlTag = "bootdisk"
    windowTitle =  N_("Boot Diskette Creation")

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setPrevEnabled (gtk.FALSE)

    def getNext (self):
        if iutil.getArch() == "alpha" or iutil.getArch() == "ia64":
            return None
        
        if self.skipDisk.get_active ():
	    self.dispatch.skipStep("makebootdisk")
	else:
	    self.dispatch.skipStep("makebootdisk", skip = 0)

        return None

    # BootdiskWindow tag="bootdisk"
    def getScreen (self, dir, disp, fsset):
	self.dispatch = disp

        box = gtk.VBox (gtk.FALSE, 5)
        pix = self.ics.readPixmap ("gnome-floppy.png")
        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            a.set (0.0, 0.0, 0.0, 0.0)
            box.pack_start (a, gtk.FALSE)
        
        label = None

        text = _("The boot diskette allows you to boot your %s "
                 "system from a floppy diskette.  A boot diskette "
		 "allows you to boot your system in the event your "
		 "bootloader configuration stops working, if you "
		 "chose not to install a boot loader, or if your "
		 "third-party boot loader does not support Linux.\n\nIt is "
		 "highly recommended you create a boot diskette.\n") % (productName,)

        label = gtk.Label (text)

        label.set_line_wrap (gtk.TRUE)
        box.pack_start (label, gtk.FALSE)

        radioBox = gtk.VBox (gtk.FALSE)

        self.createDisk = gtk.RadioButton(
            None, _("_Yes, I would like to create a boot diskette"))
	radioBox.pack_start(self.createDisk, gtk.FALSE, gtk.FALSE, padding=10)
        self.skipDisk = gtk.RadioButton(
            self.createDisk, _("No, I _do not want to create a boot diskette"))
	radioBox.pack_start(self.skipDisk, gtk.FALSE, gtk.FALSE)

	self.createDisk.set_active(1)

	align = gtk.Alignment(0.5, 0.0)
	align.add(radioBox)
	box.pack_start(align)

        return box
