#
# account_gui.py: gui root password and user creation dialog
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

import gtk
import gobject
import re
import string
import gui
from iw_gui import *
from rhpl.translate import _, N_
from flags import flags

class AccountWindow (InstallWindow):

    windowTitle = N_("Set Root Password")
    htmlTag = ("accts")

    def getNext (self):
	if not self.__dict__.has_key("pw"): return None

        self.rootPw.set (self.pw.get_text ())
        return None

    def rootPasswordsMatch (self, *args):
        pw = self.pw.get_text ()
        confirm = self.confirm.get_text ()

        if pw == confirm and len (pw) >= 6:
            self.ics.setNextEnabled (gtk.TRUE)
            self.rootStatus.set_text (_("Root password accepted."))
        else:
	    if not pw and not confirm:
                self.rootStatus.set_text ("")
            elif len (pw) < 6:
                self.rootStatus.set_text (_("Root password is too short."))
            else:
                self.rootStatus.set_text (_("Root passwords do not match."))
                
            self.ics.setNextEnabled (gtk.FALSE)

    def setFocus (self, area, data):
        self.pw.grab_focus ()

    # AccountWindow tag="accts"
    def getScreen (self, rootPw):
	self.rootPw = rootPw

	self.passwords = {}

        box = gtk.VBox ()
        box.set_border_width(5)

        hbox = gtk.HBox()
        pix = self.ics.readPixmap ("root-password.png")
        if pix:
            hbox.pack_start (pix, gtk.FALSE)

        label = gtk.Label (_("Enter the root (administrator) password "
                             "for the system."))
        label.set_line_wrap(gtk.TRUE)
        label.set_size_request(350, -1)
        label.set_alignment(0.0, 0.5)
        hbox.pack_start(label, gtk.FALSE)

        box.pack_start(hbox, gtk.FALSE)
       
        self.forward = lambda widget, box=box: box.emit('focus', gtk.DIR_TAB_FORWARD)
        
        table = gtk.Table (2, 2)
        table.set_size_request(365, -1)
        table.set_row_spacings (5)
	table.set_col_spacings (5)

        pass1 = gui.MnemonicLabel (_("Root _Password: "))
        pass1.set_alignment (0.0, 0.5)
        table.attach (pass1, 0, 1, 0, 1, gtk.FILL, 0, 10)
        pass2 = gui.MnemonicLabel (_("_Confirm: "))
        pass2.set_alignment (0.0, 0.5)
        table.attach (pass2, 0, 1, 1, 2, gtk.FILL, 0, 10)
        self.pw = gtk.Entry (128)
        pass1.set_mnemonic_widget(self.pw)
        
        self.pw.connect ("activate", self.forward)
        self.pw.connect ("changed", self.rootPasswordsMatch)
        self.pw.connect ("map-event", self.setFocus)
        self.pw.set_visibility (gtk.FALSE)
        self.confirm = gtk.Entry (128)
        pass2.set_mnemonic_widget(self.confirm)
        self.confirm.connect ("activate", self.forward)
        self.confirm.set_visibility (gtk.FALSE)
        self.confirm.connect ("changed", self.rootPasswordsMatch)
        table.attach (self.pw,      1, 2, 0, 1, gtk.FILL|gtk.EXPAND, 5)
        table.attach (self.confirm, 1, 2, 1, 2, gtk.FILL|gtk.EXPAND, 5)

        hbox = gtk.HBox()
        hbox.pack_start(table, gtk.FALSE)
        box.pack_start (hbox, gtk.FALSE)

        # root password statusbar
        self.rootStatus = gtk.Label ("")
        self.rootPasswordsMatch ()
        wrapper = gtk.HBox(0, gtk.FALSE)
        wrapper.pack_start (self.rootStatus)
        box.pack_start (wrapper, gtk.FALSE)

 	pw = self.rootPw.getPure()
	if pw:
	    self.pw.set_text(pw)
	    self.confirm.set_text(pw)

        return box
