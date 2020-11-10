#
# Copyright (C) 2018  Red Hat, Inc.
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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#
import os
import tempfile
import unittest
from textwrap import dedent
from unittest.mock import Mock

from dasbus.structure import compare_data
from tests.nosetests.pyanaconda_tests import check_kickstart_interface, patch_dbus_publish_object, \
    PropertiesChangedCallback, check_dbus_property, check_task_creation_list, check_task_creation

from pyanaconda.core.constants import ID_MODE_USE_DEFAULT, ID_MODE_USE_VALUE
from pyanaconda.modules.common.constants.services import USERS
from pyanaconda.modules.common.structures.user import UserData
from pyanaconda.modules.common.structures.group import GroupData
from pyanaconda.modules.users.users import UsersService
from pyanaconda.modules.users.users_interface import UsersInterface
from pyanaconda.modules.users.installation import ConfigureRootPasswordSSHLoginTask, \
    CreateGroupsTask, CreateUsersTask, SetRootPasswordTask, SetSshKeysTask
from dasbus.typing import get_variant, List, Str, UInt32, Bool
from pyanaconda.ui.lib.users import get_user_list, set_user_list


class UsersInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the users module."""

    def setUp(self):
        """Set up the user module."""
        # Set up the users module.
        self.users_module = UsersService()
        self.users_interface = UsersInterface(self.users_module)

        # Connect to the properties changed signal.
        self.callback = PropertiesChangedCallback()
        self.users_interface.PropertiesChanged.connect(self.callback)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.users_interface.KickstartCommands,
                         ["rootpw", "user", "group", "sshkey"])
        self.assertEqual(self.users_interface.KickstartSections, [])
        self.assertEqual(self.users_interface.KickstartAddons, [])
        self.callback.assert_not_called()

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            USERS,
            self.users_interface,
            *args, **kwargs
        )

    def default_property_values_test(self):
        """Test the default user module values are as expected."""
        self.assertEqual(self.users_interface.Users, [])
        self.assertEqual(self.users_interface.Groups, [])
        self.assertEqual(self.users_interface.SshKeys, [])
        self.assertEqual(self.users_interface.RootPassword, "")
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.assertEqual(self.users_interface.IsRootPasswordCrypted, False)
        self.assertEqual(self.users_interface.RootPasswordSSHLoginAllowed, True)
        self.assertEqual(self.users_interface.CanChangeRootPassword, True)

    def users_property_test(self):
        """Test the Users property."""
        user_1 = {
            "name": get_variant(Str, "user1"),
            "uid-mode": get_variant(Str, ID_MODE_USE_VALUE),
            "uid": get_variant(UInt32, 123),
            "groups": get_variant(List[Str], ["foo", "bar"]),
            "gid-mode": get_variant(Str, ID_MODE_USE_VALUE),
            "gid": get_variant(UInt32, 321),
            "homedir": get_variant(Str, "user1_home"),
            "password": get_variant(Str, "swordfish"),
            "is-crypted": get_variant(Bool, False),
            "lock": get_variant(Bool, False),
            "shell": get_variant(Str, "zsh"),
            "gecos": get_variant(Str, "some stuff"),
        }
        user_2 = {
            "name": get_variant(Str, "user2"),
            "uid-mode": get_variant(Str, ID_MODE_USE_DEFAULT),
            "uid": get_variant(UInt32, 456),
            "groups": get_variant(List[Str], ["baz", "bar"]),
            "gid-mode": get_variant(Str, ID_MODE_USE_DEFAULT),
            "gid": get_variant(UInt32, 654),
            "homedir": get_variant(Str, "user2_home"),
            "password": get_variant(Str, "laksdjaskldjhasjhd"),
            "is-crypted": get_variant(Bool, True),
            "lock": get_variant(Bool, False),
            "shell": get_variant(Str, "csh"),
            "gecos": get_variant(Str, "some other stuff"),
        }
        self._check_dbus_property(
            "Users",
            [user_1, user_2]
        )

    def groups_property_test(self):
        """Test the Groups property."""
        group_1 = {
            "name": get_variant(Str, "group1"),
            "gid-mode": get_variant(Str, ID_MODE_USE_VALUE),
            "gid": get_variant(UInt32, 321),
        }
        group_2 = {
            "name": get_variant(Str, "group2"),
            "gid-mode": get_variant(Str, ID_MODE_USE_DEFAULT),
            "gid": get_variant(UInt32, 654),
        }
        self._check_dbus_property(
            "Groups",
            [group_1, group_2]
        )

    def ssh_keys_property_test(self):
        """Test the SshKeys property."""
        key_1 = {
            "key": get_variant(Str, "aaa"),
            "username": get_variant(Str, "user1"),
        }
        key_2 = {
            "key": get_variant(Str, "bbb"),
            "username": get_variant(Str, "user2"),
        }
        self._check_dbus_property(
            "SshKeys",
            [key_1, key_2]
        )

    def set_crypted_roopw_test(self):
        """Test if setting crypted root password works correctly."""
        self.users_interface.SetCryptedRootPassword("abcef")

        self.assertEqual(self.users_interface.RootPassword, "abcef")
        self.assertEqual(self.users_interface.IsRootPasswordCrypted, True)
        self.assertEqual(self.users_interface.IsRootPasswordSet, True)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.callback.assert_called_once_with(USERS.interface_name, {'IsRootPasswordSet': True}, [])

    def set_crypted_roopw_and_unlock_test(self):
        """Test if setting crypted root password & unlocking it from kickstart works correctly."""
        self.users_interface.SetCryptedRootPassword("abcef")

        self.assertEqual(self.users_interface.IsRootPasswordSet, True)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.assertEqual(self.users_interface.CanChangeRootPassword, True)
        self.callback.assert_called_once_with(USERS.interface_name, {'IsRootPasswordSet': True}, [])

        # this should not be a valid admin user for interactive install
        self.assertFalse(self.users_interface.CheckAdminUserExists())

        # root password is locked by default and remains locked even after a password is set
        # and needs to be unlocked via another DBus API call
        self.users_interface.SetRootAccountLocked(False)

        self.assertEqual(self.users_interface.IsRootPasswordSet, True)
        self.assertEqual(self.users_interface.IsRootAccountLocked, False)
        self.callback.assert_called_with(USERS.interface_name, {'IsRootAccountLocked': False}, [])

    def lock_root_account_test(self):
        """Test if root account can be locked via DBus correctly."""
        self.users_interface.SetRootAccountLocked(True)

        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.callback.assert_called_once_with(USERS.interface_name, {'IsRootAccountLocked': True}, [])

    def clear_rootpw_test(self):
        """Test clearing of the root password."""
        # set the password to something
        self.users_interface.SetCryptedRootPassword("abcef")

        self.assertEqual(self.users_interface.IsRootPasswordSet, True)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.callback.assert_called_once_with(USERS.interface_name, {'IsRootPasswordSet': True}, [])

        # clear it
        self.users_interface.ClearRootPassword()

        # check if it looks cleared
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.callback.assert_called_with(USERS.interface_name, {'IsRootPasswordSet': False,
                                                                'IsRootAccountLocked': True}, [])

    def clear_unlocked_rootpw_test(self):
        """Test clearing of unlocked root password."""
        # set the password to something
        self.users_interface.SetCryptedRootPassword("abcef")
        self.callback.assert_called_once_with(USERS.interface_name, {'IsRootPasswordSet': True}, [])

        self.users_interface.SetRootAccountLocked(False)
        self.callback.assert_called_with(USERS.interface_name, {'IsRootAccountLocked': False}, [])

        self.assertEqual(self.users_interface.IsRootPasswordSet, True)
        self.assertEqual(self.users_interface.IsRootAccountLocked, False)

        # clear it
        self.users_interface.ClearRootPassword()

        # check if it looks cleared
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.callback.assert_called_with(USERS.interface_name, {'IsRootPasswordSet': False,
                                                                'IsRootAccountLocked': True}, [])

    def allow_root_password_ssh_login_test(self):
        """Test if root password SSH login can be allowed."""
        self.users_interface.SetRootPasswordSSHLoginAllowed(True)
        self.assertEqual(self.users_interface.RootPasswordSSHLoginAllowed, True)
        self.callback.assert_called_once_with(USERS.interface_name, {'RootPasswordSSHLoginAllowed': True}, [])

        self.callback.reset_mock()
        self.users_interface.SetRootPasswordSSHLoginAllowed(False)
        self.assertEqual(self.users_interface.RootPasswordSSHLoginAllowed, False)
        self.callback.assert_called_once_with(USERS.interface_name, {'RootPasswordSSHLoginAllowed': False}, [])

    def admin_user_detection_1_test(self):
        """Test that admin user detection works correctly - 3 admins."""
        # 2 admin users, unlocked root
        user1 = UserData()
        user1.name = "user1"
        user1.groups = ["foo", "wheel", "bar"]
        user1.lock = False

        user2 = UserData()
        user2.name = "user2"
        user2.groups = ["baz", "bar", "wheel"]
        user2.lock = False

        self.users_interface.SetUsers(UserData.to_structure_list([user1, user2]))
        self.users_interface.SetCryptedRootPassword("abc")
        self.users_interface.SetRootAccountLocked(False)
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def admin_user_detection_2_test(self):
        """Test that admin user detection works correctly - 0 admins (case 1)."""
        # 2 locked admin users, locked root
        user1 = UserData()
        user1.name = "user1"
        user1.groups = ["foo", "wheel", "bar"]
        user1.lock = True

        user2 = UserData()
        user2.name = "user2"
        user2.groups = ["baz", "bar", "wheel"]
        user2.lock = True

        self.users_interface.SetUsers(UserData.to_structure_list([user1, user2]))
        self.users_interface.SetCryptedRootPassword("abc")
        self.users_interface.SetRootAccountLocked(True)
        self.assertFalse(self.users_interface.CheckAdminUserExists())

    def admin_user_detection_3_test(self):
        """Test that admin user detection works correctly - 1 admin (case 2)."""
        # 2 locked admin users, unlocked root
        user1 = UserData()
        user1.name = "user1"
        user1.groups = ["foo", "wheel", "bar"]
        user1.lock = True

        user2 = UserData()
        user2.name = "user2"
        user2.groups = ["baz", "bar", "wheel"]
        user2.lock = True

        self.users_interface.SetUsers(UserData.to_structure_list([user1, user2]))
        self.users_interface.SetCryptedRootPassword("abc")
        self.users_interface.SetRootAccountLocked(False)
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def admin_user_detection_4_test(self):
        """Test that admin user detection works correctly - 1 admin (case 3)."""
        # 1 locked admin user, 1 unlocked admin user, locked root
        user1 = UserData()
        user1.name = "user1"
        user1.groups = ["foo", "wheel", "bar"]
        user1.lock = False

        user2 = UserData()
        user2.name = "user2"
        user2.groups = ["baz", "bar", "wheel"]
        user2.lock = True

        self.users_interface.SetUsers(UserData.to_structure_list([user1, user2]))
        self.users_interface.SetCryptedRootPassword("abc")
        self.users_interface.SetRootAccountLocked(True)
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def admin_user_detection_5_test(self):
        """Test that admin user detection works correctly - 1 admin (case 4)."""
        # 1 user, 1 unlocked admin user, locked root
        user1 = UserData()
        user1.name = "user1"
        user1.groups = ["foo", "bar"]
        user1.lock = False

        user2 = UserData()
        user2.name = "user2"
        user2.groups = ["baz", "bar", "wheel"]
        user2.lock = False

        self.users_interface.SetUsers(UserData.to_structure_list([user1, user2]))
        self.users_interface.SetCryptedRootPassword("abc")
        self.users_interface.SetRootAccountLocked(True)
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def admin_user_detection_6_test(self):
        """Test that admin user detection works correctly - 1 admin (case 5)."""
        # 2 users, unlocked root
        user1 = UserData()
        user1.name = "user1"
        user1.groups = ["foo", "bar"]
        user1.lock = False

        user2 = UserData()
        user2.name = "user2"
        user2.groups = ["baz", "bar"]
        user2.lock = False

        self.users_interface.SetUsers(UserData.to_structure_list([user1, user2]))
        self.users_interface.SetCryptedRootPassword("abc")
        self.users_interface.SetRootAccountLocked(False)
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def _test_kickstart(self, ks_in, ks_out, ks_tmp=None):
        check_kickstart_interface(self, self.users_interface, ks_in, ks_out, ks_tmp=ks_tmp)

    def no_kickstart_test(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = """
        #Root password
        rootpw --lock
        """
        self._test_kickstart(ks_in, ks_out)

        # root password should be empty and locked by default, but mutable
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.assertEqual(self.users_interface.CanChangeRootPassword, True)

        # this should not be considered a valid admin user for interactive install
        self.assertFalse(self.users_interface.CheckAdminUserExists())

    def kickstart_empty_test(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = """
        #Root password
        rootpw --lock
        """
        self._test_kickstart(ks_in, ks_out)

        # password should be marked as not set, locked and mutable
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.assertEqual(self.users_interface.CanChangeRootPassword, True)

        # not a valid admin user from kickstart PoV
        self.assertFalse(self.users_interface.CheckAdminUserExists())

    def kickstart_set_rootpw_test(self):
        """Test the setting root password via kickstart."""
        ks_in = """
        rootpw abcdef
        """
        ks_out = """
        # Root password
        rootpw --plaintext abcdef
        """
        self._test_kickstart(ks_in, ks_out)

        # if rootpw shows up in the kickstart is should be reported as immutable
        self.assertEqual(self.users_interface.IsRootPasswordSet, True)
        self.assertEqual(self.users_interface.IsRootAccountLocked, False)
        self.assertEqual(self.users_interface.CanChangeRootPassword, False)

        # but this should still be a valid admin user from kickstart PoV
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def kickstart_set_plain_rootpw_test(self):
        """Test the setting plaintext root password via kickstart."""
        ks_in = """
        rootpw --plaintext abcdef
        """
        ks_out = """
        # Root password
        rootpw --plaintext abcdef
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart_set_crypted_rootpw_test(self):
        """Test the setting crypted root password via kickstart."""
        ks_in = """
        rootpw --iscrypted abcdef
        """
        ks_out = """
        # Root password
        rootpw --iscrypted abcdef
        """
        self._test_kickstart(ks_in, ks_out)

        self.assertEqual(self.users_interface.IsRootPasswordSet, True)
        self.assertEqual(self.users_interface.IsRootAccountLocked, False)

    def kickstart_lock_root_account_test(self):
        """Test locking the root account via kickstart."""
        ks_in = """
        rootpw --lock
        """
        ks_out = """
        #Root password
        rootpw --lock
        """
        self._test_kickstart(ks_in, ks_out)

        # password should be marked as not set, locked and immutable
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.assertEqual(self.users_interface.CanChangeRootPassword, False)

        # but this should still be a valid admin user from kickstart PoV
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def kickstart_lock_root_account_with_password_test(self):
        """Test locking the root account with a password via kickstart."""
        ks_in = """
        rootpw abcdef --lock
        """
        ks_out = """
        # Root password
        rootpw --lock --plaintext abcdef
        """
        self._test_kickstart(ks_in, ks_out)

        # password should be marked as set, locked and immutable
        self.assertEqual(self.users_interface.IsRootPasswordSet, True)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.assertEqual(self.users_interface.CanChangeRootPassword, False)

        # but this should still be a valid admin user from kickstart PoV
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def kickstart_user_test(self):
        """Test kickstart user input and output."""
        ks_in = """
        user --name=user1 --password=abcedf
        """
        ks_out = """
        #Root password
        rootpw --lock
        user --name=user1 --password=abcedf
        """
        self._test_kickstart(ks_in, ks_out)

        # password should be marked as not set, locked and mutable
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.assertEqual(self.users_interface.CanChangeRootPassword, True)

        # no a valid admin user exists from kickstart PoV
        self.assertFalse(self.users_interface.CheckAdminUserExists())

    def kickstart_user_admin_test(self):
        """Test kickstart admin user input and output."""
        ks_in = """
        user --groups=wheel --name=user1 --password=abcedf
        """
        ks_out = """
        #Root password
        rootpw --lock
        user --groups=wheel --name=user1 --password=abcedf
        """
        self._test_kickstart(ks_in, ks_out)

        # password should be marked as not set, locked and mutable
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.assertEqual(self.users_interface.CanChangeRootPassword, True)

        # provides a valid admin user exists from kickstart PoV
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def kickstart_users_test(self):
        """Test kickstart users input and output."""
        ks_in = """
        user --name=user1 --homedir=user1_home --password=foo --shell=ksh --uid=123 --gecos=baz --gid=345 --groups=a,b,c,d --plaintext
        user --name=user2 --homedir=user2_home --password=asasas --shell=csh --uid=321 --gecos=bar --gid=543 --groups=wheel,mockuser --iscrypted
        user --name=user3 --lock
        """
        ks_out = """
        #Root password
        rootpw --lock
        user --groups=a,b,c,d --homedir=user1_home --name=user1 --password=foo --shell=ksh --uid=123 --gecos="baz" --gid=345
        user --groups=wheel,mockuser --homedir=user2_home --name=user2 --password=asasas --iscrypted --shell=csh --uid=321 --gecos="bar" --gid=543
        user --name=user3 --lock
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart_groups_test(self):
        """Test kickstart groups input and output."""
        ks_in = """
        group --name=group1 --gid=321
        group --name=group2 --gid=654
        group --name=group3
        """
        ks_out = """
        group --name=group1 --gid=321
        group --name=group2 --gid=654
        group --name=group3
        #Root password
        rootpw --lock
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart_ssh_keys_test(self):
        """Test kickstart ssh keys input and output."""
        ks_in = """
        sshkey --username=user1 "aaa"
        sshkey --username=user2 "bbb"
        sshkey --username=user3 "ccc"
        """
        ks_out = """
        #Root password
        rootpw --lock
        sshkey --username=user1 "aaa"
        sshkey --username=user2 "bbb"
        sshkey --username=user3 "ccc"
        """
        self._test_kickstart(ks_in, ks_out)

    @patch_dbus_publish_object
    def install_with_tasks_test(self, publisher):
        """Test InstallWithTasks."""
        task_classes = [
            CreateGroupsTask,
            CreateUsersTask,
            SetRootPasswordTask,
            SetSshKeysTask,
            ConfigureRootPasswordSSHLoginTask
        ]
        task_paths = self.users_interface.InstallWithTasks()
        check_task_creation_list(self, task_paths, publisher, task_classes)

    @patch_dbus_publish_object
    def configure_groups_with_task_test(self, publisher):
        """Test ConfigureGroupsWithTask."""
        task_path = self.users_interface.ConfigureGroupsWithTask()
        check_task_creation(self, task_path, publisher, CreateGroupsTask)

    @patch_dbus_publish_object
    def configure_users_with_task_test(self, publisher):
        """Test ConfigureUsersWithTask."""
        task_path = self.users_interface.ConfigureUsersWithTask()
        check_task_creation(self, task_path, publisher, CreateUsersTask)

    @patch_dbus_publish_object
    def set_root_password_with_task_test(self, publisher):
        """Test SetRootPasswordWithTask."""
        task_path = self.users_interface.SetRootPasswordWithTask()
        check_task_creation(self, task_path, publisher, SetRootPasswordTask)


class UsersDataTestCase(unittest.TestCase):
    """Test the UserData data holder class."""

    def eq_test(self):
        """Test that the __eq__() method works correctly for UserData instances."""
        # the comparison is name based
        user_data_1 = UserData()
        user_data_1.name = "foo"

        user_data_2 = UserData()
        user_data_2.name = "bar"

        user_data_3 = UserData()
        user_data_3.name = "foo"

        self.assertTrue(user_data_1 == user_data_3)
        self.assertFalse(user_data_1 == user_data_2)
        self.assertFalse(user_data_2 == user_data_1)
        self.assertFalse(user_data_2 == user_data_3)

        # now try changing the name on existing instance
        user_data_1.name = "bar"
        user_data_2.name = "foo"
        user_data_3.name = "foo"

        self.assertFalse(user_data_1 == user_data_2)
        self.assertFalse(user_data_1 == user_data_3)
        self.assertTrue(user_data_2 == user_data_3)
        self.assertTrue(user_data_3 == user_data_2)

        # only name is used, other attributes should not influence the comparison
        user_data_a = UserData()
        user_data_a.name = "foo"
        user_data_a.uid = 1
        user_data_a.gid = 1
        user_data_a.homedir = "/foo"

        user_data_b = UserData()
        user_data_b.name = "foo"
        user_data_b.uid = 2
        user_data_b.gid = 2
        user_data_b.homedir = "/bar"

        self.assertTrue(user_data_a == user_data_b)

    def has_admin_priviledges_test(self):
        """Test the has_admin_priviledges() method works correctly."""

        user_data = UserData()
        user_data.groups = ["wheel"]
        self.assertTrue(user_data.has_admin_priviledges())

        user_data = UserData()
        user_data.groups = ["foo"]
        self.assertFalse(user_data.has_admin_priviledges())

        user_data = UserData()
        user_data.groups = ["foo", "wheel", "bar"]
        self.assertTrue(user_data.has_admin_priviledges())

        # multiple wheels
        user_data = UserData()
        user_data.groups = ["foo", "wheel", "bar", "wheel", "baz"]
        self.assertTrue(user_data.has_admin_priviledges())

        # group name is case sensitive
        user_data = UserData()
        user_data.groups = ["WHEEL", "Wheel"]
        self.assertFalse(user_data.has_admin_priviledges())

    def set_admin_priviledges_test(self):
        """Test setting user admin privileges works correctly."""
        user_data = UserData()
        self.assertFalse(user_data.has_admin_priviledges())
        self.assertNotIn("wheel", user_data.groups)

        # turn it on
        user_data.set_admin_priviledges(True)
        self.assertTrue(user_data.has_admin_priviledges())
        self.assertIn("wheel", user_data.groups)

        # turn it off
        user_data.set_admin_priviledges(False)
        self.assertFalse(user_data.has_admin_priviledges())
        self.assertNotIn("wheel", user_data.groups)

        # existing groups - turn in on
        user_data = UserData()
        user_data.groups = ["foo", "bar"]
        user_data.set_admin_priviledges(True)
        self.assertTrue(user_data.has_admin_priviledges())
        self.assertIn("wheel", user_data.groups)
        self.assertIn("foo", user_data.groups)
        self.assertIn("bar", user_data.groups)

        # existing groups - turn in off
        user_data.set_admin_priviledges(False)
        self.assertFalse(user_data.has_admin_priviledges())
        self.assertNotIn("wheel", user_data.groups)
        self.assertIn("foo", user_data.groups)
        self.assertIn("bar", user_data.groups)

        # group wheel added externally
        user_data = UserData()
        user_data.groups = ["foo", "bar", "wheel"]
        self.assertTrue(user_data.has_admin_priviledges())
        self.assertIn("wheel", user_data.groups)
        self.assertIn("foo", user_data.groups)
        self.assertIn("bar", user_data.groups)

        # now remove the wheel group via API
        user_data.set_admin_priviledges(False)
        self.assertFalse(user_data.has_admin_priviledges())
        self.assertNotIn("wheel", user_data.groups)
        self.assertIn("foo", user_data.groups)
        self.assertIn("bar", user_data.groups)

    def getter_setter_test(self):
        """Test getters and setters for the User UID and GID values."""
        user_data = UserData()
        user_data.name = "user"

        # everything should be unset by default
        self.assertEqual(user_data.uid, 0)
        self.assertEqual(user_data.uid_mode, ID_MODE_USE_DEFAULT)
        self.assertEqual(user_data.get_uid(), None)
        self.assertEqual(user_data.gid, 0)
        self.assertEqual(user_data.gid_mode, ID_MODE_USE_DEFAULT)
        self.assertEqual(user_data.get_gid(), None)

        user_data.set_uid(123)
        user_data.set_gid(456)

        # now everything is set
        self.assertEqual(user_data.uid, 123)
        self.assertEqual(user_data.uid_mode, ID_MODE_USE_VALUE)
        self.assertEqual(user_data.get_uid(), 123)
        self.assertEqual(user_data.gid, 456)
        self.assertEqual(user_data.gid_mode, ID_MODE_USE_VALUE)
        self.assertEqual(user_data.get_gid(), 456)

        user_data.uid_mode = ID_MODE_USE_DEFAULT
        user_data.gid_mode = ID_MODE_USE_DEFAULT

        # mode should decide whether numbers are used, regardless of being stored
        self.assertEqual(user_data.uid_mode, ID_MODE_USE_DEFAULT)
        self.assertEqual(user_data.uid, 123)
        self.assertEqual(user_data.get_uid(), None)
        self.assertEqual(user_data.gid_mode, ID_MODE_USE_DEFAULT)
        self.assertEqual(user_data.gid, 456)
        self.assertEqual(user_data.get_gid(), None)

        user_data.set_uid(None)
        user_data.set_gid(None)

        # setting None resets everything
        self.assertEqual(user_data.uid, 0)
        self.assertEqual(user_data.uid_mode, ID_MODE_USE_DEFAULT)
        self.assertEqual(user_data.get_uid(), None)
        self.assertEqual(user_data.gid, 0)
        self.assertEqual(user_data.gid_mode, ID_MODE_USE_DEFAULT)
        self.assertEqual(user_data.get_gid(), None)


class GroupsDataTestCase(unittest.TestCase):
    """Test the GroupData data holder class."""

    def getter_setter_test(self):
        """Test getters and setters for the Group GID values."""
        group_data = GroupData()
        group_data.name = "group"

        # everything should be unset by default
        self.assertEqual(group_data.gid, 0)
        self.assertEqual(group_data.gid_mode, ID_MODE_USE_DEFAULT)
        self.assertEqual(group_data.get_gid(), None)

        group_data.set_gid(789)

        # now everything is set
        self.assertEqual(group_data.gid, 789)
        self.assertEqual(group_data.gid_mode, ID_MODE_USE_VALUE)
        self.assertEqual(group_data.get_gid(), 789)

        group_data.gid_mode = ID_MODE_USE_DEFAULT

        # mode should decide whether numbers are used, regardless of being stored
        self.assertEqual(group_data.gid_mode, ID_MODE_USE_DEFAULT)
        self.assertEqual(group_data.gid, 789)
        self.assertEqual(group_data.get_gid(), None)

        group_data.set_gid(None)

        # setting None resets everything
        self.assertEqual(group_data.gid, 0)
        self.assertEqual(group_data.gid_mode, ID_MODE_USE_DEFAULT)
        self.assertEqual(group_data.get_gid(), None)


class SharedUICodeTestCase(unittest.TestCase):
    """Test shared UI code related to user handling.

    The shared code calls the Users module interface so it makes sense to test it here.
    """

    def get_empty_user_list_test(self):
        """Test the shared get_user_list() method with no users."""
        users_module_mock = Mock()
        users_module_mock.Users = []
        user_data_list = get_user_list(users_module_mock)
        self.assertEqual(user_data_list, [])

    def get_default_user_test(self):
        """Test that default user is correctly added by get_user_list()."""
        users_module_mock = Mock()
        users_module_mock.Users = []
        user_data_list = get_user_list(users_module_mock, add_default=True)

        self.assertEqual(len(user_data_list), 1)
        self.assertIsInstance(user_data_list[0], UserData)
        self.assertTrue(compare_data(user_data_list[0], UserData()))

    def get_user_list_test(self):
        """Test the shared get_user_list() method."""
        user1 = UserData()
        user1.name = "user1"
        user1.uid = 123
        user1.groups = ["foo", "bar"]
        user1.gid = 321
        user1.homedir = "user1_home"
        user1.password = "swordfish"
        user1.is_crypted = False
        user1.lock = False
        user1.shell = "zsh"
        user1.gecos = "some stuff"

        user2 = UserData()
        user2.name = "user2"
        user2.uid = 456
        user2.groups = ["baz", "bar"]
        user2.gid = 654
        user2.homedir = "user2_home"
        user2.password = "laksdjaskldjhasjhd"
        user2.is_crypted = True
        user2.lock = False
        user2.shell = "csh"
        user2.gecos = "some other stuff"

        users_module_mock = Mock()
        users_module_mock.Users = UserData.to_structure_list([user1, user2])
        user_data_list = get_user_list(users_module_mock)

        self.assertEqual(len(user_data_list), 2)
        self.assertIsInstance(user_data_list[0], UserData)
        self.assertIsInstance(user_data_list[1], UserData)
        self.assertTrue(compare_data(user_data_list[0], user1))
        self.assertTrue(compare_data(user_data_list[1], user2))

        user_data_list = get_user_list(users_module_mock, add_default=True)

        self.assertEqual(len(user_data_list), 2)
        self.assertIsInstance(user_data_list[0], UserData)
        self.assertIsInstance(user_data_list[1], UserData)
        self.assertTrue(compare_data(user_data_list[0], user1))
        self.assertTrue(compare_data(user_data_list[1], user2))

        user_data_list = get_user_list(users_module_mock, add_default=True, add_if_not_empty=True)

        self.assertEqual(len(user_data_list), 3)
        self.assertIsInstance(user_data_list[0], UserData)
        self.assertIsInstance(user_data_list[1], UserData)
        self.assertIsInstance(user_data_list[2], UserData)
        self.assertTrue(compare_data(user_data_list[0], UserData()))
        self.assertTrue(compare_data(user_data_list[1], user1))
        self.assertTrue(compare_data(user_data_list[2], user2))

    def set_user_list_test(self):
        """Test the shared set_user_list() method."""
        user1 = UserData()
        user1.name = "user1"
        user1.uid = 123
        user1.groups = ["foo", "bar"]
        user1.gid = 321
        user1.homedir = "user1_home"
        user1.password = "swordfish"
        user1.is_crypted = False
        user1.lock = False
        user1.shell = "zsh"
        user1.gecos = "some stuff"

        user2 = UserData()
        user2.name = "user2"
        user2.uid = 456
        user2.groups = ["baz", "bar"]
        user2.gid = 654
        user2.homedir = "user2_home"
        user2.password = "laksdjaskldjhasjhd"
        user2.is_crypted = True
        user2.lock = False
        user2.shell = "csh"
        user2.gecos = "some other stuff"

        users_module_mock = Mock()
        set_user_list(users_module_mock, [user1, user2])
        user_data_list = users_module_mock.SetUsers.call_args[0][0]

        self.assertEqual(len(user_data_list), 2)
        self.assertEqual(user_data_list[0], UserData.to_structure(user1))
        self.assertEqual(user_data_list[1], UserData.to_structure(user2))

        user1.name = ""
        set_user_list(users_module_mock, [user1, user2], remove_unset=True)
        user_data_list = users_module_mock.SetUsers.call_args[0][0]

        self.assertEqual(len(user_data_list), 1)
        self.assertEqual(user_data_list[0], UserData.to_structure(user2))


class UsersModuleTasksTestCase(unittest.TestCase):
    """Test the DBus Tasks provided by the Users module."""

    SSHD_OVERRIDE_PATH = "etc/sysconfig/sshd-permitrootlogin"

    def setUp(self):
        """Set up the users module."""
        self.users_module = UsersService()
        self.users_interface = UsersInterface(self.users_module)

        # Connect to the properties changed signal.
        self.callback = PropertiesChangedCallback()
        self.users_interface.PropertiesChanged.connect(self.callback)

    def root_ssh_password_config_task_enabled_test(self):
        """Test the root password SSH login configuration task - enabled (write config file)."""
        # the config file should be written out when the override is enabled
        with tempfile.TemporaryDirectory() as sysroot:
            config_path = os.path.join(sysroot, self.SSHD_OVERRIDE_PATH)
            os.makedirs(os.path.dirname(config_path))

            # no config should exist before we run the task
            self.assertFalse(os.path.exists(config_path))

            task = ConfigureRootPasswordSSHLoginTask(sysroot=sysroot, password_allowed=True)
            task.run()

            # correct override config should exist after we run the task
            self.assertTrue(os.path.exists(config_path))

            expected_content = dedent("""
            # This file has been generated by the Anaconda Installer.
            # Allow root to log in using ssh. Remove this file to opt-out.
            PERMITROOTLOGIN="-oPermitRootLogin=yes"
            """)

            with open(config_path, "rt") as f:
                config_content = f.read()

            self.assertEqual(
                config_content.strip(),
                expected_content.strip()
            )

    def root_ssh_password_config_task_disabled_test(self):
        """Test the root password SSH login configuration task - disabled (no config file)."""
        # the config file should not be written out when the override is disabled
        with tempfile.TemporaryDirectory() as sysroot:
            config_path = os.path.join(sysroot, self.SSHD_OVERRIDE_PATH)
            os.makedirs(os.path.dirname(config_path))

            # no config should exist before we run the task
            self.assertFalse(os.path.exists(config_path))

            task = ConfigureRootPasswordSSHLoginTask(sysroot=sysroot, password_allowed=False)
            task.run()

            # correct override config should exist after we run the task
            self.assertFalse(os.path.exists(config_path))
