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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
from mock import Mock
from pykickstart.constants import SELINUX_ENFORCING

from pyanaconda.modules.common.constants.services import SECURITY
from pyanaconda.dbus.typing import get_variant, Str, List
from pyanaconda.modules.security.security import SecurityModule
from pyanaconda.modules.security.security_interface import SecurityInterface
from tests.nosetests.pyanaconda_tests import check_kickstart_interface


class SecurityInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the Security module."""

    def setUp(self):
        """Set up the security module."""
        # Set up the security module.
        self.security_module = SecurityModule()
        self.security_interface = SecurityInterface(self.security_module)

        # Connect to the properties changed signal.
        self.callback = Mock()
        self.security_interface.PropertiesChanged.connect(self.callback)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.security_interface.KickstartCommands,
                         ["auth", "authconfig", "authselect", "selinux", "realm"])
        self.assertEqual(self.security_interface.KickstartSections, [])
        self.assertEqual(self.security_interface.KickstartAddons, [])
        self.callback.assert_not_called()

    def selinux_property_test(self):
        """Test the selinux property."""
        self.security_interface.SetSELinux(SELINUX_ENFORCING)
        self.assertEqual(self.security_interface.SELinux, SELINUX_ENFORCING)
        self.callback.assert_called_once_with(SECURITY.interface_name, {'SELinux': SELINUX_ENFORCING}, [])

    def authselect_property_test(self):
        """Test the authselect property."""
        self.security_interface.SetAuthselect(["sssd", "with-mkhomedir"])
        self.assertEqual(self.security_interface.Authselect, ["sssd", "with-mkhomedir"])
        self.callback.assert_called_once_with(SECURITY.interface_name, {'Authselect': ["sssd", "with-mkhomedir"]}, [])

    def authconfig_property_test(self):
        """Test the authconfig property."""
        self.security_interface.SetAuthconfig(["--passalgo=sha512", "--useshadow"])
        self.assertEqual(self.security_interface.Authconfig, ["--passalgo=sha512", "--useshadow"])
        self.callback.assert_called_once_with(SECURITY.interface_name, {'Authconfig': ["--passalgo=sha512", "--useshadow"]}, [])

    def realm_property_test(self):
        """Test the realm property."""
        realm_in = {
            "name": "domain.example.com",
            "discover-options": ["--client-software=sssd"],
            "join-options": ["--one-time-password=password"]
        }

        realm_out = {
            "name": get_variant(Str, "domain.example.com"),
            "discover-options": get_variant(List[Str], ["--client-software=sssd"]),
            "join-options": get_variant(List[Str], ["--one-time-password=password"])
        }

        self.security_interface.SetRealm(realm_in)
        self.assertEqual(realm_out, self.security_interface.Realm)
        self.callback.assert_called_once_with(SECURITY.interface_name, {'Realm': realm_out}, [])

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.security_interface, ks_in, ks_out)

    def no_kickstart_test(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def kickstart_empty_test(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = ""
        self._test_kickstart(ks_in, ks_out)

    def selinux_kickstart_test(self):
        """Test the selinux command."""
        ks_in = """
        selinux --permissive
        """
        ks_out = """
        # SELinux configuration
        selinux --permissive
        """
        self._test_kickstart(ks_in, ks_out)

    def auth_kickstart_test(self):
        """Test the auth command."""
        ks_in = """
        auth --passalgo=sha512 --useshadow
        """
        ks_out = """
        # System authorization information
        auth --passalgo=sha512 --useshadow
        """
        self._test_kickstart(ks_in, ks_out)

    def authconfig_kickstart_test(self):
        """Test the authconfig command."""
        ks_in = """
        authconfig --passalgo=sha512 --useshadow
        """
        ks_out = """
        # System authorization information
        auth --passalgo=sha512 --useshadow
        """
        self._test_kickstart(ks_in, ks_out)

    def authselect_kickstart_test(self):
        """Test the authselect command."""
        ks_in = """
        authselect select sssd with-mkhomedir
        """
        ks_out = """
        # System authorization information
        authselect select sssd with-mkhomedir
        """
        self._test_kickstart(ks_in, ks_out)

    def realm_kickstart_test(self):
        """Test the realm command."""
        ks_in = """
        realm join --one-time-password=password --client-software=sssd domain.example.com
        """
        ks_out = """
        # Realm or domain membership
        realm join --one-time-password=password --client-software=sssd domain.example.com
        """
        self._test_kickstart(ks_in, ks_out)
