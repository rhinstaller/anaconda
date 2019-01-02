#
# network.py - network configuration install data
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
#               2008, 2009, 2017
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

import gi
gi.require_version("NM", "1.0")

from gi.repository import NM

import shutil
from pyanaconda.core import util, constants
import socket
import os
import time
import threading
import re
import dbus
import ipaddress
import itertools
import logging

from pyanaconda.simpleconfig import SimpleConfigFile
from blivet.devices import FcoeDiskDevice
import blivet.arch

from pyanaconda import nm
from pyanaconda.flags import flags
from pyanaconda.core.i18n import _
from pyanaconda.core.regexes import HOSTNAME_PATTERN_WITHOUT_ANCHORS, IBFT_CONFIGURED_DEVICE_NAME
from pyanaconda.core.configuration.anaconda import conf
from pykickstart.constants import BIND_TO_MAC
from pyanaconda.modules.common.constants.services import NETWORK, TIMEZONE
from pyanaconda.payload.livepayload import LiveImagePayload

from pyanaconda.anaconda_loggers import get_module_logger, get_ifcfg_logger
log = get_module_logger(__name__)

sysconfigDir = "/etc/sysconfig"
netscriptsDir = "%s/network-scripts" % (sysconfigDir)
networkConfFile = "%s/network" % (sysconfigDir)
hostnameFile = "/etc/hostname"
ipv6ConfFile = "/etc/sysctl.d/anaconda.conf"
ifcfgLogFile = "/tmp/ifcfg.log"
DEFAULT_HOSTNAME = "localhost.localdomain"

ifcfglog = None

network_connected = None
network_connected_condition = threading.Condition()


def setup_ifcfg_log():
    # Setup special logging for ifcfg NM interface
    from pyanaconda import anaconda_logging
    global ifcfglog
    logger = get_ifcfg_logger()
    logger.setLevel(logging.DEBUG)
    anaconda_logging.logger.addFileHandler(ifcfgLogFile, logger, logging.DEBUG)
    anaconda_logging.logger.forwardToJournal(logger)

    ifcfglog = get_ifcfg_logger()

def check_ip_address(address, version=None):
    """
    Check if the given IP address is valid in given version if set.

    :param str address: IP address for testing
    :param int version: ``4`` for IPv4, ``6`` for IPv6 or
                        ``None`` to allow either format
    :returns: ``True`` if IP address is valid or ``False`` if not
    :rtype: bool

    """
    try:
        if version == 4:
            ipaddress.IPv4Address(address)
        elif version == 6:
            ipaddress.IPv6Address(address)
        elif not version:  # any of those
            ipaddress.ip_address(address)
        else:
            log.error("IP version %s is not supported", version)
            return False
        return True
    except ValueError:
        return False

def sanityCheckHostname(hostname):
    """
    Check if the given string is (syntactically) a valid hostname.

    :param hostname: a string to check
    :returns: a pair containing boolean value (valid or invalid) and
              an error message (if applicable)
    :rtype: (bool, str)

    """

    if not hostname:
        return (False, _("Host name cannot be None or an empty string."))

    if len(hostname) > 255:
        return (False, _("Host name must be 255 or fewer characters in length."))

    if not (re.match('^' + HOSTNAME_PATTERN_WITHOUT_ANCHORS + '$', hostname)):
        return (False, _("Host names can only contain the characters 'a-z', "
                         "'A-Z', '0-9', '-', or '.', parts between periods "
                         "must contain something and cannot start or end with "
                         "'-'."))

    return (True, "")

def getIPs():
    """ Return a list of IP addresses for all active devices. """
    ipv4_addresses = []
    ipv6_addresses = []
    for devname in nm.nm_activated_devices():
        try:
            ipv4_addresses += nm.nm_device_ip_addresses(devname, version=4)
            ipv6_addresses += nm.nm_device_ip_addresses(devname, version=6)
        except (dbus.DBusException, ValueError) as e:
            log.warning("Got an exception trying to get the ip addr "
                        "of %s: %s", devname, e)
    # prefer IPv4 addresses to IPv6 addresses
    return ipv4_addresses + ipv6_addresses

def getFirstRealIP():
    """ Return the first real non-local IP we find from the list of
        all active devices.

        :rtype: str or ``None``
    """
    for ip in getIPs():
        if ip not in ("127.0.0.1", "::1"):
            return ip
    return None

def netmask2prefix(netmask):
    """ Convert netmask to prefix (CIDR bits) """
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
            _bytes.append(256 - 2 ** (8 - prefix))
            prefix = 0
    netmask = ".".join(str(byte) for byte in _bytes)
    return netmask

def current_hostname():
    return socket.gethostname()

def getHostname():
    """ Try to determine what the hostname should be for this system """
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

def _ifcfg_files(directory):
    rv = []
    for name in os.listdir(directory):
        if name.startswith("ifcfg-"):
            if name == "ifcfg-lo":
                continue
            rv.append(os.path.join(directory, name))
    return rv

def logIfcfgFiles(message=""):
    """ Log contents of all network ifcfg files.

        :param str message: append message to the log
    """
    ifcfglog.debug("content of files (%s):", message)
    for path in _ifcfg_files(netscriptsDir):
        ifcfglog.debug("%s:", path)
        with open(path, "r") as f:
            for line in f:
                ifcfglog.debug("  %s", line.strip())
    ifcfglog.debug("all settings: %s", nm.nm_get_all_settings())

class IfcfgFile(SimpleConfigFile):
    def __init__(self, filename):
        super().__init__(always_quote=True, filename=filename)
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

# get a kernel cmdline string for dracut needed for access to storage host
def dracutSetupArgs(networkStorageDevice):

    if networkStorageDevice.nic == "default" or ":" in networkStorageDevice.nic:
        if getattr(networkStorageDevice, 'ibft', False):
            nic = ibftIface()
        else:
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
                               networkStorageDevice.host_address)

def dracutBootArguments(devname, ifcfg, storage_ipaddr, hostname=None):

    netargs = set()

    if ifcfg.get('BOOTPROTO') == 'ibft':
        netargs.add("rd.iscsi.ibft")
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
                netargs.add("ip=%s::%s::%s:%s:none" % (ipaddr, gateway,
                            hostname, devname))
        else:
            if util.lowerASCII(ifcfg.get('bootproto')) == 'dhcp':
                netargs.add("ip=%s:dhcp" % devname)
            else:
                cfgidx = ''
                if ifcfg.get('IPADDR0'):
                    cfgidx = '0'
                if ifcfg.get('GATEWAY%s' % cfgidx):
                    gateway = ifcfg.get('GATEWAY%s' % cfgidx)
                else:
                    gateway = ""
                netmask = ifcfg.get('NETMASK%s' % cfgidx)
                prefix = ifcfg.get('PREFIX%s' % cfgidx)
                if not netmask and prefix:
                    netmask = prefix2netmask(int(prefix))
                ipaddr = ifcfg.get('IPADDR%s' % cfgidx)
                netargs.add("ip=%s::%s:%s:%s:%s:none" %
                            (ipaddr, gateway, netmask, hostname, devname))

        hwaddr = ifcfg.get("HWADDR")
        if hwaddr:
            netargs.add("ifname=%s:%s" % (devname, hwaddr.lower()))

        if ifcfg.get("TYPE") == "Team" or ifcfg.get("DEVICETYPE") == "Team":
            slaves = get_team_slaves([devname, ifcfg.get("UUID")])
            netargs.add("team=%s:%s" % (devname,
                                        ",".join(dev for dev, _cfg in slaves)))

        if ifcfg.get("TYPE") == "Vlan":
            physdev_spec = ifcfg.get("PHYSDEV")
            physdev = None
            if physdev_spec in nm.nm_devices():
                physdev = physdev_spec
                ifcfg_path = find_ifcfg_file_of_device(physdev)
                if ifcfg_path:
                    ifcfg = IfcfgFile(ifcfg_path)
                    ifcfg.read()
                else:
                    log.debug("can't find ifcfg of vlan parent %s", physdev)
            # physical device can be specified by connection uuid (eg from nm-c-e)
            else:
                ifcfg_path = find_ifcfg_file([("UUID", physdev_spec)])
                if ifcfg_path:
                    ifcfg = IfcfgFile(ifcfg_path)
                    ifcfg.read()
                    # On s390 with net.ifnames=0 there is no DEVICE
                    physdev = ifcfg.get("DEVICE") or ifcfg.get("NAME")

            if physdev:
                netargs.add("vlan=%s:%s" % (devname, physdev))
            else:
                log.warning("can't find parent of vlan device %s specified by %s",
                             devname, physdev_spec)

    # For vlan ifcfg now refers to the physical device file
    nettype = ifcfg.get("NETTYPE")
    subchannels = ifcfg.get("SUBCHANNELS")
    if blivet.arch.is_s390() and nettype and subchannels:
        znet = "rd.znet=%s,%s" % (nettype, subchannels)
        options = ifcfg.get("OPTIONS").strip("'\"")
        if options:
            options = filter(lambda x: x != '', options.split(' '))
            znet += ",%s" % (','.join(options))
        netargs.add(znet)

    return netargs

def _get_ip_setting_values_from_ksdata(networkdata):
    values = []

    # ipv4 settings
    if networkdata.noipv4:
        method4 = "disabled"
    elif networkdata.bootProto == "static":
        method4 = "manual"
    else:
        method4 = "auto"
    values.append(["ipv4", "method", method4, "s"])

    addresses4 = []
    if method4 == "manual":
        addr4 = nm.nm_ipv4_to_dbus_int(networkdata.ip)
        if networkdata.gateway:
            gateway4 = nm.nm_ipv4_to_dbus_int(networkdata.gateway)
        else:
            gateway4 = 0  # will be ignored by NetworkManager
        prefix4 = netmask2prefix(networkdata.netmask)
        addresses4 = [[addr4, prefix4, gateway4]]

    values.append(["ipv4", "addresses", addresses4, "aau"])

    # ipv6 settings
    if networkdata.noipv6:
        method6 = "ignore"
    else:
        if not networkdata.ipv6:
            method6 = "auto"
        elif networkdata.ipv6 == "auto":
            method6 = "auto"
        elif networkdata.ipv6 == "dhcp":
            method6 = "dhcp"
        else:
            method6 = "manual"
    values.append(["ipv6", "method", method6, "s"])

    addresses6 = []
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
        addresses6 = [(addr6, prefix6, gateway6)]
    values.append(["ipv6", "addresses", addresses6, "a(ayuay)"])

    # nameservers
    nss4 = []
    nss6 = []
    if networkdata.nameserver:
        for ns in [str.strip(i) for i in networkdata.nameserver.split(",")]:
            if check_ip_address(ns, version=6):
                nss6.append(nm.nm_ipv6_to_dbus_ay(ns))
            elif check_ip_address(ns, version=4):
                nss4.append(nm.nm_ipv4_to_dbus_int(ns))
            else:
                log.error("IP address %s is not valid", ns)
    values.append(["ipv4", "dns", nss4, "au"])
    values.append(["ipv6", "dns", nss6, "aay"])

    return values

def update_settings_with_ksdata(devname, networkdata):
    try:
        uuid = nm.nm_device_setting_value(devname, "connection", "uuid")
    except nm.MultipleSettingsFoundError as e:
        uuid = find_ifcfg_uuid_of_device(devname)
        log.debug("%s for %s, using %s", e, devname, uuid)
    new_values = _get_ip_setting_values_from_ksdata(networkdata)
    new_values.append(['connection', 'autoconnect', False, 'b'])
    if networkdata.bindto == BIND_TO_MAC:
        hwaddr = nm.nm_device_perm_hwaddress(devname)
        hwaddr = [int(b, 16) for b in hwaddr.split(":")]
        new_values.append(['802-3-ethernet', 'mac-address', hwaddr, 'ay'])
        new_values.append(['connection', 'interface-name', None, 's'])
    nm.nm_update_settings(uuid, new_values)
    return uuid

def ksdata_from_ifcfg(devname, uuid=None):

    if devname in nm.nm_devices():
        # virtual devices (bond, vlan, ...) not activated in installer
        # are not created so guard these checks
        if nm.nm_device_is_slave(devname) and nm.nm_device_type_is_ethernet(devname):
            return None
        if nm.nm_device_type_is_wifi(devname):
            # wifi from kickstart is not supported yet
            return None

    if uuid:
        ifcfg_path = find_ifcfg_file([("UUID", uuid)])
    else:
        # look it up by other values depending on its type
        ifcfg_path = find_ifcfg_file_of_device(devname)

    if not ifcfg_path:
        return None

    ifcfg = IfcfgFile(ifcfg_path)
    ifcfg.read()
    nd = ifcfg_to_ksdata(ifcfg, devname)

    if not nd:
        return None

    if devname in nm.nm_devices():
        if device_type_is_supported_wired(devname):
            nd.device = devname
        elif nm.nm_device_type_is_wifi(devname):
            nm.device = ""
        elif nm.nm_device_type_is_bond(devname):
            nd.device = devname
        elif nm.nm_device_type_is_team(devname):
            nd.device = devname
        elif nm.nm_device_type_is_bridge(devname):
            nd.device = devname
        elif nm.nm_device_type_is_vlan(devname):
            _update_vlan_interfacename_ksdata(devname, nd)
    else:
        # virtual devices (bond, vlan, ...) not activated in installer
        # are not created so look at ifcfg value instead of device property
        if nd.vlanid:
            _update_vlan_interfacename_ksdata(devname, nd)
        else:
            nd.device = devname

    return nd

def ifcfg_to_ksdata(ifcfg, devname):

    from pyanaconda.kickstart import AnacondaKSHandler
    handler = AnacondaKSHandler()
    kwargs = {}

    # no network command for non-virtual device slaves
    if ifcfg.get("TYPE") not in ("Bond", "Team"):
        if ifcfg.get("MASTER"):
            return None
        if ifcfg.get("TEAM_MASTER"):
            return None
        if ifcfg.get("BRIDGE"):
            return None

    # ipv4 and ipv6
    if ifcfg.get("ONBOOT") and ifcfg.get("ONBOOT") == "no":
        kwargs["onboot"] = False
    if ifcfg.get('MTU') and ifcfg.get('MTU') != "0":
        kwargs["mtu"] = ifcfg.get('MTU')
    # ipv4
    if not ifcfg.get('BOOTPROTO'):
        kwargs["noipv4"] = True
    else:
        if util.lowerASCII(ifcfg.get('BOOTPROTO')) == 'dhcp':
            kwargs["bootProto"] = "dhcp"
            if ifcfg.get('DHCPCLASS'):
                kwargs["dhcpclass"] = ifcfg.get('DHCPCLASS')
        elif ifcfg.get('IPADDR'):
            kwargs["bootProto"] = "static"
            kwargs["ip"] = ifcfg.get('IPADDR')
            netmask = ifcfg.get('NETMASK')
            prefix = ifcfg.get('PREFIX')
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
            prefix = ifcfg.get('PREFIX0')
            if prefix:
                netmask = prefix2netmask(int(prefix))
                kwargs["netmask"] = netmask
            # note that --gateway is common for ipv4 and ipv6
            if ifcfg.get('GATEWAY0'):
                kwargs["gateway"] = ifcfg.get('GATEWAY0')

    # ipv6
    if (not ifcfg.get('IPV6INIT') or ifcfg.get('IPV6INIT') == "no"):
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
        if util.upperASCII(key).startswith('DNS'):
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
        slaves = get_slaves_from_ifcfgs("MASTER", [devname, ifcfg.get("UUID")])
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

    # bridging
    if ifcfg.get("TYPE") == "Bridge":
        slaves = get_slaves_from_ifcfgs("BRIDGE", [devname, ifcfg.get("UUID")])
        if slaves:
            kwargs["bridgeslaves"] = ",".join(slaves)

        bridgeopts = ifcfg.get("BRIDGING_OPTS").replace('_', '-').split()
        if ifcfg.get("STP"):
            bridgeopts.append("%s=%s" % ("stp", ifcfg.get("STP")))
        if ifcfg.get("DELAY"):
            bridgeopts.append("%s=%s" % ("forward-delay", ifcfg.get("DELAY")))
        if bridgeopts:
            kwargs["bridgeopts"] = ",".join(bridgeopts)

    # pylint: disable=no-member
    nd = handler.NetworkData(**kwargs)

    # teaming
    if ifcfg.get("TYPE") == "Team" or ifcfg.get("DEVICETYPE") == "Team":
        slaves = get_team_slaves([devname, ifcfg.get("UUID")])
        for dev, cfg in slaves:
            nd.teamslaves.append((dev, cfg))

        try:
            teamconfig = nm.nm_device_setting_value(devname, "team", "config")
        except nm.MultipleSettingsFoundError as e:
            teamconfig = None
            log.debug("%s while looking for team device config", e)
        if teamconfig:
            nd.teamconfig = teamconfig

    return nd

def hostname_ksdata(hostname):
    from pyanaconda.kickstart import AnacondaKSHandler
    handler = AnacondaKSHandler()
    # pylint: disable=no-member
    return handler.NetworkData(hostname=hostname, bootProto="")

def find_ifcfg_file_of_device(devname, root_path=""):
    ifcfg_path = None

    if devname not in nm.nm_devices():
        # virtual devices (bond, vlan, ...) not activated in installer
        # are not created so just go right to searching in ifcfgs
        return find_ifcfg_file([("DEVICE", devname)])

    if nm.nm_device_type_is_wifi(devname):
        ssid = nm.nm_device_active_ssid(devname)
        if ssid:
            ifcfg_path = find_ifcfg_file([("ESSID", ssid)])
    elif nm.nm_device_type_is_bond(devname):
        ifcfg_path = find_ifcfg_file([("DEVICE", devname)])
    elif nm.nm_device_type_is_team(devname):
        ifcfg_path = find_ifcfg_file([("DEVICE", devname)])
    elif nm.nm_device_type_is_vlan(devname):
        ifcfg_path = find_ifcfg_file([("DEVICE", devname)])
    elif nm.nm_device_type_is_bridge(devname):
        ifcfg_path = find_ifcfg_file([("DEVICE", devname)])
    elif nm.nm_device_type_is_infiniband(devname):
        ifcfg_path = find_ifcfg_file([("DEVICE", devname)])
    elif nm.nm_device_type_is_ethernet(devname):
        try:
            hwaddr = nm.nm_device_perm_hwaddress(devname)
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
                ifcfg_path = find_ifcfg_file([("HWADDR", hwaddr_check),
                                              ("TEAM_MASTER", nonempty)],
                                             root_path)
            if not ifcfg_path:
                ifcfg_path = find_ifcfg_file([("HWADDR", hwaddr_check),
                                              ("BRIDGE", nonempty)],
                                             root_path)
            if not ifcfg_path:
                ifcfg_path = find_ifcfg_file([("HWADDR", hwaddr_check)], root_path)
        if not ifcfg_path:
            ifcfg_path = find_ifcfg_file([("DEVICE", devname)], root_path)
        if not ifcfg_path:
            if blivet.arch.is_s390():
                # s390 setting generated in dracut with net.ifnames=0
                # has neither DEVICE nor HWADDR (#1249750)
                ifcfg_path = find_ifcfg_file([("NAME", devname)], root_path)
            else:
                log.debug("ifcfg file for %s not found", devname)

    return ifcfg_path

def find_ifcfg_uuid_of_device(devname):
    ifcfg_path = find_ifcfg_file_of_device(devname)
    if ifcfg_path:
        ifcfg = IfcfgFile(ifcfg_path)
        ifcfg.read()
        uuid = ifcfg.get('UUID')
    else:
        log.debug("can't find ifcfg file of %s", devname)
        uuid = None
    return uuid

def find_ifcfg_file(values, root_path=""):
    for filepath in _ifcfg_files(os.path.normpath(root_path + netscriptsDir)):
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

def get_slaves_from_ifcfgs(master_option, master_specs):
    """List of slaves of master specified by master_specs in master_option.

       master_option is ifcfg option containing spec of master
       master_specs is a list containing device name of master (dracut)
       and/or master's connection uuid
    """
    slaves = []

    for filepath in _ifcfg_files(netscriptsDir):
        ifcfg = IfcfgFile(filepath)
        ifcfg.read()
        master = ifcfg.get(master_option)
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

# why not from ifcfg? because we want config json value without escapes
def get_team_slaves(master_specs):
    """List of slaves of master specified by master_specs (name, opts).

       master_specs is a list containing device name of master (dracut)
       and/or master's connection uuid
    """
    slaves = []

    for master in master_specs:
        slave_settings = nm.nm_get_settings(master, "connection", "master")
        for settings in slave_settings:
            try:
                cfg = settings["team-port"]["config"]
            except KeyError:
                cfg = ""
            devname = settings["connection"].get("interface-name")
            #nm-c-e doesn't save device name
            # TODO: wifi, infiniband
            if not devname:
                ty = settings["connection"]["type"]
                if ty == "802-3-ethernet":
                    hwaddr = settings["802-3-ethernet"]["mac-address"]
                    hwaddr = ":".join("%02X" % b for b in hwaddr)
                    devname = nm.nm_hwaddr_to_device_name(hwaddr)
            if devname:
                slaves.append((devname, cfg))
            else:
                uuid = settings["connection"].get("uuid")
                log.debug("can't get team slave device name of %s", uuid)

    return slaves

def ibftIface():
    iface = ""
    ipopts = flags.cmdline.get('ip')
    # Examples (dhcp, static):
    # ibft0:dhcp
    # 10.34.102.244::10.34.102.54:255.255.255.0::ibft0:none
    if ipopts:
        for ipopt in ipopts.split(" "):
            for item in ipopt.split(":"):
                if item.startswith('ibft'):
                    iface = item
                    break
    return iface

def hostname_from_cmdline(cmdline):
    # legacy hostname= option
    hostname = flags.cmdline.get('hostname', "")
    # ip= option
    ipopts = flags.cmdline.get('ip')
    # Example (2 options):
    # ens3:dhcp 10.34.102.244::10.34.102.54:255.255.255.0:myhostname:ens9:none
    if ipopts:
        for ipopt in ipopts.split(" "):
            try:
                hostname = ipopt.split(':')[4]
            except IndexError:
                pass
    return hostname

def ifaceForHostIP(host):
    route = util.execWithCapture("ip", ["route", "get", "to", host])
    if not route:
        log.error("Could not get interface for route to %s", host)
        return ""

    routeInfo = route.split()
    if routeInfo[0] != host or len(routeInfo) < 5 or \
       "dev" not in routeInfo or routeInfo.index("dev") > 3:
        log.error('Unexpected "ip route get to %s" reply: %s', host, routeInfo)
        return ""

    return routeInfo[routeInfo.index("dev") + 1]

def default_route_device(family="inet"):
    routes = util.execWithCapture("ip", ["-f", family, "route", "show"])
    if not routes:
        log.debug("Could not get default %s route device", family)
        return None

    for line in routes.split("\n"):
        if line.startswith("default"):
            parts = line.split()
            if len(parts) >= 5 and parts[3] == "dev":
                return parts[4]
            else:
                log.debug("Could not parse default %s route device", family)
                return None

    return None

# TODO remove
def copyFileToPath(fileName, destPath='', overwrite=False):
    if not os.path.isfile(fileName):
        return False
    destfile = os.path.join(destPath, fileName.lstrip('/'))
    if (os.path.isfile(destfile) and not overwrite):
        return False
    if not os.path.isdir(os.path.dirname(destfile)):
        util.mkdirChain(os.path.dirname(destfile))
    shutil.copy(fileName, destfile)
    return True




def devices_used_by_fcoe(storage):
    fcoe_nics = {d.nic for d in storage.devices if isinstance(d, FcoeDiskDevice)}
    fcoe_devices = [device for device in nm.nm_devices() if device in fcoe_nics]
    return fcoe_devices

def update_hostname_data(ksdata, hostname):
    log.debug("updating host name %s", hostname)
    hostname_found = False
    for nd in ksdata.network.network:
        if nd.hostname:
            nd.hostname = hostname
            hostname_found = True
    if not hostname_found:
        nd = hostname_ksdata(hostname)
        ksdata.network.network.append(nd)
    network_proxy = NETWORK.get_proxy()
    network_proxy.SetHostname(hostname)

def networkInitialize(ksdata):
    if not conf.system.can_configure_network:
        return

    log.debug("devices found %s", nm.nm_devices())
    logIfcfgFiles("network initialization")

    log.debug("ensure single initramfs connections")
    network_proxy = NETWORK.get_proxy()
    devnames = network_proxy.ConsolidateInitramfsConnections()
    if devnames:
        msg = "single connection ensured for devices %s" % devnames
        log.debug("%s", msg)
        logIfcfgFiles(msg)
    log.debug("apply kickstart")
    devnames = network_proxy.ApplyKickstart()
    if devnames:
        msg = "kickstart pre section applied for devices %s" % devnames
        log.debug("%s", msg)
        logIfcfgFiles(msg)
    log.debug("create missing ifcfg files")
    devnames = network_proxy.DumpMissingIfcfgFiles()
    if devnames:
        msg = "missing ifcfgs created for devices %s" % devnames
        log.debug("%s", msg)
        logIfcfgFiles(msg)

    # For kickstart network --activate option we set ONBOOT=yes
    # in dracut to get devices activated by NM. The real network --onboot
    # value is set here.
    log.debug("set real ONBOOT value")
    devnames = network_proxy.SetRealOnbootValuesFromKickstart()
    if devnames:
        msg = "real kickstart ONBOOT value set for devices %s" % devnames
        log.debug("%s", msg)
        logIfcfgFiles(msg)

    # initialize ksdata hostname
    if network_proxy.Hostname == DEFAULT_HOSTNAME:
        bootopts_hostname = hostname_from_cmdline(flags.cmdline)
        if bootopts_hostname:
            update_hostname_data(ksdata, bootopts_hostname)

def _get_ntp_servers_from_dhcp():
    """Check if some NTP servers were returned from DHCP and set them
    to ksdata (if not NTP servers were specified in the kickstart)"""
    timezone_proxy = TIMEZONE.get_proxy()
    ntp_servers = nm.nm_ntp_servers_from_dhcp()
    log.info("got %d NTP servers from DHCP", len(ntp_servers))
    hostnames = []
    for server_address in ntp_servers:
        try:
            hostname = socket.gethostbyaddr(server_address)[0]
        except socket.error:
            # getting hostname failed, just use the address returned from DHCP
            log.debug("getting NTP server host name failed for address: %s",
                      server_address)
            hostname = server_address
        hostnames.append(hostname)

    # check if some NTP servers were specified from kickstart
    if not timezone_proxy.NTPServers and conf.target.is_hardware:
        # no NTP servers were specified, add those from DHCP
        timezone_proxy.SetNTPServers(hostnames)

def wait_for_connected_NM(timeout=constants.NETWORK_CONNECTION_TIMEOUT, only_connecting=False):
    """Wait for NM being connected.

    If only_connecting is set, wait only if NM is in connecting state and
    return immediately after leaving this state (regardless of the new state).
    Used to wait for dhcp configuration in progress.

    :param timeout: timeout in seconds
    :type timeout: int
    :parm only_connecting: wait only for the result of NM being connecting
    :type only_connecting: bool
    :return: NM is connected
    :rtype: bool
    """

    network_proxy = NETWORK.get_proxy()
    if network_proxy.Connected:
        return True

    if only_connecting:
        if network_proxy.IsConnecting():
            log.debug("waiting for connecting NM (dhcp in progress?), timeout=%d", timeout)
        else:
            return False
    else:
        log.debug("waiting for connected NM, timeout=%d", timeout)

    i = 0
    while i < timeout:
        i += constants.NETWORK_CONNECTED_CHECK_INTERVAL
        time.sleep(constants.NETWORK_CONNECTED_CHECK_INTERVAL)
        if network_proxy.Connected:
            log.debug("NM connected, waited %d seconds", i)
            return True
        elif only_connecting:
            if not network_proxy.IsConnecting():
                break

    log.debug("NM not connected, waited %d seconds", i)
    return False

def wait_for_network_devices(devices, timeout=constants.NETWORK_CONNECTION_TIMEOUT):
    devices = set(devices)
    i = 0
    log.debug("waiting for connection of devices %s for iscsi", devices)
    while i < timeout:
        if not devices - set(nm.nm_activated_devices()):
            return True
        i += 1
        time.sleep(1)
    return False

def wait_for_connecting_NM_thread():
    """Wait for connecting NM in thread, do some work and signal connectivity.

    This function is called from a thread which is run at startup to wait for
    NetworkManager being in connecting state (eg getting IP from DHCP). When NM
    leaves connecting state do some actions and signal new state if NM becomes
    connected.
    """
    connected = wait_for_connected_NM(only_connecting=True)
    if connected:
        _get_ntp_servers_from_dhcp()
    with network_connected_condition:
        global network_connected
        network_connected = connected
        network_connected_condition.notify_all()


def wait_for_connectivity(timeout=constants.NETWORK_CONNECTION_TIMEOUT):
    """Wait for network connectivty to become available

    :param timeout: how long to wait in seconds
    :type timeout: integer of float"""
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
    if state == NM.State.CONNECTING:
        msg = _("Connecting...")
    elif state == NM.State.DISCONNECTING:
        msg = _("Disconnecting...")
    else:
        active_devs = [d for d in nm.nm_activated_devices()
                       if not is_libvirt_device(d)]
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
                if device_type_is_supported_wired(devname):
                    msg = _("Wired (%(interface_name)s) connected") \
                          % {"interface_name": devname}
                elif nm.nm_device_type_is_wifi(devname):
                    msg = _("Wireless connected to %(access_point)s") \
                          % {"access_point" : ssids[devname]}
                elif nm.nm_device_type_is_bond(devname):
                    msg = _("Bond %(interface_name)s (%(list_of_slaves)s) connected") \
                          % {"interface_name": devname, \
                             "list_of_slaves": ",".join(slaves[devname])}
                elif nm.nm_device_type_is_team(devname):
                    msg = _("Team %(interface_name)s (%(list_of_slaves)s) connected") \
                          % {"interface_name": devname, \
                             "list_of_slaves": ",".join(slaves[devname])}
                elif nm.nm_device_type_is_bridge(devname):
                    msg = _("Bridge %(interface_name)s (%(list_of_slaves)s) connected") \
                          % {"interface_name": devname, \
                             "list_of_slaves": ",".join(slaves[devname])}
                elif nm.nm_device_type_is_vlan(devname):
                    try:
                        parent = nm.nm_device_setting_value(devname, "vlan", "parent")
                        vlanid = nm.nm_device_setting_value(devname, "vlan", "id")
                    except nm.MultipleSettingsFoundError as e:
                        parent = vlanid = None
                        log.debug("%s when looking for vlan settings of %s", e, devname)
                    msg = _("VLAN %(interface_name)s (%(parent_device)s, ID %(vlanid)s) connected") \
                          % {"interface_name": devname, "parent_device": parent, "vlanid": vlanid}
            elif len(nonslaves) > 1:
                devlist = []
                for devname in nonslaves:
                    if device_type_is_supported_wired(devname):
                        devlist.append("%s" % devname)
                    elif nm.nm_device_type_is_wifi(devname):
                        devlist.append("%s" % ssids[devname])
                    elif nm.nm_device_type_is_bond(devname):
                        devlist.append("%s (%s)" % (devname, ",".join(slaves[devname])))
                    elif nm.nm_device_type_is_team(devname):
                        devlist.append("%s (%s)" % (devname, ",".join(slaves[devname])))
                    elif nm.nm_device_type_is_bridge(devname):
                        devlist.append("%s (%s)" % (devname, ",".join(slaves[devname])))
                    elif nm.nm_device_type_is_vlan(devname):
                        devlist.append("%s" % devname)
                msg = _("Connected: %(list_of_interface_names)s") % {"list_of_interface_names": ", ".join(devlist)}
        else:
            msg = _("Not connected")

    if not nm.nm_devices():
        msg = _("No network devices available")

    return msg

def default_ks_vlan_interface_name(parent, vlanid):
    return "%s.%s" % (parent, vlanid)

def _update_vlan_interfacename_ksdata(devname, ndata):
    if devname != default_ks_vlan_interface_name(ndata.device, ndata.vlanid):
        ndata.interfacename = devname

def update_onboot_value(devname, value, ksdata=None, root_path=None):
    """Update onboot value in ifcfg files and optionally ksdata

    By default ifcfg files on target system root are modified.

    :param devname: name of device
    :type devname: str
    :param value: value of onboot setting
    :type value: bool
    :param ksdata: optional ksdata to be modified accordingly
    :type ksdata: kickstart data structure
    :param root_path: optional root path for ifcfg files,
                      target system root by default
    :type root_path: str
    :returns: True if the value was updated, False otherwise
    :rtype: bool

    """
    log.debug("setting ONBOOT value of %s to %s", devname, value)
    if root_path is None:
        root_path = util.getSysroot()
    if value:
        ifcfg_value = 'yes'
    else:
        ifcfg_value = 'no'

    ifcfg_path = find_ifcfg_file_of_device(devname, root_path=root_path)
    if not ifcfg_path:
        log.debug("can't find ifcfg file of %s", devname)
        return False
    ifcfg = IfcfgFile(ifcfg_path)
    ifcfg.read()
    ifcfg.set(('ONBOOT', ifcfg_value))
    ifcfg.write()

    if ksdata:
        for nd in ksdata.network.network:
            if nd.device == devname:
                nd.onboot = value
                break
    return True

def is_using_team_device():
    return any(nm.nm_device_type_is_team(d) for d in nm.nm_devices())

def is_libvirt_device(iface):
    return iface.startswith("virbr")

def is_ibft_configured_device(iface):
    return IBFT_CONFIGURED_DEVICE_NAME.match(iface)

def device_type_is_supported_wired(name):
    return nm.nm_device_type_is_ethernet(name) or nm.nm_device_type_is_infiniband(name)

def can_overwrite_configuration(payload):
    return isinstance(payload, LiveImagePayload)
