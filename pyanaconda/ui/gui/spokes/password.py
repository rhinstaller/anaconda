# root password spoke class
#
# Copyright (C) 2012 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Jesse Keating <jkeating@redhat.com>
#

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x

from gi.repository import Gtk

from pyanaconda.users import cryptPassword, validatePassword
from pwquality import PWQError
import string

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.user_settings import UserSettingsCategory
#from _isys import isCapsLockEnabled

__all__ = ["PasswordSpoke"]


class PasswordSpoke(NormalSpoke):
    builderObjects = ["passwordWindow"]

    mainWidgetName = "passwordWindow"
    uiFile = "spokes/password.glade"

    category = UserSettingsCategory

    icon = "dialog-password-symbolic"
    title = N_("ROOT PASSWORD")

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        self._password = None
        self._error = False
        self._oldweak = None

    def initialize(self):
        NormalSpoke.initialize(self)
        # place holders for the text boxes
        self.pw = self.builder.get_object("pw")
        self.confirm = self.builder.get_object("confirm")

    def refresh(self):
#        self.setCapsLockLabel()
        self.pw.grab_focus()

# Caps lock detection isn't hooked up right now
#    def setCapsLockLabel(self):
#        if isCapsLockEnabled():
#            self.capslock.set_text("<b>" + _("Caps Lock is on.") + "</b>")
#            self.capslock.set_use_markup(True)
#        else:
#            self.capslock..set_text("")

    @property
    def status(self):
        if self._error:
            return _("Error setting root password")
        if self.data.rootpw.password:
            return _("Root password is set")
        elif self.data.rootpw.lock:
            return _("Root account is disabled")
        else:
            return _("Root password is not set")

    def apply(self):
        self.data.rootpw.password = cryptPassword(self._password)
        self.data.rootpw.isCrypted = True
        self.data.rootpw.lock = False

    @property
    def completed(self):
        return bool(self.data.rootpw.password or self.data.rootpw.lock)

    def _validatePassword(self):
        # Do various steps to validate the password
        # sets self._error to an error string
        # Return True if valid, False otherwise
        self._error = False
        pw = self.pw.get_text()
        confirm = self.confirm.get_text()

        if not pw and not confirm:
            self._error = _("You must provide and confirm a password.")
            return False

        try:
            self._error = validatePassword(pw, confirm)
        except PWQError as (e, msg):
            if pw == self._oldweak:
                # We got a second attempt with the same weak password
                pass
            else:
                self._error = _("You have provided a weak password: %s. "
                                " Press Done again to use anyway.") % msg
                self._oldweak = pw
                return False

        if self._error:
            return False

        # if no errors, clear the info for next time we go into the spoke
        self._password = pw
        self.clear_info()
        self._error = False
        return True

    def on_back_clicked(self, button):
        if self._validatePassword():
            self.clear_info()
            NormalSpoke.on_back_clicked(self, button)
        else:
            self.clear_info()
            self.set_warning(self._error)
            self.pw.grab_focus()
            self.window.show_all()
