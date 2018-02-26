#
# Persistent device configuration state for network module
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

import copy

from pyanaconda.core.regexes import IBFT_CONFIGURED_DEVICE_NAME
from pyanaconda.core.signal import Signal
from pyanaconda.modules.network.ifcfg import find_ifcfg_uuid_of_device, get_kickstart_network_data
from pyanaconda.modules.network.nm_client import get_iface_from_connection
from pyanaconda.modules.common.structures.network import NetworkDeviceConfiguration

import gi
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



class DeviceConfigurations(object):
    """Holds state of persistent configuration of network devices.

    Contains only configuration of devices supported by Anaconda.

    Configurations are hold in DeviceConfiguration objects.

    For a physical device there is only single configuration, the persistent element
    is the device. Connection uuid is not mandatory.

    For virtual devices there can be multiple configurations (persistent
    connections). The devices exist only when activated, the connection uuid
    is mandatory persistent element of the configuration.

    signals:
        configuration_changed - Provides old and new values of the configuration
                                in the form of a dictionary to the callback.
                                The idea here is that the configurations will have
                                no id but can be referenced by hashed content
                                instead.
    """

    # Maps types of connections to types of devices (both provided by NM)
    setting_types = {
        '802-11-wireless': NM.DeviceType.WIFI,
        '802-3-ethernet': NM.DeviceType.ETHERNET,
        'vlan': NM.DeviceType.VLAN,
        'bond': NM.DeviceType.BOND,
        'team': NM.DeviceType.TEAM,
        'bridge': NM.DeviceType.BRIDGE,
        'infiniband': NM.DeviceType.INFINIBAND,
        }

    def __init__(self, nm_client=None):
        self._device_configurations = None
        self.nm_client = nm_client or NM.Client.new()
        self.configuration_changed = Signal()

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

    def disconnect(self):
        """Disconnect from NetworkManager devices and connections updates."""
        for cb in [self._device_added_cb,
                   self._device_removed_cb,
                   self._connection_added_cb,
                   self._connection_removed_cb]:
            try:
                self.nm_client.disconnect_by_func(cb)
            except TypeError as e:
                if not "nothing connected" in str(e):
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
        self.configuration_changed.emit(NetworkDeviceConfiguration(), new_dev_cfg)

    def add_device(self, device):
        """Add or update configuration for libnm network device object.

        Filters out unsupported or special devices.

        For virtual devices it can only attach the device name to existing configuration
        with connection uuid (typically when the virtual device is activated).

        :param device: NetworkManager device object
        :type device: NMDevice
        :return: True if any configuration was added or modified, False otherwise
        :rtype: bool
        """
        iface = device.get_iface()

        # Only single configuration per existing device
        existing_cfgs = self.get_for_device(iface)
        if existing_cfgs:
            log.debug("not adding %s: already there: %s", iface, existing_cfgs)
            return False

        # Ignore unsupported devices
        if device.get_device_type() not in supported_device_types:
            log.debug("not adding %s: unsuported type", iface)
            return False

        # Ignore libvirt bridges
        if is_libvirt_device(iface):
            log.debug("not adding %s: libvirt special device", iface)
            return False

        # Ignore fcoe vlan devices (can be chopped off to IFNAMSIZ kernel limit)
        if iface.endswith(('-fcoe', '-fco', '-fc', '-f', '-')):
            log.debug("not adding %s: special fcoe vlan device", iface)
            return False

        # Ignore devices with active read-only connections (created by NM for iBFT VLAN)
        ac = device.get_active_connection()
        if ac:
            rc = ac.get_connection()
            # Getting of NMRemoteConnection can fail (None), isn't it a bug in NM?
            if rc:
                con_setting = rc.get_setting_connection()
                if con_setting and con_setting.get_read_only():
                    log.debug("not adding read-only connection "
                              "(assuming iBFT) for device %s", iface)
                    return False
                else:
                    log.debug("can't get remote connection of active connection "
                              "of device %s", iface)

        # TODO needs testing
        if device.get_device_type() == NM.DeviceType.WIFI:
            self.add(device_name=iface, device_type=NM.DeviceType.WIFI)
            return True

        # Find the connection for the device (assuming existence of single
        # ifcfg per non-slave device)
        connection_uuid = None

        cons = device.get_available_connections()
        if not cons:
            log.debug("no connection when adding device %s", iface)

        ifcfg_uuid = None
        if len(cons) > 1:
            # This can happen when activating device in initramfs and
            # reconfiguring it via kickstart without activation.
            log.debug("%s has multiple connections: %s", iface, [c.get_uuid() for c in cons])
            hwaddr = device.get_hw_address()
            ifcfg_uuid = find_ifcfg_uuid_of_device(iface, hwaddr=hwaddr)

        for c in cons:
            # Ignore slave connections
            if c.get_setting_connection() and c.get_setting_connection().get_slave_type():
                continue
            uuid = c.get_uuid()
            # In case of multiple connections ifcfg connections it the one.
            if not ifcfg_uuid or uuid == ifcfg_uuid:
                connection_uuid = uuid

        existing_cfgs = self.get_for_uuid(connection_uuid)
        if connection_uuid and existing_cfgs:
            # If we already have a connection for the device it is a virtual device appearing
            updated_cfg = existing_cfgs[0]
            old_cfg = copy.deepcopy(updated_cfg)
            updated_cfg.device_name = iface
            self.configuration_changed.emit(old_cfg, updated_cfg)
            log.debug("attached device %s to connection %s", iface, connection_uuid)
        else:
            self.add(device_name=iface, connection_uuid=connection_uuid,
                     device_type=device.get_device_type())
            log.debug("added device configuration for device %s", iface)
        return True

    def _get_vlan_interface_name_from_connection(self, connection):
        """Get vlan interface name from vlan connection.

        If no interface name is specified in the connection settings, infer
        the value as <PARENT_IFACE>.<VLAN_ID> - same as NetworkManager.
        """
        iface = connection.get_setting_connection().get_interface_name()
        if not iface:
            setting_vlan = connection.get_setting_vlan()
            if setting_vlan:
                vlanid = setting_vlan.get_id()
                parent = setting_vlan.get_parent()
                # if parent is specified by UUID
                if len(parent) == 36:
                    parent = get_iface_from_connection(parent)
                if vlanid is not None and parent:
                    iface = default_ks_vlan_interface_name(parent, vlanid)
        return iface

    def add_connection(self, connection):
        """Add or update configuration for libnm connection object.

        Filters out unsupported or special devices.

        Only single configuration for given uuid is allowed.
        For devices without persistent connection it will just update the configuration.

        :param device: NetworkManager conenction object
        :type device: NMConnection
        :return: True if any configuration was added or modified, False otherwise
        :rtype: bool
        """
        uuid = connection.get_uuid()

        existing_cfg = self.get_for_uuid(uuid)
        if existing_cfg:
            log.debug("not adding %s: already existing: %s", uuid, existing_cfg)
            return False

        con_setting = connection.get_setting_connection()
        if con_setting and con_setting.get_read_only():
            log.debug("not adding %s: read-only connection", uuid)
            return False

        iface = get_iface_from_connection(uuid)

        if is_libvirt_device(iface or ""):
            log.debug("not adding %s: libvirt special device connection", uuid)
            return False

        if is_ibft_configured_device(iface or ""):
            log.debug("not adding %s: configured from iBFT", uuid)
            return False

        connection_type = connection.get_connection_type()
        device_type = self.setting_types.get(connection_type, None)

        if device_type not in supported_device_types:
            log.debug("not adding %s: unsupported type", uuid)
            return False

        if device_type == NM.DeviceType.ETHERNET:
            if con_setting and con_setting.get_master():
                log.debug("not adding %s: slave connection", uuid)
                return False

        # Wireless settings are handled in scope of configuration of its device
        if device_type == NM.DeviceType.WIFI:
            log.debug("not adding %s: wireless connection", uuid)
            return False

        # Handle also vlan connections without interface-name specified
        if device_type == NM.DeviceType.VLAN:
            if not iface:
                iface = self._get_vlan_interface_name_from_connection(connection)
                log.debug("interface name for vlan connection %s inferred: %s", uuid, iface)

        existing_cfgs = self.get_for_device(iface)
        if existing_cfgs:
            for cfg in existing_cfgs:
                if cfg.connection_uuid:
                    log.debug("not adding %s, already have %s for device %s",
                            uuid, cfg.connection_uuid, cfg.device_name)
                    return False
                else:
                    old_cfg = copy.deepcopy(cfg)
                    cfg.connection_uuid = uuid
                    self.configuration_changed.emit(old_cfg, cfg)
                    log.debug("attaching connection %s to device %s", uuid, cfg.device_name)
        else:
            self.add(connection_uuid=uuid, device_type=device_type)
            log.debug("added connection %s", uuid)
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
        # We just remove the device from the DeviceConfiguration, keeping the object
        # assuming it is just a disconnected virtual device.
        iface = device.get_iface()
        log.debug("NM device removed: %s", iface)
        dev_cfgs = self.get_for_device(iface)
        for cfg in dev_cfgs:
            if cfg.connection_uuid:
                old_cfg = copy.deepcopy(cfg)
                cfg.device_name = ""
                self.configuration_changed.emit(old_cfg, cfg)
                log.debug("device name %s removed from %s", iface, cfg)
            else:
                empty_cfg = NetworkDeviceConfiguration()
                self._device_configurations.remove(cfg)
                self.configuration_changed.emit(cfg, empty_cfg)
                log.debug("%s removed", cfg)

    def _connection_added_cb(self, client, connection):
        log.debug("NM connection added: %s", connection.get_uuid())
        self.add_connection(connection)

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
                self.configuration_changed.emit(old_cfg, cfg)
                log.debug("connection uuid %s removed from %s", uuid, cfg)
            else:
                empty_cfg = NetworkDeviceConfiguration()
                self._device_configurations.remove(cfg)
                self.configuration_changed.emit(cfg, empty_cfg)
                log.debug("%s removed", cfg)

    def __str__(self):
        return str(self._device_configurations)

    def __repr__(self):
        return "DeviceConfigurations({})".format(self.nm_client)

    def _is_device_activated(self, iface):
        device = self.nm_client.get_device_by_iface(iface)
        return device and device.get_state() == NM.DeviceState.ACTIVATED

    def get_kickstart_data(self, network_data_class):
        rv = []
        for i, cfg in enumerate(self._device_configurations or []):
            network_data = None
            if cfg.device_type != NM.DeviceType.WIFI and cfg.connection_uuid:
                network_data = get_kickstart_network_data(cfg.connection_uuid,
                                                          network_data_class)
            if not network_data:
                log.debug("Device configuration %s does not generate any kickstart data", cfg)
                continue
            if cfg.device_name:
                if self._is_device_activated(cfg.device_name):
                    network_data.activate = True
                else:
                    # First network command defaults to --activate so we must
                    # use --no-activate explicitly to prevent the default
                    if i == 0:
                        network_data.activate = False
            rv.append(network_data)
        return rv

def is_libvirt_device(iface):
    return iface.startswith("virbr")

def is_ibft_configured_device(iface):
    return IBFT_CONFIGURED_DEVICE_NAME.match(iface)

def default_ks_vlan_interface_name(parent, vlanid):
    return "%s.%s" % (parent, vlanid)
