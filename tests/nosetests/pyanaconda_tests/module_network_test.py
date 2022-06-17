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
import shutil
from textwrap import dedent
from unittest.mock import patch, Mock

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_dbus_property, \
    check_kickstart_interface, check_task_creation, PropertiesChangedCallback

from pyanaconda.core.constants import FIREWALL_DEFAULT, FIREWALL_ENABLED, \
        FIREWALL_DISABLED, FIREWALL_USE_SYSTEM_DEFAULTS
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.common.constants.objects import FIREWALL
from pyanaconda.modules.common.errors.installation import FirewallConfigurationError, \
    NetworkInstallationError
from pyanaconda.modules.network.network import NetworkService
from pyanaconda.modules.network.network_interface import NetworkInterface
from pyanaconda.modules.network.constants import FirewallMode
from pyanaconda.modules.network.installation import NetworkInstallationTask, \
    ConfigureActivationOnBootTask, HostnameConfigurationTask
from pyanaconda.modules.network.firewall.firewall import FirewallModule
from pyanaconda.modules.network.firewall.firewall_interface import FirewallInterface
from pyanaconda.modules.network.firewall.installation import ConfigureFirewallTask
from pyanaconda.modules.network.kickstart import DEFAULT_DEVICE_SPECIFICATION
from dasbus.typing import *  # pylint: disable=wildcard-import
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
        self.network_module = NetworkService()
        self.network_interface = NetworkInterface(self.network_module)

        # Connect to the properties changed signal.
        self.callback = PropertiesChangedCallback()
        self.network_interface.PropertiesChanged.connect(self.callback)

    def kickstart_properties_test(self):
        """Test kickstart properties."""
        self.assertEqual(self.network_interface.KickstartCommands, ["network", "firewall"])
        self.assertEqual(self.network_interface.KickstartSections, [])
        self.assertEqual(self.network_interface.KickstartAddons, [])

    def _check_dbus_property(self, *args, **kwargs):
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
        self._check_dbus_property(
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
            self.network_interface.GetDracutArguments("ens3", "10.10.10.10", "", False), []
        )

    def log_configuration_state_test(self):
        """Test LogConfigurationState."""
        self.network_interface.LogConfigurationState("message")

    @patch_dbus_publish_object
    @patch('pyanaconda.modules.network.network.devices_ignore_ipv6', return_value=True)
    def install_network_with_task_test(self, devices_ignore_ipv6, publisher):
        """Test InstallNetworkWithTask."""
        self.network_module._disable_ipv6 = True
        self.network_module.nm_client = Mock()
        self.network_module._is_using_persistent_device_names = Mock(return_value=True)
        self.__mock_nm_client_devices(
            [
                ("ens3", "33:33:33:33:33:33", "33:33:33:33:33:33", NM.DeviceType.ETHERNET),
                ("ens4", "44:44:44:44:44:44", "44:44:44:44:44:44", NM.DeviceType.ETHERNET),
                ("ens5", "55:55:55:55:55:55", "55:55:55:55:55:55", NM.DeviceType.ETHERNET)
            ]
        )

        task_path = self.network_interface.InstallNetworkWithTask(False)

        obj = check_task_creation(self, task_path, publisher, NetworkInstallationTask)

        self.assertEqual(obj.implementation._disable_ipv6, True)
        self.assertEqual(obj.implementation._overwrite, False)
        self.assertEqual(obj.implementation._network_ifaces, ["ens3", "ens4", "ens5"])
        self.assertEqual(obj.implementation._configure_persistent_device_names, True)

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.assert_called_once()

    @patch_dbus_publish_object
    def configure_hostname_with_task_test(self, publisher):
        """Test ConfigureHostnameWithTask."""
        self.network_module._hostname = "my_hostname"

        task_path = self.network_interface.ConfigureHostnameWithTask(False)

        obj = check_task_creation(self, task_path, publisher, HostnameConfigurationTask)

        self.assertEqual(obj.implementation._overwrite, False)
        self.assertEqual(obj.implementation._hostname, "my_hostname")

    @patch_dbus_publish_object
    @patch('pyanaconda.modules.network.installation.update_connection_values')
    @patch('pyanaconda.modules.network.installation.find_ifcfg_uuid_of_device')
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

    def rdma_core_requirements_test(self):
        """Test that mocked infiniband devices result in request for rdma-core package."""

        # mock an infiniband device
        self.network_module.nm_client = Mock()
        self.__mock_nm_client_devices(
            [
                ("ibp130s0f0", None,
                 "00:00:0e:4e:fe:80:00:00:00:00:00:00:24:8a:07:03:00:49:d7:5c",
                 NM.DeviceType.INFINIBAND)
            ]
        )

        # check that the rdma-core package is requested
        self.assertEqual(self.network_interface.CollectRequirements(), [
            {
                "type": get_variant(Str, "package"),
                "name": get_variant(Str, "rdma-core"),
                "reason": get_variant(
                    Str,
                    "Necessary for network infiniband device configuration."
                )
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
        self.callback = PropertiesChangedCallback()
        self.firewall_interface.PropertiesChanged.connect(self.callback)

    def _check_dbus_property(self, *args, **kwargs):
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
        self._check_dbus_property(
            "FirewallMode",
            FIREWALL_USE_SYSTEM_DEFAULTS,
        )

    def disable_firewall_test(self):
        """Test if firewall can be disabled."""
        self._check_dbus_property(
            "FirewallMode",
            FIREWALL_DISABLED,
        )

    def toggle_firewall_test(self):
        """Test if firewall can be toggled."""
        self._check_dbus_property(
            "FirewallMode",
            FIREWALL_DISABLED,
        )
        self._check_dbus_property(
            "FirewallMode",
            FIREWALL_ENABLED,
        )

    def set_enabled_ports_test(self):
        """Test if enabled ports can be set."""
        self._check_dbus_property(
            "EnabledPorts",
            ["imap:tcp","1234:udp","47"],
        )
        self._check_dbus_property(
            "EnabledPorts",
            [],
        )
        self._check_dbus_property(
            "EnabledPorts",
            ["1337:udp","9001"],
        )

    def set_trusts_test(self):
        """Tests if trusts can be set."""
        self._check_dbus_property(
            "Trusts",
            ["eth1", "eth2", "enps1337"],
        )
        self._check_dbus_property(
            "Trusts",
            [],
        )
        self._check_dbus_property(
            "Trusts",
            ["virbr0", "wl01", "foo", "bar"],
        )

    def set_enabled_services_test(self):
        """Tests if enabled services can be set."""
        self._check_dbus_property(
            "EnabledServices",
            ["tftp", "rsyncd", "ssh"],
        )
        self._check_dbus_property(
            "EnabledServices",
            [],
        )
        self._check_dbus_property(
            "EnabledServices",
            ["ptp", "syslog", "ssh"],
        )

    def set_disabled_services_test(self):
        """Tests if disabled services can be set."""
        self._check_dbus_property(
            "DisabledServices",
            ["samba", "nfs", "ssh"],
        )
        self._check_dbus_property(
            "DisabledServices",
            [],
        )
        self._check_dbus_property(
            "DisabledServices",
            ["ldap", "ldaps", "ssh"],
        )


class HostnameConfigurationTaskTestCase(unittest.TestCase):
    """Test the Hostname configuration DBus Task."""

    def hostname_config_task_test(self):

        with tempfile.TemporaryDirectory() as sysroot:
            hostname_file_path = os.path.normpath(sysroot + HostnameConfigurationTask.HOSTNAME_CONF_FILE_PATH)
            hostname_dir = os.path.dirname(hostname_file_path)
            os.makedirs(hostname_dir)

            hostname = "bla.bla"

            task = HostnameConfigurationTask(
                sysroot=sysroot,
                hostname=hostname,
                overwrite=True
            )

            task.run()

            with open(hostname_file_path, "r") as f:
                content = f.read()
            self.assertEqual(content, "{}\n".format(hostname))

            shutil.rmtree(hostname_dir)

    def hostname_config_dir_not_exist_test(self):
        """Test hostname configuration task with missing target system directory."""
        with tempfile.TemporaryDirectory() as sysroot:

            hostname = "bla.bla"

            task = HostnameConfigurationTask(
                sysroot=sysroot,
                hostname=hostname,
                overwrite=True
            )

            with self.assertRaises(NetworkInstallationError):
                task.run()


class FirewallConfigurationTaskTestCase(unittest.TestCase):
    """Test the Firewall configuration DBus Task."""

    def setUp(self):
        """Set up the module."""
        self.firewall_module = FirewallModule()
        self.firewall_interface = FirewallInterface(self.firewall_module)

        # Connect to the properties changed signal.
        self.callback = PropertiesChangedCallback()
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
        self.network_module = NetworkService()

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


class InstallationTaskTestCase(unittest.TestCase):

    def setUp(self):
        # The source files are not in "/" but in the mocked root path, which we need
        # to use on the target as well
        self._mocked_root = tempfile.mkdtemp(prefix="network-installation-test")
        self._target_root = os.path.join(self._mocked_root, "mnt/sysimage")
        self._target_mocked_root = os.path.join(self._target_root, self._mocked_root.lstrip("/"))

        # Directories of conifiguration files
        # Will be created as existing or not in tests
        self._sysconf_dir = os.path.dirname(NetworkInstallationTask.SYSCONF_NETWORK_FILE_PATH)
        self._sysctl_dir = os.path.dirname(NetworkInstallationTask.ANACONDA_SYSCTL_FILE_PATH)
        self._resolv_conf_dir = os.path.dirname(NetworkInstallationTask.RESOLV_CONF_FILE_PATH)
        self._network_scripts_dir = NetworkInstallationTask.NETWORK_SCRIPTS_DIR_PATH
        self._prefixdevname_dir = NetworkInstallationTask.PREFIXDEVNAME_DIR_PATH
        self._rename_dir = NetworkInstallationTask.SYSTEMD_NETWORK_CONFIG_DIR
        self._dhclient_dir = os.path.dirname(NetworkInstallationTask.DHCLIENT_FILE_TEMPLATE)

    def _create_config_dirs(self, installer_dirs, target_system_dirs):
        for config_dir in installer_dirs:
            os.makedirs(os.path.join(self._mocked_root, config_dir.lstrip("/")), exist_ok=True)
        for config_dir in target_system_dirs:
            os.makedirs(
                os.path.join(self._target_mocked_root, config_dir.lstrip("/")),
                exist_ok=True
            )

    def tearDown(self):
        shutil.rmtree(self._mocked_root)

    def _dump_config_files(self, conf_dir, files_list):
        for file_name, content in files_list:
            content = dedent(content).strip()
            mocked_conf_dir = os.path.join(self._mocked_root, conf_dir.lstrip("/"))
            with open(os.path.join(mocked_conf_dir, file_name), "w") as f:
                f.write(content)

    def _dump_config_files_in_target(self, conf_dir, files_list):
        for file_name, content in files_list:
            content = dedent(content).strip()
            mocked_conf_dir = os.path.join(self._target_mocked_root, conf_dir.lstrip("/"))
            with open(os.path.join(mocked_conf_dir, file_name), "w") as f:
                f.write(content)

    def _check_config_file(self, conf_dir, file_name, expected_content):
        expected_content = dedent(expected_content).strip()
        mocked_conf_dir = os.path.join(self._target_mocked_root, conf_dir.lstrip("/"))
        with open(os.path.join(mocked_conf_dir, file_name), "r") as f:
            content = f.read().strip()
        self.assertEqual(content, expected_content)

    def _check_config_file_does_not_exist(self, conf_dir, file_name):
        mocked_conf_dir = os.path.join(self._target_mocked_root, conf_dir.lstrip("/"))
        self.assertFalse(os.path.exists(os.path.join(mocked_conf_dir, file_name)))

    def _mock_task_paths(self, task):
        # Mock the paths in the task
        task.SYSCONF_NETWORK_FILE_PATH = self._mocked_root + "/etc/sysconfig/network"
        task.ANACONDA_SYSCTL_FILE_PATH = self._mocked_root + "/etc/sysctl.d/anaconda.conf"
        task.RESOLV_CONF_FILE_PATH = self._mocked_root + "/etc/resolv.conf"
        task.NETWORK_SCRIPTS_DIR_PATH = self._mocked_root + "/etc/sysconfig/network-scripts"
        task.PREFIXDEVNAME_DIR_PATH = self._mocked_root + "/etc/systemd/network"
        task.DHCLIENT_FILE_TEMPLATE = self._mocked_root + "/etc/dhcp/dhclient-{}.conf"
        task.SYSTEMD_NETWORK_CONFIG_DIR = self._mocked_root + "/etc/systemd/network"

    def _create_all_expected_dirs(self):
        # Create directories that are expected to be existing in installer
        # environmant and on target system
        self._create_config_dirs(
            installer_dirs=[
                self._sysconf_dir,
                self._sysctl_dir,
                self._resolv_conf_dir,
                self._network_scripts_dir,
                self._prefixdevname_dir,
                self._rename_dir,
                self._dhclient_dir,
            ],
            target_system_dirs=[
                self._sysconf_dir,
                self._sysctl_dir,
                self._resolv_conf_dir,
                self._network_scripts_dir,
                self._prefixdevname_dir,
                self._rename_dir,
                self._dhclient_dir,
            ]
        )

    def network_instalation_task_no_src_files_test(self):
        """Test the task for network installation with no src files."""

        self._create_all_expected_dirs()

        # Create files that will be copied from installer
        # No files

        # Create files existing on target system (could be used to test overwrite
        # parameter.
        # No files

        # Create the task
        task = NetworkInstallationTask(
            sysroot=self._target_root,
            disable_ipv6=True,
            overwrite=True,
            network_ifaces=["ens3", "ens7"],
            ifname_option_values=["ens3:00:15:17:96:75:0a"],
            # Perhaps does not make sense together with ifname option, but for
            # test it is fine
            configure_persistent_device_names=True,
        )
        self._mock_task_paths(task)
        task.run()
        # Check /etc/sysconfig/network was written by anaconda
        self._check_config_file(
            self._sysconf_dir,
            "network",
            """
            # Created by anaconda
            """
        )
        self._check_config_file(
            self._sysctl_dir,
            "anaconda.conf",
            """
            # Anaconda disabling ipv6 (noipv6 option)
            net.ipv6.conf.all.disable_ipv6=1
            net.ipv6.conf.default.disable_ipv6=1
            """
        )

    def network_instalation_task_all_src_files_test(self):
        """Test the task for network installation with all src files available."""

        self._create_all_expected_dirs()

        # Create files that will be copied from installer
        # All possible files
        self._dump_config_files(
            self._network_scripts_dir,
            (
                ("ifcfg-ens3", "noesis"),
                ("ifcfg-ens7", "noema"),
                ("something-ens7", "res"),
                ("keys-ens7", "clavis"),
                ("route-ens7", "via"),
            )
        )
        self._dump_config_files(
            self._dhclient_dir,
            (
                ("dhclient-ens3.conf", "ens3conf"),
                ("dhclient-ens7.conf", "ens7conf"),
                ("file_that_shoudnt_be_copied.conf", "ens"),
            )
        )
        self._dump_config_files(
            self._sysconf_dir,
            (("network", "Zeug"),)
        )
        self._dump_config_files(
            self._resolv_conf_dir,
            (("resolv.conf", "nomen"),)
        )
        self._dump_config_files(
            self._prefixdevname_dir,
            (
                ("71-net-ifnames-prefix-XYZ", "bla"),
                ("70-shouldnt-be-copied", "blabla"),
            )
        )

        # Create files existing on target system (could be used to test overwrite
        # parameter.
        # No files

        # Create the task
        task = NetworkInstallationTask(
            sysroot=self._target_root,
            disable_ipv6=True,
            overwrite=True,
            network_ifaces=["ens3", "ens7"],
            ifname_option_values=["ens3:00:15:17:96:75:0a"],
            # Perhaps does not make sense together with ifname option, but for
            # test it is fine
            configure_persistent_device_names=True,
        )
        self._mock_task_paths(task)
        task.run()
        # Check /etc/sysconfig/network was written by anaconda
        self._check_config_file(
            self._sysconf_dir,
            "network",
            """
            # Created by anaconda
            """
        )
        self._check_config_file(
            self._sysctl_dir,
            "anaconda.conf",
            """
            # Anaconda disabling ipv6 (noipv6 option)
            net.ipv6.conf.all.disable_ipv6=1
            net.ipv6.conf.default.disable_ipv6=1
            """
        )
        self._check_config_file(
            self._resolv_conf_dir,
            "resolv.conf",
            """
            nomen
            """
        )
        self._check_config_file(
            self._network_scripts_dir,
            "ifcfg-ens3",
            """
            noesis
            """
        )
        self._check_config_file(
            self._network_scripts_dir,
            "ifcfg-ens7",
            """
            noema
            """
        )
        self._check_config_file(
            self._network_scripts_dir,
            "keys-ens7",
            """
            clavis
            """
        )
        self._check_config_file(
            self._network_scripts_dir,
            "route-ens7",
            """
            via
            """
        )
        self._check_config_file_does_not_exist(
            self._network_scripts_dir,
            "something-ens7"
        )
        self._check_config_file(
            self._dhclient_dir,
            "dhclient-ens3.conf",
            """
            ens3conf
            """
        )
        self._check_config_file(
            self._dhclient_dir,
            "dhclient-ens7.conf",
            """
            ens7conf
            """
        )
        self._check_config_file_does_not_exist(
            self._dhclient_dir,
            "file_that_shoudnt_be_copied.conf"
        )
        self._check_config_file(
            self._prefixdevname_dir,
            "71-net-ifnames-prefix-XYZ",
            """
            bla
            """
        )
        content_template = NetworkInstallationTask.INTERFACE_RENAME_FILE_CONTENT_TEMPLATE
        self._check_config_file(
            self._rename_dir,
            "10-anaconda-ifname-ens3.link",
            content_template.format("00:15:17:96:75:0a", "ens3")
        )
        self._check_config_file_does_not_exist(
            self._prefixdevname_dir,
            "70-shouldnt-be-copied"
        )

    def _create_config_files_to_check_overwrite(self):
        self._dump_config_files_in_target(
            self._resolv_conf_dir,
            (("resolv.conf", "original target system content"),)
        )
        self._dump_config_files_in_target(
            self._sysconf_dir,
            (("network", "original target system content"),)
        )
        self._dump_config_files_in_target(
            self._rename_dir,
            (("10-anaconda-ifname-ens3.link", "original target system content"),)
        )
        self._dump_config_files_in_target(
            self._network_scripts_dir,
            (("ifcfg-ens3", "original target system content"),)
        )
        self._dump_config_files_in_target(
            self._dhclient_dir,
            (("dhclient-ens3.conf", "original target system content"),)
        )
        self._dump_config_files_in_target(
            self._prefixdevname_dir,
            (("71-net-ifnames-prefix-XYZ", "original target system content"),)
        )

        self._dump_config_files(
            self._resolv_conf_dir,
            (("resolv.conf", "installer environment content"),)
        )
        self._dump_config_files(
            self._network_scripts_dir,
            (("ifcfg-ens3", "installer environment content"),)
        )
        self._dump_config_files(
            self._dhclient_dir,
            (("dhclient-ens3.conf", "installer environment content"),)
        )
        self._dump_config_files(
            self._prefixdevname_dir,
            (("71-net-ifnames-prefix-XYZ", "installer environment content"),)
        )

    def network_installation_task_overwrite_test(self):
        """Test the task for network installation with overwrite."""

        self._create_all_expected_dirs()
        self._create_config_files_to_check_overwrite()

        task = NetworkInstallationTask(
            sysroot=self._target_root,
            disable_ipv6=False,
            overwrite=True,
            network_ifaces=["ens3", "ens7"],
            ifname_option_values=["ens3:00:15:17:96:75:0a"],
            configure_persistent_device_names=False,
        )
        self._mock_task_paths(task)
        task.run()

        # Files that are created are overwritten
        self._check_config_file(
            self._sysconf_dir,
            "network",
            """
            # Created by anaconda
            """
        )
        content_template = NetworkInstallationTask.INTERFACE_RENAME_FILE_CONTENT_TEMPLATE
        self._check_config_file(
            self._rename_dir,
            "10-anaconda-ifname-ens3.link",
            content_template.format("00:15:17:96:75:0a", "ens3")
        )

        # Files that are copied are not actually overwritten in spite of the
        # task argument
        self._check_config_file(
            self._resolv_conf_dir,
            "resolv.conf",
            """
            original target system content
            """
        )
        self._check_config_file(
            self._network_scripts_dir,
            "ifcfg-ens3",
            """
            original target system content
            """
        )
        self._check_config_file(
            self._dhclient_dir,
            "dhclient-ens3.conf",
            """
            original target system content
            """
        )
        self._check_config_file(
            self._prefixdevname_dir,
            "71-net-ifnames-prefix-XYZ",
            """
            original target system content
            """
        )

    def network_installation_task_no_overwrite_test(self):
        """Test the task for network installation with no overwrite."""

        self._create_all_expected_dirs()
        self._create_config_files_to_check_overwrite()

        task = NetworkInstallationTask(
            sysroot=self._target_root,
            disable_ipv6=False,
            overwrite=False,
            network_ifaces=["ens3", "ens7"],
            ifname_option_values=["ens3:00:15:17:96:75:0a"],
            configure_persistent_device_names=False,
        )
        self._mock_task_paths(task)
        task.run()

        self._check_config_file(
            self._sysconf_dir,
            "network",
            """
            original target system content
            """
        )
        self._check_config_file(
            self._resolv_conf_dir,
            "resolv.conf",
            """
            original target system content
            """
        )
        self._check_config_file(
            self._rename_dir,
            "10-anaconda-ifname-ens3.link",
            """
            original target system content
            """
        )
        self._check_config_file(
            self._network_scripts_dir,
            "ifcfg-ens3",
            """
            original target system content
            """
        )
        self._check_config_file(
            self._dhclient_dir,
            "dhclient-ens3.conf",
            """
            original target system content
            """
        )
        self._check_config_file(
            self._prefixdevname_dir,
            "71-net-ifnames-prefix-XYZ",
            """
            original target system content
            """
        )

    def disable_ipv6_on_system_no_dir_test(self):
        """Test disabling of ipv6 on system when target directory is missing."""

        # Create the task
        task = NetworkInstallationTask(
            sysroot=self._target_root,
            disable_ipv6=True,
            overwrite=False,
            network_ifaces=[],
            ifname_option_values=[],
            # Perhaps does not make sense together with ifname option, but for
            # test it is fine
            configure_persistent_device_names=False,
        )
        self._mock_task_paths(task)

        with self.assertRaises(NetworkInstallationError):
            task._disable_ipv6_on_system(self._target_root)

    def network_instalation_task_missing_target_dir_test(self):
        """Test the task for network installation with missing target system directory."""

        self._create_config_dirs(
            installer_dirs=[
                self._network_scripts_dir,
                self._prefixdevname_dir,
            ],
            target_system_dirs=[
                self._sysconf_dir,
                # target dir for prefixdevname is missing
                # but it should be created by the task
            ]
        )

        self._dump_config_files(
            self._prefixdevname_dir,
            (("71-net-ifnames-prefix-XYZ", "bla"),)
        )

        # Create the task
        task = NetworkInstallationTask(
            sysroot=self._target_root,
            disable_ipv6=False,
            overwrite=True,
            network_ifaces=["ens3", "ens7"],
            ifname_option_values=[],
            configure_persistent_device_names=True,
        )
        self._mock_task_paths(task)
        task.run()

        self._check_config_file(
            self._prefixdevname_dir,
            "71-net-ifnames-prefix-XYZ",
            """
            bla
            """
        )
