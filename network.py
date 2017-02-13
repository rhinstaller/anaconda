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
import urlgrabber
from flags import flags
from simpleconfig import IfcfgFile
import anaconda_log

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

logger = logging.getLogger("ifcfg")
logger.setLevel(logging.DEBUG)
anaconda_log.logger.addFileHandler(ifcfgLogFile, logger, logging.DEBUG)
anaconda_log.logger.addFileHandler("/dev/tty3", logger, logging.DEBUG)

ifcfglog = logging.getLogger("ifcfg")

class IPError(Exception):
    pass

class IPMissing(Exception):
    pass

def sanityCheckHostname(hostname):
    if len(hostname) < 1:
        return None

    if len(hostname) > 255:
        return _("Hostname must be 255 or fewer characters in length.")

    validStart = string.ascii_letters + string.digits
    validAll = validStart + ".-"

    if string.find(validStart, hostname[0]) == -1:
        return _("Hostname must start with a valid character in the ranges "
                 "'a-z', 'A-Z', or '0-9'")

    for i in range(1, len(hostname)):
        if string.find(validAll, hostname[i]) == -1:
            return _("Hostnames can only contain the characters 'a-z', 'A-Z', '0-9', '-', or '.'")

    return None

# Try to determine what the hostname should be for this system
def getDefaultHostname(anaconda):
    isys.resetResolv()

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

    if hn and hn != 'localhost' and hn != 'localhost.localdomain':
        return hn

    try:
        hn = anaconda.id.network.hostname
    except:
        hn = None

    if not hn or hn == '(none)' or hn == 'localhost' or hn == 'localhost.localdomain':
        hn = socket.gethostname()

    if not hn or hn == '(none)' or hn == 'localhost':
        hn = 'localhost.localdomain'

    return hn

# sanity check an IP string.
def sanityCheckIPString(ip_string):
    if ip_string.strip() == "":
        raise IPMissing, _("IP address is missing.")

    if ip_string.find(':') == -1 and ip_string.find('.') > 0:
        family = socket.AF_INET
        errstr = _("IPv4 addresses must contain four numbers between 0 and 255, separated by periods.")
    elif ip_string.find(':') > 0 and ip_string.find('.') == -1:
        family = socket.AF_INET6
        errstr = _("'%s' is not a valid IPv6 address.") % ip_string
    else:
        raise IPError, _("'%s' is an invalid IP address.") % ip_string

    try:
        socket.inet_pton(family, ip_string)
    except socket.error:
        raise IPError, errstr

def hasActiveNetDev():
    try:
        bus = dbus.SystemBus()
        nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
        props = dbus.Interface(nm, isys.DBUS_PROPS_IFACE)
        state = props.Get(isys.NM_SERVICE, "State")

        if int(state) == isys.NM_STATE_CONNECTED:
            return True
        else:
            return False
    except:
        return False

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
        self.description = ""
        self._dirty = False

    def clear(self):
        IfcfgFile.clear(self)
        if self.iface.startswith('ctc'):
            self.info["TYPE"] = "CTC"

    def __str__(self):
        s = ""
        keys = self.info.keys()
        keys.sort()
        if ("DEVICE" in keys):
            keys.remove("DEVICE")
            keys.insert(0, "DEVICE")
        if "KEY" in keys:
            keys.remove("KEY")
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

    def fileContent(self):
        f = open(self.path, 'r')
        content = f.read()
        f.close()
        return content

    def usedByFCoE(self, anaconda):
        import storage
        for d in anaconda.id.storage.devices:
            if (isinstance(d, storage.devices.FcoeDiskDevice) and
                d.nic == self.iface):
                return True
        return False

    def usedByRootOnISCSI(self, anaconda):
        import storage
        rootdev = anaconda.id.storage.rootDevice
        for d in anaconda.id.storage.devices:
            if (isinstance(d, storage.devices.iScsiDiskDevice) and
                rootdev.dependsOn(d)):
                if d.nic == "default" or ":" in d.nic:
                    if getattr(d, 'ibft', False):
                        if self.get("BOOTPROTO") == "ibft":
                            return True
                    else:
                        if self.iface == ifaceForHostIP(d.host_address):
                            return True
                elif d.nic == self.iface:
                    return True

        return False

class Network:

    def __init__(self):

        self.hostname = socket.gethostname()
        self.overrideDHCPhostname = False

        self.update()
        # We want wireless devices to be nm controlled by default
        self.controlWireless()

        # Set all devices to be controlled by NM by default.
        # We can filter out storage devices only after
        # we have device tree populated. So we do it before
        # running nm-c-e and before writing ifcfg files to system.
        self.setNMControlledDevices(self.netdevices.keys())

        self.updateNMiBFTDevices()

    def update(self):

        ifcfglog.debug("Network.update() called")

        self.netdevices = {}
        self.ksdevice = None

        # populate self.netdevices
        devhash = isys.getDeviceProperties(dev=None)
        for iface in devhash.keys():
            device = NetworkDevice(netscriptsDir, iface)
            if os.access(device.path, os.R_OK):
                device.loadIfcfgFile()
            else:
                log.info("Network.update(): %s file not found" %
                         device.path)
                continue

            # TODORV - the last iface in loop wins, might be ok,
            #          not worthy of special juggling
            if device.get('HOSTNAME'):
                self.hostname = device.get('HOSTNAME')

            device.description = isys.getNetDevDesc(iface)

            self.netdevices[iface] = device


        ksdevice = flags.cmdline.get('ksdevice', None)
        if ksdevice:
            bootif_mac = None
            if ksdevice == 'bootif' and flags.cmdline.get("BOOTIF"):
                bootif_mac = flags.cmdline.get("BOOTIF")[3:].replace("-", ":").upper()
            # sort for ksdevice=link (to select the same device as in loader))
            for dev in sorted(self.netdevices):
                mac = self.netdevices[dev].get('HWADDR').upper()
                if ksdevice == 'link' and isys.getLinkStatus(dev):
                    self.ksdevice = dev
                    break
                elif ksdevice == 'bootif':
                    if bootif_mac == mac:
                        self.ksdevice = dev
                        break
                elif ksdevice == dev:
                    self.ksdevice = dev
                    break
                elif ':' in ksdevice:
                    if ksdevice.upper() == mac:
                        self.ksdevice = dev
                        break



    def getDevice(self, device):
        return self.netdevices[device]

    def getKSDevice(self):
        if self.ksdevice is None:
            return None

        try:
            return self.netdevices[self.ksdevice]
        except:
            return None

    def setHostname(self, hn):
        self.hostname = hn
        log.info("setting installation environment hostname to %s" % hn)
        iutil.execWithRedirect("hostname", ["-v", hn ],
                               stdout="/dev/tty5", stderr="/dev/tty5")

    def unsetDNS(self, devname):
        """Unset all DNS* ifcfg parameters."""
        i = 1
        dev = self.netdevices[devname]
        while True:
            if dev.get("DNS%d" % i):
                dev.unset("DNS%d" %i)
            else:
                break
            i += 1

    def setDNS(self, ns, device):
        dns = ns.split(',')
        i = 1
        for addr in dns:
            addr = addr.strip()
            dnslabel = "DNS%d" % (i,)
            self.netdevices[device].set((dnslabel, addr))
            i += 1

    @property
    def gateway(self):
        """GATEWAY - last device in list wins"""
        for dev in reversed(self.netdevices.values()):
            if dev.get('GATEWAY'):
                return dev.get('GATEWAY')
        return ""

    @property
    def ipv6_defaultgw(self):
        """IPV6_DEFAULTGW - last device in list wins"""
        for dev in reversed(self.netdevices.values()):
            if dev.get('IPV6_DEFAULTGW'):
                return dev.get('IPV6_DEFAULTGW')
        return ""

    def setGateway(self, gw, device):
        if ':' in gw:
            self.netdevices[device].set(('IPV6_DEFAULTGW', gw))
        else:
            self.netdevices[device].set(('GATEWAY', gw))

    def lookupHostname(self):
        # can't look things up if they don't exist!
        if not self.hostname or self.hostname == "localhost.localdomain":
            return None

        if not hasActiveNetDev():
            log.warning("no network devices were available to look up host name")
            return None

        try:
            (family, socktype, proto, canonname, sockaddr) = \
                socket.getaddrinfo(self.hostname, None, socket.AF_INET)[0]
            (ip, port) = sockaddr
        except:
            try:
                (family, socktype, proto, canonname, sockaddr) = \
                    socket.getaddrinfo(self.hostname, None, socket.AF_INET6)[0]
                (ip, port, flowinfo, scopeid) = sockaddr
            except:
                return None

        return ip

    # Note that the file is written-out only if there is a value
    # that has changed.
    def writeIfcfgFiles(self):
        for device in self.netdevices.values():
            device.writeIfcfgFile()

    # devices == None => set for all
    def setNMControlledDevices(self, devices=None):
        for devname, device in self.netdevices.items():
            if devices and devname not in devices:
                device.set(('NM_CONTROLLED', 'no'))
            else:
                device.set(('NM_CONTROLLED', 'yes'))

    # Because of possible race in loader devices activated by NM with iBFT
    # connection might not have correct ifcfg file (BOOTPROTO=ibft) created.
    # It is required for compatibility and supplying dracut ip=ibft option at
    # the end of installation. Also handles case  of multiple ibft devices
    # (#831002).
    def updateNMiBFTDevices(self):

        bus = dbus.SystemBus()
        nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
        nm_props_iface = dbus.Interface(nm, isys.DBUS_PROPS_IFACE)

        active_connections = nm_props_iface.Get(isys.NM_MANAGER_IFACE, "ActiveConnections")

        # Look for active connections named with 'iBFT' prefix (created by NM)
        for connection in active_connections:
            active_connection = bus.get_object(isys.NM_SERVICE, connection)
            active_connection_props_iface = dbus.Interface(active_connection, isys.DBUS_PROPS_IFACE)
            setting_path = active_connection_props_iface.Get(isys.NM_ACTIVE_CONNECTION_IFACE, 'Connection')

            setting = bus.get_object(isys.NM_SERVICE, setting_path)
            settings = setting.get_dbus_method("GetSettings")()
            try:
                con_id = str(settings['connection']['id'])
            except KeyError:
                con_id = ''

            if con_id.startswith('iBFT'):
                # Find the device using active 'iBFT' connection
                devices = active_connection_props_iface.Get(isys.NM_ACTIVE_CONNECTION_IFACE, 'Devices')

                for device_path in devices:
                    device = bus.get_object(isys.NM_SERVICE, device_path)
                    device_props_iface = dbus.Interface(device, isys.DBUS_PROPS_IFACE)

                    interface_name = device_props_iface.Get(isys.NM_DEVICE_IFACE, 'Interface')
                    # Update ifcfg of the device if needed
                    if interface_name in self.netdevices:
                        dev = self.netdevices[interface_name]
                        if dev.get('BOOTPROTO') != "ibft":
                            dev.set(('BOOTPROTO', "ibft"))
                            dev.set(('ONBOOT', "yes"))
                            dev.writeIfcfgFile()
                    # For vlan create the ifcfg
                    elif settings['connection']['type'] == "vlan":
                        buf = """
DEVICE=%s
UUID=%s
ONBOOT=yes
TYPE=Vlan
VLAN=yes
BOOTPROTO=ibft
""" % (interface_name, settings['connection']['uuid'])
                        ifcfgfile = "%s/ifcfg-%s" % (netscriptsDir, interface_name)
                        f = open(ifcfgfile, "w")
                        f.write(buf)
                        f.close()

                        device = NetworkDevice(netscriptsDir, interface_name)
                        device.loadIfcfgFile()
                        self.netdevices[interface_name] = device

    # devices == None => set for all
    def updateActiveDevices(self, devices=None):
        for devname, device in self.netdevices.items():
            if devices and devname not in devices:
                device.set(('ONBOOT', 'no'))
            else:
                device.set(('ONBOOT', 'yes'))

    def getOnbootControlledIfaces(self):
        ifaces = []
        for iface, device in self.netdevices.items():
            if (device.get('ONBOOT') == "yes" and
                device.get('NM_CONTROLLED') == "yes"):
                ifaces.append(iface)
        return ifaces

    def controlWireless(self):
        for devname, device in self.netdevices.items():
            if isys.isWireless(devname):
                device.set(('NM_CONTROLLED', 'yes'))

    def writeKS(self, f):
        devNames = self.netdevices.keys()
        devNames.sort()

        if len(devNames) == 0:
            return

        for devName in devNames:
            dev = self.netdevices[devName]

            line = "network"

            # split vlanid from device
            if dev.get("TYPE") == "Vlan":
                (device, sep, vlanid) = dev.get("DEVICE").rpartition('.')
            else:
                device = dev.get("DEVICE")

            # ipv4 and ipv6
            if dev.get("ONBOOT"):
                line += " --onboot %s" % dev.get("ONBOOT")
            line += " --device %s" % device
            if dev.get('MTU') and dev.get('MTU') != "0":
                line += " --mtu=%s" % dev.get('MTU')

            # ipv4
            if not dev.get('BOOTPROTO'):
                line += " --noipv4"
            else:
                if dev.get('BOOTPROTO').lower() == 'dhcp':
                    line += " --bootproto dhcp"
                    if dev.get('DHCPCLASS'):
                        line += " --dhcpclass %s" % dev.get('DHCPCLASS')
                elif dev.get('IPADDR'):
                    line += " --bootproto static --ip %s" % dev.get('IPADDR')
                    netmask = dev.get('NETMASK')
                    prefix  = dev.get('PREFIX')
                    if not netmask and prefix:
                        netmask = isys.prefix2netmask(int(prefix))
                    if netmask:
                        line += " --netmask %s" % netmask
                    # note that --gateway is common for ipv4 and ipv6
                    if dev.get('GATEWAY'):
                        line += " --gateway %s" % dev.get('GATEWAY')

            # ipv6
            if (not dev.get('IPV6INIT') or
                dev.get('IPV6INIT') == "no"):
                line += " --noipv6"
            else:
                if dev.get('IPV6_AUTOCONF') == "yes":
                    line += " --ipv6 auto"
                else:
                    if dev.get('IPV6ADDR'):
                        line += " --ipv6 %s" % dev.get('IPV6ADDR')
                        if dev.get('IPV6_DEFAULTGW'):
                            line += " --ipv6gateway %s" % dev.get('IPV6_DEFAULTGW')
                    if dev.get('DHCPV6') == "yes":
                        line += " --ipv6 dhcp"

            # ipv4 and ipv6
            dnsline = ''
            for key in dev.info.keys():
                if key.upper().startswith('DNS'):
                    if dnsline == '':
                        dnsline = dev.get(key)
                    else:
                        dnsline += "," + dev.get(key)
            if dnsline:
                line += " --nameserver %s" % dnsline

            if dev.get("ETHTOOL_OPTS"):
                line += " --ethtool %s" % dev.get("ETHTOOL_OPTS")

            # hostname
            if (self.overrideDHCPhostname or
                (dev.get('BOOTPROTO') and dev.get('BOOTPROTO').lower() != "dhcp")):
                if (self.hostname and
                    self.hostname != "localhost.localdomain"):
                    line += " --hostname %s" % self.hostname

            # vlanid
            if dev.get("TYPE") == "Vlan":
                line += " --vlanid %s" % vlanid

            # bonding
            if dev.get('TYPE') == "Bond":
                slaves = [dname for dname, d in self.netdevices.items()
                          if d.get('MASTER') == devName]
                line += " --bondslaves %s" % ",".join(slaves)
                bondopts = dev.get('BONDING_OPTS').split()
                separator = "," if all(',' not in opt for opt in bondopts) else ";"
                line += " --bondopts %s" % separator.join(bondopts)

            if dev.get("DOMAIN"):
                line += " --domain %s" % dev.get("DOMAIN")

            if dev.get("DEFROUTE") == "no":
                line += " --nodefroute"

            line += "\n"
            f.write(line)

    def _copyFileToPath(self, file, instPath='', overwrite=False):
        if not os.path.isfile(file):
            return False
        destfile = os.path.join(instPath, file.lstrip('/'))
        if (os.path.isfile(destfile) and not overwrite):
            return False
        if not os.path.isdir(os.path.dirname(destfile)):
            iutil.mkdirChain(os.path.dirname(destfile))
        shutil.copy(file, destfile)
        return True

    def copyConfigToPath(self, instPath=''):

        if len(self.netdevices) == 0:
            return

        # /etc/sysconfig/network-scripts/ifcfg-DEVICE
        # /etc/dhcp/dhclient-DEVICE.conf
        # TODORV: do we really don't want overwrite on live cd?
        for devName, device in self.netdevices.items():
            self._copyFileToPath(device.path, instPath)
            dhclientfile = os.path.join("/etc/dhcp/dhclient-%s.conf" % devName)
            self._copyFileToPath(dhclientfile, instPath)

        # /etc/sysconfig/network
        self._copyFileToPath(networkConfFile, instPath,
                             overwrite=flags.livecdInstall)

        # /etc/resolv.conf
        self._copyFileToPath("/etc/resolv.conf", instPath,
                             overwrite=flags.livecdInstall)

        # /etc/udev/rules.d/70-persistent-net.rules
        self._copyFileToPath("/etc/udev/rules.d/70-persistent-net.rules",
                             instPath, overwrite=flags.livecdInstall)

        self._copyFileToPath(ipv6ConfFile, instPath,
                             overwrite=flags.livecdInstall)

    def disableNMForStorageDevices(self, anaconda, instPath=''):
        for devName, device in self.netdevices.items():
            if (device.usedByFCoE(anaconda) or
                device.usedByRootOnISCSI(anaconda)):
                devNames = [devName]
                # for vlan configured in ibft turn off NM also for parent
                if device.get("TYPE") == "Vlan" and device.get("BOOTPROTO") == "ibft":
                    devNames.append(devName.split(".")[0])
                for name in devNames:
                    dev = NetworkDevice(instPath + netscriptsDir, name)
                    if os.access(dev.path, os.R_OK):
                        dev.loadIfcfgFile()
                        dev.set(('NM_CONTROLLED', 'no'))
                        dev.writeIfcfgFile()
                        log.info("network device %s used by storage will not be "
                                 "controlled by NM" % device.path)
                    else:
                        log.warning("disableNMForStorageDevices: %s file not found" %
                                    device.path)


    def autostartFCoEDevices(self, anaconda, instPath=''):
        for devName, device in self.netdevices.items():
            if device.usedByFCoE(anaconda):
                dev = NetworkDevice(instPath + netscriptsDir, devName)
                if os.access(dev.path, os.R_OK):
                    dev.loadIfcfgFile()
                    dev.set(('ONBOOT', 'yes'))
                    dev.writeIfcfgFile()
                    log.debug("setting ONBOOT=yes for network device %s used by fcoe"
                              % device.path)
                else:
                    log.warning("autoconnectFCoEDevices: %s file not found" %
                                device.path)

    def enableBondingDevice(self, devName, instPath=''):
        dev = NetworkDevice(instPath + netscriptsDir, devName)
        self.netdevices[devName] = dev
        dev.set(("DEVICE", devName))
        dev.set(("TYPE", "Bond"))
        dev.set(("NM_CONTROLLED", "yes"))
        if not os.access(dev.path, os.R_OK):
            f = open(dev.path, "w")
            f.close()
        dev.writeIfcfgFile()
        return dev

    def hasActiveIPoIBDevice(self):
        active_devs = getActiveNetDevs()
        for devName, device in self.netdevices.items():
            if (devName in active_devs and
                device.get('TYPE') == 'Infiniband'):
                return True
        return False

    def hasVlanDevice(self):
        return any(dev for dev in self.netdevices.values()
                   if dev.get('TYPE') == 'Vlan')

    def hasBondDevice(self):
        return any (dev for dev in self.netdevices.values()
                    if dev.get('TYPE') == 'Bond')

    def write(self):

        ifcfglog.debug("Network.write() called")

        devices = self.netdevices.values()

        if len(devices) == 0:
            return

        # /etc/sysconfig/network-scripts/ifcfg-*
        for dev in devices:
            device = dev.get('DEVICE')

            bootproto = dev.get('BOOTPROTO').lower()
            # write out the hostname as DHCP_HOSTNAME if given (#81613)
            if (bootproto == 'dhcp' and self.hostname and
                self.overrideDHCPhostname):
                dev.set(('DHCP_HOSTNAME', self.hostname))

            dev.writeIfcfgFile()

            # XXX: is this necessary with NetworkManager?
            # handle the keys* files if we have those
            if dev.get("KEY"):
                cfgfile = "%s/keys-%s" % (netscriptsDir, device,)

                newkey = "%s/keys-%s.new" % (netscriptsDir, device,)
                f = open(newkey, "w")
                f.write("KEY=%s\n" % (dev.get('KEY'),))
                f.close()
                os.chmod(newkey, 0600)

                destkey = "%s/keys-%s" % (netscriptsDir, device,)
                shutil.move(newkey, destkey)


        # /etc/sysconfig/network
        newnetwork = "%s.new" % (networkConfFile)

        f = open(newnetwork, "w")
        f.write("NETWORKING=yes\n")
        f.write("HOSTNAME=")

        # use instclass hostname if set(kickstart) to override
        if self.hostname:
            f.write(self.hostname + "\n")
        else:
            f.write("localhost.localdomain\n")

        if self.ipv6_defaultgw:
            f.write("IPV6_DEFAULTGW=%s\n" % self.ipv6_defaultgw)

        if self.hasBondDevice() or self.hasVlanDevice():
            f.write("NM_BOND_VLAN_ENABLED=yes\n")

        f.close()
        shutil.move(newnetwork, networkConfFile)

        # /etc/resolv.conf is managed by NM

        # disable ipv6
        if ('noipv6' in flags.cmdline
            and not [dev for dev in devices
                     if dev.get('IPV6INIT') == "yes"]):
            if os.path.exists(ipv6ConfFile):
                log.debug('%s exists' % ipv6ConfFile)
            else:
                log.info('Disabling ipv6 on target system')
                f = open(ipv6ConfFile, "w")
                f.write("# Anaconda disabling ipv6\n")
                f.write("options ipv6 disable=1\n")
                f.close()

    def waitForDevice(self, device, timeout=CONNECTION_TIMEOUT):
        props = isys.getDeviceProperties(device)
        i = 0
        while not props and i < timeout:
            props = isys.getDeviceProperties(device)
            i += 1
            time.sleep(1)
        return bool(props)

    def waitForDevicesActivation(self, devices):
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
        reset_resolver = False
        while True:
            for dev, device_props_iface in waited_devs_props.items():
                state = device_props_iface.Get(isys.NM_DEVICE_IFACE, "State")
                if state == isys.NM_DEVICE_STATE_ACTIVATED:
                    waited_devs_props.pop(dev)
                    reset_resolver = True
            if len(waited_devs_props) == 0 or i >= CONNECTION_TIMEOUT:
                break
            i += 1
            time.sleep(1)

        if reset_resolver:
            isys.resetResolv()
        return waited_devs_props.keys()

    # write out current configuration state and wait for NetworkManager
    # to bring the device up, watch NM state and return to the caller
    # once we have a state
    def waitForConnection(self):
        bus = dbus.SystemBus()
        nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
        props = dbus.Interface(nm, isys.DBUS_PROPS_IFACE)

        i = 0
        while i < CONNECTION_TIMEOUT:
            state = props.Get(isys.NM_SERVICE, "State")
            if int(state) == isys.NM_STATE_CONNECTED:
                isys.resetResolv()
                return True
            i += 1
            time.sleep(1)

        state = props.Get(isys.NM_SERVICE, "State")
        if int(state) == isys.NM_STATE_CONNECTED:
            isys.resetResolv()
            return True

        return False

    # write out current configuration state and wait for NetworkManager
    # to bring the device up, watch NM state and return to the caller
    # once we have a state
    def bringUp(self):
        self.write()
        return self.waitForConnection()

    def disconnectDevice(self, devname):
        bus = dbus.SystemBus()
        nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
        device_paths = nm.get_dbus_method("GetDevices")()
        for device_path in device_paths:
            device = bus.get_object(isys.NM_SERVICE, device_path)
            device_props_iface = dbus.Interface(device, isys.DBUS_PROPS_IFACE)
            iface = str(device_props_iface.Get(isys.NM_DEVICE_IFACE, "Interface"))
            if iface == devname:
                try:
                    device.get_dbus_method("Disconnect")()
                except dbus.DBusException as e:
                    log.debug("disconnectDevice %s: %s" % (devname, e))
                    return False
                return True
        return False

    def ibftIfaces(self):
        ifaces = []
        for devname, device in self.netdevices.items():
            if device.get("BOOTPROTO") == "ibft":
                ifaces.append(devname)
        return ifaces

    # get a kernel cmdline string for dracut needed for access to host host
    def dracutSetupArgs(self, networkStorageDevice):
        netargs=set()

        if networkStorageDevice.nic == "default" or ":" in networkStorageDevice.nic:
            if getattr(networkStorageDevice, 'ibft', False):
                nics = self.ibftIfaces()
            else:
                nics = [ifaceForHostIP(networkStorageDevice.host_address)]
            if not nics:
                return ""
        else:
            nics = [networkStorageDevice.nic]

        for nic in nics:
            if nic not in self.netdevices.keys():
                log.error('Unknown network interface: %s' % nic)
                return ""

            dev = self.netdevices[nic]

            if dev.get('BOOTPROTO') == 'ibft':
                netargs.add("ip=ibft")
            elif networkStorageDevice.host_address:
                if self.hostname:
                    hostname = self.hostname
                else:
                    hostname = ""

                # if using ipv6
                if ':' in networkStorageDevice.host_address:
                    if dev.get('DHCPV6C') == "yes":
                        # XXX combination with autoconf not yet clear,
                        # support for dhcpv6 is not yet implemented in NM/ifcfg-rh
                        netargs.add("ip=%s:dhcp6" % nic)
                    elif dev.get('IPV6_AUTOCONF') == "yes":
                        netargs.add("ip=%s:auto6" % nic)
                    elif dev.get('IPV6ADDR'):
                        ipaddr = "[%s]" % dev.get('IPV6ADDR')
                        if dev.get('IPV6_DEFAULTGW'):
                            gateway = "[%s]" % dev.get('IPV6_DEFAULTGW')
                        else:
                            gateway = ""
                        netargs.add("ip=%s::%s:%s:%s:%s:none" % (ipaddr, gateway,
                                dev.get('PREFIX'), hostname, nic))
                else:
                    if dev.get('bootproto').lower() == 'dhcp':
                        netargs.add("ip=%s:dhcp" % nic)
                    else:
                        if dev.get('GATEWAY'):
                            gateway = dev.get('GATEWAY')
                        else:
                            gateway = ""

                        netmask = dev.get('netmask')
                        prefix  = dev.get('prefix')
                        if not netmask and prefix:
                            netmask = isys.prefix2netmask(int(prefix))

                        netargs.add("ip=%s::%s:%s:%s:%s:none" % (dev.get('ipaddr'),
                                gateway, netmask, hostname, nic))

            # ifname= prevents dracut from renaming the devices configured with ip=ibft
            # to ibftX on installed system
            hwaddr = dev.get("HWADDR")
            if hwaddr:
                netargs.add("ifname=%s:%s" % (nic, hwaddr.lower()))
            # For vlan devices configured in ibft we need to bind name of the parent
            if dev.get('BOOTPROTO') == 'ibft' and dev.get("TYPE") == "Vlan":
                parent_nic = nic.split(".")[0]
                parent_dev = self.netdevices[parent_nic]
                parent_hwaddr = parent_dev.get("HWADDR")
                netargs.add("ifname=%s:%s" % (parent_nic, parent_hwaddr.lower()))

            nettype = dev.get("NETTYPE")
            subchannels = dev.get("SUBCHANNELS")
            if iutil.isS390() and nettype and subchannels:
                znet = "rd_ZNET=%s,%s" % (nettype, subchannels)

                options = dev.get("OPTIONS").strip("'\"")
                if options:
                    options = filter(lambda x: x != '', options.split(' '))
                    znet += ",%s" % (','.join(options))
                netargs.add(znet)

        return netargs

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

def saveExceptionEnableNetwork(intf):
    if not hasActiveNetDev():
        if intf.messageWindow(_("Warning"),
               _("You do not have an active network connection.  This is "
                 "required by some exception saving methods.  Would you "
                 "like to configure your network now?"),
               type = "yesno"):

            if not intf.enableNetwork():
                intf.messageWindow(_("No Network Available"),
                                   _("Remote exception saving methods will not work."))
            else:
                urlgrabber.grabber.reset_curl_obj()
