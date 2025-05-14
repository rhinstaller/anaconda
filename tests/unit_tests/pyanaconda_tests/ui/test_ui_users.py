#
# Copyright (C) 2021  Red Hat, Inc.
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
import unittest
from unittest.mock import Mock, patch

from dasbus.structure import compare_data

from pyanaconda.modules.common.structures.user import UserData
from pyanaconda.ui.lib.users import (
    can_modify_root_configuration,
    get_root_configuration_status,
    get_user_list,
    set_user_list,
)


class UsersUITestCase(unittest.TestCase):
    """Test the UI functions and classes of the Users module."""

    def test_get_empty_user_list(self):
        """Test the shared get_user_list() method with no users."""
        users_module_mock = Mock()
        users_module_mock.Users = []
        user_data_list = get_user_list(users_module_mock)
        assert user_data_list == []

    def test_get_default_user(self):
        """Test that default user is correctly added by get_user_list()."""
        users_module_mock = Mock()
        users_module_mock.Users = []
        user_data_list = get_user_list(users_module_mock, add_default=True)

        assert len(user_data_list) == 1
        assert isinstance(user_data_list[0], UserData)
        assert compare_data(user_data_list[0], UserData())

    def test_get_user_list(self):
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

        assert len(user_data_list) == 2
        assert isinstance(user_data_list[0], UserData)
        assert isinstance(user_data_list[1], UserData)
        assert compare_data(user_data_list[0], user1)
        assert compare_data(user_data_list[1], user2)

        user_data_list = get_user_list(users_module_mock, add_default=True)

        assert len(user_data_list) == 2
        assert isinstance(user_data_list[0], UserData)
        assert isinstance(user_data_list[1], UserData)
        assert compare_data(user_data_list[0], user1)
        assert compare_data(user_data_list[1], user2)

        user_data_list = get_user_list(users_module_mock, add_default=True, add_if_not_empty=True)

        assert len(user_data_list) == 3
        assert isinstance(user_data_list[0], UserData)
        assert isinstance(user_data_list[1], UserData)
        assert isinstance(user_data_list[2], UserData)
        assert compare_data(user_data_list[0], UserData())
        assert compare_data(user_data_list[1], user1)
        assert compare_data(user_data_list[2], user2)

    def test_set_user_list(self):
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

        assert len(user_data_list) == 2
        assert user_data_list[0] == UserData.to_structure(user1)
        assert user_data_list[1] == UserData.to_structure(user2)

        user1.name = ""
        set_user_list(users_module_mock, [user1, user2], remove_unset=True)
        user_data_list = users_module_mock.SetUsers.call_args[0][0]

        assert len(user_data_list) == 1
        assert user_data_list[0] == UserData.to_structure(user2)

    @patch("pyanaconda.ui.lib.users.conf")
    @patch("pyanaconda.ui.lib.users.flags")
    def test_can_modify_root_configuration(self, mocked_flags, mocked_conf):
        """Test the can_modify_root_configuration function."""
        users_module = Mock()
        mocked_flags.automatedInstall = False

        assert can_modify_root_configuration(users_module)

        mocked_flags.automatedInstall = True
        mocked_conf.ui.can_change_root = True

        assert can_modify_root_configuration(users_module)

        mocked_flags.automatedInstall = True
        mocked_conf.ui.can_change_root = False
        users_module.CanChangeRootPassword = True

        assert can_modify_root_configuration(users_module)

        mocked_flags.automatedInstall = True
        mocked_conf.ui.can_change_root = False
        users_module.CanChangeRootPassword = False

        assert not can_modify_root_configuration(users_module)

    def test_get_root_configuration_status(self):
        """Test the get_root_configuration_status function."""
        users_module = Mock()

        users_module.IsRootAccountLocked = False
        users_module.IsRootPasswordSet = False
        assert get_root_configuration_status(users_module) == "Root password is not set"

        users_module.IsRootAccountLocked = False
        users_module.IsRootPasswordSet = True
        assert get_root_configuration_status(users_module) == "Root password is set"

        users_module.IsRootAccountLocked = True
        users_module.IsRootPasswordSet = False
        assert get_root_configuration_status(users_module) == "Root account is disabled"

        users_module.IsRootAccountLocked = True
        users_module.IsRootPasswordSet = True
        assert get_root_configuration_status(users_module) == "Root account is disabled"
