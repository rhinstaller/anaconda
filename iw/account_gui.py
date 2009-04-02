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

    def getNext (self):
        def passwordError():
            self.pw.set_text("")
            self.confirm.set_text("")
            self.pw.grab_focus()            
            raise gui.StayOnScreen
            
	if not self.__dict__.has_key("pw"): return None

        # check if we already have a crypted password from kickstart
        if self.rootPassword["isCrypted"]: return None

        pw = self.pw.get_text()
        confirm = self.confirm.get_text()

        if not pw or not confirm:
            self.intf.messageWindow(_("Error with Password"),
                                    _("You must enter your root password "
                                      "and confirm it by typing it a second "
                                      "time to continue."),
                                    custom_icon="error")
            passwordError()

        if pw != confirm:
            self.intf.messageWindow(_("Error with Password"),
                                    _("The passwords you entered were "
                                      "different.  Please try again."),
                                    custom_icon="error")
            passwordError()

        if len(pw) < 6:
            self.intf.messageWindow(_("Error with Password"),
                                    _("The root password must be at least "
                                      "six characters long."),
                                    custom_icon="error")
            passwordError()
        
        allowed = string.digits + string.ascii_letters + string.punctuation + " "
        for letter in pw:
            if letter not in allowed:
                self.intf.messageWindow(_("Error with Password"),
                                        _("Requested password contains "
                                          "non-ascii characters which are "
                                          "not allowed for use in password."),
                                        custom_icon="error")
                passwordError()

        self.rootPassword["password"] = self.pw.get_text()
        self.rootPassword["isCrypted"] = False
        return None

    def setFocus (self, area, data):
        self.pw.grab_focus ()

    # AccountWindow tag="accts"
    def getScreen (self, anaconda):
	self.rootPassword = anaconda.id.rootPassword
        self.intf = anaconda.intf

	self.passwords = {}

        box = gtk.VBox ()
        box.set_border_width(5)

        hbox = gtk.HBox()
        pix = gui.readImageFromFile ("root-password.png")
        if pix:
            hbox.pack_start (pix, False)

        label = gui.WrappingLabel (_("The root account is used for "
                                     "administering the system.  Enter "
                                     "a password for the root user."))
        label.set_line_wrap(True)
        label.set_size_request(350, -1)
        label.set_alignment(0.0, 0.5)
        hbox.pack_start(label, False)

        box.pack_start(hbox, False)
       
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
        self.pw.connect ("map-event", self.setFocus)
        self.pw.set_visibility (False)
        self.confirm = gtk.Entry (128)
        pass2.set_mnemonic_widget(self.confirm)
        self.confirm.connect ("activate", self.forward)
        self.confirm.set_visibility (False)
        table.attach (self.pw,      1, 2, 0, 1, gtk.FILL|gtk.EXPAND, 5)
        table.attach (self.confirm, 1, 2, 1, 2, gtk.FILL|gtk.EXPAND, 5)

        hbox = gtk.HBox()
        hbox.pack_start(table, False)
        box.pack_start (hbox, False)

        # root password statusbar
        self.rootStatus = gtk.Label ("")
        wrapper = gtk.HBox(0, False)
        wrapper.pack_start (self.rootStatus)
        box.pack_start (wrapper, False)

        if not self.rootPassword["isCrypted"]:
	    self.pw.set_text(self.rootPassword["password"])
	    self.confirm.set_text(self.rootPassword["password"])
        else:
            self.pw.set_text("xxxxxxxx")
            self.confirm.set_text("xxxxxxxx")

        return box
