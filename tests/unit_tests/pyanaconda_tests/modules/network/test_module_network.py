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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>
#
import os
import shutil
import tempfile
import unittest
from textwrap import dedent
from unittest.mock import Mock, patch

import gi
import pytest
from dasbus.signal import Signal
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import (
    FIREWALL_DEFAULT,
    FIREWALL_DISABLED,
    FIREWALL_ENABLED,
    FIREWALL_USE_SYSTEM_DEFAULTS,
    NETWORK_CAPABILITY_TEAM,
)
from pyanaconda.core.kernel import KernelArguments
from pyanaconda.modules.common.constants.objects import FIREWALL
from pyanaconda.modules.common.constants.services import NETWORK
from pyanaconda.modules.common.errors.installation import (
    FirewallConfigurationError,
    NetworkInstallationError,
)
from pyanaconda.modules.network.constants import FirewallMode
from pyanaconda.modules.network.firewall.firewall import FirewallModule
from pyanaconda.modules.network.firewall.firewall_interface import FirewallInterface
from pyanaconda.modules.network.firewall.installation import ConfigureFirewallTask
from pyanaconda.modules.network.initialization import (
    ApplyKickstartTask,
    DumpMissingConfigFilesTask,
)
from pyanaconda.modules.network.installation import (
    ConfigureActivationOnBootTask,
    HostnameConfigurationTask,
    NetworkInstallationTask,
)
from pyanaconda.modules.network.kickstart import DEFAULT_DEVICE_SPECIFICATION
from pyanaconda.modules.network.network import NetworkService
from pyanaconda.modules.network.network_interface import NetworkInterface
from tests.unit_tests.pyanaconda_tests import (
    PropertiesChangedCallback,
    check_dbus_property,
    check_kickstart_interface,
    check_task_creation,
    patch_dbus_publish_object,
)

gi.require_version("NM", "1.0")
from gi.repository import NM


class MockedNMClient():
    def __init__(self):
        self.state = NM.State.DISCONNECTED
        self.state_callback = None
        self.capabilities = []
        self.capabilities_callback = None

    def _connect_state_changed(self, callback):
        self.state_callback = callback

    def _set_state(self, state):
        self.state = state
        self.state_callback(state)

    def get_state(self):
        return self.state

    def _connect_capabilities_changed(self, callback):
        self.capabilities_callback = callback

    def _set_capabilities(self, caps):
        self.capabilities = caps
        self.capabilities_callback(caps)

    def get_capabilities(self):
        return self.capabilities


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

    def test_kickstart_properties(self):
        """Test kickstart properties."""
        assert self.network_interface.KickstartCommands == ["network", "firewall"]
        assert self.network_interface.KickstartSections == []
        assert self.network_interface.KickstartAddons == []

    def _check_dbus_property(self, *args, **kwargs):
        check_dbus_property(
            NETWORK,
            self.network_interface,
            *args, **kwargs
        )

    @patch("pyanaconda.modules.common.base.base.setlocale")
    @patch("pyanaconda.modules.common.base.base.os")
    def test_set_locale(self, mocked_os, setlocale):
        """Test setting locale of the module."""
        from locale import LC_ALL

        import pyanaconda.core.util
        locale = "en_US.UTF-8"
        mocked_os.environ = {}
        self.network_interface.SetLocale(locale)
        assert mocked_os.environ["LANG"] == locale
        setlocale.assert_called_once_with(LC_ALL, locale)
        assert pyanaconda.core.util._child_env['LANG'] == locale

    def test_hostname_property(self):
        """Test the hostname property."""
        self._check_dbus_property(
            "Hostname",
            "dot.dot",
        )

    @patch("pyanaconda.modules.network.network.conf")
    def test_hostname_proxy(self, conf_mock):
        """Test the hostname proxy."""
        conf_mock.system.provides_system_bus = False
        service = NetworkService()
        assert not service._hostname_service_proxy

        conf_mock.system.provides_system_bus = True
        service = NetworkService()
        assert service._hostname_service_proxy

    def test_get_current_hostname(self):
        """Test the GetCurrentHostname method."""
        hostname_mock = Mock()
        hostname_mock.Hostname = "dot.dot"

        self.network_module._hostname_service_proxy = None
        assert self.network_interface.GetCurrentHostname() == ""

        self.network_module._hostname_service_proxy = hostname_mock
        assert self.network_interface.GetCurrentHostname() == "dot.dot"

    def test_set_current_hostname(self):
        """Test the SetCurrentHostname method."""
        hostname_mock = Mock()

        self.network_module._hostname_service_proxy = None
        self.network_interface.SetCurrentHostname("dot.dot")
        hostname_mock.SetStaticHostname.assert_not_called()

        self.network_module._hostname_service_proxy = hostname_mock
        self.network_interface.SetCurrentHostname("dot.dot")
        hostname_mock.SetStaticHostname.assert_called_once_with("dot.dot", False)

    def test_current_hostname_changed(self):
        """Test the CurrentHostnameChanged signal."""
        hostname_mock = Mock()
        hostname_mock.PropertiesChanged = Signal()

        hostname_changed = Mock()
        # pylint: disable=no-member
        self.network_interface.CurrentHostnameChanged.connect(hostname_changed)

        self.network_module._hostname_service_proxy = hostname_mock
        self.network_module._connect_to_hostname_service(Mock())

        hostname_mock.PropertiesChanged.emit("org.freedesktop.hostname1", {}, [])
        hostname_changed.assert_not_called()

        changed_properties = {"Hostname": get_variant(Str, "dot.dot")}
        hostname_mock.PropertiesChanged.emit("org.freedesktop.hostname1", changed_properties, [])
        hostname_changed.assert_called_once_with("dot.dot")

    def test_connected(self):
        """Test getting connectivity status does not fail."""
        connected = self.network_interface.Connected
        assert connected in (True, False)

    def test_connecting(self):
        """Test checking connecting status does not fail."""
        self.network_interface.IsConnecting()

    def test_mocked_client_connectivity(self):
        """Test connectivity properties with mocked NMClient."""
        nm_client = MockedNMClient()
        nm_client._connect_state_changed(self.network_module._nm_state_changed)
        self.network_module.nm_client = nm_client

        nm_client._set_state(NM.State.CONNECTED_LOCAL)
        assert self.network_interface.Connected

        nm_client._set_state(NM.State.DISCONNECTED)
        assert not self.network_interface.Connected
        self.callback.assert_called_with(NETWORK.interface_name, {'Connected': False}, [])
        assert not self.network_interface.IsConnecting()

        nm_client._set_state(NM.State.CONNECTED_SITE)
        assert self.network_interface.Connected
        self.callback.assert_called_with(NETWORK.interface_name, {'Connected': True}, [])
        assert not self.network_interface.IsConnecting()

        nm_client._set_state(NM.State.CONNECTED_GLOBAL)
        assert self.network_interface.Connected
        self.callback.assert_called_with(NETWORK.interface_name, {'Connected': True}, [])
        assert not self.network_interface.IsConnecting()

        nm_client._set_state(NM.State.CONNECTING)
        assert not self.network_interface.Connected
        self.callback.assert_called_with(NETWORK.interface_name, {'Connected': False}, [])
        assert self.network_interface.IsConnecting()

        nm_client._set_state(NM.State.CONNECTED_LOCAL)
        assert self.network_interface.Connected
        self.callback.assert_called_with(NETWORK.interface_name, {'Connected': True}, [])
        assert not self.network_interface.IsConnecting()

    def test_capabilities_default(self):
        """Test getting capabilities does not fail."""
        assert self.network_interface.Capabilities == []

    def test_capabilities(self):
        """Test capabilities property with mocked NMClient."""
        nm_client = MockedNMClient()
        nm_client._connect_capabilities_changed(self.network_module._nm_capabilities_changed)
        self.network_module.nm_client = nm_client

        nm_client._set_capabilities([NM.Capability.TEAM, NM.Capability.OVS])
        assert self.network_interface.Capabilities == [NETWORK_CAPABILITY_TEAM]

        nm_client._set_capabilities([])
        assert self.network_interface.Capabilities == []

        self.network_module.nm_client = None
        assert self.network_interface.Capabilities == []

    def test_nm_availability(self):
        self.network_module.nm_client = None
        assert self.network_interface.Connected
        assert not self.network_interface.IsConnecting()

    def test_create_device_configurations(self):
        """Test creating device configurations does not fail."""
        self.network_interface.CreateDeviceConfigurations()

    def test_get_device_configurations(self):
        """Test GetDeviceConfigurations."""
        assert self.network_interface.GetDeviceConfigurations() == []

    def test_network_device_configuration_changed(self):
        """Test NetworkDeviceConfigurationChanged."""
        self.network_interface.NetworkDeviceConfigurationChanged()

    def test_get_dracut_arguments(self):
        """Test GetDracutArguments."""
        assert self.network_interface.GetDracutArguments("ens3", "10.10.10.10", "", False) == []

    def test_log_configuration_state(self):
        """Test LogConfigurationState."""
        self.network_interface.LogConfigurationState("message")

    @patch_dbus_publish_object
    @patch('pyanaconda.modules.network.network.devices_ignore_ipv6', return_value=True)
    def test_install_network_with_task(self, devices_ignore_ipv6, publisher):
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

        obj = check_task_creation(task_path, publisher, NetworkInstallationTask)

        assert obj.implementation._disable_ipv6 is True
        assert obj.implementation._overwrite is False
        assert obj.implementation._network_ifaces == ["ens3", "ens4", "ens5"]
        assert obj.implementation._configure_persistent_device_names is True

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.assert_called_once()

    @patch_dbus_publish_object
    def test_configure_hostname_with_task(self, publisher):
        """Test ConfigureHostnameWithTask."""
        self.network_module._hostname = "my_hostname"

        task_path = self.network_interface.ConfigureHostnameWithTask(False)

        obj = check_task_creation(task_path, publisher, HostnameConfigurationTask)

        assert obj.implementation._overwrite is False
        assert obj.implementation._hostname == "my_hostname"

    @patch_dbus_publish_object
    @patch('pyanaconda.modules.network.installation.update_connection_values')
    @patch('pyanaconda.modules.network.installation.get_config_file_connection_of_device')
    def test_configure_activation_on_boot_with_task(self, get_config_file_connection_of_device,
                                                    update_connection_values, publisher):
        """Test ConfigureActivationOnBootWithTask."""
        self.network_module.nm_client = Mock()
        self.network_module._should_apply_onboot_policy = Mock(return_value=True)
        self.network_module._has_any_onboot_yes_device = Mock(return_value=False)
        self.network_module._get_onboot_ifaces_by_policy = Mock(return_value=["ens4"])

        task_path = self.network_interface.ConfigureActivationOnBootWithTask(
            ["ens3"],
        )

        obj = check_task_creation(task_path, publisher, ConfigureActivationOnBootTask)

        assert set(obj.implementation._onboot_ifaces) == \
            set(["ens3", "ens4"])

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
    def test_apply_kickstart_with_task(self, publisher):
        """Test ApplyKickstartWithTask."""
        self._mock_supported_devices([("ens3", "", 0)])
        task_path = self.network_interface.ApplyKickstartWithTask()

        obj = check_task_creation(task_path, publisher, ApplyKickstartTask)

        self.network_module.log_task_result = Mock()

        obj.implementation.succeeded_signal.emit()
        self.network_module.log_task_result.assert_called_once()

    @patch_dbus_publish_object
    def test_dump_missing_ifcfg_files_with_task(self, publisher):
        """Test DumpMissingConfigFilesWithTask."""
        task_path = self.network_interface.DumpMissingConfigFilesWithTask()

        obj = check_task_creation(task_path, publisher, DumpMissingConfigFilesTask)

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

    def test_get_supported_devices(self):
        """Test GetSupportedDevices."""
        # No NM available
        self.network_module.nm_client = None
        assert self.network_interface.GetSupportedDevices() == \
            []

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
        assert devs_infos[0] == \
            {
                'device-name': get_variant(Str, "ens3"),
                'hw-address': get_variant(Str, "33:33:33:33:33:33"),
                'device-type': get_variant(Int, NM.DeviceType.ETHERNET)
            }
        assert devs_infos[1] == \
            {
                'device-name': get_variant(Str, "ens4"),
                'hw-address': get_variant(Str, "44:44:44:44:44:44"),
                'device-type': get_variant(Int, NM.DeviceType.ETHERNET)
            }
        assert devs_infos[2] == \
            {
                'device-name': get_variant(Str, "ens5"),
                'hw-address': get_variant(Str, "55:55:55:55:55:55"),
                'device-type': get_variant(Int, NM.DeviceType.ETHERNET)
            }
        assert devs_infos[3] == \
            {
                'device-name': get_variant(Str, "team0"),
                'hw-address': get_variant(Str, "33:33:33:33:33:33"),
                'device-type': get_variant(Int, NM.DeviceType.TEAM)
            }

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

    def test_get_activated_interfaces(self):
        """Test GetActivatedInterfaces."""
        # No NM available
        self.network_module.nm_client = None
        assert self.network_interface.GetActivatedInterfaces() == \
            []

        # Mocked NM
        self.network_module.nm_client = Mock()
        self._mock_nm_active_connections(
            [
                (True, ["ens3"]),
                # port of bond0
                (True, ["ens5"]),
                # port of bond0
                (True, ["ens7"]),
                (True, ["bond0"]),
                (False, ["ens11"]),
                # Not sure if/when this can happen, but we have been supporting it
                (True, ["devA", "devB"]),
                (True, [])
            ]
        )
        assert self.network_interface.GetActivatedInterfaces() == \
            ["ens3", "ens5", "ens7", "bond0", "devA", "devB"]

    def _test_kickstart(self, ks_in, ks_out, **kwargs):
        check_kickstart_interface(self.network_interface, ks_in, ks_out, **kwargs)

    def test_no_kickstart(self):
        """Test with no kickstart."""
        ks_in = None
        ks_out = """
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_empty(self):
        """Test with empty string."""
        ks_in = ""
        ks_out = """
        """
        self._test_kickstart(ks_in, ks_out)

    def test_network_kickstart(self):
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

    def test_kickstart_firewall_basic(self):
        """Test basic firewall command usage."""
        ks_in = "firewall --enable --port=imap:tcp,1234:udp,47 --trust=eth0,eth1 --service=ptp,syslog,ssh --remove-service=tftp,ssh"
        ks_out = """
        # Firewall configuration
        firewall --enabled --port=imap:tcp,1234:udp,47:tcp --trust=eth0,eth1 --service=ptp,syslog,ssh --remove-service=tftp,ssh
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_firewall_disable(self):
        """Test firewall --disabled."""
        ks_in = "firewall --disabled"
        ks_out = """
        # Firewall configuration
        firewall --disabled
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_firewall_disable_with_options(self):
        """Test firewall --disabled with options."""
        # apparently Pykickstart dumps any additional options if --disabled is used
        ks_in = "firewall --disable --port=imap:tcp,1234:udp,47 --trust=eth0,eth1 --service=ptp,syslog,ssh --remove-service=tftp,ssh"
        ks_out = """
        # Firewall configuration
        firewall --disabled
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_firewall_use_system_defaults(self):
        """Test firewall --use-system-defaults."""
        ks_in = "firewall --use-system-defaults"
        ks_out = """
        # Firewall configuration
        firewall --use-system-defaults
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_firewall_use_system_defaults_with_options(self):
        """Test firewall --use-system-defaults."""
        # looks like --use-system-defaults also eats any additional options
        ks_in = "firewall --use-system-defaults --port=imap:tcp,1234:udp,47 --trust=eth0,eth1 --service=ptp,syslog,ssh --remove-service=tftp,ssh"
        ks_out = """
        # Firewall configuration
        firewall --use-system-defaults
        """
        self._test_kickstart(ks_in, ks_out)

    def test_kickstart_firewall_service_options(self):
        """Test firewall with individual service options.

        The firewall command supports enabling some well known services, such as ssh or smtp, via dedicated
        options. The services should then end up in the --service list in the output.
        """
        ks_in = "firewall --ftp --http --smtp --ssh"
        ks_out = """
        # Firewall configuration
        firewall --enabled --service=ftp,http,smtp,ssh
        """
        self._test_kickstart(ks_in, ks_out)

    def test_default_requirements(self):
        """Test that by default no packages are required by the network module."""
        assert self.network_interface.CollectRequirements() == []

    def test_kickstart_firewall_package_requirements(self):
        """Test that firewall command in kickstart results in request for firewalld package."""

        ks_in = "firewall --ftp --http --smtp --ssh"
        ks_out = """
        # Firewall configuration
        firewall --enabled --service=ftp,http,smtp,ssh
        """
        self._test_kickstart(ks_in, ks_out)
        assert self.network_interface.CollectRequirements() == [
            {
                "type": get_variant(Str, "package"),
                "name": get_variant(Str, "firewalld"),
                "reason": get_variant(Str, "Requested by the firewall kickstart command.")
            }
        ]

    def test_rdma_core_requirements(self):
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
        assert self.network_interface.CollectRequirements() == [
            {
                "type": get_variant(Str, "package"),
                "name": get_variant(Str, "rdma-core"),
                "reason": get_variant(
                    Str,
                    "Necessary for network infiniband device configuration."
                )
            }
        ]

    def test_teamd_requirements(self):
        """Test that mocked team devices result in request for teamd package."""

        # mock a team device
        self.network_module.nm_client = Mock()
        self.__mock_nm_client_devices(
            [
                ("team0", None, "33:33:33:33:33:33", NM.DeviceType.TEAM)
            ]
        )

        # check that the teamd package is requested
        assert self.network_interface.CollectRequirements() == [
            {
                "type": get_variant(Str, "package"),
                "name": get_variant(Str, "teamd"),
                "reason": get_variant(Str, "Necessary for network team device configuration.")
            }
        ]

    @patch("pyanaconda.modules.network.network.kernel_arguments")
    def test_biosdevname_requirements(self, mocked_kernel_arguments):
        """Test that biosdevevname boot option results in proper requirement."""

        kernel_args = KernelArguments.from_string("biosdevname=1")
        with patch("pyanaconda.modules.network.network.kernel_arguments", kernel_args):
            # check that the biosdevname package is requested
            assert self.network_interface.CollectRequirements() == [
                {
                    "type": get_variant(Str, "package"),
                    "name": get_variant(Str, "biosdevname"),
                    "reason": get_variant(
                        Str,
                        "Necessary for biosdevname network device naming feature."
                    )
                }
            ]

        kernel_args = KernelArguments.from_string("biosdevname=0")
        with patch("pyanaconda.modules.network.network.kernel_arguments", kernel_args):
            assert self.network_interface.CollectRequirements() == []

        kernel_args = KernelArguments.from_string("biosdevname")
        with patch("pyanaconda.modules.network.network.kernel_arguments", kernel_args):
            assert self.network_interface.CollectRequirements() == []

    def test_kickstart_invalid_hostname(self):
        """Test that invalid hostname in kickstart is not accepted"""
        ks_in = "network --hostname sorry_underscores_banned"
        ks_out = ""
        self._test_kickstart(ks_in, ks_out, ks_valid=False)


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
            FIREWALL,
            self.firewall_interface,
            *args, **kwargs
        )

    def test_default_property_values(self):
        """Test the default firewall module values are as expected."""
        assert self.firewall_interface.FirewallMode == FIREWALL_DEFAULT
        assert self.firewall_interface.EnabledPorts == []
        assert self.firewall_interface.Trusts == []
        assert self.firewall_interface.EnabledServices == []
        assert self.firewall_interface.DisabledServices == []

    def test_set_use_system_defaults(self):
        """Test if the use-system-firewall-defaults option can be set."""
        self._check_dbus_property(
            "FirewallMode",
            FIREWALL_USE_SYSTEM_DEFAULTS,
        )

    def test_disable_firewall(self):
        """Test if firewall can be disabled."""
        self._check_dbus_property(
            "FirewallMode",
            FIREWALL_DISABLED,
        )

    def test_toggle_firewall(self):
        """Test if firewall can be toggled."""
        self._check_dbus_property(
            "FirewallMode",
            FIREWALL_DISABLED,
        )
        self._check_dbus_property(
            "FirewallMode",
            FIREWALL_ENABLED,
        )

    def test_set_enabled_ports(self):
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

    def test_set_trusts(self):
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

    def test_set_enabled_services(self):
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

    def test_set_disabled_services(self):
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

    def test_hostname_config_task(self):

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
            assert content == "{}\n".format(hostname)

            shutil.rmtree(hostname_dir)

    def test_hostname_config_dir_not_exist(self):
        """Test hostname configuration task with missing target system directory."""
        with tempfile.TemporaryDirectory() as sysroot:

            hostname = "bla.bla"

            task = HostnameConfigurationTask(
                sysroot=sysroot,
                hostname=hostname,
                overwrite=True
            )

            with pytest.raises(NetworkInstallationError):
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
    def test_firewall_config_task_basic(self, publisher):
        """Test the Firewall configuration task - basic."""
        task_path = self.firewall_interface.InstallWithTask()

        obj = check_task_creation(task_path, publisher, ConfigureFirewallTask)

        assert obj.implementation._firewall_mode == FirewallMode.DEFAULT
        assert obj.implementation._enabled_services == []
        assert obj.implementation._disabled_services == []
        assert obj.implementation._enabled_ports == []
        assert obj.implementation._trusts == []

    @patch('pyanaconda.modules.network.firewall.installation.execWithRedirect')
    def test_firewall_config_task_enable_missing_tool(self, exec_mock):
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
            with pytest.raises(FirewallConfigurationError):
                task.run()
            # should not call execWithRedirect
            exec_mock.assert_not_called()

    @patch('pyanaconda.modules.network.firewall.installation.execWithRedirect')
    def test_firewall_config_task_disable_missing_tool(self, exec_mock):
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
            # should not call execWithRedirect
            exec_mock.assert_not_called()

    @patch('pyanaconda.modules.network.firewall.installation.execWithRedirect')
    def test_firewall_config_task_default_missing_tool(self, exec_mock):
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
            # should not call execWithRedirect
            exec_mock.assert_not_called()

    @patch('pyanaconda.modules.network.firewall.installation.execWithRedirect')
    def test_firewall_config_task_system_defaults_missing_tool(self, exec_mock):
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
            # should not call execWithRedirect
            exec_mock.assert_not_called()

    @patch('pyanaconda.modules.network.firewall.installation.execWithRedirect')
    def test_firewall_config_task_default(self, exec_mock):
        """Test the Firewall configuration task - default."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            assert os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.DEFAULT,
                                         enabled_services = [],
                                         disabled_services = [],
                                         enabled_ports = [],
                                         trusts = [])
            task.run()

            exec_mock.assert_called_once_with(
                '/usr/bin/firewall-offline-cmd',
                ['--enabled', '--service=ssh'],
                root=sysroot
            )

    @patch('pyanaconda.modules.network.firewall.installation.execWithRedirect')
    def test_firewall_config_task_enable(self, exec_mock):
        """Test the Firewall configuration task - enable."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            assert os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.ENABLED,
                                         enabled_services = [],
                                         disabled_services = [],
                                         enabled_ports = [],
                                         trusts = [])
            task.run()

            exec_mock.assert_called_once_with(
                '/usr/bin/firewall-offline-cmd',
                ['--enabled', '--service=ssh'],
                root=sysroot
            )

    @patch('pyanaconda.modules.network.firewall.installation.execWithRedirect')
    def test_firewall_config_task_enable_with_options(self, exec_mock):
        """Test the Firewall configuration task - enable with options."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            assert os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.ENABLED,
                                         enabled_services = ["smnp"],
                                         disabled_services = ["tftp"],
                                         enabled_ports = ["22001:tcp","6400:udp"],
                                         trusts = ["eth1"])
            task.run()

            exec_mock.assert_called_once_with(
                '/usr/bin/firewall-offline-cmd',
                ['--enabled', '--service=ssh', '--trust=eth1', '--port=22001:tcp',
                 '--port=6400:udp', '--remove-service=tftp', '--service=smnp'],
                root=sysroot
            )

    @patch('pyanaconda.modules.network.firewall.installation.execWithRedirect')
    def test_firewall_config_task_disable_ssh(self, exec_mock):
        """Test the Firewall configuration task - test SSH can be disabled."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            assert os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.ENABLED,
                                         enabled_services = [],
                                         disabled_services = ["ssh"],
                                         enabled_ports = [],
                                         trusts = [])
            task.run()

            exec_mock.assert_called_once_with(
                '/usr/bin/firewall-offline-cmd',
                ['--enabled', '--remove-service=ssh'],
                root=sysroot
            )

    @patch('pyanaconda.modules.network.firewall.installation.execWithRedirect')
    def test_firewall_config_task_enable_disable_service(self, exec_mock):
        """Test the Firewall configuration task - test enabling & disabling the same service"""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            assert os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.ENABLED,
                                         enabled_services = ["tftp"],
                                         disabled_services = ["tftp"],
                                         enabled_ports = [],
                                         trusts = [])
            task.run()

            exec_mock.assert_called_once_with(
                '/usr/bin/firewall-offline-cmd',
                ['--enabled', '--service=ssh', '--remove-service=tftp', '--service=tftp'],
                root=sysroot
            )

    @patch('pyanaconda.modules.network.firewall.installation.execWithRedirect')
    def test_firewall_config_task_disable(self, exec_mock):
        """Test the Firewall configuration task - disable."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            assert os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.DISABLED,
                                         enabled_services = [],
                                         disabled_services = [],
                                         enabled_ports = [],
                                         trusts = [])
            task.run()

            exec_mock.assert_called_once_with(
                '/usr/bin/firewall-offline-cmd',
                ['--disabled', '--service=ssh'],
                root=sysroot
            )

    @patch('pyanaconda.modules.network.firewall.installation.execWithRedirect')
    def test_firewall_config_task_disable_with_options(self, exec_mock):
        """Test the Firewall configuration task - disable with options."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            assert os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.DISABLED,
                                         enabled_services = ["smnp"],
                                         disabled_services = ["tftp"],
                                         enabled_ports = ["22001:tcp","6400:udp"],
                                         trusts = ["eth1"])
            task.run()

            # even in disable mode, we still forward all the options to firewall-offline-cmd
            exec_mock.assert_called_once_with(
                '/usr/bin/firewall-offline-cmd',
                ['--disabled', '--service=ssh', '--trust=eth1', '--port=22001:tcp',
                 '--port=6400:udp', '--remove-service=tftp', '--service=smnp'],
                root=sysroot
            )

    @patch('pyanaconda.modules.network.firewall.installation.execWithRedirect')
    def test_firewall_config_task_use_system_defaults(self, exec_mock):
        """Test the Firewall configuration task - use system defaults."""

        with tempfile.TemporaryDirectory() as sysroot:
            os.makedirs(os.path.join(sysroot, "usr/bin"))
            os.mknod(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))
            assert os.path.exists(os.path.join(sysroot, "usr/bin/firewall-offline-cmd"))

            task = ConfigureFirewallTask(sysroot=sysroot,
                                         firewall_mode = FirewallMode.USE_SYSTEM_DEFAULTS,
                                         enabled_services = [],
                                         disabled_services = [],
                                         enabled_ports = [],
                                         trusts = [])
            task.run()

            # firewall-offline-cmd should not be called in use-system-defaults mode
            exec_mock.assert_not_called()


class NetworkModuleTestCase(unittest.TestCase):
    """Test Network module."""

    def setUp(self):
        """Set up the network module."""
        # Set up the network module.
        self.network_module = NetworkService()

    def test_apply_boot_options_ksdevice(self):
        """Test _apply_boot_options function for 'ksdevice'."""
        assert self.network_module.default_device_specification == DEFAULT_DEVICE_SPECIFICATION
        mocked_kernel_args = {"something": "else"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.default_device_specification == DEFAULT_DEVICE_SPECIFICATION
        mocked_kernel_args = {'ksdevice': "ens3"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.default_device_specification == "ens3"
        mocked_kernel_args = {}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.default_device_specification == "ens3"

    def test_apply_boot_options_noipv6(self):
        """Test _apply_boot_options function for 'noipv6'."""
        assert self.network_module.disable_ipv6 is False
        mocked_kernel_args = {"something": "else"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.disable_ipv6 is False
        mocked_kernel_args = {'noipv6': None}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.disable_ipv6 is True
        mocked_kernel_args = {}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.disable_ipv6 is True

    def test_apply_boot_options_bootif(self):
        """Test _apply_boot_options function for 'BOOTIF'."""
        assert self.network_module.bootif is None
        mocked_kernel_args = {"something": "else"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.bootif is None
        mocked_kernel_args = {'BOOTIF': "01-f4-ce-46-2c-44-7a"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.bootif == "F4:CE:46:2C:44:7A"
        mocked_kernel_args = {}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.bootif == "F4:CE:46:2C:44:7A"
        # Do not crash on trash
        mocked_kernel_args = {'BOOTIF': ""}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.bootif == ""

    def test_apply_boot_options_ifname(self):
        """Test _apply_boot_options function for 'ifname'."""
        assert self.network_module.ifname_option_values == []
        mocked_kernel_args = {"something": "else"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.ifname_option_values == []
        mocked_kernel_args = {'ifname': "ens3f0:00:15:17:96:75:0a"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.ifname_option_values == ["ens3f0:00:15:17:96:75:0a"]
        mocked_kernel_args = {'ifname': "ens3f0:00:15:17:96:75:0a ens3f1:00:15:17:96:75:0b"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.ifname_option_values == \
            ["ens3f0:00:15:17:96:75:0a", "ens3f1:00:15:17:96:75:0b"]
        mocked_kernel_args = {}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.ifname_option_values == \
            ["ens3f0:00:15:17:96:75:0a", "ens3f1:00:15:17:96:75:0b"]
        mocked_kernel_args = {'ifname': "bla bla"}
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert self.network_module.ifname_option_values == ["bla", "bla"]

    def test_apply_boot_options(self):
        """Test _apply_boot_options for multiple options."""
        assert [
                self.network_module.bootif,
                self.network_module.ifname_option_values,
                self.network_module.disable_ipv6,
                self.network_module.default_device_specification,
            ] == \
            [
                None,
                [],
                False,
                DEFAULT_DEVICE_SPECIFICATION,
            ]
        mocked_kernel_args = {
            'something_else': None,
            'ifname': 'ens3f0:00:15:17:96:75:0a ens3f1:00:15:17:96:75:0b',
            'something': 'completely_else',
            'BOOTIF': '01-f4-ce-46-2c-44-7a',
            'noipv6': None,
            'ksdevice': 'ens11',
        }
        self.network_module._apply_boot_options(mocked_kernel_args)
        assert [
                self.network_module.bootif,
                self.network_module.ifname_option_values,
                self.network_module.disable_ipv6,
                self.network_module.default_device_specification,
            ] == \
            [
                "F4:CE:46:2C:44:7A",
                ["ens3f0:00:15:17:96:75:0a", "ens3f1:00:15:17:96:75:0b"],
                True,
                "ens11",
            ]


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
        self._nm_syscons_dir = NetworkInstallationTask.NM_SYSTEM_CONNECTIONS_DIR_PATH
        self._systemd_network_dir = NetworkInstallationTask.SYSTEMD_NETWORK_CONFIG_DIR
        self._dhclient_dir = os.path.dirname(NetworkInstallationTask.DHCLIENT_FILE_TEMPLATE)
        self._nm_dns_runtime_dir = NetworkInstallationTask.NM_GLOBAL_DNS_RUNTIME_CONFIG_DIR
        self._nm_dns_dir = NetworkInstallationTask.NM_GLOBAL_DNS_CONFIG_DIR
        self._nm_dns_files = NetworkInstallationTask.NM_GLOBAL_DNS_CONFIG_FILES

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
        assert content == expected_content

    def _check_config_file_does_not_exist(self, conf_dir, file_name):
        mocked_conf_dir = os.path.join(self._target_mocked_root, conf_dir.lstrip("/"))
        assert not os.path.exists(os.path.join(mocked_conf_dir, file_name))

    def _mock_task_paths(self, task):
        # Mock the paths in the task
        task.SYSCONF_NETWORK_FILE_PATH = self._mocked_root + type(task).SYSCONF_NETWORK_FILE_PATH
        task.ANACONDA_SYSCTL_FILE_PATH = self._mocked_root + type(task).ANACONDA_SYSCTL_FILE_PATH
        task.RESOLV_CONF_FILE_PATH = self._mocked_root + type(task).RESOLV_CONF_FILE_PATH
        task.NETWORK_SCRIPTS_DIR_PATH = self._mocked_root + type(task).NETWORK_SCRIPTS_DIR_PATH
        task.NM_SYSTEM_CONNECTIONS_DIR_PATH = self._mocked_root + \
            type(task).NM_SYSTEM_CONNECTIONS_DIR_PATH
        task.DHCLIENT_FILE_TEMPLATE = self._mocked_root + type(task).DHCLIENT_FILE_TEMPLATE
        task.SYSTEMD_NETWORK_CONFIG_DIR = self._mocked_root + type(task).SYSTEMD_NETWORK_CONFIG_DIR
        task.NM_GLOBAL_DNS_RUNTIME_CONFIG_DIR = self._mocked_root + \
            type(task).NM_GLOBAL_DNS_RUNTIME_CONFIG_DIR
        task.NM_GLOBAL_DNS_CONFIG_DIR = self._mocked_root + type(task).NM_GLOBAL_DNS_CONFIG_DIR

    def _create_all_expected_dirs(self):
        # Create directories that are expected to be existing in installer
        # environmant and on target system
        self._create_config_dirs(
            installer_dirs=[
                self._sysconf_dir,
                self._sysctl_dir,
                self._resolv_conf_dir,
                self._network_scripts_dir,
                self._nm_syscons_dir,
                self._systemd_network_dir,
                self._dhclient_dir,
            ],
            target_system_dirs=[
                self._sysconf_dir,
                self._sysctl_dir,
                self._resolv_conf_dir,
                self._network_scripts_dir,
                self._nm_syscons_dir,
                self._systemd_network_dir,
                self._dhclient_dir,
            ]
        )

    def test_network_instalation_ignore_ifname_nbft(self):
        """Test the task for network installation with an ifname=nbft* argument."""

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
            network_ifaces=["ens3", "ens7", "nbft0"],
            ifname_option_values=["ens3:00:15:17:96:75:0a",
                                  "nbft0:00:15:17:96:75:0b"],
            # Perhaps does not make sense together with ifname option, but for
            # test it is fine
            configure_persistent_device_names=True,
        )
        self._mock_task_paths(task)
        task.run()
        content_template = NetworkInstallationTask.INTERFACE_RENAME_FILE_CONTENT_TEMPLATE
        self._check_config_file(
            self._systemd_network_dir,
            "10-anaconda-ifname-ens3.link",
            content_template.format("00:15:17:96:75:0a", "ens3")
        )
        # nbft* devices should be ignored when renaming devices based on
        # ifname= option
        self._check_config_file_does_not_exist(
            self._systemd_network_dir,
            "10-anaconda-ifname-nbft0.link"
        )

    def test_network_instalation_task_no_src_files(self):
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

    @patch("pyanaconda.modules.network.installation.conf")
    def test_network_instalation_task_all_src_files(self, mock_conf):
        """Test the task for network installation with all src files available."""
        mock_conf.system.provides_resolver_config = True

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
            self._nm_syscons_dir,
            (
                ("ens10.nmconnection", "content1"),
                ("ens11.nmconnection", "content2"),
                ("ens10.whatever", "content3"),
                ("whatever", "content4"),
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
            self._systemd_network_dir,
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
            network_ifaces=["ens3", "ens7", "ens10", "ens11"],
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
        # on Fedora, systemd-resolved in used, so there should be no copied-over resolv.conf
        self._check_config_file_does_not_exist(self._resolv_conf_dir, "resolv.conf")
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
        self._check_config_file(
            self._nm_syscons_dir,
            "ens10.nmconnection",
            """
            content1
            """
        )
        self._check_config_file(
            self._nm_syscons_dir,
            "ens11.nmconnection",
            """
            content2
            """
        )
        self._check_config_file(
            self._nm_syscons_dir,
            "ens10.whatever",
            """
            content3
            """
        )
        self._check_config_file(
            self._nm_syscons_dir,
            "whatever",
            """
            content4
            """
        )
        self._check_config_file_does_not_exist(
            self._dhclient_dir,
            "file_that_shoudnt_be_copied.conf"
        )
        self._check_config_file(
            self._systemd_network_dir,
            "71-net-ifnames-prefix-XYZ",
            """
            bla
            """
        )
        content_template = NetworkInstallationTask.INTERFACE_RENAME_FILE_CONTENT_TEMPLATE
        self._check_config_file(
            self._systemd_network_dir,
            "10-anaconda-ifname-ens3.link",
            content_template.format("00:15:17:96:75:0a", "ens3")
        )
        self._check_config_file_does_not_exist(
            self._systemd_network_dir,
            "70-shouldnt-be-copied"
        )

    @patch("pyanaconda.modules.network.installation.conf")
    def test_network_instalation_resolv_conf_skip_on_provides_resolver_false(self, mock_conf):
        """Test the task for network install with provides_resolver_config False in config."""
        mock_conf.system.provides_resolver_config = False

        self._create_all_expected_dirs()

        # Create just resolv.conf for this test.

        self._dump_config_files(
            self._resolv_conf_dir,
            (("resolv.conf", "nomen"),)
        )

        # Create the task
        task = NetworkInstallationTask(
            sysroot=self._target_root,
            disable_ipv6=True,
            overwrite=False,
            network_ifaces=["ens3", "ens7", "ens10", "ens11"],
            ifname_option_values=["ens3:00:15:17:96:75:0a"],
            # Perhaps does not make sense together with ifname option, but for
            # test it is fine
            configure_persistent_device_names=True,
        )
        self._mock_task_paths(task)
        task.run()
        # the config says we don't provide resolver config, so there should not be any
        self._check_config_file_does_not_exist(self._resolv_conf_dir, "resolv.conf")

    @patch("pyanaconda.modules.network.installation.service")
    @patch("pyanaconda.modules.network.installation.conf")
    def test_network_instalation_resolv_conf_skipped_with_resolved(self, mock_conf, mocked_service):
        """Test the task for network installation with systemd-resolved being used."""
        mock_conf.system.provides_resolver_config = True
        mocked_service.is_service_installed.return_value = True

        self._create_all_expected_dirs()

        # Create just resolv.conf for this test.
        self._dump_config_files(
            self._resolv_conf_dir,
            (("resolv.conf", "nomen"),)
        )

        # Create the task
        task = NetworkInstallationTask(
            sysroot=self._target_root,
            disable_ipv6=True,
            overwrite=False,
            network_ifaces=["ens3", "ens7", "ens10", "ens11"],
            ifname_option_values=["ens3:00:15:17:96:75:0a"],
            # Perhaps does not make sense together with ifname option, but for
            # test it is fine
            configure_persistent_device_names=True,
        )
        self._mock_task_paths(task)
        task.run()
        # systemd-resolved is in use, so we should have not copied resolv.conf by ourselves
        self._check_config_file_does_not_exist(self._resolv_conf_dir, "resolv.conf")

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
            self._systemd_network_dir,
            (("10-anaconda-ifname-ens3.link", "original target system content"),)
        )
        self._dump_config_files_in_target(
            self._network_scripts_dir,
            (("ifcfg-ens3", "original target system content"),)
        )
        self._dump_config_files_in_target(
            self._nm_syscons_dir,
            (("ens10.nmconnection", "original target system content"),)
        )
        self._dump_config_files_in_target(
            self._dhclient_dir,
            (("dhclient-ens3.conf", "original target system content"),)
        )
        self._dump_config_files_in_target(
            self._systemd_network_dir,
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
            self._nm_syscons_dir,
            (("ens10.nmconnection", "installer environment content"),)
        )
        self._dump_config_files(
            self._dhclient_dir,
            (("dhclient-ens3.conf", "installer environment content"),)
        )
        self._dump_config_files(
            self._systemd_network_dir,
            (("71-net-ifnames-prefix-XYZ", "installer environment content"),)
        )

    @patch("pyanaconda.modules.network.installation.service")
    def test_network_installation_task_dnsconfd_enablement(self, mocked_service):
        """Test the task for network installation dnsconfd enablement."""

        self._create_all_expected_dirs()
        task = NetworkInstallationTask(
            sysroot=self._target_root,
            disable_ipv6=False,
            overwrite=True,
            network_ifaces=["ens3", "ens7", "ens10"],
            ifname_option_values=["ens3:00:15:17:96:75:0a"],
            configure_persistent_device_names=False,
        )
        self._mock_task_paths(task)

        kernel_args = KernelArguments.from_string("rd.net.dns-backend=dnsconfd")
        with patch("pyanaconda.modules.network.installation.kernel_arguments", kernel_args):
            mocked_service.is_service_installed.return_value = False
            task.run()
            mocked_service.enable_service.assert_not_called()
            mocked_service.is_service_installed.return_value = True
            task.run()
            mocked_service.enable_service.assert_called_once()

    def test_network_installation_task_overwrite(self):
        """Test the task for network installation with overwrite."""

        self._create_all_expected_dirs()
        self._create_config_files_to_check_overwrite()

        task = NetworkInstallationTask(
            sysroot=self._target_root,
            disable_ipv6=False,
            overwrite=True,
            network_ifaces=["ens3", "ens7", "ens10"],
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
            self._systemd_network_dir,
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
            self._nm_syscons_dir,
            "ens10.nmconnection",
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
            self._systemd_network_dir,
            "71-net-ifnames-prefix-XYZ",
            """
            original target system content
            """
        )

    def test_network_installation_task_no_overwrite(self):
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
            self._systemd_network_dir,
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
            self._nm_syscons_dir,
            "ens10.nmconnection",
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
            self._systemd_network_dir,
            "71-net-ifnames-prefix-XYZ",
            """
            original target system content
            """
        )

    def test_disable_ipv6_on_system_no_dir(self):
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

        with pytest.raises(NetworkInstallationError):
            task._disable_ipv6_on_system(self._target_root)

    def test_network_instalation_task_missing_target_dir(self):
        """Test the task for network installation with missing target system directory."""

        self._create_config_dirs(
            installer_dirs=[
                self._network_scripts_dir,
                self._nm_syscons_dir,
                self._systemd_network_dir,
            ],
            target_system_dirs=[
                self._sysconf_dir,
                # target dir for prefixdevname is missing
                # but it should be created by the task
            ]
        )

        self._dump_config_files(
            self._systemd_network_dir,
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
            self._systemd_network_dir,
            "71-net-ifnames-prefix-XYZ",
            """
            bla
            """
        )

    def test_network_instalation_task_global_dns_config(self):
        """Test the task for network installation and global dns configuration."""

        self._create_all_expected_dirs()

        self._create_config_dirs(
            installer_dirs=[
                self._nm_dns_runtime_dir,
                self._nm_dns_dir,
            ],
            target_system_dirs=[
                self._nm_dns_dir,
            ]
        )

        for file in self._nm_dns_files:
            self._dump_config_files(
                self._nm_dns_runtime_dir,
                ((file, "bla"),)
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

        for file in self._nm_dns_files:
            self._check_config_file(
                self._nm_dns_dir,
                file,
                """
                bla
                """
            )
