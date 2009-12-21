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
from flags import flags
from simpleconfig import SimpleConfigFile

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

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
    bus = dbus.SystemBus()
    nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
    nm_props_iface = dbus.Interface(nm, isys.DBUS_PROPS_IFACE)

    active_connections = nm_props_iface.Get(isys.NM_MANAGER_IFACE, "ActiveConnections")

    # XXX: account for Ip6Config objects when NetworkManager supports them
    for connection in active_connections:
        active_connection = bus.get_object(isys.NM_SERVICE, connection)
        active_connection_props_iface = dbus.Interface(active_connection, isys.DBUS_PROPS_IFACE)
        devices = active_connection_props_iface.Get(isys.NM_MANAGER_IFACE, 'Devices')

        for device_path in devices:
            device = bus.get_object(isys.NM_SERVICE, device_path)
            device_props_iface = dbus.Interface(device, isys.DBUS_PROPS_IFACE)

            ip4_config_path = device_props_iface.Get(isys.NM_MANAGER_IFACE, 'Ip4Config')
            ip4_config_obj = bus.get_object(isys.NM_SERVICE, ip4_config_path)
            ip4_config_props = dbus.Interface(ip4_config_obj, isys.DBUS_PROPS_IFACE)

            # addresses (3-element list:  ipaddr, netmask, gateway)
            addrs = ip4_config_props.Get(isys.NM_MANAGER_IFACE, "Addresses")[0]
            try:
                tmp = struct.pack('I', addrs[0])
                ipaddr = socket.inet_ntop(socket.AF_INET, tmp)
                hinfo = socket.gethostbyaddr(ipaddr)

                if len(hinfo) == 3:
                    hn = hinfo[0]
                else:
                    continue
            except:
                continue

    if hn and hn != 'localhost' and hn != 'localhost.localdomain':
        return hn

    try:
        hn = anaconda.network.hostname
    except:
        hn = None

    if not hn or hn == '(none)' or hn == 'localhost' or hn == 'localhost.localdomain':
        hn = socket.gethostname()

    if not hn or hn == '(none)' or hn == 'localhost':
        hn = 'localhost.localdomain'

    return hn

# return if the device is of a type that requires a ptpaddr to be specified
def isPtpDev(devname):
    if devname.startswith("ctc"):
        return True
    return False

def _anyUsing(method):
    # method names that NetworkManager might use
    if method == 'auto':
        methods = (method, 'dhcp')
    else:
        methods = (method)

    try:
        bus = dbus.SystemBus()
        nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
        nm_props_iface = dbus.Interface(nm, isys.DBUS_PROPS_IFACE)
        active_connections = nm_props_iface.Get(isys.NM_MANAGER_IFACE, "ActiveConnections")

        for path in active_connections:
            active = bus.get_object(isys.NM_SERVICE, path)
            active_props_iface = dbus.Interface(active, isys.DBUS_PROPS_IFACE)

            active_service_name = active_props_iface.Get(isys.NM_ACTIVE_CONNECTION_IFACE, "ServiceName")
            active_path = active_props_iface.Get(isys.NM_ACTIVE_CONNECTION_IFACE, "Connection")

            connection = bus.get_object(active_service_name, active_path)
            connection_iface = dbus.Interface(connection, isys.NM_CONNECTION_IFACE)
            settings = connection_iface.GetSettings()

            # XXX: add support for Ip6Config when it appears
            ip4_setting = settings['ipv4']
            if not ip4_setting or not ip4_setting['method'] or ip4_setting['method'] in methods:
                return True

            return False
    except:
        return False

# determine whether any active at boot devices are using dhcp or dhcpv6
def anyUsingDHCP():
    return _anyUsing('auto')

# determine whether any active at boot devices are using static IP config
def anyUsingStatic():
    return _anyUsing('manual')

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
        devices = active_connection_props_iface.Get(isys.NM_MANAGER_IFACE, 'Devices')

        for device_path in devices:
            device = bus.get_object(isys.NM_SERVICE, device_path)
            device_props_iface = dbus.Interface(device, isys.DBUS_PROPS_IFACE)

            interface_name = device_props_iface.Get(isys.NM_MANAGER_IFACE, 'Interface')
            active_devs.add(interface_name)

    ret = list(active_devs)
    ret.sort()
    return ret

class NetworkDevice(SimpleConfigFile):
    def __str__(self):
        s = ""
        s = s + "DEVICE=" + self.info["DEVICE"] + "\n"
        keys = self.info.keys()
        keys.sort()
        keys.remove("DEVICE")
        if "DESC" in keys:
            keys.remove("DESC")
        if "KEY" in keys:
            keys.remove("KEY")
        if iutil.isS390() and ("OPTIONS" in keys) and ("HWADDR" in keys) and \
           (self.info["OPTIONS"].find("layer2=1") != -1):
            keys.remove("HWADDR")

        for key in keys:
            if (key == 'NAME') or \
               (key == 'NM_CONTROLLED' and not flags.livecdInstall):
                continue
            # make sure we include autoneg in the ethtool line
            elif key == 'ETHTOOL_OPTS' and self.info[key].find("autoneg")== -1:
                s = s + key + """="autoneg off %s"\n""" % (self.info[key])
            elif self.info[key] is not None:
                s = s + key + "=" + self.info[key] + "\n"

        return s

    def __init__(self, dev):
        self.info = { "DEVICE" : dev }
        if dev.startswith('ctc'):
            self.info["TYPE"] = "CTC"

class Network:
    def __init__(self):
        self.netdevices = {}
        self.ksdevice = None
        self.domains = []
        self.hostname = socket.gethostname()
        self.overrideDHCPhostname = False

        # populate self.netdevices
        devhash = isys.getDeviceProperties(dev=None)
        for dev in devhash.keys():
            self.netdevices[dev] = NetworkDevice(dev)
            ifcfg_contents = self.readIfcfgContents(dev)

            # if NM_CONTROLLED is set to yes, we read in settings from
            # NetworkManager first, then fill in the gaps with the data
            # from the ifcfg file
            useNetworkManager = False
            if ifcfg_contents.has_key('NM_CONTROLLED') and \
               not ifcfg_contents['NM_CONTROLLED'].lower() == 'no':
                useNetworkManager = True

            # this interface is managed by NetworkManager, so read from
            # NetworkManager first
            if useNetworkManager:
                props = devhash[dev]

                if isys.isDeviceDHCP(dev):
                    self.netdevices[dev].set(('BOOTPROTO', 'dhcp'))
                else:
                    self.netdevices[dev].unset('BOOTPROTO')
                    bus = dbus.SystemBus()
                    config_path = props.Get(isys.NM_MANAGER_IFACE, 'Ip4Config')
                    config = bus.get_object(isys.NM_SERVICE, config_path)
                    config_props = dbus.Interface(config, isys.DBUS_PROPS_IFACE)

                    # addresses (3-element list:  ipaddr, netmask, gateway)
                    addrs = config_props.Get(isys.NM_MANAGER_IFACE, 'Addresses')[0]
                    try:
                        tmp = struct.pack('I', addrs[0])
                        ipaddr = socket.inet_ntop(socket.AF_INET, tmp)
                        self.netdevices[dev].set(('IPADDR', ipaddr))
                    except:
                        pass

                    try:
                        tmp = struct.pack('I', addrs[1])
                        netmask = socket.inet_ntop(socket.AF_INET, tmp)
                        self.netdevices[dev].set(('NETMASK', netmask))
                    except:
                        pass

                    try:
                        tmp = struct.pack('I', addrs[2])
                        gateway = socket.inet_ntop(socket.AF_INET, tmp)
                        self.netdevices[dev].set(('GATEWAY', gateway))
                    except:
                        pass

                self.hostname = socket.gethostname()

            # read in remaining settings from ifcfg file
            for key in ifcfg_contents.keys():
                if key == 'GATEWAY':
                    self.netdevices[dev].set((key, ifcfg_contents[key]))
                elif key == 'DOMAIN':
                    self.domains.append(ifcfg_contents[key])
                elif key == 'HOSTNAME':
                    self.hostname = ifcfg_contents[key]
                elif self.netdevices[dev].get(key) == '':
                    self.netdevices[dev].set((key, ifcfg_contents[key]))

        # now initialize remaining devices
        # XXX we just throw return away, the method initialize a
        # object member so we dont need to
        available_devices = self.available()

        if len(available_devices) > 0:
            # set first device to start up onboot
            oneactive = 0
            for dev in available_devices.keys():
                try:
                    if available_devices[dev].get("ONBOOT") == "yes":
                        oneactive = 1
                        break
                except:
                    continue

    def readIfcfgContents(self, dev):
        ifcfg = "/etc/sysconfig/network-scripts/ifcfg-%s" % (dev,)
        contents = {}

        try:
            f = open(ifcfg, "r")
            lines = f.readlines()
            f.close()

            for line in lines:
                line = line.strip()
                if line.startswith('#') or line == '':
                    continue

                var = string.splitfields(line, '=', 1)
                if len(var) == 2:
                    var[1] = var[1].replace('"', '')
                    contents[var[0]] = string.strip(var[1])
        except:
            return {}

        return contents

    def getDevice(self, device):
        return self.netdevices[device]

    def available(self):
        ksdevice = None
        if flags.cmdline.has_key('ksdevice'):
            ksdevice = flags.cmdline['ksdevice']

        for dev in isys.getDeviceProperties().keys():
            if not self.netdevices.has_key(dev):
                self.netdevices[dev] = NetworkDevice(dev)

            hwaddr = isys.getMacAddress(dev)

            self.netdevices[dev].set(('HWADDR', hwaddr))
            self.netdevices[dev].set(('DESC', isys.getNetDevDesc(dev)))

            if not ksdevice:
                continue

            if ksdevice == 'link' and isys.getLinkStatus(dev):
                self.ksdevice = dev
            elif ksdevice == dev:
                self.ksdevice = dev
            elif ksdevice.find(':') != -1:
                if ksdevice.upper() == hwaddr:
                    self.ksdevice = dev

        return self.netdevices

    def getKSDevice(self):
        if self.ksdevice is None:
            return None

        try:
            return self.netdevices[self.ksdevice]
        except:
            return None

    def setHostname(self, hn):
        self.hostname = hn

    def setDNS(self, ns, device):
        dns = ns.split(',')
        i = 1
        for addr in dns:
            addr = addr.strip()
            dnslabel = "DNS%d" % (i,)
            self.netdevices[device].set((dnslabel, addr))
            i += 1

    def setGateway(self, gw, device):
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

    def writeKS(self, f):
        devNames = self.netdevices.keys()
        devNames.sort()

        if len(devNames) == 0:
            return

        for devName in devNames:
            dev = self.netdevices[devName]

            if dev.get('bootproto').lower() == 'dhcp' or dev.get('ipaddr'):
                f.write("network --device %s" % dev.get('device'))

                if dev.get('MTU') and dev.get('MTU') != 0:
                    f.write(" --mtu=%s" % dev.get('MTU'))

                onboot = dev.get("onboot")
                if onboot and onboot == "no":
                    f.write(" --onboot no")
                if dev.get('bootproto').lower() == 'dhcp':
                    f.write(" --bootproto dhcp")
                    if dev.get('dhcpclass'):
                        f.write(" --dhcpclass %s" % dev.get('dhcpclass'))
                    if self.overrideDHCPhostname:
                        if (self.hostname and
                            self.hostname != "localhost.localdomain"):
                            f.write(" --hostname %s" % self.hostname)
                else:
                    f.write(" --bootproto static --ip %s" % dev.get('ipaddr'))

                    if dev.get('netmask'):
                        f.write(" --netmask %s" % dev.get('netmask'))

                    if dev.get('GATEWAY'):
                        f.write(" --gateway %s" % (dev.get('GATEWAY'),))

                    dnsline = ''
                    for key in dev.info.keys():
                        if key.upper().startswith('DNS'):
                            if dnsline == '':
                                dnsline = dev.get(key)
                            else:
                                dnsline += "," + dev.get(key)

                    if dnsline != '':
                        f.write(" --nameserver %s" % (dnsline,))

                    if (self.hostname and
                        self.hostname != "localhost.localdomain"):
                        f.write(" --hostname %s" % self.hostname)

                f.write("\n")

    def hasNameServers(self, hash):
        if hash.keys() == []:
            return False

        for key in hash.keys():
            if key.upper().startswith('DNS'):
                return True

        return False

    def write(self, instPath='', anaconda=None, devices=None):

        if devices is None:
            devices = self.netdevices.values()

        if len(devices) == 0:
            return

        sysconfig = "%s/etc/sysconfig" % (instPath,)
        netscripts = "%s/network-scripts" % (sysconfig,)
        destnetwork = "%s/network" % (sysconfig,)

        if not os.path.isdir(netscripts):
            iutil.mkdirChain(netscripts)

        # /etc/sysconfig/network-scripts/ifcfg-*
        for dev in devices:
            device = dev.get('DEVICE')

            cfgfile = "%s/ifcfg-%s" % (netscripts, device,)
            if (instPath) and (os.path.isfile(cfgfile)):
                continue

            bootproto = dev.get('BOOTPROTO').lower()
            ipv6addr = dev.get('IPV6ADDR').lower()
            ipv6prefix = dev.get('IPV6PREFIX').lower()
            ipv6autoconf = dev.get('IPV6_AUTOCONF').lower()
            dhcpv6c = dev.get('DHCPV6C').lower()

            newifcfg = "/tmp/ifcfg-%s.new" % (device,)
            f = open(newifcfg, "w")
            if len(dev.get("DESC")) > 0:
                f.write("# %s\n" % (dev.get("DESC"),))

            # if bootproto is dhcp, unset any static settings (#218489)
            # *but* don't unset if either IPv4 or IPv6 is manual (#433290)
            if bootproto == 'dhcp':
                dev.unset('IPADDR')
                dev.unset('NETMASK')
                dev.unset('GATEWAY')

            # handle IPv6 settings correctly for the ifcfg file
            dev.unset('IPV6ADDR')
            dev.unset('IPV6PREFIX')

            if ipv6addr == 'dhcp':
                dev.set(('IPV6INIT', 'yes'))
                dev.set(('DHCPV6C', 'yes'))
            elif ipv6addr != '' and ipv6addr is not None:
                dev.set(('IPV6INIT', 'yes'))

                if ipv6prefix != '' and ipv6prefix is not None:
                    dev.set(('IPV6ADDR', ipv6addr + '/' + ipv6prefix))
                else:
                    dev.set(('IPV6ADDR', ipv6addr))

            if dev.get('IPV6_AUTOCONF').lower() == 'yes':
                dev.set(('IPV6INIT', 'yes'))

            f.write(str(dev))

            # write out the hostname as DHCP_HOSTNAME if given (#81613)
            if (bootproto == 'dhcp' and self.hostname and
                self.overrideDHCPhostname):
                f.write("DHCP_HOSTNAME=%s\n" %(self.hostname,))

            if dev.get('MTU') and dev.get('MTU') != 0:
                f.write("MTU=%s\n" % dev.get('MTU'))

            # tell NetworkManager not to touch any interfaces used during
            # installation when / is on a network backed device.
            if anaconda is not None:
                import storage
                rootdev = anaconda.storage.rootDevice
                # FIXME: use d.host_address to only add "NM_CONTROLLED=no"
                # for interfaces actually used enroute to the device
                for d in anaconda.storage.devices:
                    if isinstance(d, storage.devices.NetworkStorageDevice) and\
                       (rootdev.dependsOn(d) or d.nic == device):
                        f.write("NM_CONTROLLED=no\n")
                        break

            f.close()
            os.chmod(newifcfg, 0644)

            # move the new ifcfg in place
            destcfg = "%s/ifcfg-%s" % (netscripts, device,)
            try:
                os.remove(destcfg)
            except OSError as e:
                if e.errno != 2:
                    raise
            shutil.move(newifcfg, destcfg)

            # XXX: is this necessary with NetworkManager?
            # handle the keys* files if we have those
            if dev.get("KEY"):
                cfgfile = "%s/keys-%s" % (netscripts, device,)
                if not instPath == '' and os.path.isfile(cfgfile):
                    continue

                newkey = "%s/keys-%s.new" % (netscripts, device,)
                f = open(newkey, "w")
                f.write("KEY=%s\n" % (dev.get('KEY'),))
                f.close()
                os.chmod(newkey, 0600)

                destkey = "%s/keys-%s" % (netscripts, device,)
                shutil.move(newkey, destkey)

            # /etc/dhclient-DEVICE.conf
            dhclientconf = '/etc/dhclient-' + device + '.conf'
            if os.path.isfile(dhclientconf):
                destdhclientconf = '%s%s' % (instPath, dhclientconf,)
                try:
                    shutil.copy(dhclientconf, destdhclientconf)
                except:
                    log.warning("unable to copy %s to target system" % (dhclientconf,))

        # /etc/sysconfig/network
        if (not instPath) or (not os.path.isfile(destnetwork)) or flags.livecdInstall:
            newnetwork = "%s.new" % (destnetwork,)

            f = open(newnetwork, "w")
            f.write("NETWORKING=yes\n")
            f.write("HOSTNAME=")

            # use instclass hostname if set(kickstart) to override
            if self.hostname:
                f.write(self.hostname + "\n")
            else:
                f.write("localhost.localdomain\n")

            if dev.get('GATEWAY'):
                f.write("GATEWAY=%s\n" % (dev.get('GATEWAY'),))

            if dev.get('IPV6_DEFAULTGW'):
                f.write("IPV6_DEFAULTGW=%s\n" % (dev.get('IPV6_DEFAULTGW'),))

            f.close()
            shutil.move(newnetwork, destnetwork)

        # If the hostname was not looked up, but typed in by the user,
        # domain might not be computed, so do it now.
        domainname = None
        if "." in self.hostname:
            fqdn = self.hostname
        else:
            fqdn = socket.getfqdn(self.hostname)

        if fqdn in [ "localhost.localdomain", "localhost",
                     "localhost6.localdomain6", "localhost6",
                     self.hostname ] or "." not in fqdn:
            fqdn = None

        if fqdn:
            domainname = fqdn.split('.', 1)[1]
            if domainname in [ "localdomain", "localdomain6" ]:
                domainname = None
        else:
            domainname = None

        if self.domains == ["localdomain"] or not self.domains:
            if domainname:
                self.domains = [domainname]

        # /etc/resolv.conf
        if (not instPath) or (not os.path.isfile(instPath + '/etc/resolv.conf')) or flags.livecdInstall:
            if os.path.isfile('/etc/resolv.conf') and instPath != '':
                destresolv = "%s/etc/resolv.conf" % (instPath,)
                shutil.copy('/etc/resolv.conf', destresolv)
            elif (self.domains != ['localdomain'] and self.domains) or \
                self.hasNameServers(dev.info):
                resolv = "%s/etc/resolv.conf" % (instPath,)

                f = open(resolv, "w")

                if self.domains != ['localdomain'] and self.domains:
                    f.write("search %s\n" % (string.joinfields(self.domains, ' '),))

                for key in dev.info.keys():
                    if key.upper().startswith('DNS'):
                        f.write("nameserver %s\n" % (dev.get(key),))

                f.close()

        # /etc/udev/rules.d/70-persistent-net.rules
        rules = "/etc/udev/rules.d/70-persistent-net.rules"
        destRules = instPath + rules
        if (not instPath) or (not os.path.isfile(destRules)) or \
           flags.livecdInstall:
            if not os.path.isdir("%s/etc/udev/rules.d" %(instPath,)):
                iutil.mkdirChain("%s/etc/udev/rules.d" %(instPath,))

            if os.path.isfile(rules) and rules != destRules:
                shutil.copy(rules, destRules)
            else:
                f = open(destRules, "w")
                f.write("""
# This file was automatically generated by the /lib/udev/write_net_rules
# program run by the persistent-net-generator.rules rules file.
#
# You can modify it, as long as you keep each rule on a single line.

""")
                for dev in self.netdevices.values():
                    addr = dev.get("HWADDR")
                    if not addr:
                        continue
                    devname = dev.get("DEVICE")
                    basename = devname
                    while basename != "" and basename[-1] in string.digits:
                        basename = basename[:-1]

                    # rules are case senstive for address. Lame.
                    addr = addr.lower()

                    s = ""
                    if len(dev.get("DESC")) > 0:
                        s = "# %s (rule written by anaconda)\n" % (dev.get("DESC"),)
                    else:
                        s = "# %s (rule written by anaconda)\n" % (devname,)
                        s = s + 'SUBSYSTEM==\"net\", ACTION==\"add\", DRIVERS=="?*", ATTR{address}=="%s", ATTR{type}=="1", KERNEL=="%s*", NAME="%s"\n' % (addr, basename, devname,)

                    f.write(s)

                f.close()

    # write out current configuration state and wait for NetworkManager
    # to bring the device up, watch NM state and return to the caller
    # once we have a state
    def bringUp(self, devices=None):
        self.write(devices=devices)

        bus = dbus.SystemBus()
        nm = bus.get_object(isys.NM_SERVICE, isys.NM_MANAGER_PATH)
        props = dbus.Interface(nm, isys.DBUS_PROPS_IFACE)

        i = 0
        while i < 45:
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

    # get a kernel cmdline string for dracut needed for access to host host
    def dracutSetupString(self, networkStorageDevice):
        netargs=""

        if networkStorageDevice.nic:
            # Storage bound to a specific nic (ie FCoE)
            nic = networkStorageDevice.nic
        else:
            # Storage bound through ip, find out which interface leads to host
            host = networkStorageDevice.host_address
            route = iutil.execWithCapture("ip", [ "route", "get", "to", host ])
            if not route:
                log.error("Could net get interface for route to %s" % host)
                return ""

            routeInfo = route.split()
            if routeInfo[0] != host or len(routeInfo) < 5:
                log.error('Unexpected "ip route get to %s" reply: %s' %
                          (host, routeInfo))
                return ""

            nic = routeInfo[2]

        if nic not in self.netdevices.keys():
            log.error('Unknown network interface: %s' % nic)
            return ""

        dev = self.netdevices[nic]

        if networkStorageDevice.host_address:
            if dev.get('bootproto').lower() == 'dhcp':
                netargs += "ip=%s:dhcp" % nic
            else:
                if dev.get('GATEWAY'):
                    gateway = dev.get('GATEWAY')
                else:
                    gateway = ""

                if self.hostname:
                    hostname = self.hostname
                else:
                    hostname = ""

                netargs += "ip=%s::%s:%s:%s:%s:none" % (dev.get('ipaddr'),
                           gateway, dev.get('netmask'), hostname, nic)

        hwaddr = dev.get("HWADDR")
        if hwaddr:
            if netargs != "":
                netargs += " "

            netargs += "ifname=%s:%s" % (nic, hwaddr.lower())

        return netargs
