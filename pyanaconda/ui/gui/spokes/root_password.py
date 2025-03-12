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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda import input_checking
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants
from pyanaconda.core.constants import PASSWORD_POLICY_ROOT
from pyanaconda.core.i18n import CN_, _
from pyanaconda.core.users import crypt_password
from pyanaconda.modules.common.constants.services import USERS
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.ui.categories.user_settings import UserSettingsCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui.helpers import GUISpokeInputCheckHandler
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.utils import set_password_visibility
from pyanaconda.ui.lib.users import (
    can_modify_root_configuration,
    get_root_configuration_status,
)

log = get_module_logger(__name__)

__all__ = ["PasswordSpoke"]


class PasswordSpoke(FirstbootSpokeMixIn, NormalSpoke, GUISpokeInputCheckHandler):
    """
       .. inheritance-diagram:: PasswordSpoke
          :parts: 3
    """
    builderObjects = ["passwordWindow"]

    mainWidgetName = "passwordWindow"
    focusWidgetName = "disable_root_radio"
    uiFile = "spokes/root_password.glade"
    category = UserSettingsCategory
    icon = "dialog-password-symbolic"
    title = CN_("GUI|Spoke", "_Root Account")

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "root-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Should the spoke run?"""
        if not is_module_available(USERS):
            return False

        return FirstbootSpokeMixIn.should_run(environment, data)

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        GUISpokeInputCheckHandler.__init__(self)
        self._users_module = USERS.get_proxy()

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()
        # get object references from the builders
        self._password_entry = self.builder.get_object("password_entry")
        self._password_confirmation_entry = self.builder.get_object("password_confirmation_entry")
        self._password_bar = self.builder.get_object("password_bar")
        self._password_label = self.builder.get_object("password_label")
        self._enable_root_radio = self.builder.get_object("enable_root_radio")
        self._disable_root_radio = self.builder.get_object("disable_root_radio")
        self._root_password_ssh_login_override = self.builder.get_object("root_password_ssh_login_override")
        self._revealer = self.builder.get_object("password_revealer")

        # Install the password checks:
        # - Has a password been specified?
        # - If a password has been specified and there is data in the confirm box, do they match?
        # - How strong is the password?
        # - Does the password contain non-ASCII characters?

        # Setup the password checker for password checking
        self._checker = input_checking.PasswordChecker(
                initial_password_content=self.password,
                initial_password_confirmation_content=self.password_confirmation,
                policy_name=PASSWORD_POLICY_ROOT
        )
        # configure root username for checking
        self.checker.username = "root"
        # configure the checker for password checking
        self.checker.secret_type = constants.SecretType.PASSWORD
        # remove any placeholder texts if either password or confirmation field changes content from initial state
        self.checker.password.changed_from_initial_state.connect(self.remove_placeholder_texts)
        self.checker.password_confirmation.changed_from_initial_state.connect(self.remove_placeholder_texts)
        # connect UI updates to check results
        self.checker.checks_done.connect(self._checks_done)

        # check that the password is not empty
        self._empty_check = input_checking.PasswordEmptyCheck()
        # check that the content of the password field & the conformation field are the same
        self._confirm_check = input_checking.PasswordConfirmationCheck()
        # check password validity, quality and strength
        self._validity_check = input_checking.PasswordValidityCheck()
        # connect UI updates to validity check results
        self._validity_check.result.password_score_changed.connect(self.set_password_score)
        self._validity_check.result.status_text_changed.connect(self.set_password_status)
        # check if the password contains non-ascii characters
        self._ascii_check = input_checking.PasswordASCIICheck()

        # register the individual checks with the checker in proper order
        # 1) is the password non-empty ?
        # 2) are both entered passwords the same ?
        # 3) is the password valid according to the current password checking policy ?
        # 4) is the password free of non-ASCII characters ?
        self.checker.add_check(self._empty_check)
        self.checker.add_check(self._confirm_check)
        self.checker.add_check(self._validity_check)
        self.checker.add_check(self._ascii_check)

        # Set placeholders if the password has been set outside of the Anaconda
        # GUI we either don't really know anything about it if it's crypted
        # and still would not really want to expose it if its set in plaintext,
        # and thus can'treally show it in the UI in any meaningful way.
        if self._users_module.IsRootPasswordSet:
            password_set_message = _("Root password has been set.")
            self.password_entry.set_placeholder_text(password_set_message)
            self.password_confirmation_entry.set_placeholder_text(password_set_message)

        # Configure levels for the password bar
        self._password_bar.add_offset_value("low", 2)
        self._password_bar.add_offset_value("medium", 3)
        self._password_bar.add_offset_value("high", 4)

        # Send ready signal to main event loop
        hubQ.send_ready(self.__class__.__name__)

        # report that we are done
        self.initialize_done()

    def refresh(self):
        # set the locked/unlocked state based on DBus data
        if self._users_module.IsRootAccountLocked:
            control = self._disable_root_radio
        else:
            control = self._enable_root_radio
        control.set_active(True)
        self.on_root_enabled_changed(control)

        self._root_password_ssh_login_override.set_active(
            self._users_module.RootPasswordSSHLoginAllowed
        )
        if self.root_enabled:
            # rerun checks so that we have a correct status message, if any
            self.checker.run_checks()
        # focus on the password field if it is sensitive
        if self.password_entry.get_sensitive():
            self.password_entry.grab_focus()

    @property
    def status(self):
        return get_root_configuration_status(self._users_module)

    @property
    def mandatory(self):
        """Only mandatory if no admin user has been requested."""
        return not self._users_module.CheckAdminUserExists()

    def apply(self):
        if self.root_enabled and self.password:
            # Set the root password.
            self._users_module.SetCryptedRootPassword(crypt_password(self.password))

            # Unlock the root account.
            self._users_module.IsRootAccountLocked = False
        else:
            # Reset the root password.
            self._users_module.ClearRootPassword()

            # Lock the root account.
            self._users_module.IsRootAccountLocked = True

        if self.root_enabled:
            # the checkbox makes it possible to override the default Open SSH
            # policy of not allowing root to login with password
            ssh_login_override = self._root_password_ssh_login_override.get_active()
            self._users_module.RootPasswordSSHLoginAllowed = ssh_login_override

        # clear any placeholders
        self.remove_placeholder_texts()

        # Send ready signal to main event loop
        hubQ.send_ready(self.__class__.__name__)

    @property
    def completed(self):
        return self._users_module.IsRootPasswordSet

    @property
    def sensitive(self):
        return can_modify_root_configuration(self._users_module)

    @property
    def root_enabled(self):
        return self._enable_root_radio.get_active()

    def _checks_done(self, error_message):
        """Update the warning with the input validation error from the first
           error message or clear warnings if all the checks were successful.

           Also appends the "press twice" suffix if compatible with current
           password policy and handles the press-done-twice logic.
        """
        # check if an unwaivable check failed
        unwaivable_check_failed = not self._confirm_check.result.success

        # set appropriate status bar message
        if not error_message or not self.root_enabled:
            # all is fine, just clear the message
            self.clear_info()
        elif not self.password and not self.password_confirmation:
            # Clear any info message if both the password and password
            # confirmation fields are empty.
            # This shortcut is done to make it possible for the user to leave the spoke
            # without inputting any root password. Separate logic makes sure an
            # empty string is not set as the root password.
            self.clear_info()
        else:
            if self.checker.policy.is_strict or unwaivable_check_failed:
                # just forward the error message
                self.show_warning_message(error_message)
            else:
                # add suffix for the click twice logic
                self.show_warning_message(
                    _(constants.PASSWORD_ERROR_CONCATENATION).format(
                        error_message,
                        _(constants.PASSWORD_DONE_TWICE))
                )

        # check if the spoke can be exited after the latest round of checks
        self._check_spoke_exit_conditions(unwaivable_check_failed)

    def _check_spoke_exit_conditions(self, unwaivable_check_failed):
        # Check if the user can escape from the root spoke or stay forever !

        # reset any waiving in progress
        self.waive_clicks = 0

        # Depending on the policy we allow users to waive the password strength
        # and non-ASCII checks. If the policy is set to strict, the password
        # needs to be strong, but can still contain non-ASCII characters.
        self.can_go_back = False
        self.needs_waiver = True

        # This shortcut is done to make it possible for the user to leave the spoke
        # without inputting any root password. Separate logic makes sure an
        # empty string is not set as the root password.
        if not self.password and not self.password_confirmation:
            self.can_go_back = True
            self.needs_waiver = False
        elif self.checker.success:
            # if all checks were successful we can always go back to the hub
            self.can_go_back = True
            self.needs_waiver = False
        elif unwaivable_check_failed:
            self.can_go_back = False
        else:
            if self.checker.policy.is_strict:
                if not self._validity_check.result.success:
                    # failing validity check in strict
                    # mode prevents us from going back
                    self.can_go_back = False
                elif not self._ascii_check.result.success:
                    # but the ASCII check can still be waived
                    self.can_go_back = True
                    self.needs_waiver = True
                else:
                    self.can_go_back = True
                    self.needs_waiver = False
            else:
                if not self._validity_check.result.success:
                    self.can_go_back = True
                    self.needs_waiver = True
                elif not self._ascii_check.result.success:
                    self.can_go_back = True
                    self.needs_waiver = True
                else:
                    self.can_go_back = True
                    self.needs_waiver = False

    def on_password_changed(self, editable, data=None):
        """Tell checker that the content of the password field changed."""
        self.checker.password.content = self.password

    def on_password_confirmation_changed(self, editable, data=None):
        """Tell checker that the content of the password confirmation field changed."""
        self.checker.password_confirmation.content = self.password_confirmation

    def on_password_icon_clicked(self, entry, icon_pos, event):
        """Called by Gtk callback when the icon of a password entry is clicked."""
        set_password_visibility(entry, not entry.get_visibility())

    def on_password_entry_map(self, entry):
        """Called when a password entry widget is going to be displayed.

        - Without this the password visibility toggle icon would not be shown.
        - The password should be hidden every time the entry widget is displayed
          to avoid showing the password in plain text in case the user previously
          displayed the password and then left the spoke, for example.
        """
        set_password_visibility(entry, False)

    def on_back_clicked(self, button):
        # disable root if no password is entered
        if not self.password and not self.password_confirmation and \
                not self._users_module.IsRootPasswordSet:
            control = self._disable_root_radio
            control.set_active(True)
            self.on_root_enabled_changed(control)

        # the GUI spoke input check handler handles the rest of the spoke exit logic for us
        if self.try_to_go_back() or not self.root_enabled:
            NormalSpoke.on_back_clicked(self, button)
        else:
            log.info("Return to hub prevented by password checking rules.")

    def on_root_enabled_changed(self, control):
        """Click event handler for root account enable and disable radio buttons."""
        unlocked = (control == self._enable_root_radio)
        self._revealer.set_reveal_child(unlocked)
        if unlocked:
            self.password_entry.grab_focus()
