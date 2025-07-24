#
# Kickstart module for the users module.
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.core.users import guess_username
from pyanaconda.modules.common.base import KickstartService
from pyanaconda.modules.common.constants.services import USERS
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.group import GroupData
from pyanaconda.modules.common.structures.sshkey import SshKeyData
from pyanaconda.modules.common.structures.user import UserData
from pyanaconda.modules.users.installation import (
    ConfigureRootPasswordSSHLoginTask,
    CreateGroupsTask,
    CreateUsersTask,
    SetRootPasswordTask,
    SetSshKeysTask,
)
from pyanaconda.modules.users.kickstart import UsersKickstartSpecification
from pyanaconda.modules.users.users_interface import UsersInterface

log = get_module_logger(__name__)


class UsersService(KickstartService):
    """The Users service."""

    def __init__(self):
        super().__init__()
        self.can_change_root_password_changed = Signal()
        self._can_change_root_password = True

        self.root_password_is_set_changed = Signal()
        self._root_password = ""
        self._root_password_is_crypted = False

        self.root_account_locked_changed = Signal()
        self._root_account_locked = True

        self._root_password_ssh_login_allowed = False
        self.root_password_ssh_login_allowed_changed = Signal()

        self.users_changed = Signal()
        self._users = []

        self.groups_changed = Signal()
        self._groups = []

        self.ssh_keys_changed = Signal()
        self._ssh_keys = []

        self._rootpw_seen = False

    def publish(self):
        """Publish the module."""
        TaskContainer.set_namespace(USERS.namespace)
        DBus.publish_object(USERS.object_path, UsersInterface(self))
        DBus.register_service(USERS.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return UsersKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self.set_root_password(data.rootpw.password, crypted=data.rootpw.isCrypted)
        self.set_root_account_locked(data.rootpw.lock)
        self.set_root_password_ssh_login_allowed(data.rootpw.allow_ssh)
        # make sure the root account is locked unless a password is set in kickstart
        if not data.rootpw.password:
            log.debug("root specified in kickstart without password, locking account")
            self.set_root_account_locked(True)
        # if password was set in kickstart it can't be changed by default
        if data.rootpw.seen:
            self.set_can_change_root_password(False)
            self._rootpw_seen = True

        user_data_list = []
        for user_ksdata in data.user.userList:
            user_data_list.append(self._ksdata_to_user_data(user_ksdata))
        self.set_users(user_data_list)

        group_data_list = []
        for group_ksdata in data.group.groupList:
            group_data = GroupData()
            group_data.name = group_ksdata.name
            group_data.set_gid(group_ksdata.gid)
            group_data_list.append(group_data)
        self.set_groups(group_data_list)

        ssh_key_data_list = []
        for ssh_key_ksdata in data.sshkey.sshUserList:
            ssh_key_data = SshKeyData()
            ssh_key_data.key = ssh_key_ksdata.key
            ssh_key_data.username = ssh_key_ksdata.username
            ssh_key_data_list.append(ssh_key_data)
        self.set_ssh_keys(ssh_key_data_list)

    # pylint: disable=arguments-differ
    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        data.rootpw.password = self._root_password
        data.rootpw.isCrypted = self._root_password_is_crypted
        data.rootpw.lock = self.root_account_locked
        data.rootpw.allow_ssh = self.root_password_ssh_login_allowed

        for user_data in self.users:
            data.user.userList.append(self._user_data_to_ksdata(data.UserData(),
                                                                user_data))

        for group_data in self.groups:
            group_ksdata = data.GroupData()
            group_ksdata.name = group_data.name
            group_ksdata.gid = group_data.get_gid()
            data.group.groupList.append(group_ksdata)

        for ssh_key_data in self.ssh_keys:
            ssh_key_ksdata = data.SshKeyData()
            ssh_key_ksdata.key = ssh_key_data.key
            ssh_key_ksdata.username = ssh_key_data.username
            data.sshkey.sshUserList.append(ssh_key_ksdata)

    def configure_groups_with_task(self):
        """Return the user group configuration task.

        :returns: a user group configuration task
        """
        return CreateGroupsTask(
            sysroot=conf.target.system_root,
            group_data_list=self.groups
        )

    def configure_users_with_task(self):
        """Return the user configuration task.

        :returns: a user configuration task
        """
        return CreateUsersTask(
            sysroot=conf.target.system_root,
            user_data_list=self.users
        )

    def set_root_password_with_task(self):
        """Return the root password configuration task.

        :returns: a root password configuration task
        """
        return SetRootPasswordTask(
            sysroot=conf.target.system_root,
            password=self.root_password,
            crypted=self.root_password_is_crypted,
            locked=self.root_account_locked
        )

    def set_ssh_keys_with_task(self):
        """Return the SSH key configuration task.

        :returns: o SSH key configuration task
        """
        return SetSshKeysTask(
            sysroot=conf.target.system_root,
            ssh_key_data_list=self.ssh_keys
        )

    def configure_root_password_ssh_login_with_task(self):
        """Return the root password SSH login configuration task.

        :returns: a root password SSH login configuration task
        """
        return ConfigureRootPasswordSSHLoginTask(
            sysroot=conf.target.system_root,
            password_allowed=self.root_password_ssh_login_allowed
        )

    def install_with_tasks(self):
        """Return the installation tasks of this module.

        :returns: list of tasks
        """
        return [
            self.configure_groups_with_task(),
            self.configure_users_with_task(),
            self.set_root_password_with_task(),
            self.set_ssh_keys_with_task(),
            self.configure_root_password_ssh_login_with_task()
        ]

    def _ksdata_to_user_data(self, user_ksdata):
        """Apply kickstart user command data to UserData instance.

        :param user_ksdata: data for the kickstart user command
        :return: UserData instance with kickstart data applied
        """
        user_data = UserData()
        user_data.name = user_ksdata.name
        user_data.groups = user_ksdata.groups
        user_data.set_uid(user_ksdata.uid)
        user_data.set_gid(user_ksdata.gid)
        user_data.homedir = user_ksdata.homedir
        user_data.password = user_ksdata.password
        user_data.is_crypted = user_ksdata.isCrypted
        user_data.lock = user_ksdata.lock
        # make sure the user account is locked by default unless a password
        # is set in kickstart
        if not user_ksdata.password:
            log.debug("user (%s) specified in kickstart without password, locking account",
                      user_ksdata.name)
            user_data.lock = True
        user_data.shell = user_ksdata.shell
        user_data.gecos = user_ksdata.gecos
        return user_data

    def _user_data_to_ksdata(self, user_ksdata, user_data):
        """Convert UserData instance to kickstart user command data.

        :param user_ksdata: UserData instance from Kickstart
        :param user_data: our UserData instance
        :return: kickstart user command data for a single user
        """
        user_ksdata.name = user_data.name
        user_ksdata.groups = user_data.groups
        user_ksdata.uid = user_data.get_uid()
        user_ksdata.gid = user_data.get_gid()
        user_ksdata.homedir = user_data.homedir
        user_ksdata.password = user_data.password
        user_ksdata.isCrypted = user_data.is_crypted
        user_ksdata.lock = user_data.lock
        user_ksdata.shell = user_data.shell
        user_ksdata.gecos = user_data.gecos
        return user_ksdata

    @property
    def users(self):
        """List of UserData instances, one per user."""
        return self._users

    def set_users(self, users):
        """Set the list of UserData instances, one per user."""
        self._users = users
        self.users_changed.emit()
        log.debug("A new user list has been set: %s", self._users)

    @property
    def groups(self):
        """List of GroupData instances, one per group."""
        return self._groups

    def set_groups(self, groups):
        """Set the list of GroupData instances, one per group."""
        self._groups = groups
        self.groups_changed.emit()
        log.debug("A new group list has been set: %s", self._groups)

    @property
    def ssh_keys(self):
        """List of SshKeyData instances, one per ssh key."""
        return self._ssh_keys

    def set_ssh_keys(self, ssh_keys):
        """Set the list of SshKeyData instances, one per ssh keys."""
        self._ssh_keys = ssh_keys
        self.ssh_keys_changed.emit()
        log.debug("A new ssh key list has been set: %s", self._ssh_keys)

    @property
    def can_change_root_password(self):
        return self._can_change_root_password

    def set_can_change_root_password(self, can_change_root_password):
        self._can_change_root_password = can_change_root_password
        self.can_change_root_password_changed.emit()
        log.debug("Can change root password state changed: %s.", can_change_root_password)

    @property
    def root_password(self):
        """The root password.

        :returns: root password (might be crypted)
        :rtype: str
        """
        return self._root_password

    @property
    def root_password_is_crypted(self):
        """Is the root password crypted ?

        :returns: if root password is crypted
        :rtype: bool
        """
        return self._root_password_is_crypted

    def set_root_password(self, root_password, crypted):
        """Set the crypted root password.

        NOTE: Setting password == "" is equivalent to
              calling clear_root_password().

        :param str root_password: root password
        :param bool crypted: if the root password is crypted
        """
        if root_password == "":
            self._root_password = ""
            self._root_password_is_crypted = False
            self.set_root_account_locked(True)
            self.root_password_is_set_changed.emit()
            log.debug("Root password cleared.")
        else:
            self._root_password = root_password
            self._root_password_is_crypted = crypted
            self.root_password_is_set_changed.emit()
            log.debug("Root password set.")

    def clear_root_password(self):
        """Clear any set root password."""
        self.set_root_password("", False)

    @property
    def root_password_is_set(self):
        """Is the root password set ?"""
        return bool(self._root_password)

    def set_root_account_locked(self, locked):
        """Lock or unlock the root account.

        :param bool locked: True id the account should be locked, False otherwise.
        """
        self._root_account_locked = locked
        self.root_account_locked_changed.emit()
        if locked:
            log.debug("Root account has been locked.")
        else:
            log.debug("Root account has been unlocked.")

    @property
    def root_account_locked(self):
        """Is the root account locked ?"""
        return self._root_account_locked

    def set_root_password_ssh_login_allowed(self, root_password_ssh_login_allowed):
        """Allow/disable root login via SSH with password.

        (Login as root with key is always allowed)

        param bool root_password_ssh_login_allowed: True to allow, False to disallow
        """
        self._root_password_ssh_login_allowed = root_password_ssh_login_allowed
        self.root_password_ssh_login_allowed_changed.emit()
        if root_password_ssh_login_allowed:
            log.debug("SSH login as root with password will be allowed.")
        else:
            log.debug("SSH login as root with password will not be allowed.")

    @property
    def root_password_ssh_login_allowed(self):
        """Is logging in as root via SSH with password allowed ?"""
        return self._root_password_ssh_login_allowed

    @property
    def check_admin_user_exists(self):
        """Reports if at least one admin user exists.

        - an unlocked root account is considered to be an admin user
        - an unlocked user account that is member of the group "wheel"
          is considered to be an admin user

        :return: if at least one admin user exists
        """
        # any root set from kickstart is fine
        if self._rootpw_seen:
            return True
        # if not set by kickstart root must not be
        # locked to be cosnidered admin
        elif self.root_password and not self.root_account_locked:
            return True

        # let's check all users
        for user in self.users:
            if not user.lock:
                if "wheel" in user.groups:
                    return True

        # no admin user found
        return False

    def guess_username(self, fullname):
        """Guess a username from a full name.

        :param fullname: full user name to base the username on
        :returns: guessed username
        """
        return guess_username(fullname)
