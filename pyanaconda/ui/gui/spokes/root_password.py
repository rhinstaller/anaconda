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
from pyanaconda.core.i18n import _, CN_
from pyanaconda.users import cryptPassword
from pyanaconda import input_checking
from pyanaconda.core import constants
from pyanaconda.modules.common.constants.services import USERS, SERVICES

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.categories.user_settings import UserSettingsCategory
from pyanaconda.ui.gui.helpers import GUISpokeInputCheckHandler
from pyanaconda.ui.gui.utils import set_password_visibility
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.communication import hubQ

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["PasswordSpoke"]


class PasswordSpoke(FirstbootSpokeMixIn, NormalSpoke, GUISpokeInputCheckHandler):
    """
       .. inheritance-diagram:: PasswordSpoke
          :parts: 3
    """
    builderObjects = ["passwordWindow"]

    mainWidgetName = "passwordWindow"
    focusWidgetName = "password_entry"
    uiFile = "spokes/root_password.glade"
    helpFile = "PasswordSpoke.xml"

    category = UserSettingsCategory

    icon = "dialog-password-symbolic"
    title = CN_("GUI|Spoke", "_Root Password")

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        GUISpokeInputCheckHandler.__init__(self)

        self._users_module = USERS.get_observer()
        self._users_module.connect()

        self._services_module = SERVICES.get_observer()
        self._services_module.connect()

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()
        # get object references from the builders
        self._password_entry = self.builder.get_object("password_entry")
        self._password_confirmation_entry = self.builder.get_object("password_confirmation_entry")
        self._password_bar = self.builder.get_object("password_bar")
        self._password_label = self.builder.get_object("password_label")
        self._lock = self.builder.get_object("lock")

        # set state based on kickstart
        # NOTE: this will stop working once the module supports multiple kickstart commands
        self.password_kickstarted = self._users_module.proxy.IsRootpwKickstarted

        # Install the password checks:
        # - Has a password been specified?
        # - If a password has been specified and there is data in the confirm box, do they match?
        # - How strong is the password?
        # - Does the password contain non-ASCII characters?

        # Setup the password checker for password checking
        self._checker = input_checking.PasswordChecker(
                initial_password_content = self.password,
                initial_password_confirmation_content = self.password_confirmation,
                policy = input_checking.get_policy(self.data, "root")
        )
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
        # regards both fields empty as success to let the user escape
        self._confirm_check.success_if_confirmation_empty = True
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

        # set placeholders if the password has been kickstarted as we likely don't know
        # nothing about it and can't really show it in the UI in any meaningful way
        password_set_message = _("The password was set by kickstart.")
        if self.password_kickstarted:
            self.password_entry.set_placeholder_text(password_set_message)
            self.password_confirmation_entry.set_placeholder_text(password_set_message)

        # Configure levels for the password bar
        self._password_bar.add_offset_value("low", 2)
        self._password_bar.add_offset_value("medium", 3)
        self._password_bar.add_offset_value("high", 4)

        # Send ready signal to main event loop
        hubQ.send_ready(self.__class__.__name__, False)

        # report that we are done
        self.initialize_done()

    def refresh(self):
        # focus on the password field if password was not kickstarted
        if not self.password_kickstarted or not self._lock.get_active():
            self.password_entry.grab_focus()

        self._lock.set_active(self._users_module.proxy.IsRootAccountLocked)
        self.on_lock_clicked(self._lock)

        if not self._lock.get_active():
            # rerun checks so that we have a correct status message, if any
            self.checker.run_checks()

    @property
    def status(self):
        if self._users_module.proxy.IsRootAccountLocked:
            # check if we are running in Initial Setup reconfig mode
            reconfig_mode = self._services_module.proxy.SetupOnBoot == constants.SETUP_ON_BOOT_RECONFIG
            # reconfig mode currently allows re-enabling a locked root account if
            # user sets a new root password
            if reconfig_mode and not self._lock.get_active():
                return _("Disabled, set password to enable.")
            else:
                return _("Root account is disabled.")

        elif self._users_module.proxy.IsRootPasswordSet:
            return _("Root password is set")
        else:
            return _("Root password is not set")

    @property
    def mandatory(self):
        return not any(user for user in self.data.user.userList if "wheel" in user.groups)

    def apply(self):
        pw = self.password

        # value from the kickstart changed
        # NOTE: yet again, this stops to be valid once multiple
        #       commands are supported by a single DBUS module
        self._users_module.proxy.SetRootpwKickstarted(False)
        self.password_kickstarted = False

        self._users_module.proxy.SetRootAccountLocked(self._lock.get_active())

        if not pw:
            self._users_module.proxy.ClearRootPassword()
            return

        # we have a password - set it to kickstart data

        self._users_module.proxy.SetCryptedRootPassword(cryptPassword(pw))

        # clear any placeholders
        self.remove_placeholder_texts()

        # Send ready signal to main event loop
        hubQ.send_ready(self.__class__.__name__, False)

    @property
    def completed(self):
        return bool(self._users_module.proxy.IsRootPasswordSet or self._users_module.proxy.IsRootAccountLocked)

    @property
    def sensitive(self):
        return not (self.completed and flags.automatedInstall
                    and self._users_module.proxy.IsRootpwKickstarted)

    def _checks_done(self, error_message):
        """Update the warning with the input validation error from the first
           error message or clear warnings if all the checks were successful.

           Also appends the "press twice" suffix if compatible with current
           password policy and handles the press-done-twice logic.
        """
        # check if an unwaivable check failed
        unwaivable_check_failed = not self._confirm_check.result.success

        # set appropriate status bar message
        if not error_message or self._lock.get_active():
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
            if self.checker.policy.strict or unwaivable_check_failed:
                # just forward the error message
                self.show_warning_message(error_message)
            else:
                # add suffix for the click twice logic
                self.show_warning_message("{} {}".format(error_message,
                                                         _(constants.PASSWORD_DONE_TWICE)))

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
            if self.checker.policy.strict:
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

    def on_back_clicked(self, button):
        # the GUI spoke input check handler handles the spoke exit logic for us
        if self.try_to_go_back() or self._lock.get_active():
            NormalSpoke.on_back_clicked(self, button)
        else:
            log.info("Return to hub prevented by password checking rules.")

    def on_lock_clicked(self, lock):
        self.password_entry.set_sensitive(not lock.get_active())
        self.password_confirmation_entry.set_sensitive(not lock.get_active())
        if not lock.get_active():
            self.password_entry.grab_focus()
