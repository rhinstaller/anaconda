import iutil
import isys
import os
from installclass import BaseInstallClass
from installclass import FSEDIT_CLEAR_LINUX
from installclass import FSEDIT_CLEAR_ALL
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

    def doRootPw(self, args):
	(args, extra) = isys.getopt(args, '', [ 'iscrypted' ])

	isCrypted = 0
	for n in args:
	    (str, arg) = n
	    if (str == '--iscrypted'):
		isCrypted = 1

	if len(extra) != 1:
	    raise ValueError, "a single argument is expected to rootPw"

	BaseInstallClass.doRootPw(self, extra[0], isCrypted = isCrypted)
	self.addToSkipList("accounts")

    def doAuthconfig(self, args):
	(args, extra) = isys.getopt(args, '',
                [ 'useshadow',
		  'enablemd5',
                  'enablenis', 'nisdomain=', 'nisserver=',
                  'enableldap', 'enableldapauth', 'ldapserver=', 'ldapbasedn=',
                  'enablekrb5', 'krb5realm=', 'krb5kdc=', 'krb5adminserver=',
                  'enablehesiod', 'hesiodlhs=', 'hesiodrhs='  ])

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
	
	for n in args:
	    (str, arg) = n
	    if (str == '--enablenis'):
		useNis = 1
	    elif (str == '--useshadow'):
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

	if useNis and not nisServer: nisBroadcast = 1
	    
	self.setAuthentication(useShadow, useMd5,
                               useNis, nisDomain, nisBroadcast, nisServer,
                               useLdap, useLdapauth, ldapServer, ldapBasedn,
                               useKrb5, krb5Realm, krb5Kdc, krb5Admin,
                               useHesiod, hesiodLhs, hesiodRhs )
        
	self.addToSkipList("authentication")

    def doLilo	(self, args):
	(args, extra) = isys.getopt(args, '',
		[ 'append=', 'location=', 'linear' ])

	appendLine = None
	location = "mbr"
	linear = 0

	for n in args:
	    (str, arg) = n
	    if str == '--append':
		appendLine = arg
	    elif str == '--linear':
		linear = 1
	    elif str == '--location':
	        if arg == 'mbr' or arg == 'partition':
		    location = arg
		elif arg == 'none':
		    location = None
		else:
		    raise ValueError, ("mbr, partition or none expected for "+
			"lilo command")

	self.setLiloInformation(location, linear, appendLine)
	self.addToSkipList("lilo")

    def doLiloCheck (self, args):
        drives = isys.hardDriveList ().keys()
	drives.sort(isys.compareDrives)
	device = drives[0]
	isys.makeDevInode(device, '/tmp/' + device)
	fd = os.open('/tmp/' + device, os.O_RDONLY)
	os.unlink('/tmp/' + device)
	block = os.read(fd, 512)
	os.close(fd)
	if block[6:10] == "LILO":
	    sys.exit(0)

    def doTimezone(self, args):
	(args, extra) = isys.getopt(args, '',
		[ 'utc' ])

	isUtc = 0
	
	for n in args:
	    (str, arg) = n
	    if str == '--utc':
		isUtc = 1

	self.setTimezoneInfo(extra[0], asUtc = isUtc)

	self.addToSkipList("timezone")


    def doXconfig(self, args):
	(args, extra) = isys.getopt(args, '',
		[ 'server=', 'card=', 'monitor=', 'hsync=', 'vsync=',
		  'startxonboot', 'noprobe', 'defaultdesktop=' ])

	if extra:
	    raise ValueError, "unexpected arguments to xconfig command"

	server = None
	card = None
	monitor = None
	hsync = None
	vsync = None
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
	    elif (str == "--monitor"):
		monitor = arg
	    elif (str == "--hsync"):
		hsync = arg
	    elif (str == "--vsync"):
		vsync = arg
	    elif (str == "--startxonboot"):
		startX = 1
            elif (str == "--defaultdesktop"):
                defaultdesktop = arg

	self.configureX(server, card, monitor, hsync, vsync, noProbe,
		        startX)
        self.setDesktop(defaultdesktop)
        
	self.addToSkipList("xconfig")

    def doInstall(self, args):
	self.installType = "install"

    def doUpgrade(self, args):
	self.installType = "upgrade"

    def doNetwork(self, args):
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

	self.setNetwork(bootProto, ip, netmask, gateway, nameserver, device=device)
	if hostname != "":
	    self.setHostname(hostname)

    def doLang(self, args):
        self.setLanguage(args[0])
        self.addToSkipList("language")

    def doKeyboard(self, args):
        self.setKeyboard(args[0])
        self.addToSkipList("keyboard")

    def doZeroMbr(self, args):
	if args[0] == "yes":
	    self.setZeroMbr(1)

    def doMouse(self, args):
	mouseToMouse = {
	     "alpsps/2" : "ALPS - GlidePoint (PS/2)",
	     "ascii" : "ASCII - MieMouse (serial)",
	     "asciips/2" : "ASCII - MieMouse (PS/2)",
	     "atibm" : "ATI - Bus Mouse",
	     "generic" : "Generic - 2 Button Mouse (serial)" ,
	     "generic3" : "Generic - 3 Button Mouse (serial)" ,
	     "genericps/2" : "Generic - 2 Button Mouse (PS/2)" ,
	     "generic3ps/2" : "Generic - 3 Button Mouse (PS/2)" ,
	     "geniusnm" : "Generic - 2 Button Mouse (PS/2)" ,
	     "geniusnmps/2" : "Genius - NetMouse (PS/2)" ,
	     "geniusnsps/2" : "Genius - NetScroll (PS/2)" ,
	     "thinking" : "" ,
	     "thinkingps/2" : "" ,
	     "logitech" : "Logitech - C7 Mouse (serial, old C7 type)" ,
	     "logitechcc" : "Logitech - CC Series (serial)" ,
	     "logibm" : "Logitech - Bus Mouse" ,
	     "logimman" : "Logitech - MouseMan/FirstMouse (serial)" ,
	     "logimmanps/2" : "Logitech - MouseMan/FirstMouse (PS/2)" ,
	     "logimman+" : "Logitech - MouseMan+/FirstMouse+ (serial)" ,
	     "logimman+ps/2" : "Logitech - MouseMan+/FirstMouse+ (PS/2)" ,
	     "microsoft" : "Microsoft - Compatible Mouse (serial)" ,
	     "msnew" : "Microsoft - Rev 2.1A or higher (serial)" ,
	     "msintelli" : "Microsoft - IntelliMouse (serial)" ,
	     "msintellips/2" : "Microsoft - IntelliMouse (PS/2)" ,
	     "msbm" : "Microsoft - Bus Mouse" ,
	     "mousesystems" : "Mouse Systems - Mouse (serial)" ,
	     "mmseries" : "MM - Series (serial)" ,
	     "mmhittab" : "MM - HitTablet (serial)" ,
	     "sun" : "Sun - Mouse"
	}

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
	    self.setMouseType(mouseToMouse[mouseType], device, emulThree)

        self.addToSkipList("mouse")

    def doReboot(self, args):
        self.addToSkipList("complete")

    def doSkipX(self, args):
        self.addToSkipList("xconfig")

    def readKickstart(self, file):
	handlers = { 
		     "auth"		: self.doAuthconfig	,
		     "authconfig"	: self.doAuthconfig	,
		     "cdrom"		: None			,
		     "clearpart"	: self.doClearPart	,
		     "device"		: None			,
		     "deviceprobe"	: None			,
		     "driverdisk"	: None			,
		     "harddrive"	: None			,
		     "install"		: self.doInstall	,
		     "keyboard"		: self.doKeyboard	,
		     "lang"		: self.doLang		,
		     "lilo"		: self.doLilo		,
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
	newSection = None
	for n in open(file).readlines():
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
		    else:
                        n = string.strip (n)
			packages.append(n)
		elif where == "commands":
		    if handlers[args[0]]:
			handlers[args[0]](args[1:])
		elif where == "pre" or where == "post":
		    script = script + n
		else:
		    raise SyntaxError, "I'm lost in kickstart"

	self.setGroups(groups)
	self.setPackages(packages)

        # test to see if they specified to clear partitions and also
        # tried to --onpart on a logical partition
        if iutil.getArch() == 'i386' and self.fstab:
            clear = self.getClearParts()
            if clear == FSEDIT_CLEAR_LINUX or clear == FSEDIT_CLEAR_ALL:
		for (mntpoint, (dev, fstype, reformat)) in self.fstab:
		    if int(dev[-1:]) > 4:
			raise RuntimeError, "Clearpart and --onpart on non-primary partition %s not allowed" % dev
                
	if where =="pre" or where == "post":
	    s = Script(script, scriptInterp, scriptChroot)
	    if where == "pre":
		self.preScripts.append(s)
	    else:
		self.postScripts.append(s)

    def doClearPart(self, args):
	if args[0] == '--linux':
	    clear = FSEDIT_CLEAR_LINUX
	elif args[0] == '--all':
	    clear = FSEDIT_CLEAR_ALL
	self.setClearParts(clear)

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

	self.addRaidEntry(mntPoint, raidDev, level, extra)

    def definePartition(self, args):
	# we just set up the desired partitions -- magic in our base class 
	# does the actual partitioning (no, you don't want to know the 
	# details)
	size = 0
	grow = 0
	maxSize = -1
	device = None
	onPart = None
        fsopts = None
        type = 0
        partNum = 0
        primOnly = 0
        active = 0
        format = 1
        
	(args, extra) = isys.getopt(args, '', [ 'size=', 'maxsize=', 
					'grow', 'onpart=', 'ondisk=',
                                        'bytes-per-inode=', 'usepart=',
                                        'onprimary=', 'active', 'type=',
                                        'asprimary', 'noformat'])

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

	if len(extra) != 1:
	    raise ValueError, "partition command requires one anonymous argument"

	if onPart:
           if extra[0] == 'swap':
               # handle swap filesystems correctly 
               self.addToFstab(extra[0], onPart, 'swap',1)
           else:
               if format == 0:
                   self.addToFstab(extra[0], onPart, reformat = 0)
               else:
                   self.addToFstab(extra[0], onPart, 'ext2', 1)
	else:
	    self.addNewPartition(extra[0], (size, maxSize, grow), (device, partNum, primOnly), (type, active), fsopts)

    def __init__(self, file, serial):
	BaseInstallClass.__init__(self)
	self.addToSkipList("bootdisk")
        self.addToSkipList("welcome")
        self.addToSkipList("package-selection")
        self.addToSkipList("confirm-install")
        self.addToSkipList("custom-upgrade")
        self.addToSkipList("network")
	self.setEarlySwapOn(1)
	self.partitions = []
	self.postScripts = []
	self.preScripts = []

	self.installType = "install"
	self.readKickstart(file)

	for script in self.preScripts:
	    script.run("/", serial)

def Kickstart(file, serial):

    f = open(file, "r")
    lines = f.readlines()
    f.close()

    customClass = None
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
