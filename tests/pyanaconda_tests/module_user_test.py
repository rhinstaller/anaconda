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
from mock import Mock

from pyanaconda.dbus.constants import MODULE_USER_NAME, DBUS_MODULE_NAMESPACE
from pyanaconda.modules.user.user import UserModule
from pyanaconda.modules.user.user_interface import UserInterface


class UserInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the user module."""

    def setUp(self):
        """Set up the user module."""
        # Set up the user module.
        self.user_module = UserModule()
        self.user_interface = UserInterface(self.user_module)

        # Connect to the properties changed signal.
        self.callback = Mock()
        self.user_interface.PropertiesChanged.connect(self.callback)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.user_interface.KickstartCommands, ["rootpw"])
        self.assertEqual(self.user_interface.KickstartSections, [])
        self.assertEqual(self.user_interface.KickstartAddons, [])
        self.callback.assert_not_called()

    def default_property_values_test(self):
        """Test the default user module values are as expected."""
        self.assertEqual(self.user_interface.IsRootPasswordSet, False)
        self.assertEqual(self.user_interface.IsRootAccountLocked, False)

    def set_crypted_roopw_test(self):
        """Test if setting crypted root password from kickstart works correctly."""
        self.user_interface.SetCryptedRootPassword("abcef")
        self.assertEqual(self.user_interface.IsRootPasswordSet, True)
        self.assertEqual(self.user_interface.IsRootAccountLocked, False)
        self.callback.assert_called_once_with(MODULE_USER_NAME, {'IsRootPasswordSet': True}, [])

    def lock_root_account_test(self):
        """Test if root account can be locked via DBUS correctly."""
        self.user_interface.SetRootAccountLocked(True)
        self.assertEqual(self.user_interface.IsRootPasswordSet, False)
        self.assertEqual(self.user_interface.IsRootAccountLocked, True)
        self.callback.assert_called_once_with(MODULE_USER_NAME, {'IsRootAccountLocked': True}, [])

    def ks_set_plaintext_roopw_test(self):
        """Test if setting plaintext root password from kickstart works correctly."""
        # at the moment a plaintext password can be set only via kickstart
        self.user_interface.ReadKickstart("rootpw --plaintext abcedf")
        self.assertEqual(self.user_interface.IsRootPasswordSet, True)
        self.assertEqual(self.user_interface.IsRootAccountLocked, False)

    def ks_set_crypted_roopw_test(self):
        """Test if setting crypted root password from kickstart works correctly."""
        self.user_interface.ReadKickstart("rootpw --iscrypted abcedf")
        self.assertEqual(self.user_interface.IsRootPasswordSet, True)
        self.assertEqual(self.user_interface.IsRootAccountLocked, False)

    def ks_lock_root_account_test(self):
        """Test if locking the root account from kickstart works correctly."""
        self.user_interface.ReadKickstart("rootpw --lock")
        self.assertEqual(self.user_interface.IsRootPasswordSet, False)
        self.assertEqual(self.user_interface.IsRootAccountLocked, True)

    def ks_lock_dbus_unlock_root_account_test(self):
        """Test locking root from kickstart and unlocking with DBUS."""
        self.user_interface.ReadKickstart("rootpw --lock")
        self.assertEqual(self.user_interface.IsRootPasswordSet, False)
        self.assertEqual(self.user_interface.IsRootAccountLocked, True)
        self.user_interface.SetRootAccountLocked(False)
        self.callback.assert_called_with(MODULE_USER_NAME, {'IsRootAccountLocked': False}, [])
        self.assertEqual(self.user_interface.IsRootPasswordSet, False)
        self.assertEqual(self.user_interface.IsRootAccountLocked, False)

    def clear_rootpw_test(self):
        """Test clearing of the root password."""
        # set the password to something
        self.user_interface.SetCryptedRootPassword("abcef")
        self.assertEqual(self.user_interface.IsRootPasswordSet, True)
        self.assertEqual(self.user_interface.IsRootAccountLocked, False)
        self.callback.assert_called_once_with(MODULE_USER_NAME, {'IsRootPasswordSet': True}, [])
        # clear it
        self.user_interface.ClearRootPassword()
        # check if it looks cleared
        self.assertEqual(self.user_interface.IsRootPasswordSet, False)
        self.assertEqual(self.user_interface.IsRootAccountLocked, False)
        self.callback.assert_called_with(MODULE_USER_NAME, {'IsRootPasswordSet': False}, [])

    def rootpw_not_kickstarted_test(self):
        """Test rootpw is not marked as kickstarted without kickstart."""
        # if no rootpw showed in input kickstart seen should be False
        self.assertEqual(self.user_interface.IsRootpwKickstarted, False)
        # check if we can set it to True (not sure why would we do it, but oh well)
        self.user_interface.SetRootpwKickstarted(True)
        self.assertEqual(self.user_interface.IsRootpwKickstarted, True)
        self.callback.assert_called_with(MODULE_USER_NAME, {'IsRootpwKickstarted': True}, [])

    def rootpw_kickstarted_test(self):
        """Test rootpw is marked as kickstarted with kickstart."""
        # if rootpw shows up in the kickstart is should be reported as kickstarted
        self.user_interface.ReadKickstart("rootpw abcef")
        self.assertEqual(self.user_interface.IsRootpwKickstarted, True)
        # and we should be able to set it to False (for example when we override the data from kickstart)
        self.user_interface.SetRootpwKickstarted(False)
        self.assertEqual(self.user_interface.IsRootpwKickstarted, False)
        self.callback.assert_called_with(MODULE_USER_NAME, {'IsRootpwKickstarted': False}, [])

    def _test_kickstart(self, ks_in, ks_out):
        """Test the kickstart string."""
        # Remove extra spaces from the expected output.
        ks_output = "\n".join("".join(line.strip()) for line in ks_out.strip("\n").splitlines())

        # Read a kickstart,
        result = self.user_interface.ReadKickstart(ks_in)
        self.assertEqual({k: v.unpack() for k, v in result.items()}, {"success": True})

        # Generate a kickstart.
        self.assertEqual(ks_output, self.user_interface.GenerateKickstart())

        # Test the properties changed callback.
        self.callback.assert_any_call(DBUS_MODULE_NAMESPACE, {'Kickstarted': True}, [])

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
