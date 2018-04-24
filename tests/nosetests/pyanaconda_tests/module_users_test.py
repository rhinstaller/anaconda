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
from pyanaconda.modules.users.user import UserInterface, UserModule
from pyanaconda.modules.users.users import UsersModule
from pyanaconda.modules.users.users_interface import UsersInterface
from tests.nosetests.pyanaconda_tests import check_kickstart_interface, check_dbus_property


class UsersInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the users module."""

    def setUp(self):
        """Set up the user module."""
        # Set up the users module.
        self.users_module = UsersModule()
        self.users_interface = UsersInterface(self.users_module)

        # Initialize the user interface.
        UserInterface._user_counter = 1

        # Connect to the properties changed signal.
        self.callback = Mock()
        self.users_interface.PropertiesChanged.connect(self.callback)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.users_interface.KickstartCommands, ["rootpw", "user"])
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

    @patch("pyanaconda.modules.users.users.DBus")
    def create_user_test(self, bus):
        """Test the create user method."""
        object_path = self.users_interface.CreateUser()

        # Check callbacks.
        bus.publish_object.assert_called_once()
        self.callback.assert_called_once_with(USERS.interface_name, {'Users': [object_path]}, [])

        # Check results.
        self.assertEqual("/org/fedoraproject/Anaconda/Modules/Users/User/1", object_path)
        self.assertEqual(self.users_interface.Users, [object_path])

    @patch("pyanaconda.modules.users.users.DBus")
    def multiple_users_property_test(self, _bus):
        """Test the users property with multiple users."""
        self.assertEqual(self.users_interface.Users, [])

        object_path_1 = self.users_interface.CreateUser()
        object_path_2 = self.users_interface.CreateUser()
        object_path_3 = self.users_interface.CreateUser()

        self.assertEqual("/org/fedoraproject/Anaconda/Modules/Users/User/1", object_path_1)
        self.assertEqual("/org/fedoraproject/Anaconda/Modules/Users/User/2", object_path_2)
        self.assertEqual("/org/fedoraproject/Anaconda/Modules/Users/User/3", object_path_3)
        self.assertEqual(self.users_interface.Users, [object_path_1, object_path_2, object_path_3])

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

    @patch("pyanaconda.modules.users.users.DBus")
    def kickstart_user_test(self, _bus):
        """Test the user kickstart command."""
        ks_in = """
        user --name="harry"
        """
        ks_out = """
        user --name=harry
        """
        self._test_kickstart(ks_in, ks_out, ks_tmp="")

    @patch("pyanaconda.modules.users.users.DBus")
    def kickstart_multiple_users_test(self, _bus):
        """Test the user kickstart commands."""
        ks_in = """
        user --name=harry
        user --name=hermione
        user --name=ron
        """
        ks_out = """
        user --name=harry
        user --name=hermione
        user --name=ron
        """
        self._test_kickstart(ks_in, ks_out, ks_tmp="")


class UserInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the user module."""

    def setUp(self):
        """Set up the user module."""
        # Set up the users module.
        self.user_module = UserModule()
        self.user_interface = UserInterface(self.user_module)

        # Initialize the user interface.
        UserInterface._user_counter = 1

        # Connect to the properties changed signal.
        self.callback = Mock()
        self.user_interface.PropertiesChanged.connect(self.callback)

    def _test_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            USER,
            self.user_interface,
            *args, **kwargs
        )

    def name_property_test(self):
        """Test the user name property."""
        self._test_dbus_property(
            "Name",
            "harry"
        )
