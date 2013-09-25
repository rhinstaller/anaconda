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
#            Radek Vykydal <rvykydal@redhat.com>

import string
import shutil
from pyanaconda import iutil
import socket
import os
import time
import threading
import re
import dbus
import IPy
import itertools

from pyanaconda.simpleconfig import SimpleConfigFile
from blivet.devices import FcoeDiskDevice, iScsiDiskDevice
import blivet.arch

from pyanaconda import nm
from pyanaconda import constants
from pyanaconda.flags import flags, can_touch_runtime_system
from pyanaconda.i18n import _

from gi.repository import NetworkManager

import logging
log = logging.getLogger("anaconda")

sysconfigDir = "/etc/sysconfig"
netscriptsDir = "%s/network-scripts" % (sysconfigDir)
networkConfFile = "%s/network" % (sysconfigDir)
hostnameFile = "/etc/hostname"
ipv6ConfFile = "/etc/sysctl.d/anaconda.conf"
ifcfgLogFile = "/tmp/ifcfg.log"
DEFAULT_HOSTNAME = "localhost.localdomain"

# part of a valid hostname between two periods (cannot start nor end with '-')
# for more info about '(?!-)' and '(?<!-)' see 're' module documentation
HOSTNAME_PART_RE = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)

ifcfglog = None

network_connected = None
network_connected_condition = threading.Condition()

def setup_ifcfg_log():
    # Setup special logging for ifcfg NM interface
    from pyanaconda import anaconda_log
    global ifcfglog
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

def check_ip_address(address, version=None):
    try:
        _ip, ver = IPy.parseAddress(address)
    except ValueError:
        return False
    if version and version == ver:
        return True

def sanityCheckHostname(hostname):
    """
    Check if the given string is (syntactically) a valid hostname.

    :param hostname: a string to check
    :returns: a pair containing boolean value (valid or invalid) and
              an error message (if applicable)
    :rtype: (bool, str)

    """

    if not hostname:
        return (False, _("Hostname cannot be None or an empty string."))

    if len(hostname) > 255:
        return (False, _("Hostname must be 255 or fewer characters in length."))

    validStart = string.ascii_letters + string.digits

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
    for devname in nm.nm_activated_devices():
        try:
            ips += (nm.nm_device_ip_addresses(devname, version=4) +
                    nm.nm_device_ip_addresses(devname, version=6))
        except (dbus.DBusException, ValueError) as e:
            log.warning("Got an exception trying to get the ip addr "
                        "of %s: %s", devname, e)
    return ips

# Return the first real non-local IP we find
def getFirstRealIP():
    for ip in getIPs():
        if ip not in ("127.0.0.1", "::1"):
            return ip
    return None

def netmask2prefix(netmask):
    prefix = 0

    while prefix < 33:
        if (prefix2netmask(prefix) == netmask):
            return prefix

        prefix += 1

    return prefix

def prefix2netmask(prefix):
    """ Convert prefix (CIDR bits) to netmask """
    _bytes = []
    for _i in range(4):
        if prefix >= 8:
            _bytes.append(255)
            prefix -= 8
        else:
            _bytes.append(256 - 2**(8-prefix))
            prefix = 0
    netmask = ".".join(str(byte) for byte in _bytes)
    return netmask

# Try to determine what the hostname should be for this system
def getHostname():

    hn = None

    # First address (we prefer ipv4) of last device (as it used to be) wins
    for dev in nm.nm_activated_devices():
        addrs = (nm.nm_device_ip_addresses(dev, version=4) +
                 nm.nm_device_ip_addresses(dev, version=6))
        for ipaddr in addrs:
            try:
                hinfo = socket.gethostbyaddr(ipaddr)
            except socket.herror as e:
                log.debug("Exception caught trying to get host name of %s: %s", ipaddr, e)
            else:
                if len(hinfo) == 3:
                    hn = hinfo[0]
                    break

    if not hn or hn in ('(none)', 'localhost', 'localhost.localdomain'):
        hn = socket.gethostname()

    if not hn or hn in ('(none)', 'localhost', 'localhost.localdomain'):
        hn = DEFAULT_HOSTNAME

    return hn

def logIfcfgFile(path, message=""):
    content = ""
    if os.access(path, os.R_OK):
        f = open(path, 'r')
        content = f.read()
        f.close()
    else:
        content = "file not found"
    ifcfglog.debug("%s%s:\n%s", message, path, content)

def _ifcfg_files(directory):
    rv = []
    for name in os.listdir(directory):
        if name.startswith("ifcfg-"):
            if name == "ifcfg-lo":
                continue
            rv.append(os.path.join(directory,name))
    return rv

def logIfcfgFiles(message=""):
    ifcfglog.debug("content of files (%s):", message)
    for path in _ifcfg_files(netscriptsDir):
        with open(path, "r") as f:
            content = f.read()
        ifcfglog.debug("%s:\n%s", path, content)

class IfcfgFile(SimpleConfigFile):
    def __init__(self, filename):
        SimpleConfigFile.__init__(self, always_quote=True, filename=filename)
        self._dirty = False

    def read(self, filename=None):
        self.reset()
        ifcfglog.debug("IfcfFile.read %s", self.filename)
        SimpleConfigFile.read(self)
        self._dirty = False

    def write(self, filename=None, use_tmp=False):
        if self._dirty or filename:
            # ifcfg-rh is using inotify IN_CLOSE_WRITE event so we don't use
            # temporary file for new configuration
            ifcfglog.debug("IfcfgFile.write %s:\n%s", self.filename, self.__str__())
            SimpleConfigFile.write(self, filename, use_tmp=use_tmp)
            self._dirty = False

    def set(self, *args):
        for (key, data) in args:
            if self.get(key) != data:
                break
        else:
            return
        ifcfglog.debug("IfcfgFile.set %s: %s", self.filename, args)
        SimpleConfigFile.set(self, *args)
        self._dirty = True

    def unset(self, *args):
        for key in args:
            if self.get(key):
                self._dirty = True
                break
        else:
            return
        ifcfglog.debug("IfcfgFile.unset %s: %s", self.filename, args)
        SimpleConfigFile.unset(self, *args)

def dumpMissingDefaultIfcfgs():
    """
    Dump missing default ifcfg file for wired devices.
    For default auto connections created by NM upon start - which happens
    in case of missing ifcfg file - rename the connection using device name
    and dump its ifcfg file. (For server, default auto connections will
    be turned off in NetworkManager.conf.)
    The connection id (and consequently ifcfg file) is set to device name.
    Returns True if any ifcfg file was dumped.

    """
    rv = False

    for devname in nm.nm_devices():
        # for each ethernet device
        # FIXME add more types (infiniband, bond...?)
        if not nm.nm_device_type_is_ethernet(devname):
            continue

        # check that device has connection without ifcfg file
        try:
            con_uuid = nm.nm_device_setting_value(devname, "connection", "uuid")
        except nm.DeviceSettingsNotFoundError:
            continue
        if find_ifcfg_file([("UUID", con_uuid)], root_path=""):
            continue

        try:
            nm.nm_update_settings_of_device(devname, [['connection', 'id', devname, None]])
            log.debug("network: dumping ifcfg file for default autoconnection on %s", devname)
            nm.nm_update_settings_of_device(devname, [['connection', 'autoconnect', False, None]])
            log.debug("network: setting autoconnect of %s to False" , devname)
        except nm.DeviceSettingsNotFoundError:
            log.debug("network: no ifcfg file for %s", devname)
        rv = True

    return rv

# get a kernel cmdline string for dracut needed for access to storage host
def dracutSetupArgs(networkStorageDevice):

    if networkStorageDevice.nic == "default" or ":" in networkStorageDevice.nic:
        nic = ifaceForHostIP(networkStorageDevice.host_address)
        if not nic:
            return ""
    else:
        nic = networkStorageDevice.nic

    if nic not in nm.nm_devices():
        log.error('Unknown network interface: %s', nic)
        return ""

    ifcfg_path = find_ifcfg_file_of_device(nic)
    if not ifcfg_path:
        log.error("dracutSetupArgs: can't find ifcfg file for %s", nic)
        return ""
    ifcfg = IfcfgFile(ifcfg_path)
    ifcfg.read()
    return dracutBootArguments(nic,
                               ifcfg,
                               networkStorageDevice.host_address,
                               getHostname())

def dracutBootArguments(devname, ifcfg, storage_ipaddr, hostname=None):

    netargs = set()

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
            if iutil.lowerASCII(ifcfg.get('bootproto')) == 'dhcp':
                netargs.add("ip=%s:dhcp" % devname)
            else:
                if ifcfg.get('GATEWAY'):
                    gateway = ifcfg.get('GATEWAY')
                else:
                    gateway = ""

                netmask = ifcfg.get('netmask')
                prefix  = ifcfg.get('prefix')
                if not netmask and prefix:
                    netmask = prefix2netmask(int(prefix))

                netargs.add("ip=%s::%s:%s:%s:%s:none" % (ifcfg.get('ipaddr'),
                           gateway, netmask, hostname, devname))

        hwaddr = ifcfg.get("HWADDR")
        if hwaddr:
            netargs.add("ifname=%s:%s" % (devname, hwaddr.lower()))

    nettype = ifcfg.get("NETTYPE")
    subchannels = ifcfg.get("SUBCHANNELS")
    if blivet.arch.isS390() and nettype and subchannels:
        znet = "rd.znet=%s,%s" % (nettype, subchannels)
        options = ifcfg.get("OPTIONS").strip("'\"")
        if options:
            options = filter(lambda x: x != '', options.split(' '))
            znet += ",%s" % (','.join(options))
        netargs.add(znet)

    return netargs

def update_settings_with_ksdata(devname, networkdata):

    new_values = []

    # ipv4 settings
    method4 = "auto"
    if networkdata.bootProto == "static":
        method4 = "manual"
    new_values.append(["ipv4", "method", method4, "s"])

    if method4 == "manual":
        addr4 = nm.nm_ipv4_to_dbus_int(networkdata.ip)
        gateway4 = nm.nm_ipv4_to_dbus_int(networkdata.gateway)
        prefix4 = netmask2prefix(networkdata.netmask)
        new_values.append(["ipv4", "addresses", [[addr4, prefix4, gateway4]], "aau"])

    # ipv6 settings
    if networkdata.noipv6:
        method6 = "ignore"
    else:
        if networkdata.ipv6 == "auto":
            method6 = "auto"
        elif networkdata.ipv6 == "dhcp":
            method6 = "dhcp"
        else:
            method6 = "manual"
    new_values.append(["ipv6", "method", method6, "s"])

    if method6 == "manual":
        addr6, _slash, prefix6 = networkdata.ipv6.partition("/")
        if prefix6:
            prefix6 = int(prefix6)
        else:
            prefix6 = 64
        addr6 = nm.nm_ipv6_to_dbus_ay(addr6)
        if networkdata.ipv6gateway:
            gateway6 = nm.nm_ipv6_to_dbus_ay(networkdata.ipv6gateway)
        else:
            gateway6 = [0] * 16
        new_values.append(["ipv6", "addresses", [(addr6, prefix6, gateway6)], "a(ayuay)"])

    # nameservers
    nss4 = []
    nss6 = []
    if networkdata.nameserver:
        for ns in networkdata.nameserver.split(","):
            if ":" in ns:
                nss6.append(nm.nm_ipv6_to_dbus_ay(ns))
            else:
                nss4.append(nm.nm_ipv4_to_dbus_int(ns))
    new_values.append(["ipv4", "dns", nss4, "au"])
    new_values.append(["ipv6", "dns", nss6, "aay"])

    # onboot
    new_values.append(['connection', 'autoconnect', networkdata.onboot, None])

    nm.nm_update_settings_of_device(devname, new_values)

def ksdata_from_ifcfg(devname):

    if nm.nm_device_is_slave(devname):
        return None

    ifcfg_path = None

    # Find ifcfg file for the device.
    # If the device is active, use uuid of its active connection.
    uuid = nm.nm_device_active_con_uuid(devname)
    if uuid:
        ifcfg_path = find_ifcfg_file([("UUID", uuid)])
    else:
        # If not, look it up by other values depending on its type
        if nm.nm_device_type_is_ethernet(devname):
            ifcfg_path = find_ifcfg_file_of_device(devname)
        elif nm.nm_device_type_is_wifi(devname):
            ssid = nm.nm_device_active_ssid(devname)
            if ssid:
                ifcfg_path = find_ifcfg_file([("ESSID", ssid)])
        elif nm.nm_device_type_is_bond(devname):
            ifcfg_path = find_ifcfg_file([("DEVICE", devname)])
        elif nm.nm_device_type_is_vlan(devname):
            ifcfg_path = find_ifcfg_file([("DEVICE", devname)])

    if not ifcfg_path:
        return None

    ifcfg = IfcfgFile(ifcfg_path)
    ifcfg.read()
    nd = ifcfg_to_ksdata(ifcfg, devname)

    if not nd:
        return None

    if nm.nm_device_type_is_ethernet(devname):
        nd.device = devname
    elif nm.nm_device_type_is_wifi(devname):
        nm.device = ""
    elif nm.nm_device_type_is_bond(devname):
        nd.device = devname
    elif nm.nm_device_type_is_vlan(devname):
        nd.device = devname.split(".")[0]

    return nd

def ifcfg_to_ksdata(ifcfg, devname):

    from pyanaconda.kickstart import AnacondaKSHandler
    handler = AnacondaKSHandler()
    kwargs = {}

    # no network command for bond slaves
    if ifcfg.get("MASTER"):
        return None

    # ipv4 and ipv6
    if ifcfg.get("ONBOOT") and ifcfg.get("ONBOOT" ) == "no":
        kwargs["onboot"] = False
    if ifcfg.get('MTU') and ifcfg.get('MTU') != "0":
        kwargs["mtu"] = ifcfg.get('MTU')
    # ipv4
    if not ifcfg.get('BOOTPROTO'):
        kwargs["noipv4"] = True
    else:
        if iutil.lowerASCII(ifcfg.get('BOOTPROTO')) == 'dhcp':
            kwargs["bootProto"] = "dhcp"
            if ifcfg.get('DHCPCLASS'):
                kwargs["dhcpclass"] = ifcfg.get('DHCPCLASS')
        elif ifcfg.get('IPADDR'):
            kwargs["bootProto"] = "static"
            kwargs["ip"] = ifcfg.get('IPADDR')
            netmask = ifcfg.get('NETMASK')
            prefix  = ifcfg.get('PREFIX')
            if not netmask and prefix:
                netmask = prefix2netmask(int(prefix))
            if netmask:
                kwargs["netmask"] = netmask
            # note that --gateway is common for ipv4 and ipv6
            if ifcfg.get('GATEWAY'):
                kwargs["gateway"] = ifcfg.get('GATEWAY')
        elif ifcfg.get('IPADDR0'):
            kwargs["bootProto"] = "static"
            kwargs["ip"] = ifcfg.get('IPADDR0')
            prefix  = ifcfg.get('PREFIX0')
            if prefix:
                netmask = prefix2netmask(int(prefix))
                kwargs["netmask"] = netmask
            # note that --gateway is common for ipv4 and ipv6
            if ifcfg.get('GATEWAY0'):
                kwargs["gateway"] = ifcfg.get('GATEWAY0')


    # ipv6
    if (not ifcfg.get('IPV6INIT') or
        ifcfg.get('IPV6INIT') == "no"):
        kwargs["noipv6"] = True
    else:
        if ifcfg.get('IPV6_AUTOCONF') in ("yes", ""):
            kwargs["ipv6"] = "auto"
        else:
            if ifcfg.get('IPV6ADDR'):
                kwargs["ipv6"] = ifcfg.get('IPV6ADDR')
                if ifcfg.get('IPV6_DEFAULTGW') \
                   and ifcfg.get('IPV6_DEFAULTGW') != "::":
                    kwargs["ipv6gateway"] = ifcfg.get('IPV6_DEFAULTGW')
            if ifcfg.get('DHCPV6C') == "yes":
                kwargs["ipv6"] = "dhcp"

    # ipv4 and ipv6
    dnsline = ''
    for key in ifcfg.info.keys():
        if iutil.upperASCII(key).startswith('DNS'):
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

    # bonding
    # FIXME: dracut has only BOND_OPTS
    if ifcfg.get("BONDING_MASTER") == "yes" or ifcfg.get("TYPE") == "Bond":
        slaves = get_bond_slaves_from_ifcfgs([devname, ifcfg.get("UUID")])
        if slaves:
            kwargs["bondslaves"] = ",".join(slaves)
        bondopts = ifcfg.get("BONDING_OPTS")
        if bondopts:
            sep = ","
            if sep in bondopts:
                sep = ";"
            kwargs["bondopts"] = sep.join(bondopts.split())

    # vlan
    if ifcfg.get("VLAN") == "yes" or ifcfg.get("TYPE") == "Vlan":
        kwargs["device"] = ifcfg.get("PHYSDEV")
        kwargs["vlanid"] = ifcfg.get("VLAN_ID")

    # pylint: disable-msg=E1101
    return handler.NetworkData(**kwargs)

def hostname_ksdata(hostname):
    from pyanaconda.kickstart import AnacondaKSHandler
    handler = AnacondaKSHandler()
    # pylint: disable-msg=E1101
    return handler.NetworkData(hostname=hostname, bootProto="")

def find_ifcfg_file_of_device(devname, root_path=""):
    ifcfg_path = None

    try:
        hwaddr = nm.nm_device_hwaddress(devname)
    except nm.PropertyNotFoundError:
        hwaddr = None
    if hwaddr:
        hwaddr_check = lambda mac: mac.upper() == hwaddr.upper()
        nonempty = lambda x: x
        # slave configration created in GUI takes precedence
        ifcfg_path = find_ifcfg_file([("HWADDR", hwaddr_check),
                                      ("MASTER", nonempty)],
                                     root_path)
        if not ifcfg_path:
            ifcfg_path = find_ifcfg_file([("HWADDR", hwaddr_check)], root_path)
    if not ifcfg_path:
        ifcfg_path = find_ifcfg_file([("DEVICE", devname)], root_path)
    return ifcfg_path

def find_ifcfg_file(values, root_path=""):
    for filepath in _ifcfg_files(os.path.normpath(root_path+netscriptsDir)):
        ifcfg = IfcfgFile(filepath)
        ifcfg.read()
        for key, value in values:
            if callable(value):
                if not value(ifcfg.get(key)):
                    break
            else:
                if ifcfg.get(key) != value:
                    break
        else:
            return filepath
    return None

def get_bond_slaves_from_ifcfgs(master_specs):
    """List of slave device names of master specified by master_specs.

       master_specs is a list containing device name of master (dracut)
       and/or master's connection uuid
    """
    slaves = []

    for filepath in _ifcfg_files(netscriptsDir):
        ifcfg = IfcfgFile(filepath)
        ifcfg.read()
        master = ifcfg.get("MASTER")
        if master in master_specs:
            device = ifcfg.get("DEVICE")
            if device:
                slaves.append(device)
            else:
                hwaddr = ifcfg.get("HWADDR")
                for devname in nm.nm_devices():
                    try:
                        h = nm.nm_device_property(devname, "PermHwAddress")
                    except nm.PropertyNotFoundError:
                        log.debug("can't get PermHwAddress of devname %s", devname)
                        continue
                    if h.upper() == hwaddr.upper():
                        slaves.append(devname)
                        break
    return slaves

def ifaceForHostIP(host):
    route = iutil.execWithCapture("ip", [ "route", "get", "to", host ])
    if not route:
        log.error("Could not get interface for route to %s", host)
        return ""

    routeInfo = route.split()
    if routeInfo[0] != host or len(routeInfo) < 5 or \
       "dev" not in routeInfo or routeInfo.index("dev") > 3:
        log.error('Unexpected "ip route get to %s" reply: %s', host, routeInfo)
        return ""

    return routeInfo[routeInfo.index("dev") + 1]

def copyFileToPath(fileName, destPath='', overwrite=False):
    if not os.path.isfile(fileName):
        return False
    destfile = os.path.join(destPath, fileName.lstrip('/'))
    if (os.path.isfile(destfile) and not overwrite):
        return False
    if not os.path.isdir(os.path.dirname(destfile)):
        iutil.mkdirChain(os.path.dirname(destfile))
    shutil.copy(fileName, destfile)
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
    for devName in nm.nm_devices():
        dhclientfile = os.path.join("/etc/dhcp/dhclient-%s.conf" % devName)
        copyFileToPath(dhclientfile, destPath)

def get_ksdevice_name(ksspec=""):

    if not ksspec:
        ksspec = flags.cmdline.get('ksdevice', "")
    ksdevice = ksspec

    bootif_mac = ''
    if ksdevice == 'bootif' and "BOOTIF" in flags.cmdline:
        bootif_mac = flags.cmdline["BOOTIF"][3:].replace("-", ":").upper()
    for dev in sorted(nm.nm_devices()):
        # "eth0"
        if ksdevice == dev:
            break
        # "link"
        elif ksdevice == 'link':
            try:
                link_up = nm.nm_device_carrier(dev)
            except ValueError as e:
                log.debug("get_ksdevice_name: %s", e)
                continue
            if link_up:
                ksdevice = dev
                break
        # "XX:XX:XX:XX:XX:XX" (mac address)
        elif ':' in ksdevice:
            try:
                hwaddr = nm.nm_device_hwaddress(dev)
            except ValueError as e:
                log.debug("get_ksdevice_name: %s", e)
                continue
            if ksdevice.lower() == hwaddr.lower():
                ksdevice = dev
                break
        # "bootif" and BOOTIF==XX:XX:XX:XX:XX:XX
        elif ksdevice == 'bootif':
            try:
                hwaddr = nm.nm_device_hwaddress(dev)
            except ValueError as e:
                log.debug("get_ksdevice_name: %s", e)
                continue
            if bootif_mac.lower() == hwaddr.lower():
                ksdevice = dev
                break

    return ksdevice

def set_hostname(hn):
    if can_touch_runtime_system("set hostname", touch_live=True):
        log.info("setting installation environment hostname to %s", hn)
        iutil.execWithRedirect("hostnamectl", ["set-hostname", hn])

def write_hostname(rootpath, ksdata, overwrite=False):
    cfgfile = os.path.normpath(rootpath + hostnameFile)
    if (os.path.isfile(cfgfile) and not overwrite):
        return False

    f = open(cfgfile, "w")
    f.write("%s\n" % ksdata.network.hostname)
    f.close()

    return True

def disableIPV6(rootpath):
    cfgfile = os.path.normpath(rootpath + ipv6ConfFile)
    if ('noipv6' in flags.cmdline
        and all(nm.nm_device_setting_value(dev, "ipv6", "method") == "ignore"
                for dev in nm.nm_devices() if nm.nm_device_type_is_ethernet(dev))):
        log.info('Disabling ipv6 on target system')
        with open(cfgfile, "a") as f:
            f.write("# Anaconda disabling ipv6 (noipv6 option)\n")
            f.write("net.ipv6.conf.all.disable_ipv6=1\n")
            f.write("net.ipv6.conf.default.disable_ipv6=1\n")

def disableNMForStorageDevices(rootpath, storage):
    for devname in nm.nm_devices():
        if (usedByFCoE(devname, storage) or
            usedByRootOnISCSI(devname, storage)):
            ifcfg_path = find_ifcfg_file_of_device(devname, root_path=rootpath)
            if not ifcfg_path:
                log.warning("disableNMForStorageDevices: ifcfg file for %s not found",
                            devname)
                continue
            ifcfg = IfcfgFile(ifcfg_path)
            ifcfg.read()
            ifcfg.set(('NM_CONTROLLED', 'no'))
            ifcfg.write()
            log.info("network device %s used by storage will not be "
                     "controlled by NM", devname)

# sets ONBOOT=yes (and its mirror value in ksdata) for devices used by FCoE
def autostartFCoEDevices(rootpath, storage, ksdata):
    for devname in nm.nm_devices():
        if usedByFCoE(devname, storage):
            ifcfg_path = find_ifcfg_file_of_device(devname, root_path=rootpath)
            if not ifcfg_path:
                log.warning("autoconnectFCoEDevices: ifcfg file for %s not found", devname)
                continue

            ifcfg = IfcfgFile(ifcfg_path)
            ifcfg.read()
            ifcfg.set(('ONBOOT', 'yes'))
            ifcfg.write()
            log.debug("setting ONBOOT=yes for network device %s used by fcoe", devname)
            for nd in ksdata.network.network:
                if nd.device == devname:
                    nd.onboot = True
                    break

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

def write_sysconfig_network(rootpath, overwrite=False):

    cfgfile = os.path.normpath(rootpath + networkConfFile)
    if (os.path.isfile(cfgfile) and not overwrite):
        return False

    with open(cfgfile, "w") as f:
        f.write("# Created by anaconda\n")
    return True

def write_network_config(storage, ksdata, instClass, rootpath):
    write_hostname(rootpath, ksdata, overwrite=flags.livecdInstall)
    set_hostname(ksdata.network.hostname)
    write_sysconfig_network(rootpath, overwrite=flags.livecdInstall)
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

def update_hostname_data(ksdata, hostname):
    log.debug("updating hostname %s", hostname)
    hostname_found = False
    for nd in ksdata.network.network:
        if nd.hostname:
            nd.hostname = hostname
            hostname_found = True
    if not hostname_found:
        nd = hostname_ksdata(hostname)
        ksdata.network.network.append(nd)

def get_device_name(devspec):

    devices = nm.nm_devices()
    devname = None

    if not devspec:
        if "ksdevice" in flags.cmdline:
            msg = "ksdevice boot parameter"
            devname = get_ksdevice_name(flags.cmdline["ksdevice"])
        elif nm.nm_is_connected():
            # device activated in stage 1 by network kickstart command
            msg = "first active device"
            try:
                devname = nm.nm_activated_devices()[0]
            except IndexError:
                log.debug("get_device_name: NM is connected but no activated devices found")
        else:
            msg = "first device found"
            devname = min(devices)
        log.info("unspecified network --device in kickstart, using %s (%s)",
                 devname, msg)
    else:
        if iutil.lowerASCII(devspec) == "ibft":
            devname = ""
        if iutil.lowerASCII(devspec) == "link":
            for dev in sorted(devices):
                try:
                    link_up = nm.nm_device_carrier(dev)
                except ValueError as e:
                    log.debug("get_device_name: %s", e)
                    continue
                if link_up:
                    devname = dev
                    break
            else:
                log.error("Kickstart: No network device with link found")
        elif iutil.lowerASCII(devspec) == "bootif":
            if "BOOTIF" in flags.cmdline:
                # MAC address like 01-aa-bb-cc-dd-ee-ff
                devname = flags.cmdline["BOOTIF"][3:]
                devname = devname.replace("-",":")
            else:
                log.error("Using --device=bootif without BOOTIF= boot option supplied")
        else: devname = devspec

    if devname and devname not in devices:
        for d in devices:
            try:
                hwaddr = nm.nm_device_hwaddress(d)
            except ValueError as e:
                log.debug("get_device_name: %s", e)
                continue
            if hwaddr.lower() == devname.lower():
                devname = d
                break
        else:
            return ""

    return devname

def setOnboot(ksdata):
    for network_data in ksdata.network.network:

        devname = get_device_name(network_data.device)
        if not devname:
            log.error("Kickstart: The provided network interface %s does not exist", network_data.device)
            continue

        try:
            nm.nm_update_settings_of_device(devname, [['connection', 'autoconnect', network_data.onboot, None]])
            ifcfglog.debug("setting autoconnect (ONBOOT) of %s to %s" , devname, network_data.onboot)
        except nm.DeviceSettingsNotFoundError as e:
            log.debug("setOnboot: %s", e)

def networkInitialize(ksdata):

    log.debug("network: devices found %s", nm.nm_devices())
    logIfcfgFiles("network initialization")

    if not flags.imageInstall:
        if dumpMissingDefaultIfcfgs():
            logIfcfgFiles("ifcfgs created")

    # For kickstart network --activate option we set ONBOOT=yes
    # in dracut to get devices activated by NM. The real network --onboot
    # value is set here.
    setOnboot(ksdata)

    if ksdata.network.hostname is None:
        hostname = getHostname()
        update_hostname_data(ksdata, hostname)

def _get_ntp_servers_from_dhcp(ksdata):
    """Check if some NTP servers were returned from DHCP and set them
    to ksdata (if not NTP servers were specified in the kickstart)"""
    ntp_servers = nm.nm_ntp_servers_from_dhcp()
    log.info("got %d NTP servers from DHCP", len(ntp_servers))
    hostnames = []
    for server_address in ntp_servers:
        try:
            hostname = socket.gethostbyaddr(server_address)[0]
        except socket.error:
            # getting hostname failed, just use the address returned from DHCP
            log.debug("getting NTP server hostname failed for address: %s",
                      server_address)
            hostname = server_address
        hostnames.append(hostname)
    # check if some NTP servers were specified from kickstart
    if not ksdata.timezone.ntpservers:
        # no NTP servers were specified, add those from DHCP
        ksdata.timezone.ntpservers = hostnames

def _wait_for_connecting_NM():
    """If NM is in connecting state, wait for connection.
    Return value: NM has got connection."""

    if nm.nm_is_connected:
        return True

    if nm.nm_is_connecting():
        log.debug("waiting for connecting NM (dhcp?)")
    else:
        return False

    i = 0
    while nm.nm_is_connecting() and i < constants.NETWORK_CONNECTION_TIMEOUT:
        i += constants.NETWORK_CONNECTED_CHECK_INTERVAL
        time.sleep(constants.NETWORK_CONNECTED_CHECK_INTERVAL)
        if nm.nm_is_connected():
            log.debug("connected, waited %d seconds", i)
            return True

    log.debug("not connected, waited %d of %d secs", i, constants.NETWORK_CONNECTION_TIMEOUT)
    return False

def wait_for_network_devices(devices, timeout=constants.NETWORK_CONNECTION_TIMEOUT):
    devices = set(devices)
    i = 0
    log.debug("waiting for connection of devices %s for iscsi", devices)
    while  i < timeout:
        if not devices - set(nm.nm_activated_devices()):
            return True
        i += 1
        time.sleep(1)
    return False

def wait_for_connecting_NM_thread(ksdata):
    """This function is called from a thread which is run at startup
    to wait for Network Manager to connect."""
    # connection (e.g. auto default dhcp) is activated by NM service
    connected = _wait_for_connecting_NM()
    if connected:
        if ksdata.network.hostname == DEFAULT_HOSTNAME:
            hostname = getHostname()
            update_hostname_data(ksdata, hostname)
        _get_ntp_servers_from_dhcp(ksdata)
    with network_connected_condition:
        global network_connected
        network_connected = connected
        network_connected_condition.notify_all()


def wait_for_connectivity(timeout=constants.NETWORK_CONNECTION_TIMEOUT):
    """Wait for network connectivty to become available

    :param timeout: how long to wait in seconds
    :type param: integer of float"""
    connected = False
    network_connected_condition.acquire()
    # if network_connected is None, network connectivity check
    # has not yet been run or is in progress, so wait for it to finish
    if network_connected is None:
        # wait releases the lock and reacquires it once the thread is unblocked
        network_connected_condition.wait(timeout=timeout)
    connected = network_connected
    # after wait() unblocks, we get the lock back,
    # so we need to release it
    network_connected_condition.release()
    return connected

def status_message():
    """ A short string describing which devices are connected. """

    msg = _("Unknown")

    state = nm.nm_state()
    if state == NetworkManager.State.CONNECTING:
        msg = _("Connecting...")
    elif state == NetworkManager.State.DISCONNECTING:
        msg = _("Disconnecting...")
    else:
        active_devs = nm.nm_activated_devices()
        if active_devs:

            slaves = {}
            ssids = {}

            # first find slaves and wireless aps
            for devname in active_devs:
                slaves[devname] = nm.nm_device_slaves(devname) or []
                if nm.nm_device_type_is_wifi(devname):
                    ssids[devname] = nm.nm_device_active_ssid(devname) or ""

            all_slaves = set(itertools.chain.from_iterable(slaves.values()))
            nonslaves = [dev for dev in active_devs if dev not in all_slaves]

            if len(nonslaves) == 1:
                devname = nonslaves[0]
                if nm.nm_device_type_is_ethernet(devname):
                    msg = _("Wired (%(interface_name)s) connected") \
                          % {"interface_name": devname}
                elif nm.nm_device_type_is_wifi(devname):
                    msg = _("Wireless connected to %(access_point)s") \
                          % {"access_point" : ssids[devname]}
                elif nm.nm_device_type_is_bond(devname):
                    msg = _("Bond %(interface_name)s (%(list_of_slaves)s) connected") \
                          % {"interface_name": devname, \
                             "list_of_slaves": ",".join(slaves[devname])}
                elif nm.nm_device_type_is_vlan(devname):
                    parent = nm.nm_device_setting_value(devname, "vlan", "parent")
                    vlanid = nm.nm_device_setting_value(devname, "vlan", "id")
                    msg = _("Vlan %(interface_name)s (%(parent_device)s, ID %(vlanid)s) connected") \
                          % {"interface_name": devname, "parent_device": parent, "vlanid": vlanid}
            elif len(nonslaves) > 1:
                devlist = []
                for devname in nonslaves:
                    if nm.nm_device_type_is_ethernet(devname):
                        devlist.append("%s" % devname)
                    elif nm.nm_device_type_is_wifi(devname):
                        devlist.append("%s" % ssids[devname])
                    elif nm.nm_device_type_is_bond(devname):
                        devlist.append("%s (%s)" % (devname, ",".join(slaves[devname])))
                    elif nm.nm_device_type_is_vlan(devname):
                        devlist.append("%s" % devname)
                msg = _("Connected: %(list_of_interface_names)s") \
                      % {"list_of_interface_names": ", ".join(devlist)}
        else:
            msg = _("Not connected")

    if not nm.nm_devices():
        msg = _("No network devices available")

    return msg
