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
from flags import flags
from simpleconfig import IfcfgFile
from pyanaconda.constants import ROOT_PATH
import urlgrabber.grabber
from pyanaconda.storage.devices import FcoeDiskDevice, iScsiDiskDevice

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

sysconfigDir = "/etc/sysconfig"
netscriptsDir = "%s/network-scripts" % (sysconfigDir)
networkConfFile = "%s/network" % (sysconfigDir)
ipv6ConfFile = "/etc/modprobe.d/ipv6.conf"
ifcfgLogFile = "/tmp/ifcfg.log"
CONNECTION_TIMEOUT = 45

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
    if not hostname:
        return None

    if len(hostname) > 255:
        return _("Hostname must be 255 or fewer characters in length.")

    validStart = string.ascii_letters + string.digits
    validAll = validStart + ".-"

    if hostname[0] not in validStart:
        return _("Hostname must start with a valid character in the ranges "
                 "'a-z', 'A-Z', or '0-9'")

    for char in hostname[1:]:
        if char not in validAll:
            return _("Hostnames can only contain the characters 'a-z', 'A-Z', '0-9', '-', or '.'")

    return None

# Try to determine what the hostname should be for this system
def getHostname():
    resetResolver()

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
    ifcfglog.debug("%s%s:\n%s" % (message, path, content))

def logIfcfgFiles(message=""):
    devprops = isys.getDeviceProperties(dev=None)
    for device in devprops:
        path = "%s/ifcfg-%s" % (netscriptsDir, device)
        logIfcfgFile(path, message)

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
        ifcfglog.debug("%s:\n%s" % (self.path, self.fileContent()))
        ifcfglog.debug("NetworkDevice %s:\n%s" % (self.iface, self.__str__()))
        ifcfglog.debug("loadIfcfgFile %s from %s" % (self.iface, self.path))

        self.clear()
        IfcfgFile.read(self)
        self._dirty = False

        ifcfglog.debug("NetworkDevice %s:\n%s" % (self.iface, self.__str__()))

    def writeIfcfgFile(self):
        # Write out the file only if there is a key whose
        # value has been changed since last load of ifcfg file.
        ifcfglog.debug("%s:\n%s" % (self.path, self.fileContent()))
        ifcfglog.debug("NetworkDevice %s:\n%s" % (self.iface, self.__str__()))
        ifcfglog.debug("writeIfcfgFile %s to %s%s" % (self.iface, self.path,
                                                  ("" if self._dirty else " not needed")))

        if self._dirty:
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


class Network:

    def __init__(self):

        ifcfglog.debug("Network object created called")

        # TODO this may need to be handled in getDevices()
        if flags.imageInstall:
            return

        # TODO this should go away (patch pending),
        # default ifcfg files should be created in dracut

        # populate self.netdevices
        devhash = isys.getDeviceProperties(dev=None)
        for iface in devhash.keys():
            if not isys.isWirelessDevice(iface):
                device = NetworkDevice(netscriptsDir, iface)
                if not os.access(device.path, os.R_OK):
                    device.setDefaultConfig()

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

# write out current configuration state and wait for NetworkManager
# to bring the device up, watch NM state and return to the caller
# once we have a state
def waitForConnection():
    bus = dbus.SystemBus()
    nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
    props = dbus.Interface(nm, isys.DBUS_PROPS_IFACE)

    i = 0
    while i < CONNECTION_TIMEOUT:
        state = props.Get(isys.NM_SERVICE, "State")
        if nmIsConnected(state):
            return True
        i += 1
        time.sleep(1)

    state = props.Get(isys.NM_SERVICE, "State")
    if nmIsConnected(state):
        return True

    return False

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

def kickstartNetworkData(ifcfg, hostname=None):

    from pyanaconda.kickstart import NetworkData
    kwargs = {}

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

    return NetworkData(**kwargs)

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

def resetResolver():
    isys.resetResolv()
    urlgrabber.grabber.reset_curl_obj()

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

def write_sysconfig_network(rootpath, ksdata, overwrite=False):

    cfgfile = os.path.normpath(rootpath + networkConfFile)
    if (os.path.isfile(cfgfile) and not overwrite):
        return False

    f = open(cfgfile, "w")
    f.write("# Generated by anaconda\n")
    f.write("NETWORKING=yes\n")
    f.write("HOSTNAME=")

    f.write("HOSTNAME=%s\n" % ksdata.network.hostname)

    gateway = ipv6_defaultgw = None
    for iface in reversed(getDevices()):
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

def disableNMForStorageDevices(storage):
    for devname in getDevices():
        if (usedByFCoE(devname, storage) or
            usedByRootOnISCSI(devname, storage)):
            dev = NetworkDevice(ROOT_PATH + netscriptsDir, devname)
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
def autostartFCoEDevices(storage, ksdata):
    for devname in getDevices():
        if usedByFCoE(devname, storage):
            dev = NetworkDevice(ROOT_PATH + netscriptsDir, devname)
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

def writeNetworkConf(storage, ksdata, instClass):
    write_sysconfig_network(ROOT_PATH, ksdata, overwrite=flags.livecdInstall)
    disableIPV6(ROOT_PATH)
    if not flags.imageInstall:
        copyIfcfgFiles(ROOT_PATH)
        copyDhclientConfFiles(ROOT_PATH)
        copyFileToPath("/etc/resolv.conf", ROOT_PATH, overwrite=flags.livecdInstall)
    # TODO the default for ONBOOT needs to be lay down
    # before newui we didn't set it for kickstart installs
    instClass.setNetworkOnbootDefault(ksdata)
    # NM_CONTROLLED is not mirrored in ksdata
    disableNMForStorageDevices(storage)
    autostartFCoEDevices(storage, ksdata)
