#
# kickstart.py: kickstart install support
#
# Copyright 1999-2007 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil
import isys
import os
from installclass import BaseInstallClass
from partitioning import *
from autopart import *
from fsset import *
from flags import flags
from constants import *
import sys
import raid
import string
import partRequests
import urllib2
import lvm

from rhpl.translate import _
from rhpl.log import log

KS_MISSING_PROMPT = 0
KS_MISSING_IGNORE = 1

class KickstartError(Exception):
    def __init__(self, val = ""):
        self.value = val

    def __str__ (self):
        return self.value

class KickstartValueError(KickstartError):
    def __init__(self, val = ""):
        self.value = val

    def __str__ (self):
        return self.value

class KSAppendException(KickstartError):
    def __init__(self, s=""):
	self.str = s

    def __str__(self):
	return self.str

class Script:
    def __repr__(self):
	str = ("(s: '%s' i: %s c: %d)") %  \
	    (self.script, self.interp, self.inChroot)
	return string.replace(str, "\n", "|")

    def __init__(self, script, interp, inChroot, logfile = None):
	self.script = script
	self.interp = interp
	self.inChroot = inChroot
        self.logfile = logfile

    def run(self, chroot, serial):
	scriptRoot = "/"
	if self.inChroot:
	    scriptRoot = chroot

	path = scriptRoot + "/tmp/ks-script"

	f = open(path, "w")
	f.write(self.script)
	f.close()
	os.chmod(path, 0700)

        if self.logfile is not None:
            messages = self.logfile
	elif serial:
	    messages = "/tmp/ks-script.log"
	else:
	    messages = "/dev/tty3"

	rc = iutil.execWithRedirect(self.interp,
				    [self.interp,"/tmp/ks-script"],
				    stdin = messages, stdout = messages,
                                    stderr = messages, root = scriptRoot)

	if rc != 0:
	    log("WARNING - Error code %s encountered running a kickstart %%pre/%%post script", rc)

	os.unlink(path)

class KickstartBase(BaseInstallClass):
    name = "kickstart"
    
    def postAction(self, rootPath, serial):
	log("Running kickstart %%post script(s)")
	for script in self.postScripts:
	    script.run(rootPath, serial)
	log("All kickstart %%post script(s) have been run")

    def doRootPw(self, id, args):
	(args, extra) = isys.getopt(args, '', [ 'iscrypted' ])

	isCrypted = 0
	for n in args:
	    (str, arg) = n
	    if (str == '--iscrypted'):
		isCrypted = 1
                
	if len(extra) != 1:
	    raise KickstartValueError, "a single argument is expected to rootPw"

	self.setRootPassword(id, extra[0], isCrypted = isCrypted)
	self.skipSteps.append("accounts")
	
    def doFirewall(self, id, args):
	(args, extra) = isys.getopt(args, '',
		[ 'dhcp', 'ssh', 'telnet', 'smtp', 'http', 'ftp', 'enabled',
                  'enable', 'port=', 'high', 'medium', 'disabled', 'disable',
                  'trust=' ])
		  
	enable = -1
	trusts = []
	ports = []
	
	for n in args:
	    (str, arg) = n
	    if str == '--ssh':
                ports.append("22:tcp")
	    elif str == '--telnet':
                ports.append("23:tcp")
	    elif str == '--smtp':
                ports.append("25:tcp")
	    elif str == '--http':
                ports.extend(["80:tcp", "443:tcp"])
	    elif str == '--ftp':
                ports.append("21:tcp")
	    elif str == '--high' or str == '--medium':
                log("used deprecated firewall option: %s" %(str[2:],))
		enable = 1
	    elif str == '--enabled' or str == "--enable":
		enable = 1
	    elif str == '--disabled' or str == "--disable":
		enable = 0
	    elif str == '--trust':
		trusts.append(arg)
	    elif str == '--port':
                theports = arg.split(",")
                for p in theports:
                    p = p.strip()
                    if p.find(":") == -1:
                        p = "%s:tcp" %(p,)
                    ports.append(p)
	    
	self.setFirewall(id, enable, trusts, ports)

    def doSELinux(self, id, args):
	(args, extra) = isys.getopt(args, '',
                                    [ 'disabled', 'enforcing',
                                      'permissive' ] )

        sel = 2

        for n in args:
            (str, arg) = n
            if str == "--disabled":
                sel = 0
            elif str == "--permissive":
                sel = 1
            elif str == "--enforcing":
                sel = 2

        self.setSELinux(id, sel)

    def doZFCP(self, id, args):
        (args, extra) = isys.getopt(args, '',
                                    ["devnum=", "scsiid=", "wwpn=", "scsilun=",
                                     "fcplun="])

        devnum = None
        scsiid = None
        wwpn = None
        scsilun = None
        fcplun = None

        for n in args:
            (str, arg) = n
            if str == "--devnum":
                devnum = id.zfcp.sanitizeDeviceInput(arg)
            elif str == "--scsiid":
                scsiid = id.zfcp.sanitizeHexInput(arg)
            elif str == "--wwpn":
                wwpn = id.zfcp.sanitizeHexInput(arg)
            elif str == "--scsilun":
                scsilun = id.zfcp.sanitizeHexInput(arg)
            elif str == "--fcplun":
                fcplun = id.zfcp.sanitizeFCPLInput(arg)

        if id.zfcp.checkValidDevice(devnum) == -1:
            raise KickstartValueError, "Invalid devnum specified"
        if id.zfcp.checkValidID(scsiid) == -1:
            raise KickstartValueError, "Invalid scsiid specified"
        if id.zfcp.checkValid64BitHex(wwpn) == -1:
            raise KickstartValueError, "Invalid wwpn specified"
        if id.zfcp.checkValidID(scsilun) == -1:
            raise KickstartValueError, "Invalid scsilun specified"
        if id.zfcp.checkValid64BitHex(fcplun) == -1:
            raise KickstartValueError, "Invalid fcplun specified"

        if ((devnum is None) or (scsiid is None) or (wwpn is None)
            or (scsilun is None) or (fcplun is None)):
            raise KickstartError, "ZFCP config must specify all of devnum, scsiid, wwpn, scsilun, and fcplun"

        self.setZFCP(id, devnum, scsiid, wwpn, scsilun, fcplun)
        id.zfcp.updateConfig(id.zfcp.fcpdevices, id.diskset, None)
        self.skipSteps.append("zfcpconfig")
                
    def doAuthconfig(self, id, args):
	(args, extra) = isys.getopt(args, '',
                [ 'useshadow', 'enableshadow',
		  'enablemd5', 'passalgo=',
                  'enablenis', 'nisdomain=', 'nisserver=',
                  'enableldap', 'enableldapauth', 'ldapserver=', 'ldapbasedn=',
                  'enableldaptls', 
                  'enablekrb5', 'krb5realm=', 'krb5kdc=', 'krb5adminserver=',
                  'enablehesiod', 'hesiodlhs=', 'hesiodrhs=',
                  'enablesmbauth', 'smbservers=', 'smbworkgroup=',
                  'enablecache'])

	useShadow = 0

	salt = None

	useNis = 0
	nisServer = ""
	nisDomain = ""
	nisBroadcast = 0

        useLdap = 0
        useLdapauth = 0
        useLdaptls = 0
        ldapServer = ""
        ldapBasedn = ""

        useKrb5 = 0
        krb5Realm = ""
        krb5Kdc = ""
        krb5Admin = ""

        useHesiod = 0
        hesiodLhs = ""
        hesiodRhs = ""

        useSamba = 0
        smbServers = ""
        smbWorkgroup = ""

        enableCache = 0
	
	for n in args:
	    (str, arg) = n
	    if (str == '--enablenis'):
		useNis = 1
	    elif (str == '--useshadow') or (str == '--enableshadow'):
		useShadow = 1
	    elif (str == '--enablemd5'):
                salt = 'md5'
            elif (str == '--passalgo') and (arg in ('md5', 'sha256', 'sha512')):
                salt = arg
	    elif (str == '--nisserver'):
		nisServer = arg
	    elif (str == '--nisdomain'):
		nisDomain = arg
            elif (str == '--enableldap'):
                useLdap = 1
            elif (str == '--enableldapauth'):
                useLdapauth = 1
            elif (str == '--ldapserver'):
                ldapServer = arg
            elif (str == '--ldapbasedn'):
                ldapBasedn = arg
            elif (str == '--enableldaptls'):
                useLdaptls = 1
            elif (str == '--enablekrb5'):
                useKrb5 = 1
            elif (str == '--krb5realm'):
                krb5Realm = arg
            elif (str == '--krb5kdc'):
                krb5Kdc = arg
            elif (str == '--krb5adminserver'):
                krb5Admin = arg
            elif (str == '--enablehesiod'):
                useHesiod = 1
            elif (str == '--hesiodlhs'):
                hesiodLhs = arg
            elif (str == '--hesiodrhs'):
                hesiodRhs = arg
            elif (str == '--enablesmbauth'):
                useSamba = 1
            elif (str == '--smbservers'):
                smbServers = arg
            elif (str == '--smbworkgroup'):
                smbWorkgroup = arg
            elif (str == '--enablecache'):
                enableCache = 1
                

	if useNis and not nisServer: nisBroadcast = 1
	    
	self.setAuthentication(id, useShadow, salt,
                               useNis, nisDomain, nisBroadcast, nisServer,
                               useLdap, useLdapauth, ldapServer,
                               ldapBasedn, useLdaptls,
                               useKrb5, krb5Realm, krb5Kdc, krb5Admin,
                               useHesiod, hesiodLhs, hesiodRhs,
                               useSamba, smbServers, smbWorkgroup,
                               enableCache)
        
	self.skipSteps.append("authentication")

    def doBootloader (self, id, args, useLilo = 0):
        (args, extra) = isys.getopt(args, '',
                [ 'append=', 'location=', 'useLilo', 'lba32',
                  'password=', 'md5pass=', 'linear', 'nolinear',
                  'upgrade', 'driveorder='])

        validLocations = [ "mbr", "partition", "none", "boot" ]
        appendLine = ""
        location = "mbr"
        password = None
        md5pass = None
        forceLBA = 0
        linear = 1
        upgrade = 0
        driveorder = []

        for n in args:
            (str, arg) = n
            if str == '--append':
                appendLine = arg
            elif str == '--location':
                location = arg
            elif str == '--useLilo':
#                log("used deprecated option --useLilo, ignoring")
                useLilo = 1
	    elif str == '--linear':
		linear = 1
	    elif str == '--nolinear':
		linear = 0
            elif str == '--lba32':
                forceLBA = 1
            elif str == '--password':
                password = arg
            elif str == '--md5pass':
                md5pass = arg
            elif str == '--upgrade':
                upgrade = 1
            elif str == '--driveorder':
                driveorder = string.split(arg, ',')

        if location not in validLocations:
            raise KickstartValueError, "mbr, partition, or none expected for bootloader command"
        if location == "none":
            location = None
        elif location == "partition":
            location = "boot"

        if upgrade and not id.upgrade.get():
            raise KickstartError, "Selected upgrade mode for bootloader but not doing an upgrade"

        if upgrade:
            id.bootloader.kickstart = 1
            id.bootloader.doUpgradeOnly = 1

        if location is None:
            self.skipSteps.append("bootloadersetup")
            self.skipSteps.append("instbootloader")
        else:
            self.showSteps.append("bootloadersetup")
            self.setBootloader(id, useLilo, location, linear, forceLBA,
                           password, md5pass, appendLine, driveorder)

        self.skipSteps.append("upgbootloader")
        self.skipSteps.append("bootloader")
        self.skipSteps.append("bootloaderadvanced")

    def doLilo	(self, id, args):
        self.doBootloader(id, args, useLilo = 1)

    def doFirstboot(self, id, args):
        (args, extra) = isys.getopt(args, '',
                                    ['reconfig', 'enable', 'enabled',
                                     'disable', 'disabled'])

        fb = FIRSTBOOT_SKIP

	for n in args:
	    (str, arg) = n
	    if str == '--reconfig':
                fb = FIRSTBOOT_RECONFIG
            elif str == '--enable' or str == "--enabled":
                fb = FIRSTBOOT_DEFAULT
            elif str == '--disable' or str == "--disabled":
                fb = FIRSTBOOT_SKIP

        id.firstboot = fb
        
        
    def doLiloCheck (self, id, args):
        drives = isys.hardDriveDict ().keys()
	drives.sort(isys.compareDrives)
	device = drives[0]
	isys.makeDevInode(device, '/tmp/' + device)
	fd = os.open('/tmp/' + device, os.O_RDONLY)
	os.unlink('/tmp/' + device)
	block = os.read(fd, 512)
	os.close(fd)
	if block[6:10] == "LILO":
	    sys.exit(0)

    def doTimezone(self, id, args):
	(args, extra) = isys.getopt(args, '',
		[ 'utc' ])

	isUtc = 0
	
	for n in args:
	    (str, arg) = n
	    if str == '--utc':
		isUtc = 1

	self.setTimezoneInfo(id, extra[0], asUtc = isUtc)

	self.skipSteps.append("timezone")


    def doXconfig(self, id, args):
	(args, extra) = isys.getopt(args, '',
		[ 'server=', 'card=', 'videoram=',
                  'monitor=', 'hsync=', 'vsync=',
                  'resolution=', 'depth=', 
		  'startxonboot', 'noprobe', 'defaultdesktop=' ])

	if extra:
	    raise KickstartValueError, "unexpected arguments to xconfig command"

	server = None
	card = None
        videoRam = None
	monitor = None
	hsync = None
	vsync = None
        resolution = None
        depth = None
        noProbe = 0
	startX = 0
        defaultdesktop = ""

	for n in args:
	    (str, arg) = n
	    if (str == "--noprobe"):
		noProbe = 1
	    elif (str == "--server"):
		server = arg
	    elif (str == "--card"):
		card = arg
            elif (str == "--videoram"):
                videoRam = arg
	    elif (str == "--monitor"):
		monitor = arg
	    elif (str == "--hsync"):
		hsync = arg
	    elif (str == "--vsync"):
		vsync = arg
            elif (str == "--resolution"):
                resolution = arg
            elif (str == "--depth"):
                depth = string.atoi(arg)
	    elif (str == "--startxonboot"):
		startX = 1
            elif (str == "--defaultdesktop"):
                defaultdesktop = arg

	self.configureX(id, server, card, videoRam, monitor, hsync, vsync,
                        resolution, depth, noProbe, startX)
        self.setDesktop(id, defaultdesktop)

        self.skipSteps.append("videocard")
        self.skipSteps.append("monitor")
        self.skipSteps.append("xcustom")
        self.skipSteps.append("handleX11pkgs")
        self.skipSteps.append("checkmonitorok")
        self.skipSteps.append("setsanex")

    def doMonitor(self, id, args):
	(args, extra) = isys.getopt(args, '',
                                    [ 'monitor=', 'hsync=', 'vsync=' ])

	if extra:
	    raise KickstartValueError, "unexpected arguments to monitor command"

	monitor = None
	hsync = None
	vsync = None

	for n in args:
	    (str, arg) = n
	    if (str == "--monitor"):
		monitor = arg
	    elif (str == "--hsync"):
		hsync = arg
	    elif (str == "--vsync"):
		vsync = arg

        self.skipSteps.append("monitor")
        self.skipSteps.append("checkmonitorok")

        self.setMonitor(id, hsync = hsync, vsync = vsync,
                        monitorName = monitor)

    def doUpgrade(self, id, args):
	self.installType = "upgrade"
        id.upgrade.set(1)

    def doNetwork(self, id, args):
	# nodns is only used by the loader
	(args, extra) = isys.getopt(args, '',
		[ 'bootproto=', 'ip=', 'netmask=', 'gateway=', 'nameserver=',
		  'nodns', 'device=', 'hostname=', 'ethtool=', 'onboot=',
		  'dhcpclass=', 'essid=', 'wepkey=', 'notksdevice'])
	bootProto = "dhcp"
	ip = None
	netmask = ""
	gateway = ""
	nameserver = ""
	hostname = ""
        ethtool = ""
        essid = ""
        wepkey = ""
	onboot = 1
        device = None
        dhcpclass = None
	for n in args:
	    (str, arg) = n
	    if str == "--bootproto":
		bootProto = arg
	    elif str == "--ip":
		ip = arg
	    elif str == "--netmask":
		netmask = arg
	    elif str == "--gateway":
		gateway = arg
	    elif str == "--nameserver":
		nameserver = arg
	    elif str == "--device":
		device = arg
	    elif str == "--hostname":
		hostname = arg
            elif str== "--ethtool":
                ethtool = arg
            elif str == "--essid":
                essid = arg
            elif str == "--wepkey":
                wepkey = arg
            elif str== "--onboot":
		if arg == 'no':
		    onboot = 0
		else:
		    onboot = 1
	    elif str == "--class":
		dhcpclass = arg

	self.setNetwork(id, bootProto, ip, netmask, ethtool, device=device, onboot=onboot, dhcpclass=dhcpclass, essid=essid, wepkey=wepkey)
	if hostname != "":
	    self.setHostname(id, hostname, override = 1)
        if nameserver != "":
            self.setNameserver(id, nameserver)
        if gateway != "":
            self.setGateway(id, gateway)

    def doLang(self, id, args):
        self.setLanguage(id, args[0])
	self.skipSteps.append("language")

    def doLangSupport (self, id, args):
        (args, extra) = isys.getopt(args, '', [ 'default=' ])
	deflang = "en_US.UTF-8"
        if args:
	    deflang = args[0][1]
	else:
	    # if they specified no default we default to en_US if
	    # they installed support for more than one lang, otherwise
	    # we default to the one language they specified support for
	    if extra is None:
		deflang = "en_US.UTF-8"
	    elif len(extra) >= 1:
		deflang = extra[0]
	    else:
		deflang = "en_US.UTF-8"
		
	self.setLanguageDefault (id, deflang)
        self.setLanguageSupport(id, extra)

        self.skipSteps.append("languagesupport")

    def doKeyboard(self, id, args):
        self.setKeyboard(id, args[0])
        id.keyboard.beenset = 1
	self.skipSteps.append("keyboard")

    def doZeroMbr(self, id, args):
        self.setZeroMbr(id, 1)

    def doMouse(self, id, args):
        #Don't do anything with mice anymore
        return

## 	(args, extra) = isys.getopt(args, '', [ 'device=', 'emulthree' ])
##         mouseType = "none"
## 	device = None
## 	emulThree = 0

## 	for n in args:
## 	    (str, arg) = n
## 	    if str == "--device":
## 		device = arg
## 	    elif str == "--emulthree":
## 		emulThree = 1

## 	if extra:
## 	    mouseType = extra[0]

##  	if mouseType != "none":
##             self.setMouse(id, mouseType, device, emulThree)

##         self.skipSteps.append("mouse")

    def doReboot(self, id, args):
        self.skipSteps.append("complete")

    def doSkipX(self, id, args):
        self.skipSteps.append("checkmonitorok")
        self.skipSteps.append("setsanex")
        self.skipSteps.append("videocard")
        self.skipSteps.append("monitor")
        self.skipSteps.append("xcustom")
        self.skipSteps.append("handleX11pkgs")
        self.skipSteps.append("writexconfig")
        if id.xsetup is not None:
            id.xsetup.skipx = 1

    def doInteractive(self, id, args):
        self.interactive = 1

    def doAutoStep(self, id, args):
        flags.autostep = 1
	flags.autoscreenshot = 0

	(xargs, xtra) = isys.getopt(args, '', ['autoscreenshot'])
	for n in xargs:
	    (str, arg) = n
	    if str == "--autoscreenshot":
		flags.autoscreenshot = 1

		
    # read the kickstart config...  if parsePre is set, only parse
    # the %pre, otherwise ignore the %pre.  assume we're starting in where
    def readKickstart(self, id, file, parsePre = 0, where = "commands"):
	handlers = { 
		     "auth"		: self.doAuthconfig	,
		     "authconfig"	: self.doAuthconfig	,
                     "autopart"         : self.doAutoPart       ,
		     "cdrom"		: None			,
		     "clearpart"	: self.doClearPart	,
		     "ignoredisk"	: self.doIgnoreDisk	,
		     "device"		: None			,
		     "deviceprobe"	: None			,
		     "driverdisk"	: None			,
		     "firewall"		: self.doFirewall	,
                     "selinux"          : self.doSELinux        ,
		     "harddrive"	: None			,
		     "install"		: None          	,
		     "keyboard"		: self.doKeyboard	,
		     "lang"		: self.doLang		,
                     "langsupport"	: self.doLangSupport	,
		     "lilo"		: self.doLilo		,
                     "bootloader"       : self.doBootloader     ,
		     "lilocheck"	: self.doLiloCheck	,
		     "mouse"		: self.doMouse		,
		     "network"		: self.doNetwork	,
		     "nfs"		: None			,
		     "part"		: self.definePartition	,
		     "partition"	: self.definePartition	,
		     "raid"		: self.defineRaid	,
                     "volgroup"         : self.defineVolumeGroup,
                     "logvol"           : self.defineLogicalVolume,
		     "reboot"		: self.doReboot		,
		     "poweroff"	        : self.doReboot		,
		     "halt"             : self.doReboot		,
                     "shutdown"         : self.doReboot		,
		     "rootpw"		: self.doRootPw		,
		     "skipx"		: self.doSkipX		,
		     "text"		: None			,
		     "graphical"	: None			,
                     "cmdline"          : None                  ,
		     "timezone"		: self.doTimezone	,
		     "url"		: None			,
		     "upgrade"		: self.doUpgrade	,
		     "xconfig"		: self.doXconfig	,
                     "monitor"		: self.doMonitor	,
		     "xdisplay"		: None			,
		     "zerombr"		: self.doZeroMbr	,
                     "interactive"      : self.doInteractive    ,
                     "autostep"         : self.doAutoStep       ,
                     "firstboot"        : self.doFirstboot      ,
                     "zfcp"             : self.doZFCP           ,
                     "vnc"              : None                  ,
		   }

	packages = []
	groups = []
        excludedPackages = []
        
        script = ""
        scriptInterp = "/bin/sh"
        scriptLog = None
        if where == "pre" or where == "traceback":
            scriptChroot = 0
        else:
            scriptChroot = 1
        
	for n in open(file).readlines():
	    args = isys.parseArgv(n)

	    # don't eliminate white space or comments from scripts
	    if where not in ["pre", "post", "traceback"]:
		if not args or args[0][0] == '#': continue

	    if args and (args[0] in ["%pre", "%post", "%traceback"]):
		if ((where =="pre" and parsePre) or
		    (where in ["post", "traceback"] and not parsePre)):
		    s = Script(script, scriptInterp, scriptChroot, scriptLog)
		    if where == "pre":
                        self.preScripts.append(s)
		    elif where == "post":
			self.postScripts.append(s)
		    else:
			self.tracebackScripts.append(s)

		where = args[0][1:]
		args = isys.parseArgv(n)

                script = ""
                scriptInterp = "/bin/sh"
                scriptLog = None
                if where == "pre" or where == "traceback":
                    scriptChroot = 0
                else:
                    scriptChroot = 1

		argList = [ 'interpreter=', "log=", "logfile=" ]
		if where == "post":
		    argList.append('nochroot')

		(args, extra) = isys.getopt(args, '', argList)
		for n in args:
		    (str, arg) = n
		    
		    if str == "--nochroot":
			scriptChroot = 0
		    elif str == "--interpreter":
			scriptInterp = arg
                    elif str == "--log" or str == "--logfile":
                        scriptLog = arg

            elif args and args[0] == "%include" and not parsePre:
                if len(args) < 2:
                    raise KickstartError, "Invalid %include line"
                else:
                    # read in the included file and set our where appropriately
                    where = self.readKickstart(id, args[1], where = where)
            elif args and args[0] == "%packages":
		if ((where =="pre" and parsePre) or
		    (where in ["post", "traceback"] and not parsePre)):
		    s = Script(script, scriptInterp, scriptChroot, scriptLog)
		    if where == "pre":
                        self.preScripts.append(s)
		    elif where == "post":
			self.postScripts.append(s)
		    else:
			self.tracebackScripts.append(s)

                # if we're parsing the %pre, we don't need to continue
                if parsePre:
                    continue

                if len(args) > 1:
                    for arg in args[1:]:
                        if arg == "--resolvedeps":
                            id.handleDeps = RESOLVE_DEPS
                        elif arg == "--ignoredeps":
                            id.handleDeps = IGNORE_DEPS
                        elif arg == "--excludedocs":
                            id.excludeDocs = 1
                        elif arg == "--ignoremissing":
                            self.handleMissing = KS_MISSING_IGNORE
                        elif arg == "--nobase":
                            self.addBase = 0
                
		where = "packages"
                self.skipSteps.append("package-selection")
	    else:
                # if we're parsing the %pre and not in the pre, continue
                if parsePre and where != "pre":
                    continue
		elif where == "packages":
                    #Scan for comments in package list...drop off
                    #everything after "#" mark
                    try:
                        ind = string.index(n, "#")
                        n = n[:ind]
                    except:
                        #No "#" found in line
                        pass
                    
		    if n[0] == '@':
			n = n[1:]
                        n = string.strip (n)
			groups.append(n)
                    elif n[0] == '-':
                        n = n[1:]
                        n = string.strip(n)
                        excludedPackages.append(n)
		    else:
                        n = string.strip (n)
			packages.append(n)
		elif where == "commands":
                    if handlers.has_key(args[0]):
                        if handlers[args[0]] is not None:
                            handlers[args[0]](id, args[1:])
                    else:
			# unrecognized command
			raise KickstartError, "Unrecognized ks command: %s\nOn the line: %s" % (args[0], n)
		elif where in ["pre", "post", "traceback"]:
		    script = script + n
		else:
		    raise KickstartError, "I'm lost in kickstart"

        self.groupList.extend(groups)
        self.packageList.extend(packages)
        self.excludedList.extend(excludedPackages)

        # test to see if they specified to clear partitions and also
        # tried to --onpart on a logical partition
	#
	# XXX
	#
        #if iutil.getArch() == 'i386' and self.fstab:
            #clear = self.getClearParts()
            #if clear == FSEDIT_CLEAR_LINUX or clear == FSEDIT_CLEAR_ALL:
		#for (mntpoint, (dev, fstype, reformat)) in self.fstab:
		    #if int(dev[-1:]) > 4:
			#raise RuntimeError, "Clearpart and --onpart on non-primary partition %s not allowed" % dev
                
	if ((where =="pre" and parsePre) or
	    (where in ["post", "traceback"] and not parsePre)):
	    s = Script(script, scriptInterp, scriptChroot, scriptLog)
	    if where == "pre":
		self.preScripts.append(s)
	    elif where == "post":
		self.postScripts.append(s)
	    else:
		self.tracebackScripts.append(s)

        return where

    def doClearPart(self, id, args):
        type = CLEARPART_TYPE_NONE
        drives = None
        initAll = 0

        (args, extra) = isys.getopt(args, '', [ 'linux', 'all', 'drives=',
                                                'initlabel', 'none'])

        for n in args:
            (str, arg) = n
            if str == '--linux':
                type = CLEARPART_TYPE_LINUX
            elif str == '--all':
                type = CLEARPART_TYPE_ALL
            elif str == '--drives':
                drives = string.split(arg, ',')
            elif str == '--initlabel':
                initAll = 1
            elif str == '--none':
                type = CLEARPART_TYPE_NONE
            
        self.setClearParts(id, type, drives, initAll = initAll)

    # this adds a partition to the autopartition list replacing anything
    # else with this mountpoint so that you can use autopart and override /
    def addPartRequest(self, partitions, request):
        if not request.mountpoint:
            partitions.autoPartitionRequests.append(request)
            return

        for req in partitions.autoPartitionRequests:
            if req.mountpoint and req.mountpoint == request.mountpoint:
                partitions.autoPartitionRequests.remove(req)
                break
        partitions.autoPartitionRequests.append(request)            

    def doAutoPart(self, id, args):
        # sets up default autopartitioning.  use clearpart separately
        # if you want it
        self.setDefaultPartitioning(id, doClear = 0)

        id.partitions.isKickstart = 1

        self.skipSteps.append("partition")
        self.skipSteps.append("partitionmethod")
        self.skipSteps.append("partitionmethodsetup")
        self.skipSteps.append("fdisk")
        self.skipSteps.append("autopartition")
        self.skipSteps.append("zfcpconfig")

    def defineLogicalVolume(self, id, args):
        (args, extra) = isys.getopt(args, '', [ 'vgname=',
                                                'size=',
                                                'name=',
                                                'fstype=',
                                                'percent=',
						'maxsize=',
						'grow',
                                                'recommended',
                                                'noformat',
                                                'useexisting'])

        mountpoint = None
        vgname = None
        size = None
        name = None
        fstype = None
        percent = None
	grow = 0
	maxSizeMB = 0
        format = 1
        recommended = None
        preexist = 0

        for n in args:
            (str, arg) = n
            if str == '--vgname':
                vgname = arg
            elif str == '--size':
                size = int(arg)
            elif str == '--name':
                name = arg
            elif str == '--fstype':
                fstype = arg
            elif str == '--percent':
                percent = int(arg)
	    elif str == '--maxsize':
		maxSizeMB = int(arg)
	    elif str == '--grow':
		grow = 1
            elif str == '--recommended':
                recommended = 1
            elif str == "--noformat":
                format = 0
                preexist = 1
            elif str == "--useexisting":
                preexist = 1

        if extra[0] == 'swap':
            filesystem = fileSystemTypeGet('swap')
            mountpoint = None
            if recommended:
                (size, maxSizeMB) = iutil.swapSuggestion()
                grow = 1
        else:
            if fstype:
                filesystem = fileSystemTypeGet(fstype)
            else:
                filesystem = fileSystemTypeGetDefault()

            mountpoint = extra[0]

	# sanity check mountpoint
	if mountpoint is not None and mountpoint[0] != '/':
	    raise KickstartError, "The mount point \"%s\" is not valid." % (mountpoint,)

        if not vgname:
            raise KickstartError, "Must specify the volume group for the logical volume to be in"
        if not size and not percent and not preexist:
            raise KickstartError, "Must specify the size of a logical volume"
        if percent and percent <= 0 or percent > 100:
            raise KickstartValueError, "Logical Volume percentage must be between 0 and 100 percent"

        if not name:
            raise KickstartError, "Must specify a logical volume name"
        if not self.ksVGMapping.has_key(vgname):
            raise KickstartValueError, "Logical volume specifies a non-existent volume group"

        vgid = self.ksVGMapping[vgname]
	for areq in id.partitions.autoPartitionRequests:
	    if areq.type == REQUEST_LV:
		if areq.volumeGroup == vgid and areq.logicalVolumeName == name:
		    raise KickstartValueError, "Logical volume name %s already used in volume group %s" % (name,vgname)

        request = partRequests.LogicalVolumeRequestSpec(filesystem,
                                                        format = format,
                                                        mountpoint = mountpoint,
                                                        size = size,
                                                        percent = percent,
                                                        volgroup = vgid,
                                                        lvname = name,
							grow = grow,
							maxSizeMB=maxSizeMB,
                                                        preexist = preexist)
        self.addPartRequest(id.partitions, request)
                                                        

    def defineVolumeGroup(self, id, args):
        (args, extra) = isys.getopt(args, '', ['noformat','useexisting',
                                               'pesize='])

        preexist = 0
        format = 1
        pesize = 32768

        vgname = extra[0]

	for n in args:
	    (str, arg) = n
	    if str == '--noformat' or str == '--useexisting':
                preexist = 1
                format = 0
            elif str == "--pesize":
                pesize = int(arg)

        pvs = []
        # get the unique ids of each of the physical volumes
        for pv in extra[1:]:
            if pv not in self.ksPVMapping.keys():
                raise KickstartError, "Tried to use an undefined partition in Volume Group specification"
            pvs.append(self.ksPVMapping[pv])

        if len(pvs) == 0 and not preexist:
            raise KickstartError, "Volume group defined without any physical volumes"

        if pesize not in lvm.getPossiblePhysicalExtents(floor=1024):
            raise KickstartError, "Volume group specified invalid pesize: %d" %(pesize,)

        # get a sort of hackish id
        uniqueID = self.ksID
        self.ksVGMapping[extra[0]] = uniqueID
        self.ksID = self.ksID + 1
            
        request = partRequests.VolumeGroupRequestSpec(vgname = vgname,
                                                      physvols = pvs,
                                                      preexist = preexist,
                                                      format = format,
                                                      pesize = pesize)
        request.uniqueID = uniqueID
        self.addPartRequest(id.partitions, request)

    def defineRaid(self, id, args):
	(args, extra) = isys.getopt(args, '', [ 'level=', 'device=',
                                                'spares=', 'fstype=',
                                                'noformat', 'useexisting'] )

        level = None
        raidDev = None
        spares = 0
        fstype = None
        format = 1
        uniqueID = None
        preexist = 0
					
	for n in args:
	    (str, arg) = n
	    if str == '--level':
		level = arg
	    elif str == "--device":
		raidDev = arg
                if raidDev[0:2] == "md":
                    raidDev = raidDev[2:]
                raidDev = int(raidDev)
            elif str == "--spares":
                spares = int(arg)
            elif str == "--noformat":
                format = 0
                preexist = 1
            elif str == "--useexisting":
                preexist = 1
            elif str == "--fstype":
                fstype = arg

        if extra[0] == 'swap':
            filesystem = fileSystemTypeGet('swap')
            mountpoint = None
        elif extra[0].startswith("pv."):
            filesystem = fileSystemTypeGet("physical volume (LVM)")
            mountpoint = None

            if self.ksPVMapping.has_key(extra[0]):
                raise KickstartError, "Defined PV partition %s multiple times" % (extra[0],)

            # get a sort of hackish id
            uniqueID = self.ksID
            self.ksPVMapping[extra[0]] = uniqueID
            self.ksID = self.ksID + 1
        else:
            if fstype:
                filesystem = fileSystemTypeGet(fstype)
            else:
                filesystem = fileSystemTypeGetDefault()

            mountpoint = extra[0]

	# sanity check mountpoint
	if mountpoint is not None and mountpoint[0] != '/':
	    raise KickstartError, "The mount point \"%s\" is not valid." % (mountpoint,)

        raidmems = []
        # get the unique ids of each of the raid members
        for member in extra[1:]:
            if member not in self.ksRaidMapping.keys():
                raise KickstartError, "Tried to use an undefined partition in RAID specification"
	    if member in self.ksUsedMembers:
                raise KickstartError, "Tried to use the RAID member %s in two or more RAID specifications" % (member,)
		
            raidmems.append(self.ksRaidMapping[member])
	    self.ksUsedMembers.append(member)

        # XXX this shouldn't have to happen =\
        if raid.isRaid0(level):
            level = "RAID0"
        elif raid.isRaid1(level):
            level = "RAID1"
        elif raid.isRaid5(level):
            level = "RAID5"
        elif raid.isRaid6(level):
            level = "RAID6"

        if not level and preexist == 0:
            raise KickstartValueError, "RAID Partition defined without RAID level"
        if len(raidmems) == 0 and preexist == 0:
            raise KickstartValueError, "RAID Partition defined without any RAID members"

        request = partRequests.RaidRequestSpec(filesystem,
                                               mountpoint = mountpoint,
                                               raidmembers = raidmems,
                                               raidlevel = level,
                                               raidspares = spares,
                                               format = format,
                                               raidminor = raidDev,
                                               preexist = preexist)
        
        if uniqueID:
            request.uniqueID = uniqueID
        if preexist and raidDev is not None:
            request.device = "md%s" %(raidDev,)

        self.addPartRequest(id.partitions, request)


    def definePartition(self, id, args):
	# we set up partition requests (whee!)
	size = None
	grow = None
	maxSize = None
	disk = None
	onPart = None
        fsopts = None
        type = None
        primOnly = None
        format = 1
        fstype = None
        mountpoint = None
        uniqueID = None
        start = None
        end = None
        badblocks = None
        recommended = None

	(args, extra) = isys.getopt(args, '', [ 'size=', 'maxsize=', 
					'grow', 'onpart=', 'ondisk=',
                                        'bytes-per-inode=', 'usepart=',
                                        'type=', 'fstype=', 'asprimary',
                                        'noformat', 'start=', 'end=',
                                        'badblocks', 'recommended',
                                        'ondrive=', 'onbiosdisk=' ])

	for n in args:
	    (str, arg) = n
	    if str == '--size':
		size = int(arg)
	    elif str == '--maxsize':
		maxSize = int(arg)
	    elif str == '--grow':
		grow = 1
	    elif str == '--onpart' or str == '--usepart':
		onPart = arg
	    elif str == '--ondisk' or str == '--ondrive':
		disk = arg
            elif str == '--onbiosdisk':
                disk = isys.doGetBiosDisk(arg)
                if disk is None:
                    raise KickstartValueError, "Specified BIOS disk %s cannot be determined" %(arg,)
            elif str == '--bytes-per-inode':
                fsopts = ['-i', arg]
            # XXX this doesn't do anything right now
            elif str == '--type':
                type = int(arg)
            elif str == "--active":
                active = 1
            elif str == "--asprimary":
                primOnly = 1
            elif str == "--noformat":
                format = 0
            elif str == "--fstype":
                fstype = arg
            elif str == "--start":
                start = int(arg)
            elif str == "--end":
                end = int(arg)
            elif str == "--badblocks":
                # no longer support badblocks checking
		log("WARNING: --badblocks specified but is no longer supported")
            elif str == "--recommended":
                recommended = 1

	if len(extra) != 1:
	    raise KickstartValueError, "partition command requires one anonymous argument"

        if extra[0] == 'swap':
            filesystem = fileSystemTypeGet('swap')
            mountpoint = None
            if recommended:
                (size, maxSize) = iutil.swapSuggestion()
                grow = 1
        # if people want to specify no mountpoint for some reason, let them
        # this is really needed for pSeries boot partitions :(
        elif extra[0] == 'None':
            mountpoint = None
            if fstype:
                filesystem = fileSystemTypeGet(fstype)
            else:
                filesystem = fileSystemTypeGetDefault()
        elif extra[0] == 'prepboot':
            filesystem = fileSystemTypeGet("PPC PReP Boot")
            mountpoint = None
        elif extra[0].startswith("raid."):
            filesystem = fileSystemTypeGet("software RAID")
            
            if self.ksRaidMapping.has_key(extra[0]):
                raise KickstartError, "Defined RAID partition %s multiple times" % (extra[0],)
            
            # get a sort of hackish id
            uniqueID = self.ksID
            self.ksRaidMapping[extra[0]] = uniqueID
            self.ksID = self.ksID + 1
        elif extra[0].startswith("pv."):
            filesystem = fileSystemTypeGet("physical volume (LVM)")

            if self.ksPVMapping.has_key(extra[0]):
                raise KickstartError, "Defined PV partition %s multiple times" % (extra[0],)

            # get a sort of hackish id
            uniqueID = self.ksID
            self.ksPVMapping[extra[0]] = uniqueID
            self.ksID = self.ksID + 1
        # XXX should we let people not do this for some reason?
        elif extra[0] == "/boot/efi":
            filesystem = fileSystemTypeGet("vfat")
            mountpoint = extra[0]
        else:
            if fstype:
                filesystem = fileSystemTypeGet(fstype)
                mountpoint = extra[0]                
            else:
                filesystem = fileSystemTypeGetDefault()
                mountpoint = extra[0]

        if (size is None) and (not start and not end) and (not onPart):
            raise KickstartValueError, "partition command requires a size specification"
        if start and not disk:
            raise KickstartValueError, "partition command with start cylinder requires a drive specification"
        if disk and disk not in isys.hardDriveDict().keys():
            raise KickstartValueError, "specified disk %s in partition command which does not exist" %(disk,)
        
        # XXX bytes per inode is the only per fs option at the moment
        # and we can assume that it works like this since it only works
        # with ext[23]
        if fsopts:
            filesystem.extraFormatArgs.extend(fsopts)

        request = partRequests.PartitionSpec(filesystem,
                                             mountpoint = mountpoint,
                                             format = 1)
        
        if size is not None:
            request.size = size
        if start:
            request.start = start
        if end:
            request.end = end
        if grow:
            request.grow = 1
        if maxSize:
            request.maxSizeMB = maxSize
        if disk:
            request.drive = [ disk ]
        if primOnly:
            request.primary = 1
        if not format:
            request.format = 0
        if uniqueID:
            request.uniqueID = uniqueID
        if badblocks:
            request.badblocks = badblocks
        if onPart:
            # strip spurious /dev
            if onPart.startswith("/dev/"):
                onPart = onPart[5:]
            request.device = onPart
            for areq in id.partitions.autoPartitionRequests:
                if areq.device is not None and areq.device == onPart:
		    raise KickstartValueError, "Partition %s already used" %(onPart,)

        self.addPartRequest(id.partitions, request)
        id.partitions.isKickstart = 1

        self.skipSteps.append("partition")
        self.skipSteps.append("partitionmethod")
        self.skipSteps.append("partitionmethodsetup")
        self.skipSteps.append("fdisk")
        self.skipSteps.append("autopartition")
        self.skipSteps.append("zfcpconfig")        

    def doIgnoreDisk(self, id, args):
        # add disks to ignore list
        ignoreDrives = []
        exclusiveDrives = []
	(args, extra) = isys.getopt(args, '', [ 'drives=', 'only-use=' ])

        for n in args:
            (str, arg) = n
            if str == '--drives':
                ignoreDrives = string.split(arg, ',')
            elif str =='--only-use':
                exclusiveDrives = string.split(arg, ',')

        self.setIgnoredDisks(id, ignoreDrives)
        self.setExclusiveDisks(id, exclusiveDrives)

    def setSteps(self, dispatch):
        if self.installType == "upgrade":
            from upgradeclass import InstallClass
            theUpgradeclass = InstallClass(0)
            theUpgradeclass.setSteps(dispatch)
            
            # we have no way to specify migrating yet
            dispatch.skipStep("upgrademigfind")
            dispatch.skipStep("upgrademigratefs")
            dispatch.skipStep("upgradecontinue")
            dispatch.skipStep("findinstall", permanent = 1)
            dispatch.skipStep("language")
            dispatch.skipStep("keyboard")
#            dispatch.skipStep("mouse")
            dispatch.skipStep("welcome")
            dispatch.skipStep("betanag")
            dispatch.skipStep("installtype")
        else:
            BaseInstallClass.setSteps(self, dispatch)
            dispatch.skipStep("findrootparts")

        if self.interactive or flags.autostep:
            dispatch.skipStep("installtype")
            dispatch.skipStep("partitionmethod")
            dispatch.skipStep("partitionmethodsetup")
            dispatch.skipStep("fdisk")
            dispatch.skipStep("autopartition")
	    dispatch.skipStep("bootdisk")

	    # because these steps depend on the monitor being probed
	    # properly, and will stop you if you have an unprobed monitor,
	    # we should skip them for autostep
	    if flags.autostep:
		dispatch.skipStep("checkmonitorok")
		dispatch.skipStep("monitor")
            return

	dispatch.skipStep("bootdisk")
        dispatch.skipStep("welcome")
        dispatch.skipStep("betanag")
        dispatch.skipStep("confirminstall")
        dispatch.skipStep("confirmupgrade")
        dispatch.skipStep("network")
        dispatch.skipStep("installtype")

        # skipping firewall by default, disabled by default
	dispatch.skipStep("firewall")

	for n in self.skipSteps:
	    dispatch.skipStep(n)
        for n in self.showSteps:
            dispatch.skipStep(n, skip = 0)

    def setInstallData(self, id, intf = None):
	BaseInstallClass.setInstallData(self, id)

	self.setEarlySwapOn(1)
	self.postScripts = []
	self.preScripts = []
	self.tracebackScripts = []

	self.installType = "install"
        self.id = id
        self.id.firstboot = FIRSTBOOT_SKIP

        # parse the %pre
        try:
            self.readKickstart(id, self.file, parsePre = 1)
        except KickstartError, e:
            raise KickstartError, e

	log("Running kickstart %%pre script(s)")
	for script in self.preScripts:
	    script.run("/", self.serial)
	log("All kickstart %%pre script(s) have been run")

        # now read the kickstart file for real
        try:
            self.readKickstart(id, self.file)
        except KickstartError, e:
            log("Exception parsing ks.cfg: %s" %(e,))
            if intf is None:
                raise KickstartError, e
            else:
                intf.kickstartErrorWindow(e.__str__())

    def runTracebackScripts(self):
	log("Running kickstart %%traceback script(s)")
	for script in self.tracebackScripts:
	    script.run("/", self.serial)

    # Note that this assumes setGroupSelection() is called before
    # setPackageSelection()
    def setPackageSelection(self, hdlist, intf):
	for n in self.packageList:

            # allow arch:name syntax
            if n.find(".") != -1:
                fields = n.split(".")
                name = string.join(fields[:-1], ".")
                arch = fields[-1]
                found = 0
                if hdlist.pkgnames.has_key(name):
                    pkgs = hdlist.pkgnames[name]
                    for (nevra, parch) in pkgs:
                        if parch == arch:
                            hdlist.pkgs[nevra].select()
                            found = 1
                            continue
                    if found:
                        continue
            
            if hdlist.has_key(n):
                hdlist[n].select()
                continue

            if self.handleMissing == KS_MISSING_IGNORE:
                log("package %s doesn't exist, ignoring" %(n,))
                continue

            
            rc = intf.messageWindow(_("Missing Package"),
                                    _("You have specified that the "
                                      "package '%s' should be installed.  "
                                      "This package does not exist. "
                                      "Would you like to continue or "
                                      "abort your installation?") %(n,),
                                    type="custom",
                                    custom_buttons=[_("_Abort"),
                                                    _("_Continue")])
            if rc == 0:
                sys.exit(1)
            else:
                pass
                                

    def setGroupSelection(self, grpset, intf):
        grpset.unselectAll()
        
        if self.addBase:
            grpset.selectGroup("base")
	for n in self.groupList:
            try:
                grpset.selectGroup(n)
            except KeyError:
                if self.handleMissing == KS_MISSING_IGNORE:
                    log("group %s doesn't exist, ignoring" %(n,))
                else:
                    rc = intf.messageWindow(_("Missing Group"),
                                            _("You have specified that the "
                                              "group '%s' should be installed.  "
                                              "This group does not exist. "
                                              "Would you like to continue or "
                                              "abort your installation?")
                                            %(n,),
                                            type="custom",
                                            custom_buttons=[_("_Abort"),
                                                            _("_Continue")])
                    if rc == 0:
                        sys.exit(1)
                    else:
                        pass

        for n in self.excludedList:
            # allow arch:name syntax
            if n.find(".") != -1:
                fields = n.split(".")
                name = string.join(fields[:-1], ".")
                arch = fields[-1]
                if grpset.hdrlist.pkgnames.has_key(name):
                    pkgs = grpset.hdrlist.pkgnames[name]
                    for (nevra, parch) in pkgs:
                        if parch == arch:
                            grpset.hdrlist.pkgs[nevra].unselect(isManual = 1)
                            continue
            
            if grpset.hdrlist.has_key(n):
                grpset.hdrlist[n].unselect(isManual = 1)
            else:
                log("%s does not exist, can't exclude" %(n,))


    def __init__(self, file, serial):
	self.serial = serial
	self.file = file
	self.skipSteps = []
        self.showSteps = []
        self.interactive = 0
        self.addBase = 1
        self.packageList = []
        self.groupList = []
        self.excludedList = []
        self.ksRaidMapping = {}
	self.ksUsedMembers = []
        self.ksPVMapping = {}
        self.ksVGMapping = {}
        # XXX hack to give us a starting point for RAID, LVM, etc unique IDs.
        self.ksID = 100000

        # how to handle missing packages
        self.handleMissing = KS_MISSING_PROMPT
        
        BaseInstallClass.__init__(self, 0)

def Kickstart(file, serial):

    f = open(file, "r")
    lines = f.readlines()
    f.close()

    passedLines = []
    while lines:
	l = lines[0]
	lines = lines[1:]
	if l == "%installclass\n":
	    break
	passedLines.append(l)

    if lines:
	newKsFile = file + ".new"
	f = open(newKsFile, "w")
	f.writelines(passedLines)
	f.close()

	f = open('/tmp/ksclass.py', "w")
	f.writelines(lines)
	f.close()

	oldPath = sys.path
	sys.path.append('/tmp')

	from ksclass import CustomKickstart
	os.unlink("/tmp/ksclass.py")

	ksClass = CustomKickstart(newKsFile, serial)
	os.unlink(newKsFile)
    else:
	ksClass = KickstartBase(file, serial)

    return ksClass


# see if any vnc parameters are specified in the kickstart file
def parseKickstartVNC(ksfile):
    try:
	f = open(ksfile, "r")
    except:
	raise KSAppendException("Unable to open ks file %s" % (ksfile,))

    lines = f.readlines()
    f.close()

    usevnc = 0
    vnchost = None
    vncport = None
    vncpasswd = None
    for l in lines:
	args = isys.parseArgv(l)
	
	if args:
            if args[0] in ("%pre", "%post", "%traceback", "%packages"):
                break
            
	    if args[0] != 'vnc':
		continue
	else:
	    continue

	idx = 1
	while idx < len(args):
	    if args[idx] == "--password":
		try:
		    vncpasswd = args[idx+1]
		except:
		    raise KickstartError, "Missing argument to vnc --password option"
		idx += 2
	    elif args[idx] == "--connect":
		try:
		    connectspec = args[idx+1]
		except:
		    raise KickstartError, "Missing argument to vnc --connect option"
		cargs = string.split(connectspec, ":")
		vnchost = cargs[0]
		if len(cargs) > 1:
		    if len(cargs[1]) > 0:
			vncport = cargs[1]
		    
		idx += 2
	    else:
		raise KickstartError, "Unknown vnc option %s" % (args[idx],)

	usevnc = 1
	break

    return (usevnc, vncpasswd, vnchost, vncport)

#
# look through ksfile and if it contains a line:
#
# %ksappend <url>
#
# pull <url> down and append to /tmp/ks.cfg. This is run before we actually
# parse the complete kickstart file.
#
# Main use is to have the ks.cfg you send to the loader by minimal, and then
# use %ksappend to pull via https anything private (like passwords, etc) in
# the second stage.
#
def pullRemainingKickstartConfig(ksfile):
    try:
	f = open(ksfile, "r")
    except:
	raise KSAppendException("Unable to open ks file %s" % (ksfile,))

    lines = f.readlines()
    f.close()

    url = None
    for l in lines:
	ll = l.strip()
	if string.find(ll, "%ksappend") == -1:
	    continue

	try:
	    (xxx, ksurl) = string.split(ll, ' ')
	except:
	    raise KSAppendException("Illegal url for %%ksappend - %s" % (ll,))

	log("Attempting to pull second part of ks.cfg from url %s" % (ksurl,))

	try:
	    url = urllib2.urlopen(ksurl)
	except urllib2.HTTPError, e:
	    raise KSAppendException("IOError: %s:%s" % (e.code, e.msg))
	except urllib2.URLError, e:
	    raise KSAppendException("IOError: -1:%s" % (e.reason,))
	else:
	    # sanity check result - sometimes FTP doesnt
	    # catch a file is missing
	    try:
		clen = url.info()['content-length']
	    except Exception, e:
		clen = 0

	    if clen < 1:
		raise KSAppendException("IOError: -1:File not found")

	break

    # if we got something then rewrite /tmp/ks.cfg with new information
    if url is not None:
	os.rename("/tmp/ks.cfg", "/tmp/ks.cfg-part1")

	# insert contents of original /tmp/ks.cfg w/o %ksappend line
	f = open("/tmp/ks.cfg", 'w+')
	for l in lines:
	    ll = l.strip()
	    if string.find(ll, "%ksappend") != -1:
		continue
	    f.write(l)

	# now write part we just grabbed
	f.write(url.read())
	f.close()

	# close up url and we're done
	url.close()
	
    return None

