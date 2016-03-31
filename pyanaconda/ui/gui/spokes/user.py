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
# Red Hat Author(s): Martin Sivak <msivak@redhat.com>
#                    Chris Lumens <clumens@redhat.com>
#

import re
import os
import copy
from pyanaconda.flags import flags
from pyanaconda.i18n import _, CN_
from pyanaconda.users import cryptPassword, validatePassword, guess_username

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.categories.user_settings import UserSettingsCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.helpers import InputCheck
from pyanaconda.ui.gui.helpers import GUISpokeInputCheckHandler, GUIDialogInputCheckHandler
from pyanaconda.ui.gui.utils import blockedHandler

from pyanaconda.constants import ANACONDA_ENVIRON, FIRSTBOOT_ENVIRON,\
        PASSWORD_EMPTY_ERROR, PASSWORD_CONFIRM_ERROR_GUI, PASSWORD_STRENGTH_DESC,\
        PASSWORD_WEAK, PASSWORD_WEAK_WITH_ERROR, PASSWORD_WEAK_CONFIRM,\
        PASSWORD_WEAK_CONFIRM_WITH_ERROR, PASSWORD_DONE_TWICE,\
        PW_ASCII_CHARS, PASSWORD_ASCII
from pyanaconda.regexes import GECOS_VALID, USERNAME_VALID, GROUPNAME_VALID, GROUPLIST_FANCY_PARSE

__all__ = ["UserSpoke", "AdvancedUserDialog"]

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
            if not GROUPNAME_VALID.match(group_name):
                return _("Invalid group name: %s") % group_name

        return InputCheck.CHECK_OK

    def __init__(self, user, data):
        GUIObject.__init__(self, data)

        saveButton = self.builder.get_object("save_button")
        GUIDialogInputCheckHandler.__init__(self, saveButton)

        self._user = user

        # Track whether the user has requested a home directory other
        # than the default. This way, if the home directory is left as
        # the default, the default will change if the username changes.
        # Otherwise, once the directory is set it stays that way.
        self._origHome = None

        if self._user.homedir:
            self._homeSet = True
        else:
            self._homeSet = False

    def _grabObjects(self):
        self._cUid = self.builder.get_object("c_uid")
        self._cGid = self.builder.get_object("c_gid")
        self._tHome = self.builder.get_object("t_home")
        self._lHome = self.builder.get_object("l_home")
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

    def refresh(self):
        if self._user.homedir:
            homedir = self._user.homedir
        elif self._user.name:
            homedir = "/home/" + self._user.name

        self._tHome.set_text(homedir)
        self._origHome = homedir

        self._cUid.set_active(bool(self._user.uid))
        self._cGid.set_active(bool(self._user.gid))

        self._spinUid.update()
        self._spinGid.update()

        self._tGroups.set_text(", ".join(self._user.groups))

    def apply(self):
        # Copy data from the UI back to the kickstart object
        homedir = self._tHome.get_text()

        # If the user cleared the home directory, revert back to the
        # default
        if not homedir:
            self._homeSet = False
            self._user.homedir = None
        # If the user modified the home directory input, save that the
        # home directory has been modified and use the value.
        elif self._origHome != homedir:
            self._homeSet = True

            if not os.path.isabs(homedir):
                homedir = "/" + homedir
            self._user.homedir = homedir

        # Otherwise leave the home directory alone. If the home
        # directory is currently the default value, the next call
        # to refresh() will update the input text to reflect
        # changes in the username.

        if self._cUid.get_active():
            self._user.uid = int(self._uid.get_value())
        else:
            self._user.uid = None

        if self._cGid.get_active():
            self._user.gid = int(self._gid.get_value())
        else:
            self._user.gid = None

        # ''.split(',') returns [''] instead of [], which is not what we want
        self._user.groups = [g.strip() for g in self._tGroups.get_text().split(",") if g]

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
    focusWidgetName = "t_fullname"
    uiFile = "spokes/user.glade"
    helpFile = "UserSpoke.xml"

    category = UserSettingsCategory

    icon = "avatar-default-symbolic"
    title = CN_("GUI|Spoke", "_USER CREATION")

    @classmethod
    def should_run(cls, environment, data):
        # the user spoke should run always in the anaconda and in firstboot only
        # when doing reconfig or if no user has been created in the installation
        if environment == ANACONDA_ENVIRON:
            return True
        elif environment == FIRSTBOOT_ENVIRON and data is None:
            # cannot decide, stay in the game and let another call with data
            # available (will come) decide
            return True
        elif environment == FIRSTBOOT_ENVIRON and data and len(data.user.userList) == 0:
            return True
        else:
            return False

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        GUISpokeInputCheckHandler.__init__(self)

    def initialize(self):
        NormalSpoke.initialize(self)

        # Create a new UserData object to store this spoke's state
        # as well as the state of the advanced user dialog.
        if self.data.user.userList:
            self._user = copy.copy(self.data.user.userList[0])
        else:
            self._user = self.data.UserData()

        # placeholders for the text boxes
        self.fullname = self.builder.get_object("t_fullname")
        self.username = self.builder.get_object("t_username")
        self.pw = self.builder.get_object("t_password")
        self.confirm = self.builder.get_object("t_verifypassword")
        self.admin = self.builder.get_object("c_admin")
        self.usepassword = self.builder.get_object("c_usepassword")
        self.b_advanced = self.builder.get_object("b_advanced")

        # Counters for checks that ask the user to click Done to confirm
        self._waiveStrengthClicks = 0
        self._waiveASCIIClicks = 0

        self.guesser = True

        self.pw_bar = self.builder.get_object("password_bar")
        self.pw_label = self.builder.get_object("password_label")

        # Configure levels for the password bar
        self.pw_bar.add_offset_value("low", 2)
        self.pw_bar.add_offset_value("medium", 3)
        self.pw_bar.add_offset_value("high", 4)
        self.pw_bar.add_offset_value("full", 4)

        # Configure the password policy, if available. Otherwise use defaults.
        self.policy = self.data.anaconda.pwpolicy.get_policy("user")
        if not self.policy:
            self.policy = self.data.anaconda.PwPolicyData()

        # indicate when the password was set by kickstart
        self._password_kickstarted = self.data.user.seen

        # Password checks, in order of importance:
        # - if a password is required, is one specified?
        # - if a password is specified and there is data in the confirm box, do they match?
        # - if a password is specified and the confirm box is empty or match, how strong is it?
        # - if a strong password is specified, does it contain non-ASCII data?
        # - if a password is required, is there any data in the confirm box?
        self.add_check(self.pw, self._checkPasswordEmpty)

        # the password confirmation needs to be checked whenever either of the password
        # fields change. attach to the confirm field so that errors focus on confirm,
        # and check changes to the password field in password_changed
        self._confirm_check = self.add_check(self.confirm, self._checkPasswordConfirm)

        # Keep a reference to these checks, since they have to be manually run for the
        # click Done twice check.
        self._pwStrengthCheck = self.add_check(self.pw, self._checkPasswordStrength)
        self._pwASCIICheck = self.add_check(self.pw, self._checkPasswordASCII)

        self.add_check(self.confirm, self._checkPasswordEmpty)

        # Allow empty usernames so the spoke can be exited without creating a user
        self.add_re_check(self.username, re.compile(USERNAME_VALID.pattern + r'|^$'),
                _("Invalid user name"))

        self.add_re_check(self.fullname, GECOS_VALID, _("Full name cannot contain colon characters"))

        # Modify the GUI based on the kickstart and policy information
        # This needs to happen after the input checks have been created, since
        # the Gtk signal handlers use the input check variables.
        if self._password_kickstarted:
            self.usepassword.set_active(True)
            self.pw.set_placeholder_text(_("The password was set by kickstart."))
            self.confirm.set_placeholder_text(_("The password was set by kickstart."))
        elif not self.policy.emptyok:
            # Policy is that a non-empty password is required
            self.usepassword.set_active(True)

        if not self.policy.emptyok:
            # User isn't allowed to change whether password is required or not
            self.usepassword.set_sensitive(False)

        self._advanced = AdvancedUserDialog(self._user, self.data)
        self._advanced.initialize()

    def refresh(self):
        # Enable the input checks in case they were disabled on the last exit
        for check in self.checks:
            check.enabled = True

        self.username.set_text(self._user.name)
        self.fullname.set_text(self._user.gecos)
        self.admin.set_active("wheel" in self._user.groups)

        self.pw.emit("changed")
        self.confirm.emit("changed")

    @property
    def status(self):
        if len(self.data.user.userList) == 0:
            return _("No user will be created")
        elif "wheel" in self.data.user.userList[0].groups:
            return _("Administrator %s will be created") % self.data.user.userList[0].name
        else:
            return _("User %s will be created") % self.data.user.userList[0].name

    @property
    def mandatory(self):
        """ Only mandatory if the root pw hasn't been set in the UI
            eg. not mandatory if the root account was locked in a kickstart
        """
        return not self.data.rootpw.password and not self.data.rootpw.lock

    def apply(self):
        # set the password only if the user enters anything to the text entry
        # this should preserve the kickstart based password
        if self.usepassword.get_active():
            if self.pw.get_text():
                self._password_kickstarted = False
                self._user.password = cryptPassword(self.pw.get_text())
                self._user.isCrypted = True
                self.pw.set_placeholder_text("")
                self.confirm.set_placeholder_text("")

        # reset the password when the user unselects it
        else:
            self.pw.set_placeholder_text("")
            self.confirm.set_placeholder_text("")
            self._user.password = ""
            self._user.isCrypted = False
            self._password_kickstarted = False

        self._user.name = self.username.get_text()
        self._user.gecos = self.fullname.get_text()

        # Copy the spoke data back to kickstart
        # If the user name is not set, no user will be created.
        if self._user.name:
            ksuser = copy.copy(self._user)

            if not self.data.user.userList:
                self.data.user.userList.append(ksuser)
            else:
                self.data.user.userList[0] = ksuser
        elif self.data.user.userList:
            self.data.user.userList.pop(0)

    @property
    def sensitive(self):
        # Spoke cannot be entered if a user was set in the kickstart and the user
        # policy doesn't allow changes.
        return not (self.completed and flags.automatedInstall
                    and self.data.user.seen and not self.policy.changesok)

    @property
    def completed(self):
        return len(self.data.user.userList) > 0

    def _updatePwQuality(self, empty, strength):
        """This method updates the password indicators according
        to the password entered by the user.
        """
        # If the password is empty, clear the strength bar
        if empty:
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

    def usepassword_toggled(self, togglebutton=None, data=None):
        """Called by Gtk callback when the "Use password" check
        button is toggled. It will make password entries in/sensitive."""

        self.pw.set_sensitive(togglebutton.get_active())
        self.confirm.set_sensitive(togglebutton.get_active())

        # Re-check the password
        self.pw.emit("changed")
        self.confirm.emit("changed")

    def password_changed(self, editable=None, data=None):
        """Update the password strength level bar"""
        # Reset the counters used for the "press Done twice" logic
        self._waiveStrengthClicks = 0
        self._waiveASCIIClicks = 0

        # Update the password/confirm match check on changes to the main password field
        self._confirm_check.update_check_status()

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

    def username_changed(self, editable, data=None):
        """Called by Gtk on all username changes."""

        # Disable the advanced user dialog button when no username is set
        if editable.get_text():
            self.b_advanced.set_sensitive(True)
        else:
            self.b_advanced.set_sensitive(False)

        # Re-run the password checks against the new username
        self.pw.emit("changed")
        self.confirm.emit("changed")

    def full_name_changed(self, editable, data=None):
        """Called by Gtk callback when the full name field changes."""

        if self.guesser:
            fullname = editable.get_text()
            username = guess_username(fullname)

            with blockedHandler(self.username, self.on_username_set_by_user):
                self.username.set_text(username)

    def on_admin_toggled(self, togglebutton, data=None):
        # Add or remove "wheel" from the grouplist on changes to the admin checkbox
        if togglebutton.get_active():
            if "wheel" not in self._user.groups:
                self._user.groups.append("wheel")
        elif "wheel" in self._user.groups:
            self._user.groups.remove("wheel")

    def _checkPasswordEmpty(self, inputcheck):
        """Check whether a password has been specified at all.

           This check is used for both the password and the confirmation.
        """

        # If the password was set by kickstart, skip the strength check
        if self._password_kickstarted and not self.policy.changesok:
            return InputCheck.CHECK_OK

        # Skip the check if no password is required
        if (not self.usepassword.get_active()) or self._password_kickstarted:
            return InputCheck.CHECK_OK
        elif not self.get_input(inputcheck.input_obj):
            if inputcheck.input_obj == self.pw:
                return _(PASSWORD_EMPTY_ERROR)
            else:
                return _(PASSWORD_CONFIRM_ERROR_GUI)
        else:
            return InputCheck.CHECK_OK

    def _checkPasswordConfirm(self, inputcheck):
        """If the user has entered confirmation data, check whether it matches the password."""

        # Skip the check if no password is required
        if (not self.usepassword.get_active()) or self._password_kickstarted:
            result = InputCheck.CHECK_OK
        elif self.confirm.get_text() and (self.pw.get_text() != self.confirm.get_text()):
            result = _(PASSWORD_CONFIRM_ERROR_GUI)
        else:
            result = InputCheck.CHECK_OK

        return result

    def _checkPasswordStrength(self, inputcheck):
        """Update the error message based on password strength.

           The password strength check can be waived by pressing "Done" twice. This
           is controlled through the self._waiveStrengthClicks counter. The counter
           is set in on_back_clicked, which also re-runs this check manually.
         """

        # Skip the check if no password is required
        if not self.usepassword.get_active or self._password_kickstarted:
            return InputCheck.CHECK_OK

        # If the password is empty, clear the strength bar and skip this check
        pw = self.pw.get_text()
        if not pw:
            self._updatePwQuality(True, 0)
            return InputCheck.CHECK_OK

        # determine the password strength
        username = self.username.get_text()
        valid, pwstrength, error = validatePassword(pw, username, minlen=self.policy.minlen)

        # set the strength bar
        self._updatePwQuality(False, pwstrength)

        # If the password failed the validity check, fail this check
        if not valid and error:
            return error

        if pwstrength < self.policy.minquality:
            # If Done has been clicked twice, waive the check
            if self._waiveStrengthClicks > 1:
                return InputCheck.CHECK_OK
            elif self._waiveStrengthClicks == 1:
                if error:
                    return _(PASSWORD_WEAK_CONFIRM_WITH_ERROR) % error
                else:
                    return _(PASSWORD_WEAK_CONFIRM)
            else:
                # non-strict allows done to be clicked twice
                if self.policy.strict:
                    done_msg = ""
                else:
                    done_msg = _(PASSWORD_DONE_TWICE)

                if error:
                    return _(PASSWORD_WEAK_WITH_ERROR) % error + " " + done_msg
                else:
                    return _(PASSWORD_WEAK) % done_msg
        else:
            return InputCheck.CHECK_OK

    def _checkPasswordASCII(self, inputcheck):
        """Set an error message if the password contains non-ASCII characters.

           Like the password strength check, this check can be bypassed by
           pressing Done twice.
        """

        # If Done has been clicked, waive the check
        if self._waiveASCIIClicks > 0:
            return InputCheck.CHECK_OK

        password = self.get_input(inputcheck.input_obj)
        if password and any(char not in PW_ASCII_CHARS for char in password):
            return _(PASSWORD_ASCII)

        return InputCheck.CHECK_OK

    def on_advanced_clicked(self, _button, data=None):
        """Handler for the Advanced.. button. It starts the Advanced dialog
        for setting homedit, uid, gid and groups.
        """

        self._user.name = self.username.get_text()

        self._advanced.refresh()
        with self.main_window.enlightbox(self._advanced.window):
            self._advanced.run()

        self.admin.set_active("wheel" in self._user.groups)

    def on_back_clicked(self, button):
        # If the failed check is for non-ASCII characters,
        # add a click to the counter and check again
        failed_check = next(self.failed_checks_with_message, None)
        if not self.policy.strict and failed_check == self._pwStrengthCheck:
            self._waiveStrengthClicks += 1
            self._pwStrengthCheck.update_check_status()
        elif failed_check == self._pwASCIICheck:
            self._waiveASCIIClicks += 1
            self._pwASCIICheck.update_check_status()

        # If there is no user set, skip the checks
        if not self.username.get_text():
            for check in self.checks:
                check.enabled = False

        if GUISpokeInputCheckHandler.on_back_clicked(self, button):
            NormalSpoke.on_back_clicked(self, button)
