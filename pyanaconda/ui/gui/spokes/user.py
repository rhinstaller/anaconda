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

from gi.repository import Gtk

from pyanaconda.flags import flags
from pyanaconda.i18n import _, N_
from pyanaconda.users import cryptPassword, validatePassword, guess_username, USERNAME_VALID
from pwquality import PWQError

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.categories.user_settings import UserSettingsCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.gui.utils import enlightbox

from pykickstart.constants import FIRSTBOOT_RECONFIG
from pyanaconda.constants import ANACONDA_ENVIRON, FIRSTBOOT_ENVIRON

import pwquality

__all__ = ["UserSpoke", "AdvancedUserDialog"]

class AdvancedUserDialog(GUIObject):
    builderObjects = ["advancedUserDialog", "uid", "gid"]
    mainWidgetName = "advancedUserDialog"
    uiFile = "spokes/advanced_user.glade"

    def __init__(self, user, groupDict, data):
        GUIObject.__init__(self, data)
        self._user = user
        self._groupDict = groupDict

    def initialize(self):
        GUIObject.initialize(self)

    def _apply_checkboxes(self, _editable = None, data = None):
        """Update the state of this screen according to the
        checkbox states on the screen. It is called from
        the toggled Gtk event.
        """
        c_home = self.builder.get_object("c_home").get_active()
        c_uid = self.builder.get_object("c_uid").get_active()
        c_gid = self.builder.get_object("c_gid").get_active()

        self.builder.get_object("t_home").set_sensitive(c_home)
        self.builder.get_object("l_home").set_sensitive(c_home)
        self.builder.get_object("spin_uid").set_sensitive(c_uid)
        self.builder.get_object("spin_gid").set_sensitive(c_gid)

    def refresh(self):
        t_home = self.builder.get_object("t_home")
        if self._user.homedir:
            t_home.set_text(self._user.homedir)
        elif self._user.name:
            homedir = "/home/" + self._user.name
            t_home.set_text(homedir)
            self._user.homedir = homedir

        c_home = self.builder.get_object("c_home")
        c_home.set_active(bool(self._user.homedir))
        c_uid = self.builder.get_object("c_uid")
        c_uid.set_active(bool(self._user.uid))
        c_gid = self.builder.get_object("c_gid")
        c_gid.set_active(bool(self._user.gid))
        self._apply_checkboxes()

        self.builder.get_object("spin_uid").update()
        self.builder.get_object("spin_gid").update()

        groups = []
        for group_name in self._user.groups:
            group = self._groupDict[group_name]

            if group.name and group.gid is not None:
                groups.append("%s (%d)" % (group.name, group.gid))
            elif group.name:
                groups.append(group.name)
            elif group.gid is not None:
                groups.append("(%d)" % (group.gid,))

        self.builder.get_object("t_groups").set_text(", ".join(groups))

    def run(self):
        self.window.show()
        rc = self.window.run()
        self.window.hide()

        #OK clicked
        if rc == 1:
            if self.builder.get_object("c_home").get_active():
                self._user.homedir = self.builder.get_object("t_home").get_text()
            else:
                self._user.homedir = None

            if self.builder.get_object("c_uid").get_active():
                self._user.uid = int(self.builder.get_object("uid").get_value())
            else:
                self._user.uid = None

            if self.builder.get_object("c_gid").get_active():
                self._user.gid = int(self.builder.get_object("gid").get_value())
            else:
                self._user.gid = None

            groups = self.builder.get_object("t_groups").get_text().split(",")
            self._user.groups = []
            for group in groups:
                group = group.strip()
                if group not in self._groupDict:
                    self._groupDict[group] = self.data.GroupData(name = group)
                self._user.groups.append(group)

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
        self._error = False

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

        self.guesser = {
            self.username: True
            }

        # set up passphrase quality checker
        self._pwq = pwquality.PWQSettings()
        self._pwq.read_config()

        self.pw_bar = self.builder.get_object("password_bar")
        self.pw_label = self.builder.get_object("password_label")

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

        self._advanced = AdvancedUserDialog(self._user, self._groupDict,
                                            self.data)
        self._advanced.initialize()

    def refresh(self):
        self.username.set_text(self._user.name)
        self.fullname.set_text(self._user.gecos)
        self.admin.set_active(self._wheel.name in self._user.groups)

        if self.usepassword.get_active():
            self._checkPassword()

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
        if self._error:
            return _("Error creating user account: %s") % self._error
        elif len(self.data.user.userList) == 0:
            return _("No user will be created")
        elif self._wheel.name in self.data.user.userList[0].groups:
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

        # the user will be created only if the username is set
        if self._user.name:
            if self.admin.get_active() and \
               self._wheel.name not in self._user.groups:
                self._user.groups.append(self._wheel.name)
            elif not self.admin.get_active() and \
                 self._wheel.name in self._user.groups:
                self._user.groups.remove(self._wheel.name)

            self.data.group.groupList += (self._groupDict[g] for g in self._user.groups
                                                             if g != self._wheel.name)

            if self._user not in self.data.user.userList:
                self.data.user.userList.append(self._user)

        elif self._user in self.data.user.userList:
            self.data.user.userList.remove(self._user)

    @property
    def sensitive(self):
        return not (self.completed and flags.automatedInstall)

    @property
    def completed(self):
        return len(self.data.user.userList) > 0

    def _passwordDisabler(self, editable = None, data = None):
        """Called by Gtk callback when the "Use password" check
        button is toggled. It will make password entries in/sensitive."""

        self.pw.set_sensitive(self.usepassword.get_active())
        self.confirm.set_sensitive(self.usepassword.get_active())
        if not self.usepassword.get_active():
            self.clear_info()
        else:
            self._checkPassword()

    def _guessNameDisabler(self, editable = None, data = None):
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

    def _guessNames(self, editable = None, data = None):
        """Called by Gtk callback when the full name field changes.
        It guesses the username and hostname, strips diacritics
        and make those lowercase.
        """
        fullname = self.fullname.get_text()
        username = guess_username(fullname)

        # after the text is updated in guesser, the guess has to be reenabled
        if self.guesser[self.username]:
            self.username.set_text(username)
            self.guesser[self.username] = True

    def _checkPassword(self, editable = None, data = None):
        """This method updates the password indicators according
        to the passwords entered by the user. It is called by
        the changed Gtk event handler.
        """

        # If the password was set by kickstart, skip the strength check
        if self._user.password_kickstarted:
            return True

        try:
            strength = self._pwq.check(self.pw.get_text(), None, None)
            _pwq_error = None
        except pwquality.PWQError as (e, msg):
            _pwq_error = msg
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
        """This method checks the password weakness and
        implements the Press Done twice logic. It is used from
        the on_back_clicked handler.

        It also sets the self._error of the password is not
        sufficient or does not pass the pwquality checks.

        :return: True if the password should be accepted, False otherwise
        :rtype: bool

        """

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
        except PWQError as (_e, msg):
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

    def on_advanced_clicked(self, _button):
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
            response = self._advanced.run()

        self.admin.set_active(self._wheel.name in self._user.groups)

    def on_back_clicked(self, button):
        username = self.username.get_text()
        # if an invalid username was given, that's the biggest issue
        if username and not USERNAME_VALID.match(username):
            self.clear_info()
            self.set_warning(_("Invalid username"))
            self.username.grab_focus()
            self.window.show_all()
        # Return if:
        # - no user is requested (empty username)
        # - no password is required
        # - password is set by kickstart and password text entry is empty
        # - password is set by dialog and _validatePassword returns True
        elif not username or \
           not self.usepassword.get_active() or \
           (self.pw.get_text() == "" and \
            self.pw.get_text() == self.confirm.get_text() and \
            self._user.password_kickstarted) or \
           self._validatePassword():
            self._error = False
            self.clear_info()
            NormalSpoke.on_back_clicked(self, button)
        # Show the confirmation message if the password is not acceptable
        else:
            self.clear_info()
            self.set_warning(self._error)
            self.pw.grab_focus()
            self.window.show_all()

