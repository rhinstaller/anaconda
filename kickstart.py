import iutil
import isys
import os
from installclass import BaseInstallClass
from partitioning import *
from autopart import *
from fsset import *
import sys
import string

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

	iutil.execWithRedirect (self.interp, [self.interp, "/tmp/ks-script" ], 
		stdout = messages, stderr = messages, root = scriptRoot)
				
	os.unlink(path)

class KickstartBase(BaseInstallClass):
    def postAction(self, rootPath, serial):
	for script in self.postScripts:
	    script.run(rootPath, serial)

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
	ports = None
	
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
		    ports = '%s %s' % (ports, arg)
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
                  'enablekrb5', 'krb5realm=', 'krb5kdc=', 'krb5adminserver=',
                  'enablehesiod', 'hesiodlhs=', 'hesiodrhs=',
                  'enablesmbauth', 'smbservers=', 'smbworkgroup='])

	useShadow = 0

	useMd5 = 0

	useNis = 0
	nisServer = None
	nisDomain = None
	nisBroadcast = 0

        useLdap = 0
        useLdapauth = 0
        ldapServer = None
        ldapBasedn = None

        useKrb5 = 0
        krb5Realm = None
        krb5Kdc = None
        krb5Admin = None

        useHesiod = 0
        hesiodLhs = None
        hesiodRhs = None

        useSamba = 0
        smbServers = None
        smbWorkgroup = None
	
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
                

	if useNis and not nisServer: nisBroadcast = 1
	    
	self.setAuthentication(id, useShadow, useMd5,
                               useNis, nisDomain, nisBroadcast, nisServer,
                               useLdap, useLdapauth, ldapServer, ldapBasedn,
                               useKrb5, krb5Realm, krb5Kdc, krb5Admin,
                               useHesiod, hesiodLhs, hesiodRhs,
                               useSamba, smbServers, smbWorkgroup)
        
	self.skipSteps.append("authentication")

    def doBootloader (self, id, args):
        (args, extra) = isys.getopt(args, '',
                [ 'append=', 'location=', 'useLilo' ])

        appendLine = None
        location = "mbr"
        useLilo = 0

        for n in args:
            (str, arg) = n
            if str == '--append':
                appendLine = arg
            elif str == '--location':
                # XXX need this to do something
                pass
            elif str == '--useLilo':
                useLilo = 1
                
        self.setBootloader(id, useLilo, appendLine)
        self.skipSteps.append("bootloader")

    def doLilo	(self, id, args):
	(args, extra) = isys.getopt(args, '',
		[ 'append=', 'location=', 'linear', 'nolinear' ])

	appendLine = None
	location = "mbr"
	linear = 1

	for n in args:
	    (str, arg) = n
	    if str == '--append':
		appendLine = arg
	    elif str == '--linear':
		linear = 1
	    elif str == '--nolinear':
		linear = 0
	    elif str == '--location':
                # XXX this doesn't really do anything right now
	        if arg == 'mbr' or arg == 'partition':
		    location = arg
		elif arg == 'none':
		    location = None
		else:
		    raise ValueError, ("mbr, partition or none expected for "+
			"lilo command")

	self.setLiloInformation(id, location, linear, appendLine)
        self.skipSteps.append("bootloader")        

    def doLiloCheck (self, args):
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

        # XXX make sure new xconfig args get documented
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
                depth = arg
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
	#
	# XXX
	#
	# this won't work. it needs to much with the set of install steps
	#
	self.installType = "upgrade"

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

	self.setNetwork(id, bootProto, ip, netmask, gateway, nameserver, device=device)
	if hostname != "":
	    self.setHostname(hostname)

    def doLang(self, id, args):
        self.setLanguage(id, args[0])
	self.skipSteps.append("language")

    def doLangSupport (self, id, args):
        (args, extra) = isys.getopt(args, '', [ 'default=' ])
        if args:
            self.setLanguageDefault (id, args[0][1])
        self.setLanguageSupport(id, extra)

        # XXX make sure langsupport command gets documented
        self.skipSteps.append("languagesupport")

    def doKeyboard(self, id, args):
        self.setKeyboard(id, args[0])
	self.skipSteps.append("keyboard")

    def doZeroMbr(self, args):
	if args[0] == "yes":
	    self.setZeroMbr(1)

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
        pass
#        self.skipSteps.append("complete")

    def doSkipX(self, id, args):
        self.skipSteps.append("videocard")
        self.skipSteps.append("monitor")
        self.skipSteps.append("xcustom")
        self.skipSteps.append("handleX11pkgs")
        self.skipSteps.append("writexconfig")

    def readKickstart(self, id, file):
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
		   }

	where = "commands"
	packages = []
	groups = []
        excludedPackages = []
	for n in open(file).readlines():
            print n
	    args = isys.parseArgv(n)

	    # don't eliminate white space or comments from scripts
	    if where != "pre" and where != "post":
		if not args or args[0][0] == '#': continue

	    if args and (args[0] == "%post" or args[0] == "%pre"):
		if where =="pre" or where == "post":
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

	    elif args and args[0] == "%packages":
		if where =="pre" or where == "post":
		    s = Script(script, scriptInterp, scriptChroot)
		    if where == "pre":
			self.preScripts.append(s)
		    else:
			self.postScripts.append(s)

		where = "packages"
	    else:
		if where == "packages":
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

	self.groupList = groups
	self.packageList = packages
        self.excludedList = excludedPackages

        # XXX this is just not really a good way to do this...
        id.bootloader.setDefaultDevice = 1

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
                
	if where =="pre" or where == "post":
	    s = Script(script, scriptInterp, scriptChroot)
	    if where == "pre":
		self.preScripts.append(s)
	    else:
		self.postScripts.append(s)

    def doClearPart(self, id, args):
        if args[0] == '--linux':
            type = CLEARPART_TYPE_LINUX
        elif args[0] == '--all':
            type = CLEARPART_TYPE_ALL
        else:
            # XXX invalid clearpart arguments
            return

        # XXX want to have --drive hda,hdb 
        self.setClearParts(id, type, None)

    def defineRaid(self, args):
	(args, extra) = isys.getopt(args, '', [ 'level=', 'device=' ] )
					
	for n in args:
	    (str, arg) = n
	    if str == '--level':
		level = int(arg)
	    elif str == "--device":
		raidDev = arg

	mntPoint = extra[0]
	extra = extra[1:]

        # XXX reimplement
        #	self.addRaidEntry(mntPoint, raidDev, level, extra)

    def definePartition(self, id, args):
	# we set up partition requests (whee!)
	size = None
	grow = None
	maxSize = None
	device = None
	onPart = None
        fsopts = None
        type = None
        partNum = None
        primOnly = None
        active = None
        format = 1
        fstype = None
        mountpoint = None
        
	(args, extra) = isys.getopt(args, '', [ 'size=', 'maxsize=', 
					'grow', 'onpart=', 'ondisk=',
                                        'bytes-per-inode=', 'usepart=',
                                        'onprimary=', 'active', 'type=',
                                        'fstype=', 'asprimary', 'noformat'])

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
	    elif str == '--ondisk':
		device = arg
            elif str == '--bytes-per-inode':
                fsopts = ['-i', arg]
            elif str == '--onprimary':
                partNum = int(arg)
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

	if len(extra) != 1:
	    raise ValueError, "partition command requires one anonymous argument"

        if extra[0] == 'swap':
            filesystem = fileSystemTypeGet('swap')
            mountpoint = None
        elif not fstype:
            filesystem = fileSystemTypeGetDefault()
            mountpoint = extra[0]
        else:
            filesystem = fileSystemTypeGet(fstype)
            mountpoint = extra[0]            

        if not size:
            raise ValueError, "temporarily requiring a size to be specified"

        request = PartitionSpec(filesystem, size = size, mountpoint = mountpoint, format=1)
        if grow:
            request.grow = 1
        if maxSize:
            request.maxSize = maxSize
        if device:
            request.drive = [ device ]
        if partNum or primOnly:
            request.primary = 1
        if not format:
            request.format = 0
        
        id.autoPartitionRequests.append(request)

        self.skipSteps.append("partition")
        self.skipSteps.append("partitionmethod")
        self.skipSteps.append("partitionmethodsetup")
        self.skipSteps.append("fdisk")
        self.skipSteps.append("autopartition")

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch)

	dispatch.skipStep("bootdisk")
        dispatch.skipStep("welcome")
        dispatch.skipStep("package-selection")
        dispatch.skipStep("confirminstall")
        dispatch.skipStep("confirmupgrade")
        dispatch.skipStep("network")
        dispatch.skipStep("installtype")

        # skipping firewall by default, disabled by default
	dispatch.skipStep("firewall")

	for n in self.skipSteps:
	    dispatch.skipStep(n)

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)

	self.setEarlySwapOn(1)
	self.partitions = []
	self.postScripts = []
	self.preScripts = []

	self.installType = "install"
	self.readKickstart(id, self.file)

	for script in self.preScripts:
	    script.run("/", self.serial)

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
            comps.packages[n].unselect()

    def __init__(self, file, serial):
	self.serial = serial
	self.file = file
	self.skipSteps = []
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
