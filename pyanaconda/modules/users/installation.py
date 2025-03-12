#
# Copyright (C) 2019 Red Hat, Inc.
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

import os

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import users
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)

__all__ = [
    "ConfigureRootPasswordSSHLoginTask",
    "CreateGroupsTask",
    "CreateUsersTask",
    "SetRootPasswordTask",
    "SetSshKeysTask",
]


class SetRootPasswordTask(Task):
    """Installation task fot setting the root password."""

    def __init__(self, sysroot, password, crypted, locked):
        """Create a new root password configuration task.

        :param str sysroot: a path to the root of the target system
        :param str password: root password to be set
        :param bool crypted: is the root password already encrypted ?
        :param bool locked: should the root password be locked ?
        """
        super().__init__()
        self._sysroot = sysroot
        self._password = password
        self._crypted = crypted
        self._locked = locked

    @property
    def name(self):
        return "Configure root password"

    def run(self):
        self._set_root_password()

    def _set_root_password(self):
        users.set_root_password(self._password,
                                self._crypted,
                                self._locked,
                                self._sysroot)


class CreateUsersTask(Task):
    """Create users on the target system."""

    def __init__(self, sysroot, user_data_list):
        """Create a new user creation task.

        :param str sysroot: a path to the root of the installed system
        :param user_data_list: list of users to create
        :type user_data_list: list of UserData instances
        """
        super().__init__()
        self._sysroot = sysroot
        self._user_data_list = user_data_list

    @property
    def name(self):
        return "Create users"

    def run(self):
        self._create_users()

    def _create_users(self):
        for user_data in self._user_data_list:
            uid = user_data.get_uid()
            gid = user_data.get_gid()

            try:
                users.create_user(username=user_data.name,
                                  password=user_data.password,
                                  is_crypted=user_data.is_crypted,
                                  lock=user_data.lock,
                                  homedir=user_data.homedir,
                                  uid=uid, gid=gid,
                                  groups=user_data.groups,
                                  shell=user_data.shell,
                                  gecos=user_data.gecos,
                                  root=self._sysroot)
            except ValueError as e:
                log.warning(str(e))


class CreateGroupsTask(Task):
    """Create groups on the target system."""

    def __init__(self, sysroot, group_data_list):
        """Create a new group creation task.

        :param str sysroot: a path to the root of the installed system
        :param group_data_list: list of groups to create
        :type group_data_list: list of GroupData instances
        """
        super().__init__()
        self._sysroot = sysroot
        self._group_data_list = group_data_list

    @property
    def name(self):
        return "Create groups"

    def run(self):
        self._create_groups()

    def _create_groups(self):
        for group_data in self._group_data_list:
            gid = group_data.get_gid()
            try:
                users.create_group(group_name=group_data.name, gid=gid, root=self._sysroot)
            except ValueError as e:
                log.warning(str(e))


class SetSshKeysTask(Task):
    """Install specified SSH keys to the target system."""

    def __init__(self, sysroot, ssh_key_data_list):
        """Create a new SSH key installation task.

        :param str sysroot: a path to the root of the installed system
        :param ssh_key_data_list: list of keys to install
        :type ssh_key_data_list: list of SshKeyData instances
        """
        super().__init__()
        self._sysroot = sysroot
        self._ssh_key_data_list = ssh_key_data_list

    @property
    def name(self):
        return "Set SSH keys"

    def run(self):
        self._set_ssh_keys()

    def _set_ssh_keys(self):
        for key_data in self._ssh_key_data_list:
            users.set_user_ssh_key(key_data.username, key_data.key)


class ConfigureRootPasswordSSHLoginTask(Task):
    """Optionally add an override allowing root to login with password over SSH."""

    CONFIG_PATH = "etc/ssh/sshd_config.d/01-permitrootlogin.conf"

    def __init__(self, sysroot, password_allowed):
        """Create a new root password SSH login configuration task.

        :param str sysroot: a path to the root of the installed system
        :param bool password_allowed: True allows root to login via SSH with password auth.
                                      False prevents it by not changing the default OpenSSH
                                      behavior
        """
        super().__init__()
        self._sysroot = sysroot
        self._password_allowed = password_allowed

    @property
    def name(self):
        return "Configure optional root password SSH login"

    def run(self):
        """Run the task."""
        if self._password_allowed:
            log.debug("Adding an override allowing root login with password via SSH.")
            with open(os.path.join(self._sysroot, self.CONFIG_PATH), "wt") as f:
                f.write(
                    '# This file has been generated by the Anaconda Installer.\n'
                    '# Allow root to log in using ssh. Remove this file to opt-out.\n'
                    'PermitRootLogin yes\n'
                )
        else:
            log.debug("Not adding an override allowing root login with password via SSH.")
