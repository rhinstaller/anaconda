# User creation spoke
#
# Copyright (C) 2013-2014 Red Hat, Inc.
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
import os

from pyanaconda import input_checking
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import PASSWORD_POLICY_USER
from pyanaconda.core.i18n import CN_, _
from pyanaconda.core.regexes import GROUPLIST_FANCY_PARSE
from pyanaconda.core.users import check_groupname, crypt_password, guess_username
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.services import USERS
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.ui.categories.user_settings import UserSettingsCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.helpers import (
    GUIDialogInputCheckHandler,
    GUISpokeInputCheckHandler,
)
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.utils import blockedHandler, set_password_visibility
from pyanaconda.ui.helpers import InputCheck
from pyanaconda.ui.lib.users import get_user_list, set_user_list

log = get_module_logger(__name__)

__all__ = ["AdvancedUserDialog", "UserSpoke"]


class AdvancedUserDialog(GUIObject, GUIDialogInputCheckHandler):
    """
       .. inheritance-diagram:: AdvancedUserDialog
          :parts: 3
    """
    builderObjects = ["advancedUserDialog", "uid", "gid"]
    mainWidgetName = "advancedUserDialog"
    uiFile = "spokes/advanced_user.glade"

    def _validateGroups(self, inputcheck):
        groups_string = self.get_input(inputcheck.input_obj)

        # Pass if the string is empty
        if not groups_string:
            return InputCheck.CHECK_OK

        # Check each group name in the list
        for group in groups_string.split(","):
            group_name = GROUPLIST_FANCY_PARSE.match(group).group('name')
            valid, message = check_groupname(group_name)
            if not valid:
                return message or _("Invalid group name.")

        return InputCheck.CHECK_OK

    def __init__(self, user_spoke):
        GUIObject.__init__(self, user_spoke)

        saveButton = self.builder.get_object("save_button")
        GUIDialogInputCheckHandler.__init__(self, saveButton)

        self._user_spoke = user_spoke

        # Track whether the user has requested a home directory other
        # than the default. This way, if the home directory is left as
        # the default, the default will change if the username changes.
        # Otherwise, once the directory is set it stays that way.
        self._origHome = None

    def _grabObjects(self):
        self._cUid = self.builder.get_object("c_uid")
        self._cGid = self.builder.get_object("c_gid")
        self._tHome = self.builder.get_object("t_home")
        self._tGroups = self.builder.get_object("t_groups")
        self._spinUid = self.builder.get_object("spin_uid")
        self._spinGid = self.builder.get_object("spin_gid")
        self._uid = self.builder.get_object("uid")
        self._gid = self.builder.get_object("gid")

    def initialize(self):
        GUIObject.initialize(self)

        self._grabObjects()

        # Validate the group input box
        self.add_check(self._tGroups, self._validateGroups)
        # Send ready signal to main event loop
        hubQ.send_ready(self.__class__.__name__)

    @property
    def user(self):
        """Shortcut to user data from the user spoke."""
        return self._user_spoke.user

    def refresh(self):
        # start be reloading the user data from the user spoke
        if self.user.homedir:
            homedir = self.user.homedir
        elif self.user.name:
            homedir = "/home/" + self.user.name
        else:
            # this state shouldn't happen
            raise ValueError("Can't resolve home directory")

        self._tHome.set_text(homedir)
        self._origHome = homedir

        self._cUid.set_active(self.user.get_uid() is not None)
        self._cGid.set_active(self.user.get_gid() is not None)

        self._spinUid.update()
        self._spinGid.update()

        self._tGroups.set_text(", ".join(self.user.groups))

    def apply(self):
        # Copy data from the UI back to the user data object
        homedir = self._tHome.get_text()

        # If the user cleared the home directory, revert back to the
        # default
        if not homedir:
            self.user.homedir = ""
        # If the user modified the home directory input, save that the
        # home directory has been modified and use the value.
        elif self._origHome != homedir:
            if not os.path.isabs(homedir):
                homedir = "/" + homedir
            self.user.homedir = homedir

        # Otherwise leave the home directory alone. If the home
        # directory is currently the default value, the next call
        # to refresh() will update the input text to reflect
        # changes in the username.

        if self._cUid.get_active():
            self.user.set_uid(int(self._uid.get_value()))
        else:
            self.user.set_uid(None)

        if self._cGid.get_active():
            self.user.set_gid(int(self._gid.get_value()))
        else:
            self.user.set_gid(None)

        # ''.split(',') returns [''] instead of [], which is not what we want
        self.user.groups = [''.join(g.split()) for g in self._tGroups.get_text().split(",") if g]

        # Send ready signal to main event loop
        hubQ.send_ready(self.__class__.__name__)

    def run(self):
        self.window.show()
        while True:
            rc = self.window.run()

            #OK clicked
            if rc == 1:
                # Input checks pass
                if self.on_ok_clicked():
                    self.apply()
                    break
                # Input checks fail, try again
                else:
                    continue

            #Cancel clicked, window destroyed...
            else:
                break

        self.window.hide()
        return rc

    def on_uid_checkbox_toggled(self, togglebutton, data=None):
        # Set the UID spinner sensitivity based on the UID checkbox
        self._spinUid.set_sensitive(togglebutton.get_active())

    def on_gid_checkbox_toggled(self, togglebutton, data=None):
        # Same as above, for GID
        self._spinGid.set_sensitive(togglebutton.get_active())

    def on_uid_mnemonic_activate(self, widget, group_cycling, user_data=None):
        # If this is the only widget with the mnemonic (group_cycling is False),
        # and the checkbox is not currently toggled, toggle the checkbox and
        # then set the focus to the UID spinner
        if not group_cycling and not widget.get_active():
            widget.set_active(True)
            self._spinUid.grab_focus()
            return True

        # Otherwise just use the default signal handler
        return False

    def on_gid_mnemonic_activate(self, widget, group_cycling, user_data=None):
        # Same as above, but for GID
        if not group_cycling and not widget.get_active():
            widget.set_active(True)
            self._spinGid.grab_focus()
            return True

        return False


class UserSpoke(FirstbootSpokeMixIn, NormalSpoke, GUISpokeInputCheckHandler):
    """
       .. inheritance-diagram:: UserSpoke
          :parts: 3
    """
    builderObjects = ["userCreationWindow"]

    mainWidgetName = "userCreationWindow"
    focusWidgetName = "fullname_entry"
    uiFile = "spokes/user.glade"
    category = UserSettingsCategory
    icon = "avatar-default-symbolic"
    title = CN_("GUI|Spoke", "_User Creation")

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "user-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Should the spoke run?"""
        if not is_module_available(USERS):
            return False

        # the user spoke should run always in the anaconda and in firstboot only
        # when doing reconfig or if no user has been created in the installation
        users_module = USERS.get_proxy()
        user_list = get_user_list(users_module)

        if environment == constants.ANACONDA_ENVIRON:
            return True
        elif environment == constants.FIRSTBOOT_ENVIRON and data is None:
            # cannot decide, stay in the game and let another call with data
            # available (will come) decide
            return True
        elif environment == constants.FIRSTBOOT_ENVIRON and data and not user_list:
            return True
        else:
            return False

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        GUISpokeInputCheckHandler.__init__(self)

        self._users_module = USERS.get_proxy()
        self._password_is_required = True

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()

        # We consider user creation requested if there was at least one user
        # in the DBus module user list at startup.
        # We also remember how the user was called so that we can clear it
        # in a reasonably safe way & if it was cleared.
        self._user_list = get_user_list(self._users_module, add_default=True)
        self._user_requested = False
        self._requested_user_cleared = False
        # if user has a name, it's an actual user that has been requested,
        # rather than a default user added by us
        if self.user.name:
            self._user_requested = True

        # gather references to relevant GUI objects

        # entry fields
        self._fullname_entry = self.builder.get_object("fullname_entry")
        self._username_entry = self.builder.get_object("username_entry")
        self._password_entry = self.builder.get_object("password_entry")
        self._password_confirmation_entry = self.builder.get_object("password_confirmation_entry")
        # check boxes
        self._admin_checkbox = self.builder.get_object("admin_checkbox")
        self._password_required_checkbox = self.builder.get_object("password_required_checkbox")
        # advanced user configration dialog button
        self._advanced_button = self.builder.get_object("advanced_button")
        # password checking status bar & label
        self._password_bar = self.builder.get_object("password_bar")
        self._password_label = self.builder.get_object("password_label")

        # Install the password checks:
        # - Has a password been specified?
        # - If a password has been specified and there is data in the confirm box, do they match?
        # - How strong is the password?
        # - Does the password contain non-ASCII characters?

        # Setup the password checker for password checking
        self._checker = input_checking.PasswordChecker(
                initial_password_content=self.password,
                initial_password_confirmation_content=self.password_confirmation,
                policy_name=PASSWORD_POLICY_USER
        )
        # configure the checker for password checking
        self.checker.username = self.username
        self.checker.secret_type = constants.SecretType.PASSWORD
        # remove any placeholder texts if either password or confirmation field changes content from initial state
        self.checker.password.changed_from_initial_state.connect(self.remove_placeholder_texts)
        self.checker.password_confirmation.changed_from_initial_state.connect(self.remove_placeholder_texts)
        # connect UI updates to check results
        self.checker.checks_done.connect(self._checks_done)

        # username and full name checks
        self._username_check = input_checking.UsernameCheck()
        self._fullname_check = input_checking.FullnameCheck()
        # empty username is considered a success so that the user can leave
        # the spoke without filling it in
        self._username_check.success_if_username_empty = True
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
        # Skip the empty and validity password checks if no username is set
        self._empty_check.skip = True
        self._validity_check.skip = True

        # register the individual checks with the checker in proper order
        # 0) is the username and fullname valid ?
        # 1) is the password non-empty ?
        # 2) are both entered passwords the same ?
        # 3) is the password valid according to the current password checking policy ?
        # 4) is the password free of non-ASCII characters ?
        self.checker.add_check(self._username_check)
        self.checker.add_check(self._fullname_check)
        self.checker.add_check(self._empty_check)
        self.checker.add_check(self._confirm_check)
        self.checker.add_check(self._validity_check)
        self.checker.add_check(self._ascii_check)

        self.guesser = {
            self.username_entry: True
            }

        # Configure levels for the password bar
        self.password_bar.add_offset_value("low", 2)
        self.password_bar.add_offset_value("medium", 3)
        self.password_bar.add_offset_value("high", 4)

        # Modify the GUI based on the kickstart and policy information
        # This needs to happen after the input checks have been created, since
        # the Gtk signal handlers use the input check variables.
        password_set_message = _("The password was set by kickstart.")
        if self.password_kickstarted:
            self.password_required = True
            self.password_entry.set_placeholder_text(password_set_message)
            self.password_confirmation_entry.set_placeholder_text(password_set_message)
        elif not self.checker.policy.allow_empty:
            # Policy is that a non-empty password is required
            self.password_required = True

        if not self.checker.policy.allow_empty:
            # User isn't allowed to change whether password is required or not
            self.password_required_checkbox.set_sensitive(False)

        self._advanced_user_dialog = AdvancedUserDialog(self)
        self._advanced_user_dialog.initialize()

        # report that we are done
        self.initialize_done()

    @property
    def username_entry(self):
        return self._username_entry

    @property
    def username(self):
        return self.username_entry.get_text()

    @username.setter
    def username(self, new_username):
        self.username_entry.set_text(new_username)

    @property
    def fullname_entry(self):
        return self._fullname_entry

    @property
    def fullname(self):
        return self.fullname_entry.get_text()

    @fullname.setter
    def fullname(self, new_fullname):
        self.fullname_entry.set_text(new_fullname)

    @property
    def password_required_checkbox(self):
        return self._password_required_checkbox

    @property
    def password_required(self):
        return self.password_required_checkbox.get_active()

    @password_required.setter
    def password_required(self, value):
        self.password_required_checkbox.set_active(value)

    @property
    def user(self):
        """The user that is manipulated by the User spoke.

        This user is always the first one in the user list.

        :return: a UserData instance
        """
        return self._user_list[0]

    def refresh(self):
        # user data could have changed in the Users DBus module
        # since the last visit, so reload it from DBus
        #
        # In the case that the user list is empty or
        # a requested user has been cleared from the list in previous
        # spoke visit we need to have an empty user instance prepended
        # to the list.
        self._user_list = get_user_list(self._users_module, add_default=True, add_if_not_empty=self._requested_user_cleared)

        self.username = self.user.name
        self.fullname = self.user.gecos
        self._admin_checkbox.set_active(self.user.has_admin_priviledges())

        # rerun checks so that we have a correct status message, if any
        self.checker.run_checks()

    @property
    def status(self):
        user_list = get_user_list(self._users_module)
        if not user_list:
            return _("No user will be created")
        elif user_list[0].has_admin_priviledges():
            return _("Administrator %s will be created") % user_list[0].name
        else:
            return _("User %s will be created") % user_list[0].name

    @property
    def mandatory(self):
        """Only mandatory if no admin user has been requested."""
        return not self._users_module.CheckAdminUserExists()

    def apply(self):
        # set the password only if the user enters anything to the text entry
        # this should preserve the kickstart based password
        if self.password_required:
            if self.password:
                self.password_kickstarted = False
                self.user.password = crypt_password(self.password)
                self.user.is_crypted = True
                self.remove_placeholder_texts()

        # reset the password when the user unselects it
        else:
            self.remove_placeholder_texts()
            self.user.password = ""
            self.user.is_crypted = False
            self.password_kickstarted = False

        self.user.name = self.username
        self.user.gecos = self.fullname

        # We make it possible to clear users requested from kickstart (or DBus API)
        # during an interactive installation. This is done by setting their name
        # to "". Then during apply() we will check the user name and if it is
        # equal to "", we will remember that locally and not forward the user which
        # has been cleared to the DBus module, by using the remove_uset flag
        # for the set_user_list function.

        # record if the requested user has been explicitely unset
        self._requested_user_cleared = not self.user.name
        # clear the unset user (if any)
        set_user_list(self._users_module, self._user_list, remove_unset=True)

    @property
    def sensitive(self):
        # Spoke cannot be entered if a user was set in the kickstart and the user
        # policy doesn't allow changes.
        return not (self.completed and flags.automatedInstall
                    and self._user_requested and not conf.ui.can_change_users)

    @property
    def completed(self):
        return bool(get_user_list(self._users_module))

    def on_password_required_toggled(self, togglebutton=None, data=None):
        """Called by Gtk callback when the "Use password" check
        button is toggled. It will make password entries in/sensitive."""
        password_is_required = togglebutton.get_active()
        self.password_entry.set_sensitive(password_is_required)
        self.password_confirmation_entry.set_sensitive(password_is_required)
        self._password_is_required = password_is_required
        # also disable/enable corresponding password checks
        self._empty_check.skip = not password_is_required or not self.username
        self._confirm_check.skip = not password_is_required
        self._validity_check.skip = not password_is_required or not self.username
        self._ascii_check.skip = not password_is_required

        # and rerun the checks
        self.checker.run_checks()

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

    def on_username_set_by_user(self, editable, data=None):
        """Called by Gtk on user-driven changes to the username field.

           This handler is blocked during changes from the username guesser.
        """

        # If the user set a user name, turn off the username guesser.
        # If the user cleared the username, turn it back on.
        if editable.get_text():
            self.guesser = False
        else:
            self.guesser = True

    def on_username_changed(self, editable, data=None):
        """Called by Gtk on all username changes."""
        new_username = editable.get_text()

        # Disable the advanced user dialog button when no username is set
        if editable.get_text():
            self._advanced_button.set_sensitive(True)
        else:
            self._advanced_button.set_sensitive(False)

        # update the username in checker
        self.checker.username = new_username

        # Skip the empty password checks if no username is set,
        # otherwise the user will not be able to leave the
        # spoke if password is not set but policy requires that.
        self._empty_check.skip = not new_username or not self._password_is_required
        self._validity_check.skip = not new_username or not self._password_is_required
        # Re-run the password checks against the new username
        self.checker.run_checks()

    def on_full_name_changed(self, editable, data=None):
        """Called by Gtk callback when the full name field changes."""

        fullname = editable.get_text()
        if self.guesser:
            username = guess_username(fullname)
            with blockedHandler(self.username_entry, self.on_username_set_by_user):
                self.username = username

        self.checker.fullname = fullname

        # rerun the checks
        self.checker.run_checks()

    def on_admin_toggled(self, togglebutton, data=None):
        # Add or remove user admin status based on changes to the admin checkbox
        self.user.set_admin_priviledges(togglebutton.get_active())

    def on_advanced_clicked(self, _button, data=None):
        """Handler for the Advanced.. button. It starts the Advanced dialog
        for setting homedir, uid, gid and groups.
        """

        self.user.name = self.username

        self._advanced_user_dialog.refresh()
        with self.main_window.enlightbox(self._advanced_user_dialog.window):
            self._advanced_user_dialog.run()

        self._admin_checkbox.set_active(self.user.has_admin_priviledges())

    def _checks_done(self, error_message):
        """Update the warning with the input validation error from the first
           error message or clear warnings if all the checks were successful.

           Also appends the "press twice" suffix if compatible with current
           password policy and handles the press-done-twice logic.
        """

        # check if an unwaivable check failed
        unwaivable_checks = [not self._confirm_check.result.success,
                             not self._username_check.result.success,
                             not self._fullname_check.result.success,
                             not self._empty_check.result.success]

        # with allow_empty == False the empty password check become unwaivable
        # if not self.checker.policy.allow_empty:
        #   unwaivable_checks.append(not self._empty_check.result.success)
        unwaivable_check_failed = any(unwaivable_checks)

        # set appropriate status bar message
        if not error_message:
            # all is fine, just clear the message
            self.clear_info()
        elif not self.username and not self.password and not self.password_confirmation:
            # Clear any info message if username and both the password and password
            # confirmation fields are empty.
            # This shortcut is done to make it possible for the user to leave the spoke
            # without inputting any username or password. Separate logic makes sure an
            # empty string is not unexpectedly set as the user password.
            self.clear_info()
        elif not self.username and not self.password and not self.password_confirmation:
            # Also clear warnings if username is set but empty password is fine.
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
        """Check if the user can escape from the root spoke or stay forever !"""

        # reset any waiving in progress
        self.waive_clicks = 0

        # Depending on the policy we allow users to waive the password strength
        # and non-ASCII checks. If the policy is set to strict, the password
        # needs to be strong, but can still contain non-ASCII characters.
        self.can_go_back = False
        self.needs_waiver = True

        # This shortcut is done to make it possible for the user to leave the spoke
        # without inputting anything. Separate logic makes sure an
        # empty string is not unexpectedly set as the user password.
        if not self.username and not self.password and not self.password_confirmation:
            self.can_go_back = True
            self.needs_waiver = False
        elif self.checker.success:
            # if all checks were successful we can always go back to the hub
            self.can_go_back = True
            self.needs_waiver = False
        elif unwaivable_check_failed:
            self.can_go_back = False
        elif not self.password and not self.password_confirmation:
            self.can_go_back = True
            self.needs_waiver = False
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
                if not self._confirm_check.result.success:
                    self.can_go_back = False
                if not self._validity_check.result.success:
                    self.can_go_back = True
                    self.needs_waiver = True
                elif not self._ascii_check.result.success:
                    self.can_go_back = True
                    self.needs_waiver = True
                else:
                    self.can_go_back = True
                    self.needs_waiver = False

    def on_back_clicked(self, button):
        # the GUI spoke input check handler handles the spoke exit logic for us
        if self.try_to_go_back():
            NormalSpoke.on_back_clicked(self, button)
        else:
            log.info("Return to hub prevented by password checking rules.")
