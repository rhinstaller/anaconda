import rpm
import os
rpm.addMacro("_i18ndomains", "redhat-dist")

import iutil, isys
from lilo import LiloConfiguration
arch = iutil.getArch ()
if arch == "sparc":
    from silo import SiloInstall
elif arch == "alpha":
    from milo import MiloInstall, onMILO
elif arch == "ia64":
    from eli import EliConfiguration
import string
import socket
import crypt
import sys
import whrandom
import pcmcia
import _balkan
import kudzu
from kbd import Keyboard
from simpleconfig import SimpleConfigFile
from mouse import Mouse
from xf86config import XF86Config
import errno
import raid
from translate import cat
import timer
import fstab
import time
import re
import gettext_rh
import os.path
import upgrade
from translate import _
from log import log

class NetworkDevice (SimpleConfigFile):
    def __str__ (self):
        s = ""
        s = s + "DEVICE=" + self.info["DEVICE"] + "\n"
        keys = self.info.keys ()
        keys.sort ()
        keys.remove ("DEVICE")

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
	    else:
		s = s + key + "=" + self.info[key] + "\n"

	    if key == 'ONBOOT':
		onBootWritten = 1

	if not onBootWritten:
	    s = s + 'ONBOOT=no\n'

        return s

    def __init__ (self, dev):
        self.info = { "DEVICE" : dev }

class Network:
    def __init__ (self):
        self.netdevices = {}
        self.gateway = ""
        self.primaryNS = ""
        self.secondaryNS = ""
        self.ternaryNS = ""
        self.domains = []
        self.readData = 0
	self.isConfigured = 0
        self.hostname = "localhost.localdomain"

        try:
            f = open ("/tmp/netinfo", "r")
        except:
            pass
        else:
            lines = f.readlines ()
	    f.close ()
            info = {}
	    self.isConfigured = 1
            for line in lines:
                netinf = string.splitfields (line, '=')
                info [netinf[0]] = string.strip (netinf[1])
            self.netdevices [info["DEVICE"]] = NetworkDevice (info["DEVICE"])
            if info.has_key ("IPADDR"):
                self.netdevices [info["DEVICE"]].set (("IPADDR", info["IPADDR"]))
            if info.has_key ("NETMASK"):
                self.netdevices [info["DEVICE"]].set (("NETMASK", info["NETMASK"]))
            if info.has_key ("BOOTPROTO"):
                self.netdevices [info["DEVICE"]].set (("BOOTPROTO", info["BOOTPROTO"]))
            if info.has_key ("ONBOOT"):
                self.netdevices [info["DEVICE"]].set (("ONBOOT", info["ONBOOT"]))
            if info.has_key ("GATEWAY"):
                self.gateway = info["GATEWAY"]
            if info.has_key ("DOMAIN"):
                self.domains.append(info["DOMAIN"])
            if info.has_key ("HOSTNAME"):
                self.hostname = info["HOSTNAME"]
            
            self.readData = 1
	try:
	    f = open ("/etc/resolv.conf", "r")
	except:
	    pass
	else:
	    lines = f.readlines ()
	    f.close ()
	    for line in lines:
		resolv = string.split (line)
		if resolv and resolv[0] == 'nameserver':
		    if self.primaryNS == "":
			self.primaryNS = resolv[1]
		    elif self.secondaryNS == "":
			self.secondaryNS = resolv[1]
		    elif self.ternaryNS == "":
			self.ternaryNS = resolv[1]

    def getDevice(self, device):
	return self.netdevices[device]

    def available (self):
        f = open ("/proc/net/dev")
        lines = f.readlines()
        f.close ()
        # skip first two lines, they are header
        lines = lines[2:]
        for line in lines:
            dev = string.strip (line[0:6])
            if dev != "lo" and not self.netdevices.has_key (dev):
                self.netdevices[dev] = NetworkDevice (dev)
        return self.netdevices

    def lookupHostname (self):
	# can't look things up if they don't exist!
	if not self.hostname or self.hostname == "localhost.localdomain": return None
	if not self.primaryNS: return
	if not self.isConfigured:
	    for dev in self.netdevices.values():
		if dev.get('bootproto') == "dhcp":
		    self.primaryNS = isys.pumpNetDevice(dev.get('device'))
                    self.isConfigured = 1
                    break
		elif dev.get('ipaddr') and dev.get('netmask'):
                    try:
                        isys.configNetDevice(dev.get('device'),
                                             dev.get('ipaddr'),
                                             dev.get('netmask'),
                                             self.gateway)
                        self.isConfigured = 1
                        break
                    except SystemError:
                        log ("failed to configure network device %s when "
                             "looking up host name", dev.get('device'))

	if not self.isConfigured:
            log ("no network devices were availabe to look up host name")
            return None

	f = open("/etc/resolv.conf", "w")
	f.write("nameserver %s\n" % self.primaryNS)
	f.close()
	isys.resetResolv()
	isys.setResolvRetry(2)

	try:
	    ip = socket.gethostbyname(self.hostname)
	except socket.error:
	    return None

	return ip

    def nameservers (self):
        return [ self.primaryNS, self.secondaryNS, self.ternaryNS ]

class Password:
    def __init__ (self):
        self.crypt = None
	self.pure = None

    def getPure(self):
	return self.pure

    def set (self, password, isCrypted = 0):
	if isCrypted:
	    self.crypt = password
	    self.pure = None
	else:
            salt = (whrandom.choice (string.letters +
                                     string.digits + './') + 
                    whrandom.choice (string.letters +
                                     string.digits + './'))
            self.crypt = crypt.crypt (password, salt)
	    self.pure = password

    def getCrypted(self):
	return self.crypt

class Desktop (SimpleConfigFile):
    def __init__ (self):
        SimpleConfigFile.__init__ (self)

    def set (self, desktop):
        self.info ['DESKTOP'] = desktop

def expandLangs(str):
    langs = [str]
    # remove charset ...
    if '.' in str:
	langs.append(string.split(str, '.')[0])

    if '@' in str:
	langs.append(string.split(str, '@')[0])

    # also add 2 character language code ...
    if len(str) > 2:
	langs.append(str[:2])

    return langs

class InstallTimeLanguage:

    def __init__ (self):
	if os.access("lang-table", os.R_OK):
	    f = open("lang-table", "r")
	elif os.access("/etc/lang-table", os.R_OK):
	    f = open("/etc/lang-table", "r")
	else:
	    f = open("/usr/lib/anaconda/lang-table", "r")

	lines = f.readlines ()
	f.close()
	self.langNicks = {}
	self.font = {}
	self.map = {}
	self.kbd = {}
	self.tz = {}
	self.langList = []

        self.tempDefault = ""

	for line in lines:
	    string.strip(line)
	    l = string.split(line)
	    
	    longName = l[0]
	    font = l[2]
	    map = l[3]
	    shortName = l[4]
	    keyboard = l[5]
	    timezone = l[6]

	    self.langList.append(longName)
	    self.langNicks[longName] = shortName
	    self.font[longName] = font
	    self.map[longName] = map
	    self.kbd[longName] = keyboard
	    self.tz[longName] = timezone

	self.langList.sort()

    def getFontMap (self, lang):
	return self.map[lang]

    def getFontFile (self, lang):
	# Note: in /etc/fonts.cgz fonts are named by the map
	# name as that's unique, font names are not
	return self.font[lang]

    def getLangNick (self, lang):
	return self.langNicks[lang]

    def getLangNameByNick(self, lang):
	# The nick we get here may be long (fr_FR@euro), when we need
	# shorter (fr_FR), so be a bit fuzzy
	for (langName, nick) in self.langNicks.items():
	    if (nick == lang) or (nick == lang[0:len(nick)]):
		return langName

	raise KeyError, "language %s not found" % lang

    def getDefaultKeyboard(self):
	return self.kbd[self.getCurrent()]

    def getDefaultTimeZone(self):
	return self.tz[self.getCurrent()]

    def available (self):
        return self.langList

    def getCurrentLangSearchList(self):
	return expandLangs(self.langNicks[self.getCurrent()]) + ['C']

    def getCurrent(self):
	if os.environ.has_key('LANG'):
	    what = os.environ['LANG']
	else:
	    what = 'en_US'
	return self.getLangNameByNick(what)

    def setRuntimeLanguage(self, name):
	lang = self.langNicks[name]

        os.environ["LC_ALL"] = lang
        os.environ["LANG"] = lang
        os.environ["LC_NUMERIC"] = 'C'

        newlangs = [lang]
	if len(lang) > 2:
            newlangs.append(lang[:2])
        cat.setlangs (newlangs)

class Language (SimpleConfigFile):

    def __init__ (self):
        self.info = {}
        self.info["SUPPORTED"] = None
	self.supported = []
	self.default = None

	self.allSupportedLangs = []
	self.langInfoByName = {}
	if os.access("/usr/share/anaconda/locale-list", os.R_OK):
	    f = open("/usr/share/anaconda/locale-list")
	    lines = f.readlines()
	    f.close()
	    for line in lines:
		line = string.strip(line)
		(lang, map, font, name) = string.split(line, ' ', 3)
		self.langInfoByName[name] = (lang, map, font)
		self.allSupportedLangs.append(name)
	else:
	    self.langInfoByName['English (US)'] = ('en_US', 'iso01', 'default8x16')
	    self.allSupportedLangs.append('English (US)')

    def getAllSupported(self):
	return self.allSupportedLangs

    def getLangNameByNick(self, nick):
	for langName in self.langInfoByName.keys():
	    (lang, map, font) = self.langInfoByName[langName]
	    if (nick == lang) or (nick == lang[0:len(nick)]):
		return langName

	raise KeyError, "language %s not found" % nick

    def getSupported (self):
	return self.supported

    def getDefault (self):
	if self.default:
	    return self.default
	elif os.environ.has_key('LANG'):
	    lang = os.environ['LANG']
	    name = self.getLangNameByNick(lang)
	    if name not in self.getSupported():
		# the default language needs to be in the supported list!
		s = self.getSupported()
		s.append(name)
		s.sort()
		self.setSupported(s)

	    return name
	else:
	    return 'English (US)'
    
    def setDefault(self, name):
	if not name:
	    self.default = None
	    return

	self.default = name
	(lang, map, font) = self.langInfoByName[name]

	self.info['LANG'] = lang
	self.info['SYSFONT'] = font
	self.info['SYSFONTACM'] = map

    def setSupported (self, langlist):
	if len(langlist) == len(self.allSupportedLangs):
            self.info["SUPPORTED"] = None
	    self.supported = langlist
            rpm.delMacro ("_install_langs")
        elif langlist:
	    rpmNickList = []
	    for name in langlist:
		(lang, map, font) = self.langInfoByName[name]
		rpmNickList = rpmNickList + expandLangs(lang)

            linguas = string.join (rpmNickList, ':')
            self.info["SUPPORTED"] = linguas
	    self.supported = langlist

            shortLinguas = string.join (rpmNickList, ':')
            rpm.addMacro("_install_langs", shortLinguas)
        else:
            self.info["SUPPORTED"] = None
            rpm.delMacro ("_install_langs")
	    self.supported = None
	
	if self.info["SUPPORTED"]:
	    os.environ ["LINGUAS"] = self.info["SUPPORTED"]
	else:
	    os.environ ["LINGUAS"] = ""
    
class Firewall:
    def __init__ (self):
	self.enabled = -1
	self.ssh = 0
	self.telnet = 0
	self.smtp = 0
	self.http = 0
	self.ftp = 0
	self.portlist = ""
	self.ports = []
	self.policy = 0
	self.dhcp = 0
	self.trustdevs = []
    
class Authentication:
    def __init__ (self):
        self.useShadow = 1
        self.useMD5 = 1

        self.useNIS = 0
        self.nisDomain = ""
        self.nisuseBroadcast = 1
        self.nisServer = ""

        self.useLdap = 0
        self.useLdapauth = 0
        self.ldapServer = ""
        self.ldapBasedn = ""
        self.ldapTLS = ""

        self.useKrb5 = 0
        self.krb5Realm = ""
        self.krb5Kdc = ""
        self.krb5Admin = ""

        self.useHesiod = 0
        self.hesiodDlhs = ""
        self.hesiodRhs = ""
 
class InstSyslog:
    def __init__ (self, root, log):
        self.pid = os.fork ()
        if not self.pid:
            if os.access ("./anaconda", os.X_OK):
                path = "./anaconda"
            elif os.access ("/usr/bin/anaconda.real", os.X_OK):
                path = "/usr/bin/anaconda.real"
            else:
                path = "/usr/bin/anaconda"
            os.execv (path, ("syslogd", "--syslogd", root, log))

    def __del__ (self):
        os.kill (self.pid, 15)
	os.wait (self.pid)
        
class ToDo:
    def __init__(self, intf, method, rootPath, setupFilesystems = 1,
		 installSystem = 1, mouse = None, instClass = None, x = None,
		 expert = 0, serial = 0, reconfigOnly = 0, test = 0,
		 extraModules = []):
	self.intf = intf
	self.method = method
	self.hdList = None
	self.comps = None
	self.instPath = rootPath
	self.setupFilesystems = setupFilesystems
	self.installSystem = installSystem
        self.instTimeLanguage = InstallTimeLanguage ()
        self.language = Language ()
	self.serial = serial
        self.reconfigOnly = reconfigOnly
        self.network = Network ()
        self.rootpassword = Password ()
        self.extraModules = extraModules
        self.verifiedState = None

        if mouse:
            self.mouse = mouse
        else:
            self.mouse = Mouse ()
        
        self.keyboard = Keyboard ()
        self.auth = Authentication ()
	self.firewall = Firewall()
        self.ddruidReadOnly = 0
        self.bootdisk = 1
        self.bdstate = ""

        log.open (serial, reconfigOnly, test, setupFilesystems)

        self.fstab = None

	# liloDevice, liloLinear, liloAppend are initialized form the
	# default install class
        arch = iutil.getArch ()
        self.lilo = LiloConfiguration()
	if arch == "sparc":
	    self.silo = SiloInstall (self.serial)
        elif arch == "alpha":
            self.milo = MiloInstall (self)
        elif arch == "ia64":
            self.eli = EliConfiguration ()
	self.timezone = None
        self.upgrade = 0
	self.ddruidAlreadySaved = 0
        self.initlevel = 3
	self.expert = expert
        self.progressWindow = None
	self.fdDevice = None
        self.lilostate = ""
        self.videoCardOriginalName = ""
        self.videoCardOriginalNode = ""
        self.isDDC = ""
        self.videoCardStateName = ""
        self.videoCardStateNode = ""
        self.videoRamState = ""
        self.videoRamOriginal = ""
        self.monitorOriginalName = ""
        self.monitorOriginalNode = ""
        self.monitorHsync = ""
        self.monitorVsync = ""
        self.monitorHsyncState = ""
        self.monitorVsyncState = ""        
        self.probedFlag = ""
        self.resState = ""
        self.depthState = ""
        self.initState = 0
        self.dhcpState = ""
        self.firewallState = 0

        # If reconfig mode, don't probe floppy
        #print self.reconfigOnly
        if self.reconfigOnly != 1:
            self.setFdDevice()
        
	if (not instClass):
	    raise TypeError, "installation class expected"
        if x:
            self.x = x
            self.x.setMouse (self.mouse)
        else:
            self.x = XF86Config (mouse = self.mouse)

	# This absolutely, positively MUST BE LAST
	self.setClass(instClass)

    def setFdDevice(self):
	if self.fdDevice:
	    return

	self.fdDevice = "fd0"
	if iutil.getArch() == "sparc":
	    try:
		f = open(self.fdDevice, "r")
	    except IOError, (errnum, msg):
		if errno.errorcode[errnum] == 'ENXIO':
		    self.fdDevice = "fd1"
	    else:
		f.close()
	elif iutil.getArch() == "alpha":
	    pass
	elif iutil.getArch() == "i386" or iutil.getArch() == "ia64":
	    # Look for the first IDE floppy device
	    drives = isys.floppyDriveDict()
	    if not drives:
		log("no IDE floppy devices found")
		return 0

            floppyDrive = drives.keys()[0]
            # need to go through and find if there is an LS-120
            for dev in drives.keys():
                if re.compile(".*[Ll][Ss]-120.*").search(drives[dev]):
                    floppyDrive = dev

	    # No IDE floppy's -- we're fine w/ /dev/fd0
	    if not floppyDrive: return

	    if iutil.getArch() == "ia64":
		self.fdDevice = floppyDrive
		log("anaconda floppy device is %s", self.fdDevice)
		return

	    # Look in syslog for a real fd0 (which would take precedence)
            try:
                f = open("/tmp/syslog", "r")
            except IOError:
                return
	    for line in f.readlines():
		# chop off the loglevel (which init's syslog leaves behind)
		line = line[3:]
		match = "Floppy drive(s): "
		if match == line[:len(match)]:
		    # Good enough
		    floppyDrive = "fd0"
		    break

	    self.fdDevice = floppyDrive
	else:
	    raise SystemError, "cannot determine floppy device for this arch"

	log("anaconda floppy device is %s", self.fdDevice)

    def writeTimezone(self):
	if (self.timezone):
	    (timezone, asUtc, asArc) = self.timezone
	    fromFile = self.instPath + "/usr/share/zoneinfo/" + timezone

            try:
                iutil.copyFile(fromFile, self.instPath + "/etc/localtime")
            except OSError, (errno, msg):
                log ("Error copying timezone (from %s): %s" % (fromFile, msg))
	else:
	    asUtc = 0
	    asArc = 0

	f = open(self.instPath + "/etc/sysconfig/clock", "w")
	f.write('ZONE="%s"\n' % timezone)
	f.write("UTC=")
	if (asUtc):
	    f.write("true\n")
	else:
	    f.write("false\n")

	f.write("ARC=")
	if (asArc):
	    f.write("true\n")
	else:
	    f.write("false\n")
	f.close()

    def getTimezoneInfo(self):
	return self.timezone

    def setTimezoneInfo(self, timezone, asUtc = 0, asArc = 0):
	self.timezone = (timezone, asUtc, asArc)

    def writeLanguage(self):
	f = open(self.instPath + "/etc/sysconfig/i18n", "w")
	f.write(str (self.language))
	f.close()

    def writeMouse(self):
	if self.serial: return
	f = open(self.instPath + "/etc/sysconfig/mouse", "w")
	f.write(str (self.mouse))
	f.close()
	self.mouse.makeLink(self.instPath)

    def writeDesktop(self):
        desktop = Desktop ()
        desktop.set (self.instClass.getDesktop())
	f = open(self.instPath + "/etc/sysconfig/desktop", "w")
	f.write(str (desktop))
	f.close()

    def writeKeyboard(self):
	if self.serial: return
	f = open(self.instPath + "/etc/sysconfig/keyboard", "w")
	f.write(str (self.keyboard))
	f.close()

    def needBootdisk (self):
	if self.bootdisk or self.fstab.rootOnLoop(): return 1

    def makeBootdisk (self):
	# this is faster then waiting on mkbootdisk to fail
	device = self.fdDevice
	file = "/tmp/floppy"
	isys.makeDevInode(device, file)
	try:
	    fd = os.open(file, os.O_RDONLY)
	except:
            raise RuntimeError, "boot disk creation failed"
	os.close(fd)

	kernel = self.hdList['kernel']
        kernelTag = "-%s-%s" % (kernel[rpm.RPMTAG_VERSION],
                                kernel[rpm.RPMTAG_RELEASE])

        w = self.intf.waitWindow (_("Creating"), _("Creating boot disk..."))
        rc = iutil.execWithRedirect("/sbin/mkbootdisk",
                                    [ "/sbin/mkbootdisk",
                                      "--noprompt",
                                      "--device",
                                      "/dev/" + self.fdDevice,
                                      kernelTag[1:] ],
                                    stdout = '/dev/tty5', stderr = '/dev/tty5',
				    searchPath = 1, root = self.instPath)
        w.pop()
        if rc:
            raise RuntimeError, "boot disk creation failed"

    def freeHeaderList(self):
	if (self.hdList):
	    self.hdList = None

    def getHeaderList(self):
	if (not self.hdList):
	    w = self.intf.waitWindow(_("Reading"),
                                     _("Reading package information..."))
	    self.hdList = self.method.readHeaders()
	    w.pop()
	return self.hdList

    def getCompsList(self):
	if not self.comps:
	    self.getHeaderList()
	    self.comps = self.method.readComps(self.hdList)
            self.updateInstClassComps ()
        else:
            # re-evaluate all the expressions for packages with qualifiers.
            self.comps.updateSelections()
            
	return self.comps

    def updateInstClassComps(self):
	# don't load it just for this
	if not self.comps: return

        
	group = self.instClass.getGroups()
        optional = self.instClass.getOptionalGroups()
	packages = self.instClass.getPackages()
	for comp in self.comps:
	    comp.unselect()

	if group == None and packages == None:
            # this comp has no special groups, set up the defaults
            # and exit
            for comp in self.comps:
                comp.setDefaultSelection()
            return

	self.comps['Base'].select()
	if group:
	    for n in group:
		self.comps[n].select()

        if optional:
            for n in optional:
		if type((1,)) == type(n):
		    (on, n) = n
		    if (on):
			self.comps[n].select()
		else:
		    self.comps[n].setDefaultSelection()
                
	if packages:
	    for n in packages:
		self.selectPackage(n)


        if self.hdList.packages.has_key('XFree86') and self.hdList.packages['XFree86'].selected:
            log ("X is being installed, need to enable server if set")
            if self.x.server and not self.x.server == "XFree86":
                log("enabling server %s" % self.x.server)
                try:
                    self.selectPackage ('XFree86-' + self.x.server[5:])
                except ValueError, message:
                    log ("Error selecting XFree86 server package: %s", message)

    def selectPackage(self, package):
	if not self.hdList.packages.has_key(package):
	    str = "package %s is not available" % (package,)
	    raise ValueError, str
	self.hdList.packages[package].selected = 1

    def writeNetworkConfig (self):
        # /etc/sysconfig/network-scripts/ifcfg-*
        for dev in self.network.netdevices.values ():
            device = dev.get ("device")
	    fn = self.instPath + "/etc/sysconfig/network-scripts/ifcfg-" + device
            f = open (fn, "w")
	    os.chmod(fn, 0600)
            f.write (str (dev))
            f.close ()

        # /etc/sysconfig/network

        f = open (self.instPath + "/etc/sysconfig/network", "w")
        f.write ("NETWORKING=yes\n"
                 "HOSTNAME=")


        # use instclass hostname if set (kickstart) to override
        if self.instClass.getHostname():
              f.write(self.instClass.getHostname() + "\n")
        elif self.network.hostname:
	    f.write(self.network.hostname + "\n")
	else:
	    f.write("localhost.localdomain" + "\n")
	if self.network.gateway:
	    f.write("GATEWAY=" + self.network.gateway + "\n")
        f.close ()

        # /etc/hosts
        f = open (self.instPath + "/etc/hosts", "w")
        localline = "127.0.0.1\t\t"

        log ("self.network.hostname = %s", self.network.hostname)

	ip = self.network.lookupHostname()

	# If the hostname is not resolvable, tie it to 127.0.0.1
	if not ip and self.network.hostname != "localhost.localdomain":
	    localline = localline + self.network.hostname + " "
	    l = string.split(self.network.hostname, ".")
	    if len(l) > 1:
		localline = localline + l[0] + " "
                
	localline = localline + "localhost.localdomain localhost\n"
        f.write("# Do not remove the following line, or various programs\n")
        f.write("# that require network functionality will fail.\n")
        f.write (localline)

	if ip:
	    f.write ("%s\t\t%s\n" % (ip, self.network.hostname))

	# If the hostname was not looked up, but typed in by the user,
	# domain might not be computed, so do it now.
	if self.network.domains == [ "localdomain" ] or not self.network.domains:
	    if '.' in self.network.hostname:
		# chop off everything before the leading '.'
		domain = self.network.hostname[(string.find(self.network.hostname, '.') + 1):]
		self.network.domains = [ domain ]

        # /etc/resolv.conf
        f = open (self.instPath + "/etc/resolv.conf", "w")

	if self.network.domains != [ 'localdomain' ] and self.network.domains:
	    f.write ("search " + string.joinfields (self.network.domains, ' ') 
			+ "\n")

        for ns in self.network.nameservers ():
            if ns:
                f.write ("nameserver " + ns + "\n")

        f.close ()

    def writeRootPassword (self):
	pure = self.rootpassword.getPure()
	if pure:
	    self.setPassword("root", pure)
	else:
	    self.setPassword("root", self.rootpassword.getCrypted (),
			     alreadyCrypted = 1)
	    
    def setupFirewall (self):
	args = [ "/usr/sbin/lokkit", "--quiet", "--nostart" ]
	if self.firewall.policy:
	    args.append ("--medium")
	else:
	    args.append ("--high")
	if self.firewall.dhcp:
	    args.append ("--dhcp")
	if self.firewall.portlist:
	    ports = string.split(self.firewall.portlist,',')
	    for port in ports:
		port = string.strip(port)
                try:
                    if not string.index(port,':'):
                        port = '%s:tcp' % port
                except:
                    pass
		self.firewall.ports.append(port)
	for port in self.firewall.ports:
	    args = args + [ "--port", port ]
	if self.firewall.smtp:
	    args = args + [ "--port","smtp:tcp" ]
	if self.firewall.http:
	    args = args + [ "--port","http:tcp" ]
	if self.firewall.ftp:
	    args = args + [ "--port","ftp:tcp" ]
	if self.firewall.ssh:
	    args = args + [ "--port","ssh:tcp" ]
	if self.firewall.telnet:
	    args = args + [ "--port","telnet:tcp" ]
	for dev in self.firewall.trustdevs:
	    args = args + [ "--trust", dev ]
	if self.firewall.enabled > 0:
            try:
                iutil.execWithRedirect(args[0], args, root = self.instPath,
                                       stdout = None, stderr = None)
            except RuntimeError, msg:
                log ("lokkit run failed: %s", msg)
            except OSError, (errno, msg):
                log ("lokkit run failed: %s", msg)
                
    def setupAuthentication (self):
        args = [ "/usr/sbin/authconfig", "--kickstart", "--nostart" ]
        if self.auth.useShadow:
            args.append ("--enableshadow")
	else:
            args.append ("--disableshadow")

        if self.auth.useMD5:
            args.append ("--enablemd5")
	else:
            args.append ("--disablemd5")
	

        if self.auth.useNIS:
            args.append ("--enablenis")
            args.append ("--nisdomain")
            args.append (self.auth.nisDomain)
            if not self.auth.nisuseBroadcast:
                args.append ("--nisserver")
                args.append (self.auth.nisServer)
        else:
            args.append ("--disablenis")

        if self.auth.useLdap:
            args.append ("--enableldap")
        else:
            args.append ("--disableldap")
        if self.auth.useLdapauth:
            args.append ("--enableldapauth")
        else:
            args.append ("--disableldapauth")
        if self.auth.useLdap or self.auth.useLdapauth:
            args.append ("--ldapserver")
            args.append (self.auth.ldapServer)
            args.append ("--ldapbasedn")
            args.append (self.auth.ldapBasedn)
        if self.auth.ldapTLS:
            args.append ("--enableldaptls")
        else:
            args.append ("--disableldaptls")

        if self.auth.useKrb5:
            args.append ("--enablekrb5")
            args.append ("--krb5realm")
            args.append (self.auth.krb5Realm)
            args.append ("--krb5kdc")
            args.append (self.auth.krb5Kdc)
            args.append ("--krb5adminserver")
            args.append (self.auth.krb5Admin)
        else:
            args.append ("--disablekrb5")

        if self.auth.useHesiod:
            args.append ("--enablehesiod")
            args.append ("--hesiodlhs")
            args.append (self.auth.hesiodLhs)
            args.append ("--hesiodrhs")
            args.append (self.auth.hesiodRhs)
        else:
            args.append ("--disablehesiod")


        log ("running authentication cmd |%s|" % args)
        try:
            iutil.execWithRedirect(args[0], args,
                                   stdout = None, stderr = None,
                                   searchPath = 1,
                                   root = self.instPath)
        except RuntimeError, msg:
            log ("Error running %s: %s", args, msg)

    def copyConfModules (self):
        try:
            inf = open ("/tmp/modules.conf", "r")
        except:
            pass
        else:
            out = open (self.instPath + "/etc/modules.conf", "a")
            out.write (inf.read ())

    def verifyDeps (self):
        # if we still have the same packages selected, bail - we don't need to
        # do this again.
        if self.verifiedState == self.comps.getSelectionState()[1]:
            return

        self.verifiedState = None
        
	win = self.intf.waitWindow(_("Dependency Check"),
	  _("Checking dependencies in packages selected for installation..."))
	self.getCompsList()
        if self.upgrade:
            self.fstab.mountFilesystems (self.instPath)
            db = rpm.opendb (0, self.instPath)
            ts = rpm.TransactionSet(self.instPath, db)
        else:
            ts = rpm.TransactionSet()
            
	for p in self.hdList.packages.values ():
            if p.selected:
                ts.add(p.h, (p.h, p.h[rpm.RPMTAG_NAME]))
            else:
                ts.add(p.h, (p.h, p.h[rpm.RPMTAG_NAME]), "a")

        deps = ts.depcheck()
        rc = []
        if deps:
            for ((name, version, release),
                 (reqname, reqversion),
                 flags, suggest, sense) in deps:
                if sense == rpm.RPMDEP_SENSE_REQUIRES:
                    if suggest:
                        (header, sugname) = suggest
                    else:
                        sugname = _("no suggestion")
                    if not (name, sugname) in rc:
                        rc.append ((name, sugname))
                elif sense == rpm.RPMDEP_SENSE_CONFLICTS:
		    # We need to check if the one we are going to
		    # install is ok.
		    conflicts = 1
		    if reqversion:
			fields = string.split(reqversion, '-')
			if (len (fields) == 2):
			    needed = ("", fields [0], fields [1])
			else:
			    needed = ("", fields [0], "")
                        try:
                            h = self.hdList[reqname].h
                        except KeyError:
                            conflicts = 0
			installed = ("", h[rpm.RPMTAG_VERSION],
				     h [rpm.RPMTAG_RELEASE])
			if rpm.labelCompare (installed, needed) >= 0:
			    conflicts = 0

		    if conflicts:
			log ("%s-%s-%s conflicts with to-be-installed "
                             "package %s-%s, removing from set",
                             name, version, release, reqname, reqversion)
			if self.hdList.packages.has_key (reqname):
			    self.hdList.packages[reqname].selected = 0
			    log ("... removed")

        del ts
        if self.upgrade:
            del db
            self.fstab.umountFilesystems (self.instPath)            

	win.pop()

        if not rc: 
            self.verifiedState = self.comps.getSelectionState()[1]

        return rc

    def selectDeps (self, deps):
        if deps:
            for (who, dep) in deps:
                if dep != _("no suggestion"):
                    self.hdList[dep].select ()

    def unselectDeps (self, deps):
        if deps:
            for (who, dep) in deps:
                if dep != _("no suggestion"):
                    self.hdList[dep].unselect ()

    def selectDepCause (self, deps):
        if deps:
            for (who, dep) in deps:
                self.hdList[who].select ()

    def unselectDepCause (self, deps):
        if deps:
            for (who, dep) in deps:
                self.hdList[who].unselect ()

    def canResolveDeps (self, deps):
        canresolve = 0
        if deps:
            for (who, dep) in deps:
                if dep != _("no suggestion"):
                    canresolve = 1
        return canresolve

    def upgradeFindRoot(self):
	if not self.setupFilesystems: return [ self.instPath ]
	return upgrade.findExistingRoots(self.intf, self.fstab)
                    
    def upgradeFindPackages (self, rootInfo):
        if self.setupFilesystems:
	    try:
		upgrade.mountRootPartition(self.intf,rootInfo,
                                           self.fstab, self.instPath,
					   allowDirty = 0)
	    except SystemError, msg:
		intf.messageWindow(("Dirty Filesystems"),
		    _("One or more of the filesystems listed in the "
		      "/etc/fstab on your Linux system cannot be mounted. "
		      "Please fix this problem and try to upgrade again."))
		sys.exit(0)

	    if os.access("/mnt/loophost/rh-swap.img", os.R_OK):
		self.fstab.setLoopbackSwapSize(-1)

	    checkLinks = [ '/etc', '/var', '/var/lib', '/var/lib/rpm',
			   '/boot', '/tmp', '/var/tmp' ]
	    badLinks = []
	    for n in checkLinks:
		if not os.path.islink(self.instPath + n): continue
		l = os.readlink(self.instPath + n)
		if l[0] == '/':
		    badLinks.append(n)

	    if badLinks:
		message = _("The following files are absolute symbolic " 
			    "links, which we do not support during an " 
			    "upgrade. Please change them to relative "
			    "symbolic links and restart the upgrade.\n\n")
		for n in badLinks:
		    message = message + '\t' + n + '\n'
		self.intf.messageWindow(("Absolute Symlinks"), message)
		sys.exit(0)

	    self.fstab.turnOnSwap(formatSwap = 0)

        self.getCompsList ()
	self.getHeaderList ()
	self.method.mergeFullHeaders(self.hdList)

        win = self.intf.waitWindow (_("Finding"),
                                    _("Finding packages to upgrade..."))

        self.dbpath = "/var/lib/anaconda-rebuilddb" + str(int(time.time()))
        rpm.addMacro("_dbpath_rebuild", self.dbpath)
        rpm.addMacro("_dbapi", "-1")

        # now, set the system clock so the timestamps will be right:
        iutil.setClock (self.instPath)
        
        # and rebuild the database so we can run the dependency problem
        # sets against the on disk db
        rc = rpm.rebuilddb (self.instPath)
        if rc:
            win.pop()
            self.intf.messageWindow(_("Error"),
                                    _("Rebuild of RPM database failed. "
                                      "You may be out of disk space?"))
	    if self.setupFilesystems:
		self.fstab.umountFilesystems (self.instPath)
	    sys.exit(0)

        rpm.addMacro("_dbpath", self.dbpath)
        rpm.addMacro("_dbapi", "3")
        try:
            packages = rpm.findUpgradeSet (self.hdList.hdlist, self.instPath)
        except rpm.error:
            win.pop()
            self.intf.messageWindow(_("Error"),
                                    _("An error occured when finding the packages to "
                                      "upgrade."))
	    if self.setupFilesystems:
		self.fstab.umountFilesystems (self.instPath)
	    sys.exit(0)
                
        # Turn off all comps
        for comp in self.comps:
            comp.unselect()

        # unselect all packages
        for package in self.hdList.packages.values ():
            package.selected = 0

        hasX = 0
        hasFileManager = 0
        # turn on the packages in the upgrade set
        for package in packages:
            self.hdList[package[rpm.RPMTAG_NAME]].select()
            if package[rpm.RPMTAG_NAME] == "XFree86":
                hasX = 1
            if package[rpm.RPMTAG_NAME] == "gmc":
                hasFileManager = 1
            if package[rpm.RPMTAG_NAME] == "kdebase":
                hasFileManager = 1

        # open up the database to check dependencies
        db = rpm.opendb (0, self.instPath)

        # if we have X but not gmc, we need to turn on GNOME.  We only
        # want to turn on packages we don't have installed already, though.
        if hasX and not hasFileManager:
            log ("Has X but no desktop -- Installing GNOME")
            for package in self.comps['GNOME'].pkgs:
                try:
                    rec = db.findbyname (package.name)
                except rpm.error:
                    rec = None
                if not rec:
                    log ("GNOME: Adding %s", package)
                    package.select()
            
        del db

	if self.setupFilesystems:
	    self.fstab.umountFilesystems (self.instPath)

        # new package dependency fixup
        deps = self.verifyDeps ()
        loops = 0
        while deps and self.canResolveDeps (deps) and loops < 10:
            for (name, suggest) in deps:
                if name != _("no suggestion"):
                    log ("Upgrade Dependency: %s needs %s, "
                         "automatically added.", name, suggest)
            self.selectDeps (deps)
            deps = self.verifyDeps ()
            loops = loops + 1

        win.pop ()

    def rpmError (todo):
        todo.instLog.write (rpm.errorString () + "\n")

    def getClass(todo):
	return todo.instClass

    def setClass(todo, instClass):
	todo.instClass = instClass
	todo.hostname = todo.instClass.getHostname()
	todo.updateInstClassComps()
	( enable, policy, trusts, ports, dhcp, ssh,
	  telnet, smtp, http, ftp ) = todo.instClass.getFirewall()
	  
	todo.firewall.enabled = enable
	todo.firewall.policy = policy
	todo.firewall.trustdevs = trusts
	todo.firewall.portlist = ports
	todo.firewall.dhcp = dhcp
	todo.firewall.ssh = ssh
	todo.firewall.telnet = telnet
	todo.firewall.smtp = smtp
	todo.firewall.http = http
	todo.firewall.ftp = ftp
	
	( useShadow, useMd5,
          useNIS, nisDomain, nisBroadcast, nisServer,
          useLdap, useLdapauth, ldapServer, ldapBasedn,
          useKrb5, krb5Realm, krb5Kdc, krb5Admin,
          useHesiod, hesiodLhs, hesiodRhs) = todo.instClass.getAuthentication()
	  
        todo.auth.useShadow = useShadow
        todo.auth.useMD5 = useMd5
        todo.auth.useNIS = useNIS
        todo.auth.nisDomain = nisDomain
        todo.auth.nisuseBroadcast = nisBroadcast
        todo.auth.nisServer = nisServer
        todo.auth.useLdap = useLdap
        todo.auth.useLdapauth = useLdapauth
        todo.auth.ldapServer = ldapServer
        todo.auth.ldapBasedn = ldapBasedn
        todo.auth.useKrb5 = useKrb5
        todo.auth.krb5Realm = krb5Realm
        todo.auth.krb5Kdc = krb5Kdc
        todo.auth.krb5Admin = krb5Admin
        todo.auth.useHesiod = useHesiod
        todo.auth.hesiodLhs = hesiodLhs
        todo.auth.hesiodRhs = hesiodRhs

	todo.timezone = instClass.getTimezoneInfo()
	todo.bootdisk = todo.instClass.getMakeBootdisk()
	todo.zeroMbr = todo.instClass.zeroMbr
	(where, linear, append) = todo.instClass.getLiloInformation()

        arch = iutil.getArch ()
	if arch == "i386":	
	    todo.lilo.setDevice(where)
	    todo.lilo.setLinear(linear)
	    if append: todo.lilo.setAppend(append)
 	elif arch == "sparc":
	    todo.silo.setDevice(where)
	    todo.silo.setAppend(append)

	todo.users = []
	if todo.instClass.rootPassword:
	    todo.rootpassword.set(todo.instClass.rootPassword,
			      isCrypted = todo.instClass.rootPasswordCrypted)

	if todo.instClass.language:
	    langName = todo.language.getLangNameByNick(todo.instClass.language)
            if todo.instClass.langsupported != None:
                todo.language.setSupported([langName])
            if not todo.instClass.langdefault:
                todo.language.setDefault(langName)
	    instLangName = todo.instTimeLanguage.getLangNameByNick(todo.instClass.language)
	    todo.instTimeLanguage.setRuntimeLanguage(instLangName)

	if todo.instClass.langsupported != None:
            if len (todo.instClass.langsupported) == 0:
                all = todo.language.getAllSupported()
                todo.language.setSupported(all)
            else:
                newlist = []
                for lang in todo.instClass.langsupported:
                    newlist.append(todo.language.getLangNameByNick(lang))
                todo.language.setSupported(newlist)

        if todo.instClass.langdefault:
            todo.language.setDefault(todo.language.getLangNameByNick(
                todo.instClass.langdefault))
            
	if todo.instClass.keyboard:
	    todo.keyboard.set(todo.instClass.keyboard)
            if todo.instClass.keyboard != "us":
                xkb = todo.keyboard.getXKB ()

                if xkb:
                    apply (todo.x.setKeyboard, xkb)

                    # hack - apply to instclass preset if present as well
                    if (todo.instClass.x):
                        apply (todo.instClass.x.setKeyboard, xkb)

	(bootProto, ip, netmask, gateway, nameserver, netDevice) = \
		todo.instClass.getNetwork()
	if bootProto:
	    todo.network.gateway = gateway
	    todo.network.primaryNS = nameserver

	    devices = todo.network.available ()
	    if (devices and bootProto):
		if not netDevice:
		    list = devices.keys ()
		    list.sort()
		    netDevice = list[0]
		dev = devices[netDevice]
                dev.set (("bootproto", bootProto))
                if bootProto == "static":
                    if (ip):
                        dev.set (("ipaddr", ip))
                    if (netmask):
                        dev.set (("netmask", netmask))

	if (todo.instClass.x):
	    todo.x = todo.instClass.x

	if (todo.instClass.mouse):
	    (type, device, emulateThreeButtons) = todo.instClass.mouse
	    todo.mouse.set(type, emulateThreeButtons, thedev = device)
            todo.x.setMouse(todo.mouse)
            
        # this is messy, needed for upgradeonly install class
        if todo.instClass.installType == "upgrade":
            todo.upgrade = 1

    def getPartitionWarningText(self):
	return self.instClass.clearPartText

    # List of (accountName, fullName, password) tupes
    def setUserList(todo, users):
	todo.users = users

    def getUserList(todo):
	return todo.users

    def setPassword(self, account, password, alreadyCrypted = 0):
	if not alreadyCrypted:
	    if self.auth.useMD5:
		salt = "$1$"
		saltLen = 8
	    else:
		salt = ""
		saltLen = 2

	    for i in range(saltLen):
		salt = salt + whrandom.choice (string.letters +
					 string.digits + './')

            password = crypt.crypt (password, salt)

	devnull = os.open("/dev/null", os.O_RDWR)

	argv = [ "/usr/sbin/usermod", "-p", password, account ]
	iutil.execWithRedirect(argv[0], argv, root = self.instPath, 
			       stdout = '/dev/null', stderr = None)
	os.close(devnull)

    def createAccounts(todo):
	if not todo.users: return

	for (account, name, password) in todo.users:
	    devnull = os.open("/dev/null", os.O_RDWR)

	    argv = [ "/usr/sbin/useradd", account ]
	    iutil.execWithRedirect(argv[0], argv, root = todo.instPath,
				   stdout = devnull)

	    argv = [ "/usr/bin/chfn", "-f", name, account]
	    iutil.execWithRedirect(argv[0], argv, root = todo.instPath,
				   stdout = devnull)
        
	    todo.setPassword(account, password)

	    os.close(devnull)

    def setDefaultRunlevel (self):
        try:
            inittab = open (self.instPath + '/etc/inittab', 'r')
        except IOError:
            log ("WARNING, there is no inittab, bad things will happen!")
            return
        lines = inittab.readlines ()
        inittab.close ()
        inittab = open (self.instPath + '/etc/inittab', 'w')        
        for line in lines:
            if len (line) > 3 and line[:3] == "id:":
                fields = string.split (line, ':')
                fields[1] = str (self.initlevel)
                line = string.join (fields, ':')
            inittab.write (line)
        inittab.close ()

    def migrateXinetd(self):
        if not os.access (self.instPath + "/usr/sbin/inetdconvert", os.X_OK):
            log("did not find %s" % self.instPath + "/usr/sbin/inetdconvert")
            return

        if not os.access (self.instPath + "/etc/inetd.conf.rpmsave", os.R_OK):
            log("did not run inetdconvert because no inetd.conf.rpmsave found")
            return

        argv = [ "/usr/sbin/inetdconvert", "--convertremaining",
                 "--inetdfile", "/etc/inetd.conf.rpmsave" ]
        
        log("found inetdconvert, executing %s" % argv)

        logfile = os.open (self.instLogName, os.O_APPEND)
        iutil.execWithRedirect(argv[0], argv, root = self.instPath,
                               stdout = logfile, stderr = logfile)
        os.close(logfile)
        
    def instCallback(self, what, amount, total, h, (param)):
	(intf, messageWindow, pkgTimer) = param
        if (what == rpm.RPMCALLBACK_TRANS_START):
            # step 6 is the bulk of the transaction set
            # processing time
            if amount == 6:
                self.progressWindow = \
                   self.intf.progressWindow (_("Processing"),
                                             _("Preparing to install..."),
                                             total)
        if (what == rpm.RPMCALLBACK_TRANS_PROGRESS):
            if self.progressWindow:
                self.progressWindow.set (amount)
                
        if (what == rpm.RPMCALLBACK_TRANS_STOP and self.progressWindow):
            self.progressWindow.pop ()

        if (what == rpm.RPMCALLBACK_INST_OPEN_FILE):
	    # We don't want to start the timer until we get to the first
	    # file.
	    pkgTimer.start()

            intf.setPackage(h)
            intf.setPackageScale(0, 1)
            self.instLog.write (self.modeText % (h[rpm.RPMTAG_NAME],))
            self.instLog.flush ()
            fn = self.method.getFilename(h, pkgTimer)

	    self.rpmFD = -1
	    while self.rpmFD < 0:
		try:
		    self.rpmFD = os.open(fn, os.O_RDONLY)
		    # Make sure this package seems valid
		    try:
			(h, isSource) = rpm.headerFromPackage(self.rpmFD)
			os.lseek(self.rpmFD, 0, 0)
		    except:
			self.rpmFD = -1
			os.close(self.rpmFD)
			raise SystemError
		except:
		    messageWindow(_("Error"),
			_("The file %s cannot be opened. This is due to "
			  "a missing file, a bad package, or bad media. "
			  "Press <return> to try again.") % fn)

            fn = self.method.unlinkFilename(fn)
            return self.rpmFD
        elif (what == rpm.RPMCALLBACK_INST_PROGRESS):
            if total:
                intf.setPackageScale(amount, total)
        elif (what == rpm.RPMCALLBACK_INST_CLOSE_FILE):
            os.close (self.rpmFD)
            intf.completePackage(h, pkgTimer)
        else:
            pass

    def kernelVersionList(self):
	kernelVersions = []

	for ktag in [ 'kernel-smp', 'kernel-enterprise' ]:
	    tag = string.split(ktag, '-')[1]
	    if (self.hdList.has_key(ktag) and 
		self.hdList[ktag].selected):
		version = (self.hdList[ktag][rpm.RPMTAG_VERSION] + "-" +
			   self.hdList[ktag][rpm.RPMTAG_RELEASE] + tag)
		kernelVersions.append(version)
 
 	version = (self.hdList['kernel'][rpm.RPMTAG_VERSION] + "-" +
 		   self.hdList['kernel'][rpm.RPMTAG_RELEASE])
 	kernelVersions.append(version)
 
	return kernelVersions

    def copyExtraModules(self):
	kernelVersions = self.kernelVersionList()

        for (path, subdir, name) in self.extraModules:
	    pattern = ""
	    names = ""
	    for n in kernelVersions:
		pattern = pattern + " " + n + "/" + name + ".o"
		names = names + " " + name + ".o"
	    command = ("cd %s/lib/modules; gunzip < %s/modules.cgz | " +
			"%s/bin/cpio  --quiet -iumd %s") % \
		(self.instPath, path, self.instPath, pattern)
	    log("running: '%s'" % (command, ))
	    os.system(command)

	    for n in kernelVersions:
		fromFile = "%s/lib/modules/%s/%s.o" % (self.instPath, n, name)
		to = "%s/lib/modules/%s/kernel/drivers%s/%s.o" % \
			(self.instPath, n, subdir, name)

		if (os.access(fromFile, os.R_OK)):
		    log("copying %s to %s" % (fromFile, to))
		    os.rename(fromFile, to)
		else:
		    log("missing DD module %s (this may be okay)" % 
				fromFile)

    def depmodModules(self):
	kernelVersions = self.kernelVersionList()

        for version in kernelVersions:
	    iutil.execWithRedirect ("/sbin/depmod",
                                    [ "/sbin/depmod", "-a", version ],
                                    root = self.instPath, stderr = '/dev/null')

    def writeConfiguration(self):
        self.writeLanguage ()
        self.writeMouse ()
        self.writeKeyboard ()
        self.writeNetworkConfig ()
        self.setupAuthentication ()
	self.setupFirewall ()
        self.writeRootPassword ()
        self.createAccounts ()

        self.writeTimezone()

    def sortPackages(self, first, second):
        # install packages in cd order (cd tag is 1000002)
	one = None
	two = None

        if first[1000003] != None:
	    one = first[1000003]

        if second[1000003] != None:
	    two = second[1000003]

        if one == None or two == None:
            one = 0
            two = 0
            if first[1000002] != None:
                one = first[1000002]

            if second[1000002] != None:
                two = second[1000002]

	if one < two:
	    return -1
	elif one > two:
	    return 1
	elif string.lower(first[rpm.RPMTAG_NAME]) < string.lower(second[rpm.RPMTAG_NAME]):
	    return -1
	elif string.lower(first[rpm.RPMTAG_NAME]) > string.lower(second[rpm.RPMTAG_NAME]):
	    return 1

	return 0

    def doInstall(self):
	# make sure we have the header list and comps file
	self.getHeaderList()
	self.getCompsList()

        arch = iutil.getArch ()

        if arch == "alpha":
            # if were're on alpha with ARC console, set the clock
            # so that our installed files won't be in the future
            if onMILO ():
                args = ("clock", "-A", "-s")
                try:
                    iutil.execWithRedirect('/usr/sbin/clock', args)
                except:
                    pass

	# this is NICE and LATE. It lets kickstart/server/workstation
	# installs detect this properly
	if (self.hdList.has_key('kernel-smp') and isys.smpAvailable()):
	    self.hdList['kernel-smp'].selected = 1

	if (self.hdList.has_key('kernel-enterprise')):
	    import lilo

	    if lilo.needsEnterpriseKernel():
		self.hdList['kernel-enterprise'].selected = 1

	# we *always* need a kernel installed
	if (self.hdList.has_key('kernel')):
	    self.hdList['kernel'].selected = 1

        # if NIS is configured, install ypbind and dependencies:
        if self.auth.useNIS:
            self.hdList['ypbind'].selected = 1
            self.hdList['yp-tools'].selected = 1
            self.hdList['portmap'].selected = 1

        if self.auth.useLdap:
            self.hdList['nss_ldap'].selected = 1
            self.hdList['openldap'].selected = 1
            self.hdList['perl'].selected = 1

        if self.auth.useKrb5:
            self.hdList['pam_krb5'].selected = 1
            self.hdList['krb5-workstation'].selected = 1
            self.hdList['krbafs'].selected = 1
            self.hdList['krb5-libs'].selected = 1

        if self.x.server and not self.x.server == "XFree86":
            # trim off the XF86_
            try:
                self.selectPackage ('XFree86-' + self.x.server[5:])
            except ValueError, message:
                log ("Error selecting XFree86 server package: %s", message)

        # make sure that all comps that include other comps are
        # selected (i.e. - recurse down the selected comps and turn
        # on the children
        if self.setupFilesystems:
            if not self.upgrade:
		if (self.ddruidAlreadySaved):
		    self.fstab.makeFilesystems ()
		else:
		    self.fstab.savePartitions ()
		    self.fstab.makeFilesystems ()
		    self.fstab.turnOnSwap()

            self.fstab.mountFilesystems (self.instPath)

	self.method.mergeFullHeaders(self.hdList)

        if self.upgrade:
	    # An old mtab can cause confusion (esp if loop devices are
	    # in it)
	    f = open(self.instPath + "/etc/mtab", "w+")
	    f.close()

	if self.method.systemMounted (self.fstab, self.instPath, self.hdList.selected()):
	    self.fstab.umountFilesystems(self.instPath)
	    return 1

	if not self.installSystem: 
	    return

	for i in ( '/var', '/var/lib', '/var/lib/rpm', '/tmp', '/dev', '/etc',
                   '/etc/sysconfig', '/etc/sysconfig/network-scripts',
                   '/etc/X11' ):
	    try:
	        os.mkdir(self.instPath + i)
	    except os.error, (errno, msg):
                # self.intf.messageWindow("Error", "Error making directory %s: %s" % (i, msg))
                pass

	db = rpm.opendb(1, self.instPath)
	ts = rpm.TransactionSet(self.instPath, db)

        total = 0
	totalSize = 0

        if self.upgrade:
            how = "u"
        else:
            how = "i"

	l = []

	for p in self.hdList.selected():
            l.append(p)
	l.sort(self.sortPackages)

	for p in l:
            ts.add(p.h, p.h, how)
            total = total + 1
            totalSize = totalSize + (p[rpm.RPMTAG_SIZE] / 1024 )

        if not self.hdList.preordered():
            log ("WARNING: not all packages in hdlist had order tag")
            ts.order()

        if self.upgrade:
            logname = '/tmp/upgrade.log'
        else:
            logname = '/tmp/install.log'

        self.instLogName = self.instPath + logname
	self.instLog = open(self.instLogName, "w+")
	syslog = InstSyslog (self.instPath, self.instPath + logname)

	ts.scriptFd = self.instLog.fileno ()
	# the transaction set dup()s the file descriptor and will close the
	# dup'd when we go out of scope

	p = self.intf.packageProgressWindow(total, totalSize)

        if self.upgrade:
            self.modeText = _("Upgrading %s.\n")
        else:
            self.modeText = _("Installing %s.\n")

        oldError = rpm.errorSetCallback (self.rpmError)
	pkgTimer = timer.Timer(start = 0)

        problems = ts.run(0, ~rpm.RPMPROB_FILTER_DISKSPACE,
                          self.instCallback, 
			  (p, self.intf.messageWindow, pkgTimer))

#        problems = ts.run(rpm.RPMTRANS_FLAG_TEST, ~0,
#                          self.instCallback, (p, self.intf.messageWindow))

        if problems:
            spaceneeded = {}
            nodeneeded = {}
            size = 12

            # XXX
            nodeprob = -1
            if rpm.__dict__.has_key ("RPMPROB_DISKNODES"):
                nodeprob = rpm.RPMPROB_DISKNODES

            for (descr, (type, mount, need)) in problems:
                idx = string.find (mount, "/mnt/sysimage")
		if mount[0:13] == "/mnt/sysimage":
                    mount = mount[13:]
		    if not mount:
			mount = '/'

                if type == rpm.RPMPROB_DISKSPACE:
                    if spaceneeded.has_key (mount) and spaceneeded[mount] < need:
                        spaceneeded[mount] = need
                    else:
                        spaceneeded[mount] = need
                elif type == nodeprob:
                    if nodeneeded.has_key (mount) and nodeneeded[mount] < need:
                        nodeneeded[mount] = need
                    else:
                        nodeneeded[mount] = need
                else:
                    log ("WARNING: unhandled problem returned from transaction set type %d",
                         type)

            probs = ""
            if spaceneeded:
                probs = probs + _("You don't appear to have enough disk space to install "
                                  "the packages you've selected. You need more space on the "
                                  "following filesystems:\n\n")
                probs = probs + ("%-15s %s\n") % (_("Mount Point"), _("Space Needed"))

                for (mount, need) in spaceneeded.items ():
                    if need > (1024*1024):
                        need = (need + 1024 * 1024 - 1) / (1024 * 1024)
                        suffix = "M"
                    else:
                        need = (need + 1023) / 1024
                        suffix = "k"

                    prob = "%-15s %d %c\n" % (mount, need, suffix)
                    probs = probs + prob
            if nodeneeded:
                probs = probs + _("You don't appear to have enough file nodes to install "
                                  "the packages you've selected. You need more file nodes on the "
                                  "following filesystems:\n\n")
                probs = probs + ("%-15s %s\n") % (_("Mount Point"), _("Nodes Needed"))

                for (mount, need) in nodeneeded.items ():
                    prob = "%-15s %d\n" % (mount, need)
                    probs = probs + prob

            self.intf.messageWindow (_("Disk Space"), probs)

	    del ts
	    del db
	    self.instLog.close()
	    del syslog


	    self.method.systemUnmounted ()
	    self.fstab.umountFilesystems(self.instPath)
            
            rpm.errorSetCallback (oldError)
            return 1

        # This should close the RPM database so that you can
        # do RPM ops in the chroot in a %post ks script
        del ts
        del db
        rpm.errorSetCallback (oldError)
        
        self.method.filesDone ()
        
        del p

        if self.upgrade:
            self.instLog.write ("\n\nThe following packages were available on the CD but NOT upgraded:\n")
            for p in self.hdList.packages.values ():
                if not p.selected:
                    self.instLog.write("%s-%s-%s.%s.rpm\n" %
                                       (p.h[rpm.RPMTAG_NAME],
                                        p.h[rpm.RPMTAG_VERSION],
                                        p.h[rpm.RPMTAG_RELEASE],
                                        p.h[rpm.RPMTAG_ARCH]))
        self.instLog.close ()

        w = self.intf.progressWindow(_("Post Install"), 
			     _("Performing post install configuration..."), 8)

        try:
            if not self.upgrade:
                self.fstab.addMount(self.fdDevice, "/mnt/floppy", "auto")

		w.set(1)

                self.copyExtraModules()
                self.fstab.write (self.instPath)
                self.writeConfiguration ()
                self.writeDesktop ()
                if (self.instClass.defaultRunlevel):
                    self.initlevel = self.instClass.defaultRunlevel
                    self.setDefaultRunlevel ()

		w.set(2)

                # pcmcia is supported only on i386 at the moment
                if arch == "i386":
                    pcmcia.createPcmciaConfig(
			    self.instPath + "/etc/sysconfig/pcmcia")
			   
                self.copyConfModules ()
                if not self.x.skip and self.x.server:
                    if os.access (self.instPath + "/etc/X11/X", os.R_OK):
                        os.rename (self.instPath + "/etc/X11/X",
                                   self.instPath + "/etc/X11/X.rpmsave")
                    try:
                        os.unlink (self.instPath + "/etc/X11/X")
                    except OSError:
                        pass
                    os.symlink ("../../usr/X11R6/bin/" + self.x.server,
                                self.instPath + "/etc/X11/X")

                    self.x.write (self.instPath + "/etc/X11")
                self.setDefaultRunlevel ()

		w.set(3)

                # blah.  If we're on a serial mouse, and we have X, we need to
                # close the mouse device, then run kudzu, then open it again.

                # turn it off
                mousedev = None

                # XXX currently Bad Things (X async reply) happen when doing
                # Mouse Magic on Sparc (Mach64, specificly)
                if os.environ.has_key ("DISPLAY") and not arch == "sparc":
                    import xmouse
                    try:
                        mousedev = xmouse.get()[0]
                    except RuntimeError:
                        pass

                if mousedev:
                    try:
                        os.rename (mousedev, "/dev/disablemouse")
                    except OSError:
                        pass
                    try:
                        xmouse.reopen()
                    except RuntimeError:
                        pass

                log("Mounting /proc/bus/usb in install path")
                unmountUSB = 0
                try:
                    isys.mount('/usbdevfs', self.instPath+'/proc/bus/usb', 'usbdevfs')
                    log("Mount of USB succeeded")
                    unmountUSB = 1
                except:
                    log("Mount of USB failed")
                    pass

                    
                argv = [ "/usr/sbin/kudzu", "-q" ]
                devnull = os.open("/dev/null", os.O_RDWR)
                iutil.execWithRedirect(argv[0], argv, root = self.instPath,
                                       stdout = devnull)
                # turn it back on            
                if mousedev:
                    try:
                        os.rename ("/dev/disablemouse", mousedev)
                    except OSError:
                        pass
                    try:
                        xmouse.reopen()
                    except RuntimeError:
                        pass
                if unmountUSB:
                    isys.umount(self.instPath + '/proc/bus/usb', removeDir = 0)

	    w.set(4)

            if self.upgrade:
                # move the rebuilt db into place.
                try:
                    iutil.rmrf (self.instPath + "/var/lib/rpm.rpmsave")
                except OSError:
                    pass
                os.rename (self.instPath + "/var/lib/rpm",
                           self.instPath + "/var/lib/rpm.rpmsave")
                os.rename (self.instPath + self.dbpath,
                           self.instPath + "/var/lib/rpm")

                # XXX - rpm 4.0.2 %post braindeadness support
                try:
                    os.unlink (self.instPath + "/etc/rpm/macros.db1")
                except OSError:
                    pass

                # needed for prior systems which were not xinetd based
                self.migrateXinetd()

            # XXX make me "not test mode"
            if self.setupFilesystems:
                if arch == "sparc":
                    self.silo.install (self.fstab, self.instPath, self.hdList, 
                                       self.upgrade)
                elif arch == "i386":
                    self.lilo.install (self.fstab, self.instPath, self.hdList, 
                                       self.upgrade)
                elif arch == "ia64":
                    self.eli.install (self.fstab, self.instPath, self.hdList, 
                                       self.upgrade)
                elif arch == "alpha":
                    self.milo.write ()
                else:
                    raise RuntimeError, "What kind of machine is this, anyway?!"

		w.set(5)


                # go ahead and depmod modules as modprobe in rc.sysinit
                # will complain loaduly if we don't do it now.
                self.depmodModules()

	    w.set(6)

            self.instClass.postAction(self.instPath, self.serial)

	    w.set(7)

            if self.setupFilesystems:
                f = open("/tmp/cleanup", "w")
                self.method.writeCleanupPath(f)
                self.fstab.writeCleanupPath(f)
                f.close()

	    w.set(8)

            del syslog

        finally:
            w.pop ()
        sys.stdout.flush()
