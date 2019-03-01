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

from pyanaconda.modules.common.task import Task
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.network.nm_client import get_device_name_from_network_data, \
    ensure_active_connection_for_device, update_connection_from_ksdata, add_connection_from_ksdata, \
    update_iface_setting_values, bound_hwaddr_of_device
from pyanaconda.modules.network.ifcfg import get_ifcfg_file_of_device, find_ifcfg_uuid_of_device, \
    update_onboot_value, update_slaves_onboot_value
from pyanaconda.modules.network.device_configuration import supported_wired_device_types

log = get_module_logger(__name__)

import gi
gi.require_version("NM", "1.0")
from gi.repository import NM


class ApplyKickstartTask(Task):
    """Task for application of kickstart network configuration."""

    def __init__(self, nm_client, network_data, supported_devices, bootif, ifname_option_values):
        """Create a new task.

        :param nm_client: NetworkManager client used as configuration backend
        :type nm_client: NM.Client
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
        self._nm_client = nm_client
        self._network_data = network_data
        self._supported_devices = supported_devices
        self._bootif = bootif
        self._ifname_option_values = ifname_option_values

    @property
    def name(self):
        return "Apply kickstart"

    def run(self):
        """Run the kickstart application.

        :returns: names of devices to which kickstart was applied
        :rtype: list(str)
        """
        applied_devices = []

        if not self._network_data:
            log.debug("%s: No kickstart data.", self.name)
            return applied_devices

        if not self._nm_client:
            log.debug("%s: No NetworkManager available.", self.name)
            return applied_devices

        for network_data in self._network_data:
            # Wireless is not supported
            if network_data.essid:
                log.info("%s: Wireless devices configuration is not supported.", self.name)
                continue

            device_name = get_device_name_from_network_data(self._nm_client,
                                                            network_data,
                                                            self._supported_devices,
                                                            self._bootif)
            if not device_name:
                log.warning("%s: --device %s not found", self.name, network_data.device)
                continue

            ifcfg_file = get_ifcfg_file_of_device(self._nm_client, device_name)
            if ifcfg_file and ifcfg_file.is_from_kickstart:
                if network_data.activate:
                    if ensure_active_connection_for_device(self._nm_client, ifcfg_file.uuid,
                                                           device_name):
                        applied_devices.append(device_name)
                continue

            # If there is no kickstart ifcfg from initramfs the command was added
            # in %pre section after switch root, so apply it now
            applied_devices.append(device_name)
            if ifcfg_file:
                # if the device was already configured in initramfs update the settings
                con_uuid = ifcfg_file.uuid
                log.debug("%s: pre kickstart - updating settings %s of device %s",
                          self.name, con_uuid, device_name)
                connection = self._nm_client.get_connection_by_uuid(con_uuid)
                update_connection_from_ksdata(self._nm_client, connection, network_data,
                                              device_name=device_name)
                if network_data.activate:
                    device = self._nm_client.get_device_by_iface(device_name)
                    self._nm_client.activate_connection_async(connection, device, None, None)
                    log.debug("%s: pre kickstart - activating connection %s with device %s",
                              self.name, con_uuid, device_name)
            else:
                log.debug("%s: pre kickstart - adding connection for %s", self.name, device_name)
                add_connection_from_ksdata(self._nm_client, network_data, device_name,
                                           activate=network_data.activate,
                                           ifname_option_values=self._ifname_option_values)

        return applied_devices


class ConsolidateInitramfsConnectionsTask(Task):
    """Task for consolidation of initramfs connections."""

    def __init__(self, nm_client):
        """Create a new task.

        :param nm_client: NetworkManager client used as configuration backend
        :type nm_client: NM.Client
        """
        super().__init__()
        self._nm_client = nm_client

    @property
    def name(self):
        return "Consolidate initramfs connections"

    def run(self):
        """Run the connections consolidation.

        :returns: names of devices of which the connections have been consolidated
        :rtype: list(str)
        """
        consolidated_devices = []

        if not self._nm_client:
            log.debug("%s: No NetworkManager available.", self.name)
            return consolidated_devices

        for device in self._nm_client.get_devices():
            cons = device.get_available_connections()
            number_of_connections = len(cons)
            iface = device.get_iface()

            if number_of_connections < 2:
                continue

            # Ignore devices which are slaves
            if any(con.get_setting_connection().get_master() for con in cons):
                log.debug("%s: %d for %s - it is OK, device is a slave",
                          self.name, number_of_connections, iface)
                continue

            ifcfg_file = get_ifcfg_file_of_device(self._nm_client, iface)
            if not ifcfg_file:
                log.error("%s: %d for %s - no ifcfg file found",
                          self.name, number_of_connections, iface)
                continue
            else:
                # Handle only ifcfgs created from boot options in initramfs
                # (Kickstart based ifcfgs are handled when applying kickstart)
                if ifcfg_file.is_from_kickstart:
                    continue

            log.debug("%s: %d for %s - ensure active ifcfg connection",
                      self.name, number_of_connections, iface)

            ensure_active_connection_for_device(self._nm_client, ifcfg_file.uuid, iface, only_replace=True)

            consolidated_devices.append(iface)

        return consolidated_devices


class SetRealOnbootValuesFromKickstartTask(Task):
    """Task for setting of real ONBOOT values from kickstart."""

    def __init__(self, nm_client, network_data, supported_devices, bootif, ifname_option_values):
        """Create a new task.

        :param nm_client: NetworkManager client used as configuration backend
        :type nm_client: NM.Client
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
        self._nm_client = nm_client
        self._network_data = network_data
        self._supported_devices = supported_devices
        self._bootif = bootif
        self._ifname_option_values = ifname_option_values

    @property
    def name(self):
        return "Set real ONBOOT values from kickstart"

    def run(self):
        """Run the ONBOOT values updating.

        :return: names of devices for which ONBOOT was updated
        :rtype: list(str)
        """
        updated_devices = []

        if not self._nm_client:
            log.debug("%s: No NetworkManager available.", self.name)
            return updated_devices

        if not self._network_data:
            log.debug("%s: No kickstart data.", self.name)
            return updated_devices

        for network_data in self._network_data:
            device_name = get_device_name_from_network_data(self._nm_client,
                                                            network_data,
                                                            self._supported_devices,
                                                            self._bootif)
            if not device_name:
                log.warning("%s: --device %s does not exist.", self.name, network_data.device)

            devices_to_update = [device_name]
            master = device_name
            # When defining both bond/team and vlan in one command we need more care
            # network --onboot yes --device bond0 --bootproto static --bondslaves ens9,ens10
            # --bondopts mode=active-backup,miimon=100,primary=ens9,fail_over_mac=2
            # --ip 192.168.111.1 --netmask 255.255.255.0 --gateway 192.168.111.222 --noipv6
            # --vlanid 222 --no-activate
            if network_data.vlanid and (network_data.bondslaves or network_data.teamslaves):
                master = network_data.device
                devices_to_update.append(master)

            for devname in devices_to_update:
                if network_data.onboot:
                    # We need to handle "no" -> "yes" change by changing ifcfg file instead of the NM connection
                    # so the device does not get autoactivated (BZ #1261864)
                    uuid = find_ifcfg_uuid_of_device(self._nm_client, devname) or ""
                    if not update_onboot_value(uuid, network_data.onboot, root_path=""):
                        continue
                else:
                    n_cons = update_iface_setting_values(self._nm_client, devname,
                        [("connection", NM.SETTING_CONNECTION_AUTOCONNECT, network_data.onboot)])
                    if n_cons != 1:
                        log.debug("%s: %d connections found for %s", self.name, n_cons, devname)
                        if n_cons > 1:
                            # In case of multiple connections for a device, update ifcfg directly
                            uuid = find_ifcfg_uuid_of_device(self._nm_client, devname) or ""
                            if not update_onboot_value(uuid, network_data.onboot, root_path=""):
                                continue

                updated_devices.append(devname)

            # Handle slaves if there are any
            if network_data.bondslaves or network_data.teamslaves or network_data.bridgeslaves:
                # Master can be identified by devname or uuid, try to find master uuid
                uuid = None
                device = self._nm_client.get_device_by_iface(master)
                if device:
                    cons = device.get_available_connections()
                    n_cons = len(cons)
                    if n_cons == 1:
                        uuid = cons[0].get_uuid()
                    else:
                        log.debug("%s: %d connections found for %s", self.name, n_cons, master)
                updated_slaves = update_slaves_onboot_value(self._nm_client, master, network_data.onboot, uuid=uuid)
                updated_devices.extend(updated_slaves)

        return updated_devices


class DumpMissingIfcfgFilesTask(Task):
    """Task for dumping of missing ifcfg files."""

    def __init__(self, nm_client, default_network_data, ifname_option_values):
        """Create a new task.

        :param nm_client: NetworkManager client used as configuration backend
        :type nm_client: NM.Client
        :param default_network_data: kickstart network data of default device configuration
        :type default_network_data: NetworkData
        :param ifname_option_values: list of ifname boot option values
        :type ifname_option_values: list(str)
        """
        super().__init__()
        self._nm_client = nm_client
        self._default_network_data = default_network_data
        self._ifname_option_values = ifname_option_values

    @property
    def name(self):
        return "Dump missing ifcfg files"

    def run(self):
        """Run dumping of missing ifcfg files.

        :returns: names of devices for which ifcfg file was created
        :rtype: list(str)
        """
        new_ifcfgs = []

        if not self._nm_client:
            log.debug("%s: No NetworkManager available.", self.name)
            return new_ifcfgs

        for device in self._nm_client.get_devices():
            if device.get_device_type() not in supported_wired_device_types:
                continue

            iface = device.get_iface()
            if get_ifcfg_file_of_device(self._nm_client, iface):
                continue

            cons = device.get_available_connections()
            n_cons = len(cons)
            device_is_slave = any(con.get_setting_connection().get_master() for con in cons)

            if n_cons == 0:
                log.debug("%s: creating default connection for %s", self.name, iface)
                add_connection_from_ksdata(self._nm_client, self._default_network_data, iface, activate=False,
                                           ifname_option_values=self._ifname_option_values)
            elif n_cons == 1:
                if device_is_slave:
                    log.debug("%s: not creating default connection for slave device %s",
                              self.name, iface)
                    continue
                con = cons[0]
                log.debug("%s: dumping default autoconnection %s for %s",
                          self.name, con.get_uuid(), iface)
                s_con = con.get_setting_connection()
                s_con.set_property(NM.SETTING_CONNECTION_ID, iface)
                s_con.set_property(NM.SETTING_CONNECTION_INTERFACE_NAME, iface)
                if not bound_hwaddr_of_device(self._nm_client, iface, self._ifname_option_values):
                    s_wired = con.get_setting_wired()
                    s_wired.set_property(NM.SETTING_WIRED_MAC_ADDRESS, None)
                else:
                    log.debug("%s: iface %s bound to mac address by ifname boot option",
                              self.name, iface)
                con.commit_changes(True, None)
            elif n_cons > 1:
                if not device_is_slave:
                    log.warning("%s: %d non-slave connections found for device %s",
                                self.name, n_cons, iface)
                continue

            new_ifcfgs.append(iface)

        return new_ifcfgs
