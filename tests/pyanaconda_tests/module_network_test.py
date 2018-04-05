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
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>
#
import unittest
from mock import Mock

from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.network.network import NetworkModule
from pyanaconda.modules.network.network_interface import NetworkInterface
from tests.pyanaconda_tests import check_kickstart_interface


class NetworkInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the Network module."""

    def setUp(self):
        """Set up the network module."""
        # Set up the network module.
        self.network_module = NetworkModule()
        self.network_interface = NetworkInterface(self.network_module)

        # Connect to the properties changed signal.
        self.callback = Mock()
        self.network_interface.PropertiesChanged.connect(self.callback)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.network_interface.KickstartCommands, ["network"])
        self.assertEqual(self.network_interface.KickstartSections, [])
        self.assertEqual(self.network_interface.KickstartAddons, [])
        self.callback.assert_not_called()

    def hostname_property_test(self):
        """Test the hostname property."""
        self.network_interface.SetHostname("dot.dot")
        self.assertEqual(self.network_interface.Hostname, "dot.dot")
        self.callback.assert_called_once_with(NETWORK.interface_name, {'Hostname': "dot.dot"}, [])

    def get_current_hostname_test(self):
        """Test getting current hostname does not fail."""
        self.network_interface.GetCurrentHostname()

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.network_interface, ks_in, ks_out)

    def no_kickstart_test(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = """
        # Network information
        network  --hostname=localhost.localdomain
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart_empty_test(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = """
        # Network information
        network  --hostname=localhost.localdomain
        """
        self._test_kickstart(ks_in, ks_out)

    def network_kickstart_test(self):
        """Test the network command.

        Only hostname is implemented in the module for now.
        """
        ks_in = """
        network --device ens7 --bootproto static --ip 192.168.124.200 --netmask 255.255.255.0 --gateway 192.168.124.255 --nameserver 10.34.39.2 --activate --onboot=no --hostname=dot.dot
        """
        ks_out = """
        # Network information
        network  --hostname=dot.dot
        """
        self._test_kickstart(ks_in, ks_out)
