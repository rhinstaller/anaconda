#
# bootdisk_gui.py: gui bootdisk creation dialog
#
# Copyright 2001 Red Hat, Inc.
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
from gtk import *
from translate import _, N_
from constants import *

class BootdiskWindow (InstallWindow):

    htmlTag = "bootdisk"
    windowTitle =  N_("Boot Disk Creation")

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setPrevEnabled (FALSE)

    def getNext (self):
        if iutil.getArch() == "alpha" or iutil.getArch() == "ia64":
            return None
        
        if self.skipBootdisk.get_active ():
	    self.dispatch.skipStep("makebootdisk")
	else:
	    self.dispatch.skipStep("makebootdisk", skip = 0)

        return None

    # BootdiskWindow tag="bootdisk"
    def getScreen (self, dir, disp, fsset):
	self.dispatch = disp

        box = GtkVBox (FALSE, 5)
        pix = self.ics.readPixmap ("gnome-floppy.png")
        if pix:
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.0, 0.0, 0.0, 0.0)
            box.pack_start (a, FALSE)
        
        label = None

        if dir == DISPATCH_FORWARD:
            text = _("The boot disk allows you to boot your Red Hat "
                     "Linux system from a floppy diskette.\n\n"
                     "Please remove any diskettes from the floppy drive and "
                     "insert a blank diskette. All data will be ERASED "
                     "during creation of the boot disk.")
            if fsset.rootOnLoop():
                text = text + _("\n\nA boot disk is REQUIRED to boot a "
                                "partitionless install.")
        else:
            text = _("An error occured while making the boot disk. "
                     "Please make sure that there is a formatted floppy "
                     "in the first floppy drive.")
        label = GtkLabel (text)

        label.set_line_wrap (TRUE)
        box.pack_start (label, FALSE)
        
        self.skipBootdisk = GtkCheckButton (_("Skip boot disk creation"))
        self.skipBootdisk.set_active (FALSE)
        box.pack_start (GtkHSeparator (), FALSE, padding=3)
        box.pack_start (self.skipBootdisk, FALSE)

	if fsset.rootOnLoop():
	    self.skipBootdisk.set_sensitive(FALSE)

        return box
