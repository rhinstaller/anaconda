# User creation text spoke
#
# Copyright (C) 2013-2014  Red Hat, Inc.
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

from pykickstart.constants import FIRSTBOOT_RECONFIG

from pyanaconda.constants import ANACONDA_ENVIRON, FIRSTBOOT_ENVIRON, PASSWORD_SET
from pyanaconda.flags import flags
from pyanaconda.i18n import N_, _
from pyanaconda.regexes import GECOS_VALID
from pyanaconda.ui.categories.user_settings import UserSettingsCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.tuiobject import Dialog, PasswordDialog, report_if_failed, report_check_func
from pyanaconda.users import guess_username, check_username, check_grouplist

from simpleline.render.screen import InputState
from simpleline.render.containers import ListColumnContainer
from simpleline.render.widgets import CheckboxWidget, EntryWidget

__all__ = ["UserSpoke"]


FULLNAME_ERROR_MSG = N_("Full name can't contain the ':' character")


class UserSpoke(FirstbootSpokeMixIn, NormalTUISpoke):
    """
       .. inheritance-diagram:: UserSpoke
          :parts: 3
    """
    helpFile = "UserSpoke.txt"
    category = UserSettingsCategory

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
                (data.firstboot.firstboot == FIRSTBOOT_RECONFIG or
                 len(data.user.userList) == 0):
            return True
        else:
            return False

    def __init__(self, data, storage, payload, instclass):
        FirstbootSpokeMixIn.__init__(self)
        NormalTUISpoke.__init__(self, data, storage, payload, instclass)

        self.initialize_start()

        self.title = N_("User creation")
        self._container = None

        if self.data.user.userList:
            self._user_data = self.data.user.userList[0]
            self._create_user = True
        else:
            self._user_data = self.data.UserData()
            self._create_user = False

        self._use_password = self._user_data.isCrypted or self._user_data.password
        self._groups = ""
        self._is_admin = False
        self._policy = self.data.anaconda.pwpolicy.get_policy("user", fallback_to_default=True)

        self.errors = []

        self.initialize_done()

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)
        self._is_admin = "wheel" in self._user_data.groups
        self._groups = ", ".join(self._user_data.groups)

        self._container = ListColumnContainer(1)

        w = CheckboxWidget(title=_("Create user"), completed=self._create_user)
        self._container.add(w, self._set_create_user)

        if self._create_user:
            dialog = Dialog(title=_("Full name"), conditions=[self._check_fullname])
            self._container.add(EntryWidget(dialog.title, self._user_data.gecos), self._set_fullname, dialog)

            dialog = Dialog(title=_("User name"), conditions=[self._check_username])
            self._container.add(EntryWidget(dialog.title, self._user_data.name), self._set_username, dialog)

            w = CheckboxWidget(title=_("Use password"), completed=self._use_password)
            self._container.add(w, self._set_use_password)

            if self._use_password:
                password_dialog = PasswordDialog(title=_("Password"), policy=self._policy)
                if self._user_data.password:
                    entry = EntryWidget(password_dialog.title, _(PASSWORD_SET))
                else:
                    entry = EntryWidget(password_dialog.title)

                self._container.add(entry, self._set_password, password_dialog)

            msg = _("Administrator")
            w = CheckboxWidget(title=msg, completed=self._is_admin)
            self._container.add(w, self._set_administrator)

            dialog = Dialog(title=_("Groups"), conditions=[self._check_groups])
            self._container.add(EntryWidget(dialog.title, self._groups), self._set_groups, dialog)

        self.window.add_with_separator(self._container)

    @report_if_failed(message=FULLNAME_ERROR_MSG)
    def _check_fullname(self, user_input, report_func):
        return GECOS_VALID.match(user_input) is not None

    @report_check_func()
    def _check_username(self, user_input, report_func):
        return check_username(user_input)

    @report_check_func()
    def _check_groups(self, user_input, report_func):
        return check_grouplist(user_input)

    def _set_create_user(self, args):
        self._create_user = not self._create_user

    def _set_fullname(self, dialog):
        self._user_data.gecos = dialog.run()

    def _set_username(self, dialog):
        self._user_data.name = dialog.run()

    def _set_use_password(self, args):
        self._use_password = not self._use_password

    def _set_password(self, password_dialog):
        password = password_dialog.run()

        while password is None:
            password = password_dialog.run()

        self._user_data.password = password

    def _set_administrator(self, args):
        self._is_admin = not self._is_admin

    def _set_groups(self, dialog):
        self._groups = dialog.run()

    def show_all(self):
        NormalTUISpoke.show_all(self)
        # if we have any errors, display them
        while self.errors:
            print(self.errors.pop())

    @property
    def completed(self):
        """ Verify a user is created; verify pw is set if option checked. """
        if len(self.data.user.userList) > 0:
            if self._use_password and not bool(self._user_data.password or self._user_data.isCrypted):
                return False
            else:
                return True
        else:
            return False

    @property
    def showable(self):
        return not (self.completed and flags.automatedInstall
                    and self.data.user.seen and not self._policy.changesok)

    @property
    def mandatory(self):
        """ Only mandatory if the root pw hasn't been set in the UI
            eg. not mandatory if the root account was locked in a kickstart
        """
        return not self.data.rootpw.password and not self.data.rootpw.lock

    @property
    def status(self):
        if len(self.data.user.userList) == 0:
            return _("No user will be created")
        elif self._use_password and not bool(self._user_data.password or self._user_data.isCrypted):
            return _("You must set a password")
        elif "wheel" in self.data.user.userList[0].groups:
            return _("Administrator %s will be created") % self.data.user.userList[0].name
        else:
            return _("User %s will be created") % self.data.user.userList[0].name

    def input(self, args, key):
        if self._container.process_user_input(key):
            self.apply()
            self.redraw()
            return InputState.PROCESSED

        return super(UserSpoke, self).input(args, key)

    def apply(self):
        if self._user_data.gecos and not self._user_data.name:
            username = guess_username(self._user_data.gecos)
            valid, msg = check_username(username)
            if not valid:
                self.errors.append(_("Invalid user name: %(name)s.\n%(error_message)s")
                                   % {"name": username, "error_message": msg})
            else:
                self._user_data.name = guess_username(self._user_data.gecos)

        self._user_data.groups = [g.strip() for g in self._groups.split(",") if g]

        # Add or remove the user from wheel group
        if self._is_admin and "wheel" not in self._user_data.groups:
            self._user_data.groups.append("wheel")
        elif not self._is_admin and "wheel" in self._user_data.groups:
            self._user_data.groups.remove("wheel")

        # Add or remove the user from userlist as needed
        if self._create_user and (self._user_data not in self.data.user.userList and self._user_data.name):
            self.data.user.userList.append(self._user_data)
        elif (not self._create_user) and (self._user_data in self.data.user.userList):
            self.data.user.userList.remove(self._user_data)

        # encrypt and store password only if user entered anything; this should
        # preserve passwords set via kickstart
        if self._use_password and self._user_data.password and len(self._user_data.password) > 0:
            self._user_data.password = self._user_data.password
            self._user_data.isCrypted = True
            self._user_data.password_kickstarted = False
        # clear pw when user unselects to use pw
        else:
            self._user_data.password = ""
            self._user_data.isCrypted = False
            self._user_data.password_kickstarted = False
