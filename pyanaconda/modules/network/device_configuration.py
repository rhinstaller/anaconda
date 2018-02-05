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

from pyanaconda.core.regexes import IBFT_CONFIGURED_DEVICE_NAME
from pyanaconda.modules.network import ifcfg

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


class DeviceConfiguration(object):
    """Holds references to persistent configuration of a device.

    Binds device name and NM connection (by its uuid). Device type is
    additional information useful for clients.
    """

    def __init__(self, device_name=None, connection_uuid=None, device_type=None):
        """Create DeviceConfiguration instance.

        :param device_name: name of the device
        :type device_name: str
        :param connection_uuid: uuid of NetworkManager persistent connection
        :type connection_uuid: str
        :param device_type: type of device
        :type device_type: NM.DeviceType
        """
        self.device_name = device_name
        self.connection_uuid = connection_uuid
        self.device_type = device_type

    @property
    def ifcfg_path(self):
        """Path to ifcfg file for the configuration.

        return: ifcfg file path or None if it does not exist
        rtype: str
        """
        if not self.connection_uuid:
            return None
        return ifcfg.find_ifcfg_file([("UUID", self.connection_uuid)])

    def __repr__(self):
        return "DeviceConfiguration(device_name={}, connection_uuid={}, device_type={})".format(
            self.device_name, self.connection_uuid, self.device_type)


class DeviceConfigurations(object):
    """Holds state of persistent configuration of network devices.

    Contains only configuration of devices supported by Anaconda.

    Configurations are hold in DeviceConfiguration objects.

    For a physical device there is only single configuration, the persistent element
    is the device. Connection uuid is not mandatory.

    For virtual devices there can be multiple configurations (persistent
    connections). The devices exist only when activated, the connection uuid :w
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

    def reload(self):
        """Reload the state from the system."""
        self._device_configurations = []
        for device in self.nm_client.get_devices():
            self.add_device(device)
        for connection in self.nm_client.get_connections():
            self.add_connection(connection)

    def connect(self):
        """Connect to NM listening for updates."""
        # TODO
        pass

    def add(self, device_name=None, connection_uuid=None, device_type=None):
        """Add a new DeviceConfiguration."""
        self._device_configurations.append(DeviceConfiguration(device_name,
                                                               connection_uuid,
                                                               device_type))
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
            ifcfg_uuid = ifcfg.find_ifcfg_uuid_of_device(iface, hwaddr=hwaddr)

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
            existing_cfgs[0].device_name = iface
            log.debug("attached device %s to connection %s", iface, connection_uuid)
        else:
            self.add(device_name=iface, connection_uuid=connection_uuid,
                     device_type=device.get_device_type())
            log.debug("added device configuration for device %s", iface)
        return True

    def _get_iface_from_connection(self, connection):
        """Get the name of device that would be used for the connection.

        In installer it should be just one device.
        We need to account also for the case of configurations bound to mac address
        (HWADDR), eg network --bindto=mac command.
        """
        iface = connection.get_setting_connection().get_interface_name()
        if not iface:
            wired_setting = connection.get_setting_wired()
            if wired_setting:
                mac = wired_setting.get_mac_address()
                if mac:
                    iface = self._hwaddr_to_device_name(mac)
        return iface

    def _hwaddr_to_device_name(self, hwaddr):
        """Find the name of device specified by mac address."""
        for device in self.nm_client.get_devices():
            if device.get_device_type() in (NM.DeviceType.ETHERNET,
                                            NM.DeviceType.WIFI):
                try:
                    address = device.get_permanent_hw_address()
                except AttributeError as e:
                    log.warning("Device %s: %s", device.get_iface(), e)
                    address = device.get_hw_address()
            else:
                address = device.get_hw_address()
            if address.upper() == hwaddr.upper():
                return device.get_iface()
        return None

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
                    parent = self.nm_client.get_connection_by_uuid(parent).get_interface_name()
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

        iface = self._get_iface_from_connection(connection)

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
                    cfg.connection_uuid = uuid
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

    def __str__(self):
        return str(self._device_configurations)

    def __repr__(self):
        return "DeviceConfigurations({})".format(self.nm_client)


def is_libvirt_device(iface):
    return iface.startswith("virbr")

def is_ibft_configured_device(iface):
    return IBFT_CONFIGURED_DEVICE_NAME.match(iface)

def default_ks_vlan_interface_name(parent, vlanid):
    return "%s.%s" % (parent, vlanid)
