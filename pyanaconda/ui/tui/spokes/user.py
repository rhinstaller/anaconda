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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from simpleline.render.containers import ListColumnContainer
from simpleline.render.screen import InputState
from simpleline.render.widgets import CheckboxWidget, EntryWidget

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    FIRSTBOOT_ENVIRON,
    PASSWORD_POLICY_USER,
    PASSWORD_SET,
)
from pyanaconda.core.i18n import N_, _
from pyanaconda.core.regexes import GECOS_VALID
from pyanaconda.core.users import check_grouplist, check_username, guess_username
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.services import USERS
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.ui.categories.user_settings import UserSettingsCategory
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.ui.lib.users import get_user_list, set_user_list
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.tuiobject import (
    Dialog,
    PasswordDialog,
    report_check_func,
    report_if_failed,
)

__all__ = ["UserSpoke"]


FULLNAME_ERROR_MSG = N_("Full name can't contain the ':' character")


class UserSpoke(FirstbootSpokeMixIn, NormalTUISpoke):
    """
       .. inheritance-diagram:: UserSpoke
          :parts: 3
    """
    category = UserSettingsCategory

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "user-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Should the spoke run?"""
        if not is_module_available(USERS):
            return False

        if FirstbootSpokeMixIn.should_run(environment, data):
            return True

        # the user spoke should run always in the anaconda and in firstboot only
        # when doing reconfig or if no user has been created in the installation
        users_module = USERS.get_proxy()
        user_list = get_user_list(users_module)
        if environment == FIRSTBOOT_ENVIRON and data and not user_list:
            return True

        return False

    def __init__(self, data, storage, payload):
        FirstbootSpokeMixIn.__init__(self)
        NormalTUISpoke.__init__(self, data, storage, payload)

        self.initialize_start()

        # connect to the Users DBus module
        self._users_module = USERS.get_proxy()

        self.title = N_("User creation")
        self._container = None

        # was user creation requested by the Users DBus module
        # - at the moment this basically means user creation was
        #   requested via kickstart
        # - note that this does not currently update when user
        #   list is changed via DBus
        self._user_requested = False
        self._user_cleared = False

        # should a user be created ?
        self._create_user = False

        self._user_list = get_user_list(self._users_module, add_default=True)
        # if user has a name, it's an actual user that has been requested,
        # rather than a default user added by us
        if self.user.name:
            self._user_requested = True
            self._create_user = True

        self._use_password = self.user.is_crypted or self.user.password
        self._groups = ""
        self._is_admin = False
        self.errors = []

        self._users_module = USERS.get_proxy()

        self.initialize_done()

    @property
    def user(self):
        """The user that is manipulated by the User spoke.

        This user is always the first one in the user list.

        :return: a UserData instance
        """
        return self._user_list[0]

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        # refresh the user list
        self._user_list = get_user_list(self._users_module, add_default=True, add_if_not_empty=self._user_cleared)

        self._is_admin = self.user.has_admin_priviledges()
        self._groups = ", ".join(self.user.groups)

        self._container = ListColumnContainer(1)

        w = CheckboxWidget(title=_("Create user"), completed=self._create_user)
        self._container.add(w, self._set_create_user)

        if self._create_user:
            dialog = Dialog(title=_("Full name"), conditions=[self._check_fullname])
            self._container.add(EntryWidget(dialog.title, self.user.gecos), self._set_fullname, dialog)

            dialog = Dialog(title=_("User name"), conditions=[self._check_username])
            self._container.add(EntryWidget(dialog.title, self.user.name), self._set_username, dialog)

            w = CheckboxWidget(title=_("Use password"), completed=self._use_password)
            self._container.add(w, self._set_use_password)

            if self._use_password:
                password_dialog = PasswordDialog(
                    title=_("Password"),
                    policy_name=PASSWORD_POLICY_USER
                )
                password_dialog.username = self.user.name
                if self.user.password:
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
        self.user.gecos = dialog.run()

    def _set_username(self, dialog):
        self.user.name = dialog.run()

    def _set_use_password(self, args):
        self._use_password = not self._use_password

    def _set_password(self, password_dialog):
        password = password_dialog.run()

        while password is None:
            password = password_dialog.run()

        self.user.password = password

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
        user_list = get_user_list(self._users_module)
        if user_list:
            if self._use_password and not bool(self.user.password or self.user.is_crypted):
                return False
            else:
                return True
        else:
            return False

    @property
    def showable(self):
        return not (self.completed and flags.automatedInstall
                    and self._user_requested and not conf.ui.can_change_users)

    @property
    def mandatory(self):
        """The spoke is mandatory only if some input is missing.

        Possible reasons to be mandatory:
        - No admin user has been created
        - Password has been requested but not entered
        """
        return (not self._users_module.CheckAdminUserExists() or
                (self._use_password and not bool(self.user.password or
                                                 self.user.is_crypted)))

    @property
    def status(self):
        user_list = get_user_list(self._users_module)
        if not user_list:
            return _("No user will be created")
        elif self._use_password and not bool(self.user.password or self.user.is_crypted):
            return _("You must set a password")
        elif user_list[0].has_admin_priviledges():
            return _("Administrator %s will be created") % user_list[0].name
        else:
            return _("User %s will be created") % user_list[0].name

    def input(self, args, key):
        if self._container.process_user_input(key):
            self.apply()
            return InputState.PROCESSED_AND_REDRAW

        return super().input(args, key)

    def apply(self):
        if self.user.gecos and not self.user.name:
            username = guess_username(self.user.gecos)
            valid, msg = check_username(username)
            if not valid:
                self.errors.append(_("Invalid user name: %(name)s.\n%(error_message)s")
                                   % {"name": username, "error_message": msg})
            else:
                self.user.name = guess_username(self.user.gecos)

        self.user.groups = [g.strip() for g in self._groups.split(",") if g]

        # Add or remove user admin status
        self.user.set_admin_priviledges(self._is_admin)

        # encrypt and store password only if user entered anything; this should
        # preserve passwords set via kickstart
        if self._use_password and self.user.password and len(self.user.password) > 0:
            self.user.password = self.user.password
            self.user.is_crypted = True
        # clear pw when user unselects to use pw
        else:
            self.user.password = ""
            self.user.is_crypted = False

        # Turning user creation off clears any already configured user,
        # regardless of origin (kickstart, user, DBus).
        if not self._create_user and self.user.name:
            self.user.name = ""
            self._user_cleared = True
        # An the other hand, if we have a user with name set,
        # it is valid and should be used if the spoke is re-visited.
        if self.user.name:
            self._user_cleared = False
        # Set the user list while removing any unset users, where unset
        # means the user has nema == "".
        set_user_list(self._users_module, self._user_list, remove_unset=True)
