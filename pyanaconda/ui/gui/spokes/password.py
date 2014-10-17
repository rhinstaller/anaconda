# root password spoke class
#
# Copyright (C) 2012-2014 Red Hat, Inc.
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
#                    Chris Lumens <clumens@redhat.com>
#

from pyanaconda.flags import flags
from pyanaconda.i18n import _, N_
from pyanaconda.users import cryptPassword, validatePassword, checkPassword
from pwquality import PWQError

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.user_settings import UserSettingsCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn

__all__ = ["PasswordSpoke"]


class PasswordSpoke(FirstbootSpokeMixIn, NormalSpoke):
    builderObjects = ["passwordWindow"]

    mainWidgetName = "passwordWindow"
    uiFile = "spokes/password.glade"
    helpFile = "PasswordSpoke.xml"

    category = UserSettingsCategory

    icon = "dialog-password-symbolic"
    title = N_("_ROOT PASSWORD")

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        self._password = None
        self._error = False
        self._oldweak = None
        self._kickstarted = False

    def initialize(self):
        NormalSpoke.initialize(self)
        # place holders for the text boxes
        self.pw = self.builder.get_object("pw")
        self.confirm = self.builder.get_object("confirmPW")

        self._kickstarted = self.data.rootpw.seen
        if self._kickstarted:
            self.pw.set_placeholder_text(_("The password is set."))
            self.confirm.set_placeholder_text(_("The password is set."))

        self.pw_bar = self.builder.get_object("password_bar")
        self.pw_label = self.builder.get_object("password_label")

    def refresh(self):
        self.pw.grab_focus()
        self._checkPassword()

    @property
    def status(self):
        if self._error:
            return _("Error setting root password")
        elif self.data.rootpw.password:
            return _("Root password is set")
        elif self.data.rootpw.lock:
            return _("Root account is disabled")
        else:
            return _("Root password is not set")

    @property
    def mandatory(self):
        return not any(user for user in self.data.user.userList
                            if "wheel" in user.groups)

    def apply(self):
        if self._password is None and self._kickstarted:
            return

        self.data.rootpw.password = cryptPassword(self._password)
        self.data.rootpw.isCrypted = True
        self.data.rootpw.lock = False

        # value from the kickstart changed
        self.data.rootpw.seen = False
        self._kickstarted = False

        self.pw.set_placeholder_text("")
        self.confirm.set_placeholder_text("")

    @property
    def completed(self):
        return bool(self.data.rootpw.password or self.data.rootpw.lock)

    @property
    def sensitive(self):
        return not (self.completed and flags.automatedInstall)

    def _checkPassword(self, editable = None, data = None):
        """This method updates the password indicators according
        to the passwords entered by the user. It is called by
        the changed Gtk event handler.
        """
        try:
            strength = checkPassword(self.pw.get_text())
            _pwq_error = None
        except PWQError as e:
            _pwq_error = e.message
            strength = 0

        if strength < 50:
            val = 1
            text = _("Weak")
            self._error = _("The password you have provided is weak")
            if _pwq_error:
                self._error += ": %s. " % _pwq_error
            else:
                self._error += ". "
            self._error += _("You will have to press Done twice to confirm it.")
        elif strength < 75:
            val = 2
            text = _("Fair")
            self._error = False
        elif strength < 90:
            val = 3
            text = _("Good")
            self._error = False
        else:
            val = 4
            text = _("Strong")
            self._error = False

        if not self.pw.get_text():
            val = 0
            text = _("Empty")
            self._error = _("The password is empty.")
        elif self.confirm.get_text() and self.pw.get_text() != self.confirm.get_text():
            self._error = _("The passwords do not match.")

        self.pw_bar.set_value(val)
        self.pw_label.set_text(text)

        self.clear_info()
        if self._error:
            self.set_warning(self._error)
            self.window.show_all()
            return False

        return True

    def _validatePassword(self):
        # Do various steps to validate the password
        # sets self._error to an error string
        # Return True if valid, False otherwise
        self._error = False
        pw = self.pw.get_text()
        confirm = self.confirm.get_text()

        if not pw and not confirm:
            if self._kickstarted:
                return True
            else:
                self._error = _("You must provide and confirm a password.")
                return False

        try:
            self._error = validatePassword(pw, confirm)
        except PWQError as e:
            if pw == self._oldweak:
                # We got a second attempt with the same weak password
                pass
            else:
                self._error = _("You have provided a weak password: %s. "
                                " Press Done again to use anyway.") % e.message
                self._oldweak = pw
                return False

        if self._error:
            return False

        # the self._checkPassword function is used to indicate the password
        # strength and need of hitting the Done button twice so use it here as
        # well
        if not self._checkPassword() and pw != self._oldweak:
            # check failed and the Done button was clicked for the first time
            self._oldweak = pw
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
