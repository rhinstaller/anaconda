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
import tempfile
import os
from unittest.mock import patch, Mock

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_dbus_property, \
    check_kickstart_interface, check_task_creation

from pyanaconda.core.constants import FIREWALL_DEFAULT, FIREWALL_ENABLED, \
        FIREWALL_DISABLED, FIREWALL_USE_SYSTEM_DEFAULTS
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.common.constants.objects import FIREWALL
from pyanaconda.modules.common.errors.installation import FirewallConfigurationError
from pyanaconda.modules.network.network import NetworkModule
from pyanaconda.modules.network.network_interface import NetworkInterface
from pyanaconda.modules.network.constants import FirewallMode
from pyanaconda.modules.network.installation import NetworkInstallationTask, \
    ConfigureActivationOnBootTask
from pyanaconda.modules.network.firewall.firewall import FirewallModule
from pyanaconda.modules.network.firewall.firewall_interface import FirewallInterface
from pyanaconda.modules.network.firewall.installation import ConfigureFirewallTask
from pyanaconda.modules.network.kickstart import DEFAULT_DEVICE_SPECIFICATION
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.network.initialization import ApplyKickstartTask, \
    SetRealOnbootValuesFromKickstartTask, DumpMissingIfcfgFilesTask, \
    ConsolidateInitramfsConnectionsTask

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

    def _test_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            self,
            NETWORK,
            self.network_interface,
            *args, **kwargs
        )

    @patch("pyanaconda.modules.common.base.base.setlocale")
    @patch("pyanaconda.modules.common.base.base.os")
    def set_locale_test(self, mocked_os, setlocale):
        """Test setting locale of the module."""
        from locale import LC_ALL
        import pyanaconda.core.util
        locale = "en_US.UTF-8"
        mocked_os.environ = {}
        self.network_interface.SetLocale(locale)
        self.assertEqual(mocked_os.environ["LANG"], locale)
        setlocale.assert_called_once_with(LC_ALL, locale)
        self.assertEqual(pyanaconda.core.util._child_env['LANG'], locale)

    def hostname_property_test(self):
        """Test the hostname property."""
        self._test_dbus_property(
            "Hostname",
            "dot.dot",
        )

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

    def create_device_configurations_test(self):
        """Test creating device configurations does not fail."""
        self.network_interface.CreateDeviceConfigurations()

    def get_device_configurations_test(self):
        """Test GetDeviceConfigurations."""
        self.assertListEqual(self.network_interface.GetDeviceConfigurations(), [])

    def network_device_configuration_changed_test(self):
        """Test NetworkDeviceConfigurationChanged."""
        self.network_interface.NetworkDeviceConfigurationChanged()

    def get_dracut_arguments_test(self):
        """Test GetDracutArguments."""
        self.assertListEqual(
            self.network_interface.GetDracutArguments("ens3", "10.10.10.10", ""), []
        )

    def log_configuration_state_test(self):
        """Test LogConfigurationState."""
        self.network_interface.LogConfigurationState("message")

    @patch('pyanaconda.modules.network.network.devices_ignore_ipv6', return_value=True)
    @patch_dbus_publish_object
    def install_network_with_task_test(self, devices_ignore_ipv6, publisher):
        """Test InstallNetworkWithTask."""
        self.network_module._hostname = "my_hostname"
        self.network_module._disable_ipv6 = True
        self.network_module.nm_client = Mock()
        self.__mock_nm_client_devices(
            [
                ("ens3", "33:33:33:33:33:33", "33:33:33:33:33:33", NM.DeviceType.ETHERNET),
                ("ens4", "44:44:44:44:44:44", "44:44:44:44:44:44", NM.DeviceType.ETHERNET),
                ("ens5", "55:55:55:55:55:55", "55:55:55:55:55:55", NM.DeviceType.ETHERNET)
            ]
        )

        task_path = self.network_interface.InstallNetworkWithTask(
            False,
        )

        obj = check_task_creation(self, task_path, publisher, NetworkInstallationTask)

        self.assertEqual(obj.implementation._hostname, "my_hostname")
        self.assertEqual(obj.implementation._disable_ipv6, True)
        self.assertEqual(obj.implementation._overwrite, False)
        self.assertEqual(obj.implementation._network_ifaces, ["ens3", "ens4", "ens5"])

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.assert_called_once()

    @patch('pyanaconda.modules.network.installation.update_connection_values')
    @patch('pyanaconda.modules.network.installation.find_ifcfg_uuid_of_device')
    @patch_dbus_publish_object
    def configure_activation_on_boot_with_task_test(self, find_ifcfg_uuid_of_device,
                                                    update_connection_values, publisher):
        """Test ConfigureActivationOnBootWithTask."""
        self.network_module.nm_client = Mock()
        self.network_module._should_apply_onboot_policy = Mock(return_value=True)
        self.network_module._has_any_onboot_yes_device = Mock(return_value=False)
        self.network_module._get_onboot_ifaces_by_policy = Mock(return_value=["ens4"])

        task_path = self.network_interface.ConfigureActivationOnBootWithTask(
            ["ens3"],
        )

        obj = check_task_creation(self, task_path, publisher, ConfigureActivationOnBootTask)

        self.assertEqual(
            set(obj.implementation._onboot_ifaces),
            set(["ens3", "ens4"])
        )

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.assert_called_once()

    def _mock_supported_devices(self, devices_attributes):
        ret_val = []
        for dev_name, dev_hwaddr, dev_type in devices_attributes:
            dev = Mock()
            dev.device_name = dev_name
            dev.device_hwaddress = dev_hwaddr
            dev.device_type = dev_type
            ret_val.append(dev)
        self.network_module.get_supported_devices = Mock(return_value=ret_val)

    @patch_dbus_publish_object
    def consolidate_initramfs_connections_with_task_test(self, publisher):
        """Test ConsolidateInitramfsConnectionsWithTask."""
        task_path = self.network_interface.ConsolidateInitramfsConnectionsWithTask()

        obj = check_task_creation(self, task_path, publisher, ConsolidateInitramfsConnectionsTask)

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.assert_called_once()

    @patch_dbus_publish_object
    def apply_kickstart_with_task_test(self, publisher):
        """Test ApplyKickstartWithTask."""
        self._mock_supported_devices([("ens3", "", 0)])
        task_path = self.network_interface.ApplyKickstartWithTask()

        obj = check_task_creation(self, task_path, publisher, ApplyKickstartTask)

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.assert_called_once()

    @patch_dbus_publish_object
    def set_real_onboot_values_from_kickstart_with_task_test(self, publisher):
        """Test SetRealOnbootValuesFromKickstartWithTask."""
        self._mock_supported_devices([("ens3", "", 0)])
        task_path = self.network_interface.SetRealOnbootValuesFromKickstartWithTask()

        obj = check_task_creation(self, task_path, publisher, SetRealOnbootValuesFromKickstartTask)

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.assert_called_once()

    @patch_dbus_publish_object
    def dump_missing_ifcfg_files_with_task_test(self, publisher):
        """Test DumpMissingIfcfgFilesWithTask."""
        task_path = self.network_interface.DumpMissingIfcfgFilesWithTask()

        obj = check_task_creation(self, task_path, publisher, DumpMissingIfcfgFilesTask)

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.assert_called_once()

    def __mock_nm_client_devices(self, device_specs):
        """Mock NM Client devices obtained by get_devices() method.
        :param device_specs: list of specifications of devices which are tuples
                             (DEVICE_NAME, PERMANENT_HWADDRESS, HWADDRESS, DEVICE_TYPE)
                             None value of PERMANENT_HWADDRESS means raising Attribute exception
        :type device_specs: list(tuple(str, str, str, int))
        """
        ret_val = []
        for name, perm_hw, hw, dtype in device_specs:
            dev = Mock()
            dev.get_iface.return_value = name
            dev.get_device_type.return_value = dtype
            dev.get_hw_address.return_value = hw
            if perm_hw:
                dev.get_permanent_hw_address.return_value = perm_hw
            else:
                dev.get_permanent_hw_address = Mock(side_effect=AttributeError('mocking no permanent hw address'))
            ret_val.append(dev)
        self.network_module.nm_client.get_devices.return_value = ret_val

    def get_supported_devices_test(self):
        """Test GetSupportedDevices."""
        # No NM available
        self.network_module.nm_client = None
        self.assertEqual(
            self.network_interface.GetSupportedDevices(),
            []
        )

        # Mocked NM
        self.network_module.nm_client = Mock()
        self.__mock_nm_client_devices(
            [
                ("ens3", "33:33:33:33:33:33", "33:33:33:33:33:33", NM.DeviceType.ETHERNET),
                ("ens4", "44:44:44:44:44:44", "44:44:44:44:44:44", NM.DeviceType.ETHERNET),
                # Permanent address is preferred
                ("ens5", "55:55:55:55:55:55", "FF:FF:FF:FF:FF:FF", NM.DeviceType.ETHERNET),
                # Virtual devices don't have permanent hw address
                ("team0", None, "33:33:33:33:33:33", NM.DeviceType.TEAM)
            ]
        )

        devs_infos = self.network_interface.GetSupportedDevices()
        self.assertDictEqual(
            devs_infos[0],
            {
                'device-name': get_variant(Str, "ens3"),
                'hw-address': get_variant(Str, "33:33:33:33:33:33"),
                'device-type': get_variant(Int, NM.DeviceType.ETHERNET)
            }
        )
        self.assertDictEqual(
            devs_infos[1],
            {
                'device-name': get_variant(Str, "ens4"),
                'hw-address': get_variant(Str, "44:44:44:44:44:44"),
                'device-type': get_variant(Int, NM.DeviceType.ETHERNET)
            }
        )
        self.assertDictEqual(
            devs_infos[2],
            {
                'device-name': get_variant(Str, "ens5"),
                'hw-address': get_variant(Str, "55:55:55:55:55:55"),
                'device-type': get_variant(Int, NM.DeviceType.ETHERNET)
            }
        )
        self.assertDictEqual(
            devs_infos[3],
            {
                'device-name': get_variant(Str, "team0"),
                'hw-address': get_variant(Str, "33:33:33:33:33:33"),
                'device-type': get_variant(Int, NM.DeviceType.TEAM)
            }
        )

    def _mock_nm_active_connections(self, connection_specs):
        active_connections = []
        for activated, ifaces in connection_specs:
            con = Mock()
            if activated:
                con.get_state.return_value = NM.ActiveConnectionState.ACTIVATED
            devs = []
            for iface in ifaces:
                dev = Mock()
                dev.get_ip_iface.return_value = iface
                dev.get_iface.return_value = iface
                devs.append(dev)
            con.get_devices.return_value = devs
            active_connections.append(con)
        self.network_module.nm_client.get_active_connections.return_value = active_connections

    def get_activated_interfaces_test(self):
        """Test GetActivatedInterfaces."""
        # No NM available
        self.network_module.nm_client = None
        self.assertEqual(
            self.network_interface.GetActivatedInterfaces(),
            []
        )

        # Mocked NM
        self.network_module.nm_client = Mock()
        self._mock_nm_active_connections(
            [
                (True, ["ens3"]),
                # Slave of bond0
                (True, ["ens5"]),
                # Slave of bond0
                (True, ["ens7"]),
                (True, ["bond0"]),
                (False, ["ens11"]),
                # Not sure if/when this can happen, but we have been supporting it
                (True, ["devA", "devB"]),
                (True, [])
            ]
        )
        self.assertListEqual(
            self.network_interface.GetActivatedInterfaces(),
            ["ens3", "ens5", "ens7", "bond0", "devA", "devB"]
        )

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

    def default_requirements_test(self):
        """Test that by default no packages are required by the network module."""
        self.assertEqual(self.network_interface.CollectRequirements(), [])

    def kickstart_firewall_package_requirements_test(self):
        """Test that firewall command in kickstart results in request for firewalld package."""

        ks_in = "firewall --ftp --http --smtp --ssh"
        ks_out = """
        # Firewall configuration
        firewall --enabled --service=ftp,http,smtp,ssh
        # Network information
        network  --hostname=localhost.localdomain
        """
        self._test_kickstart(ks_in, ks_out)
        self.assertEqual(self.network_interface.CollectRequirements(), [
            {
                "type": get_variant(Str, "package"),
                "name": get_variant(Str, "firewalld"),
                "reason": get_variant(Str, "Requested by the firewall kickstart command.")
            }
        ])

    def teamd_requirements_test(self):
        """Test that mocked team devices result in request for teamd package."""

        # mock a team device
        self.network_module.nm_client = Mock()
        self.__mock_nm_client_devices(
            [
                ("team0", None, "33:33:33:33:33:33", NM.DeviceType.TEAM)
            ]
        )

        # check that the teamd package is requested
        self.assertEqual(self.network_interface.CollectRequirements(), [
            {
                "type": get_variant(Str, "package"),
                "name": get_variant(Str, "teamd"),
                "reason": get_variant(Str, "Necessary for network team device configuration.")
            }
        ])


class FirewallInterfaceTestCase(unittest.TestCase):
    """Test DBus interface of the Firewall module."""

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


class FirewallConfigurationTaskTestCase(unittest.TestCase):
    """Test the Firewall configuration DBus Task."""

    def setUp(self):
        """Set up the module."""
        self.firewall_module = FirewallModule()
        self.firewall_interface = FirewallInterface(self.firewall_module)

        # Connect to the properties changed signal.
        self.callback = Mock()
        self.firewall_interface.PropertiesChanged.connect(self.callback)

    @patch_dbus_publish_object
    def firewall_config_task_basic_test(self, publisher):
        """Test the Firewall configuration task - basic."""
        task_path = self.firewall_interface.InstallWithTask()

        obj = check_task_creation(self, task_path, publisher, ConfigureFirewallTask)

        self.assertEqual(obj.implementation._firewall_mode, FirewallMode.DEFAULT)
        self.assertEqual(obj.implementation._enabled_services, [])
        self.assertEqual(obj.implementation._disabled_services, [])
        self.assertEqual(obj.implementation._enabled_ports, [])
        self.assertEqual(obj.implementation._trusts, [])

    @patch('pyanaconda.core.util.execInSysroot')
    def firewall_config_task_enable_missing_tool_test(self, execInSysroot):
        """Test the Firewall configuration task - enable & missing firewall-offline-cmd."""

        with tempfile.TemporaryDirectory() as sysroot:
            # no firewall-offline-cmd in the sysroot
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.ENABLED,
                                         enabled_services = [],
                                         disabled_services = [],
                                         enabled_ports = [],
                                         trusts = [])
            # should raise an exception
            with self.assertRaises(FirewallConfigurationError):
                task.run()
            # should not call execInSysroot
            execInSysroot.assert_not_called()

    @patch('pyanaconda.core.util.execInSysroot')
    def firewall_config_task_disable_missing_tool_test(self, execInSysroot):
        """Test the Firewall configuration task - disable & missing firewall-offline-cmd"""

        with tempfile.TemporaryDirectory() as sysroot:
            # no firewall-offline-cmd in the sysroot
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.DISABLED,
                                         enabled_services = [],
                                         disabled_services = [],
                                         enabled_ports = [],
                                         trusts = [])
            # should not raise an exception
            task.run()
            # should not call execInSysroot
            execInSysroot.assert_not_called()

    @patch('pyanaconda.core.util.execInSysroot')
    def firewall_config_task_default_missing_tool_test(self, execInSysroot):
        """Test the Firewall configuration task - default & missing firewall-offline-cmd"""

        with tempfile.TemporaryDirectory() as sysroot:
            # no firewall-offline-cmd in the sysroot
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.DEFAULT,
                                         enabled_services = [],
                                         disabled_services = [],
                                         enabled_ports = [],
                                         trusts = [])
            # should not raise an exception
            task.run()
            # should not call execInSysroot
            execInSysroot.assert_not_called()

    @patch('pyanaconda.core.util.execInSysroot')
    def firewall_config_task_system_defaults_missing_tool_test(self, execInSysroot):
        """Test the Firewall configuration task - use-system-defaults & missing firewall-offline-cmd"""

        with tempfile.TemporaryDirectory() as sysroot:
            # no firewall-offline-cmd in the sysroot
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.USE_SYSTEM_DEFAULTS,
                                         enabled_services = [],
                                         disabled_services = [],
                                         enabled_ports = [],
                                         trusts = [])
            # should not raise an exception
            task.run()
            # should not call execInSysroot
            execInSysroot.assert_not_called()

    @patch('pyanaconda.core.util.execInSysroot')
    def firewall_config_task_default_test(self, execInSysroot):
        """Test the Firewall configuration task - default."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            self.assertTrue(os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd")))
            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.DEFAULT,
                                         enabled_services = [],
                                         disabled_services = [],
                                         enabled_ports = [],
                                         trusts = [])
            task.run()

            execInSysroot.assert_called_once_with('/usr/bin/firewall-offline-cmd',
                                                  ['--enabled', '--service=ssh'], root=sysroot)

    @patch('pyanaconda.core.util.execInSysroot')
    def firewall_config_task_enable_test(self, execInSysroot):
        """Test the Firewall configuration task - enable."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            self.assertTrue(os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd")))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.ENABLED,
                                         enabled_services = [],
                                         disabled_services = [],
                                         enabled_ports = [],
                                         trusts = [])
            task.run()

            execInSysroot.assert_called_once_with('/usr/bin/firewall-offline-cmd', ['--enabled', '--service=ssh'], root=sysroot)

    @patch('pyanaconda.core.util.execInSysroot')
    def firewall_config_task_enable_with_options_test(self, execInSysroot):
        """Test the Firewall configuration task - enable with options."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            self.assertTrue(os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd")))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.ENABLED,
                                         enabled_services = ["smnp"],
                                         disabled_services = ["tftp"],
                                         enabled_ports = ["22001:tcp","6400:udp"],
                                         trusts = ["eth1"])
            task.run()

            execInSysroot.assert_called_once_with('/usr/bin/firewall-offline-cmd',
                                                  ['--enabled', '--service=ssh', '--trust=eth1', '--port=22001:tcp',
                                                   '--port=6400:udp', '--remove-service=tftp', '--service=smnp'],
                                                  root=sysroot)

    @patch('pyanaconda.core.util.execInSysroot')
    def firewall_config_task_disable_ssh_test(self, execInSysroot):
        """Test the Firewall configuration task - test SSH can be disabled."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            self.assertTrue(os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd")))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.ENABLED,
                                         enabled_services = [],
                                         disabled_services = ["ssh"],
                                         enabled_ports = [],
                                         trusts = [])
            task.run()

            execInSysroot.assert_called_once_with('/usr/bin/firewall-offline-cmd',
                                                  ['--enabled', '--remove-service=ssh'],
                                                  root=sysroot)

    @patch('pyanaconda.core.util.execInSysroot')
    def firewall_config_task_enable_disable_service_test(self, execInSysroot):
        """Test the Firewall configuration task - test enabling & disabling the same service"""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            self.assertTrue(os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd")))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.ENABLED,
                                         enabled_services = ["tftp"],
                                         disabled_services = ["tftp"],
                                         enabled_ports = [],
                                         trusts = [])
            task.run()

            execInSysroot.assert_called_once_with('/usr/bin/firewall-offline-cmd',
                                                  ['--enabled', '--service=ssh', '--remove-service=tftp', '--service=tftp'],
                                                  root=sysroot)

    @patch('pyanaconda.core.util.execInSysroot')
    def firewall_config_task_disable_test(self, execInSysroot):
        """Test the Firewall configuration task - disable."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            self.assertTrue(os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd")))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.DISABLED,
                                         enabled_services = [],
                                         disabled_services = [],
                                         enabled_ports = [],
                                         trusts = [])
            task.run()

            execInSysroot.assert_called_once_with('/usr/bin/firewall-offline-cmd', ['--disabled', '--service=ssh'], root=sysroot)

    @patch('pyanaconda.core.util.execInSysroot')
    def firewall_config_task_disable_with_options_test(self, execInSysroot):
        """Test the Firewall configuration task - disable with options."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            self.assertTrue(os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd")))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.DISABLED,
                                         enabled_services = ["smnp"],
                                         disabled_services = ["tftp"],
                                         enabled_ports = ["22001:tcp","6400:udp"],
                                         trusts = ["eth1"])
            task.run()

            # even in disable mode, we still forward all the options to firewall-offline-cmd
            execInSysroot.assert_called_once_with('/usr/bin/firewall-offline-cmd',
                                                  ['--disabled', '--service=ssh', '--trust=eth1', '--port=22001:tcp',
                                                   '--port=6400:udp', '--remove-service=tftp', '--service=smnp'],
                                                  root=sysroot)

    @patch('pyanaconda.core.util.execInSysroot')
    def firewall_config_task_use_system_defaults_test(self, execInSysroot):
        """Test the Firewall configuration task - use system defaults."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            self.assertTrue(os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd")))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.USE_SYSTEM_DEFAULTS,
                                         enabled_services = [],
                                         disabled_services = [],
                                         enabled_ports = [],
                                         trusts = [])
            task.run()

            # firewall-offline-cmd should not be called in use-system-defaults mode
            execInSysroot.assert_not_called()


class NetworkModuleTestCase(unittest.TestCase):
    """Test Network module."""

    def setUp(self):
        """Set up the network module."""
        # Set up the network module.
        self.network_module = NetworkModule()

    def apply_boot_options_ksdevice_test(self):
        """Test _apply_boot_options function for 'ksdevice'."""
        self.assertEqual(
            self.network_module.default_device_specification,
            DEFAULT_DEVICE_SPECIFICATION
        )
        mocked_kernel_args = {"something": "else"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.default_device_specification,
            DEFAULT_DEVICE_SPECIFICATION
        )
        mocked_kernel_args = {'ksdevice': "ens3"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.default_device_specification,
            "ens3"
        )
        mocked_kernel_args = {}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.default_device_specification,
            "ens3"
        )

    def apply_boot_options_noipv6_test(self):
        """Test _apply_boot_options function for 'noipv6'."""
        self.assertEqual(
            self.network_module.disable_ipv6,
            False
        )
        mocked_kernel_args = {"something": "else"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.disable_ipv6,
            False
        )
        mocked_kernel_args = {'noipv6': None}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.disable_ipv6,
            True
        )
        mocked_kernel_args = {}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.disable_ipv6,
            True
        )

    def apply_boot_options_bootif_test(self):
        """Test _apply_boot_options function for 'BOOTIF'."""
        self.assertEqual(
            self.network_module.bootif,
            None
        )
        mocked_kernel_args = {"something": "else"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.bootif,
            None
        )
        mocked_kernel_args = {'BOOTIF': "01-f4-ce-46-2c-44-7a"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.bootif,
            "F4:CE:46:2C:44:7A"
        )
        mocked_kernel_args = {}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.bootif,
            "F4:CE:46:2C:44:7A"
        )
        # Do not crash on trash
        mocked_kernel_args = {'BOOTIF': ""}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.bootif,
            ""
        )

    def apply_boot_options_ifname_test(self):
        """Test _apply_boot_options function for 'ifname'."""
        self.assertEqual(
            self.network_module.ifname_option_values,
            []
        )
        mocked_kernel_args = {"something": "else"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.ifname_option_values,
            []
        )
        mocked_kernel_args = {'ifname': "ens3f0:00:15:17:96:75:0a"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.ifname_option_values,
            ["ens3f0:00:15:17:96:75:0a"]
        )
        mocked_kernel_args = {'ifname': "ens3f0:00:15:17:96:75:0a ens3f1:00:15:17:96:75:0b"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.ifname_option_values,
            ["ens3f0:00:15:17:96:75:0a", "ens3f1:00:15:17:96:75:0b"]
        )
        mocked_kernel_args = {}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.ifname_option_values,
            ["ens3f0:00:15:17:96:75:0a", "ens3f1:00:15:17:96:75:0b"]
        )
        mocked_kernel_args = {'ifname': "bla bla"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertEqual(
            self.network_module.ifname_option_values,
            ["bla", "bla"]
        )

    def apply_boot_options_test(self):
        """Test _apply_boot_options for multiple options."""
        self.assertListEqual(
            [
                self.network_module.bootif,
                self.network_module.ifname_option_values,
                self.network_module.disable_ipv6,
                self.network_module.default_device_specification,
            ],
            [
                None,
                [],
                False,
                DEFAULT_DEVICE_SPECIFICATION,
            ]
        )
        mocked_kernel_args = {
            'something_else': None,
            'ifname': 'ens3f0:00:15:17:96:75:0a ens3f1:00:15:17:96:75:0b',
            'something': 'completely_else',
            'BOOTIF': '01-f4-ce-46-2c-44-7a',
            'noipv6': None,
            'ksdevice': 'ens11',
        }
        self.network_module._apply_boot_options(mocked_kernel_args)
        self.assertListEqual(
            [
                self.network_module.bootif,
                self.network_module.ifname_option_values,
                self.network_module.disable_ipv6,
                self.network_module.default_device_specification,
            ],
            [
                "F4:CE:46:2C:44:7A",
                ["ens3f0:00:15:17:96:75:0a", "ens3f1:00:15:17:96:75:0b"],
                True,
                "ens11",
            ]
        )
