#
# account_gui.py: gui root password and crypt algorithm dialog
#
# Copyright (C) 2000, 2001, 2002, 2003, 2004, 2005,  Red Hat Inc.
#               2006, 2007, 2008
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import gtk
import string
import gui
from iw_gui import *
from flags import flags
from constants import *
import cracklib
import _isys

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class AccountWindow (InstallWindow):
    def getScreen(self, anaconda):
        self.anaconda = anaconda
        self.intf = anaconda.intf

        (self.xml, self.align) = gui.getGladeWidget("account.glade",
                                                    "account_align")
        self.icon = self.xml.get_widget("icon")
        self.capslock = self.xml.get_widget("capslock")
        self.pwlabel = self.xml.get_widget("pwlabel")
        self.pw = self.xml.get_widget("pw")
        self.confirmlabel = self.xml.get_widget("confirmlabel")
        self.confirm = self.xml.get_widget("confirm")

        # load the icon
        gui.readImageFromFile("root-password.png", image=self.icon)

        # connect hotkeys
        self.pwlabel.set_text_with_mnemonic(_("Root _Password:"))
        self.pwlabel.set_mnemonic_widget(self.pw)
        self.confirmlabel.set_text_with_mnemonic(_("_Confirm:"))
        self.confirmlabel.set_mnemonic_widget(self.confirm)

        # watch for Caps Lock so we can warn the user
        self.intf.icw.window.connect("key-release-event",
            lambda w, e: self.handleCapsLockRelease(w, e, self.capslock))

        # we might have a root password already
        if not self.anaconda.users.rootPassword['isCrypted']:
            self.pw.set_text(self.anaconda.users.rootPassword['password'])
            self.confirm.set_text(self.anaconda.users.rootPassword['password'])

        # pressing Enter in confirm == clicking Next
        vbox = self.xml.get_widget("account_box")
        self.confirm.connect("activate", lambda widget,
                             vbox=vbox: self.ics.setGrabNext(1))

        # set initial caps lock label text
        self.setCapsLockLabel()

        return self.align

    def focus(self):
        self.pw.grab_focus()

    def passwordError(self):
        self.pw.set_text("")
        self.confirm.set_text("")
        self.pw.grab_focus()
        raise gui.StayOnScreen

    def handleCapsLockRelease(self, window, event, label):
        if event.keyval == gtk.keysyms.Caps_Lock and \
           event.state & gtk.gdk.LOCK_MASK:
            self.setCapsLockLabel()

    def setCapsLockLabel(self):
        if _isys.isCapsLockEnabled():
            self.capslock.set_text("<b>" + _("Caps Lock is on.") + "</b>")
            self.capslock.set_use_markup(True)
        else:
            self.capslock.set_text("")

    def getNext (self):
        pw = self.pw.get_text()
        confirm = self.confirm.get_text()

        if not pw or not confirm:
            self.intf.messageWindow(_("Error with Password"),
                                    _("You must enter your root password "
                                      "and confirm it by typing it a second "
                                      "time to continue."),
                                    custom_icon="error")
            self.passwordError()

        if pw != confirm:
            self.intf.messageWindow(_("Error with Password"),
                                    _("The passwords you entered were "
                                      "different.  Please try again."),
                                    custom_icon="error")
            self.passwordError()

        if len(pw) < 6:
            self.intf.messageWindow(_("Error with Password"),
                                    _("The root password must be at least "
                                      "six characters long."),
                                    custom_icon="error")
            self.passwordError()

        try:
            cracklib.FascistCheck(pw)
        except ValueError, e:
            msg = gettext.ldgettext("cracklib", e)
            ret = self.intf.messageWindow(_("Weak Password"),
                                          _("You have provided a weak password: %s") % msg,
                                          type="custom", custom_icon="error",
                                          custom_buttons=[_("Cancel"), _("Use Anyway")])
            if ret == 0:
                self.passwordError()

        legal = string.digits + string.ascii_letters + string.punctuation + " "
        for letter in pw:
            if letter not in legal:
                self.intf.messageWindow(_("Error with Password"),
                                        _("Requested password contains "
                                          "non-ASCII characters, which are "
                                          "not allowed."),
                                        custom_icon="error")
                self.passwordError()

        self.anaconda.users.rootPassword["password"] = self.pw.get_text()
        self.anaconda.users.rootPassword["isCrypted"] = False

        return None
