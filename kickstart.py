import isys
import os
from installclass import InstallClass
from installclass import FSEDIT_CLEAR_LINUX
from installclass import FSEDIT_CLEAR_ALL
import sys
import string

class Kickstart(InstallClass):

    def doRootPw(self, args):
	(args, extra) = isys.getopt(args, '', [ 'iscrypted' ])

	isCrypted = 0
	for n in args:
	    (str, arg) = n
	    if (str == '--iscrypted'):
		isCrypted = 1

	if len(extra) != 1:
	    raise ValueError, "a single argument is expected to rootPw"

	InstallClass.doRootPw(self, extra[0], isCrypted = isCrypted)
	self.addToSkipList("accounts")

    def doAuthconfig(self, args):
	(args, extra) = isys.getopt(args, '',
		[ 'enablenis', 'nisdomain=', 'nisserver=', 'useshadow',
		  'enablemd5' ])

	useNis = 0
	useShadow = 0
	useMd5 = 0
	nisServer = None
	nisDomain = None
	nisBroadcast = 0
	
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

	if useNis and not nisServer: nisBroadcast = 1
	    
	self.setAuthentication(useShadow, useMd5, useNis, nisDomain,
			       nisBroadcast, nisServer)
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
		  'startxonboot', 'noprobe' ])

	if extra:
	    raise ValueError, "unexpected arguments to xconfig command"

	server = None
	card = None
	monitor = None
	hsync = None
	vsync = None
        noProbe = 0
	startX = 0

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

	self.configureX(server, card, monitor, hsync, vsync, noProbe,
		        startX)
	self.addToSkipList("xconfig")

    def doInstall(self, args):
	self.installType = "install"

    def doUpgrade(self, args):
	self.installType = "upgrade"

    def doNetwork(self, args):
	# nodns is only used by the loader
	(args, extra) = isys.getopt(args, '',
		[ 'bootproto=', 'ip=', 'netmask=', 'gateway=', 'nameserver=',
		  'nodns'])
	bootProto = "dhcp"
	ip = None
	netmask = ""
	gateway = ""
	nameserver = ""
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
	self.setNetwork(bootProto, ip, netmask, gateway, nameserver)

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
	     "logimmanps/2" : "Logitech - MouseMan/FirstMouse (ps/2)" ,
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
		     "upgrade"		: self.doUpgrade	,
		     "xconfig"		: self.doXconfig	,
		     "xdisplay"		: None			,
		     "zerombr"		: self.doZeroMbr	,
		   }

	where = "commands"
	packages = []
	groups = []
	post = ""
	postInChroot = 1
	for n in open(file).readlines():
	    if where == "post":
		post = post + n
	    else:
		n = n[:len(n) - 1]	    # chop

		args = isys.parseArgv(n)
		if not args or args[0][0] == '#': continue

		if where == "commands":
		    cmd = args[0]
		    if cmd == "%packages":
			where = "packages"
		    elif handlers[cmd]: 
			handlers[cmd](args[1:])
		elif where == "packages":
		    if n[0:5] == "%post":
			args = isys.parseArgv(n)
			if len(args) >= 2 and args[1] == "--nochroot":
			    postInChroot = 0
			where = "post"
		    elif n[0] == '@':
			n = n[1:]
                        n = string.strip (n)
			groups.append(n)
		    else:
                        n = string.strip (n)
			packages.append(n)

	self.setGroups(groups)
	self.setPackages(packages)
	self.setPostScript(post, postInChroot)

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

	(args, extra) = isys.getopt(args, '', [ 'size=', 'maxsize=', 
					'grow', 'onpart=', 'ondisk=' ])

	for n in args:
	    (str, arg) = n
	    if str == '--size':
		size = int(arg)
	    elif str == '--maxsize':
		maxSize = int(arg)
	    elif str == '--grow':
		grow = 1
	    elif str == '--onpart':
		onPart = arg
	    elif str == '--ondisk':
		device = arg

	if len(extra) != 1:
	    raise ValueError, "partition command requires one anonymous argument"

	if onPart:
	    self.addToFstab(extra[0], onPart)
	else:
	    self.addNewPartition(extra[0], size, maxSize, grow, device)

    def __init__(self, file):
	InstallClass.__init__(self)
	self.addToSkipList("bootdisk")
        self.addToSkipList("welcome")
        self.addToSkipList("package-selection")
        self.addToSkipList("confirm-install")
        self.addToSkipList("custom-upgrade")
        self.addToSkipList("network")
	self.setEarlySwapOn(1)
	self.partitions = []

	self.installType = "install"
	self.readKickstart(file)

