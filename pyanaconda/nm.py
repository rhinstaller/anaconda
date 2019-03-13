# Network configuration proxy to NetworkManager
#
# Copyright (C) 2013,2017  Red Hat, Inc.
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

import gi
gi.require_version("Gio", "2.0")
gi.require_version("NM", "1.0")

from gi.repository import Gio
from gi.repository import NM
from pyanaconda.core.glib import GError, VariantType
import struct
import socket

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

from pyanaconda.core.configuration.anaconda import conf


DEFAULT_PROXY_FLAGS = \
    Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS | Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES

class UnknownDeviceError(ValueError):
    """Device of specified name was not found by NM"""
    def __str__(self):
        return self.__repr__()

class PropertyNotFoundError(ValueError):
    """Property of NM object was not found"""
    def __str__(self):
        return self.__repr__()

class UnknownMethodGetError(Exception):
    """Object does not have Get, most probably being invalid"""
    def __str__(self):
        return self.__repr__()

def _get_proxy(bus_type=Gio.BusType.SYSTEM,
               proxy_flags=DEFAULT_PROXY_FLAGS,
               info=None,
               name="org.freedesktop.NetworkManager",
               object_path="/org/freedesktop/NetworkManager",
               interface_name="org.freedesktop.NetworkManager",
               cancellable=None):
    try:
        proxy = Gio.DBusProxy.new_for_bus_sync(bus_type,
                                               proxy_flags,
                                               info,
                                               name,
                                               object_path,
                                               interface_name,
                                               cancellable)
    except GError as e:
        if conf.system.provides_system_bus:
            raise

        log.error("_get_proxy failed: %s", e)
        proxy = None

    return proxy

def _get_property(object_path, prop, interface_name_suffix=""):
    interface_name = "org.freedesktop.NetworkManager" + interface_name_suffix
    proxy = _get_proxy(object_path=object_path, interface_name="org.freedesktop.DBus.Properties")
    if not proxy:
        return None

    try:
        prop = proxy.Get('(ss)', interface_name, prop)
    except GError as e:
        if ("org.freedesktop.DBus.Error.AccessDenied" in e.message or
            "org.freedesktop.DBus.Error.InvalidArgs" in e.message):
            return None
        elif "org.freedesktop.DBus.Error.UnknownMethod" in e.message:
            raise UnknownMethodGetError
        else:
            raise

    return prop

def _get_object_iface_names(object_path):
    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    res_xml = connection.call_sync("org.freedesktop.NetworkManager",
                                   object_path,
                                   "org.freedesktop.DBus.Introspectable",
                                   "Introspect",
                                   None,
                                   VariantType.new("(s)"),
                                   Gio.DBusCallFlags.NONE,
                                   -1,
                                   None)
    node_info = Gio.DBusNodeInfo.new_for_xml(res_xml[0])
    return [iface.name for iface in node_info.interfaces]

def _device_type_specific_interface(device):
    ifaces = _get_object_iface_names(device)
    for iface in ifaces:
        if iface.startswith("org.freedesktop.NetworkManager.Device.") \
           and iface != "org.freedesktop.NetworkManager.Device.Statistics":
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
    try:
        device = proxy.GetDeviceByIpIface('(s)', name)
    except GError as e:
        if "org.freedesktop.NetworkManager.UnknownDevice" in e.message:
            raise UnknownDeviceError(name, e)
        raise

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
