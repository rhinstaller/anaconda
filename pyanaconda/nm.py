# Network configuration proxy to NetworkManager
#
# Copyright (C) 2013  Red Hat, Inc.
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

from gi.repository import Gio, GLib
from gi.repository import NetworkManager
import IPy
import struct
import socket
import re

from pyanaconda.constants import DEFAULT_DBUS_TIMEOUT

supported_device_types = [
    NetworkManager.DeviceType.ETHERNET,
    NetworkManager.DeviceType.WIFI,
    NetworkManager.DeviceType.INFINIBAND,
    NetworkManager.DeviceType.BOND,
    NetworkManager.DeviceType.VLAN,
    NetworkManager.DeviceType.BRIDGE,
]

class UnknownDeviceError(ValueError):
    """Device of specified name was not found by NM"""
    def __str__(self):
        return self.__repr__()

class UnmanagedDeviceError(Exception):
    """Device of specified name is not managed by NM or unavailable"""
    def __str__(self):
        return self.__repr__()

class PropertyNotFoundError(ValueError):
    """Property of NM object was not found"""
    def __str__(self):
        return self.__repr__()

class SettingNotFoundError(ValueError):
    """Setting of NMRemoteConnection was not found"""
    def __str__(self):
        return self.__repr__()

class DeviceSettingsNotFoundError(ValueError):
    """Settings NMRemoteConnection object was not found"""
    def __str__(self):
        return self.__repr__()

class UnknownMethodGetError(Exception):
    """Object does not have Get, most probably being invalid"""
    def __str__(self):
        return self.__repr__()

def _get_proxy(bus_type=Gio.BusType.SYSTEM,
               flags=Gio.DBusProxyFlags.NONE,
               info=None,
               name="org.freedesktop.NetworkManager",
               object_path="/org/freedesktop/NetworkManager",
               interface_name="org.freedesktop.NetworkManager",
               cancellable=None):
    proxy = Gio.DBusProxy.new_for_bus_sync(bus_type,
                                           flags,
                                           info,
                                           name,
                                           object_path,
                                           interface_name,
                                           cancellable)
    return proxy

def _get_property(object_path, prop, interface_name_suffix=""):
    interface_name = "org.freedesktop.NetworkManager" + interface_name_suffix
    proxy = _get_proxy(object_path=object_path, interface_name="org.freedesktop.DBus.Properties")
    args = GLib.Variant('(ss)', (interface_name, prop))
    try:
        prop = proxy.call_sync("Get",
                                args,
                                Gio.DBusCallFlags.NONE,
                                DEFAULT_DBUS_TIMEOUT,
                                None)
    except GLib.GError as e:
        if "org.freedesktop.DBus.Error.AccessDenied" in e.message:
            return None
        elif "org.freedesktop.DBus.Error.UnknownMethod" in e.message:
            raise UnknownMethodGetError
        else:
            raise

    return prop.unpack()[0]

def nm_state():
    """Return state of NetworkManager

    :return: state of NetworkManager
    :rtype: integer
    """
    return _get_property("/org/freedesktop/NetworkManager", "State")

# FIXME - use just GLOBAL? There is some connectivity checking
# for GLOBAL in NM (nm_connectivity_get_connected), not sure if
# and how it is implemented.
# Also see Gio g_network_monitor_can_reach.
def nm_is_connected():
    """Is NetworkManager connected?

    :return: True if NM is connected, False otherwise.
    :rtype: bool
    """
    return nm_state() in (NetworkManager.State.CONNECTED_GLOBAL,
                          NetworkManager.State.CONNECTED_SITE,
                          NetworkManager.State.CONNECTED_LOCAL)

def nm_is_connecting():
    """Is NetworkManager connecting?

    :return: True if NM is in CONNECTING state, False otherwise.
    :rtype: bool
    """
    return nm_state() == NetworkManager.State.CONNECTING

def nm_devices():
    """Return names of network devices supported in installer.

    :return: names of network devices supported in installer
    :rtype: list of strings
    """

    interfaces = []

    proxy = _get_proxy()
    args = None
    devices = proxy.call_sync("GetDevices",
                              args,
                              Gio.DBusCallFlags.NONE,
                              DEFAULT_DBUS_TIMEOUT,
                              None)

    devices = devices.unpack()[0]
    for device in devices:
        device_type = _get_property(device, "DeviceType", ".Device")
        if device_type not in supported_device_types:
            continue
        iface = _get_property(device, "Interface", ".Device")
        interfaces.append(iface)

    return interfaces

def nm_activated_devices():
    """Return names of activated network devices.

    :return: names of activated network devices
    :rtype: list of strings
    """

    interfaces = []

    active_connections = _get_property("/org/freedesktop/NetworkManager", "ActiveConnections")
    for ac in active_connections:
        state = _get_property(ac, "State", ".Connection.Active")
        if state != NetworkManager.ActiveConnectionState.ACTIVATED:
            continue
        devices = _get_property(ac, "Devices", ".Connection.Active")
        for device in devices:
            iface = _get_property(device, "Interface", ".Device")
            interfaces.append(iface)

    return interfaces

def _get_object_iface_names(object_path):
    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    res_xml = connection.call_sync("org.freedesktop.NetworkManager",
                                   object_path,
                                   "org.freedesktop.DBus.Introspectable",
                                   "Introspect",
                                   None,
                                   GLib.VariantType.new("(s)"),
                                   Gio.DBusCallFlags.NONE,
                                   -1,
                                   None)
    node_info = Gio.DBusNodeInfo.new_for_xml(res_xml[0])
    return [iface.name for iface in node_info.interfaces]

def _device_type_specific_interface(device):
    ifaces = _get_object_iface_names(device)
    for iface in ifaces:
        if iface.startswith("org.freedesktop.NetworkManager.Device."):
            return iface
    return None

def nm_device_property(name, prop):
    """Return value of device NM property

       :param name: name of device
       :type name: str
       :param prop: property
       :type name: str
       :return: value of device's property
       :rtype: unpacked GDBus value
       :raise UnknownDeviceError: if device is not found
       :raise PropertyNotFoundError: if property is not found
    """

    retval = None

    proxy = _get_proxy()
    args = GLib.Variant('(s)', (name,))
    try:
        device = proxy.call_sync("GetDeviceByIpIface",
                                  args,
                                  Gio.DBusCallFlags.NONE,
                                  DEFAULT_DBUS_TIMEOUT,
                                  None)
    except GLib.GError as e:
        if "org.freedesktop.NetworkManager.UnknownDevice" in e.message:
            raise UnknownDeviceError(name, e)
        raise

    device = device.unpack()[0]

    retval = _get_property(device, prop, ".Device")
    if not retval:
        # Look in device type based interface
        interface = _device_type_specific_interface(device)
        if interface:
            retval = _get_property(device, prop, interface[30:])
            if not retval:
                raise PropertyNotFoundError(prop)
        else:
            raise PropertyNotFoundError(prop)

    return retval

def nm_device_type_is_wifi(name):
    """Is the type of device wifi?

       :param name: name of device
       :type name: str
       :return: True if type of device is WIFI, False otherwise
       :rtype: bool
       :raise UnknownDeviceError: if device is not found
       :raise PropertyNotFoundError: if property is not found
    """
    return nm_device_type(name) == NetworkManager.DeviceType.WIFI

def nm_device_type_is_ethernet(name):
    """Is the type of device ethernet?

       :param name: name of device
       :type name: str
       :return: True if type of device is ETHERNET, False otherwise
       :rtype: bool
       :raise UnknownDeviceError: if device is not found
       :raise PropertyNotFoundError: if property is not found
    """
    return nm_device_type(name) == NetworkManager.DeviceType.ETHERNET

def nm_device_type_is_bond(name):
    """Is the type of device bond?

       :param name: name of device
       :type name: str
       :return: True if type of device is BOND, False otherwise
       :rtype: bool
       :raise UnknownDeviceError: if device is not found
       :raise PropertyNotFoundError: if property is not found
    """
    return nm_device_type(name) == NetworkManager.DeviceType.BOND

def nm_device_type_is_vlan(name):
    """Is the type of device vlan?

       :param name: name of device
       :type name: str
       :return: True if type of device is VLAN, False otherwise
       :rtype: bool
       :raise UnknownDeviceError: if device is not found
       :raise PropertyNotFoundError: if property is not found
    """
    return nm_device_type(name) == NetworkManager.DeviceType.VLAN

def nm_device_is_slave(name):
    """Is the device a slave?

       Exceptions:
       UnknownDeviceError if device is not found
    """
    active_con = nm_device_property(name, 'ActiveConnection')
    if active_con == "/":
        return False

    master = _get_property(active_con, "Master", ".Connection.Active")
    return master and master != "/"

def nm_device_hwaddress(name):
    """Return active hardware address of device ('HwAddress' property)

       :param name: name of device
       :type name: str
       :return: active hardware address of device ('HwAddress' property)
       :rtype: str
       :raise UnknownDeviceError: if device is not found
       :raise PropertyNotFoundError: if 'HwAddress' property is not found
    """
    return nm_device_property(name, "HwAddress")

def nm_device_active_con_uuid(name):
    """Return uuid of device's active connection

       Exceptions:
       UnknownDeviceError if device is not found
    """
    active_con = nm_device_property(name, 'ActiveConnection')
    if active_con == "/":
        return None

    uuid = _get_property(active_con, "Uuid", ".Connection.Active")
    return uuid

def nm_device_type(name):
    """Return device's type ('DeviceType' property).

       :param name: name of device
       :type name: str
       :return: device type
       :rtype: integer
       :raise UnknownDeviceError: if device is not found
       :raise PropertyNotFoundError: if 'DeviceType' property is not found
    """
    return nm_device_property(name, "DeviceType")

def nm_device_carrier(name):
    """Return whether physical carrier of device is found.
       ('Carrier' property)

       :param name: name of device
       :type name: str
       :return: True if physical carrier is found, False otherwise
       :rtype: bool
       :raise UnknownDeviceError: if device is not found
       :raise PropertyNotFoundError: if 'Carrier' property is not found
    """
    return nm_device_property(name, "Carrier")

def nm_device_ip_addresses(name, version=4):
    """Return IP addresses of device in ACTIVATED state.

       :param name: name of device
       :type name: str
       :param version: version of IP protocol (value 4 or 6)
       :type version: int
       :return: IP addresses of device, empty list if device is not
                in ACTIVATED state
       :rtype: list of strings
       :raise UnknownDeviceError: if device is not found
       :raise PropertyNotFoundError: if IP configuration is not found
    """
    retval = []
    config = nm_device_ip_config(name, version)
    if config:
        retval = [addrs[0] for addrs in config[0]]

    return retval

def nm_device_active_ssid(name):
    """Return ssid of device's active access point.

       :param name: name of device
       :type name: str
       :return ssid of active access point, None if device has no active AP
       :rtype: str
       :raise UnknownDeviceError: if device is not found
    """

    try:
        aap = nm_device_property(name, "ActiveAccessPoint")
    except PropertyNotFoundError:
        return None

    if aap == "/":
        return None

    ssid_ay = _get_property(aap, "Ssid", ".AccessPoint")
    ssid = "".join(chr(b) for b in ssid_ay)

    return ssid

def nm_device_ip_config(name, version=4):
    """Return IP configurations of device in ACTIVATED state.

       :param name: name of device
       :type name: str
       :param version: version of IP protocol (value 4 or 6)
       :type version: int
       :return: IP configuration of device, empty list if device is not
                in ACTIVATED state
       :rtype: [[[address1, prefix1, gateway1], [address2, prefix2, gateway2], ...],
                [nameserver1, nameserver2]]
               addressX, gatewayX: string
               prefixX: int
       :raise UnknownDeviceError: if device is not found
       :raise PropertyNotFoundError: if ip configuration is not found
    """
    state = nm_device_property(name, "State")
    if state != NetworkManager.DeviceState.ACTIVATED:
        return []

    if version == 4:
        dbus_iface = ".IP4Config"
        prop= "Ip4Config"
    elif version == 6:
        dbus_iface = ".IP6Config"
        prop= "Ip6Config"
    else:
        return []

    config = nm_device_property(name, prop)
    if config == "/":
        return []

    try:
        addresses = _get_property(config, "Addresses", dbus_iface)
    # object is valid only if device is in ACTIVATED state (racy)
    except UnknownMethodGetError:
        return []

    addr_list = []
    for addr, prefix, gateway in addresses:
        # TODO - look for a library function (could have used IPy but byte order!)
        if version == 4:
            addr_str = nm_dbus_int_to_ipv4(addr)
            gateway_str = nm_dbus_int_to_ipv4(gateway)
        elif version == 6:
            addr_str = nm_dbus_ay_to_ipv6(addr)
            gateway_str = nm_dbus_ay_to_ipv6(gateway)
        addr_list.append([addr_str, prefix, gateway_str])

    try:
        nameservers = _get_property(config, "Nameservers", dbus_iface)
    # object is valid only if device is in ACTIVATED state (racy)
    except UnknownMethodGetError:
        return []

    ns_list = []
    for ns in nameservers:
        # TODO - look for a library function
        if version == 4:
            ns_str = nm_dbus_int_to_ipv4(ns)
        elif version == 6:
            ns_str = nm_dbus_ay_to_ipv6(ns)
        ns_list.append(ns_str)

    return [addr_list, ns_list]

def nm_device_slaves(name):
    """Return slaves of device.

       :param name: name of device
       :type name: str
       :return: names of slaves of device or None if device has no 'Slaves' property
       :rtype: list of strings or None
       :raise UnknownDeviceError: if device is not found
    """

    try:
        slaves = nm_device_property(name, "Slaves")
    except PropertyNotFoundError:
        return None

    slave_ifaces = []
    for slave in slaves:
        iface = _get_property(slave, "Interface", ".Device")
        slave_ifaces.append(iface)

    return slave_ifaces


def nm_ntp_servers_from_dhcp():
    """Return NTP servers obtained by DHCP.

       return: NTP servers obtained by DHCP
       rtype: list of str
    """
    ntp_servers = []
    # get paths for all actively connected interfaces
    active_devices = nm_activated_devices()
    for device in active_devices:
        # harvest NTP server addresses from DHCPv4
        dhcp4_path = nm_device_property(device, "Dhcp4Config")
        try:
            options = _get_property(dhcp4_path, "Options", ".DHCP4Config")
        # object is valid only if device is in ACTIVATED state (racy)
        except UnknownMethodGetError:
            options = None
        if options and 'ntp_servers' in options:
            # NTP server addresses returned by DHCP are whitespace delimited
            ntp_servers_string = options["ntp_servers"]
            for ip in ntp_servers_string.split(" "):
                ntp_servers.append(ip)

        # NetworkManager does not request NTP/SNTP options for DHCP6
    return ntp_servers

def _device_settings(name):
    """Return object path of device setting.

       :param name: name of device
       :type name: str
       :return: path of settings, None if not found
       :rtype: str or None
       :raise UnknownDeviceError: if device is not found
    """
    devtype = nm_device_type(name)
    if devtype == NetworkManager.DeviceType.BOND:
        settings = _find_settings(name, 'bond', 'interface-name')
    elif devtype == NetworkManager.DeviceType.VLAN:
        settings = _find_settings(name, 'vlan', 'interface-name')
    else:
        try:
            hwaddr_str = nm_device_hwaddress(name)
        except PropertyNotFoundError:
            settings = None
        else:
            settings = _settings_for_hwaddr(hwaddr_str)

    return settings

def _settings_for_ap(ssid):
    """Return object path of wireless access point settings.

       :param ssid: ssid of access point
       :type ssid: str
       :return: path of settings, None if not found
       :rtype: str or None
`   """
    return _find_settings(ssid, '802-11-wireless', 'ssid',
            format_value=lambda ba: "".join(chr(b) for b in ba))

def _settings_for_hwaddr(hwaddr):
    """Return object path of settings of device specified by hw address.

       :param hwaddr: hardware address (uppercase)
       :type hwaddr: str
       :return: path of settings, None if not found
       :rtype: str or None
    """
    return _find_settings(hwaddr, '802-3-ethernet', 'mac-address',
            format_value=lambda ba: ":".join("%02X" % b for b in ba))

def _find_settings(value, key1, key2, format_value=lambda x:x):
    """Return object path of settings having given value of key1, key2 setting

       :param value: required value of setting
       :type value: corresponds to dbus type of setting
       :param key1: first-level key of setting (eg "connection")
       :type key1: str
       :param key2: second-level key of setting (eg "uuid")
       :type key2: str
       :param format_value: function to be called on setting value before
                            comparing
       :type format_value: function taking one argument (setting value)
       :return: path of settings, None if not found
       :rtype: str or None
    """
    retval = None

    proxy = _get_proxy(object_path="/org/freedesktop/NetworkManager/Settings", interface_name="org.freedesktop.NetworkManager.Settings")

    args = None
    connections = proxy.call_sync("ListConnections",
                                  args,
                                  Gio.DBusCallFlags.NONE,
                                  DEFAULT_DBUS_TIMEOUT,
                                  None)

    for con in connections.unpack()[0]:
        proxy = _get_proxy(object_path=con, interface_name="org.freedesktop.NetworkManager.Settings.Connection")
        args = None
        settings = proxy.call_sync("GetSettings",
                                   args,
                                   Gio.DBusCallFlags.NONE,
                                   DEFAULT_DBUS_TIMEOUT,
                                   None)
        settings = settings.unpack()[0]
        try:
            v = settings[key1][key2]
        except KeyError:
            continue
        if format_value(v) == value:
            retval = con
            break

    return retval

def nm_device_setting_value(name, key1, key2):
    """Return value of device's setting specified by key1 and key2.

       :param name: name of device
       :type name: str
       :param key1: first-level key of setting (eg "connection")
       :type key1: str
       :param key2: second-level key of setting (eg "uuid")
       :type key2: str
       :return: value of setting or None if the setting was not found
                which means it does not exist or default value is used
                by NM
       :rtype: unpacked GDBus variant or None
       :raise UnknownDeviceError: if device is not found
       :raise DeviceSettingsNotFoundError: if settings were not found
                                           (eg for "wlan0")
    """
    settings_path = _device_settings(name)
    if not settings_path:
        raise DeviceSettingsNotFoundError(name)
    proxy = _get_proxy(object_path=settings_path, interface_name="org.freedesktop.NetworkManager.Settings.Connection")
    args = None
    settings = proxy.call_sync("GetSettings",
                               args,
                               Gio.DBusCallFlags.NONE,
                               DEFAULT_DBUS_TIMEOUT,
                               None)
    settings = settings.unpack()[0]
    try:
        value = settings[key1][key2]
    except KeyError:
        #raise SettingNotFoundError(key1, key2)
        value = None
    return value

def nm_activate_device_connection(dev_name, con_uuid):
    """Activate device with specified connection.

       :param dev_name: name of device
       :type dev_name: str
       :param con_uuid: uuid of connection to be activated on device
       :type con_uuid: str
       :raise UnknownDeviceError: if device is not found
       :raise UnmanagedDeviceError: if device is not managed by NM
                                    or unavailable
    """

    proxy = _get_proxy()
    args = GLib.Variant('(s)', (dev_name,))
    try:
        device = proxy.call_sync("GetDeviceByIpIface",
                                  args,
                                  Gio.DBusCallFlags.NONE,
                                  DEFAULT_DBUS_TIMEOUT,
                                  None)
    except GLib.GError as e:
        if "org.freedesktop.NetworkManager.UnknownDevice" in e.message:
            raise UnknownDeviceError(dev_name, e)
        raise

    device_path = device.unpack()[0]

    con_path = _find_settings(con_uuid, 'connection', 'uuid')

    args = GLib.Variant('(ooo)', (con_path, device_path, "/"))
    nm_proxy = _get_proxy()
    try:
        nm_proxy.call_sync("ActivateConnection",
                            args,
                            Gio.DBusCallFlags.NONE,
                            DEFAULT_DBUS_TIMEOUT,
                            None)
    except GLib.GError as e:
        if "org.freedesktop.NetworkManager.UnmanagedDevice" in e.message:
            raise UnmanagedDeviceError(dev_name, e)
        raise

def nm_update_settings_of_device(name, new_values):
    """Update setting of device.

       The type of value is determined from existing settings of device.
       If setting for key1, key2 does not exist, default_type_str is used or
       if None, the type is inferred from the value supplied (string and bool only).

       :param name: name of device
       :type name: str
       :param new_values: list of settings with new values and its types
                          [[key1, key2, value, default_type_str]]
                          key1: first-level key of setting (eg "connection")
                          key2: second-level key of setting (eg "uuid")
                          value: new value
                          default_type_str: dbus type of new value to be used
                                            if the setting does not already exist;
                                            if None, the type is inferred from
                                            value (string and bool only)
       :type new_values: [[key1, key2, value, default_type_str], ...]
                         key1: str
                         key2: str
                         value:
                         default_type_str: str
       :raise UnknownDeviceError: if device is not found
       :raise DeviceSettingsNotFoundError: if settings were not found
                                           (eg for "wlan0")
    """
    settings_path = _device_settings(name)
    if not settings_path:
        raise DeviceSettingsNotFoundError(name)
    return _update_settings(settings_path, new_values)

def _update_settings(settings_path, new_values):
    """Update setting of object specified by settings_path with value.

       The type of value is determined from existing setting.
       If setting for key1, key2 does not exist, default_type_str is used or
       if None, the type is inferred from the value supplied (string and bool only).

       :param settings_path: path of settings object
       :type settings_path: str
       :param new_values: list of settings with new values and its types
                          [[key1, key2, value, default_type_str]]
                          key1: first-level key of setting (eg "connection")
                          key2: second-level key of setting (eg "uuid")
                          value: new value
                          default_type_str: dbus type of new value to be used
                                            if the setting does not already exist;
                                            if None, the type is inferred from
                                            value (string and bool only)
       :type new_values: [[key1, key2, value, default_type_str], ...]
                         key1: str
                         key2: str
                         value:
                         default_type_str: str
    """
    proxy = _get_proxy(object_path=settings_path, interface_name="org.freedesktop.NetworkManager.Settings.Connection")
    args = None
    settings = proxy.call_sync("GetSettings",
                               args,
                               Gio.DBusCallFlags.NONE,
                               DEFAULT_DBUS_TIMEOUT,
                               None)
    for key1, key2, value, default_type_str in new_values:
        settings = _gvariant_settings(settings, key1, key2, value, default_type_str)

    proxy.call_sync("Update",
                    settings,
                    Gio.DBusCallFlags.NONE,
                    DEFAULT_DBUS_TIMEOUT,
                    None)

def _gvariant_settings(settings, updated_key1, updated_key2, value, default_type_str=None):
    """Update setting of updated_key1, updated_key2 of settings object with value.

       The type of value is determined from existing setting.
       If setting for key1, key2 does not exist, default_type_str is used or
       the type is inferred from the value supplied (string and bool only).
    """

    type_str = default_type_str

    # build copy of GVariant settings as mutable python object
    new_settings = {}
    dict1 = settings.get_child_value(0)

    # loop over first level dict (key1)
    for key1_idx in range(dict1.n_children()):

        key_dict2 = dict1.get_child_value(key1_idx)
        key1 = key_dict2.get_child_value(0).unpack()
        new_settings[key1] = {}
        dict2 = key_dict2.get_child_value(1)

        # loop over second level dict (key2)
        for key2_idx in range(dict2.n_children()):

            key_val = dict2.get_child_value(key2_idx)
            key2 = key_val.get_child_value(0).unpack()
            val = key_val.get_child_value(1).get_child_value(0)

            # get type string of updated value
            if key1 == updated_key1 and key2 == updated_key2:
                type_str = val.get_type_string()

            # copy old value to new python object
            new_settings[key1][key2] = val

    if type_str is None:
        # infer the new value type for string and boolean
        if type(value) is type(True):
            type_str = 'b'
        if type(value) is type(''):
            type_str = 's'

    if type_str is not None:
        if updated_key1 not in new_settings:
            new_settings[updated_key1] = {}
        new_settings[updated_key1][updated_key2] = GLib.Variant(type_str, value)

    return GLib.Variant(settings.get_type_string(), (new_settings,))

def nm_ipv6_to_dbus_ay(address):
    """Convert ipv6 address from string to list of bytes 'ay' for dbus

    :param address: IPv6 address
    :type address: str
    :return: address in format 'ay' for NM dbus setting
    :rtype: list of bytes
    """
    return [int(byte, 16) for byte in re.findall('.{1,2}', IPy.IP(address).strFullsize().replace(':', ''))]

def nm_ipv4_to_dbus_int(address):
    """Convert ipv4 address from string to int for dbus (switched endianess).

    :param address: IPv4 address
    :type address: str
    :return: IPv4 address as an integer 'u' for NM dbus setting
    :rtype: integer
    """
    return struct.unpack("=L", socket.inet_aton(address))[0]

def nm_dbus_ay_to_ipv6(bytelist):
    """Convert ipv6 address from list of bytes (dbus 'ay') to string.

    :param address: IPv6 address as list of bytes returned by dbus ('ay')
    :type address: list of bytes - dbus 'ay'
    :return: IPv6 address
    :rtype: str
    """
    return socket.inet_ntop(socket.AF_INET6, "".join(chr(byte) for byte in bytelist))

def nm_dbus_int_to_ipv4(address):
    """Convert ipv4 address from dus int 'u' (switched endianess) to string.

    :param address: IPv4 address as integer returned by dbus ('u')
    :type address: integer - dbus 'u'
    :return: IPv6 address
    :rtype: str
    """
    return socket.inet_ntop(socket.AF_INET, struct.pack('=L', address))

def test():
    print "NM state: %s:" % nm_state()
    print "NM is connected: %s" % nm_is_connected()

    print "Devices: %s" % nm_devices()
    print "Activated devices: %s" % nm_activated_devices()

    wireless_device = ""

    devs = nm_devices()
    devs.append("nonexisting")
    for devname in devs:

        print devname

        try:
            devtype = nm_device_type(devname)
        except UnknownDeviceError as e:
            print "     %s" % e
            devtype = None
        if devtype == NetworkManager.DeviceType.ETHERNET:
            print "     type %s" % "ETHERNET"
        elif devtype == NetworkManager.DeviceType.WIFI:
            print "     type %s" % "WIFI"
            wireless_device = devname

        try:
            print "     Wifi device: %s" % nm_device_type_is_wifi(devname)
        except UnknownDeviceError as e:
            print "     %s" % e

        try:
            hwaddr = nm_device_hwaddress(devname)
            print "     HwAaddress: %s" % hwaddr
        except ValueError as e:
            print "     %s" % e
            hwaddr = ""

        try:
            print "     Carrier: %s" % nm_device_carrier(devname)
        except ValueError as e:
            print "     %s" % e

        try:
            print "     IP4 config: %s" % nm_device_ip_config(devname)
            print "     IP6 config: %s" % nm_device_ip_config(devname, version=6)
            print "     IP4 addrs: %s" % nm_device_ip_addresses(devname)
            print "     IP6 addrs: %s" % nm_device_ip_addresses(devname, version=6)
            print "     Udi: %s" % nm_device_property(devname, "Udi")
        except UnknownDeviceError as e:
            print "     %s" % e

        if devname in nm_devices():
            try:
                print "     Nonexisting: %s" % nm_device_property(devname, "Nonexisting")
            except PropertyNotFoundError as e:
                print "     %s" % e
        try:
            print "     Nonexisting: %s" % nm_device_property(devname, "Nonexisting")
        except ValueError as e:
            print "     %s" % e

        try:
            print "     Settings: %s" % _device_settings(devname)
        except UnknownDeviceError as e:
            print "     %s" % e
        try:
            print "     Settings for hwaddr %s: %s" % (hwaddr, _settings_for_hwaddr(hwaddr))
        except UnknownDeviceError as e:
            print "     %s" % e
        try:
            print "     Setting value %s %s: %s" % ("ipv6", "method", nm_device_setting_value(devname, "ipv6", "method"))
        except ValueError as e:
            print "     %s" % e
        try:
            print "     Setting value %s %s: %s" % ("ipv7", "method", nm_device_setting_value(devname, "ipv7", "method"))
        except ValueError as e:
            print "     %s" % e

    ssid = "Red Hat Guest"
    print "Settings for AP %s: %s" % (ssid, _settings_for_ap(ssid))
    ssid = "nonexisting"
    print "Settings for AP %s: %s" % (ssid, _settings_for_ap(ssid))

    devname = devs[0]
    key1 = "connection"
    key2 = "autoconnect"
    original_value = nm_device_setting_value(devname, key1, key2)
    print "Value of setting %s %s: %s" % (key1, key2, original_value)
    # None means default in this case, which is true
    if original_value in (None, True):
        new_value = False
    else:
        new_value = True

    print "Updating to %s" % new_value
    nm_update_settings_of_device(devname, [[key1, key2, new_value, None]])
    print "Value of setting %s %s: %s" % (key1, key2, nm_device_setting_value(devname, key1, key2))
    nm_update_settings_of_device(devname, [[key1, key2, original_value, None]])
    print "Value of setting %s %s: %s" % (key1, key2, nm_device_setting_value(devname, key1, key2))
    nm_update_settings_of_device(devname, [[key1, key2, original_value, "b"]])
    print "Value of setting %s %s: %s" % (key1, key2, nm_device_setting_value(devname, key1, key2))

    nm_update_settings_of_device(devname, [[key1, "nonexisting", new_value, None]])
    nm_update_settings_of_device(devname, [["nonexisting", "nonexisting", new_value, None]])
    try:
        nm_update_settings_of_device("nonexixting", [[key1, key2, new_value, None]])
    except UnknownDeviceError as e:
        print "%s" % e

    if wireless_device:
        try:
            nm_update_settings_of_device(wireless_device, [[key1, key2, new_value, None]])
        except DeviceSettingsNotFoundError as e:
            print "%s" % e

    #nm_update_settings_of_device(devname, [["connection", "id", "test", None]])
    #nm_update_settings_of_device(devname, [["connection", "timestamp", 11111111, None]])
    #nm_update_settings_of_device(devname, [["802-3-ethernet", "mac-address", [55,55,55,55,55,55], None]])
    #nm_update_settings_of_device(devname, [["ipv6", "method", "auto", None]])
    #nm_update_settings_of_device(devname, [["ipv6", "addressess", [[[32,1,0,0,0,0,0,0,0,0,0,0,0,0,0,a], 64, [0]*16]], None]])
    #nm_update_settings_of_device(devname, [["connection", "autoconnect", True, None]])
    #nm_update_settings_of_device(devname, [["connection", "autoconnect", False, "b"]])

if __name__ == "__main__":
    test()
