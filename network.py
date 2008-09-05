#
# network.py - network configuration install data
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008  Red Hat, Inc.
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
import isys
import iutil
import socket
import os
import minihal
import rhpl
import dbus
from flags import flags

from rhpl.simpleconfig import SimpleConfigFile

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

    # XXX: POSIX says this limit is 255, but Linux also defines HOST_NAME_MAX
    # as 64, so I don't know which we should believe.  --dcantrell
    if len(hostname) > 64:
	return _("Hostname must be 64 or fewer characters in length.")

    validStart = string.ascii_letters + string.digits
    validAll = validStart + ".-"

    if string.find(validStart, hostname[0]) == -1:
	return _("Hostname must start with a valid character in the ranges "
		 "'a-z', 'A-Z', or '0-9'")

    for i in range(1, len(hostname)):
	if string.find(validAll, hostname[i]) == -1:
	    return _("Hostnames can only contain the characters 'a-z', 'A-Z', '0-9', '-', or '.'")

    return None

# return if the device is of a type that requires a ptpaddr to be specified
def isPtpDev(devname):
    if (devname.startswith("ctc") or devname.startswith("iucv")):
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

        # Don't let onboot be turned on unless we have config information
        # to go along with it
        proto = self.get('bootproto') or ""
        if proto.lower() != 'dhcp' and not self.get('ipaddr'):
            forceOffOnBoot = 1
        else:
            forceOffOnBoot = 0

        onBootWritten = 0
        for key in keys:
            if key in ("USEIPV4", "USEIPV6"): # XXX: these are per-device, but not written out
                continue
            if key == 'ONBOOT' and forceOffOnBoot:
                s = s + key + "=" + 'no' + "\n"
            # make sure we include autoneg in the ethtool line
            elif key == 'ETHTOOL_OPTS' and self.info[key].find("autoneg")== -1:
                s = s + key + """="autoneg off %s"\n""" % (self.info[key])
            elif self.info[key] is not None:
                s = s + key + "=" + self.info[key] + "\n"

            if key == 'ONBOOT':
                onBootWritten = 1

        if not onBootWritten:
            s = s + 'ONBOOT=no\n'

        return s

    def __init__(self, dev):
        self.info = { "DEVICE" : dev }
	if dev.startswith('ctc'):
	    self.info["TYPE"] = "CTC"
	elif dev.startswith('iucv'):
	    self.info["TYPE"] = "IUCV"

class Network:
    def __init__(self):
	self.firstnetdevice = None
        self.netdevices = {}
        self.gateway = ""
        self.primaryNS = ""
        self.secondaryNS = ""
        self.domains = []
        self.hostname = socket.gethostname()

        # populate self.netdevices
        devhash = isys.getDeviceProperties(dev=None)
        for dev in devhash.keys():
            self.netdevices[dev] = NetworkDevice(dev)
            ifcfg_contents = {}

            # try to read settings from ifcfg-* file
            try:
                ifcfg = "/etc/sysconfig/network-scripts/ifcfg-%s" % (dev,)
                f = open(f, "r")
                lines = f.readlines()
                f.close()

                for line in lines:
                    var = string.splitfields(line, '=')
                    if len(var) >= 2:
                        ifcfg_contents[var[0]] = string.strip(var[1])
            except:
                pass

            # if NM_CONTROLLED is set to yes, we read in settings from
            # NetworkManager first, then fill in the gaps with the data
            # from the ifcfg file
            useNetworkManager = False
            if ifcfg_contents.has_key('NM_CONTROLLED'):
                if ifcfg_contents['NM_CONTROLLED'].lower() == 'yes':
                    self.netdevices[dev].set(('NM_CONTROLLED', ifcfg_contents['NM_CONTROLLED']))
                    useNetworkManager = True

            # this interface is managed by NetworkManager, so read from
            # NetworkManager first
            if useNetworkManager:
                props = devhash[dev]
                active_service_name = props.Get(isys.NM_ACTIVE_CONNECTION_IFACE, 'ServiceName')
                active_path = props.Get(isys.NM_ACTIVE_CONNECTION_IFACE, 'Connection')

                connection = bus.get_object(active_service_name, active_path)
                connection_iface = dbus.Interface(connection, isys.NM_CONNECTION_IFACE)
                settings = connection_iface.GetSettings()

                ip4_setting = settings['ipv4']
                if not ip4_setting or not ip4_setting['method'] or \
                   ip4_setting['method'] == 'auto' or \
                   ip4_setting['method'] == 'dhcp':
                    self.netdevices[dev].set(('BOOTPROTO', 'dhcp'))
                else:
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
                        self.gateway = gateway
                    except:
                        pass

                self.hostname = socket.gethostname()

            # read in remaining settings from ifcfg file
            for key in ifcfg_contents.keys():
                if key == 'GATEWAY':
                    self.netdevices[dev].set((key, ifcfg_contents[key]))
                    self.gateway = ifcfg_contents[key]
                elif key == 'DOMAIN':
                    self.domains.append(ifcfg_contents[key])
                elif key == 'HOSTNAME':
                    self.hostname = ifcfg_contents[key]
                elif self.netdevices[dev].get(key) == '':
                    self.netdevices[dev].set((key, ifcfg_contents[key]))

            self.netdevices[dev].set(('useIPv4', flags.useIPv4))
            self.netdevices[dev].set(('useIPv6', flags.useIPv6))

            # XXX: fix this block
            if self.netdevices[dev].get('BOOTPROTO') == '':
                if self.netdevices[dev].get('IPADDR') == '':
                    self.netdevices[dev].set(('useIPv4', False))
                if (self.netdevices[dev].get('IPV6ADDR') == '' and \
                    self.netdevices[dev].get('IPV6_AUTOCONF') == '' and \
                    self.netdevices[dev].get('DHCPV6C') == ''):
                    self.netdevices[dev].set(('useIPv6', False))

        # XXX: this code needs to be improved too
	try:
	    f = open("/etc/resolv.conf", "r")
	except:
	    pass
	else:
	    lines = f.readlines()
	    f.close()
	    for line in lines:
		resolv = string.split(line)
		if resolv and resolv[0] == 'nameserver':
		    if self.primaryNS == "":
			self.primaryNS = resolv[1]
		    elif self.secondaryNS == "":
			self.secondaryNS = resolv[1]

	# now initialize remaining devices
	# XXX we just throw return away, the method initialize a
	# object member so we dont need to
	available_devices = self.available()

	if len(available_devices) > 0:
	    # set first device to start up onboot
	    oneactive = 0
	    for dev in available_devices.keys():
		try:
		    if available_devices[dev].get("onboot") == "yes":
			oneactive = 1
			break
		except:
		    continue

	    if not oneactive:
		self.netdevices[self.firstnetdevice].set(("onboot", "yes"))

    def getDevice(self, device):
	return self.netdevices[device]

    def getFirstDeviceName(self):
	return self.firstnetdevice

    def available(self):
        # XXX: this should use NetworkManager
        for device in minihal.get_devices_by_type("net"):
            if device.has_key('net.arp_proto_hw_id'):
                if device['net.arp_proto_hw_id'] == 1:
                    dev = device['device']
                    if not self.netdevices.has_key(dev):
                        self.netdevices[dev] = NetworkDevice(dev);
                    if self.firstnetdevice is None:
                        self.firstnetdevice = dev
                    self.netdevices[dev].set(('hwaddr', device['net.address']))
                    self.netdevices[dev].set(('desc', device['description']))

        ksdevice = None
        if flags.cmdline.has_key("ksdevice"):
            ksdevice = flags.cmdline["ksdevice"]

        if ksdevice and self.netdevices.get(ksdevice) != '':
            self.firstnetdevice = ksdevice

        return self.netdevices

    def setHostname(self, hn):
	self.hostname = hn

    def setDNS(self, ns):
        dns = ns.split(',')
        if len(dns) >= 1:
            self.primaryNS = dns[0]
        if len(dns) >= 2:
            self.secondaryNS = dns[1]

    def setGateway(self, gw):
        self.gateway = gw

    def lookupHostname(self):
	# can't look things up if they don't exist!
	if not self.hostname or self.hostname == "localhost.localdomain":
            return None
	if not self.primaryNS:
            return
        myns = self.primaryNS
	if not hasActiveNetDev():
	    for dev in self.netdevices.values():
                if (dev.get('bootproto').lower() == "dhcp" and
                    dev.get('onboot') == "yes"):
		    ret = isys.dhcpNetDevice(dev)
                    if ret is None:
                        continue
                    myns = ret
                    break
                elif (dev.get('ipaddr') and dev.get('netmask') and
                      self.gateway is not None and dev.get('onboot') == "yes"):
                    try:
                        isys.configNetDevice(dev, self.gateway)
                        break
                    except SystemError:
                        log.error("failed to configure network device %s when "
                                  "looking up host name", dev.get('device'))

            if hasActiveNetDev() and not flags.rootpath:
                f = open("/etc/resolv.conf", "w")
                f.write("nameserver %s\n" % myns)
                f.close()
                isys.resetResolv()
                isys.setResolvRetry(1)

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

    def nameservers(self):
        return (self.primaryNS, self.secondaryNS)

    def dnsString(self):
        str = ""
        for ns in self.nameservers():
            if not ns:
                continue
            if str: str = str + ","
            str = str + ns
        return str
            
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
			f.write(" --class %s" % dev.get('dhcpclass'))
		    if self.overrideDHCPhostname:
			if (self.hostname and
			    self.hostname != "localhost.localdomain"):
			    f.write(" --hostname %s" % self.hostname)
                else:
                    f.write(" --bootproto static --ip %s --netmask %s" % 
                       (dev.get('ipaddr'), dev.get('netmask')))

		    if self.gateway is not None:
			f.write(" --gateway %s" % (self.gateway,))

		    if self.dnsString():
                        f.write(" --nameserver %s" % (self.dnsString(),))
                        
		    if (self.hostname and
			self.hostname != "localhost.localdomain"):
			f.write(" --hostname %s" % self.hostname)

                f.write("\n");

    def write(self, instPath):
        # make sure the directory exists
        if not os.path.isdir("%s/etc/sysconfig/network-scripts" %(instPath,)):
            iutil.mkdirChain("%s/etc/sysconfig/network-scripts" %(instPath,))

        # /etc/sysconfig/network-scripts/ifcfg-*
        for dev in self.netdevices.values():
            device = dev.get('DEVICE')
            bootproto = dev.get('BOOTPROTO').lower()
            ipv6addr = dev.get('IPV6ADDR').lower()
            ipv6prefix = dev.get('IPV6PREFIX').lower()
            ipv6autoconf = dev.get('IPV6_AUTOCONF').lower()
            dhcpv6c = dev.get('DHCPV6C').lower()

            fn = "%s/etc/sysconfig/network-scripts/ifcfg-%s" % (instPath,
                                                                device)
            f = open(fn, "w")
            os.chmod(fn, 0644)
            if len(dev.get("DESC")) > 0:
                f.write("# %s\n" % (dev.get("DESC"),))

            # if bootproto is dhcp, unset any static settings (#218489)
            # *but* don't unset if either IPv4 or IPv6 is manual (#433290)
            if bootproto == 'dhcp' and \
               (ipv6addr == 'dhcp' or ipv6autoconf == 'yes'):
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
            if dev.get('dhcpclass'):
                f.write("DHCP_CLASSID=%s\n" % dev.get('dhcpclass'))

            if dev.get('MTU') and dev.get('MTU') != 0:
                f.write("MTU=%s\n" % dev.get('MTU'))

            # write per-interface DNS information for NetworkManager (#443244)
            dnsIndex = 1
            for ns in self.nameservers():
                if ns:
                    f.write("DNS%d=%s\n" % (dnsIndex, ns,))
                    dnsIndex += 1

            if self.domains != ['localdomain'] and self.domains:
                searchLine = string.joinfields(self.domains, ' ')
                f.write("SEARCH=\"%s\"\n" % (searchLine,))

            f.write("NM_CONTROLLED=yes\n")
            f.close()

            if dev.get("key"):
                fn = "%s/etc/sysconfig/network-scripts/keys-%s" % (instPath,
                                                                   device)
                f = open(fn, "w")
                os.chmod(fn, 0600)
                f.write("KEY=%s\n" % dev.get('key'))
                f.close()

        # /etc/sysconfig/network
        f = open(instPath + "/etc/sysconfig/network", "w")
        f.write("NETWORKING=yes\n")
        f.write("HOSTNAME=")

        # use instclass hostname if set(kickstart) to override
        if self.hostname:
            f.write(self.hostname + "\n")
        else:
            f.write("localhost.localdomain\n")

        if self.gateway:
            if self.gateway.find('.') != -1:
                f.write("GATEWAY=%s\n" % (self.gateway,))
                f.write("IPV6_DEFAULTGW=\n")
            elif self.gateway.find(':') != -1:
                f.write("GATEWAY=\n")
                f.write("IPV6_DEFAULTGW=%s\n" % (self.gateway,))

        f.close()

        # /etc/hosts
        f = open(instPath + "/etc/hosts", "w")
        localline = ""

        log.info("self.hostname = %s", self.hostname)

        ip = self.lookupHostname()
        l = string.split(self.hostname, ".")

        # If the hostname is not resolvable, tie it to 127.0.0.1
        if not ip and self.hostname != "localhost.localdomain":
            localline += self.hostname + " "
            if len(l) > 1:
                localline += l[0] + " "

        # always add the short hostname to 127.0.0.1 (#253979)
        localline += "localhost.localdomain localhost"
        if len(l) > 1:
            localline += " " + l[0]

        f.write("# Do not remove the following line, or various programs\n")
        f.write("# that require network functionality will fail.\n")
        f.write("127.0.0.1\t\t" + localline + "\n")
        f.write("::1\t\tlocalhost6.localdomain6 localhost6\n")

        if ip:
            nameline = "%s\t\t%s" % (ip, self.hostname)
            n = string.split(self.hostname, ".")
            if len(n) > 1:
                nameline = nameline + " " + n[0]
            f.write("%s\n" %(nameline,))

        # If the hostname was not looked up, but typed in by the user,
        # domain might not be computed, so do it now.
        if self.domains == ["localdomain"] or not self.domains:
            if '.' in self.hostname:
                # chop off everything before the leading '.'
                domain = self.hostname[(string.find(self.hostname, '.') + 1):]
                self.domains = [domain]

        # /etc/resolv.conf
        f = open(instPath + "/etc/resolv.conf", "w")

        if self.domains != ['localdomain'] and self.domains:
            f.write("search %s\n" % (string.joinfields(self.domains, ' '),))

        for ns in self.nameservers():
            if ns:
                f.write("nameserver %s\n" % (ns,))
        f.close()

        # /lib/udev/rules.d/70-persistent-net.rules
        if not os.path.isdir("%s/lib/udev/rules.d" %(instPath,)):
            iutil.mkdirChain("%s/lib/udev/rules.d" %(instPath,))

        f = open(instPath + "/lib/udev/rules.d/70-persistent-net.rules", "w")
        f.write("""
# This file was automatically generated by the /lib/udev/write_net_rules
# program run by the persistent-net-generator.rules rules file.
#
# You can modify it, as long as you keep each rule on a single line.

""")
        for dev in self.netdevices.values():
            addr = dev.get("hwaddr")
            if not addr:
                continue
            devname = dev.get("device")
            basename = devname
            while basename is not "" and basename[-1] in string.digits:
                basename = basename[:-1]

            # rules are case senstive for address. Lame.
            addr = addr.lower()

            s = "" 
            if len(dev.get("DESC")) > 0:
                s = "# %s (rule written by anaconda)\n" % (dev.get("DESC"),)
            else:
                s = "# %s (rule written by anaconda)\n" % (devname,)
            s = s + 'SUBSYSTEM==\"net\", ACTION==\"add\", DRIVERS=="?*", ATTR{address}=="%s", ATTR{type}=="1", KERNEL=="%s*", NAME="%s"\n' % (addr, basename, devname)
            f.write(s)
        
        f.close()
