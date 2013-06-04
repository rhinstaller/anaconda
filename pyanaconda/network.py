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
import iutil
import socket
import os
import time
import tempfile
import simpleconfig
import re
from flags import flags
from simpleconfig import IfcfgFile
import urlgrabber.grabber
from blivet.devices import FcoeDiskDevice, iScsiDiskDevice
import blivet.arch

from pyanaconda import nm
from pyanaconda.constants import NETWORK_CONNECTION_TIMEOUT
from pyanaconda.i18n import _

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
HOSTNAME_PART_RE = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)

ifcfglog = None
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
    for devname in nm.nm_activated_devices():
        try:
            ips += (nm.nm_device_ip_addresses(devname, version=4) +
                    nm.nm_device_ip_addresses(devname, version=6))
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

def netmask2prefix(netmask):
    prefix = 0

    while prefix < 33:
        if (prefix2netmask(prefix) == netmask):
            return prefix

        prefix += 1

    return prefix

def prefix2netmask(prefix):
    """ Convert prefix (CIDR bits) to netmask """
    bytes = []
    for i in range(4):
        if prefix >= 8:
            bytes.append(255)
            prefix -= 8
        else:
            bytes.append(256 - 2**(8-prefix))
            prefix = 0
    netmask = ".".join(str(byte) for byte in bytes)
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
            except Exception as e:
                log.debug("Exception caught trying to get host name of %s: %s" %
                          (ipaddr, e))
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
    ifcfglog.debug("%s%s:\n%s" % (message, path, content))

def _ifcfg_files(directory):
    rv = []
    for name in os.listdir(directory):
        if name.startswith("ifcfg-"):
            if name == "ifcfg-lo":
                continue
            rv.append(name)
    return rv

def logIfcfgFiles(message=""):
    ifcfglog.debug("content of files (%s):" % message)
    for name in _ifcfg_files(netscriptsDir):
        path = os.path.join(netscriptsDir, name)
        with open(path, "r") as f:
            content = f.read()
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
        if blivet.arch.isS390() and ("HWADDR" in keys):
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
        s = " ".join("%s=%s" % key_val for key_val in args)
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

    def fileContent(self):
        if not os.path.exists(self.path):
            return ""
        f = open(self.path, 'r')
        content = f.read()
        f.close()
        return content


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

        # if there is no ifcfg file for the device
        device_cfg = NetworkDevice(netscriptsDir, devname)
        if os.access(device_cfg.path, os.R_OK):
            continue

        try:
            nm.nm_update_settings_of_device(devname, 'connection', 'id', devname)
            log.debug("network: dumping ifcfg file for default autoconnection on %s" % devname)
            nm.nm_update_settings_of_device(devname, 'connection', 'autoconnect', False)
            log.debug("network: setting autoconnect of %s to False" % devname)
        except nm.DeviceSettingsNotFoundError as e:
            log.debug("network: no ifcfg file for %s" % devname)
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

def kickstartNetworkData(ifcfg=None, hostname=None):

    from pyanaconda.kickstart import AnacondaKSHandler
    handler = AnacondaKSHandler()
    kwargs = {}

    if not ifcfg and hostname:
        return handler.NetworkData(hostname=hostname, bootProto="")

    # no network command for bond slaves
    if ifcfg.get("MASTER"):
        return None

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
                if ifcfg.get('IPV6_DEFAULTGW'):
                    kwargs["ipv6gateway"] = ifcfg.get('IPV6_DEFAULTGW')
            if ifcfg.get('DHCPV6C') == "yes":
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
            hostname != DEFAULT_HOSTNAME):
            kwargs["hostname"] = hostname

    # bonding
    # FIXME: dracut has only BOND_OPTS
    if ifcfg.get("BONDING_MASTER") == "yes" or ifcfg.get("TYPE") == "Bond":
        slaves = get_bond_slaves_from_ifcfgs([ifcfg.iface, ifcfg.get("UUID")])
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

    return handler.NetworkData(**kwargs)

def get_bond_master_ifcfg_name(devname):
    """Name of ifcfg file of bond device devname"""

    for filename in _ifcfg_files(netscriptsDir):
        ifcfg = NetworkDevice(netscriptsDir, filename[6:])
        ifcfg.loadIfcfgFile()
        # FIXME: dracut has only BOND_OPTS
        if ifcfg.get("BONDING_MASTER") == "yes" or ifcfg.get("TYPE") == "Bond":
            if ifcfg.get("DEVICE") == devname:
                return filename

def get_vlan_ifcfg_name(devname):
    """Name of ifcfg file of vlan device devname"""

    for filename in _ifcfg_files(netscriptsDir):
        ifcfg = NetworkDevice(netscriptsDir, filename[6:])
        ifcfg.loadIfcfgFile()
        if ifcfg.get("VLAN") == "yes" or ifcfg.get("TYPE") == "Vlan":
            if ifcfg.get("DEVICE") == devname:
                return filename

def get_bond_slaves_from_ifcfgs(master_specs):
    """List of slave device names of master specified by master_specs.

       master_specs is a list containing device name of master (dracut)
       and/or master's connection uuid
    """
    slaves = []

    for filename in _ifcfg_files(netscriptsDir):
        ifcfg = NetworkDevice(netscriptsDir, filename[6:])
        ifcfg.loadIfcfgFile()
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
                        log.debug("can't get PermHwAddress of devname %s" % devname)
                        continue
                    if h.upper() == hwaddr.upper():
                        slaves.append(devname)
                        break
    return slaves

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
    for devName in nm.nm_devices():
        dhclientfile = os.path.join("/etc/dhcp/dhclient-%s.conf" % devName)
        copyFileToPath(dhclientfile, destPath)

def get_ksdevice_name(ksspec=""):

    if not ksspec:
        ksspec = flags.cmdline.get('ksdevice', "")
    ksdevice = ksspec

    bootif_mac = None
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
                log.debug("get_ksdevice_name: %s" % e)
                continue
            if link_up:
                ksdevice = dev
                break
        # "XX:XX:XX:XX:XX:XX" (mac address)
        elif ':' in ksdevice:
            try:
                hwaddr = nm.nm_device_hwaddress(dev)
            except ValueError as e:
                log.debug("get_ksdevice_name: %s" % e)
                continue
            if ksdevice.lower() == hwaddr.lower():
                ksdevice = dev
                break
        # "bootif" and BOOTIF==XX:XX:XX:XX:XX:XX
        elif ksdevice == 'bootif':
            try:
                hwaddr = nm.nm_device_hwaddress(dev)
            except ValueError as e:
                log.debug("get_ksdevice_name: %s" % e)
                continue
            if bootif_mac.lower() == hwaddr.lower():
                ksdevice = dev
                break

    return ksdevice

# note that NetworkDevice.get returns "" if key is not found
def get_ifcfg_value(iface, key, root_path=""):
    dev = NetworkDevice(os.path.normpath(root_path + netscriptsDir), iface)
    try:
        dev.loadIfcfgFile()
    except IOError as e:
        log.debug("get_ifcfg_value %s %s: %s" % (iface, key, e))
        return ""
    return dev.get(key)

def set_hostname(hn):
    if flags.imageInstall:
        log.info("image install -- not setting hostname")
        return

    log.info("setting installation environment hostname to %s" % hn)
    iutil.execWithRedirect("hostname", [hn])

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
    for devname in nm.nm_devices():
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

def wait_for_connecting_NM():
    """If NM is in connecting state, wait for connection.
    Return value: NM has got connection."""

    if nm.nm_is_connected:
        return True

    if nm.nm_is_connecting():
        log.debug("waiting for connecting NM (dhcp?)")
    else:
        return False

    i = 0
    while nm.nm_is_connecting() and i < NETWORK_CONNECTION_TIMEOUT:
        i += 1
        time.sleep(1)
        if nm.nm_is_connected():
            log.debug("connected, waited %d seconds" % i)
            return True

    log.debug("not connected, waited %d of %d secs" % (i, NETWORK_CONNECTION_TIMEOUT))
    return False

def update_hostname_data(ksdata, hostname):
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
        log.info("unspecified network --device in kickstart, using %s (%s)" %
                 (devname, msg))
    else:
        if devspec.lower() == "ibft":
            devname = ""
        if devspec.lower() == "link":
            for dev in sorted(devices):
                try:
                    link_up = nm.nm_device_carrier(dev)
                except ValueError as e:
                    log.debug("get_device_name: %s" % e)
                    continue
                if link_up:
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

    if devname and devname not in devices:
        for d in devices:
            try:
                hwaddr = nm.nm_device_hwaddress(d)
            except ValueError as e:
                log.debug("get_device_name: %s" % e)
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
            log.error("Kickstart: The provided network interface %s does not exist" % network_data.device)
            continue

        try:
            nm.nm_update_settings_of_device(devname, 'connection', 'autoconnect', network_data.onboot)
            ifcfglog.debug("setting autoconnect (ONBOOT) of %s to %s" % (devname, network_data.onboot))
        except nm.DeviceSettingsNotFoundError as e:
            log.debug("setOnboot: %s" % e)

def networkInitialize(ksdata):

    log.debug("network: devices found %s" % nm.nm_devices())
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
    log.info("got %d NTP servers from DHCP" % len(ntp_servers))
    hostnames = []
    for server_address in ntp_servers:
        try:
            hostname = socket.gethostbyaddr(server_address)[0]
        except socket.error:
            # getting hostname failed, just use the address returned from DHCP
            log.debug("getting NTP server hostname failed for address: %s"
                      % server_address)
            hostname = server_address
        hostnames.append(hostname)
    # check if some NTP servers were specified from kickstart
    if not ksdata.timezone.ntpservers:
        # no NTP servers were specified, add those from DHCP
        ksdata.timezone.ntpservers = hostnames

def wait_for_connecting_NM_thread(ksdata):
    # connection (e.g. auto default dhcp) is activated by NM service
    if wait_for_connecting_NM():
        hostname = getHostname()
        update_hostname_data(ksdata, hostname)
        _get_ntp_servers_from_dhcp(ksdata)
