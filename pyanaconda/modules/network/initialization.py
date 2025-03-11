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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import copy
import re

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import NETWORK_CAPABILITY_TEAM
from pyanaconda.core.regexes import NM_MAC_INITRAMFS_CONNECTION
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.network.device_configuration import (
    supported_wired_device_types,
    virtual_device_types,
)
from pyanaconda.modules.network.network_interface import (
    NetworkInitializationTaskInterface,
)
from pyanaconda.modules.network.nm_client import (
    add_connection_from_ksdata,
    bound_hwaddr_of_device,
    clone_connection_sync,
    commit_changes_with_autoconnection_blocked,
    get_config_file_connection_of_device,
    get_device_name_from_network_data,
    is_bootif_connection,
    nm_client_in_thread,
    update_connection_from_ksdata,
    update_connection_values,
)
from pyanaconda.modules.network.utils import (
    guard_by_system_configuration,
    is_nbft_device,
)

log = get_module_logger(__name__)

import gi

gi.require_version("NM", "1.0")
from gi.repository import NM


class ApplyKickstartTask(Task):
    """Task for application of kickstart network configuration."""

    def __init__(self, network_data, supported_devices, capabilities,
                 bootif, ifname_option_values):
        """Create a new task.

        :param network_data: kickstart network data to be applied
        :type: list(NetworkData)
        :param supported_devices: list of names of supported network devices
        :type supported_devices: list(str)
        :param capabilities: list of capabilities supported by the network backend
        :type capabilities: list(int)
        :param bootif: MAC addres of device to be used for --device=bootif specification
        :type bootif: str
        :param ifname_option_values: list of ifname boot option values
        :type ifname_option_values: list(str)
        """
        super().__init__()
        self._network_data = network_data
        self._supported_devices = supported_devices
        self._capabilities = capabilities
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
            log.debug("%s: No kickstart data.", self.name)
            return applied_devices

        if not nm_client:
            log.debug("%s: No NetworkManager available.", self.name)
            return applied_devices

        for network_data in self._network_data:
            # Wireless is not supported
            if network_data.essid:
                log.info("%s: Wireless devices configuration is not supported.", self.name)
                continue

            if network_data.teamslaves and NETWORK_CAPABILITY_TEAM not in self._capabilities:
                log.info("%s: Team devices configuration is not supported.", self.name)
                continue

            device_name = get_device_name_from_network_data(nm_client,
                                                            network_data,
                                                            self._supported_devices,
                                                            self._bootif)
            if not device_name:
                log.warning("%s: --device %s not found", self.name, network_data.device)
                continue

            if is_nbft_device(device_name):
                log.debug("Ignoring nBFT device %s", device_name)
                continue

            applied_devices.append(device_name)

            connection = self._find_initramfs_connection_of_iface(nm_client, device_name)

            if connection:
                # if the device was already configured in initramfs update the settings
                log.debug("%s: updating connection %s of device %s",
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
                    log.debug("%s: activating updated connection %s with device %s",
                              self.name, connection.get_uuid(), device_name)
            else:
                log.debug("%s: adding connection for %s", self.name, device_name)
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
                if allow_ports or not con.get_setting_connection().get_controller():
                    return con
            else:
                log.debug("%s: active connection for %s can't be used as persistent",
                          self.name, iface)
        for con in cons:
            if con.get_interface_name() == iface:
                if allow_ports or not con.get_setting_connection().get_controller():
                    return con
        return None

    def _update_connection(self, nm_client, con, iface):
        log.debug("%s: updating id and binding (interface-name) of connection %s for %s",
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
                log.debug("%s: iface %s bound to mac address %s by ifname boot option",
                          self.name, iface, bound_mac)
        log.debug("%s: updating addr-gen-mode of connection %s for %s",
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
            log.debug("%s: No NetworkManager available.", self.name)
            return new_configs

        dumped_device_types = supported_wired_device_types + virtual_device_types
        for device in nm_client.get_devices():
            if device.get_device_type() not in dumped_device_types:
                continue

            iface = device.get_iface()

            if is_nbft_device(iface or ""):
                log.debug("Ignoring nBFT device %s", iface)
                continue

            if get_config_file_connection_of_device(nm_client, iface):
                continue

            available_cons = device.get_available_connections()
            log.debug("%s: %s connections found for device %s", self.name,
                      [con.get_uuid() for con in available_cons], iface)
            initramfs_cons = [con for con in available_cons
                              if self._is_initramfs_connection(con, iface)]
            log.debug("%s: %s initramfs connections found for device %s", self.name,
                      [con.get_uuid() for con in initramfs_cons], iface)

            dumped_con = None

            device_is_port = any(con.get_setting_connection().get_controller()
                                 for con in available_cons)
            if device_is_port:
                # We have to dump persistent ifcfg files for ports created in initramfs
                # Filter out potenital connection created for BOOTIF option rhbz#2175664
                port_cons = [c for c in available_cons if not is_bootif_connection(c)]
                if initramfs_cons:
                    if len(port_cons) == 1:
                        log.debug("%s: port device %s has an initramfs port connection",
                                  self.name, iface)
                        dumped_con = self._select_persistent_connection_for_device(
                            device, port_cons, allow_ports=True)
                    else:
                        log.debug("%s: port device %s has an initramfs connection",
                                  self.name, iface)
                else:
                    log.debug("%s: not creating default connection for port device %s",
                              self.name, iface)
                    continue

            if not dumped_con:
                dumped_con = self._select_persistent_connection_for_device(device, available_cons)

            if not dumped_con and len(initramfs_cons) == 1:
                # Try to clone the persistent connection for the device
                # from the connection which should be a generic (not bound
                # to iface) connection created by NM in initramfs
                dumped_con = clone_connection_sync(nm_client, initramfs_cons[0], con_id=iface)

            if dumped_con:
                log.debug("%s: dumping connection %s to config file for %s",
                          self.name, dumped_con.get_uuid(), iface)
                self._dump_connection(nm_client, dumped_con, iface, bool(initramfs_cons))
            else:
                log.debug("%s: none of the connections can be dumped as persistent",
                          self.name)
                if len(available_cons) > 1 and not device_is_port:
                    log.warning("%s: unexpected number of connections, not dumping any",
                                self.name)
                    continue
                log.debug("%s: creating default connection for %s", self.name, iface)
                self._create_default_connection(nm_client, iface, bool(initramfs_cons))

            new_configs.append(iface)

        return new_configs

    def _dump_connection(self, nm_client, dumped_con, iface, initramfs_con):
        self._update_connection(nm_client, dumped_con, iface)
        # Update some values of connection generated in initramfs so it
        # can be used as persistent configuration.
        if initramfs_con:
            update_connection_values(
                dumped_con,
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
        commit_changes_with_autoconnection_blocked(dumped_con, nm_client)

    def _create_default_connection(self, nm_client, iface, initramfs_con):
        network_data = copy.deepcopy(self._default_network_data)
        network_data.onboot = initramfs_con
        add_connection_from_ksdata(
            nm_client,
            network_data,
            iface,
            activate=False,
            ifname_option_values=self._ifname_option_values
        )

    def _is_initramfs_connection(self, con, iface):
        con_id = con.get_id()
        return con_id in ["Wired Connection", iface] \
            or re.match(NM_MAC_INITRAMFS_CONNECTION, con_id)
