import rpm, os
rpm.addMacro("_i18ndomains", "redhat-dist");

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
import fstab
import time
import gettext_rh
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

        for key in keys:
	    if key == 'ONBOOT' and forceOffOnBoot:
		s = s + key + "=" + 'no' + "\n"
	    else:
		s = s + key + "=" + self.info[key] + "\n"

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

	if not self.isConfigured:
	    for dev in self.netdevices.values():
		if dev.get('bootproto') == "dhcp":
		    self.primaryNS = isys.pumpNetDevice(dev.get('device'))
		    break
		elif dev.get('ipaddr') and dev.get('netmask'):
		    isys.configNetDevice(dev.get('device'),
			    dev.get('ipaddr'), dev.get('netmask'),
			    self.gateway)
		    break

	if not self.primaryNS: return

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

class Language (SimpleConfigFile):
    def __init__ (self):
        self.info = {}

	if os.access("lang-table", os.R_OK):
	    f = open("lang-table", "r")
	elif os.access("/etc/lang-table", os.R_OK):
	    f = open("/etc/lang-table", "r")
	else:
	    f = open("/usr/lib/anaconda/lang-table", "r")

	lines = f.readlines ()
	f.close()
	self.langs = {}
	self.font = {}
	self.map = {}

	for line in lines:
	    string.strip(line)
	    l = string.split(line)
	    self.langs[l[0]] = l[4]
	    self.font[l[0]] = l[2]
	    self.map[l[0]] = l[3]
	
        # kickstart needs this
        self.abbrevMap = {}
        for (key, value) in self.langs.items ():
            self.abbrevMap[value] = key

	self.setByAbbrev("en_US")

    def available (self):
        return self.langs

    def setByAbbrev(self, lang):
	self.set(self.abbrevMap[lang])
    
    def set (self, lang):
        self.lang = self.langs[lang]
        self.info["LANG"] = self.langs[lang]
        os.environ["LANG"] = self.langs[lang]

	if self.font[lang] != "None":
	    self.info["SYSFONT"] = self.font[lang]
	    self.info["SYSFONTACM"] = self.map[lang]
	else:
            if self.info.has_key("SYSFONT"):
                del self.info["SYSFONT"]
            if self.info.has_key("SYSFONTACM"):
                del self.info["SYSFONTACM"]

	rpm.addMacro("_install_langs", self.langs[lang]);
        os.environ["LINGUAS"] = self.langs[lang]
        
    def get (self):
	return self.lang

    def getFontMap (self, lang):
	return self.map[lang]

    def getFontFile (self, lang):
	# Note: in /etc/fonts.cgz fonts are named by the map
	# name as that's unique, font names are not
	return self.font[lang]

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
        self.language = Language ()
	self.serial = serial
        self.reconfigOnly = reconfigOnly
        self.network = Network ()
        self.rootpassword = Password ()
        self.extraModules = extraModules
        self.mouse = Mouse ()
        self.keyboard = Keyboard ()
        self.auth = Authentication ()
        self.desktop = Desktop ()
        self.ddruidReadOnly = 0
        self.bootdisk = 1

        log.open (serial, reconfigOnly, test)

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
	elif iutil.getArch() == "ia64":
	    fdDevice = "hda"
	elif iutil.getArch() == "i386":
	    # Look for the first IDE floppy device
	    drives = isys.hardDriveDict().keys()

	    # We don't need to be picky about sort order as we toss
	    # items that aren't hd* anyway
	    drives.sort()
	    floppyDrive = None
	    for drive in drives:
		if drives[0:2] != 'hd': continue
		f = open("/proc/ide/%s/media" % floppyDevice, "r")
		type = f.readline()
		f.close()
		if type == "floppy\n":
		    floppyDrive = drive
		    break

	    # No IDE floppy's -- we're fine w/ /dev/fd0
	    if not floppyDrive: return

	    # Look in syslog for a real fd0 (which would take precedence)
	    f = open("/tmp/syslog", "r")
	    for line in f.readlines():
		# chop off the loglevel (which init's syslog leaves behind)
		line = line[1:]
		match = "Floppy drive(s): "
		if match == line[:len(match)]:
		    # Good enough
		    return

	    self.fdDevice = "%s" % floppyDevice
	else:
	    raise SystemError, "cannot determine floppy device for this arch"

    def writeTimezone(self):
	if (self.timezone):
	    (timezone, asUtc, asArc) = self.timezone
	    fromFile = self.instPath + "/usr/share/zoneinfo/" + timezone

            try:
                iutil.copyFile(fromFile, self.instPath + "/etc/localtime")
            except OSError, (errno, msg):
                self.intf.messageWindow(_("Error"),
		    _("Error copying timezone (from %s): %s") % (fromFile, msg))
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
	f = open(self.instPath + "/etc/sysconfig/desktop", "w")
	f.write(str (self.desktop))
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
        kernelTag = "-%s-%s" % (kernel['version'], kernel['release'])

        w = self.intf.waitWindow (_("Creating"), _("Creating boot disk..."))
        rc = iutil.execWithRedirect("/sbin/mkbootdisk",
                                    [ "/sbin/mkbootdisk",
                                      "--noprompt",
                                      "--device",
                                      "/dev/" + self.fdDevice,
                                      kernelTag[1:] ],
                                    stdout = None, stderr = None, 
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
	if (not self.comps):
	    self.getHeaderList()
	    self.comps = self.method.readComps(self.hdList)
            self.updateInstClassComps()
            
	return self.comps

    def updateInstClassComps(self):
	# don't load it just for this
	if (not self.comps): return

	group = self.instClass.getGroups()
	packages = self.instClass.getPackages()
	if (group == None and packages == None): return 0
	for n in self.comps.keys():
	    self.comps[n].unselect()

	self.comps['Base'].select()
	if group:
	    for n in group:
		self.comps[n].select()

	if packages:
	    for n in packages:
		self.selectPackage(n)

        if self.x.server and not self.x.server == "XFree86":
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
            f = open (self.instPath + "/etc/sysconfig/network-scripts/ifcfg-" + device, "w")
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
            crypt = self.rootpassword.getCrypted ()
            devnull = os.open("/dev/null", os.O_RDWR)

            argv = [ "/usr/sbin/usermod", "-p", crypt, "root" ]
            iutil.execWithRedirect(argv[0], argv, root = self.instPath, 
                                   stdout = devnull, stderr = None)
            os.close(devnull)

    def setupAuthentication (self):
        args = [ "/usr/sbin/authconfig", "--kickstart", "--nostart" ]
        if self.auth.useShadow:
            args.append ("--useshadow")
        if self.auth.useMD5:
            args.append ("--enablemd5")

        if self.auth.useNIS:
            args.append ("--enablenis")
            args.append ("--nisdomain")
            args.append (self.auth.nisDomain)
            if not self.auth.nisuseBroadcast:
                args.append ("--nisserver")
                args.append (self.auth.nisServer)

        if self.auth.useLdap:
            args.append ("--enableldap")
        if self.auth.useLdapauth:
            args.append ("--enableldapauth")
        if self.auth.useLdap or self.auth.useLdapauth:
            args.append ("--ldapserver")
            args.append (self.auth.ldapServer)
            args.append ("--ldapbasedn")
            args.append (self.auth.ldapBasedn)

        if self.auth.useKrb5:
            args.append ("--enablekrb5")
            args.append ("--krb5realm")
            args.append (self.auth.krb5Realm)
            args.append ("--krb5kdc")
            args.append (self.auth.krb5Kdc)
            args.append ("--krb5adminserver")
            args.append (self.auth.krb5Admin)

        if self.auth.useHesiod:
            args.append ("--enablehesiod")
            args.append ("--hesiodlhs")
            args.append (self.auth.hesiodLhs)
            args.append ("--hesiodrhs")
            args.append (self.auth.hesiodRhs)

        log ("running authentication cmd |%s|" % args)
        iutil.execWithRedirect(args[0], args,
                              stdout = None, stderr = None, searchPath = 1,
                              root = self.instPath)

    def copyConfModules (self):
        try:
            inf = open ("/tmp/modules.conf", "r")
        except:
            pass
        else:
            out = open (self.instPath + "/etc/modules.conf", "a")
            out.write (inf.read ())

    def verifyDeps (self):
	win = self.intf.waitWindow(_("Dependency Check"),
	  _("Checking dependencies in packages selected for installation..."))
	self.getCompsList()
        if self.upgrade:
            self.fstab.mountFilesystems (self.instPath)
            db = rpm.opendb (0, self.instPath)
            ts = rpm.TransactionSet(self.instPath, db)
        else:
            ts = rpm.TransactionSet()
            
        self.comps['Base'].select ()

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
                    log ("%s-%s-%s conflicts with to-be-installed "
                              "package %s, removing from set",
                              name, version, release, reqname)
                    if self.hdList.packages.has_key (reqname):
                        self.hdList.packages[reqname].selected = 0
                        log ("... removed")

        del ts
        if self.upgrade:
            del db
            self.fstab.umountFilesystems (self.instPath)            

	win.pop()

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
                    

    def upgradeFindRoot (self):
        rootparts = []
        if not self.setupFilesystems: return [ self.instPath ]
        win = self.intf.waitWindow (_("Searching"),
                                    _("Searching for Red Hat Linux installations..."))
        
        drives = self.fstab.driveList()
	mdList = raid.startAllRaid(drives)

	for dev in mdList:
            if fstab.isValidExt2 (dev):
                try:
                    isys.mount(dev, '/mnt/sysimage')
                except SystemError, (errno, msg):
                    self.intf.messageWindow(_("Error"),
                                            _("Error mounting ext2 filesystem on %s: %s") % (dev, msg))
                    continue
                if os.access ('/mnt/sysimage/etc/fstab', os.R_OK):
                    rootparts.append (dev)
                isys.umount('/mnt/sysimage')

	raid.stopAllRaid(mdList)
	
        for drive in drives:
            isys.makeDevInode(drive, '/tmp/' + drive)
            
            try:
                table = _balkan.readTable ('/tmp/' + drive)
            except SystemError:
                pass
            else:
                for i in range (len (table)):
                    (type, sector, size) = table[i]
                    if size and type == _balkan.EXT2:
			# for RAID arrays of format c0d0p1
			if drive [:3] == "rd/" or drive [:4] == "ida/":
                            dev = drive + 'p' + str (i + 1)
			else:
                            dev = drive + str (i + 1)
                        try:
                            isys.mount(dev, '/mnt/sysimage')
                        except SystemError, (errno, msg):
                            self.intf.messageWindow(_("Error"),
                                                    _("Error mounting ext2 filesystem on %s: %s") % (dev, msg))
                            continue
                        if os.access ('/mnt/sysimage/etc/fstab', os.R_OK):
                            rootparts.append (dev)
                        isys.umount('/mnt/sysimage')
            os.remove ('/tmp/' + drive)
        win.pop ()
        return rootparts

    def upgradeFindPackages (self, root):
        win = self.intf.waitWindow (_("Finding"),
                                    _("Finding packages to upgrade..."))
        if self.setupFilesystems:
	    mdList = raid.startAllRaid(self.fstab.driveList())
            isys.mount(root, '/mnt/sysimage')
	    fstab.readFstab('/mnt/sysimage/etc/fstab', self.fstab)
            isys.umount('/mnt/sysimage')        
	    raid.stopAllRaid(mdList)

	    if self.fstab.hasDirtyFilesystems():
		win.pop()
		self.intf.messageWindow(("Dirty Filesystems"),
		    _("One or more of the filesystems for your Linux system "
		      "was not unmounted cleanly. Please boot your Linux "
		      "installation, let the filesystems be checked, and "
		      "shut down cleanly to upgrade."))
                os.kill (os.getpid(), 9)    

            self.fstab.mountFilesystems (self.instPath)
	    self.fstab.turnOnSwap(formatSwap = 0)
        self.getCompsList ()
	self.getHeaderList ()

        self.dbpath = "/var/lib/anaconda-rebuilddb" + str(int(time.time()))
        rpm.addMacro("_dbpath_rebuild", self.dbpath);

        # now, set the system clock so the timestamps will be right:
        iutil.setClock (self.instPath)
        
        # and rebuild the database so we can run the dependency problem
        # sets against the on disk db
        rc = rpm.rebuilddb (self.instPath)
        if rc:
            self.intf.messageWindow(_("Error"),
                                    _("Rebuild of RPM database failed. "
                                      "You may be out of disk space?"))
            raise RuntimeError, "Rebuild of RPM database failed."

### XXXXXXXXXXXXXXXXXXXXXXXXXXX fix me - move the replace back down to
#                               doInstall        
#        rpm.addMacro("_dbpath", self.dbpath);

        # move the rebuilt db into place.
        os.rename (self.instPath + "/var/lib/rpm",
                   self.instPath + "/var/lib/anaconda-oldrpm" + str(int(time.time())))
        os.rename (self.instPath + self.dbpath,
                   self.instPath + "/var/lib/rpm")
        rpm.addMacro ("_dbpath", "%{_var}/lib/rpm")
#        iutil.rmrf (self.instPath + "/var/lib/rpm-old")

        # flag this so we only do it once.
        self.dbpath = None

        packages = rpm.findUpgradeSet (self.hdList.hdlist, self.instPath)
        # unselect all packages
        for package in self.hdList.packages.values ():
            package.selected = 0

        # always upgrade all packages in Base package group
        # XXX, well - people say this isn't a good idea, so we won't
        # do it anymore.
#	self.comps['Base'].select()

        hasX = 0
        hasgmc = 0
        # turn on the packages in the upgrade set
        for package in packages:
            self.hdList[package[rpm.RPMTAG_NAME]].selected = 1
            if package[rpm.RPMTAG_NAME] == "XFree86":
                hasX = 1
            if package[rpm.RPMTAG_NAME] == "gmc":
                hasgmc = 1

        # open up the database to check dependencies
        db = rpm.opendb (0, self.instPath)

        # if we have X but not gmc, we need to turn on GNOME.  We only
        # want to turn on packages we don't have installed already, though.
        if hasX and not hasgmc:
            log ("Has X but not GNOME")
            for package in self.comps['GNOME'].pkgs:
                rec = db.findbyname (package.name)
                if not rec:
                    log ("GNOME: Adding %s", package)
                    package.select()
            
        del db
        self.fstab.umountFilesystems (self.instPath)

        # new package dependency fixup
        deps = self.verifyDeps ()

        for (name, suggest) in deps:
            log ("Upgrade Dependency: %s needs %s, automatically added.", name, suggest)
        self.selectDeps (deps)
        win.pop ()

    def rpmError (todo):
        todo.instLog.write (rpm.errorString () + "\n")

    def getClass(todo):
	return todo.instClass

    def setClass(todo, instClass):
	todo.instClass = instClass
	todo.hostname = todo.instClass.getHostname()
	todo.updateInstClassComps()
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
	    todo.lilo.setAppend(append)
 	elif arch == "sparc":
	    todo.silo.setDevice(where)
	    todo.silo.setAppend(append)

#
#       only important for ks - not needed here for general case so
#       commenting out for now...
#
#	for (mntpoint, (dev, fstype, reformat)) in todo.instClass.fstab:
#	    todo.fstab.addMount(dev, mntpoint, fstype, reformat)

	todo.users = []
	if todo.instClass.rootPassword:
	    todo.rootpassword.set(todo.instClass.rootPassword,
			      isCrypted = todo.instClass.rootPasswordCrypted)
	if todo.instClass.language:
	    todo.language.setByAbbrev(todo.instClass.language)

	if todo.instClass.keyboard:
	    todo.keyboard.set(todo.instClass.keyboard)
            if todo.instClass.keyboard != "us":
                xkb = todo.keyboard.getXKB ()

                if xkb:
                    apply (todo.x.setKeyboard, xkb)

                    # hack - apply to instclass preset if present as well
                    if (todo.instClass.x):
                        apply (todo.instClass.x.setKeyboard, xkb)

	(bootProto, ip, netmask, gateway, nameserver) = \
		todo.instClass.getNetwork()
	if bootProto:
	    todo.network.gateway = gateway
	    todo.network.primaryNS = nameserver

	    devices = todo.network.available ()
	    if (devices and bootProto):
		list = devices.keys ()
		list.sort()
		dev = devices[list[0]]
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
            
        if todo.instClass.desktop:
            todo.desktop.set (todo.instClass.desktop)

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

    def setPassword(todo, account, password):
	devnull = os.open("/dev/null", os.O_RDWR)

	argv = [ "/usr/bin/passwd", "--stdin", account ]
	p = os.pipe()
	os.write(p[1], password + "\n")
	iutil.execWithRedirect(argv[0], argv, root = todo.instPath, 
			       stdin = p[0], stdout = devnull)
	os.close(p[0])
	os.close(p[1])
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

    def createCdrom(self):
        log ("making cd-rom links")
	list = isys.cdromList()
	count = 0
	for device in list:
	    cdname = "cdrom"
	    if (count):
		cdname = "%s%d" % (cdname, count)
	    count = count + 1

            log ("creating cdrom link for " + device)
            try:
                os.stat(self.instPath + "/dev/" + cdname)
                log ("link exists, removing")
                os.unlink(self.instPath + "/dev/" + cdname)
            except OSError:
                pass
	    os.symlink(device, self.instPath + "/dev/" + cdname)
	    mntpoint = "/mnt/" + cdname
	    self.fstab.addMount(cdname, mntpoint, "iso9660")

    def createRemovable(self, rType):
	devDict = isys.floppyDriveDict()

	d = isys.hardDriveDict()
	for item in d.keys():
	    devDict[item] = d[item]

	list = devDict.keys()
	list.sort()

	count = 0
	for device in list:
	    descript = devDict[device]
	    if string.find(string.upper(descript), string.upper(rType)) == -1:
		continue

	    log ("found %s disk, creating link", rType)

	    try:
		os.stat(self.instPath + "/dev/%s" % rType)
		log ("link exists, removing")
		os.unlink(self.instPath + "/dev/%s" % rType)
	    except OSError:
		pass
	    # the 4th partition of zip/jaz disks is the one that usually
	    # contains the DOS filesystem.  We'll guess at using that
	    # one, it is a sane default.
	    device = device + "4";
	    os.symlink(device, self.instPath + "/dev/%s" % rType)
	    mntpoint = "/mnt/%s" % rType
	    self.fstab.addMount(rType, mntpoint, "auto")

    def setDefaultRunlevel (self):
        inittab = open (self.instPath + '/etc/inittab', 'r')
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
        
    def instCallback(self, what, amount, total, h, intf):
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
            intf.setPackage(h)
            intf.setPackageScale(0, 1)
            self.instLog.write (self.modeText % (h[rpm.RPMTAG_NAME],))
            self.instLog.flush ()
            fn = self.method.getFilename(h)
            self.rpmFD = os.open(fn, os.O_RDONLY)
            fn = self.method.unlinkFilename(fn)
            return self.rpmFD
        elif (what == rpm.RPMCALLBACK_INST_PROGRESS):
            if total:
                intf.setPackageScale(amount, total)
        elif (what == rpm.RPMCALLBACK_INST_CLOSE_FILE):
            os.close (self.rpmFD)
            intf.completePackage(h)
        else:
            pass

    def copyExtraModules(self):
	kernelVersions = []
	
	if (self.hdList.has_key('kernel-smp') and 
	    self.hdList['kernel-smp'].selected):
	    version = (self.hdList['kernel-smp']['version'] + "-" +
		       self.hdList['kernel-smp']['release'] + "smp")
	    kernelVersions.append(version)

	version = (self.hdList['kernel']['version'] + "-" +
		   self.hdList['kernel']['release'])
	kernelVersions.append(version)

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
		to = "%s/lib/modules/%s/%s/%s.o" % (self.instPath, n, 
							subdir, name)

		if (os.access(fromFile, os.R_OK)):
		    log("copying %s to %s" % (fromFile, to))
		    os.rename(fromFile, to)
		else:
		    log("missing DD module %s (this may be okay)" % 
				fromFile)

    def depmodModules(self):
	kernelVersions = []
	
	if (self.hdList.has_key('kernel-smp') and 
	    self.hdList['kernel-smp'].selected):
	    version = (self.hdList['kernel-smp']['version'] + "-" +
		       self.hdList['kernel-smp']['release'] + "smp")
	    kernelVersions.append(version)

	version = (self.hdList['kernel']['version'] + "-" +
		   self.hdList['kernel']['release'])
	kernelVersions.append(version)

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
        self.writeRootPassword ()
        self.createAccounts ()
        self.writeTimezone()

    def sortPackages(self, first, second):
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
	elif string.lower(first['name']) < string.lower(second['name']):
	    return -1
	elif string.lower(first['name']) > string.lower(second['name']):
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

#        if self.upgrade and self.dbpath:
            # move the rebuilt db into place.
#              os.rename (self.instPath + "/var/lib/rpm",
#                         self.instPath + "/var/lib/rpm-old")
#              os.rename (self.instPath + self.dbpath,
#                         self.instPath + "/var/lib/rpm")
#              rpm.addMacro ("_dbpath", "%{_var}/lib/rpm")
#              iutil.rmrf (self.instPath + "/var/lib/rpm-old")
#              # flag this so we only do it once.
#              self.dbpath = None

        self.method.systemMounted (self.fstab, self.instPath)

	if not self.installSystem: 
	    return

	for i in [ '/var', '/var/lib', '/var/lib/rpm', '/tmp', '/dev' ]:
	    try:
	        os.mkdir(self.instPath + i)
	    except os.error, (errno, msg):
                # self.intf.messageWindow("Error", "Error making directory %s: %s" % (i, msg))
                pass

        # XXX in case we started out in Upgrade land, we need to
        # reset this macro to point to the right place.
        rpm.addMacro ("_dbpath", "%{_var}/lib/rpm")
        rpm.addMacro ("_dbi_config", "hash perms=0644")
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

        # XXX HACK HACK for Japanese.
        #     Remove me when the japanese locales are in glibc package
	localePackage = self.hdList['locale-ja'].h
	l = [ localePackage ] + l
	total = total + 1
	totalSize = totalSize + localePackage[rpm.RPMTAG_SIZE]

	for p in l:
            if p['name'] != 'locale-ja':
                ts.add(p.h, p.h, how)
                total = total + 1
                totalSize = totalSize + p['size']

	ts.order()

        if self.upgrade:
            logname = '/tmp/upgrade.log'
        else:
            logname = '/tmp/install.log'
            
	self.instLog = open(self.instPath + logname, "w+")
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

        problems = ts.run(0, ~rpm.RPMPROB_FILTER_DISKSPACE,
                          self.instCallback, p)
        
        if problems:
            needed = {}
            size = 12
            for (descr, (type, mount, need)) in problems:
                idx = string.find (mount, "/mnt/sysimage")
                if idx != -1:
                    # 13 chars in /mnt/sysimage
                    mount = mount[13:]

                if needed.has_key (mount) and needed[mount] < need:
                    needed[mount] = need
                else:
                    needed[mount] = need
                    
            probs = _("You don't appear to have enough disk space to install "
                      "the packages you've selected. You need more space on the "
                      "following filesystems:\n\n")
            probs = probs + ("%-15s %s\n") % (_("Mount Point"), _("Space Needed"))
                    
            for (mount, need) in needed.items ():
                if need > (1024*1024):
                    need = (need + 1024 * 1024 - 1) / (1024 * 1024)
                    suffix = "M"
                else:
                    need = (need + 1023) / 1024
                    suffix = "k"

                prob = "%-15s %d %c\n" % (mount, need, suffix)
                probs = probs + prob
                
            self.intf.messageWindow (_("Disk Space"), probs)

	    del ts
	    del db
	    self.instLog.close()
	    del syslog

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

        self.instLog.close ()

        w = self.intf.waitWindow(_("Post Install"), 
                                 _("Performing post install configuration..."))

        if not self.upgrade:
	    self.createCdrom()
	    self.createRemovable("zip")
	    self.createRemovable("jaz")
	    self.copyExtraModules()
            self.fstab.write (self.instPath, fdDevice = self.fdDevice)
            self.writeConfiguration ()
            self.writeDesktop ()
	    if (self.instClass.defaultRunlevel):
		self.initlevel = self.instClass.defaultRunlevel
		self.setDefaultRunlevel ()
            
            # pcmcia is supported only on i386 at the moment
            if arch == "i386":
                pcmcia.createPcmciaConfig(self.instPath + "/etc/sysconfig/pcmcia")
            self.copyConfModules ()
            if not self.x.skip and self.x.server:
		if self.x.server[0:3] == 'Sun':
                    try:
                        os.unlink(self.instPath + "/etc/X11/X")
                    except:
                        pass
		    script = open(self.instPath + "/etc/X11/X","w")
		    script.write("#!/bin/bash\n")
		    script.write("exec /usr/X11R6/bin/Xs%s -fp unix/:-1 $@\n" % self.x.server[1:])
		    script.close()
		    os.chmod(self.instPath + "/etc/X11/X", 0755)
		else:
                    if os.access (self.instPath + "/etc/X11/X", os.R_OK):
                        os.rename (self.instPath + "/etc/X11/X",
                                   self.instPath + "/etc/X11/X.rpmsave")
		    os.symlink ("../../usr/X11R6/bin/" + self.x.server,
				self.instPath + "/etc/X11/X")

		self.x.write (self.instPath + "/etc/X11")
            self.setDefaultRunlevel ()

            # go ahead and depmod modules on alpha, as rtc modprobe
            # will complain loudly if we don't do it now.
#            if arch == "alpha":
#                self.depmodModules()

            # lets just do it always, not just on alpha
            self.depmodModules()
                
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

	self.instClass.postAction(self.instPath, self.serial)

	if self.setupFilesystems:
	    f = open("/tmp/cleanup", "w")
	    self.method.writeCleanupPath(f)
	    self.fstab.writeCleanupPath(f)
	    f.close()

        del syslog
        
        w.pop ()

