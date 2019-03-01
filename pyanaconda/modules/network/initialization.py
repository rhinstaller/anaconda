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
    ensure_active_connection_for_device, update_connection_from_ksdata, add_connection_from_ksdata
from pyanaconda.modules.network.ifcfg import get_ifcfg_file_of_device

log = get_module_logger(__name__)



class ApplyKickstartTask(Task):
    """Task for application of kickstart network configuration."""

    def __init__(self, nm_client, network_data, supported_devices, bootif, ifname_option_values):
        """Create a new task.

        :param nm_client: NetworkManager client used as configuration backend
        :type nm_client: NM.Client
        :param network_data: kickstart network data to be applied
        :type: pykickstart NetworkData
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
