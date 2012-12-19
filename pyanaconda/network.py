#
# network.py - network configuration install data
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
#               2008, 2009
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
# Author(s): Matt Wilson <ewt@redhat.com>
#            Erik Troan <ewt@redhat.com>
#            Mike Fulbright <msf@redhat.com>
#            Brent Fox <bfox@redhat.com>
#            David Cantrell <dcantrell@redhat.com>
#

import string
import shutil
import isys
import iutil
import socket
import struct
import os
import time
import dbus
import tempfile
import simpleconfig
import re
from flags import flags
from simpleconfig import IfcfgFile
import urlgrabber.grabber
from pyanaconda.storage.devices import FcoeDiskDevice, iScsiDiskDevice

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

sysconfigDir = "/etc/sysconfig"
netscriptsDir = "%s/network-scripts" % (sysconfigDir)
networkConfFile = "%s/network" % (sysconfigDir)
hostnameFile = "/etc/hostname"
ipv6ConfFile = "/etc/modprobe.d/ipv6.conf"
ifcfgLogFile = "/tmp/ifcfg.log"
CONNECTION_TIMEOUT = 45

# part of a valid hostname between two periods (cannot start nor end with '-')
# for more info about '(?!-)' and '(?<!-)' see 're' module documentation
HOSTNAME_PART_RE = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)

# Setup special logging for ifcfg NM interface
from pyanaconda import anaconda_log
logger = logging.getLogger("ifcfg")
logger.setLevel(logging.DEBUG)
anaconda_log.logger.addFileHandler(ifcfgLogFile, logger, logging.DEBUG)
if os.access("/dev/tty3", os.W_OK):
    anaconda_log.logger.addFileHandler("/dev/tty3", logger,
                                       anaconda_log.DEFAULT_TTY_LEVEL,
                                       anaconda_log.TTY_FORMAT,
                                       autoLevel=True)
anaconda_log.logger.forwardToSyslog(logger)

ifcfglog = logging.getLogger("ifcfg")

class IPError(Exception):
    pass

class IPMissing(Exception):
    pass

def sanityCheckHostname(hostname):
    """
    Check if the given string is (syntactically) a valid hostname.

    @param hostname: a string to check
    @returns: a pair containing boolean value (valid or invalid) and
              an error message (if applicable)
    @rtype: (bool, str)

    """

    if not hostname:
        return (False, _("Hostname cannot be None or an empty string."))

    if len(hostname) > 255:
        return (False, _("Hostname must be 255 or fewer characters in length."))

    validStart = string.ascii_letters + string.digits
    validAll = validStart + ".-"

    if hostname[0] not in validStart:
        return (False, _("Hostname must start with a valid character in the "
                         "ranges 'a-z', 'A-Z', or '0-9'"))

    if hostname.endswith("."):
        # hostname can end with '.', but the regexp used below would not match
        hostname = hostname[:-1]

    if not all(HOSTNAME_PART_RE.match(part) for part in hostname.split(".")):
        return (False, _("Hostnames can only contain the characters 'a-z', "
                         "'A-Z', '0-9', '-', or '.', parts between periods "
                         "must contain something and cannot start or end with "
                         "'-'."))

    return (True, "")

# Return a list of IP addresses for all active devices.
def getIPs():
    ips = []
    for devname in getActiveNetDevs():
        try:
            ips += (isys.getIPAddresses(devname, version=4) +
                   isys.getIPAddresses(devname, version=6))
        except Exception as e:
            log.warning("Got an exception trying to get the ip addr "
                        "of %s: %s" % (devname, e))
    return ips

# Return the first real non-local IP we find
def getFirstRealIP():
    for ip in getIPs():
        if ip not in ("127.0.0.1", "::1"):
            return ip
    return None

# Try to determine what the hostname should be for this system
def getHostname():

    hn = None

    # First address (we prefer ipv4) of last device (as it used to be) wins
    for dev in getActiveNetDevs():
        addrs = (isys.getIPAddresses(dev, version=4) +
                 isys.getIPAddresses(dev, version=6))
        for ipaddr in addrs:
            try:
                hinfo = socket.gethostbyaddr(ipaddr)
            except Exception as e:
                log.debug("Exception caught trying to get host name of %s: %s" %
                          (ipaddr, e))
            else:
                if len(hinfo) == 3:
                    hn = hinfo[0]
                    break

    if not hn or hn in ('(none)', 'localhost', 'localhost.localdomain'):
        hn = socket.gethostname()

    if not hn or hn in ('(none)', 'localhost'):
        hn = 'localhost.localdomain'

    return hn

# sanity check an IP string.
def sanityCheckIPString(ip_string):
    if not ip_string.strip():
        raise IPMissing, _("IP address is missing.")

    if '.' in ip_string[1:] and ':' not in ip_string:
        family = socket.AF_INET
        errstr = _("IPv4 addresses must contain four numbers between 0 and 255, separated by periods.")
    elif ':' in ip_string[1:] and '.' not in ip_string:
        family = socket.AF_INET6
        errstr = _("'%s' is not a valid IPv6 address.") % ip_string
    else:
        raise IPError, _("'%s' is an invalid IP address.") % ip_string

    try:
        socket.inet_pton(family, ip_string)
    except socket.error:
        raise IPError, errstr

def nmIsConnected(state):
    return state in (isys.NM_STATE_CONNECTED_LOCAL,
                     isys.NM_STATE_CONNECTED_SITE,
                     isys.NM_STATE_CONNECTED_GLOBAL)

def hasActiveNetDev():
    try:
        bus = dbus.SystemBus()
        nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
        props = dbus.Interface(nm, isys.DBUS_PROPS_IFACE)
        state = props.Get(isys.NM_SERVICE, "State")

        return nmIsConnected(state)
    except:
        return flags.testing

# Return a list of device names (e.g., eth0) for all active devices.
# Returning a list here even though we will almost always have one
# device.  NM uses lists throughout its D-Bus communication, so trying
# to follow suit here.  Also, if this uses a list now, we can think
# about multihomed hosts during installation later.
def getActiveNetDevs():
    active_devs = set()

    bus = dbus.SystemBus()
    nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
    nm_props_iface = dbus.Interface(nm, isys.DBUS_PROPS_IFACE)

    active_connections = nm_props_iface.Get(isys.NM_MANAGER_IFACE, "ActiveConnections")

    for connection in active_connections:
        active_connection = bus.get_object(isys.NM_SERVICE, connection)
        active_connection_props_iface = dbus.Interface(active_connection, isys.DBUS_PROPS_IFACE)
        devices = active_connection_props_iface.Get(isys.NM_ACTIVE_CONNECTION_IFACE, 'Devices')

        for device_path in devices:
            device = bus.get_object(isys.NM_SERVICE, device_path)
            device_props_iface = dbus.Interface(device, isys.DBUS_PROPS_IFACE)

            interface_name = device_props_iface.Get(isys.NM_DEVICE_IFACE, 'Interface')
            active_devs.add(interface_name)

    ret = list(active_devs)
    ret.sort()
    return ret

def logIfcfgFile(path, message=""):
    content = ""
    if os.access(path, os.R_OK):
        f = open(path, 'r')
        content = f.read()
        f.close()
    else:
        content = "file not found"
    ifcfglog.debug("%s%s:\n%s" % (message, path, content))

def logIfcfgFiles(message=""):
    ifcfglog.debug("content of files (%s):" % message)
    for name in os.listdir(netscriptsDir):
        if name.startswith("ifcfg-"):
            if name == 'ifcfg-lo':
                continue
            path = os.path.join(netscriptsDir, name)
            f = open(path, 'r')
            content = f.read()
            f.close()
            ifcfglog.debug("%s:\n%s" % (path, content))

class NetworkDevice(IfcfgFile):

    def __init__(self, dir, iface):
        IfcfgFile.__init__(self, dir, iface)
        if iface.startswith('ctc'):
            self.info["TYPE"] = "CTC"
        self.wepkey = ""
        self._dirty = False

    def clear(self):
        IfcfgFile.clear(self)
        if self.iface.startswith('ctc'):
            self.info["TYPE"] = "CTC"
        self.wepkey = ""

    def __str__(self):
        s = ""
        keys = self.info.keys()
        if iutil.isS390() and ("HWADDR" in keys):
            keys.remove("HWADDR")
        # make sure we include autoneg in the ethtool line
        if 'ETHTOOL_OPTS' in keys:
            eopts = self.get('ETHTOOL_OPTS')
            if "autoneg" not in eopts:
                self.set(('ETHTOOL_OPTS', "autoneg off %s" % eopts))

        for key in keys:
            if self.info[key] is not None:
                s = s + key + '="' + self.info[key] + '"\n'

        return s

    # anaconda doesn't actually need this configuration, but if we don't write
    # it to the installed system then 'ifup' doesn't work after install.
    # FIXME: make 'ifup' use its own defaults!
    def setDefaultConfig(self):
        ifcfglog.debug("NetworkDevice %s: setDefaultConfig()" % self.iface)
        self.set(("DEVICE", self.iface),
                 ("BOOTPROTO", "dhcp"),
                 ("ONBOOT", "no")) # for "security", or something

        try:
            mac = open("/sys/class/net/%s/address" % self.iface).read().strip()
            self.set(("HWADDR", mac.upper()))
        except IOError as e:
            ifcfglog.warning("HWADDR: %s" % str(e))

        try:
            uuid = open("/proc/sys/kernel/random/uuid").read().strip()
            self.set(("UUID", uuid))
        except IOError as e:
            ifcfglog.warning("UUID: %s" % str(e))

        self.writeIfcfgFile()

    def loadIfcfgFile(self):
        ifcfglog.debug("loadIfcfFile %s" % self.path)

        self.clear()
        IfcfgFile.read(self)
        self._dirty = False

    def writeIfcfgFile(self):
        # Write out the file only if there is a key whose
        # value has been changed since last load of ifcfg file.
        ifcfglog.debug("writeIfcfgFile %s to %s%s" % (self.iface, self.path,
                                                  ("" if self._dirty else " not needed")))
        if self._dirty:
            ifcfglog.debug("old %s:\n%s" % (self.path, self.fileContent()))
            ifcfglog.debug("writing NetworkDevice %s:\n%s" % (self.iface, self.__str__()))
            IfcfgFile.write(self)
            self._dirty = False

        # We can't read the file right now racing with ifcfg-rh update
        #ifcfglog.debug("%s:\n%s" % (device.path, device.fileContent()))

    def set(self, *args):
        # If we are changing value of a key set _dirty flag
        # informing that ifcfg file needs to be synced.
        s = " ".join(["%s=%s" % key_val for key_val in args])
        ifcfglog.debug("NetworkDevice %s set: %s" %
                       (self.iface, s))
        for (key, data) in args:
            if self.get(key) != data:
                break
        else:
            return
        IfcfgFile.set(self, *args)
        self._dirty = True

    @property
    def keyfilePath(self):
        return os.path.join(self.dir, "keys-%s" % self.iface)

    def writeWepkeyFile(self, dir=None, overwrite=True):
        if not self.wepkey:
            return False
        if not dir:
            keyfile = self.keyfilePath
        else:
            keyfile = os.path.join(dir, os.path.basename(self.keyfilePath))

        if not overwrite and os.path.isfile(keyfile):
            return False

        fd, newifcfg = tempfile.mkstemp(prefix="keys-%s" % self.iface, text=False)
        os.write(fd, "KEY1=%s\n" % self.wepkey)
        os.close(fd)

        os.chmod(newifcfg, 0644)
        try:
            os.remove(keyfile)
        except OSError as e:
            if e.errno != 2:
                raise
        shutil.move(newifcfg, keyfile)

    def fileContent(self):
        if not os.path.exists(self.path):
            return ""
        f = open(self.path, 'r')
        content = f.read()
        f.close()
        return content

    def setGateway(self, gw):
        if ':' in gw:
            self.set(('IPV6_DEFAULTGW', gw))
        else:
            self.set(('GATEWAY', gw))

    def unsetDNS(self):
        """Unset all DNS* ifcfg parameters."""
        i = 1
        while True:
            if self.get("DNS%d" % i):
                self.unset("DNS%d" %i)
            else:
                break
            i += 1

    def setDNS(self, ns):
        dns = ns.split(',')
        i = 1
        for addr in dns:
            addr = addr.strip()
            dnslabel = "DNS%d" % (i,)
            self.set((dnslabel, addr))
            i += 1

class WirelessNetworkDevice(NetworkDevice):

    """
    This class overwrites NetworkDevice's, IfcfgFile's and SimpleConfigFile's
    methods to prevent working with per-device ifcfgfiles (which doesn't make
    sense with wifi devices)
    """

    def __init__(self, iface):
        self.info = dict()
        self.iface = iface
        self.dir = ""

    def clear(self):
        self.info = dict()

    #method __str__ can be left untouched

    def loadIfcfgFile(self):
        pass

    def writeIfcfgFile(self):
        pass

    def set(self, *args):
        msg = "".join(["%s=%s" % (key, val) for (key, val) in args])
        for (key, val) in args:
            self.info[simpleconfig.uppercase_ASCII_string(key)] = val

    #not used, remove?
    def fileContent(self):
        return ""

    #@property path can be left untouched (code using it skips nonexisting
    #ifcfg files

    def read(self):
        #same return value as IfcfgFile.read()
        return len(self.info)

    def write(self):
        pass

def get_NM_object(path):
    return dbus.SystemBus().get_object(isys.NM_SERVICE, path)

def createMissingDefaultIfcfgs():
    """
    Create or dump missing default ifcfg file for wired devices.
    For default auto connections created by NM upon start - which happens
    in case of missing ifcfg file - rename the connection using device name
    and dump its ifcfg file. (For server, default auto connections will
    be turned off in NetworkManager.conf.)
    If there is no default auto connection for a device, create default
    ifcfg file.
    Returns True if any ifcfg file was created or dumped.

    """
    rv = False
    nm = get_NM_object(isys.NM_MANAGER_PATH)
    dev_paths = nm.GetDevices()
    settings = get_NM_object(isys.NM_SETTINGS_PATH)
    for devpath in dev_paths:
        device = get_NM_object(devpath)
        device_props_iface = dbus.Interface(device, isys.DBUS_PROPS_IFACE)
        devicetype = device_props_iface.Get(isys.NM_DEVICE_IFACE, "DeviceType")
        if devicetype == isys.NM_DEVICE_TYPE_WIFI:
            continue
        # if there is no ifcfg file for the device
        interface = str(device_props_iface.Get(isys.NM_DEVICE_IFACE, "Interface"))
        device_cfg = NetworkDevice(netscriptsDir, interface)
        if os.access(device_cfg.path, os.R_OK):
            continue
        # check if there is a connection for the device (default autoconnection)
        hwaddr = device_props_iface.Get(isys.NM_DEVICE_WIRED_IFACE, "HwAddress")
        con_paths = settings.ListConnections()
        for con_path in con_paths:
            con = get_NM_object(con_path)
            setting = con.GetSettings()
            con_hwaddr = ":".join("%02X" % byte for byte in
                                  setting['802-3-ethernet']['mac-address'])
            # if so, write its configuration with name changed to iface
            if con_hwaddr.upper() == hwaddr.upper():
                setting['connection']['id'] = interface
                con.Update(setting)
                rv = True
                log.debug("network: dumped ifcfg file for default autoconnection on %s" % interface)
                break
        else:
            # if there is no connection, create default ifcfg
            device_cfg.setDefaultConfig()
            rv = True
    return rv

def getDevices():
    # TODO: filter with existence of ifcfg file?
    return isys.getDeviceProperties().keys()

def waitForDevicesActivation(devices):
    waited_devs_props = {}

    bus = dbus.SystemBus()
    nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
    device_paths = nm.get_dbus_method("GetDevices")()
    for device_path in device_paths:
        device = bus.get_object(isys.NM_SERVICE, device_path)
        device_props_iface = dbus.Interface(device, isys.DBUS_PROPS_IFACE)
        iface = str(device_props_iface.Get(isys.NM_DEVICE_IFACE, "Interface"))
        if iface in devices:
            waited_devs_props[iface] = device_props_iface

    i = 0
    while True:
        for dev, device_props_iface in waited_devs_props.items():
            state = device_props_iface.Get(isys.NM_DEVICE_IFACE, "State")
            if state == isys.NM_DEVICE_STATE_ACTIVATED:
                waited_devs_props.pop(dev)
        if len(waited_devs_props) == 0 or i >= CONNECTION_TIMEOUT:
            break
        i += 1
        time.sleep(1)

    return waited_devs_props.keys()

# get a kernel cmdline string for dracut needed for access to storage host
def dracutSetupArgs(networkStorageDevice):

    if networkStorageDevice.nic == "default" or ":" in networkStorageDevice.nic:
        nic = ifaceForHostIP(networkStorageDevice.host_address)
        if not nic:
            return ""
    else:
        nic = networkStorageDevice.nic

    if nic not in getDevices():
        log.error('Unknown network interface: %s' % nic)
        return ""

    ifcfg = NetworkDevice(netscriptsDir, nic)
    ifcfg.loadIfcfgFile()
    return dracutBootArguments(ifcfg,
                               networkStorageDevice.host_address,
                               getHostname())

def dracutBootArguments(ifcfg, storage_ipaddr, hostname=None):

    netargs = set()
    devname = ifcfg.iface

    if ifcfg.get('BOOTPROTO') == 'ibft':
        netargs.add("ip=ibft")
    elif storage_ipaddr:
        if hostname is None:
            hostname = ""
        # if using ipv6
        if ':' in storage_ipaddr:
            if ifcfg.get('DHCPV6C') == "yes":
                # XXX combination with autoconf not yet clear,
                # support for dhcpv6 is not yet implemented in NM/ifcfg-rh
                netargs.add("ip=%s:dhcp6" % devname)
            elif ifcfg.get('IPV6_AUTOCONF') == "yes":
                netargs.add("ip=%s:auto6" % devname)
            elif ifcfg.get('IPV6ADDR'):
                ipaddr = "[%s]" % ifcfg.get('IPV6ADDR')
                if ifcfg.get('IPV6_DEFAULTGW'):
                    gateway = "[%s]" % ifcfg.get('IPV6_DEFAULTGW')
                else:
                    gateway = ""
                netargs.add("ip=%s::%s:%s:%s:%s:none" % (ipaddr, gateway,
                           ifcfg.get('PREFIX'), hostname, devname))
        else:
            if ifcfg.get('bootproto').lower() == 'dhcp':
                netargs.add("ip=%s:dhcp" % devname)
            else:
                if ifcfg.get('GATEWAY'):
                    gateway = ifcfg.get('GATEWAY')
                else:
                    gateway = ""

                netmask = ifcfg.get('netmask')
                prefix  = ifcfg.get('prefix')
                if not netmask and prefix:
                    netmask = isys.prefix2netmask(int(prefix))

                netargs.add("ip=%s::%s:%s:%s:%s:none" % (ifcfg.get('ipaddr'),
                           gateway, netmask, hostname, devname))

    hwaddr = ifcfg.get("HWADDR")
    if hwaddr:
        netargs.add("ifname=%s:%s" % (devname, hwaddr.lower()))

    nettype = ifcfg.get("NETTYPE")
    subchannels = ifcfg.get("SUBCHANNELS")
    if iutil.isS390() and nettype and subchannels:
        znet = "rd.znet=%s,%s" % (nettype, subchannels)
        options = ifcfg.get("OPTIONS").strip("'\"")
        if options:
            options = filter(lambda x: x != '', options.split(' '))
            znet += ",%s" % (','.join(options))
        netargs.add(znet)

    return netargs

def kickstartNetworkData(ifcfg=None, hostname=None):

    from pyanaconda.kickstart import AnacondaKSHandler
    handler = AnacondaKSHandler()
    kwargs = {}

    if not ifcfg and hostname:
        return handler.NetworkData(hostname=hostname, bootProto="")

    # ipv4 and ipv6
    if not ifcfg.get("ESSID"):
        kwargs["device"] = ifcfg.iface
    if ifcfg.get("ONBOOT") and ifcfg.get("ONBOOT" ) == "no":
        kwargs["onboot"] = False
    if ifcfg.get('MTU') and ifcfg.get('MTU') != "0":
        kwargs["mtu"] = ifcfg.get('MTU')

    # ipv4
    if not ifcfg.get('BOOTPROTO'):
        kwargs["noipv4"] = True
    else:
        if ifcfg.get('BOOTPROTO').lower() == 'dhcp':
            kwargs["bootProto"] = "dhcp"
            if ifcfg.get('DHCPCLASS'):
                kwargs["dhcpclass"] = ifcfg.get('DHCPCLASS')
        elif ifcfg.get('IPADDR'):
            kwargs["bootProto"] = "static"
            kwargs["ip"] = ifcfg.get('IPADDR')
            netmask = ifcfg.get('NETMASK')
            prefix  = ifcfg.get('PREFIX')
            if not netmask and prefix:
                netmask = isys.prefix2netmask(int(prefix))
            if netmask:
                kwargs["netmask"] = netmask
            # note that --gateway is common for ipv4 and ipv6
            if ifcfg.get('GATEWAY'):
                kwargs["gateway"] = ifcfg.get('GATEWAY')

    # ipv6
    if (not ifcfg.get('IPV6INIT') or
        ifcfg.get('IPV6INIT') == "no"):
        kwargs["noipv6"] = True
    else:
        if ifcfg.get('IPV6_AUTOCONF') == "yes":
            kwargs["ipv6"] = "auto"
        else:
            if ifcfg.get('IPV6ADDR'):
                kwargs["ipv6"] = ifcfg.get('IPV6ADDR')
                if ifcfg.get('IPV6_DEFAULTGW'):
                    kwargs["gateway"] = ifcfg.get('IPV6_DEFAULTGW')
            if ifcfg.get('DHCPV6') == "yes":
                kwargs["ipv6"] = "dhcp"

    # ipv4 and ipv6
    dnsline = ''
    for key in ifcfg.info.keys():
        if key.upper().startswith('DNS'):
            if dnsline == '':
                dnsline = ifcfg.get(key)
            else:
                dnsline += "," + ifcfg.get(key)
    if dnsline:
        kwargs["nameserver"] = dnsline

    if ifcfg.get("ETHTOOL_OPTS"):
        kwargs["ethtool"] = ifcfg.get("ETHTOOL_OPTS")

    if ifcfg.get("ESSID"):
        kwargs["essid"] = ifcfg.get("ESSID")

    # hostname
    if ifcfg.get("DHCP_HOSTNAME"):
        kwargs["hostname"] = ifcfg.get("DHCP_HOSTNAME")
    elif ifcfg.get("BOOTPROTO").lower != "dhcp":
        if (hostname and
            hostname != "localhost.localdomain"):
            kwargs["hostname"] = hostname

    return handler.NetworkData(**kwargs)

def getSSIDs(devices_to_scan=None):

    rv = {}
    bus = dbus.SystemBus()
    nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
    device_paths = nm.get_dbus_method("GetDevices")()

    for device_path in device_paths:

        device = bus.get_object(isys.NM_SERVICE, device_path)
        device_props_iface = dbus.Interface(device, isys.DBUS_PROPS_IFACE)
        # interface name, eg. "eth0", "wlan0"
        dev = str(device_props_iface.Get(isys.NM_DEVICE_IFACE, "Interface"))

        if (isys.isWirelessDevice(dev) and
            (not devices_to_scan or dev in devices_to_scan)):

            i = 0
            log.info("scanning APs for %s" % dev)
            while i < 5:
                ap_paths = device.GetAccessPoints(dbus_interface='org.freedesktop.NetworkManager.Device.Wireless')
                if ap_paths:
                    break
                time.sleep(0.5)
                i += 0.5

            ssids = []
            for ap_path in ap_paths:
                ap = bus.get_object(isys.NM_SERVICE, ap_path)
                ap_props = dbus.Interface(ap, isys.DBUS_PROPS_IFACE)
                ssid_bytearray = ap_props.Get(isys.NM_ACCESS_POINT_IFACE, "Ssid")
                ssid = "".join((str(b) for b in ssid_bytearray))
                ssids.append(ssid)
            log.info("APs found for %s: %s" % (dev, str(ssids)))
            # XXX there can be duplicates in a list, but maybe
            # we want to keep them when/if we differentiate on something
            # more then just ssids; for now, remove them
            rv[dev]=list(set(ssids))

    return rv

def ifaceForHostIP(host):
    route = iutil.execWithCapture("ip", [ "route", "get", "to", host ])
    if not route:
        log.error("Could not get interface for route to %s" % host)
        return ""

    routeInfo = route.split()
    if routeInfo[0] != host or len(routeInfo) < 5 or \
       "dev" not in routeInfo or routeInfo.index("dev") > 3:
        log.error('Unexpected "ip route get to %s" reply: %s' %
                  (host, routeInfo))
        return ""

    return routeInfo[routeInfo.index("dev") + 1]

def setHostname(hn):
    if flags.imageInstall:
        log.info("image install -- not setting hostname")
        return

    log.info("setting installation environment hostname to %s" % hn)
    iutil.execWithRedirect("hostname", ["-v", hn ],
                           stdout="/dev/tty5", stderr="/dev/tty5")

def copyFileToPath(file, destPath='', overwrite=False):
    if not os.path.isfile(file):
        return False
    destfile = os.path.join(destPath, file.lstrip('/'))
    if (os.path.isfile(destfile) and not overwrite):
        return False
    if not os.path.isdir(os.path.dirname(destfile)):
        iutil.mkdirChain(os.path.dirname(destfile))
    shutil.copy(file, destfile)
    return True

# /etc/sysconfig/network-scripts/ifcfg-*
# /etc/sysconfig/network-scripts/keys-*
# TODO: routing info from /etc/sysconfig/network-scripts?
def copyIfcfgFiles(destPath):
    files = os.listdir(netscriptsDir)
    for cfgFile in files:
        if cfgFile.startswith(("ifcfg-","keys-")):
            srcfile = os.path.join(netscriptsDir, cfgFile)
            copyFileToPath(srcfile, destPath)

# /etc/dhcp/dhclient-DEVICE.conf
# TODORV: do we really don't want overwrite on live cd?
def copyDhclientConfFiles(destPath):
    for devName in getDevices():
        dhclientfile = os.path.join("/etc/dhcp/dhclient-%s.conf" % devName)
        copyFileToPath(dhclientfile, destPath)

def get_ksdevice_name(ksspec=""):

    if not ksspec:
        ksspec = flags.cmdline.get('ksdevice', "")
    ksdevice = ksspec

    bootif_mac = None
    if ksdevice == 'bootif' and "BOOTIF" in flags.cmdline:
        bootif_mac = flags.cmdline["BOOTIF"][3:].replace("-", ":").upper()
    for dev in sorted(getDevices()):
        # "eth0"
        if ksdevice == dev:
            break
        # "link"
        elif ksdevice == 'link' and isys.getLinkStatus(dev):
            ksdevice = dev
            break
        # "XX:XX:XX:XX:XX:XX" (mac address)
        elif ':' in ksdevice:
            if ksdevice.upper() == isys.getMacAddress(dev):
                ksdevice = dev
                break
        # "bootif" and BOOTIF==XX:XX:XX:XX:XX:XX
        elif ksdevice == 'bootif':
            if bootif_mac == isys.getMacAddress(dev):
                ksdevice = dev
                break

    return ksdevice

# note that NetworkDevice.get returns "" if key is not found
def get_ifcfg_value(iface, key, root_path=""):
    dev = NetworkDevice(os.path.normpath(root_path + netscriptsDir), iface)
    dev.loadIfcfgFile()
    return dev.get(key)

def write_hostname(rootpath, ksdata, overwrite=False):
    cfgfile = os.path.normpath(rootpath + hostnameFile)
    if (os.path.isfile(cfgfile) and not overwrite):
        return False

    f = open(cfgfile, "w")
    f.write("%s\n" % ksdata.network.hostname)
    f.close()

    return True

def write_sysconfig_network(rootpath, ksdata, overwrite=False):

    cfgfile = os.path.normpath(rootpath + networkConfFile)
    if (os.path.isfile(cfgfile) and not overwrite):
        return False

    f = open(cfgfile, "w")
    f.write("# Generated by anaconda\n")
    f.write("NETWORKING=yes\n")

    gateway = ipv6_defaultgw = None
    for iface in reversed(getDevices()):
        if isys.isWirelessDevice(iface):
            continue
        dev = NetworkDevice(netscriptsDir, iface)
        dev.loadIfcfgFile()
        if dev.get('DEFROUTE') != "no":
            continue
        if dev.get('GATEWAY'):
            gateway = dev.get('GATEWAY')
        if dev.get('IPV6_DEFAULTGW'):
            ipv6_defaultgw = dev.get('IPV6_DEFAULTGW')
        if gateway and ipv6_defaultgw:
            break

    if gateway:
        f.write("GATEWAY=%s\n" % gateway)

    if ipv6_defaultgw:
        f.write("IPV6_DEFAULTGW=%s\n" % ipv6_defaultgw)
    f.close()

    return True

def disableIPV6(rootpath):
    cfgfile = os.path.normpath(rootpath + ipv6ConfFile)
    if ('noipv6' in flags.cmdline
        and not any(get_ifcfg_value(dev, 'IPV6INIT') == "yes"
                    for dev in getDevices())):
        if os.path.exists(cfgfile):
            log.warning('Not disabling ipv6, %s exists' % cfgfile)
        else:
            log.info('Disabling ipv6 on target system')
            f = open(cfgfile, "w")
            f.write("# Anaconda disabling ipv6\n")
            f.write("options ipv6 disable=1\n")
            f.close()

def disableNMForStorageDevices(rootpath, storage):
    for devname in getDevices():
        if (usedByFCoE(devname, storage) or
            usedByRootOnISCSI(devname, storage)):
            dev = NetworkDevice(rootpath + netscriptsDir, devname)
            if os.access(dev.path, os.R_OK):
                dev.loadIfcfgFile()
                dev.set(('NM_CONTROLLED', 'no'))
                dev.writeIfcfgFile()
                log.info("network device %s used by storage will not be "
                         "controlled by NM" % devname)
            else:
                log.warning("disableNMForStorageDevices: ifcfg file for %s not found" %
                            devname)

# sets ONBOOT=yes (and its mirror value in ksdata) for devices used by FCoE
def autostartFCoEDevices(rootpath, storage, ksdata):
    for devname in getDevices():
        if usedByFCoE(devname, storage):
            dev = NetworkDevice(rootpath + netscriptsDir, devname)
            if os.access(dev.path, os.R_OK):
                dev.loadIfcfgFile()
                dev.set(('ONBOOT', 'yes'))
                dev.writeIfcfgFile()
                log.debug("setting ONBOOT=yes for network device %s used by fcoe"
                          % devname)
                for nd in ksdata.network.network:
                    if nd.device == dev.iface:
                        nd.onboot = True
                        break
            else:
                log.warning("autoconnectFCoEDevices: ifcfg file for %s not found" %
                            devname)

def usedByFCoE(iface, storage):
    for d in storage.devices:
        if (isinstance(d, FcoeDiskDevice) and
            d.nic == iface):
            return True
    return False

def usedByRootOnISCSI(iface, storage):
    rootdev = storage.rootDevice
    for d in storage.devices:
        if (isinstance(d, iScsiDiskDevice) and
            rootdev.dependsOn(d)):
            if d.nic == "default" or ":" in d.nic:
                if iface == ifaceForHostIP(d.host_address):
                    return True
            elif d.nic == iface:
                return True

    return False

def write_network_config(storage, ksdata, instClass, rootpath):
    write_hostname(rootpath, ksdata, overwrite=flags.livecdInstall)
    write_sysconfig_network(rootpath, ksdata, overwrite=flags.livecdInstall)
    disableIPV6(rootpath)
    if not flags.imageInstall:
        copyIfcfgFiles(rootpath)
        copyDhclientConfFiles(rootpath)
        copyFileToPath("/etc/resolv.conf", rootpath, overwrite=flags.livecdInstall)
    # TODO the default for ONBOOT needs to be lay down
    # before newui we didn't set it for kickstart installs
    instClass.setNetworkOnbootDefault(ksdata)
    # NM_CONTROLLED is not mirrored in ksdata
    disableNMForStorageDevices(rootpath, storage)
    autostartFCoEDevices(rootpath, storage, ksdata)

def wait_for_dhcp():
    """If NM is in connecting state, wait for connection.
    Return value: NM has got connection."""
    bus = dbus.SystemBus()
    nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
    props = dbus.Interface(nm, isys.DBUS_PROPS_IFACE)
    state = props.Get(isys.NM_SERVICE, "State")

    if state == isys.NM_STATE_CONNECTING:
        log.debug("waiting for connecting NM (dhcp?)")
    else:
        return False

    i = 0
    while (state == isys.NM_STATE_CONNECTING and
           i < CONNECTION_TIMEOUT):
        state = props.Get(isys.NM_SERVICE, "State")
        if nmIsConnected(state):
            log.debug("connected, waited %d seconds" % i)
            return True
        i += 1
        time.sleep(1)

    log.debug("not connected, waited %d of %d secs" % (i, CONNECTION_TIMEOUT))
    return False

def update_hostname(ksdata, hostname=None):
    if not hostname:
        hostname = getHostname()
    log.debug("updating hostname %s" % hostname)
    hostname_found = False
    for nd in ksdata.network.network:
        if nd.hostname:
            nd.hostname = hostname
            hostname_found = True
    if not hostname_found:
        nd = kickstartNetworkData(hostname=hostname)
        ksdata.network.network.append(nd)

def get_device_name(devspec):

    devices = getDevices()
    devname = None

    if not devspec:
        if "ksdevice" in flags.cmdline:
            msg = "ksdevice boot parameter"
            devname = get_ksdevice_name(flags.cmdline["ksdevice"])
        elif hasActiveNetDev():
            # device activated in stage 1 by network kickstart command
            msg = "first active device"
            devname = getActiveNetDevs()[0]
        else:
            msg = "first device found"
            devname = min(devices)
        log.info("unspecified network --device in kickstart, using %s (%s)" %
                 (devname, msg))
    else:
        if devspec.lower() == "ibft":
            devname = ""
        if devspec.lower() == "link":
            for dev in sorted(devices):
                if isys.getLinkStatus(dev):
                    devname = dev
                    break
            else:
                log.error("Kickstart: No network device with link found")
        elif devspec.lower() == "bootif":
            if "BOOTIF" in flags.cmdline:
                # MAC address like 01-aa-bb-cc-dd-ee-ff
                devname = flags.cmdline["BOOTIF"][3:]
                devname = devname.replace("-",":")
            else:
                log.error("Using --device=bootif without BOOTIF= boot option supplied")
        else: devname = devspec

    if devname not in devices:
        for d in devices:
            if isys.getMacAddress(d).lower() == devname.lower():
                devname = d
                break

    return devname

def setOnboot(ksdata):
    for network_data in ksdata.network.network:

        devname = get_device_name(network_data.device)
        if not devname:
            log.error("Kickstart: The provided network interface %s does not exist" % devname)
            continue

        dev = NetworkDevice(netscriptsDir, devname)
        try:
            dev.loadIfcfgFile()
        except IOError as e:
            log.info("Can't load ifcfg file %s, %s" % (dev.path, e))
            continue

        if network_data.onboot:
            dev.set (("ONBOOT", "yes"))
        else:
            dev.set (("ONBOOT", "no"))
        dev.writeIfcfgFile()

# networking initialization and ksdata object update
def networkInitialize(ksdata):

    log.debug("network: devices found %s" % getDevices())
    logIfcfgFiles("network initialization")
    if not flags.imageInstall:
        # XXX: this should go to anaconda dracut
        if createMissingDefaultIfcfgs():
            logIfcfgFiles("ifcfgs created")

    # we set ONBOOT value using network --activate activate in dracut
    # to get devices activated by NM, so set proper ONBOOT value
    # based on --onboot here
    setOnboot(ksdata)

    if ksdata.network.hostname is None:
        update_hostname(ksdata)

    # auto default dhcp connection would be activated by NM service
    if wait_for_dhcp():
        update_hostname(ksdata)
