#
# kickstart.py: kickstart install support
#
# Copyright 1999-2002 Red Hat, Inc.
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

class Script:
    def __repr__(self):
	str = ("(s: '%s' i: %s c: %d)") %  \
	    (self.script, self.interp, self.inChroot)
	return string.replace(str, "\n", "|")

    def __init__(self, script, interp, inChroot):
	self.script = script
	self.interp = interp
	self.inChroot = inChroot

    def run(self, chroot, serial):
	scriptRoot = "/"
	if self.inChroot:
	    scriptRoot = chroot

	path = scriptRoot + "/tmp/ks-script"

	f = open(path, "w")
	f.write(self.script)
	f.close()
	os.chmod(path, 0700)

	if serial:
	    messages = "/tmp/ks-script.log"
	else:
	    messages = "/dev/tty3"

	rc = iutil.execWithRedirect(self.interp,
				    [self.interp,"/tmp/ks-script"],
				    stdout = messages, stderr = messages,
				    root = scriptRoot)

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
	    raise ValueError, "a single argument is expected to rootPw"

	self.setRootPassword(id, extra[0], isCrypted = isCrypted)
	self.skipSteps.append("accounts")
	
    def doFirewall(self, id, args):
	(args, extra) = isys.getopt(args, '',
		[ 'dhcp', 'ssh', 'telnet', 'smtp', 'http', 'ftp',
		  'port=', 'high', 'medium', 'disabled', 'trust=' ])
		  
	dhcp = 0
	ssh = 0
	telnet = 0
	smtp = 0
	http = 0
	ftp = 0
	policy = 0
	enable = -1
	trusts = []
	ports = ""
	
	for n in args:
	    (str, arg) = n
	    if str == '--dhcp':
		dhcp = 1
	    elif str == '--ssh':
		ssh = 1
	    elif str == '--telnet':
		telnet = 1
	    elif str == '--smtp':
		smtp = 1
	    elif str == '--http':
		http = 1
	    elif str == '--ftp':
		ftp = 1
	    elif str == '--high':
		policy = 0
		enable = 1
	    elif str == '--medium':
		policy = 1
		enable = 1
	    elif str == '--disabled':
		enable = 0
	    elif str == '--trust':
		trusts.append(arg)
	    elif str == '--port':
		if ports:
		    ports = '%s,%s' % (ports, arg)
		else:
		    ports = arg
	    
	self.setFirewall(id, enable, policy, trusts, ports, dhcp, ssh, telnet,
			smtp, http, ftp)
	    
    def doAuthconfig(self, id, args):
	(args, extra) = isys.getopt(args, '',
                [ 'useshadow', 'enableshadow',
		  'enablemd5',
                  'enablenis', 'nisdomain=', 'nisserver=',
                  'enableldap', 'enableldapauth', 'ldapserver=', 'ldapbasedn=',
                  'enableldaptls', 
                  'enablekrb5', 'krb5realm=', 'krb5kdc=', 'krb5adminserver=',
                  'enablehesiod', 'hesiodlhs=', 'hesiodrhs=',
                  'enablesmbauth', 'smbservers=', 'smbworkgroup=',
                  'enablecache'])

	useShadow = 0

	useMd5 = 0

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
		useMd5 = 1
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
	    
	self.setAuthentication(id, useShadow, useMd5,
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
                  'upgrade'])

        validLocations = [ "mbr", "partition", "none" ]
        appendLine = ""
        location = "mbr"
        password = None
        md5pass = None
        forceLBA = 0
        linear = 1
        upgrade = 0

        for n in args:
            (str, arg) = n
            if str == '--append':
                appendLine = arg
            elif str == '--location':
                location = arg
            elif str == '--useLilo':
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

        if location not in validLocations:
            raise ValueError, "mbr, partition, or none expected for bootloader command"
        if location == "none":
            location = None
        elif location == "partition":
            location = "boot"

        if upgrade and not id.upgrade.get():
            raise RuntimeError, "Selected upgrade mode for bootloader but not doing an upgrade"

        if upgrade:
            id.bootloader.kickstart = 1
            id.bootloader.doUpgradeOnly = 1

        
        self.showSteps.append("bootloadersetup")
                
        self.setBootloader(id, useLilo, location, linear, forceLBA,
                           password, md5pass, appendLine)
        self.skipSteps.append("upgbootloader")
        self.skipSteps.append("bootloader")
        self.skipSteps.append("bootloaderadvanced")

        if location is None:
            self.skipSteps.append("instbootloader")

    def doLilo	(self, id, args):
        self.doBootloader(id, args, useLilo = 1)

    def doFirstboot(self, id, args):
        (args, extra) = isys.getopt(args, '',
                                    ['reconfig', 'enable', 'disable'])

        fb = FIRSTBOOT_SKIP

	for n in args:
	    (str, arg) = n
	    if str == '--reconfig':
                fb = FIRSTBOOT_RECONFIG
            elif str == '--enable':
                fb = FIRSTBOOT_DEFAULT
            elif str == '--disable':
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
	    raise ValueError, "unexpected arguments to xconfig command"

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


    def doUpgrade(self, id, args):
	self.installType = "upgrade"
        id.upgrade.set(1)

    def doNetwork(self, id, args):
	# nodns is only used by the loader
	(args, extra) = isys.getopt(args, '',
		[ 'bootproto=', 'ip=', 'netmask=', 'gateway=', 'nameserver=',
		  'nodns', 'device=', 'hostname='])
	bootProto = "dhcp"
	ip = None
	netmask = ""
	gateway = ""
	nameserver = ""
	hostname = ""
        device = None
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

	self.setNetwork(id, bootProto, ip, netmask, device=device)
	if hostname != "":
	    self.setHostname(id, hostname)
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
	(args, extra) = isys.getopt(args, '', [ 'device=', 'emulthree' ])
        mouseType = "none"
	device = None
	emulThree = 0

	for n in args:
	    (str, arg) = n
	    if str == "--device":
		device = arg
	    elif str == "--emulthree":
		emulThree = 1

	if extra:
	    mouseType = extra[0]

	if mouseType != "none":
            self.setMouse(id, mouseType, device, emulThree)

        self.skipSteps.append("mouse")

    def doReboot(self, id, args):
        self.skipSteps.append("complete")

    def doSkipX(self, id, args):
        self.skipSteps.append("videocard")
        self.skipSteps.append("monitor")
        self.skipSteps.append("xcustom")
        self.skipSteps.append("handleX11pkgs")
        self.skipSteps.append("writexconfig")
        id.xsetup.skipx = 1

    def doInteractive(self, id, args):
        self.interactive = 1

    def doAutoStep(self, id, args):
        flags.autostep = 1

    # read the kickstart config...  if parsePre is set, only parse
    # the %pre, otherwise ignore the %pre.  assume we're starting in where
    def readKickstart(self, id, file, parsePre = 0, where = "commands"):
	handlers = { 
		     "auth"		: self.doAuthconfig	,
		     "authconfig"	: self.doAuthconfig	,
		     "cdrom"		: None			,
		     "clearpart"	: self.doClearPart	,
		     "device"		: None			,
		     "deviceprobe"	: None			,
		     "driverdisk"	: None			,
		     "firewall"		: self.doFirewall	,
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
		     "rootpw"		: self.doRootPw		,
		     "skipx"		: self.doSkipX		,
		     "text"		: None			,
		     "timezone"		: self.doTimezone	,
		     "url"		: None			,
		     "upgrade"		: self.doUpgrade	,
		     "xconfig"		: self.doXconfig	,
		     "xdisplay"		: None			,
		     "zerombr"		: self.doZeroMbr	,
                     "interactive"      : self.doInteractive    ,
                     "autostep"         : self.doAutoStep       ,
                     "firstboot"        : self.doFirstboot      ,
		   }

	packages = []
	groups = []
        excludedPackages = []
	for n in open(file).readlines():
	    args = isys.parseArgv(n)

	    # don't eliminate white space or comments from scripts
	    if where != "pre" and where != "post":
		if not args or args[0][0] == '#': continue

	    if args and (args[0] == "%post" or args[0] == "%pre"):
		if ((where =="pre" and parsePre) or
                    (where == "post" and not parsePre)):
		    s = Script(script, scriptInterp, scriptChroot)
		    if where == "pre":
                        self.preScripts.append(s)
		    else:
			self.postScripts.append(s)

		where = args[0][1:]
		args = isys.parseArgv(n)

		scriptInterp = "/bin/sh"
		if where == "pre":
		    scriptChroot = 0
		else:
		    scriptChroot = 1

		script = ""

		argList = [ 'interpreter=' ]
		if where == "post":
		    argList.append('nochroot')

		(args, extra) = isys.getopt(args, '', argList)
		for n in args:
		    (str, arg) = n
		    
		    if str == "--nochroot":
			scriptChroot = 0
		    elif str == "--interpreter":
			scriptInterp = arg

            elif args and args[0] == "%include" and not parsePre:
                if len(args) < 2:
                    raise RuntimeError, "Invalid %include line"
                else:
                    # read in the included file and set our where appropriately
                    where = self.readKickstart(id, args[1], where = where)
            elif args and args[0] == "%packages":
		if ((where =="pre" and parsePre) or
                    (where == "post" and not parsePre)):
		    s = Script(script, scriptInterp, scriptChroot)
		    if where == "pre":
			self.preScripts.append(s)
		    else:
			self.postScripts.append(s)

                # if we're parsing the %pre, we don't need to continue
                if parsePre:
                    continue

                if len(args) > 1:
                    if args[1] == "--resolvedeps":
                        id.handleDeps = RESOLVE_DEPS
                    elif args[1] == "--ignoredeps":
                        id.handleDeps = IGNORE_DEPS
                
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
		    if handlers[args[0]]:
			handlers[args[0]](id, args[1:])
		elif where == "pre" or where == "post":
		    script = script + n
		else:
		    raise SyntaxError, "I'm lost in kickstart"

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
            (where == "post" and not parsePre)):
	    s = Script(script, scriptInterp, scriptChroot)
	    if where == "pre":
		self.preScripts.append(s)
	    else:
		self.postScripts.append(s)

        return where

    def doClearPart(self, id, args):
        type = CLEARPART_TYPE_NONE
        drives = None
        initAll = 0

        (args, extra) = isys.getopt(args, '', [ 'linux', 'all', 'drives=',
                                                'initlabel'])

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
            
        self.setClearParts(id, type, drives, initAll = initAll)

    def defineLogicalVolume(self, id, args):
        (args, extra) = isys.getopt(args, '', [ 'vgname=',
                                                'size=',
                                                'name=',
                                                'fstype=',
                                                'percent=',
						'maxsize=',
						'grow', 'recommended'])

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
            else:
                print str, " ", arg

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

        if not vgname:
            raise RuntimeError, "Must specify the volume group for the logical volume to be in"
        if not size and not percent:
            raise RuntimeError, "Must specify the size of a logical volume"
        if percent and percent <= 0 or percent > 100:
            raise ValueError, "Logical Volume percentage must be between 0 and 100 percent"
        if not name:
            raise RuntimeError, "Must specify a logical volume name"

        if not self.ksVGMapping.has_key(vgname):
            raise ValueError, "Logical volume specifies a non-existent volume group"
        vgid = self.ksVGMapping[vgname]

        request = partRequests.LogicalVolumeRequestSpec(filesystem,
                                                        format = format,
                                                        mountpoint = mountpoint,
                                                        size = size,
                                                        percent = percent,
                                                        volgroup = vgid,
                                                        lvname = name,
							grow = grow,
							maxSizeMB=maxSizeMB)
        id.partitions.autoPartitionRequests.append(request)        
                                                        

    def defineVolumeGroup(self, id, args):
        (args, extra) = isys.getopt(args, '', [])

        vgname = extra[0]

        pvs = []
        # get the unique ids of each of the physical volumes
        for pv in extra[1:]:
            if pv not in self.ksPVMapping.keys():
                raise RuntimeError, "Tried to use an undefined partition in Volume Group specification"
            pvs.append(self.ksPVMapping[pv])

        if len(pvs) == 0:
            raise ValueError, "Volume group defined without any physical volumes"

        # get a sort of hackish id
        uniqueID = self.ksID
        self.ksVGMapping[extra[0]] = uniqueID
        self.ksID = self.ksID + 1
            
        request = partRequests.VolumeGroupRequestSpec(vgname = vgname,
                                                      physvols = pvs)
        request.uniqueID = uniqueID
        id.partitions.autoPartitionRequests.append(request)

    def defineRaid(self, id, args):
	(args, extra) = isys.getopt(args, '', [ 'level=', 'device=',
                                                'spares=', 'fstype=',
                                                'noformat'] )

        level = None
        raidDev = None
        spares = 0
        fstype = None
        format = 1
        uniqueID = None
					
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
            elif str == "--fstype":
                fstype = arg

        if extra[0] == 'swap':
            filesystem = fileSystemTypeGet('swap')
            mountpoint = None
        elif extra[0].startswith("pv."):
            filesystem = fileSystemTypeGet("physical volume (LVM)")
            mountpoint = None

            if self.ksPVMapping.has_key(extra[0]):
                raise RuntimeError, "Defined PV partition %s multiple times" % (extra[0],)

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

        raidmems = []
        # get the unique ids of each of the raid members
        for member in extra[1:]:
            if member not in self.ksRaidMapping.keys():
                raise RuntimeError, "Tried to use an undefined partition in RAID specification"
            raidmems.append(self.ksRaidMapping[member])

        # XXX this shouldn't have to happen =\
        if raid.isRaid0(level):
            level = "RAID0"
        elif raid.isRaid1(level):
            level = "RAID1"
        elif raid.isRaid5(level):
            level = "RAID5"

        if not level:
            raise ValueError, "RAID Partition defined without RAID level"
        if len(raidmems) == 0:
            raise ValueError, "RAID Partition defined without any RAID members"

        request = partRequests.RaidRequestSpec(filesystem,
                                               mountpoint = mountpoint,
                                               raidmembers = raidmems,
                                               raidlevel = level,
                                               raidspares = spares,
                                               format = format,
                                               raidminor = raidDev)
        
        if uniqueID:
            request.uniqueID = uniqueID
            
        id.partitions.autoPartitionRequests.append(request)


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
                                        'ondrive='])

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
                badblocks = 1
            elif str == "--recommended":
                recommended = 1

	if len(extra) != 1:
	    raise ValueError, "partition command requires one anonymous argument"

        if extra[0] == 'swap':
            filesystem = fileSystemTypeGet('swap')
            mountpoint = None
            if recommended:
                (size, maxSize) = iutil.swapSuggestion()
                grow = 1
        elif extra[0].startswith("raid."):
            filesystem = fileSystemTypeGet("software RAID")
            
            if self.ksRaidMapping.has_key(extra[0]):
                raise RuntimeError, "Defined RAID partition %s multiple times" % (extra[0],)
            
            # get a sort of hackish id
            uniqueID = self.ksID
            self.ksRaidMapping[extra[0]] = uniqueID
            self.ksID = self.ksID + 1
        elif extra[0].startswith("pv."):
            filesystem = fileSystemTypeGet("physical volume (LVM)")

            if self.ksPVMapping.has_key(extra[0]):
                raise RuntimeError, "Defined PV partition %s multiple times" % (extra[0],)

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

        if (not size) and (not start and not end) and (not onPart):
            raise ValueError, "partition command requires a size specification"
        if start and not disk:
            raise ValueError, "partition command with start cylinder requires a drive specification"
        
        # XXX bytes per inode is the only per fs option at the moment
        # and we can assume that it works like this since it only works
        # with ext[23]
        if fsopts:
            filesystem.extraFormatArgs.extend(fsopts)

        request = partRequests.PartitionSpec(filesystem,
                                             mountpoint = mountpoint,
                                             format = 1)
        if size:
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
            request.device = onPart

        id.partitions.autoPartitionRequests.append(request)
        id.partitions.isKickstart = 1

        self.skipSteps.append("partition")
        self.skipSteps.append("partitionmethod")
        self.skipSteps.append("partitionmethodsetup")
        self.skipSteps.append("fdisk")
        self.skipSteps.append("fdasd")
        self.skipSteps.append("autopartition")

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
            dispatch.skipStep("mouse")
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
            dispatch.skipStep("fdasd")
            dispatch.skipStep("autopartition")
            dispatch.skipStep("bootdisk")            
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

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)

	self.setEarlySwapOn(1)
	self.postScripts = []
	self.preScripts = []

	self.installType = "install"
        self.id = id
        self.id.firstboot = FIRSTBOOT_SKIP

        # parse the %pre
	self.readKickstart(id, self.file, parsePre = 1)

	log("Running kickstart %%pre script(s)")
	for script in self.preScripts:
	    script.run("/", self.serial)
	log("All kickstart %%pre script(s) have been run")

        # now read the kickstart file for real
	self.readKickstart(id, self.file)            

    # Note that this assumes setGroupSelection() is called after
    # setPackageSelection()
    def setPackageSelection(self, hdlist):
	for pkg in hdlist.keys():
	    hdlist[pkg].setState((0, 0))

	for n in self.packageList:
	    hdlist[n].select()

    def setGroupSelection(self, comps):
	for comp in comps:
	    comp.unselect()

	comps['Base'].select()
	for n in self.groupList:
	    comps[n].select()

        for n in self.excludedList:
            if comps.packages.has_key(n):
                comps.packages[n].unselect()
            else:
                log("%s does not exist, can't exclude" %(n,))

    def __init__(self, file, serial):
	self.serial = serial
	self.file = file
	self.skipSteps = []
        self.showSteps = []
        self.interactive = 0
        self.packageList = []
        self.groupList = []
        self.excludedList = []
        self.ksRaidMapping = {}
        self.ksPVMapping = {}
        self.ksVGMapping = {}
        # XXX hack to give us a starting point for RAID, LVM, etc unique IDs.
        self.ksID = 100000 
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
