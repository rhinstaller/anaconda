#
# Copyright (C) 2019 Red Hat, Inc.
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
import copy
import re

from pyanaconda.core.regexes import NM_MAC_INITRAMFS_CONNECTION
from pyanaconda.modules.common.task import Task
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.network.network_interface import NetworkInitializationTaskInterface
from pyanaconda.modules.network.nm_client import get_device_name_from_network_data, \
    update_connection_from_ksdata, add_connection_from_ksdata, bound_hwaddr_of_device, \
    update_connection_values, commit_changes_with_autoconnection_blocked, \
    get_config_file_connection_of_device, clone_connection_sync, nm_client_in_thread
from pyanaconda.modules.network.device_configuration import supported_wired_device_types, \
    virtual_device_types
from pyanaconda.modules.network.utils import guard_by_system_configuration

log = get_module_logger(__name__)

import gi
gi.require_version("NM", "1.0")
from gi.repository import NM


class ApplyKickstartTask(Task):
    """Task for application of kickstart network configuration."""

    def __init__(self, network_data, supported_devices, bootif, ifname_option_values):
        """Create a new task.

        :param network_data: kickstart network data to be applied
        :type: list(NetworkData)
        :param supported_devices: list of names of supported network devices
        :type supported_devices: list(str)
        :param bootif: MAC addres of device to be used for --device=bootif specification
        :type bootif: str
        :param ifname_option_values: list of ifname boot option values
        :type ifname_option_values: list(str)
        """
        super().__init__()
        self._network_data = network_data
        self._supported_devices = supported_devices
        self._bootif = bootif
        self._ifname_option_values = ifname_option_values

    @property
    def name(self):
        return "Apply kickstart"

    def for_publication(self):
        """Return a DBus representation."""
        return NetworkInitializationTaskInterface(self)

    @guard_by_system_configuration(return_value=[])
    def run(self):
        """Run the kickstart application.

        :returns: names of devices to which kickstart was applied
        :rtype: list(str)
        """
        with nm_client_in_thread() as nm_client:
            return self._run(nm_client)

    def _run(self, nm_client):
        applied_devices = []

        if not self._network_data:
            log.debug("{}: No kickstart data.", self.name)
            return applied_devices

        if not nm_client:
            log.debug("{}: No NetworkManager available.", self.name)
            return applied_devices

        for network_data in self._network_data:
            # Wireless is not supported
            if network_data.essid:
                log.info("{}: Wireless devices configuration is not supported.", self.name)
                continue

            device_name = get_device_name_from_network_data(nm_client,
                                                            network_data,
                                                            self._supported_devices,
                                                            self._bootif)
            if not device_name:
                log.warning("{}: --device {} not found", self.name, network_data.device)
                continue

            applied_devices.append(device_name)

            connection = self._find_initramfs_connection_of_iface(nm_client, device_name)

            if connection:
                # if the device was already configured in initramfs update the settings
                log.debug("{}: updating connection {} of device {}",
                          self.name, connection.get_uuid(), device_name)
                update_connection_from_ksdata(
                    nm_client,
                    connection,
                    network_data,
                    device_name,
                    ifname_option_values=self._ifname_option_values
                )
                if network_data.activate:
                    device = nm_client.get_device_by_iface(device_name)
                    nm_client.activate_connection_async(connection, device, None, None)
                    log.debug("{}: activating updated connection {} with device {}",
                              self.name, connection.get_uuid(), device_name)
            else:
                log.debug("{}: adding connection for {}", self.name, device_name)
                add_connection_from_ksdata(
                    nm_client,
                    network_data,
                    device_name,
                    activate=network_data.activate,
                    ifname_option_values=self._ifname_option_values
                )

        return applied_devices

    def _find_initramfs_connection_of_iface(self, nm_client, iface):
        device = nm_client.get_device_by_iface(iface)
        if device:
            cons = device.get_available_connections()
            for con in cons:
                if con.get_interface_name() == iface and con.get_id() == iface:
                    return con
        return None


class DumpMissingConfigFilesTask(Task):
    """Task for dumping of missing config files."""

    def __init__(self, default_network_data, ifname_option_values):
        """Create a new task.

        :param default_network_data: kickstart network data of default device configuration
        :type default_network_data: NetworkData
        :param ifname_option_values: list of ifname boot option values
        :type ifname_option_values: list(str)
        """
        super().__init__()
        self._default_network_data = default_network_data
        self._ifname_option_values = ifname_option_values

    @property
    def name(self):
        return "Dump missing config files"

    def for_publication(self):
        """Return a DBus representation."""
        return NetworkInitializationTaskInterface(self)

    def _select_persistent_connection_for_device(self, device, cons, allow_ports=False):
        """Select the connection suitable to store configuration for the device."""
        iface = device.get_iface()
        ac = device.get_active_connection()
        if ac:
            con = ac.get_connection()
            if con.get_interface_name() == iface and con in cons:
                if allow_ports or not con.get_setting_connection().get_master():
                    return con
            else:
                log.debug("{}: active connection for {} can't be used as persistent",
                          self.name, iface)
        for con in cons:
            if con.get_interface_name() == iface:
                if allow_ports or not con.get_setting_connection().get_master():
                    return con
        return None

    def _update_connection(self, nm_client, con, iface):
        log.debug("{}: updating id and binding (interface-name) of connection {} for {}",
                  self.name, con.get_uuid(), iface)
        s_con = con.get_setting_connection()
        s_con.set_property(NM.SETTING_CONNECTION_ID, iface)
        s_con.set_property(NM.SETTING_CONNECTION_INTERFACE_NAME, iface)
        s_wired = con.get_setting_wired()
        if s_wired:
            # By default connections are bound to interface name
            s_wired.set_property(NM.SETTING_WIRED_MAC_ADDRESS, None)
            bound_mac = bound_hwaddr_of_device(nm_client, iface, self._ifname_option_values)
            if bound_mac:
                s_wired.set_property(NM.SETTING_WIRED_MAC_ADDRESS, bound_mac)
                log.debug("{}: iface {} bound to mac address {} by ifname boot option",
                          self.name, iface, bound_mac)
        log.debug("{}: updating addr-gen-mode of connection {} for {}",
                  self.name, con.get_uuid(), iface)
        s_ipv6 = con.get_setting_ip6_config()
        # For example port connections do not have ipv6 setting present
        if s_ipv6:
            s_ipv6.set_property(NM.SETTING_IP6_CONFIG_ADDR_GEN_MODE,
                                NM.SettingIP6ConfigAddrGenMode.EUI64)

    @guard_by_system_configuration(return_value=[])
    def run(self):
        """Run dumping of missing config files.

        :returns: names of devices for which config file was created
        :rtype: list(str)
        """
        with nm_client_in_thread() as nm_client:
            return self._run(nm_client)

    def _run(self, nm_client):
        new_configs = []

        if not nm_client:
            log.debug("{}: No NetworkManager available.", self.name)
            return new_configs

        dumped_device_types = supported_wired_device_types + virtual_device_types
        for device in nm_client.get_devices():
            if device.get_device_type() not in dumped_device_types:
                continue

            iface = device.get_iface()
            if get_config_file_connection_of_device(nm_client, iface):
                continue

            cons = device.get_available_connections()
            log.debug("{}: {} connections found for device {}", self.name,
                      [con.get_uuid() for con in cons], iface)
            n_cons = len(cons)
            con = None

            device_is_port = any(con.get_setting_connection().get_master() for con in cons)
            if device_is_port:
                # We have to dump persistent ifcfg files for ports created in initramfs
                if n_cons == 1 and self._is_initramfs_connection(cons[0], iface):
                    log.debug("{}: device {} has an initramfs port connection",
                              self.name, iface)
                    con = self._select_persistent_connection_for_device(
                        device, cons, allow_ports=True)
                else:
                    log.debug("{}: creating default connection for port device {}",
                              self.name, iface)

            if not con:
                con = self._select_persistent_connection_for_device(device, cons)

            has_initramfs_con = any(self._is_initramfs_connection(con, iface) for con in cons)
            if has_initramfs_con:
                log.debug("{}: device %s has initramfs connection", self.name, iface)
                if not con and n_cons == 1:
                    # Try to clone the persistent connection for the device
                    # from the connection which should be a generic (not bound
                    # to iface) connection created by NM in initramfs
                    con = clone_connection_sync(nm_client, cons[0], con_id=iface)

            if con:
                self._update_connection(nm_client, con, iface)
                # Update some values of connection generated in initramfs so it
                # can be used as persistent configuration.
                if has_initramfs_con:
                    update_connection_values(
                        con,
                        [
                            # Make sure ONBOOT is yes
                            (NM.SETTING_CONNECTION_SETTING_NAME,
                             NM.SETTING_CONNECTION_AUTOCONNECT,
                             True),
                            # Update cloned generic connection from initramfs
                            (NM.SETTING_CONNECTION_SETTING_NAME,
                             NM.SETTING_CONNECTION_MULTI_CONNECT,
                             0),
                            # Update cloned generic connection from initramfs
                            (NM.SETTING_CONNECTION_SETTING_NAME,
                             NM.SETTING_CONNECTION_WAIT_DEVICE_TIMEOUT,
                             -1)
                        ]
                    )
                log.debug("{}: dumping connection %s to config file for {}",
                          self.name, con.get_uuid(), iface)
                commit_changes_with_autoconnection_blocked(con, nm_client)
            else:
                log.debug("{}: none of the connections can be dumped as persistent",
                          self.name)
                if n_cons > 1 and not device_is_port:
                    log.warning("{}: unexpected number of connections, not dumping any",
                                self.name)
                    continue
                log.debug("{}: creating default connection for {}", self.name, iface)
                network_data = copy.deepcopy(self._default_network_data)
                if has_initramfs_con:
                    network_data.onboot = True
                add_connection_from_ksdata(
                    nm_client,
                    network_data,
                    iface,
                    activate=False,
                    ifname_option_values=self._ifname_option_values
                )

            new_configs.append(iface)

        return new_configs

    def _is_initramfs_connection(self, con, iface):
        con_id = con.get_id()
        return con_id in ["Wired Connection", iface] \
            or re.match(NM_MAC_INITRAMFS_CONNECTION, con_id)
