#
# network.py - network configuration install data
#
# Matt Wilson <ewt@redhat.com>
# Erik Troan <ewt@redhat.com>
# Mike Fulbright <msf@redhat.com>
# Brent Fox <bfox@redhat.com>
#
# Copyright 2001-2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import string
import isys
import iutil
import socket
import os
import re
import kudzu
import rhpl
from flags import flags

from rhpl.translate import _, N_
from rhpl.simpleconfig import SimpleConfigFile

import logging
log = logging.getLogger("anaconda")

def inStrRange(v, s):
    if string.find(s, v) == -1:
	return 0
    else:
	return 1

def sanityCheckHostname(hostname):
    if len(hostname) < 1:
	return None

    if len(hostname) > 64:
	return _("Hostname must be 64 or less characters in length.")
    
    if not inStrRange(hostname[0], string.ascii_letters):
	return _("Hostname must start with a valid character in the range "
		 "'a-z' or 'A-Z'")

    for i in range(1, len(hostname)):
	if not inStrRange(hostname[i], string.ascii_letters+string.digits+".-"):
	    return _("Hostnames can only contain the characters 'a-z', 'A-Z', '-', or '.'")

    return None
	    

def networkDeviceCheck(network, dispatch):
    devs = network.available()
    if not devs:
        dispatch.skipStep("network")


# return if the device is of a type that requires a ptpaddr to be specified
def isPtpDev(devname):
    if (devname.startswith("ctc") or devname.startswith("iucv")):
        return 1
    return 0

# determine whether any active at boot devices are using dhcp
def anyUsingDHCP(devices):
    for dev in devices.keys():
        bootproto = devices[dev].get("bootproto")
        if bootproto and bootproto == "dhcp":
            onboot = devices[dev].get("onboot")
            if onboot and onboot != "no":
                return 1
    return 0

# sanity check an IP string.  if valid, returns octets, if invalid, return None
def sanityCheckIPString(ip_string):
    ip_re = re.compile('^([0-2]?[0-9]?[0-9])\\.([0-2]?[0-9]?[0-9])\\.([0-2]?[0-9]?[0-9])\\.([0-2]?[0-9]?[0-9])$')
    
    #Sanity check the string
    m = ip_re.match (ip_string)
    try:
        if not m:
            return None
        octets = m.groups()
        if len(octets) != 4:
            return None
        for octet in octets:
            if (int(octet) < 0) or (int(octet) > 255):
                return None
    except TypeError:
        return None

    return octets

def hasActiveNetDev():
    # try to load /tmp/netinfo and see if we can sniff out network info
    netinfo = Network()
    for dev in netinfo.netdevices.keys():
        try:
            ip = isys.getIPAddress(dev)
        except Exception, e:
            log.error("Got an exception trying to get the ip addr of %s: "
                      "%s" %(dev, e))
            continue
        if ip == '127.0.0.1' or ip is None:
            continue
        return True
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
	if self.get('bootproto') != 'dhcp' and not self.get('ipaddr'):
	    forceOffOnBoot = 1
	else:
	    forceOffOnBoot = 0

	onBootWritten = 0
        for key in keys:
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
        self.info = { "DEVICE" : dev,
                      "ONBOOT": "no" }
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
        self.ternaryNS = ""
        self.domains = []
	self.isConfigured = 0
        self.hostname = "localhost.localdomain"

        # if we specify a hostname and are using dhcp, do an override
        # originally used by the gui but overloaded now
	# we also test in places if the hostname is localhost.localdomain
	# to see if its been override. Need some consolidation in future.
	self.overrideDHCPhostname = 0

        try:
            f = open("/tmp/netinfo", "r")
        except:
            pass
        else:
            lines = f.readlines()
	    f.close()
            info = {}
	    self.isConfigured = 1
            for line in lines:
                netinf = string.splitfields(line, '=')
                if len(netinf) >= 2:
                    info [netinf[0]] = string.strip(netinf[1])
            self.netdevices [info["DEVICE"]] = NetworkDevice(info["DEVICE"])
            self.firstnetdevice = info["DEVICE"]
            for key in ("IPADDR", "NETMASK", "BOOTPROTO", "ONBOOT", "MTU",
                        "NETTYPE", "SUBCHANNELS", "PORTNAME", "CTCPROT",
                        "PEERID", "ESSID", "KEY"):
                if info.has_key(key):
                    self.netdevices [info["DEVICE"]].set((key, info[key]))
            if info.has_key("GATEWAY"):
                self.gateway = info["GATEWAY"]
            if info.has_key("DOMAIN"):
                self.domains.append(info["DOMAIN"])
            if info.has_key("HOSTNAME"):
                self.hostname = info["HOSTNAME"]
            
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
		    elif self.ternaryNS == "":
			self.ternaryNS = resolv[1]

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

	    # assign description to each device based on kudzu information
	    probedevs = kudzu.probe(kudzu.CLASS_NETWORK, kudzu.BUS_UNSPEC, 0)
	    for netdev in probedevs:
		device = netdev.device
		if device in self.netdevices.keys():
		    desc = netdev.desc
		    if desc is not None and len(desc) > 0:
			self.netdevices[device].set(("desc", desc))

                    # hwaddr for qeth doesn't make sense (#135023)
                    if netdev.driver == "qeth":
                        continue
                    # add hwaddr
                    hwaddr = isys.getMacAddress(device)
                    if hwaddr and hwaddr != "00:00:00:00:00:00" and hwaddr != "ff:ff:ff:ff:ff:ff":
                        self.netdevices[device].set(("hwaddr", hwaddr))

    def getDevice(self, device):
	return self.netdevices[device]

    def getFirstDeviceName(self):
	return self.firstnetdevice

    def available(self):
        ksdevice = None
        if flags.cmdline.has_key("ksdevice"):
            ksdevice = flags.cmdline["ksdevice"]

        f = open("/proc/net/dev")
        lines = f.readlines()
        f.close()
        # skip first two lines, they are header
        lines = lines[2:]
        for line in lines:
            dev = string.strip(line[0:6])
            if dev != "lo" and not self.netdevices.has_key(dev):
		if self.firstnetdevice is None:
		    self.firstnetdevice = dev
                self.netdevices[dev] = NetworkDevice(dev)
            try:
                hwaddr = isys.getMacAddress(dev)
                if rhpl.getArch() != "s390" and hwaddr and hwaddr != "00:00:00:00:00:00" and hwaddr != "ff:ff:ff:ff:ff:ff":
                    self.netdevices[dev].set(("hwaddr", hwaddr))
            except Exception, e:
                log.error("exception getting mac addr: %s" %(e,))

        if ksdevice and self.netdevices.has_key(ksdevice):
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
        if len(dns) >= 3:
            self.ternaryNS = dns[2]

    def setGateway(self, gw):
        self.gateway = gw

    def lookupHostname(self):
	# can't look things up if they don't exist!
	if not self.hostname or self.hostname == "localhost.localdomain":
            return None
	if not self.primaryNS:
            return
        myns = self.primaryNS
	if not self.isConfigured:
	    for dev in self.netdevices.values():
                if (dev.get('bootproto') == "dhcp" and
                    dev.get('onboot') == "yes"):
		    ret = isys.pumpNetDevice(dev.get('device'), dev.get('dhcpclass'))
                    if ret is None:
                        continue
                    myns = ret
                    self.isConfigured = 1
                    break
                elif (dev.get('ipaddr') and dev.get('netmask') and
                      self.gateway is not None and dev.get('onboot') == "yes"):
                    try:
                        isys.configNetDevice(dev.get('device'),
                                             dev.get('ipaddr'),
                                             dev.get('netmask'),
                                             self.gateway)
                        self.isConfigured = 1
                        break
                    except SystemError:
                        log.error("failed to configure network device %s when "
                                  "looking up host name", dev.get('device'))

	if not self.isConfigured:
            log.warning("no network devices were available to look up host name")
            return None

        if not flags.rootpath:
            f = open("/etc/resolv.conf", "w")
            f.write("nameserver %s\n" % myns)
            f.close()
            isys.resetResolv()
            isys.setResolvRetry(1)

	try:
	    ip = socket.gethostbyname(self.hostname)
	except:
	    return None

	return ip

    def nameservers(self):
        return (self.primaryNS, self.secondaryNS, self.ternaryNS)

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

            if dev.get('bootproto') == 'dhcp' or dev.get('ipaddr'):
                f.write("network --device %s" % dev.get('device'))
		onboot = dev.get("onboot")
		if onboot and onboot == "no":
		    f.write(" --onboot no")
                if dev.get('bootproto') == 'dhcp':
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
            device = dev.get("device")
	    fn = "%s/etc/sysconfig/network-scripts/ifcfg-%s" % (instPath,
                                                                device)
            f = open(fn, "w")
	    os.chmod(fn, 0644)
	    if len(dev.get("DESC")) > 0:
		f.write("# %s\n" % (dev.get("DESC"),))
		
            f.write(str(dev))

            # write out the hostname as DHCP_HOSTNAME if given (#81613)
            if (dev.get('bootproto') == 'dhcp' and self.hostname and
                self.overrideDHCPhostname):
                f.write("DHCP_HOSTNAME=%s\n" %(self.hostname,))
            if dev.get('dhcpclass'):
                f.write("DHCP_CLASSID=%s\n" % dev.get('dhcpclass'))

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
        f.write("NETWORKING=yes\n"
                "HOSTNAME=")

        # use instclass hostname if set(kickstart) to override
        if self.hostname:
	    f.write(self.hostname + "\n")
	else:
	    f.write("localhost.localdomain\n")
	if self.gateway:
	    f.write("GATEWAY=%s\n" % (self.gateway,))
        f.close()

        # /etc/hosts
        f = open(instPath + "/etc/hosts", "w")
        localline = "127.0.0.1\t\t"

        log.info("self.hostname = %s", self.hostname)

	ip = self.lookupHostname()

	# If the hostname is not resolvable, tie it to 127.0.0.1
	if not ip and self.hostname != "localhost.localdomain":
	    localline = localline + self.hostname + " "
	    l = string.split(self.hostname, ".")
	    if len(l) > 1:
		localline = localline + l[0] + " "
                
	localline = localline + "localhost.localdomain localhost\n"
        f.write("# Do not remove the following line, or various programs\n")
        f.write("# that require network functionality will fail.\n")
        f.write(localline)

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

