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

from pyanaconda.flags import flags
from pyanaconda.i18n import _, CN_
from pyanaconda.users import cryptPassword

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.categories.user_settings import UserSettingsCategory
from pyanaconda.ui.gui.helpers import GUISpokeInputCheckHandler
from pyanaconda.ui.gui.utils import set_password_visibility
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.communication import hubQ

__all__ = ["PasswordSpoke"]


class PasswordSpoke(FirstbootSpokeMixIn, NormalSpoke, GUISpokeInputCheckHandler):
    """
       .. inheritance-diagram:: PasswordSpoke
          :parts: 3
    """
    builderObjects = ["passwordWindow"]

    mainWidgetName = "passwordWindow"
    focusWidgetName = "pw"
    uiFile = "spokes/root_password.glade"
    helpFile = "PasswordSpoke.xml"

    category = UserSettingsCategory

    icon = "dialog-password-symbolic"
    title = CN_("GUI|Spoke", "_ROOT PASSWORD")

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        GUISpokeInputCheckHandler.__init__(self)
        self._kickstarted = False

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()
        # place holders for the text boxes
        self.pw = self.builder.get_object("pw")
        self.confirm = self.builder.get_object("confirmPW")

        # Install the password checks:
        # - Has a password been specified?
        # - If a password has been specified and there is data in the confirm box, do they match?
        # - How strong is the password?
        # - Does the password contain non-ASCII characters?
        # - Is there any data in the confirm box?
        self._confirm_check = self.add_check(self.confirm, self.check_password_confirm)

        # Keep a reference for these checks, since they have to be manually run for the
        # click Done twice check.
        self._pwEmptyCheck = self.add_check(self.pw, self.check_password_empty)
        self._pwStrengthCheck = self.add_check(self.pw, self.check_user_password_strength)
        self._pwASCIICheck = self.add_check(self.pw, self.check_password_ASCII)

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
        self.pw_bar.add_offset_value("full", 4)

        # Configure the password policy, if available. Otherwise use defaults.
        self.policy = self.data.anaconda.pwpolicy.get_policy("root", fallback_to_default=True)

        # set the visibility of the password entries
        set_password_visibility(self.pw, False)
        set_password_visibility(self.confirm, False)

        # Send ready signal to main event loop
        hubQ.send_ready(self.__class__.__name__, False)

        # report that we are done
        self.initialize_done()

    def refresh(self):
        # Enable the input checks in case they were disabled on the last exit
        for check in self.checks:
            check.enabled = True

        self.pw.grab_focus()
        self.pw.emit("changed")
        self.confirm.emit("changed")

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
        return not any(user for user in self.data.user.userList if "wheel" in user.groups)

    def apply(self):
        pw = self.pw.get_text()

        # value from the kickstart changed
        self.data.rootpw.seen = False
        self._kickstarted = False

        self.data.rootpw.lock = False

        if not pw:
            self.data.rootpw.password = ''
            self.data.rootpw.isCrypted = False
            return

        self.data.rootpw.password = cryptPassword(pw)
        self.data.rootpw.isCrypted = True

        self.pw.set_placeholder_text("")
        self.confirm.set_placeholder_text("")

        # Send ready signal to main event loop
        hubQ.send_ready(self.__class__.__name__, False)

    @property
    def completed(self):
        return bool(self.data.rootpw.password or self.data.rootpw.lock)

    @property
    def sensitive(self):
        return not (self.completed and flags.automatedInstall
                    and self.data.rootpw.seen)

    @property
    def input(self):
        return self.pw.get_text()

    @property
    def input_confirmation(self):
        return self.confirm.get_text()

    @property
    def input_kickstarted(self):
        return self.data.rootpw.seen

    @property
    def input_username(self):
        return "root"

    def set_input_score(self, score):
        self.pw_bar.set_value(score)

    def set_input_status(self, status_message):
        self.pw_label.set_text(status_message)

    def on_password_changed(self, editable, data=None):
        # Reset the counters used for the "press Done twice" logic
        self.waive_clicks = 0
        self.waive_ASCII_clicks = 0

        # Update the password/confirm match check on changes to the main password field
        self._confirm_check.update_check_status()

    def on_password_icon_clicked(self, entry, icon_pos, event):
        """Called by Gtk callback when the icon of a password entry is clicked."""
        set_password_visibility(entry, not entry.get_visibility())

    def on_back_clicked(self, button):
        # If the failed check is for password strength or non-ASCII
        # characters, add a click to the counter and check again
        failed_check = next(self.failed_checks_with_message, None)
        if not self.policy.strict:
            if failed_check == self._pwStrengthCheck:
                self.waive_clicks += 1
                self._pwStrengthCheck.update_check_status()
            elif failed_check == self._pwEmptyCheck:
                self.waive_clicks += 1
                self._pwEmptyCheck.update_check_status()
            elif failed_check == self._pwASCIICheck:
                self.waive_ASCII_clicks += 1
                self._pwASCIICheck.update_check_status()
            elif failed_check:  # no failed checks -> failed_check == None
                failed_check.update_check_status()

        if GUISpokeInputCheckHandler.on_back_clicked(self, button):
            NormalSpoke.on_back_clicked(self, button)
