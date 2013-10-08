# User creation spoke
#
# Copyright (C) 2013 Red Hat, Inc.
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
#

from pyanaconda.i18n import _, N_
from pyanaconda.users import cryptPassword, validatePassword, guess_username

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui import GUIObject, GUIDialog, check_re, GUICheck
from pyanaconda.ui.gui.categories.user_settings import UserSettingsCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.gui.utils import enlightbox

from pykickstart.constants import FIRSTBOOT_RECONFIG
from pyanaconda.constants import ANACONDA_ENVIRON, FIRSTBOOT_ENVIRON,\
        PASSWORD_EMPTY_ERROR, PASSWORD_CONFIRM_ERROR_GUI, PASSWORD_STRENGTH_DESC,\
        PASSWORD_WEAK, PASSWORD_WEAK_WITH_ERROR, PASSWORD_WEAK_CONFIRM,\
        PASSWORD_WEAK_CONFIRM_WITH_ERROR
from pyanaconda.regexes import GECOS_VALID, USERNAME_VALID, GROUPNAME_VALID, GROUPLIST_FANCY_PARSE

__all__ = ["UserSpoke", "AdvancedUserDialog"]

def _checkUsername(editable, data):
    """Validate a username. Allow empty usernames."""
    if not (editable.get_text()):
        return GUICheck.CHECK_OK
    else:
        return check_re(editable, data)

def _validateGroups(editable, data):
    groups_list = editable.get_text().split(",")

    # Check each group name in the list
    for group in groups_list:
        group_name = GROUPLIST_FANCY_PARSE.match(group).group('name')
        if not GROUPNAME_VALID.match(group_name):
            return _("Invalid group name: %s") % group_name

    return GUICheck.CHECK_OK

class AdvancedUserDialog(GUIDialog):
    builderObjects = ["advancedUserDialog", "uid", "gid"]
    mainWidgetName = "advancedUserDialog"
    uiFile = "spokes/advanced_user.glade"

    def __init__(self, user, groupDict, data):
        GUIDialog.__init__(self, data)
        self._user = user
        self._groupDict = groupDict

    def _grabObjects(self):
        self._cHome = self.builder.get_object("c_home")
        self._cUid = self.builder.get_object("c_uid")
        self._cGid = self.builder.get_object("c_gid")
        self._tHome = self.builder.get_object("t_home")
        self._lHome = self.builder.get_object("l_home")
        self._tGroups = self.builder.get_object("t_groups")
        self._spinUid = self.builder.get_object("spin_uid")
        self._spinGid = self.builder.get_object("spin_gid")
        self._uid = self.builder.get_object("uid")
        self._gid = self.builder.get_object("gid")
        self._groupsError = self.builder.get_object("groups_error")
        self._saveButton = self.builder.get_object("save_button")

    def initialize(self):
        GUIObject.initialize(self)

        self._grabObjects()

        # Validate the group input box
        self.add_check_with_error_label(editable=self._tGroups, 
                error_label=self._groupsError, 
                run_check=_validateGroups)

    def update_check(self, check, check_status):
        # If there are any errors, disable the save button
        self._saveButton.set_sensitive(not next(self.failed_checks, None))

        return GUIDialog.update_check(self, check, check_status)

    def _apply_checkboxes(self, _editable = None, data = None):
        """Update the state of this screen according to the
        checkbox states on the screen. It is called from
        the toggled Gtk event.
        """
        c_home = self._cHome.get_active()
        c_uid = self._cUid.get_active()
        c_gid = self._cGid.get_active()

        self._tHome.set_sensitive(c_home)
        self._lHome.set_sensitive(c_home)
        self._spinUid.set_sensitive(c_uid)
        self._spinGid.set_sensitive(c_gid)

    def _parse_groups(self):
        group_strings = self._tGroups.get_text().split(",")
        group_objects = []

        for group in group_strings:
            # Skip empty strings
            if not group:
                continue

            (group_name, group_id) = GROUPLIST_FANCY_PARSE.match(group).groups()
            if group_id:
                group_id = int(group_id)

            group_objects.append(self.data.GroupData(name=group_name, gid=group_id))

        return group_objects

    def refresh(self):
        if self._user.homedir:
            self._tHome.set_text(self._user.homedir)
        elif self._user.name:
            homedir = "/home/" + self._user.name
            self._tHome.set_text(homedir)
            self._user.homedir = homedir

        self._cHome.set_active(bool(self._user.homedir))
        self._cUid.set_active(bool(self._user.uid))
        self._cGid.set_active(bool(self._user.gid))
        self._apply_checkboxes()

        self._spinUid.update()
        self._spinGid.update()

        groups = []
        for group_name in self._user.groups:
            group = self._groupDict[group_name]

            if group.name and group.gid is not None:
                groups.append("%s (%d)" % (group.name, group.gid))
            elif group.name:
                groups.append(group.name)
            elif group.gid is not None:
                groups.append("(%d)" % (group.gid,))

        self._tGroups.set_text(", ".join(groups))

    def run(self):
        self.window.show()
        rc = self.window.run()
        self.window.hide()

        #OK clicked
        if rc == 1:
            if self._cHome.get_active():
                self._user.homedir = self._tHome.get_text()
            else:
                self._user.homedir = None

            if self._cUid.get_active():
                self._user.uid = int(self._uid.get_value())
            else:
                self._user.uid = None

            if self._cGid.get_active():
                self._user.gid = int(self._gid.get_value())
            else:
                self._user.gid = None

            groups = self._parse_groups()
            self._user.groups = []
            self._groupDict.clear()
            for group in groups:
                self._groupDict[group.name] = group
                self._user.groups.append(group.name)

        #Cancel clicked, window destroyed...
        else:
            pass

        return rc

class UserSpoke(FirstbootSpokeMixIn, NormalSpoke):
    builderObjects = ["userCreationWindow"]

    mainWidgetName = "userCreationWindow"
    uiFile = "spokes/user.glade"

    category = UserSettingsCategory

    icon = "avatar-default-symbolic"
    title = N_("_USER CREATION")

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
        elif environment == FIRSTBOOT_ENVIRON and data and \
                (data.firstboot.firstboot == FIRSTBOOT_RECONFIG or \
                     len(data.user.userList) == 0):
            return True
        else:
            return False

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        self._oldweak = None

    def initialize(self):
        NormalSpoke.initialize(self)

        if self.data.user.userList:
            self._user = self.data.user.userList[0]
        else:
            self._user = self.data.UserData()
        self._wheel = self.data.GroupData(name = "wheel")
        self._groupDict = {"wheel": self._wheel}

        # placeholders for the text boxes
        self.fullname = self.builder.get_object("t_fullname")
        self.username = self.builder.get_object("t_username")
        self.pw = self.builder.get_object("t_password")
        self.confirm = self.builder.get_object("t_verifypassword")
        self.admin = self.builder.get_object("c_admin")
        self.usepassword = self.builder.get_object("c_usepassword")
        self.b_advanced = self.builder.get_object("b_advanced")

        # Counter for the click Done twice check
        self._waivePasswordClicks = 0

        self.guesser = {
            self.username: True
            }

        # Updated during the password changed event and used by the password
        # field validity checker
        self._pwq_error = None
        self._pwq_valid = True

        self.pw_bar = self.builder.get_object("password_bar")
        self.pw_label = self.builder.get_object("password_label")

        # Configure levels for the password bar
        self.pw_bar.add_offset_value("low", 2)
        self.pw_bar.add_offset_value("medium", 3)
        self.pw_bar.add_offset_value("high", 4)

        # indicate when the password was set by kickstart
        self._user.password_kickstarted = self.data.user.seen
        if self._user.password_kickstarted:
            self.usepassword.set_active(self._user.password != "")
            if not self._user.isCrypted:
                self.pw.set_text(self._user.password)
                self.confirm.set_text(self._user.password)
            else:
                self.usepassword.set_active(True)
                self.pw.set_placeholder_text(_("The password was set by kickstart."))
                self.confirm.set_placeholder_text(_("The password was set by kickstart."))

        # Password checks, in order of importance:
        # - if a password is required, is one specified?
        # - if a password is specified and there is data in the confirm box, do they match?
        # - if a password is specified and the confirm box is empty or match, how strong is it?
        # - if a password is required, is there any data in the confirm box?
        self.add_check(self.pw, self._checkPasswordEmpty)
        
        # The password confirmation needs to be checked whenever either of the password
        # fields change. Separate checks are created on each field so that edits on
        # either will trigger a check and so that the last edited field will get the focus
        # when Done is clicked. Whichever check is run needs to run the other check in
        # order to reset the status. The check_data field is used as a flag to prevent
        # infinite recursion.
        self._confirm_check = self.add_check(self.confirm, self._checkPasswordConfirm)
        self._password_check = self.add_check(self.pw, self._checkPasswordConfirm)

        # Keep a reference to this check, since it has to be manually run for the
        # click Done twice check.
        self._pwStrengthCheck = self.add_check(self.pw, self._checkPasswordStrength)

        self.add_check(self.confirm, self._checkPasswordEmpty)

        # Allow empty usernames so the spoke can be exited without creating a user
        self.add_check(self.username, _checkUsername,
                {'regex': USERNAME_VALID, 'message': _("Invalid username")})

        self.add_re_check(self.fullname, GECOS_VALID, _("Full name cannot contain colon characters"))

        self._advanced = AdvancedUserDialog(self._user, self._groupDict,
                                            self.data)
        self._advanced.initialize()

    def refresh(self):
        # Enable the input checks in case they were disabled on the last exit
        for check in self.checks:
            check.enable()

        self.username.set_text(self._user.name)
        self.fullname.set_text(self._user.gecos)
        self.admin.set_active(self._wheel.name in self._user.groups)

        self.pw.emit("changed")
        self.confirm.emit("changed")

        if self.username.get_text() and self.usepassword.get_active() and \
           self._user.password == "":
            self.pw.grab_focus()
        elif self.fullname.get_text():
            self.username.grab_focus()
        else:
            self.fullname.grab_focus()

        self.b_advanced.set_sensitive(bool(self._user.name))

    @property
    def status(self):
        if len(self.data.user.userList) == 0:
            return _("No user will be created")
        elif self._wheel.name in self.data.user.userList[0].groups:
            return _("Administrator %s will be created") % self.data.user.userList[0].name
        else:
            return _("User %s will be created") % self.data.user.userList[0].name

    @property
    def mandatory(self):
        # mandatory only if root account is disabled
        return (not self.data.rootpw.password) or self.data.rootpw.lock

    def apply(self):
        # set the password only if the user enters anything to the text entry
        # this should preserve the kickstart based password
        if self.usepassword.get_active():
            if self.pw.get_text():
                self._user.password_kickstarted = False
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
            self._user.password_kickstarted = False

        self._user.name = self.username.get_text()
        self._user.gecos = self.fullname.get_text()

        # Remove any groups that were created in a previous visit to this spoke
        self.data.group.groupList = [g for g in self.data.group.groupList \
                if not hasattr(g, 'anaconda_group')]

        # the user will be created only if the username is set
        if self._user.name:
            if self.admin.get_active() and \
               self._wheel.name not in self._user.groups:
                self._user.groups.append(self._wheel.name)
            elif not self.admin.get_active() and \
                 self._wheel.name in self._user.groups:
                self._user.groups.remove(self._wheel.name)

            anaconda_groups = [self._groupDict[g] for g in self._user.groups
                                if g != self._wheel.name]

            self.data.group.groupList += anaconda_groups

            # Flag the groups as being created in this spoke
            for g in anaconda_groups:
                g.anaconda_group = True

            if self._user not in self.data.user.userList:
                self.data.user.userList.append(self._user)

        elif self._user in self.data.user.userList:
            self.data.user.userList.remove(self._user)

    @property
    def completed(self):
        return len(self.data.user.userList) > 0

    def _updatePwQuality(self):
        """This method updates the password indicators according
        to the password entered by the user.
        """
        pwtext = self.pw.get_text()
        username = self.username.get_text()

        # Reset the counter used for the "press Done twice" logic
        self._waivePasswordClicks = 0

        self._pwq_valid, strength, self._pwq_error = validatePassword(pwtext, username)

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

    def usepassword_toggled(self, togglebutton = None, data = None):
        """Called by Gtk callback when the "Use password" check
        button is toggled. It will make password entries in/sensitive."""

        self.pw.set_sensitive(self.usepassword.get_active())
        self.confirm.set_sensitive(self.usepassword.get_active())

        # Re-check the password
        self.pw.emit("changed")

    def password_changed(self, editable=None, data=None):
        """Update the password strength level bar"""
        self._updatePwQuality()

    def username_changed(self, editable = None, data = None):
        """Called by Gtk callback when the username or hostname
        entry changes. It disables the guess algorithm if the
        user added his own text there and reenable it when the
        user deletes the whole text."""

        if editable.get_text() == "":
            self.guesser[editable] = True
            self.b_advanced.set_sensitive(False)
        else:
            self.guesser[editable] = False
            self.b_advanced.set_sensitive(True)

            # Re-run the password checks against the new username
            self.pw.emit("changed")

    def full_name_changed(self, editable = None, data = None):
        """Called by Gtk callback when the full name field changes.
        It guesses the username and hostname, strips diacritics
        and make those lowercase.
        """

        # after the text is updated in guesser, the guess has to be reenabled
        if self.guesser[self.username]:
            fullname = self.fullname.get_text()
            username = guess_username(fullname)
            self.username.set_text(username)
            self.guesser[self.username] = True

    def _checkPasswordEmpty(self, editable, data):
        """Check whether a password has been specified at all.
        
           This check is used for both the password and the confirmation.
        """

        # If the password was set by kickstart, skip the strength check
        if self._user.password_kickstarted:
            return GUICheck.CHECK_OK

        # Skip the check if no password is required
        if (not self.usepassword.get_active()) or self._user.password_kickstarted:
            return GUICheck.CHECK_OK
        elif not editable.get_text():
            if editable == self.pw:
                return _(PASSWORD_EMPTY_ERROR)
            else:
                return _(PASSWORD_CONFIRM_ERROR_GUI)
        else:
            return GUICheck.CHECK_OK

    def _checkPasswordConfirm(self, editable=None, reset_status=None):
        """If the user has entered confirmation data, check whether it matches the password."""

        # This check is triggered by changes to either the password field or the
        # confirmation field. If this method is being run from a successful check
        # to reset the status, just return success
        if reset_status:
            return GUICheck.CHECK_OK
        
        # Skip the check if no password is required
        if (not self.usepassword.get_active()) or self._user.password_kickstarted:
            result = GUICheck.CHECK_OK
        elif self.confirm.get_text() and (self.pw.get_text() != self.confirm.get_text()):
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

    def _checkPasswordStrength(self, editable=None, data=None):
        """Update the error message based on password strength.
        
           The password strength has already been checked in _updatePwQuality, called
           previously in the signal chain. This method converts the data set from there
           into an error message.

           The password strength check can be waived by pressing "Done" twice. This
           is controlled through the self._waivePasswordClicks counter. The counter
           is set in on_back_clicked, which also re-runs this check manually.
         """

        # Skip the check if no password is required
        if (not self.usepassword.get_active()) or \
                ((not self.pw.get_text()) and (self._user.password_kickstarted)):
            return GUICheck.CHECK_OK

        # If the password failed the validity check, fail this check
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

    def on_advanced_clicked(self, _button, data=None):
        """Handler for the Advanced.. button. It starts the Advanced dialog
        for setting homedit, uid, gid and groups.
        """

        self._user.name = self.username.get_text()

        if self.admin.get_active() and \
           self._wheel.name not in self._user.groups:
            self._user.groups.append(self._wheel.name)
        elif not self.admin.get_active() and \
             self._wheel.name in self._user.groups:
            self._user.groups.remove(self._wheel.name)

        self._advanced.refresh()
        with enlightbox(self.window, self._advanced.window):
            self._advanced.run()

        self.admin.set_active(self._wheel.name in self._user.groups)

    def on_back_clicked(self, button):
        # Add a click and re-check the password strength
        self._waivePasswordClicks += 1
        self._pwStrengthCheck.update_check_status()

        # If there is no user set, skip the checks
        if not self.username.get_text():
            for check in self.checks:
                check.disable()
        NormalSpoke.on_back_clicked(self, button)

