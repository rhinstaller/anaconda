#
# isys.py - installer utility functions and glue for C module
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Matt Wilson <msw@redhat.com>
#            Erik Troan <ewt@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#

try:
    from pyanaconda import _isys
except ImportError:
    # We're running in some sort of testing mode, in which case we can fix
    # up PYTHONPATH and just do this basic import.
    import _isys

import string
import os
import os.path
import socket
import stat
import posix
import sys
from pyanaconda import iutil
import blivet.arch
import re
import struct
import dbus

import logging
log = logging.getLogger("anaconda")

NM_SERVICE = "org.freedesktop.NetworkManager"
NM_MANAGER_PATH = "/org/freedesktop/NetworkManager"
NM_SETTINGS_PATH = "/org/freedesktop/NetworkManager/Settings"
NM_MANAGER_IFACE = "org.freedesktop.NetworkManager"
NM_ACTIVE_CONNECTION_IFACE = "org.freedesktop.NetworkManager.Connection.Active"
NM_CONNECTION_IFACE = "org.freedesktop.NetworkManager.Settings.Connection"
NM_DEVICE_IFACE = "org.freedesktop.NetworkManager.Device"
NM_DEVICE_WIRED_IFACE = "org.freedesktop.NetworkManager.Device.Wired"
NM_IP4CONFIG_IFACE = "org.freedesktop.NetworkManager.IP4Config"
NM_IP6CONFIG_IFACE = "org.freedesktop.NetworkManager.IP6Config"
NM_ACCESS_POINT_IFACE = "org.freedesktop.NetworkManager.AccessPoint"

NM_STATE_UNKNOWN = 0
NM_STATE_ASLEEP = 10
NM_STATE_DISCONNECTED = 20
NM_STATE_DISCONNECTING = 30
NM_STATE_CONNECTING = 40
NM_STATE_CONNECTED_LOCAL = 50
NM_STATE_CONNECTED_SITE = 60
NM_STATE_CONNECTED_GLOBAL = 70
NM_DEVICE_STATE_ACTIVATED = 100
NM_DEVICE_TYPE_WIFI = 2
NM_DEVICE_TYPE_ETHERNET = 1

DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"

if blivet.arch.getArch() in ("sparc", "ppc64"):
    MIN_RAM = 768 * 1024
    GUI_INSTALL_EXTRA_RAM = 512 * 1024
else:
    MIN_RAM = 512 * 1024
    GUI_INSTALL_EXTRA_RAM = 0

MIN_GUI_RAM = MIN_RAM + GUI_INSTALL_EXTRA_RAM
EARLY_SWAP_RAM = 896 * 1024

## Get the amount of free space available under a directory path.
# @param path The directory path to check.
# @return The amount of free space available, in 
def pathSpaceAvailable(path):
    return _isys.devSpaceFree(path)

def resetResolv():
    return _isys.resetresolv()

def modulesWithPaths():
    mods = []
    for modline in open("/proc/modules", "r"):
        modName = modline.split(" ", 1)[0]
        modInfo = iutil.execWithCapture("modinfo",
                ["-F", "filename", modName]).splitlines()
        modPaths = [ line.strip() for line in modInfo if line!="" ]
        mods.extend(modPaths)
    return mods

def isPseudoTTY (fd):
    return _isys.isPseudoTTY (fd)

## Flush filesystem buffers.
def sync ():
    return _isys.sync ()

## Determine if a file is an ISO image or not.
# @param file The full path to a file to check.
# @return True if ISO image, False otherwise.
def isIsoImage(file):
    return _isys.isisoimage(file)

# Return number of network devices
def getNetworkDeviceCount():
    bus = dbus.SystemBus()
    nm = bus.get_object(NM_SERVICE, NM_MANAGER_PATH)
    devlist = nm.get_dbus_method("GetDevices")()
    return len(devlist)

# Get a D-Bus interface for the specified device's (e.g., eth0) properties.
# If dev=None, return a hash of the form 'hash[dev] = props_iface' that
# contains all device properties for all interfaces that NetworkManager knows
# about.
def getDeviceProperties(dev=None):
    bus = dbus.SystemBus()
    nm = bus.get_object(NM_SERVICE, NM_MANAGER_PATH)
    devlist = nm.get_dbus_method("GetDevices")()
    all = {}

    for path in devlist:
        device = bus.get_object(NM_SERVICE, path)
        device_props_iface = dbus.Interface(device, DBUS_PROPS_IFACE)

        device_interface = str(device_props_iface.Get(NM_DEVICE_IFACE, "Interface"))

        if dev is None:
            all[device_interface] = device_props_iface
        elif device_interface == dev:
            return device_props_iface

    if dev is None:
        return all
    else:
        return None

def getMacAddress(dev):
    """Return MAC address of device. "" if not found"""
    if dev == '' or dev is None:
        return ""

    device_props_iface = getDeviceProperties(dev=dev)
    if device_props_iface is None:
        return ""

    device_macaddr = ""
    try:
        device_macaddr = device_props_iface.Get(NM_DEVICE_WIRED_IFACE, "HwAddress").upper()
    except dbus.exceptions.DBusException as e:
        log.debug("getMacAddress %s: %s" % (dev, e))
    return device_macaddr

# Determine if a network device is a wireless device.
def isWirelessDevice(dev_name):
    bus = dbus.SystemBus()
    nm = bus.get_object(NM_SERVICE, NM_MANAGER_PATH)
    devlist = nm.get_dbus_method("GetDevices")()

    for path in devlist:
        device = bus.get_object(NM_SERVICE, path)
        device_props_iface = dbus.Interface(device, DBUS_PROPS_IFACE)

        iface = device_props_iface.Get(NM_DEVICE_IFACE, "Interface")
        if iface == dev_name:
            device_type = device_props_iface.Get(NM_DEVICE_IFACE, "DeviceType")
            return device_type == NM_DEVICE_TYPE_WIFI

    return False


# Get IP addresses for a network device.
# Returns list of ipv4 or ipv6 addresses, depending
# on version parameter. ipv4 is default.
def getIPAddresses(dev, version=4):
    if dev == '' or dev is None:
       return None

    device_props_iface = getDeviceProperties(dev=dev)
    if device_props_iface is None:
        return None

    bus = dbus.SystemBus()

    addresses = []

    if version == 4:
        ip4_config_path = device_props_iface.Get(NM_DEVICE_IFACE, 'Ip4Config')
        if ip4_config_path != '/':
            ip4_config_obj = bus.get_object(NM_SERVICE, ip4_config_path)
            ip4_config_props = dbus.Interface(ip4_config_obj, DBUS_PROPS_IFACE)

            # addresses (3-element list:  ipaddr, netmask, gateway)
            addrs = ip4_config_props.Get(NM_IP4CONFIG_IFACE, "Addresses")
            for addr in addrs:
                try:
                    tmp = struct.pack('I', addr[0])
                    ipaddr = socket.inet_ntop(socket.AF_INET, tmp)
                    addresses.append(ipaddr)
                except ValueError as e:
                    log.debug("Exception caught trying to convert IP address %s: %s" %
                    (addr, e))
    elif version == 6:
        ip6_config_path = device_props_iface.Get(NM_DEVICE_IFACE, 'Ip6Config')
        if ip6_config_path != '/':
            ip6_config_obj = bus.get_object(NM_SERVICE, ip6_config_path)
            ip6_config_props = dbus.Interface(ip6_config_obj, DBUS_PROPS_IFACE)

            addrs = ip6_config_props.Get(NM_IP6CONFIG_IFACE, "Addresses")
            for addr in addrs:
                try:
                    addrstr = "".join(str(byte) for byte in addr[0])
                    ipaddr = socket.inet_ntop(socket.AF_INET6, addrstr)
                    # XXX - should we prefer Global or Site-Local types?
                    #       does NM prefer them?
                    addresses.append(ipaddr)
                except ValueError as e:
                    log.debug("Exception caught trying to convert IP address %s: %s" %
                    (addr, e))
    else:
        raise ValueError, "invalid IP version %d" % version

    return addresses

def prefix2netmask(prefix):
    return _isys.prefix2netmask(prefix)

def netmask2prefix (netmask):
    prefix = 0

    while prefix < 33:
        if (prefix2netmask(prefix) == netmask):
            return prefix

        prefix += 1

    return prefix

isPAE = None
def isPaeAvailable():
    global isPAE
    if isPAE is not None:
        return isPAE

    isPAE = False
    if not blivet.arch.isX86():
        return isPAE

    f = open("/proc/cpuinfo", "r")
    lines = f.readlines()
    f.close()

    for line in lines:
        if line.startswith("flags") and line.find("pae") != -1:
            isPAE = True
            break

    return isPAE

def getLinkStatus(dev):
    return _isys.getLinkStatus(dev)

def getAnacondaVersion():
    return _isys.getAnacondaVersion()

auditDaemon = _isys.auditdaemon

handleSegv = _isys.handleSegv

printObject = _isys.printObject
bind_textdomain_codeset = _isys.bind_textdomain_codeset
isVioConsole = _isys.isVioConsole
initLog = _isys.initLog
total_memory = _isys.total_memory
