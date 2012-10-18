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
import resource
import re
import struct
import dbus
import selinux

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

DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"

mountCount = {}

MIN_RAM = _isys.MIN_RAM
MIN_GUI_RAM = _isys.MIN_GUI_RAM
GUI_INSTALL_EXTRA_RAM = _isys.GUI_INSTALL_EXTRA_RAM
EARLY_SWAP_RAM = _isys.EARLY_SWAP_RAM

## Get the amount of free space available under a directory path.
# @param path The directory path to check.
# @return The amount of free space available, in 
def pathSpaceAvailable(path):
    return _isys.devSpaceFree(path)

## Mount a filesystem, similar to the mount system call.
# @param device The device to mount.  If bindMount is True, this should be an
#               already mounted directory.  Otherwise, it should be a device
#               name.
# @param location The path to mount device on.
# @param fstype The filesystem type on device.  This can be disk filesystems
#               such as vfat or ext3, or pseudo filesystems such as proc or
#               selinuxfs.
# @param readOnly Should this filesystem be mounted readonly?
# @param bindMount Is this a bind mount?  (see the mount(8) man page)
# @param remount Are we mounting an already mounted filesystem?
# @return The return value from the mount system call.
def mount(device, location, fstype = "ext2", readOnly = False,
          bindMount = False, remount = False, options = None):
    flags = None
    location = os.path.normpath(location)
    if not options:
        opts = ["defaults"]
    else:
        opts = options.split(",")

    # We don't need to create device nodes for devices that start with '/'
    # (like '/usbdevfs') and also some special fake devices like 'proc'.
    # First try to make a device node and if that fails, assume we can
    # mount without making a device node.  If that still fails, the caller
    # will have to deal with the exception.
    # We note whether or not we created a node so we can clean up later.

    if mountCount.has_key(location) and mountCount[location] > 0 and not remount:
	mountCount[location] = mountCount[location] + 1
	return

    if readOnly or bindMount or remount:
        if readOnly:
            opts.append("ro")
        if bindMount:
            opts.append("bind")
        if remount:
            opts.append("remount")

    flags = ",".join(opts)

    log.debug("isys.py:mount()- going to mount %s on %s as %s with options %s" %(device, location, fstype, flags))
    rc = _isys.mount(fstype, device, location, flags)

    if not rc:
	mountCount[location] = 1

    return rc

## Unmount a filesystem, similar to the umount system call.
# @param what The directory to be unmounted.  This does not need to be the
#             absolute path.
# @param removeDir Should the mount point be removed after being unmounted?
# @return The return value from the umount system call.
def umount(what, removeDir = True):
    what = os.path.normpath(what)

    if not os.path.isdir(what):
	raise ValueError, "isys.umount() can only umount by mount point"

    if mountCount.has_key(what) and mountCount[what] > 1:
	mountCount[what] = mountCount[what] - 1
	return

    log.debug("isys.py:umount()- going to unmount %s, removeDir = %s" % (what, removeDir))
    rc = _isys.umount(what)

    if removeDir and os.path.isdir(what):
        try:
            os.rmdir(what)
        except:
            pass

    if not rc and mountCount.has_key(what):
	del mountCount[what]

    return rc

## Disable swap.
# @param path The full path of the swap device to disable.
def swapoff (path):
    return _isys.swapoff (path)

## Enable swap.
# @param path The full path of the swap device to enable.
def swapon (path):
    return _isys.swapon (path)

def resetResolv():
    return _isys.resetresolv()

def readFSUuid(device):
    if not os.path.exists(device):
        device = "/dev/%s" % device

    label = _isys.getblkid(device, "UUID")
    return label

def readFSLabel(device):
    if not os.path.exists(device):
        device = "/dev/%s" % device

    label = _isys.getblkid(device, "LABEL")
    return label

def readFSType(device):
    if not os.path.exists(device):
        device = "/dev/%s" % device

    fstype = _isys.getblkid(device, "TYPE")
    if fstype is None:
        # FIXME: libblkid doesn't show physical volumes as having a filesystem
        # so let's sniff for that.(#409321)
        try:
            fd = os.open(device, os.O_RDONLY)
            buf = os.read(fd, 2048)
        except:
            return fstype
        finally:
            try:
                os.close(fd)
            except:
                pass

        if buf.startswith("HM"):
            return "physical volume (LVM)"
        for sec in range(0, 4):
            off = (sec * 512) + 24
            if len(buf) < off:
                continue
            if buf[off:].startswith("LVM2"):
                return "physical volume (LVM)"
    elif fstype == "lvm2pv":
        return "physical volume (LVM)"
    return fstype

def ext2IsDirty(device):
    label = _isys.e2dirty(device)
    return label

def ext2HasJournal(device):
    hasjournal = _isys.e2hasjournal(device)
    return hasjournal

def modulesWithPaths():
    mods = []
    for modline in open("/proc/modules", "r"):
        modName = modline.split(" ", 1)[0]
        modInfo = iutil.execWithCapture("modinfo",
                ["-F", "filename", modName]).splitlines()
        modPaths = [ line.strip() for line in modInfo if line!="" ]
        mods.extend(modPaths)
    return mods

def driveUsesModule(device, modules):
    """Returns true if a drive is using a prticular module.  Only works
       for SCSI devices right now."""

    if not isinstance(modules, ().__class__) and not \
            isinstance(modules, [].__class__):
        modules = [modules]

    if device[:2] == "hd":
        return False
    rc = False
    if os.access("/tmp/scsidisks", os.R_OK):
        sdlist=open("/tmp/scsidisks", "r")
        sdlines = sdlist.readlines()
        sdlist.close()
        for l in sdlines:
            try:
                # each line has format of:  <device>  <module>
                (sddev, sdmod) = string.split(l)

                if sddev == device:
                    if sdmod in modules:
                        rc = True
                        break
            except:
                    pass
    return rc

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

# Get the MAC address for a network device.
def getMacAddress(dev):
    if dev == '' or dev is None:
        return False

    device_props_iface = getDeviceProperties(dev=dev)
    if device_props_iface is None:
        return None

    device_macaddr = None
    try:
        device_macaddr = device_props_iface.Get(NM_DEVICE_WIRED_IFACE, "HwAddress").upper()
    except dbus.exceptions.DBusException as e:
        if e.get_dbus_name() != 'org.freedesktop.DBus.Error.InvalidArgs':
            raise
    return device_macaddr

# Get a description string for a network device (e.g., eth0)
def getNetDevDesc(dev):
    from pyanaconda.baseudev import udev_get_device
    desc = "Network Interface"

    if dev == '' or dev is None:
        return desc

    bus = dbus.SystemBus()
    nm = bus.get_object(NM_SERVICE, NM_MANAGER_PATH)
    devlist = nm.get_dbus_method("GetDevices")()

    for path in devlist:
        device = bus.get_object(NM_SERVICE, path)
        device_iface = dbus.Interface(device, DBUS_PROPS_IFACE)
        device_props = device_iface.get_dbus_method("GetAll")(NM_DEVICE_IFACE)

        if dev == device_props['Interface']:
            # This is the sysfs path (for now).
            udev_path = device_props['Udi']
            dev = udev_get_device(udev_path[4:])

            if dev is None:
                log.debug("weird, we have a None dev with path %s" % path)
            elif dev.has_key("ID_VENDOR_ENC") and dev.has_key("ID_MODEL_ENC"):
                desc = "%s %s" % (dev["ID_VENDOR_ENC"], dev["ID_MODEL_ENC"])
            elif dev.has_key("ID_VENDOR_FROM_DATABASE") and dev.has_key("ID_MODEL_FROM_DATABASE"):
                desc = "%s %s" % (dev["ID_VENDOR_FROM_DATABASE"], dev["ID_MODEL_FROM_DATABASE"])

            return desc

    return desc

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

## Get the correct context for a file from loaded policy.
# @param fn The filename to query.
def matchPathContext(fn):
    con = None
    try:
        con = selinux.matchpathcon(os.path.normpath(fn), 0)[1]
    except OSError as e:
        log.info("failed to get default SELinux context for %s: %s" % (fn, e))
    return con

## Set the SELinux file context of a file
# @param fn The filename to fix.
# @param con The context to use.
# @param instroot An optional root filesystem to look under for fn.
def setFileContext(fn, con, instroot = '/'):
    full_path = os.path.normpath("%s/%s" % (instroot, fn))
    rc = False
    if con is not None and os.access(full_path, os.F_OK):
        try:
            rc = (selinux.lsetfilecon(full_path, con) == 0)
        except OSError as e:
            log.info("failed to set SELinux context for %s: %s" % (full_path, e))
    return rc

## Restore the SELinux file context of a file to its default.
# @param fn The filename to fix.
# @param instroot An optional root filesystem to look under for fn.
def resetFileContext(fn, instroot = '/'):
    con = matchPathContext(fn)
    if con:
        if setFileContext(fn, con, instroot):
            return con
    return None

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
    if not iutil.isX86():
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
