#
# Persistent device configuration state for network module
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

import gi

from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.network import NetworkDeviceConfiguration
from pyanaconda.modules.network.constants import (
    NM_CONNECTION_TYPE_BOND,
    NM_CONNECTION_TYPE_BRIDGE,
    NM_CONNECTION_TYPE_ETHERNET,
    NM_CONNECTION_TYPE_INFINIBAND,
    NM_CONNECTION_TYPE_TEAM,
    NM_CONNECTION_TYPE_VLAN,
    NM_CONNECTION_TYPE_WIFI,
)
from pyanaconda.modules.network.nm_client import (
    get_config_file_connection_of_device,
    get_iface_from_connection,
    get_vlan_interface_name_from_connection,
    is_bootif_connection,
)
from pyanaconda.modules.network.utils import is_ibft_configured_device, is_nbft_device

gi.require_version("NM", "1.0")
from gi.repository import NM

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)


supported_device_types = [
    NM.DeviceType.ETHERNET,
    NM.DeviceType.WIFI,
    NM.DeviceType.INFINIBAND,
    NM.DeviceType.BOND,
    NM.DeviceType.VLAN,
    NM.DeviceType.BRIDGE,
    NM.DeviceType.TEAM,
]

supported_wired_device_types = [
    NM.DeviceType.ETHERNET,
    NM.DeviceType.INFINIBAND,
]

virtual_device_types = [
    NM.DeviceType.BOND,
    NM.DeviceType.VLAN,
    NM.DeviceType.BRIDGE,
    NM.DeviceType.TEAM,
]


class DeviceConfigurations:
    """Stores the state of persistent configuration of network devices.

    Contains only configuration of devices supported by Anaconda.

    Configurations are hold in NetworkDeviceConfiguration objects.

    For a physical device there is only single NetworkDeviceConfiguration
    object bound to the device name (the mandatory persistent element of
    the object).  The uuid corresponds to the configuration of the device
    for installed system.

    For a virtual device there can be multiple NetworkDeviceConfiguration
    objects, bound to uuid of the device configuration (the mandatory
    persistent element of the object).  The device name is set in the
    object only if there exists respective active device with the
    configuration given by uuid applied.

    Configurations correspond to NetworkManager persistent connections by
    their uuid.

    signals:
        configurations_changed - Provides list of changes - tuples containing
                                 NetworkDeviceConfiguration objects with old and new
                                 values.
    """

    # Maps types of connections to types of devices (both provided by NM)
    setting_types = {
        NM_CONNECTION_TYPE_WIFI: NM.DeviceType.WIFI,
        NM_CONNECTION_TYPE_ETHERNET: NM.DeviceType.ETHERNET,
        NM_CONNECTION_TYPE_VLAN: NM.DeviceType.VLAN,
        NM_CONNECTION_TYPE_BOND: NM.DeviceType.BOND,
        NM_CONNECTION_TYPE_TEAM: NM.DeviceType.TEAM,
        NM_CONNECTION_TYPE_BRIDGE: NM.DeviceType.BRIDGE,
        NM_CONNECTION_TYPE_INFINIBAND: NM.DeviceType.INFINIBAND,
    }

    def __init__(self, nm_client=None):
        self._device_configurations = None
        self.nm_client = nm_client or NM.Client.new()
        self.configurations_changed = Signal()

    def reload(self):
        """Reload the state from the system."""
        self._device_configurations = []
        for device in self.nm_client.get_devices():
            self.add_device(device)
        for connection in self.nm_client.get_connections():
            self.add_connection(connection)

    def connect(self):
        """Connect to NetworkManager for devices and connections updates."""
        self.nm_client.connect("device-added", self._device_added_cb)
        self.nm_client.connect("device-removed", self._device_removed_cb)
        self.nm_client.connect("connection-added", self._connection_added_cb)
        self.nm_client.connect("connection-removed", self._connection_removed_cb)
        self.nm_client.connect("active-connection-added", self._active_connection_added_cb)

    def disconnect(self):
        """Disconnect from NetworkManager devices and connections updates."""
        for cb in [self._device_added_cb,
                   self._device_removed_cb,
                   self._connection_added_cb,
                   self._connection_removed_cb,
                   self._active_connection_added_cb]:
            try:
                self.nm_client.disconnect_by_func(cb)
            except TypeError as e:
                if "nothing connected" not in str(e):
                    log.debug("%s", e)

    def add(self, device_name=None, connection_uuid=None, device_type=None):
        """Add a new NetworkDeviceConfiguration."""
        new_dev_cfg = NetworkDeviceConfiguration()
        if device_name is not None:
            new_dev_cfg.device_name = device_name
        if connection_uuid is not None:
            new_dev_cfg.connection_uuid = connection_uuid
        if device_type is not None:
            new_dev_cfg.device_type = device_type
        self._device_configurations.append(new_dev_cfg)
        log.debug("added %s", new_dev_cfg)
        self.configurations_changed.emit([(NetworkDeviceConfiguration(), new_dev_cfg)])

    def attach(self, dev_cfg, device_name=None, connection_uuid=None):
        """Attach device or connection to existing NetworkDeviceConfiguration."""
        if not device_name and not connection_uuid:
            return
        old_dev_cfg = copy.deepcopy(dev_cfg)
        if device_name:
            dev_cfg.device_name = device_name
            log.debug("attached device name to %s", dev_cfg)
        if connection_uuid:
            dev_cfg.connection_uuid = connection_uuid
            log.debug("attached connection uuid to %s", dev_cfg)
        self.configurations_changed.emit([(old_dev_cfg, dev_cfg)])

    def _should_add_device(self, device):
        """Should the network device be added ?

        :param device: NetworkManager device object
        :type device: NMDevice
        :returns: tuple containing reply and message with reason
        :rtype: (bool, str)
        """
        decline_reason = ""

        # Ignore unsupported device types
        if device.get_device_type() not in supported_device_types:
            decline_reason = "unsupported type"

        # Ignore libvirt bridges
        elif is_libvirt_device(device.get_iface()):
            decline_reason = "libvirt special device"

        # Ignore fcoe vlan devices (can be chopped off to IFNAMSIZ kernel limit)
        elif device.get_iface().endswith(('-fcoe', '-fco', '-fc', '-f', '-')):
            decline_reason = "special FCoE vlan device"

        # Ignore devices configured via iBFT, ie
        # devices with active read-only connections (created by NM for iBFT VLAN)
        elif self._has_read_only_active_connection(device):
            decline_reason = "has active read-only connection (assuming configuration via iBFT)"

        reply = not decline_reason
        return reply, decline_reason

    def _has_read_only_active_connection(self, device):
        """Does the device have read-only active connection ?

        :param device: NetworkManager device object
        :type device: NMDevice
        """
        ac = device.get_active_connection()
        if ac:
            rc = ac.get_connection()
            # Getting of NMRemoteConnection can fail (None), isn't it a bug in NM?
            if rc:
                con_setting = rc.get_setting_connection()
                if con_setting and con_setting.get_read_only():
                    return True
            else:
                log.debug("can't get remote connection of active connection "
                          "of device %s", device.get_iface())
        return False

    def _find_connection_uuid_of_device(self, device):
        """Find uuid of connection that should be bound to the device.

        Assumes existence of no more than one config file per non-port physical
        device.

        :param device: NetworkManager device object
        :type device: NMDevice
        :returns: uuid of NetworkManager connection
        :rtype: str

        """
        uuid = None
        iface = device.get_iface()

        # For virtual device only the active connection could be the connection
        if device.get_device_type() in virtual_device_types:
            ac = device.get_active_connection()
            if ac:
                uuid = ac.get_connection().get_uuid()
            else:
                log.debug("no active connection for virtual device %s", iface)
        # For physical device we need to pick the right connection in some
        # cases.
        else:
            cons = [c for c in device.get_available_connections() if not is_bootif_connection(c)]
            config_uuid = None
            if not cons:
                log.debug("no available connection for physical device %s", iface)
            elif len(cons) > 1:
                # This can happen when activating device in initramfs and
                # reconfiguring it via kickstart without activation.
                log.debug("physical device %s has multiple connections: %s",
                          iface, [c.get_uuid() for c in cons])
                hwaddr = device.get_hw_address()
                config_uuid = get_config_file_connection_of_device(
                    self.nm_client, iface, device_hwaddr=hwaddr)
                log.debug("config file connection for %s: %s", iface, config_uuid)

            for c in cons:
                # Ignore port connections
                if c.get_setting_connection() and c.get_setting_connection().get_port_type():
                    continue
                candidate_uuid = c.get_uuid()
                # In case of multiple connections choose the config connection
                if not config_uuid or candidate_uuid == config_uuid:
                    uuid = candidate_uuid

        return uuid

    def add_device(self, device):
        """Add or update configuration for libnm network device object.

        Filters out unsupported or special devices.

        For virtual devices it may only attach the device name to existing
        configuration with connection uuid (typically when the virtual device
        is activated).

        :param device: NetworkManager device object
        :type device: NMDevice
        :return: True if any configuration was added or modified, False otherwise
        :rtype: bool
        """
        iface = device.get_iface()

        # Only single configuration per existing device
        existing_cfgs = self.get_for_device(iface)
        if existing_cfgs:
            log.debug("add_device: not adding %s: already there: %s", iface, existing_cfgs)
            return False

        # Filter out special or unsupported devices
        should_add, reason = self._should_add_device(device)
        if not should_add:
            log.debug("add_device: not adding %s: %s", iface, reason)
            return False

        log.debug("add device: adding device %s", iface)

        # Handle wireless device
        # TODO needs testing
        if device.get_device_type() == NM.DeviceType.WIFI:
            self.add(device_name=iface, device_type=NM.DeviceType.WIFI)
            return True

        existing_connection_uuid = self._find_connection_uuid_of_device(device)
        existing_cfgs_for_uuid = self.get_for_uuid(existing_connection_uuid)

        if existing_connection_uuid and existing_cfgs_for_uuid:
            existing_cfg = existing_cfgs_for_uuid[0]
            self.attach(existing_cfg, device_name=iface)
        else:
            self.add(device_name=iface, connection_uuid=existing_connection_uuid,
                     device_type=device.get_device_type())
        return True

    def _should_add_connection(self, connection):
        """Should the connection be added ?

        :param connection: NetworkManager connection object
        :type connection: NMConnection
        :returns: tuple containing reply and message with reason
        :rtype: (bool, str)
        """
        decline_reason = ""

        uuid = connection.get_uuid()
        iface = get_iface_from_connection(self.nm_client, uuid)
        connection_type = connection.get_connection_type()
        device_type = self.setting_types.get(connection_type, None)
        con_setting = connection.get_setting_connection()

        # Ignore read-only connections
        if con_setting and con_setting.get_read_only():
            decline_reason = "read-only connection"

        # Ignore libvirt devices
        elif is_libvirt_device(iface or ""):
            decline_reason = "libvirt special device connection"

        # TODO we might want to remove the check if the devices are not renamed
        # to ibftX in dracut (BZ #1749331)
        # Ignore devices configured via iBFT
        elif is_ibft_configured_device(iface or ""):
            decline_reason = "configured from iBFT"

        elif is_nbft_device(iface or ""):
            decline_reason = "nBFT device"

        # Ignore unsupported device types
        elif device_type not in supported_device_types:
            decline_reason = "unsupported type"

        # BOOTIF connection created in initramfs
        elif is_bootif_connection(connection):
            decline_reason = "BOOTIF connection from initramfs"

        # Ignore port connections
        elif device_type == NM.DeviceType.ETHERNET:
            if con_setting and con_setting.get_controller():
                decline_reason = "port connection"

        # Wireless settings are handled in scope of configuration of its device
        elif device_type == NM.DeviceType.WIFI:
            decline_reason = "wireless connection"

        reply = not decline_reason
        return reply, decline_reason

    def _find_existing_cfg_for_iface(self, iface):
        cfgs = self.get_for_device(iface)
        if cfgs:
            if len(cfgs) > 1:
                log.error("multiple configurations for device %s: %s", iface, cfgs)
            return cfgs[0]
        return None

    def add_connection(self, connection):
        """Add or update configuration for libnm connection object.

        Filters out unsupported or special devices.

        Only single configuration for given uuid is allowed.  For devices
        without persistent connection it will just update the configuration.

        :param connection: NetworkManager conenction object
        :type connection: NMConnection
        :return: True if any configuration was added or modified, False otherwise
        :rtype: bool
        """
        uuid = connection.get_uuid()

        existing_cfg = self.get_for_uuid(uuid)
        if existing_cfg:
            log.debug("add_connection: not adding %s: already existing: %s", uuid, existing_cfg)
            return False

        # Filter out special or unsupported devices
        should_add, reason = self._should_add_connection(connection)
        if not should_add:
            log.debug("add_connection: not adding %s: %s", uuid, reason)
            return False

        connection_type = connection.get_connection_type()
        device_type = self.setting_types.get(connection_type, None)
        iface = get_iface_from_connection(self.nm_client, uuid)

        # Require interface name for physical devices
        if device_type in supported_wired_device_types and not iface:
            log.debug("add_connection: not adding %s: interface name is required for type %s",
                      uuid, device_type)
            return False

        # Handle also vlan connections without interface-name specified
        if device_type == NM.DeviceType.VLAN:
            if not iface:
                iface = get_vlan_interface_name_from_connection(self.nm_client, connection)
                log.debug("add_connection: interface name for vlan connection %s inferred: %s",
                          uuid, iface)

        iface_cfg = self._find_existing_cfg_for_iface(iface)

        log.debug("add_connection: adding connection %s", uuid)

        # virtual devices
        if device_type in virtual_device_types:
            if iface_cfg:
                if not iface_cfg.connection_uuid:
                    self.attach(iface_cfg, connection_uuid=uuid)
                    return True
                else:
                    # TODO check that the device shouldn't be reattached?
                    log.debug("add_connection: already have %s for device %s, adding another one",
                              iface_cfg.connection_uuid, iface_cfg.device_name)
            self.add(connection_uuid=uuid, device_type=device_type)
        # physical devices
        else:
            if iface_cfg:
                if iface_cfg.connection_uuid:
                    log.debug("add_connection: already have %s for device %s, not adding %s",
                              iface_cfg.connection_uuid, iface_cfg.device_name, uuid)
                    return False
                else:
                    self.attach(iface_cfg, connection_uuid=uuid)
            else:
                self.add(connection_uuid=uuid, device_type=device_type)
        return True

    def get_for_device(self, device_name):
        return [cfg for cfg in self._device_configurations
                if cfg.device_name == device_name]

    def get_for_uuid(self, connection_uuid):
        return [cfg for cfg in self._device_configurations
                if cfg.connection_uuid == connection_uuid]

    def get_all(self):
        return list(self._device_configurations)

    def _device_added_cb(self, client, device, *args):
        # We need to wait for valid state before adding the device
        log.debug("NM device added: %s", device.get_iface())
        if device.get_state() == NM.DeviceState.UNKNOWN:
            device.connect("state-changed", self._added_device_state_changed_cb)
        else:
            self.add_device(device)

    def _added_device_state_changed_cb(self, device, new_state, *args):
        # We need to wait for valid state before adding the device
        if new_state != NM.DeviceState.UNKNOWN:
            device.disconnect_by_func(self._added_device_state_changed_cb)
            self.add_device(device)

    def _device_removed_cb(self, client, device, *args):
        # We just remove the device from the NetworkDeviceConfiguration, keeping the object
        # assuming it is just a disconnected virtual device.
        iface = device.get_iface()
        log.debug("NM device removed: %s", iface)
        dev_cfgs = self.get_for_device(iface)
        for cfg in dev_cfgs:
            if cfg.connection_uuid and cfg.device_type in virtual_device_types:
                old_cfg = copy.deepcopy(cfg)
                cfg.device_name = ""
                self.configurations_changed.emit([(old_cfg, cfg)])
                log.debug("device name %s removed from %s", iface, cfg)
            else:
                empty_cfg = NetworkDeviceConfiguration()
                self._device_configurations.remove(cfg)
                self.configurations_changed.emit([(cfg, empty_cfg)])
                log.debug("%s removed", cfg)

    def _connection_added_cb(self, client, connection):
        log.debug("NM connection added: %s", connection.get_uuid())
        self.add_connection(connection)

    def _active_connection_added_cb(self, client, connection):
        connection_uuid = connection.get_uuid()
        log.debug("NM active connection added: %s", connection_uuid)
        dev_cfgs = self.get_for_uuid(connection_uuid)
        for cfg in dev_cfgs:
            if not cfg.device_name:
                devices = connection.get_devices()
                if devices:
                    log.debug("adding active connection %s", connection_uuid)
                    self.attach(cfg, device_name=devices[0].get_iface())

    def _connection_removed_cb(self, client, connection):
        uuid = connection.get_uuid()
        log.debug("NM connection removed: %s", uuid)
        # Remove the configuration if it does not have a device_name
        # which means it is a virtual device configurtation
        dev_cfgs = self.get_for_uuid(uuid)
        for cfg in dev_cfgs:
            if cfg.device_name:
                old_cfg = copy.deepcopy(cfg)
                cfg.connection_uuid = ""
                self.configurations_changed.emit([(old_cfg, cfg)])
                log.debug("connection uuid %s removed from %s", uuid, cfg)
            else:
                empty_cfg = NetworkDeviceConfiguration()
                self._device_configurations.remove(cfg)
                self.configurations_changed.emit([(cfg, empty_cfg)])
                log.debug("%s removed", cfg)

    def __str__(self):
        return str(self._device_configurations)

    def __repr__(self):
        return "DeviceConfigurations({})".format(self.nm_client)


def is_libvirt_device(iface):
    return iface.startswith("virbr")
