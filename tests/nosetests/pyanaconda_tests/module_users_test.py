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
import unittest
from unittest.mock import Mock, patch

from pyanaconda.modules.common.constants.interfaces import USER
from pyanaconda.modules.common.constants.services import USERS
from pyanaconda.modules.common.structures.user import UserData
from pyanaconda.modules.users.users import UsersModule
from pyanaconda.modules.users.users_interface import UsersInterface
from pyanaconda.dbus.typing import get_variant, List, Str, Int, Bool
from tests.nosetests.pyanaconda_tests import check_kickstart_interface, check_dbus_property


class UsersInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the users module."""

    def setUp(self):
        """Set up the user module."""
        # Set up the users module.
        self.users_module = UsersModule()
        self.users_interface = UsersInterface(self.users_module)

        # Connect to the properties changed signal.
        self.callback = Mock()
        self.users_interface.PropertiesChanged.connect(self.callback)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.users_interface.KickstartCommands, ["rootpw", "user", "group", "sshkey"])
        self.assertEqual(self.users_interface.KickstartSections, [])
        self.assertEqual(self.users_interface.KickstartAddons, [])
        self.callback.assert_not_called()

    def default_property_values_test(self):
        """Test the default user module values are as expected."""
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, False)

    def set_crypted_roopw_test(self):
        """Test if setting crypted root password from kickstart works correctly."""
        self.users_interface.SetCryptedRootPassword("abcef")
        self.assertEqual(self.users_interface.IsRootPasswordSet, True)
        self.assertEqual(self.users_interface.IsRootAccountLocked, False)
        self.callback.assert_called_once_with(USERS.interface_name, {'IsRootPasswordSet': True}, [])

    def lock_root_account_test(self):
        """Test if root account can be locked via DBUS correctly."""
        self.users_interface.SetRootAccountLocked(True)
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.callback.assert_called_once_with(USERS.interface_name, {'IsRootAccountLocked': True}, [])

    def ks_set_plaintext_roopw_test(self):
        """Test if setting plaintext root password from kickstart works correctly."""
        # at the moment a plaintext password can be set only via kickstart
        self.users_interface.ReadKickstart("rootpw --plaintext abcedf")
        self.assertEqual(self.users_interface.IsRootPasswordSet, True)
        self.assertEqual(self.users_interface.IsRootAccountLocked, False)

    def ks_set_crypted_roopw_test(self):
        """Test if setting crypted root password from kickstart works correctly."""
        self.users_interface.ReadKickstart("rootpw --iscrypted abcedf")
        self.assertEqual(self.users_interface.IsRootPasswordSet, True)
        self.assertEqual(self.users_interface.IsRootAccountLocked, False)

    def ks_lock_root_account_test(self):
        """Test if locking the root account from kickstart works correctly."""
        self.users_interface.ReadKickstart("rootpw --lock")
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)

    def ks_lock_dbus_unlock_root_account_test(self):
        """Test locking root from kickstart and unlocking with DBUS."""
        self.users_interface.ReadKickstart("rootpw --lock")
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, True)
        self.users_interface.SetRootAccountLocked(False)
        self.callback.assert_called_with(USERS.interface_name, {'IsRootAccountLocked': False}, [])
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, False)

    def clear_rootpw_test(self):
        """Test clearing of the root password."""
        # set the password to something
        self.users_interface.SetCryptedRootPassword("abcef")
        self.assertEqual(self.users_interface.IsRootPasswordSet, True)
        self.assertEqual(self.users_interface.IsRootAccountLocked, False)
        self.callback.assert_called_once_with(USERS.interface_name, {'IsRootPasswordSet': True}, [])
        # clear it
        self.users_interface.ClearRootPassword()
        # check if it looks cleared
        self.assertEqual(self.users_interface.IsRootPasswordSet, False)
        self.assertEqual(self.users_interface.IsRootAccountLocked, False)
        self.callback.assert_called_with(USERS.interface_name, {'IsRootPasswordSet': False}, [])

    def rootpw_not_kickstarted_test(self):
        """Test rootpw is not marked as kickstarted without kickstart."""
        # if no rootpw showed in input kickstart seen should be False
        self.assertEqual(self.users_interface.IsRootpwKickstarted, False)
        # check if we can set it to True (not sure why would we do it, but oh well)
        self.users_interface.SetRootpwKickstarted(True)
        self.assertEqual(self.users_interface.IsRootpwKickstarted, True)
        self.callback.assert_called_with(USERS.interface_name, {'IsRootpwKickstarted': True}, [])

    def rootpw_kickstarted_test(self):
        """Test rootpw is marked as kickstarted with kickstart."""
        # if rootpw shows up in the kickstart is should be reported as kickstarted
        self.users_interface.ReadKickstart("rootpw abcef")
        self.assertEqual(self.users_interface.IsRootpwKickstarted, True)
        # and we should be able to set it to False (for example when we override the data from kickstart)
        self.users_interface.SetRootpwKickstarted(False)
        self.assertEqual(self.users_interface.IsRootpwKickstarted, False)
        self.callback.assert_called_with(USERS.interface_name, {'IsRootpwKickstarted': False}, [])

    def no_users_property_test(self):
        """Test the users property with no users."""
        self.assertEqual(self.users_interface.Users, [])
        self.callback.assert_not_called()

    def basic_users_test(self):
        """Test that user data can be set and read again."""
        user1 = {
                "name" : "user1",
                "uid" : 123,
                "groups" : ["foo", "bar"],
                "gid" : 321,
                "homedir" : "user1_home",
                "password" : "swordfish",
                "is_crypted" : False,
                "lock" : False,
                "shell" : "zsh",
                "gecos" : "some stuff",
        }
        user2 = {
                "name" : "user2",
                "uid" : 456,
                "groups" : ["baz", "bar"],
                "gid" : 654,
                "homedir" : "user2_home",
                "password" : "laksdjaskldjhasjhd",
                "is_crypted" : True,
                "lock" : False,
                "shell" : "csh",
                "gecos" : "some other stuff",
        }

        user_list_in = [user1, user2]
        # set the users list via API
        self.users_interface.SetUsers(user_list_in)

        # retrieve the users list via API and validate the returned data
        users_list_out = self.users_interface.Users

        # construct the expected result
        user1_out = {
                    "name" : get_variant(Str, "user1"),
                    "uid" : get_variant(Int, 123),
                    "groups" : get_variant(List[Str], ["foo", "bar"]),
                    "gid" : get_variant(Int, 321),
                    "homedir" : get_variant(Str, "user1_home"),
                    "password" : get_variant(Str, "swordfish"),
                    "is_crypted" : get_variant(Bool, False),
                    "lock" : get_variant(Bool, False),
                    "shell" : get_variant(Str, "zsh"),
                    "gecos" : get_variant(Str, "some stuff"),
        }
        user2_out = {
                    "name" : get_variant(Str, "user2"),
                    "uid" : get_variant(Int, 456),
                    "groups" : get_variant(List[Str], ["baz", "bar"]),
                    "gid" : get_variant(Int, 654),
                    "homedir" : get_variant(Str, "user2_home"),
                    "password" : get_variant(Str, "laksdjaskldjhasjhd"),
                    "is_crypted" : get_variant(Bool, True),
                    "lock" : get_variant(Bool, False),
                    "shell" : get_variant(Str, "csh"),
                    "gecos" : get_variant(Str, "some other stuff"),
        }

        # check the output os the same as the expected result & in correct order
        self.assertEqual(users_list_out[0], user1_out)
        self.assertEqual(users_list_out[1], user2_out)

    def users_clear_test(self):
        """Test that user data can be se and then cleared."""
        user1 = {
                "name" : "user1",
                "uid" : 123,
                "groups" : ["foo", "bar"],
                "gid" : 321,
                "homedir" : "user1_home",
                "password" : "swordfish",
                "is_crypted" : False,
                "lock" : False,
                "shell" : "zsh",
                "gecos" : "some stuff",
        }
        user2 = {
                "name" : "user2",
                "uid" : 456,
                "groups" : ["baz", "bar"],
                "gid" : 654,
                "homedir" : "user2_home",
                "password" : "laksdjaskldjhasjhd",
                "is_crypted" : True,
                "lock" : False,
                "shell" : "csh",
                "gecos" : "some other stuff",
        }
        user_list_in = [user1, user2]
        # set the users list via API
        self.users_interface.SetUsers(user_list_in)

        # check the list is nonempty
        self.assertEqual(len(self.users_interface.Users), 2)

        # set an empty user list next
        self.users_interface.SetUsers([])

        # retrieve the users list via API and validate it is empty
        self.assertEqual(self.users_interface.Users, [])

    def users_modify_test(self):
        """Test that user data can be overwritten in place."""
        user1 = {
                "name" : "user1",
                "uid" : 123,
                "groups" : ["foo", "bar"],
                "gid" : 321,
                "homedir" : "user1_home",
                "password" : "swordfish",
                "is_crypted" : False,
                "lock" : False,
                "shell" : "zsh",
                "gecos" : "some stuff",
        }
        user_list_in = [user1]
        # set the users list via API
        self.users_interface.SetUsers(user_list_in)
        # check content is correct
        user1_out = {
                    "name" : get_variant(Str, "user1"),
                    "uid" : get_variant(Int, 123),
                    "groups" : get_variant(List[Str], ["foo", "bar"]),
                    "gid" : get_variant(Int, 321),
                    "homedir" : get_variant(Str, "user1_home"),
                    "password" : get_variant(Str, "swordfish"),
                    "is_crypted" : get_variant(Bool, False),
                    "lock" : get_variant(Bool, False),
                    "shell" : get_variant(Str, "zsh"),
                    "gecos" : get_variant(Str, "some stuff"),
        }
        self.assertEqual(self.users_interface.Users[0], user1_out)
        # replace the user data by changed user data
        userG = {
                "name" : "Gandalf",
                "uid" : 5,
                "groups" : ["wizzards", "vallar"],
                "gid" : 1,
                "homedir" : "behind_the_sea",
                "password" : "mellon",
                "is_crypted" : False,
                "lock" : False,
                "shell" : "gsh",
                "gecos" : "Run you fools!",
        }
        self.users_interface.SetUsers([userG])
        # check we get the changed data
        userG_out = {
                "name" : get_variant(Str, "Gandalf"),
                "uid" : get_variant(Int, 5),
                "groups" : get_variant(List[Str], ["wizzards", "vallar"]),
                "gid" : get_variant(Int, 1),
                "homedir" : get_variant(Str, "behind_the_sea"),
                "password" : get_variant(Str, "mellon"),
                "is_crypted" : get_variant(Bool, False),
                "lock" : get_variant(Bool, False),
                "shell" : get_variant(Str, "gsh"),
                "gecos" : get_variant(Str, "Run you fools!"),
        }
        self.assertEqual(self.users_interface.Users[0], userG_out)

    def admin_user_detection_1_test(self):
        """Test that admin user detection works correctly - 3 admins."""
        # 2 admin users, unlocked root
        user1 = {
                "name" : "user1",
                "groups" : ["foo", "wheel", "bar"],
                "lock" : False,
        }
        user2 = {
                "name" : "user2",
                "groups" : ["baz", "bar", "wheel"],
                "lock" : False,
        }
        user_list_in = [user1, user2]
        self.users_interface.SetUsers(user_list_in)
        self.users_interface.SetCryptedRootPassword("abc")
        self.users_interface.SetRootAccountLocked(False)
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def admin_user_detection_2_test(self):
        """Test that admin user detection works correctly - 0 admins (case 1)."""
        # 2 locked admin users, locked root
        user1 = {
                "name" : "user1",
                "groups" : ["foo", "wheel", "bar"],
                "lock" : True,
        }
        user2 = {
                "name" : "user2",
                "groups" : ["baz", "bar", "wheel"],
                "lock" : True,
        }
        user_list_in = [user1, user2]
        self.users_interface.SetUsers(user_list_in)
        self.users_interface.SetCryptedRootPassword("abc")
        self.users_interface.SetRootAccountLocked(True)
        self.assertFalse(self.users_interface.CheckAdminUserExists())

    def admin_user_detection_3_test(self):
        """Test that admin user detection works correctly - 1 admin (case 2)."""
        # 2 locked admin users, unlocked root
        user1 = {
                "name" : "user1",
                "groups" : ["foo", "wheel", "bar"],
                "lock" : True,
        }
        user2 = {
                "name" : "user2",
                "groups" : ["baz", "bar", "wheel"],
                "lock" : True,
        }
        user_list_in = [user1, user2]
        self.users_interface.SetUsers(user_list_in)
        self.users_interface.SetCryptedRootPassword("abc")
        self.users_interface.SetRootAccountLocked(False)
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def admin_user_detection_4_test(self):
        """Test that admin user detection works correctly - 1 admin (case 3)."""
        # 1 locked admin user, 1 unlocked admin user, locked root
        user1 = {
                "name" : "user1",
                "groups" : ["foo", "wheel", "bar"],
                "lock" : False,
        }
        user2 = {
                "name" : "user2",
                "groups" : ["baz", "bar", "wheel"],
                "lock" : True,
        }
        user_list_in = [user1, user2]
        self.users_interface.SetUsers(user_list_in)
        self.users_interface.SetCryptedRootPassword("abc")
        self.users_interface.SetRootAccountLocked(True)
        self.assertTrue(self.users_interface.CheckAdminUserExists())


    def admin_user_detection_5_test(self):
        """Test that admin user detection works correctly - 1 admin (case 4)."""
        # 1 user, 1 unlocked admin user, locked root
        user1 = {
                "name" : "user1",
                "groups" : ["foo", "bar"],
                "lock" : False,
        }
        user2 = {
                "name" : "user2",
                "groups" : ["baz", "bar", "wheel"],
                "lock" : False,
        }
        user_list_in = [user1, user2]
        self.users_interface.SetUsers(user_list_in)
        self.users_interface.SetCryptedRootPassword("abc")
        self.users_interface.SetRootAccountLocked(True)
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def admin_user_detection_6_test(self):
        """Test that admin user detection works correctly - 1 admin (case 5)."""
        # 2 users, unlocked root
        user1 = {
                "name" : "user1",
                "groups" : ["foo", "bar"],
                "lock" : False,
        }
        user2 = {
                "name" : "user2",
                "groups" : ["baz", "bar"],
                "lock" : False,
        }
        user_list_in = [user1, user2]
        self.users_interface.SetUsers(user_list_in)
        self.users_interface.SetCryptedRootPassword("abc")
        self.users_interface.SetRootAccountLocked(False)
        self.assertTrue(self.users_interface.CheckAdminUserExists())

    def users_type_test(self):
        """Test that type checking works correctly when setting user data."""
        with self.assertRaises(TypeError):
            user = {"name" : 1}
            self.users_interface.SetUsers([user])

        with self.assertRaises(TypeError):
            user = {"uid" : "abc"}
            self.users_interface.SetUsers([user])

        # TODO: should we prevent <0 uid/gid from being set ?
        user = {"uid" : -500}
        self.users_interface.SetUsers([user])
        output = self.users_interface.Users[0]
        self.assertEqual(get_variant(Int, -500), output["uid"])

        # TODO: looks like the Int type accepts floating point numbers ?
        #       (which are definitely not a valid uid/gid)
        #       - the result seems converted to Int:
        #       0.75 -> 0
        #       1.75 -> 1

        user = {"uid" : 1.75}
        self.users_interface.SetUsers([user])
        output = self.users_interface.Users[0]
        self.assertEqual(get_variant(Int, 1), output["uid"])

        with self.assertRaises(TypeError):
            user = {"gid" : "abc"}
            self.users_interface.SetUsers([user])

        with self.assertRaises(TypeError):
            user = {"groups" : [1, 2, 3]}
            self.users_interface.SetUsers([user])

        with self.assertRaises(TypeError):
            user = {"homedir" : True}
            self.users_interface.SetUsers([user])

        with self.assertRaises(TypeError):
            user = {"password" : None}
            self.users_interface.SetUsers([user])

        # TODO: looks like Bool also accepts almost anything,
        #       but converts it into a True/False value on output
        #       - None is still rejected though
        user = {"is_crypted" : "yes"}
        self.users_interface.SetUsers([user])
        output = self.users_interface.Users[0]
        self.assertEqual(get_variant(Bool, True), output["is_crypted"])

        user = {"lock" : "secure"}
        self.users_interface.SetUsers([user])
        output = self.users_interface.Users[0]
        self.assertEqual(get_variant(Bool, True), output["lock"])

        user = {"lock" : 1}
        self.users_interface.SetUsers([user])
        output = self.users_interface.Users[0]
        self.assertEqual(get_variant(Bool, True), output["lock"])

        user = {"lock" : 0}
        self.users_interface.SetUsers([user])
        output = self.users_interface.Users[0]
        self.assertEqual(get_variant(Bool, False), output["lock"])

        user = {"lock" : ""}
        self.users_interface.SetUsers([user])
        output = self.users_interface.Users[0]
        self.assertEqual(get_variant(Bool, False), output["lock"])

        user = {"lock" : []}
        self.users_interface.SetUsers([user])
        output = self.users_interface.Users[0]
        self.assertEqual(get_variant(Bool, False), output["lock"])

        with self.assertRaises(TypeError):
            user = {"shell" : True}
            self.users_interface.SetUsers([user])

        with self.assertRaises(TypeError):
            user = {"gecos" : -1}
            self.users_interface.SetUsers([user])

    def users_kickstart_output_test(self):
        """Check if user data values set via DBUS API are valid in the output kickstart."""
        user1 = {
                "name" : "user1",
                "uid" : 123,
                "groups" : ["foo", "bar"],
                "gid" : 321,
                "homedir" : "user1_home",
                "password" : "swordfish",
                "is_crypted" : False,
                "lock" : False,
                "shell" : "zsh",
                "gecos" : "some stuff",
        }
        user2 = {
                "name" : "user2",
                "uid" : 456,
                "groups" : ["baz", "bar"],
                "gid" : 654,
                "homedir" : "user2_home",
                "password" : "laksdjaskldjhasjhd",
                "is_crypted" : True,
                "lock" : False,
                "shell" : "csh",
                "gecos" : "some other stuff",
        }

        user_list_in = [user1, user2]
        # set the users list via API
        self.users_interface.SetUsers(user_list_in)
        # also set some other atributes of the users module DBUS API
        self.users_interface.SetCryptedRootPassword("abcdef")
        self.users_interface.SetRootAccountLocked(True)

        # validate the resulting kickstart
        ksdata = self.users_interface.GenerateKickstart()
        self.maxDiff = None
        expected_kickstart = """# Root password
rootpw --iscrypted --lock abcdef
user --groups=foo,bar --homedir=user1_home --name=user1 --password=swordfish --shell=zsh --uid=123 --gecos="some stuff" --gid=321
user --groups=baz,bar --homedir=user2_home --name=user2 --password=laksdjaskldjhasjhd --iscrypted --shell=csh --uid=456 --gecos="some other stuff" --gid=654
"""
        self.assertEqual(str(ksdata), expected_kickstart)

    def no_groups_property_test(self):
        """Test the groups property with no groups."""
        self.assertEqual(self.users_interface.Groups, [])
        self.callback.assert_not_called()

    def basic_groups_test(self):
        """Test that the group data can be set and read again."""
        group1 = {
                "name" : "group1",
                "gid" : 321,
        }
        group2 = {
                "name" : "group2",
                "gid" : 654,
        }

        group_list_in = [group1, group2]
        # set the groups list via API
        self.users_interface.SetGroups(group_list_in)

        # retrieve the group list via API and validate the returned data
        group_list_out = self.users_interface.Groups

        # construct the expected result
        group1_out = {
                    "name" : get_variant(Str, "group1"),
                    "gid" : get_variant(Int, 321),
        }
        group2_out = {
                    "name" : get_variant(Str, "group2"),
                    "gid" : get_variant(Int, 654),
        }

        # check the output os the same as the expected result & in correct order
        self.assertEqual(group_list_out[0], group1_out)
        self.assertEqual(group_list_out[1], group2_out)

    def groups_clear_test(self):
        """Test that we can set group data and then clear it again."""
        group1 = {
                "name" : "group1",
                "gid" : 321,
        }
        group2 = {
                "name" : "group2",
                "gid" : 654,
        }
        group_list_in = [group1, group2]
        # set the group list via API
        self.users_interface.SetGroups(group_list_in)

        # check the list is nonempty
        self.assertEqual(len(self.users_interface.Groups), 2)

        # set an empty group list next
        self.users_interface.SetGroups([])

        # retrieve the groups list via API and validate it is empty
        self.assertEqual(self.users_interface.Groups, [])

    def groups_modify_test(self):
        """Test that group data can be overwritten in place."""
        group = {
                "name" : "group1",
                "gid" : 321,
        }
        group_list_in = [group]
        # set the groups list via API
        self.users_interface.SetGroups(group_list_in)
        # check content is correct
        group_out = {
                    "name" : get_variant(Str, "group1"),
                    "gid" : get_variant(Int, 321),
        }
        self.assertEqual(self.users_interface.Groups[0], group_out)
        # replace the group data by changed user data
        different_group = {
                "name" : "different",
                "gid" : 1337,
        }
        self.users_interface.SetGroups([different_group])
        # check we get the changed data
        different_group_out = {
                "name" : get_variant(Str, "different"),
                "gid" : get_variant(Int, 1337),
        }
        self.assertEqual(self.users_interface.Groups[0], different_group_out)

    def group_kickstart_output_test(self):
        """Check if group data values set via DBUS API are valid in the output kickstart."""
        group1 = {
                "name" : "group1",
                "gid" : 321,
        }
        group2 = {
                "name" : "group2",
                "gid" : 654,
        }
        # lets try a gid-less group as well
        group3 = {
                "name" : "group3",
        }

        group_list_in = [group1, group2, group3]
        # set the group list via API
        self.users_interface.SetGroups(group_list_in)
        # also set some other atributes of the users module DBUS API
        self.users_interface.SetCryptedRootPassword("abcdef")
        self.users_interface.SetRootAccountLocked(True)

        # validate the resulting kickstart
        ksdata = self.users_interface.GenerateKickstart()
        self.maxDiff = None
        expected_kickstart = """group --name=group1 --gid=321
group --name=group2 --gid=654
group --name=group3
# Root password
rootpw --iscrypted --lock abcdef
"""
        self.assertEqual(str(ksdata), expected_kickstart)

    def no_ssh_keys_property_test(self):
        """Test the SSH keys property with no ssh keys."""
        self.assertEqual(self.users_interface.SshKeys, [])
        self.callback.assert_not_called()

    def basic_ssh_keys_test(self):
        """Test that the SSH key data can be set and read again."""
        key1 = {
                "key" : "aaa",
                "username" : "user1",
        }
        key2 = {
                "key" : "bbb",
                "username" : "user2",
        }

        key_list_in = [key1, key2]
        # set the SSH key list via API
        self.users_interface.SetSshKeys(key_list_in)

        # retrieve the SSH key list via API and validate the returned data
        key_list_out = self.users_interface.SshKeys

        # construct the expected result
        key1_out = {
                    "key" : get_variant(Str, "aaa"),
                    "username" : get_variant(Str, "user1"),
        }
        key2_out = {
                    "key" : get_variant(Str, "bbb"),
                    "username" : get_variant(Str, "user2"),
        }

        # check the output is the same as the expected result & in correct order
        self.assertEqual(key_list_out[0], key1_out)
        self.assertEqual(key_list_out[1], key2_out)

    def ssh_keys_clear_test(self):
        """Test that we can set SSH key data and then clear it again."""
        key1 = {
                "key" : "aaa",
                "username" : "user1",
        }
        key2 = {
                "key" : "bbb",
                "username" : "user2",
        }
        key_list_in = [key1, key2]
        # set the SSH key list via API
        self.users_interface.SetSshKeys(key_list_in)

        # check the list is nonempty
        self.assertEqual(len(self.users_interface.SshKeys), 2)

        # set an empty SSH key list next
        self.users_interface.SetSshKeys([])

        # retrieve the groups list via API and validate it is empty
        self.assertEqual(self.users_interface.Groups, [])

    def ssh_keys_modify_test(self):
        """Test that SSH key data can be overwritten in place."""
        key = {
                "key" : "aaa",
                "username" : "user1",
        }
        key_list_in = [key]
        # set the SSH key list via API
        self.users_interface.SetSshKeys(key_list_in)
        # check content is correct
        key_out = {
                    "key" : get_variant(Str, "aaa"),
                    "username" : get_variant(Str, "user1"),
        }
        self.assertEqual(self.users_interface.SshKeys[0], key_out)
        # replace the SSH key data by changed user data
        different_key = {
                "key" : "nanananana",
                "username" : "batman",
        }
        self.users_interface.SetSshKeys([different_key])
        # check we get the changed data
        different_key_out = {
                "key" : get_variant(Str, "nanananana"),
                "username" : get_variant(Str, "batman"),
        }
        self.assertEqual(self.users_interface.SshKeys[0], different_key_out)

    def ssh_keys_kickstart_output_test(self):
        """Check if SSH key data values set via DBUS API are valid in the output kickstart."""
        key1 = {
                "key" : "aaa",
                "username" : "user1",
        }
        key2 = {
                "key" : "bbb",
                "username" : "user2",
        }
        # lets try a username-less key as well
        key3 = {
                "key" : "ccc",
                "username" : "user3",
        }

        key_list_in = [key1, key2, key3]
        # set the SSH key list via API
        self.users_interface.SetSshKeys(key_list_in)
        # also set some other atributes of the users module DBUS API
        self.users_interface.SetCryptedRootPassword("abcdef")
        self.users_interface.SetRootAccountLocked(True)

        # validate the resulting kickstart
        ksdata = self.users_interface.GenerateKickstart()
        self.maxDiff = None
        expected_kickstart = """\
# Root password
rootpw --iscrypted --lock abcdef
sshkey --username=user1 "aaa"
sshkey --username=user2 "bbb"
sshkey --username=user3 "ccc"
"""
        self.assertEqual(str(ksdata), expected_kickstart)

    def _test_kickstart(self, ks_in, ks_out, ks_tmp=None):
        check_kickstart_interface(self, self.users_interface, ks_in, ks_out, ks_tmp=ks_tmp)

    def kickstart_set_plain_rootpw_test(self):
        """Test the setting plaintext root password via kickstart."""

        # the --plaintext option is assumed by default
        ks_in = """
        rootpw abcdef
        """
        ks_out = """
        # Root password
        rootpw --plaintext abcdef
        """
        self._test_kickstart(ks_in, ks_out)

        # but check if the result is the same if it's actually used
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

    def kickstart_users_test(self):
        """Test kickstart user input and output."""
        ks_in = """
        user --name=user1 --homedir=user1_home --password=foo --shell=ksh --uid=123 --gecos=baz --gid=345 --groups=a,b,c,d --plaintext
        user --name=user2 --homedir=user2_home --password=asasas --shell=csh --uid=321 --gecos=bar --gid=543 --groups=wheel,mockuser --iscrypted
        user --name=user3 --lock
        """
        ks_out = """
        user --groups=a,b,c,d --homedir=user1_home --name=user1 --password=foo --shell=ksh --uid=123 --gecos="baz" --gid=345
        user --groups=wheel,mockuser --homedir=user2_home --name=user2 --password=asasas --iscrypted --shell=csh --uid=321 --gecos="bar" --gid=543
        user --name=user3 --lock
        """
        self._test_kickstart(ks_in, ks_out)


class UsersDataTestCase(unittest.TestCase):
    """Test the UserData data holder class."""

    def set_property_test(self):
        """Test UserData properties can be set and read again."""
        user_data = UserData()
        user_data.name = "foo"
        user_data.password = "abc"
        user_data.is_crypted = False
        user_data.uid = 2
        user_data.gid = 1
        user_data.homedir = "/home/bar"
        user_data.groups = ["mockuser", "wheel"]
        user_data.gecos = "some stuff"
        user_data.lock = False
        user_data.shell = "zsh"
        self.assertEqual(user_data.name, "foo")
        self.assertEqual(user_data.password, "abc")
        self.assertEqual(user_data.is_crypted, False)
        self.assertEqual(user_data.uid, 2)
        self.assertEqual(user_data.gid, 1)
        self.assertEqual(user_data.homedir, "/home/bar")
        self.assertEqual(user_data.groups, ["mockuser", "wheel"])
        self.assertEqual(user_data.gecos, "some stuff")
        self.assertEqual(user_data.lock, False)
        self.assertEqual(user_data.shell, "zsh")

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

    def i_in_list_test(self):
        """Check if __eq__() works correctly also for lists."""
        user_data_x = UserData()
        user_data_x.name = "foo"

        user_data_y = UserData()
        user_data_y.name = "bar"

        user_data_z = UserData()
        user_data_z.name = "foo"

        list1 = [user_data_x, user_data_y]
        self.assertIn(user_data_x, list1)
        self.assertIn(user_data_y, list1)
        self.assertIn(user_data_z, list1)

        list2 = [user_data_x, user_data_z]
        self.assertIn(user_data_x, list2)
        self.assertIn(user_data_z, list2)
        self.assertNotIn(user_data_y, list2)

        list3 = []
        self.assertNotIn(user_data_x, list3)
        self.assertNotIn(user_data_y, list3)
        self.assertNotIn(user_data_z, list3)

        list4 = [user_data_x]
        self.assertIn(user_data_x, list4)
        self.assertIn(user_data_z, list4)
        self.assertNotIn(user_data_y, list4)

        list5 = [user_data_y]
        self.assertIn(user_data_y, list5)
        self.assertNotIn(user_data_x, list5)
        self.assertNotIn(user_data_z, list5)

    def is_admin_test(self):
        """Check the check_is_admin() method works correctly."""

        user_data = UserData()
        user_data.groups = ["wheel"]
        self.assertTrue(user_data.check_is_admin())

        user_data = UserData()
        user_data.groups = ["foo"]
        self.assertFalse(user_data.check_is_admin())

        user_data = UserData()
        user_data.groups = ["foo", "wheel", "bar"]
        self.assertTrue(user_data.check_is_admin())

        # multiple wheels
        user_data = UserData()
        user_data.groups = ["foo", "wheel", "bar", "wheel", "baz"]
        self.assertTrue(user_data.check_is_admin())

        # group name is case sensitive
        user_data = UserData()
        user_data.groups = ["WHEEL", "Wheel"]
        self.assertFalse(user_data.check_is_admin())
