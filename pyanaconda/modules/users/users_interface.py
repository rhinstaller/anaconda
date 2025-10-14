#
# DBus interface for the users module.
#
# Copyright (C) 2018 Red Hat, Inc.
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

from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.constants.services import USERS
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.group import GroupData
from pyanaconda.modules.common.structures.sshkey import SshKeyData
from pyanaconda.modules.common.structures.user import UserData


@dbus_interface(USERS.interface_name)
class UsersInterface(KickstartModuleInterface):
    """DBus interface for Users module."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("Users", self.implementation.users_changed)
        self.watch_property("Groups", self.implementation.groups_changed)
        self.watch_property("SshKeys", self.implementation.ssh_keys_changed)
        self.watch_property("IsRootPasswordSet",
                            self.implementation.root_password_is_set_changed)
        self.watch_property("IsRootAccountLocked",
                            self.implementation.root_account_locked_changed)
        self.watch_property("RootPasswordSSHLoginAllowed",
                            self.implementation.root_password_ssh_login_allowed_changed)
        self.watch_property("CanChangeRootPassword",
                            self.implementation.can_change_root_password_changed)

    @property
    def CanChangeRootPassword(self) -> Bool:
        """Can the root password be changed ?

        :return: True, if the root password can the changed, False otherwise
        """
        return self.implementation.can_change_root_password

    @property
    def RootPassword(self) -> Str:
        """Root password.

        NOTE: this property should be only temporary and should be
              dropped once the users module itself can configure the root password

        :return: root password (might be crypted)
        """
        return self.implementation.root_password

    @property
    def IsRootPasswordCrypted(self) -> Bool:
        """Is the root password crypted ?

        NOTE: this property should be only temporary and should be
              dropped once the users module itself can configure the root password

        :return: True, if the root password is crypted, otherwise False
        """
        return self.implementation.root_password_is_crypted

    @emits_properties_changed
    def SetCryptedRootPassword(self, crypted_root_password: Str):
        """Set the root password.

        The password is expected to be provided in already crypted.

        :param crypted_root_password: already crypted root password
        """
        self.implementation.set_root_password(crypted_root_password, crypted=True)

    @emits_properties_changed
    def ClearRootPassword(self):
        """Clear any set root password."""
        self.implementation.clear_root_password()

    @property
    def IsRootPasswordSet(self) -> Bool:
        """Is the root password set ?

        :return: True, if the root password is set, otherwise False
        """
        return self.implementation.root_password_is_set

    @property
    def IsRootAccountLocked(self) -> Bool:
        """Is the root account locked ?

        :return: True, if the root account is locked, otherwise False
        """
        return self.implementation.root_account_locked

    @IsRootAccountLocked.setter
    @emits_properties_changed
    def IsRootAccountLocked(self, root_account_locked: Bool):
        """Lock or unlock the root account."""
        self.implementation.set_root_account_locked(root_account_locked)

    @property
    def RootPasswordSSHLoginAllowed(self) -> Bool:
        """Is logging in as root via SSH with password allowed ?

        :return: True if root SSH loggin with password is allowed, False otherwise
        """
        return self.implementation.root_password_ssh_login_allowed

    @RootPasswordSSHLoginAllowed.setter
    @emits_properties_changed
    def RootPasswordSSHLoginAllowed(self, root_password_ssh_login_allowed: Bool):
        """Allow or disallow the root from logging in via SSH with password authetication."""
        self.implementation.set_root_password_ssh_login_allowed(root_password_ssh_login_allowed)

    @property
    def Users(self) -> List[Structure]:
        """List of users, each describing a single user.

        :return: a list of user describing DBus Structures
        """
        return UserData.to_structure_list(self.implementation.users)

    @Users.setter
    @emits_properties_changed
    def Users(self, users: List[Structure]):
        """Set a list of users, each corresponding to a single user.

        :param users: a list of user describing DBus structures
        """
        self.implementation.set_users(UserData.from_structure_list(users))

    @property
    def Groups(self) -> List[Structure]:
        """List of groups, each describing a single group.

        :return: a list of group describing DBus Structures
        """
        return GroupData.to_structure_list(self.implementation.groups)

    @Groups.setter
    @emits_properties_changed
    def Groups(self, groups: List[Structure]):
        """Set a list of groups, each corresponding to a single group.

        :param groups: a list of group describing DBus structures
        """
        self.implementation.set_groups(GroupData.from_structure_list(groups))

    @property
    def SshKeys(self) -> List[Structure]:
        """List of SSH keys, each describing a single SSH key.

        :return: a list of SSH key describing DBus Structures
        """
        return SshKeyData.to_structure_list(self.implementation.ssh_keys)

    @SshKeys.setter
    @emits_properties_changed
    def SshKeys(self, ssh_keys: List[Structure]):
        """Set a list of DBus structures, each corresponding to a single SSH key.

        :param ssh_keys: a list of SSH key describing DBus structures
        """
        self.implementation.set_ssh_keys(SshKeyData.from_structure_list(ssh_keys))

    def CheckAdminUserExists(self) -> Bool:
        """Reports if at least one admin user exists.

        - an unlocked root account is considered to be an admin user
        - an unlocked user account that is member of the group "wheel"
          is considered to be an admin user

        :return: if at least one admin user exists
        """
        return self.implementation.check_admin_user_exists

    def ConfigureGroupsWithTask(self) -> ObjPath:
        """Configure user groups via a DBus task.

        :returns: DBus path of the task
        """
        return TaskContainer.to_object_path(
            self.implementation.configure_groups_with_task()
        )

    def ConfigureUsersWithTask(self) -> ObjPath:
        """Configure users via a DBus task.

        :returns: DBus path of the task
        """
        return TaskContainer.to_object_path(
            self.implementation.configure_users_with_task()
        )

    def SetRootPasswordWithTask(self) -> ObjPath:
        """Set root password via a DBus task.

        :returns: DBus path of the task
        """
        return TaskContainer.to_object_path(
            self.implementation.set_root_password_with_task()
        )

    def GuessUsernameFromFullName(self, fullname: Str) -> Str:
        """Guess a username from a full name.

        :param fullname: full user name to base the username on
        :returns: guessed username
        """
        return self.implementation.guess_username(fullname)
