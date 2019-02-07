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

from pyanaconda.core.constants import FIREWALL_DEFAULT, FIREWALL_ENABLED, \
        FIREWALL_DISABLED, FIREWALL_USE_SYSTEM_DEFAULTS
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.common.constants.objects import FIREWALL
from pyanaconda.modules.network.network import NetworkModule
from pyanaconda.modules.network.network_interface import NetworkInterface
from pyanaconda.modules.network.firewall.firewall import FirewallModule
from pyanaconda.modules.network.firewall.firewall_interface import FirewallInterface
from tests.nosetests.pyanaconda_tests import check_kickstart_interface, check_dbus_property

import gi
gi.require_version("NM", "1.0")
from gi.repository import NM


class MockedNMClient():
    def __init__(self):
        self.state = NM.State.DISCONNECTED
        self.state_callback = None
    def _connect_state_changed(self, callback):
        self.state_callback = callback
    def _set_state(self, state):
        self.state = state
        self.state_callback(state)
    def get_state(self):
        return self.state


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
        self.assertEqual(self.network_interface.KickstartCommands, ["network", "firewall"])
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

    def connected_test(self):
        """Test getting connectivity status does not fail."""
        connected = self.network_interface.Connected
        self.assertIn(connected, (True, False))

    def connecting_test(self):
        """Test checking connecting status does not fail."""
        self.network_interface.IsConnecting()

    def mocked_client_connectivity_test(self):
        """Test connectivity properties with mocked NMClient."""
        nm_client = MockedNMClient()
        nm_client._connect_state_changed(self.network_module._nm_state_changed)
        self.network_module.nm_client = nm_client

        nm_client._set_state(NM.State.CONNECTED_LOCAL)
        self.assertTrue(self.network_interface.Connected)

        nm_client._set_state(NM.State.DISCONNECTED)
        self.assertFalse(self.network_interface.Connected)
        self.callback.assert_called_with(NETWORK.interface_name, {'Connected': False}, [])
        self.assertFalse(self.network_interface.IsConnecting())

        nm_client._set_state(NM.State.CONNECTED_SITE)
        self.assertTrue(self.network_interface.Connected)
        self.callback.assert_called_with(NETWORK.interface_name, {'Connected': True}, [])
        self.assertFalse(self.network_interface.IsConnecting())

        nm_client._set_state(NM.State.CONNECTED_GLOBAL)
        self.assertTrue(self.network_interface.Connected)
        self.callback.assert_called_with(NETWORK.interface_name, {'Connected': True}, [])
        self.assertFalse(self.network_interface.IsConnecting())

        nm_client._set_state(NM.State.CONNECTING)
        self.assertFalse(self.network_interface.Connected)
        self.callback.assert_called_with(NETWORK.interface_name, {'Connected': False}, [])
        self.assertTrue(self.network_interface.IsConnecting())

        nm_client._set_state(NM.State.CONNECTED_LOCAL)
        self.assertTrue(self.network_interface.Connected)
        self.callback.assert_called_with(NETWORK.interface_name, {'Connected': True}, [])
        self.assertFalse(self.network_interface.IsConnecting())

    def nm_availability_test(self):
        self.network_module.nm_client = None
        self.assertTrue(self.network_interface.Connected)
        self.assertFalse(self.network_interface.IsConnecting())

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

        In case of kickstart-only network configuration the original commands are
        preserved instead of generating the commands from ifcfg files which happens
        if there has been any non-kickstart (UI) configuration.
        """
        ks_in = """
        network --device ens7 --bootproto static --ip 192.168.124.200 --netmask 255.255.255.0 --gateway 192.168.124.255 --nameserver 10.34.39.2 --activate --onboot=no --hostname=dot.dot
        """
        ks_out = """
        # Network information
        network  --bootproto=static --device=ens7 --gateway=192.168.124.255 --hostname=dot.dot --ip=192.168.124.200 --nameserver=10.34.39.2 --netmask=255.255.255.0 --onboot=off --activate
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart_firewall_basic_test(self):
        """Test basic firewall command usage."""
        ks_in = "firewall --enable --port=imap:tcp,1234:udp,47 --trust=eth0,eth1 --service=ptp,syslog,ssh --remove-service=tftp,ssh"
        ks_out = """
        # Firewall configuration
        firewall --enabled --port=imap:tcp,1234:udp,47:tcp --trust=eth0,eth1 --service=ptp,syslog,ssh --remove-service=tftp,ssh
        # Network information
        network  --hostname=localhost.localdomain
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart_firewall_disable_test(self):
        """Test firewall --disabled."""
        ks_in = "firewall --disabled"
        ks_out = """
        # Firewall configuration
        firewall --disabled
        # Network information
        network  --hostname=localhost.localdomain
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart_firewall_disable_with_options_test(self):
        """Test firewall --disabled with options."""
        # apparently Pykickstart dumps any additional options if --disabled is used
        ks_in = "firewall --disable --port=imap:tcp,1234:udp,47 --trust=eth0,eth1 --service=ptp,syslog,ssh --remove-service=tftp,ssh"
        ks_out = """
        # Firewall configuration
        firewall --disabled
        # Network information
        network  --hostname=localhost.localdomain
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart_firewall_use_system_defaults_test(self):
        """Test firewall --use-system-defaults."""
        ks_in = "firewall --use-system-defaults"
        ks_out = """
        # Firewall configuration
        firewall --use-system-defaults
        # Network information
        network  --hostname=localhost.localdomain
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart_firewall_use_system_defaults_with_options_test(self):
        """Test firewall --use-system-defaults."""
        # looks like --use-system-defaults also eats any additional options
        ks_in = "firewall --use-system-defaults --port=imap:tcp,1234:udp,47 --trust=eth0,eth1 --service=ptp,syslog,ssh --remove-service=tftp,ssh"
        ks_out = """
        # Firewall configuration
        firewall --use-system-defaults
        # Network information
        network  --hostname=localhost.localdomain
        """
        self._test_kickstart(ks_in, ks_out)

    def kickstart_firewall_service_options_test(self):
        """Test firewall with individual service options.

        The firewall command supports enabling some well known services, such as ssh or smtp, via dedicated
        options. The services should then end up in the --service list in the output.
        """
        ks_in = "firewall --ftp --http --smtp --ssh"
        ks_out = """
        # Firewall configuration
        firewall --enabled --service=ftp,http,smtp,ssh
        # Network information
        network  --hostname=localhost.localdomain
        """
        self._test_kickstart(ks_in, ks_out)


class FirewallInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the disk initialization module."""

    def setUp(self):
        """Set up the module."""
        self.firewall_module = FirewallModule()
        self.firewall_interface = FirewallInterface(self.firewall_module)

        # Connect to the properties changed signal.
        self.callback = Mock()
        self.firewall_interface.PropertiesChanged.connect(self.callback)

    def _test_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            FIREWALL,
            self.firewall_interface,
            *args, **kwargs
        )

    def _test_kickstart(self, ks_in, ks_out):
        check_kickstart_interface(self, self.firewall_interface, ks_in, ks_out)

    def default_property_values_test(self):
        """Test the default firewall module values are as expected."""
        self.assertFalse(self.firewall_interface.FirewallKickstarted)
        self.assertEqual(self.firewall_interface.FirewallMode, FIREWALL_DEFAULT)
        self.assertListEqual(self.firewall_interface.EnabledPorts, [])
        self.assertListEqual(self.firewall_interface.Trusts, [])
        self.assertListEqual(self.firewall_interface.EnabledServices, [])
        self.assertListEqual(self.firewall_interface.DisabledServices, [])

    def set_use_system_defaults_test(self):
        """Test if the use-system-firewall-defaults option can be set."""
        self._test_dbus_property(
            "FirewallMode",
            FIREWALL_USE_SYSTEM_DEFAULTS,
        )

    def disable_firewall_test(self):
        """Test if firewall can be disabled."""
        self._test_dbus_property(
            "FirewallMode",
            FIREWALL_DISABLED,
        )

    def toggle_firewall_test(self):
        """Test if firewall can be toggled."""
        self._test_dbus_property(
            "FirewallMode",
            FIREWALL_DISABLED,
        )
        self._test_dbus_property(
            "FirewallMode",
            FIREWALL_ENABLED,
        )

    def set_enabled_ports_test(self):
        """Test if enabled ports can be set."""
        self._test_dbus_property(
            "EnabledPorts",
            ["imap:tcp","1234:udp","47"],
        )
        self._test_dbus_property(
            "EnabledPorts",
            [],
        )
        self._test_dbus_property(
            "EnabledPorts",
            ["1337:udp","9001"],
        )

    def set_trusts_test(self):
        """Tests if trusts can be set."""
        self._test_dbus_property(
            "Trusts",
            ["eth1", "eth2", "enps1337"],
        )
        self._test_dbus_property(
            "Trusts",
            [],
        )
        self._test_dbus_property(
            "Trusts",
            ["virbr0", "wl01", "foo", "bar"],
        )

    def set_enabled_services_test(self):
        """Tests if enabled services can be set."""
        self._test_dbus_property(
            "EnabledServices",
            ["tftp", "rsyncd", "ssh"],
        )
        self._test_dbus_property(
            "EnabledServices",
            [],
        )
        self._test_dbus_property(
            "EnabledServices",
            ["ptp", "syslog", "ssh"],
        )

    def set_disabled_services_test(self):
        """Tests if disabled services can be set."""
        self._test_dbus_property(
            "DisabledServices",
            ["samba", "nfs", "ssh"],
        )
        self._test_dbus_property(
            "DisabledServices",
            [],
        )
        self._test_dbus_property(
            "DisabledServices",
            ["ldap", "ldaps", "ssh"],
        )
