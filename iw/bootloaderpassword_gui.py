#
# bootloaderpassword_gui.py: gui bootloader password setup dialog
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

from iw_gui import *

from gtk import *
from gnome.ui import *
from translate import _, N_
import GdkImlib
import gui

class BootloaderPasswordWindow (InstallWindow):

    windowTitle = N_("Boot Loader Password Configuration")
    htmlTag = "grubpasswd"
    
    def getNext (self):
        if self.usegrubpasscb.get_active():
            self.bl.setPassword(self.pw.get_text(), isCrypted = 0)
        else:
            self.bl.setPassword(None)

    def toggle (self, *args):
        self.passtable.set_sensitive(self.usegrubpasscb.get_active())
        self.ics.setNextEnabled(not self.usegrubpasscb.get_active())

    def rootPasswordsMatch (self, *args):
        pw = self.pw.get_text ()
        confirm = self.confirm.get_text ()

        if pw == confirm and len (pw) >= 6:
            self.ics.setNextEnabled (TRUE)
            self.rootStatus.set_text (_("Password accepted."))
        else:
	    if not pw and not confirm:
                self.rootStatus.set_text ("")
            elif len (pw) < 6:
                self.rootStatus.set_text (_("Password is too short."))
            else:
                self.rootStatus.set_text (_("Passwords do not match.asdfasdfdsafasdfdf"))
                
            self.ics.setNextEnabled (FALSE)
        
    def getScreen(self, bl, intf):
        self.bl = bl

        box = GtkVBox(FALSE, 5)
        box.set_border_width (5)

        self.forward = lambda widget, box=box: box.focus (DIR_TAB_FORWARD)

        self.passtable = GtkTable (2, 2)
        self.passtable.set_row_spacings (5)
	self.passtable.set_col_spacings (5)
        grubpassinfo = GtkLabel(_("A GRUB password prevents users from passing arbitrary options to the kernel.  For highest security, we recommend setting a password, but this is not necessary for more casual users."))
        self.password = None
        grubpassinfo.set_line_wrap(TRUE)
        grubpassinfo.set_usize(400, -1)
        grubpassinfo.set_alignment(0.0,0.0)
        box.pack_start(grubpassinfo, FALSE)

        self.usegrubpasscb = GtkCheckButton(_("Use a GRUB Password?"))
        box.pack_start(self.usegrubpasscb, FALSE)

        self.passtable.attach(GtkLabel(_("Password:")), 0, 1, 2, 3, FILL, 0, 10)
        self.pw = GtkEntry (16)
        self.pw.set_visibility (FALSE)
        self.passtable.attach(self.pw, 1, 2, 2, 3, FILL, 0, 10)
        self.passtable.attach(GtkLabel(_("Confirm:")), 0, 1, 3, 4, FILL, 0, 10) 
        self.confirm = GtkEntry (16)
        self.confirm.set_visibility (FALSE)
        self.passtable.attach(self.confirm, 1, 2, 3, 4, FILL, 0, 10)
        
        if self.bl.getPassword():
            passwd = self.bl.getPassword()
            self.pw.set_text(passwd)
            self.confirm.set_text(passwd)
            self.usegrubpasscb.set_active(TRUE)

        self.pw.connect ("changed", self.rootPasswordsMatch)
        self.pw.connect ("activate", self.forward)
        self.confirm.connect ("changed", self.rootPasswordsMatch)
        self.confirm.connect ("activate", self.forward)
        self.passtable.set_sensitive(self.usegrubpasscb.get_active())
        self.usegrubpasscb.connect("toggled", self.toggle)

        self.rootStatus = GtkLabel(_("Please enter password"))
        a = GtkAlignment (0.2, 0.5)
        a.add(self.rootStatus)
        box.pack_start(self.passtable, FALSE)
        box.pack_start(a, FALSE)


        return box

