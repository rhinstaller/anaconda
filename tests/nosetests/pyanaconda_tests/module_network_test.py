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
from unittest.mock import patch, Mock

from pyanaconda.core.constants import FIREWALL_DEFAULT, FIREWALL_ENABLED, \
        FIREWALL_DISABLED, FIREWALL_USE_SYSTEM_DEFAULTS
from pyanaconda.modules.common.task import TaskInterface
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.common.constants.objects import FIREWALL
from pyanaconda.modules.network.network import NetworkModule
from pyanaconda.modules.network.network_interface import NetworkInterface
from pyanaconda.modules.network.installation import NetworkInstallationTask
from pyanaconda.modules.network.firewall.firewall import FirewallModule
from pyanaconda.modules.network.firewall.firewall_interface import FirewallInterface
from tests.nosetests.pyanaconda_tests import check_kickstart_interface, check_dbus_property
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

class MockedSimpleIfcfgFileGetter():
    def __init__(self, values):
        self.values = {}
        for key, value in values:
            self.values[key] = value
    def get(self, key):
        return self.values.get(key, "")
    def read(self):
        pass

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

    @patch('pyanaconda.modules.network.network.find_ifcfg_uuid_of_device',
           return_value="mocked_uuid")
    @patch('pyanaconda.modules.network.network.devices_ignore_ipv6', return_value=True)
    @patch('pyanaconda.dbus.DBus.publish_object')
    def install_network_with_task_test(self, publisher, devices_ignore_ipv6,
                                       find_ifcfg_uuid_of_device):
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
        self.network_module._should_apply_onboot_policy = Mock(return_value=True)
        self.network_module._has_any_onboot_yes_device = Mock(return_value=False)
        self.network_module._get_onboot_ifaces_by_policy = Mock(return_value=["ens4"])

        task_path = self.network_interface.InstallNetworkWithTask(
            "/mnt/sysimage",
            ["ens3"],
            False,
        )

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, NetworkInstallationTask)
        self.assertEqual(obj.implementation._sysroot, "/mnt/sysimage")
        self.assertEqual(obj.implementation._hostname, "my_hostname")
        self.assertEqual(obj.implementation._disable_ipv6, True)
        self.assertEqual(obj.implementation._overwrite, False)
        self.assertEqual(obj.implementation._onboot_yes_uuids, ["mocked_uuid", "mocked_uuid"])
        self.assertEqual(obj.implementation._network_ifaces, ["ens3", "ens4", "ens5"])

        self.assertSetEqual(set(self.network_module._onboot_yes_ifaces), set(["ens3", "ens4"]))

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.called_once()

    def _mock_supported_devices(self, devices_attributes):
        ret_val = []
        for dev_name, dev_hwaddr, dev_type in devices_attributes:
            dev = Mock()
            dev.device_name = dev_name
            dev.device_hwaddress = dev_hwaddr
            dev.device_type = dev_type
            ret_val.append(dev)
        self.network_module.get_supported_devices = Mock(return_value=ret_val)

    @patch('pyanaconda.dbus.DBus.publish_object')
    def consolidate_initramfs_connections_with_task_test(self, publisher):
        """Test ConsolidateInitramfsConnectionsWithTask."""
        task_path = self.network_interface.ConsolidateInitramfsConnectionsWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, ConsolidateInitramfsConnectionsTask)

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.called_once()

    @patch('pyanaconda.dbus.DBus.publish_object')
    def apply_kickstart_with_task_test(self, publisher):
        """Test ApplyKickstartWithTask."""
        self._mock_supported_devices([("ens3", "", 0)])
        task_path = self.network_interface.ApplyKickstartWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, ApplyKickstartTask)

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.called_once()

    @patch('pyanaconda.dbus.DBus.publish_object')
    def set_real_onboot_values_from_kickstart_with_task_test(self, publisher):
        """Test SetRealOnbootValuesFromKickstartWithTask."""
        self._mock_supported_devices([("ens3", "", 0)])
        task_path = self.network_interface.SetRealOnbootValuesFromKickstartWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, SetRealOnbootValuesFromKickstartTask)

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.called_once()

    @patch('pyanaconda.dbus.DBus.publish_object')
    def dump_missing_ifcfg_files_with_task_test(self, publisher):
        """Test DumpMissingIfcfgFilesWithTask."""
        task_path = self.network_interface.DumpMissingIfcfgFilesWithTask()

        publisher.assert_called_once()
        object_path, obj = publisher.call_args[0]

        self.assertEqual(task_path, object_path)
        self.assertIsInstance(obj, TaskInterface)

        self.assertIsInstance(obj.implementation, DumpMissingIfcfgFilesTask)

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.called_once()

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

    def set_connection_onboot_value_test(self):
        """Test SetConnectionOnbootValue."""
        self.network_interface.SetConnectionOnbootValue(
            "ddc991d3-a495-4f24-9416-30a6fae01469",
            False
        )

    @patch('pyanaconda.modules.network.network.get_ifcfg_file')
    def get_connection_onboot_value_test(self, get_ifcfg_file):
        """Test GetConnectionOnbootValue."""
        get_ifcfg_file.return_value = MockedSimpleIfcfgFileGetter([('ONBOOT', "yes")])
        self.assertEqual(
            self.network_interface.GetConnectionOnbootValue("ddc991d3-a495-4f24-9416-30a6fae01469"),
            True
        )
        get_ifcfg_file.return_value = MockedSimpleIfcfgFileGetter([])
        self.assertEqual(
            self.network_interface.GetConnectionOnbootValue("ddc991d3-a495-4f24-9416-30a6fae01469"),
            True
        )
        get_ifcfg_file.return_value = MockedSimpleIfcfgFileGetter([('ONBOOT', "no")])
        self.assertEqual(
            self.network_interface.GetConnectionOnbootValue("ddc991d3-a495-4f24-9416-30a6fae01469"),
            False
        )
        get_ifcfg_file.return_value = MockedSimpleIfcfgFileGetter([('ONBOOT', "whatever")])
        self.assertEqual(
            self.network_interface.GetConnectionOnbootValue("ddc991d3-a495-4f24-9416-30a6fae01469"),
            True
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
