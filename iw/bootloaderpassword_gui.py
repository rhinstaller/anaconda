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

import gtk
import gui
from translate import _, N_
from iw_gui import *

class BootloaderPasswordWindow (InstallWindow):

    windowTitle = N_("Boot Loader Password Configuration")
    htmlTag = "grubpasswd"
    
    def getNext (self):
        if self.usegrubpasscb.get_active() and len(self.pw.get_text()) < 6:
            rc = self.intf.messageWindow(_("Warning"),
                                    _("Your boot loader password is less than "
                                      "six characters.  We recommend a longer "
                                      "boot loader password."
                                      "\n\n"
                                      "Would you like to continue with this "
                                      "password?"),
                                    type = "yesno")
            if rc == 0:
                raise gui.StayOnScreen
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

        if pw == confirm and len(pw) >= 1:
            self.ics.setNextEnabled (gtk.TRUE)
            self.rootStatus.set_text (_("Password accepted."))
        else:
            if not pw and not confirm:
                self.rootStatus.set_text ("")
            elif len(pw) < 1:
                self.rootStatus.set_text(_("Password is too short."))
            else:
                self.rootStatus.set_text (_("Passwords do not match."))
                
            self.ics.setNextEnabled (gtk.FALSE)
        
    def getScreen(self, bl, intf):
        self.bl = bl
        self.intf = intf

        box = gtk.VBox(gtk.FALSE, 5)
        box.set_border_width (5)

        self.forward = lambda widget, box=box: box.focus (DIR_TAB_FORWARD)

        self.passtable = gtk.Table (2, 2)
        self.passtable.set_row_spacings (5)
	self.passtable.set_col_spacings (5)
        grubpassinfo =  gui.WrappingLabel(
            _("A boot loader password prevents users from "
              "passing arbitrary options to the kernel.  For "
              "highest security, we recommend setting a "
              "password, but this is not necessary for more "
              "casual users."))
        self.password = None
        grubpassinfo.set_alignment(0.0,0.0)
        box.pack_start(grubpassinfo, gtk.FALSE)

        self.usegrubpasscb = gtk.CheckButton(_("Use a GRUB Password?"))
        box.pack_start(self.usegrubpasscb, gtk.FALSE)

        self.passtable.attach(gtk.Label(_("Password:")), 0, 1, 2, 3, gtk.FILL, 0, 10)
        self.pw = gtk.Entry (16)
        self.pw.set_visibility (gtk.FALSE)
        self.passtable.attach(self.pw, 1, 2, 2, 3, gtk.FILL, 0, 10)
        self.passtable.attach(gtk.Label(_("Confirm:")), 0, 1, 3, 4, gtk.FILL, 0, 10) 
        self.confirm = gtk.Entry (16)
        self.confirm.set_visibility (gtk.FALSE)
        self.passtable.attach(self.confirm, 1, 2, 3, 4, gtk.FILL, 0, 10)
        
        if self.bl.getPassword():
            passwd = self.bl.getPassword()
            self.pw.set_text(passwd)
            self.confirm.set_text(passwd)
            self.usegrubpasscb.set_active(gtk.TRUE)

        self.pw.connect ("changed", self.rootPasswordsMatch)
        self.pw.connect ("activate", self.forward)
        self.confirm.connect ("changed", self.rootPasswordsMatch)
        self.confirm.connect ("activate", self.forward)
        self.passtable.set_sensitive(self.usegrubpasscb.get_active())
        self.usegrubpasscb.connect("toggled", self.toggle)

        self.rootStatus = gtk.Label(_("Please enter password"))
        a = gtk.Alignment (0.2, 0.5)
        a.add(self.rootStatus)
        box.pack_start(self.passtable, gtk.FALSE)
        box.pack_start(a, gtk.FALSE)


        return box

