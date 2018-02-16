#
# Kickstart module for network and hostname settings
#
# Copyright (C) 2018 Red Hat, Inc.
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
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.dbus import DBus, SystemBus
from pyanaconda.dbus.structure import get_structure
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartModule
from pyanaconda.modules.common.constants.services import NETWORK, HOSTNAME
from pyanaconda.modules.network.network_interface import NetworkInterface
from pyanaconda.modules.network.kickstart import NetworkKickstartSpecification, \
    update_network_hostname_data, update_network_data_with_default_device, DEFAULT_DEVICE_SPECIFICATION, \
    update_first_network_command_activate_value
from pyanaconda.modules.network.firewall import FirewallModule
from pyanaconda.modules.network.device_configuration import DeviceConfigurations, supported_device_types
from pyanaconda.modules.network.nm_client import nm_client, get_device_name_from_network_data, \
    add_connection_from_ksdata, update_connection_from_ksdata
from pyanaconda.modules.network.ifcfg import find_ifcfg_file_of_device, ifcfg_is_from_kickstart, \
    find_ifcfg_uuid_of_device

import gi
gi.require_version("NM", "1.0")
from gi.repository import NM

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class NetworkModule(KickstartModule):
    """The Network module."""

    def __init__(self):
        super().__init__()

        self._firewall_module = FirewallModule()

        self.hostname_changed = Signal()
        self._hostname = "localhost.localdomain"

        self.current_hostname_changed = Signal()
        self._hostname_service_proxy = None

        if conf.system.provides_system_bus:
            self._hostname_service_proxy = HOSTNAME.get_proxy()
            self._hostname_service_proxy.PropertiesChanged.connect(self._hostname_service_properties_changed)

        self.connected_changed = Signal()
        self.nm_client = None
        # TODO fallback solution - use Gio/GNetworkMonitor ?
        if SystemBus.check_connection():
            if nm_client.get_nm_running():
                self.nm_client = nm_client
                self.nm_client.connect("notify::%s" % NM.CLIENT_STATE, self._nm_state_changed)
                initial_state = self.nm_client.get_state()
                self.set_connected(self._nm_state_connected(initial_state))
            else:
                log.debug("NetworkManager is not running.")

        self._original_network_data = []
        self._device_configurations = None
        self.configuration_changed = Signal()

        self._default_device_specification = DEFAULT_DEVICE_SPECIFICATION
        self._bootif = None

    def publish(self):
        """Publish the module."""
        self._firewall_module.publish()

        DBus.publish_object(NETWORK.object_path, NetworkInterface(self))
        DBus.register_service(NETWORK.service_name)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return NetworkKickstartSpecification

    @property
    def default_device_specification(self):
        """Get the default specification for missing kickstart --device option."""
        return self._default_device_specification

    @default_device_specification.setter
    def default_device_specification(self, specification):
        """Set the default specification for missing kickstart --device option.

        :param specifiacation: device specification accepted by network --device option
        :type specification: str
        """
        self._default_device_specification = specification
        log.debug("default kickstart device specification set to %s", specification)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        log.debug("kickstart to be processed:\n%s", str(data))

        # Handle default value for --device
        spec = self.default_device_specification
        if update_network_data_with_default_device(data.network.network, spec):
            log.debug("used '%s' for missing network --device options", spec)
        if update_first_network_command_activate_value(data.network.network):
            log.debug("updated activate value of the first network command (None -> True)")

        self._original_network_data = data.network.network
        if data.network.hostname:
            self.set_hostname(data.network.hostname)
        self._firewall_module.process_kickstart(data)

        log.debug("processed kickstart:\n%s", str(data))

    def generate_kickstart(self):
        """Return the kickstart string."""

        data = self.get_kickstart_handler()
        if self._device_configurations:
            device_data = self._device_configurations.get_kickstart_data(data.NetworkData)
            log.debug("using device configurations to generate kickstart")
        else:
            device_data = self._original_network_data
            log.debug("using original kickstart data to generate kickstart")
        data.network.network = device_data

        hostname_data = data.NetworkData(hostname=self.hostname, bootProto="")
        update_network_hostname_data(data.network.network, hostname_data)

        # firewall
        self._firewall_module.setup_kickstart(data)

        log.debug("generated kickstart:\n%s", str(data))

        return str(data)

    @property
    def hostname(self):
        """Return the hostname."""
        return self._hostname

    def set_hostname(self, hostname):
        """Set the hostname."""
        self._hostname = hostname
        self.hostname_changed.emit()
        log.debug("Hostname is set to %s", hostname)

    def _hostname_service_properties_changed(self, interface, changed, invalid):
        if interface == HOSTNAME.interface_name and "Hostname" in changed:
            hostname = changed["Hostname"]
            self.current_hostname_changed.emit(hostname)
            log.debug("Current hostname changed to %s", hostname)

    def get_current_hostname(self):
        """Return current hostname of the system."""
        if self._hostname_service_proxy:
            return self._hostname_service_proxy.Hostname

        log.debug("Current hostname cannot be get.")
        return ""

    def set_current_hostname(self, hostname):
        """Set current system hostname."""
        if not self._hostname_service_proxy:
            log.debug("Current hostname cannot be set.")
            return

        self._hostname_service_proxy.SetHostname(hostname, False)
        log.debug("Current hostname is set to %s", hostname)

    @property
    def nm_available(self):
        return self.nm_client is not None

    @property
    def connected(self):
        """Is the system connected to the network?"""
        if self.nm_available:
            return self._connected
        else:
            log.debug("Connectivity state can't be determined, assuming connected.")
            return True

    def set_connected(self, connected):
        """Set network connectivity status."""
        self._connected = connected
        self.connected_changed.emit()
        self.module_properties_changed.emit()
        log.debug("Connected to network: %s", connected)

    def is_connecting(self):
        """Is NM in connecting state?"""
        if self.nm_available:
            return self.nm_client.get_state() == NM.State.CONNECTING
        else:
            log.debug("Connectivity state can't be determined, assuming not connecting.")
            return False

    @staticmethod
    def _nm_state_connected(state):
        return state in (NM.State.CONNECTED_LOCAL, NM.State.CONNECTED_SITE, NM.State.CONNECTED_GLOBAL)

    def _nm_state_changed(self, *args):
        state = self.nm_client.get_state()
        log.debug("NeworkManager state changed to %s", state)
        self.set_connected(self._nm_state_connected(state))

    def create_device_configurations(self):
        self._device_configurations = DeviceConfigurations(self.nm_client)
        self._device_configurations.configuration_changed.connect(self.device_configurations_changed_cb)
        self._device_configurations.reload()
        self._device_configurations.connect()

    def get_device_configurations(self):
        if not self._device_configurations:
            return []
        return self._device_configurations.get_all()

    def device_configurations_changed_cb(self, old_dev_cfg, new_dev_cfg):
        log.debug("Configuration changed: %s -> %s", old_dev_cfg, new_dev_cfg)
        log.debug("%s", self._device_configurations)
        self.configuration_changed.emit([
            (get_structure(old_dev_cfg), get_structure(new_dev_cfg))
        ])

    def consolidate_initramfs_connections(self):
        """Ensure devices configured in initramfs have no more than one NM connection.

        In case of multiple connections for device having ifcfg configuration from
        boot options, the connection should correspond to the ifcfg file.
        NetworkManager can be generating additional in-memory connection in case it
        fails to match device configuration to the ifcfg (#1433891).  By
        reactivating the device with ifcfg connection the generated in-memory
        connection will be deleted by NM.

        Don't enforce on slave devices for which having multiple connections can be
        valid (slave connection, regular device connection).
        """
        consolidated_devices = []

        for device in self.nm_client.get_devices():
            cons = device.get_available_connections()
            number_of_connections = len(cons)
            iface = device.get_iface()

            if number_of_connections < 2:
                continue

            # Ignore devices which are slaves
            if any(con.get_setting_connection().get_master() for con in cons):
                log.debug("consolidate %d initramfs connections for %s: it is OK, device is a slave",
                          number_of_connections, iface)
                continue

            ifcfg_path = find_ifcfg_file_of_device(iface)
            if not ifcfg_path:
                log.error("consolidate %d initramfs connections for %s: no ifcfg file",
                          number_of_connections, iface)
                continue

            # Handle only ifcfgs created from boot options in initramfs
            # (Kickstart based ifcfgs are handled when applying kickstart)
            if ifcfg_is_from_kickstart(ifcfg_path):
                continue

            log.debug("consolidate %d initramfs connections for %s: ensure active ifcfg connection",
                      number_of_connections, iface)

            self._ensure_active_ifcfg_connection_for_device(iface, only_replace=True)

            consolidated_devices.append(iface)

        return consolidated_devices

    def _ensure_active_ifcfg_connection_for_device(self, iface, only_replace=False):
        """Make sure active connection of a device is the one of ifcfg file

        :param iface: name of device to apply the connection to
        :type iface: str
        :param only_replace: apply the connection only if the device has different
                             active connection
        :type only_replace: bool
        """
        msg = "not activating"
        active_uuid = None
        ifcfg_uuid = find_ifcfg_uuid_of_device(iface)
        device = self.nm_client.get_device_by_iface(iface)
        if device:
            ac = device.get_active_connection()
            if ac or not only_replace:
                active_uuid = ac.get_uuid()
                if ifcfg_uuid != active_uuid:
                    ifcfg_con = self.nm_client.get_connection_by_uuid(ifcfg_uuid)
                    # TODO sync somewhere?
                    self.nm_client.activate_connection_async(ifcfg_con, None, None, None)
                    msg = "activating"
        log.debug("ensure active ifcfg connection for %s (%s -> %s): %s",
                  iface, active_uuid, ifcfg_uuid, msg)

    def get_supported_devices(self):
        """Get names of existing supported devices on the system."""
        return [device.get_iface() for device in self.nm_client.get_devices()
                if device.get_device_type() in supported_device_types]

    @property
    def bootif(self):
        """Get the value of kickstart --bootif option."""
        return self._bootif

    @bootif.setter
    def bootif(self, specification):
        """Set the value of kickstart --bootif option.

        :param specifiacation: mac address specified in kickstart --bootif option
        :type specification: str
        """
        self._bootif = specification
        log.debug("bootif device specification is set to %s", specification)

    def apply_kickstart(self):
        """Apply kickstart configuration which has not already been applied.

        * Activate configurations created in initramfs if --activate is True.
        * Create configurations for %pre kickstart commands and activate eventually.

        :returns: list of devices to which kickstart configuration was applied
        """

        applied_devices = []

        if not self._original_network_data:
            log.debug("No kickstart data to apply.")
            return []

        for network_data in self._original_network_data:

            # Wireless is not supported
            if network_data.essid:
                log.info("Wireless devices configuration is not supported.")
                continue

            supported_devices = self.get_supported_devices()
            device_name = get_device_name_from_network_data(network_data,
                                                            supported_devices,
                                                            self._bootif)
            if not device_name:
                log.warning("apply kickstart: --device %s not found", network_data.device)
                continue

            ifcfg_path = find_ifcfg_file_of_device(device_name)
            if ifcfg_path:
                if ifcfg_is_from_kickstart(ifcfg_path):
                    if network_data.activate:
                        self._ensure_active_ifcfg_connection_for_device(device_name)
                        applied_devices.append(device_name)
                    continue

            # If there is no kickstart ifcfg from initramfs the command was added
            # in %pre section after switch root, so apply it now
            applied_devices.append(device_name)
            if ifcfg_path:
                # if the device was already configured in initramfs update the settings
                con_uuid = find_ifcfg_uuid_of_device(device_name)
                log.debug("pre kickstart - updating settings %s of device %s",
                          con_uuid, device_name)
                update_connection_from_ksdata(con_uuid, network_data, device_name=device_name)
                if network_data.activate:
                    connection = self.nm_client.get_connection_by_uuid(con_uuid)
                    device = self.nm_client.get_device_by_iface(device_name)
                    self.nm_client.activate_connection_async(connection, device, None, None)
                    log.debug("pre kickstart - activating connection %s with device %s",
                              con_uuid, device_name)
            else:
                log.debug("pre kickstart - adding connection for %s", device_name)
                add_connection_from_ksdata(network_data, device_name,
                                           activate=network_data.activate)

        return applied_devices
