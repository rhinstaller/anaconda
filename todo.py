# For an install to proceed, the following todo fields must be filled in
#
#	mount list (unless todo.runLive)		addMount()
#	lilo boot.b installation (may be None)		liloLocation()

import rpm, os
import iutil, isys
from lilo import LiloConfiguration
from syslogd import Syslogd
import string
import socket
import crypt
import whrandom
import _balkan

def _(x):
    return x

class LogFile:
    def __init__ (self):
        self.logFile = open("/dev/tty3", "w")

    def __call__ (self, format, *args):
        if args:
            self.logFile.write (format % args)
        else:
            self.logFile.write (format)

    def getFile (self):
        return self.logFile.fileno ()
            
class SimpleConfigFile:
    def __str__ (self):
        s = ""
        keys = self.info.keys ()
        keys.sort ()
        for key in keys:
            # FIXME - use proper escaping
            s = s + key + "=\"" + self.info[key] + "\"\n"
        return s
            
    def __init__ (self):
        self.info = {}

    def set (self, *args):
        for (key, data) in args:
            self.info[string.upper (key)] = data

    def unset (self, *keys):
        for key in keys:
            key = string.upper (key)
            if self.info.has_key (key):
               del self.info[key] 

    def get (self, key):
        key = string.upper (key)
        if self.info.has_key (key):
            return self.info[key]
        else:
            return ""


class NetworkDevice (SimpleConfigFile):
    def __str__ (self):
        s = ""
        s = s + "DEVICE=" + self.info["DEVICE"] + "\n"
        keys = self.info.keys ()
        keys.sort ()
        keys.remove ("DEVICE")
        for key in keys:
            s = s + key + "=" + self.info[key] + "\n"
        return s

    def __init__ (self, dev):
        self.info = { "DEVICE" : dev }
        self.hostname = ""

class Network:
    def __init__ (self):
        self.netdevices = {}
        self.gateway = ""
        self.primaryNS = ""
        self.secondaryNS = ""
        self.ternaryNS = ""
        self.domains = []
        try:
            f = open ("/tmp/netinfo", "r")
        except:
            pass
        else:
            lines = f.readlines ()
            info = {}
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
            if info.has_key ("GATEWAY"):
                self.gateway = info["GATEWAY"]
            if info.has_key ("NS1"):
                self.primaryNS = info["NS1"]
    
    def available (self):
        if self.netdevices:
            return self.netdevices
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

    def guessHostnames (self):
        # guess the hostname for the first device with an IP
        # XXX fixme - need to set up resolv.conf
        self.domains = []
        for dev in self.netdevices.values ():
            ip = dev.get ("ipaddr")
            if ip:
                try:
                    (hostname, aliases, ipaddrs) = socket.gethostbyaddr (ip)
                except socket.error:
                    hostname = ""
                if hostname:
                    dev.hostname = hostname
                    if '.' in hostname:
                        # chop off everything before the leading '.'
                        self.domains.append (hostname[(string.find (hostname, '.') + 1):])
            else:
                dev.hostname = "localhost.localdomain"
        if not self.domains:
            self.domains = [ "localdomain" ]

    def nameservers (self):
        return [ self.primaryNS, self.secondaryNS, self.ternaryNS ]

class Password:
    def __init__ (self):
        self.crypt = ""

    def set (self, password, isCrypted = 0):
        if not isCrypted:
            salt = (whrandom.choice (string.letters +
                                     string.digits + './') + 
                    whrandom.choice (string.letters +
                                     string.digits + './'))
            self.crypt = crypt.crypt (password, salt)
        else:
            self.crypt = password

    def get (self):
        return self.crypt
            
class Language (SimpleConfigFile):
    def __init__ (self):
        self.info = {}
        self.lang = None
        self.langs = {
            "English" : "C",
            "German" : "de",
            }

    def available (self):
        return self.langs
    
    def set (self, lang):
        self.lang = self.langs[lang]
        self.info["LANG"] = self.langs[lang]
        self.info["LINGUAS"] = self.langs[lang]
        self.info["LC_ALL"] = self.langs[lang]
        
    def get (self):
        if self.lang:
            return self.lang
        else:
            return "C"

class Mouse (SimpleConfigFile):
    # XXX fixme - externalize
    def __init__ (self):
        self.info = {}
        self.mice = {
            "ALPS - GlidePoint (PS/2)" :
                    ("ps/2", "GlidePointPS/2", "psaux"),
            "ASCII - MieMouse (serial)" :
                    ("ms3", "IntelliMouse", "ttyS"),
            "ASCII - MieMouse (PS/2)" : 
                    ("ps/2", "NetMousePS/2", "psaux"),
            "ATI - Bus Mouse" :
                    ("Busmouse", "BusMouse", "atibm"),
            "Generic - 2 Button Mouse (serial)" :
                    ("Microsoft", "Microsoft", "ttyS"),
            "Generic - 3 Button Mouse (serial)" :
                    ("Microsoft", "Microsoft", "ttyS"),
            "Generic - 2 Button Mouse (PS/2)" :
                    ("ps/2", "PS/2", "psaux"),
            "Generic - 3 Button Mouse (PS/2)" :
	            ("ps/2", "PS/2", "psaux"),
            "Genius - NetMouse (serial)" :
        	   ("ms3", "IntelliMouse", "ttyS"),
            "Genius - NetMouse (PS/2)" :
	            ("netmouse", "NetMousePS/2", "psaux"),
            "Genius - NetMouse Pro (PS/2)" :
	            ("netmouse", "NetMousePS/2", "psaux"),
            "Genius - NetScroll (PS/2)" :
	            ("netmouse", "NetScrollPS/2", "psaux"),
            "Kensington - Thinking Mouse (PS/2)" :
            	    ("ps/2", "ThinkingMousePS/2", "psaux"),
            "Logitech - C7 Mouse (serial, old C7 type)" :
            	    ("Logitech", "Logitech", "ttyS"),
            "Logitech - CC Series (serial)" :
	            ("logim", "MouseMan", "ttyS"),
            "Logitech - Bus Mouse" :
            	    ("Busmouse", "BusMouse", "logibm"),
            "Logitech - MouseMan/FirstMouse (serial)" :
            	    ("MouseMan", "MouseMan", "ttyS"),
            "Logitech - MouseMan/FirstMouse (ps/2)" :
            	    ("ps/2", "PS/2", "psaux"),
            "Logitech - MouseMan+/FirstMouse+ (serial)" :
	            ("pnp", "IntelliMouse", "ttyS"),
            "Logitech - MouseMan+/FirstMouse+ (PS/2)" :
	            ("ps/2", "MouseManPlusPS/2", "psaux"),
            "Microsoft - Compatible Mouse (serial)" :
            	    ("Microsoft",    "Microsoft", "ttyS"),
            "Microsoft - Rev 2.1A or higher (serial)" :
                    ("pnp", "Auto", "ttyS"),
            "Microsoft - IntelliMouse (serial)" :
                    ("ms3", "IntelliMouse", "ttyS"),
            "Microsoft - IntelliMouse (PS/2)" :
            	    ("imps2", "IMPS/2", "psaux"), 
            "Microsoft - Bus Mouse" :
	            ("Busmouse", "BusMouse", "inportbm"),
            "Mouse Systems - Mouse (serial)" :
            	    ("MouseSystems", "MouseSystems", "ttyS"), 
            "MM - Series (serial)" :
	            ("MMSeries", "MMSeries", "ttyS"),
            "MM - HitTablet (serial)" :
	            ("MMHitTab", "MMHittab", "ttyS"),
            }

    def available (self):
        return self.mice

    def get (self):
        if self.info.has_key ("FULLNAME"):
            return self.info ["FULLNAME"]
        else:
            return "Generic - 3 Button Mouse (PS/2)"

    def set (self, mouse):
        (gpm, x11, dev) = self.mice[mouse]
        self.info["MOUSETYPE"] = gpm
        self.info["XMOUSETYPE"] = x11
        self.info["FULLNAME"] = mouse

class Keyboard (SimpleConfigFile):
    # XXX fixme - externalize
    def __init__ (self):
        self.info = {}

    def available (self):
        return [
            "azerty",
            "be-latin1",
            "be2-latin1",
            "fr-latin0",
            "fr-latin1",
            "fr-pc",
            "fr",
            "wangbe",
            "ANSI-dvorak",
            "dvorak-l",
            "dvorak-r",
            "dvorak",
            "pc-dvorak-latin1",
            "tr_f-latin5",
            "trf",
            "bg",
            "cf",
            "cz-lat2-prog",
            "cz-lat2",
            "defkeymap",
            "defkeymap_V1.0",
            "dk-latin1",
            "dk",
            "emacs",
            "emacs2",
            "es",
            "fi-latin1",
            "fi",
            "gr-pc",
            "gr",
            "hebrew",
            "hu101",
            "is-latin1",
            "it-ibm",
            "it",
            "it2",
            "jp106",
            "la-latin1",
            "lt",
            "lt.l4",
            "nl",
            "no-latin1",
            "no",
            "pc110",
            "pl",
            "pt-latin1",
            "pt-old",
            "ro",
            "ru-cp1251",
            "ru-ms",
            "ru-yawerty",
            "ru",
            "ru1",
            "ru2",
            "ru_win",
            "se-latin1",
            "sk-prog-qwerty",
            "sk-prog",
            "sk-qwerty",
            "tr_q-latin5",
            "tralt",
            "trf",
            "trq",
            "ua",
            "uk",
            "us",
            "croat",
            "cz-us-qwertz",
            "de-latin1-nodeadkeys",
            "de-latin1",
            "de",
            "fr_CH-latin1",
            "fr_CH",
            "hu",
            "sg-latin1-lk450",
            "sg-latin1",
            "sg",
            "sk-prog-qwertz",
            "sk-qwertz",
            "slovene",
            ]

    def set (self, keytable):
        self.info["KEYTABLE"] = keytable

    def get (self):
        if self.info.has_key ("KEYTABLE"):
            return self.info["KEYTABLE"]
        else:
            return "us"

class Authentication:
    def __init__ (self):
        self.useShadow = 1
        self.useMD5 = 1
        self.useNIS = 0
        self.domain = ""
        self.useBroadcast = 1
        self.server = ""

class Drives:
    def available (self):
        return isys.hardDriveList ()

rpmFD = None
        
class ToDo:
    def __init__(self, intf, method, rootPath, setupFilesystems = 1,
		 installSystem = 1):
	self.intf = intf
	self.method = method
	self.mounts = {}
	self.hdList = None
	self.comps = None
	self.instPath = rootPath
	self.setupFilesystems = setupFilesystems
	self.installSystem = installSystem
        self.language = Language ()
        self.network = Network ()
        self.rootpassword = Password ()
        self.mouse = Mouse ()
        self.keyboard = Keyboard ()
        self.auth = Authentication ()
        self.ddruid = None;
        self.drives = Drives ()
        self.log = LogFile ()
        self.bootdisk = 0
        self.liloDevice = None
        self.upgrade = 0
	self.lilo = LiloConfiguration()
        
    def umountFilesystems(self):
	if (not self.setupFilesystems): return 

        keys = self.mounts.keys ()
	keys.sort()
	keys.reverse()
	for n in keys:
            (device, fsystem, format) = self.mounts[n]
            if fsystem != "swap":
                try:
                    isys.umount('/mnt/sysimage/' + n)
                except:
                    # XXX
                    pass

    def mountFilesystems(self):
	if (not self.setupFilesystems): return 

        keys = self.mounts.keys ()
	keys.sort()
        for mntpoint in keys:
            (device, filesystem, format) = self.mounts[mntpoint]
            isys.makeDevInode(device, '/tmp/' + device)
            try:
                os.mkdir (self.instPath + mntpoint)
            except:
                pass
	    isys.mount( '/tmp/' + device, self.instPath + mntpoint)
	    os.remove( '/tmp/' + device);

    def makeFilesystems(self):
	if (not self.setupFilesystems): return 
        
        keys = self.mounts.keys ()
	keys.sort()
	for mntpoint in keys:
	    (device, fsystem, format) = self.mounts[mntpoint]
	    if not format: continue
	    w = self.intf.waitWindow("Formatting", 
			"Formatting %s filesystem..." % (mntpoint,))
	    isys.makeDevInode(device, '/tmp/' + device)
            if fsystem == "ext2":
                iutil.execWithRedirect ("/usr/sbin/mke2fs",
                                        [ "mke2fs", '/tmp/' + device ],
                                        stdout = None, stderr = None,
                                        searchPath = 1)
            elif fsystem == "swap":
                rc = iutil.execWithRedirect ("/usr/sbin/mkswap",
                                             [ "mkswap", '/tmp/' + device ],
                                             stdout = None, stderr = None,
                                             searchPath = 1)
                if rc:
                    raise ToDoError, "error making swap on " + device
#                isys.swapon ('/tmp/' + device)
            else:
                pass

            os.remove('/tmp/' + device)
	    w.pop()

    def addMount(self, device, location, fsystem, reformat = 0):
        if fsystem == "swap":
            location = "swap"
            reformat = 1
        self.mounts[location] = (device, fsystem, reformat)

    def writeFstab(self):
	format = "%-23s %-23s %-7s %-15s %d %d\n";

	f = open (self.instPath + "/etc/fstab", "w")
        keys = self.mounts.keys ()
	keys.sort ()
	for mntpoint in keys: 
	    (dev, fs, reformat) = self.mounts[mntpoint]
	    if (mntpoint == '/'):
		f.write (format % ( '/dev/' + dev, mntpoint, fs, 'defaults', 1, 1))
	    else:
                if (fs == "ext2"):
                    f.write (format % ( '/dev/' + dev, mntpoint, fs, 'defaults', 1, 2))
                else:
                    f.write (format % ( '/dev/' + dev, mntpoint, fs, 'defaults', 0, 0))
	f.write (format % ("/mnt/floppy", "/dev/fd0", 'ext', 'noauto', 0, 0))
	f.write (format % ("none", "/proc", 'proc', 'defaults', 0, 0))
	f.write (format % ("none", "/dev/pts", 'devpts', 'gid=5,mode=620', 0, 0))
	f.close ()
        # touch mtab
        open (self.instPath + "/etc/mtab", "w+")
        f.close ()

    def readFstab (self, path):
        f = open (path, "r")
        lines = f.readlines ()
        f.close
        fstab = {}
        for line in lines:
            fields = string.split (line)
            if fields and fields[2] == "ext2" or fields[2] == "swap":
                fstab[fields[1]] = (fields[0][5:], fields[2], 0)
        return fstab

    def writeLanguage(self):
	f = open(self.instPath + "/etc/sysconfig/i18n", "w")
	f.write(str (self.language))
	f.close()

    def writeMouse(self):
	f = open(self.instPath + "/etc/sysconfig/mouse", "w")
	f.write(str (self.mouse))
	f.close()

    def writeKeyboard(self):
	f = open(self.instPath + "/etc/sysconfig/keyboard", "w")
	f.write(str (self.keyboard))
	f.close()

    def makeInitrd (self):
        if not self.__dict__.has_key ("madeinitrd"):
            initrd = "/boot/initrd-%s.img" % (self.kernelVersion,)
            
            iutil.execWithRedirect("/sbin/mkinitrd",
                                  [ "/sbin/mkinitrd",
                                    initrd,
                                    self.kernelVersion ],
                                  stdout = None, stderr = None, searchPath = 1,
                                  root = self.instPath)
            self.madeinitrd = 1

    def makeBootdisk (self):
        self.makeInitrd ()
        w = self.intf.waitWindow ("Creating", "Creating boot disk...")
        rc = iutil.execWithRedirect("/sbin/mkbootdisk",
                                    [ "/sbin/mkbootdisk",
                                      "--noprompt",
                                      "--device",
                                      "/dev/fd0",
                                      self.kernelVersion ],
                                    stdout = None, stderr = None, searchPath = 1,
                                    root = self.instPath)
        w.pop()
        if rc:
            raise ToDoError, "boot disk creation failed"

    def installLilo (self):
	if not self.liloDevice: return

        kernelVersion = "%s-%s" % (self.kernelPackage[rpm.RPMTAG_VERSION],
                                   self.kernelPackage[rpm.RPMTAG_RELEASE])
        initrd = "/boot/initrd-%s.img" % (kernelVersion,)
            
        self.makeInitrd ()

	self.lilo.addEntry("boot", '/dev/' + self.liloDevice)
	self.lilo.addEntry("map", "/boot/map")
	self.lilo.addEntry("install", "/boot/boot.b")
	self.lilo.addEntry("prompt")
	self.lilo.addEntry("timeout", "50")
	self.lilo.addEntry("default", "linux")        

	sl = LiloConfiguration()
	sl.addEntry("label", "linux")
        if os.access (self.instPath + initrd, os.R_OK):
            sl.addEntry("initrd", initrd)

        if not self.mounts.has_key ('/'):
            return
        (dev, type, size) = self.mounts['/']
        sl.addEntry("root", '/dev/' + dev)
	sl.addEntry("read-only")

	kernelFile = "/boot/vmlinuz-" + kernelVersion
	    
	self.lilo.addImageetyat("image", kernelFile, sl)
	self.lilo.write(self.instPath + "/etc/lilo.conf")

        for (type, name, config) in self.lilo.images:
            # remove entries for missing kernels (upgrade)
            if type == "image":
                if not os.access (self.instPath + name, os.R_OK):
                    self.lilo.delEntry (name)
            # remove entries for unbootable partitions
            if type == "other":
                device = name[5:]
                isys.makeDevInode(device, '/tmp/' + device)
                if not isys.checkBoot ('/tmp/' + device):
                    self.lilo.delEntry (name)
                os.remove ('/tmp/' + device)

	iutil.execWithRedirect(self.instPath + '/sbin/lilo' , [ "lilo", 
				"-r", self.instPath ], stdout = None)

    def freeHeaderList(self):
	if (self.hdList):
	    self.hdList = None

    def getHeaderList(self):
	if (not self.hdList):
	    w = self.intf.waitWindow("Reading",
                                     "Reading package information...")
	    self.hdList = self.method.readHeaders()
	    w.pop()
	return self.hdList

    def setLiloLocation(self, device):
	self.liloDevice = device

    def getLiloLocation (self):
        return self.liloDevice

    def getCompsList(self):
	if (not self.comps):
	    self.getHeaderList()
	    self.comps = self.method.readComps(self.hdList)
	    for comp in self.comps:
		if comp.selected:
		    comp.select (1)
	self.comps['Base'].select(1)
	self.kernelPackage = self.hdList['kernel']

	if (self.hdList.has_key('kernel-smp') and isys.smpAvailable()):
	    self.hdList['kernel-smp'].selected = 1
	    self.kernelPackage = self.hdList['kernel-smp']
            
        self.kernelVersion = "%s-%s" % (self.kernelPackage[rpm.RPMTAG_VERSION],
                                        self.kernelPackage[rpm.RPMTAG_RELEASE])

	return self.comps

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
                 "FORWARD_IPV4=false\n"
                 "HOSTNAME=localhost.localdomain\n"
                 "GATEWAY=" + self.network.gateway + "\n")
        f.close ()

        # /etc/hosts
        f = open (self.instPath + "/etc/hosts", "w")
        f.write ("127.0.0.1\t\tlocalhost.localdomain\n")
        for dev in self.network.netdevices.values ():
            ip = dev.get ("ipaddr")
            if dev.hostname and ip:
                f.write ("%s\t\t%s\n" % (ip, dev.hostname))
        f.close ()

        # /etc/resolv.conf
        f = open (self.instPath + "/etc/resolv.conf", "w")
        f.write ("search " + string.joinfields (self.network.domains, ' ') + "\n")
        for ns in self.network.nameservers ():
            if ns:
                f.write ("nameserver " + ns + "\n")
        f.close ()

    def writeRootPassword (self):
        f = open (self.instPath + "/etc/passwd", "r")
        lines = f.readlines ()
        f.close ()
        index = 0
        for line in lines:
            if line[0:4] == "root":
                entry = string.splitfields (line, ':')
                entry[1] = self.rootpassword.get ()
                lines[index] = string.joinfields (entry, ':')
                break
            index = index + 1
        f = open (self.instPath + "/etc/passwd", "w")
        f.writelines (lines)
        f.close ()

    def setupAuthentication (self):
        args = [ "/usr/sbin/authconfig", "--kickstart", "--nostart" ]
        if self.auth.useShadow:
            args.append ("--useshadow")
        if self.auth.useMD5:
            args.append ("--enablemd5")
        if self.auth.useNIS:
            args.append ("--enablenis")
            args.append ("--nisdomain")
            args.append (self.auth.domain)
            if not self.auth.useBroadcast:
                args.append ("--nisserver")
                args.append (self.auth.server)
        iutil.execWithRedirect(args[0], args,
                              stdout = None, stderr = None, searchPath = 1,
                              root = self.instPath)

    def copyConfModules (self):
        try:
            inf = open ("/tmp/conf.modules", "r")
        except:
            pass
        else:
            out = open (self.instPath + "/etc/conf.modules", "w")
            out.write (inf.read ())

    def verifyDeps (self):
	ts = rpm.TransactionSet()
        self.comps['Base'].select (1)

	for p in self.hdList.packages.values ():
            if p.selected:
                ts.add(p.h, (p.h, p.h[rpm.RPMTAG_NAME]))
            else:
                ts.add(p.h, (p.h, p.h[rpm.RPMTAG_NAME]), "a")

	ts.order()
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
            return rc
        else:
            return None

    def selectDeps (self, deps):
        for (who, dep) in deps:
            if dep != _("no suggestion"):
                self.hdList[dep].selected = 1

    def upgradeFindRoot (self):
        win = self.intf.waitWindow ("Examining System",
                                    "Searching for Red Hat Linux installations...")
        rootparts = []
        drives = self.drives.available ().keys ()
        for drive in drives:
            isys.makeDevInode(drive, '/tmp/' + drive)
            table = _balkan.readTable ('/tmp/' + drive)
            for i in range (len (table)):
                (type, sector, size) = table[i]
                # 2 is ext2 in balkan speek
                if size and type == 2:
                    dev = drive + str (i + 1)
                    isys.makeDevInode(dev, '/tmp/' + dev)                    
                    isys.mount('/tmp/' + dev, '/mnt/sysimage')
                    if os.access ('/mnt/sysimage/etc/fstab', os.R_OK):
                        rootparts.append (dev)
                    isys.umount('/mnt/sysimage')
                    os.remove ('/tmp/' + dev)
            os.remove ('/tmp/' + drive)
        win.pop ()
        return rootparts

    def upgradeFindPackages (self, root):
        win = self.intf.waitWindow ("Examining System",
                                    "Finding packages to upgrade...")
	self.getHeaderList()
        isys.makeDevInode(root, '/tmp/' + root)
        isys.mount('/tmp/' + root, '/mnt/sysimage')
        self.mounts = self.readFstab ('/mnt/sysimage/etc/fstab')
        isys.umount('/mnt/sysimage')        
        self.mountFilesystems ()
        packages = rpm.findUpgradeSet (self.hdList.hdlist, '/mnt/sysimage')
        self.umountFilesystems ()
        for package in packages:
            self.hdList[package[rpm.RPMTAG_NAME]].selected = 1
        win.pop ()
        
    def doInstall(self):
	# make sure we have the header list and comps file
	self.getHeaderList()
	self.getCompsList()

        # make sure that all comps that include other comps are
        # selected (i.e. - recurse down the selected comps and turn
        # on the children
        if self.setupFilesystems:
            if not self.upgrade:
                self.ddruid.save ()
                self.makeFilesystems ()
            self.mountFilesystems ()

        self.method.targetFstab (self.mounts)

	if not self.installSystem: 
	    return

	for i in [ '/var', '/var/lib', '/var/lib/rpm', '/tmp', '/dev' ]:
	    try:
	        os.mkdir(self.instPath + i)
	    except os.error, (errno, msg):
                self.intf.messageWindow("Error", "Error making directory %s: %s" % (i, msg))

	db = rpm.opendb(1, self.instPath)
	ts = rpm.TransactionSet(self.instPath, db)

        total = 0
	totalSize = 0

        if self.upgrade:
            how = "u"
        else:
            how = "i"
        
	for p in self.hdList.selected():
	    ts.add(p.h, (p.h, self), how)
	    total = total + 1
	    totalSize = totalSize + p.h[rpm.RPMTAG_SIZE]

	ts.order()

	self.instLog = open(self.instPath + '/tmp/install.log', "w+")
	syslog = Syslogd(root = self.instPath, output = self.instLog)

	instLogFd = os.open(self.instPath + '/tmp/install.log', os.O_APPEND)
	ts.scriptFd = instLogFd
	# the transaction set dup()s the file descriptor and will close the
	# dup'd when we go out of scope
	os.close(instLogFd)	

	p = self.intf.packageProgressWindow(total, totalSize)

        if self.upgrade:
            self.modeText = _("Upgrading %s.\n")
        else:
            self.modeText = _("Installing %s.\n")

        def instCallback(what, amount, total, key, intf):
            if (what == rpm.RPMCALLBACK_INST_OPEN_FILE):
                (h, self) = key
                intf.setPackage(h)
                intf.setPackageScale(0, 1)
                self.instLog.write (self.modeText % (h[rpm.RPMTAG_NAME],))
                self.instLog.flush ()
                fn = self.method.getFilename(h)
                self.rpmFD = os.open(fn, os.O_RDONLY)
                return self.rpmFD
            elif (what == rpm.RPMCALLBACK_INST_PROGRESS):
                intf.setPackageScale(amount, total)
            elif (what == rpm.RPMCALLBACK_INST_CLOSE_FILE):
                (h, self) = key
                os.close (self.rpmFD)
                intf.completePackage(h)
            else:
                pass

        # XXX FIXME FIXME: -1 IGNORES all problems
        ts.run(0, -1, instCallback, p)

        self.method.filesDone ()
        
	del syslog
        del p

        w = self.intf.waitWindow("Post Install", 
                                 "Performing post install configuration...")

        if not self.upgrade:
            self.writeFstab ()
            self.writeLanguage ()
            self.writeMouse ()
            self.writeKeyboard ()
            self.writeNetworkConfig ()
            self.writeRootPassword ()
            self.setupAuthentication ()
            self.copyConfModules ()
	self.installLilo ()
        
        w.pop ()

