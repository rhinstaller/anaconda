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

from pyanaconda.i18n import _, N_
from pyanaconda.users import cryptPassword, validatePassword

from pyanaconda.ui.gui import GUICheck
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.user_settings import UserSettingsCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn

from pyanaconda.constants import PASSWORD_EMPTY_ERROR, PASSWORD_CONFIRM_ERROR_GUI,\
        PASSWORD_STRENGTH_DESC, PASSWORD_WEAK, PASSWORD_WEAK_WITH_ERROR,\
        PASSWORD_WEAK_CONFIRM, PASSWORD_WEAK_CONFIRM_WITH_ERROR

__all__ = ["PasswordSpoke"]


class PasswordSpoke(FirstbootSpokeMixIn, NormalSpoke):
    builderObjects = ["passwordWindow"]

    mainWidgetName = "passwordWindow"
    uiFile = "spokes/password.glade"

    category = UserSettingsCategory

    icon = "dialog-password-symbolic"
    title = N_("_ROOT PASSWORD")

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        self._kickstarted = False

    def initialize(self):
        NormalSpoke.initialize(self)
        # place holders for the text boxes
        self.pw = self.builder.get_object("pw")
        self.confirm = self.builder.get_object("confirm")

        # Install the password checks:
        # - Has a password been specified?
        # - If a password has been specified and there is data in the confirm box, do they match?
        # - How strong is the password?
        # - Is there any data in the confirm box?
        self.add_check(self.pw, self._checkPasswordEmpty)

        # The password confirmation needs to be checked whenever either of the password
        # fields change. Separate checks are created for each field so that edits on either
        # will trigger a new check and so that the last edited field will get focus when
        # Done is clicked. The checks are saved here so that either check can trigger the
        # other check in order to reset the status on both when either field is changed.
        # The check_data field is used as a flag to prevent infinite recursion.
        self._confirm_check = self.add_check(self.confirm, self._checkPasswordConfirm)
        self._password_check = self.add_check(self.pw, self._checkPasswordConfirm)

        # Keep a reference for this check, since it has to be manually run for the
        # click Done twice check.
        self._pwStrengthCheck = self.add_check(self.pw, self._checkPasswordStrength)

        self.add_check(self.confirm, self._checkPasswordEmpty)

        # Counter for the click Done twice check override
        self._waivePasswordClicks = 0

        # Password validation data
        self._pwq_error = None
        self._pwq_valid = True

        self._kickstarted = self.data.rootpw.seen
        if self._kickstarted:
            self.pw.set_placeholder_text(_("The password is set."))
            self.confirm.set_placeholder_text(_("The password is set."))

        self.pw_bar = self.builder.get_object("password_bar")
        self.pw_label = self.builder.get_object("password_label")

        # Configure levels for the password bar
        self.pw_bar.add_offset_value("low", 2)
        self.pw_bar.add_offset_value("medium", 3)
        self.pw_bar.add_offset_value("high", 4)

    def refresh(self):
        # Enable the input checks in case they were disabled on the last exit
        for check in self.checks:
            check.enable()

        self.pw.grab_focus()
        self.pw.emit("changed")

    @property
    def status(self):
        if self.data.rootpw.password:
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
        pw = self.pw.get_text()
        if not pw:
            return

        self.data.rootpw.password = cryptPassword(pw)
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

    def _checkPasswordEmpty(self, editable, data):
        """Check whether a password has been specified at all."""

        # If the password was set by kickstart, skip this check
        if self._kickstarted:
            return GUICheck.CHECK_OK

        if not editable.get_text():
            if editable == self.pw:
                return _(PASSWORD_EMPTY_ERROR)
            else:
                return _(PASSWORD_CONFIRM_ERROR_GUI)
        else:
            return GUICheck.CHECK_OK

    def _checkPasswordConfirm(self, editable=None, reset_status=None):
        """Check whether the password matches the confirmation data."""

        # This check is triggered by changes to either the password field or the
        # confirmation field. If this method is being run from a successful check
        # to reset the status, just return success
        if reset_status:
            return GUICheck.CHECK_OK

        pw = self.pw.get_text()
        confirm = self.confirm.get_text()

        # Skip the check if no password is required
        if (not pw and not confirm) and self._kickstarted:
            result = GUICheck.CHECK_OK
        elif confirm and (pw != confirm):
            result = _(PASSWORD_CONFIRM_ERROR_GUI)
        else:
            result = GUICheck.CHECK_OK

        # If the check succeeded, reset the status of the other check object
        if result == GUICheck.CHECK_OK:
            if editable == self.confirm:
                self._password_check.update_check_status(check_data=True)
            else:
                self._confirm_check.update_check_status(check_data=True)

        return result

    def _updatePwQuality(self, editable=None, data=None):
        """Update the password quality information.

           This function is called by the ::changed signal handler on the
           password field.
        """

        pwtext = self.pw.get_text()

        # Reset the counter used for the "press Done twice" logic
        self._waivePasswordClicks = 0

        self._pwq_valid, strength, self._pwq_error = validatePassword(pwtext, "root")

        if not pwtext:
            val = 0
        elif strength < 50:
            val = 1
        elif strength < 75:
            val = 2
        elif strength < 90:
            val = 3
        else:
            val = 4
        text = _(PASSWORD_STRENGTH_DESC[val])

        self.pw_bar.set_value(val)
        self.pw_label.set_text(text)

    def _checkPasswordStrength(self, editable=None, data=None):
        """Update the error message based on password strength.

           Convert the strength set by _updatePwQuality into an error message.
        """

        pw = self.pw.get_text()
        confirm = self.confirm.get_text()

        # Skip the check if no password is required
        if (not pw and not confirm) and self._kickstarted:
            return GUICheck.CHECK_OK

        # Check for validity errors
        if (not self._pwq_valid) and (self._pwq_error):
            return self._pwq_error

        pwstrength = self.pw_bar.get_value()

        if pwstrength < 2:
            # If Done has been clicked twice, waive the check
            if self._waivePasswordClicks > 1:
                return GUICheck.CHECK_OK
            elif self._waivePasswordClicks == 1:
                if self._pwq_error:
                    return _(PASSWORD_WEAK_CONFIRM_WITH_ERROR) % self._pwq_error
                else:
                    return _(PASSWORD_WEAK_CONFIRM)
            else:
                if self._pwq_error:
                    return _(PASSWORD_WEAK_WITH_ERROR) % self._pwq_error
                else:
                    return _(PASSWORD_WEAK)
        else:
            return GUICheck.CHECK_OK

    def on_back_clicked(self, button):
        # Add a click and re-check the password strength
        self._waivePasswordClicks += 1
        self._pwStrengthCheck.update_check_status()

        # If neither the password nor the confirm field are set, skip the checks
        if (not self.pw.get_text()) and (not self.confirm.get_text()):
            for check in self.checks:
                check.disable()

        NormalSpoke.on_back_clicked(self, button)
