import isys
from installclass import InstallClass
from installclass import FSEDIT_CLEAR_LINUX
from installclass import FSEDIT_CLEAR_ALL
import sys

class Kickstart(InstallClass):

    def doRootPw(self, args):
	(args, extra) = isys.getopt(args, '', [ 'iscrypted=' ])

	isCrypted = 0
	for n in args:
	    (str, arg) = n
	    if (str == '--iscrypted'):
		isCrypted = 1

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

    def doInstall(self, args):
	self.installType = "install"

    def doUpgrade(self, args):
	self.installType = "upgrade"

    def doNetwork(self, args):
	(args, extra) = isys.getopt(args, '',
		[ 'bootproto', 'ip', 'netmask', 'gateway', 'nameserver' ])
	bootProto = "dhcp"
	ip = None
	netmask = None
	gateway = None
	nameserve = None
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

    def doZeroMbr(self, args):
	if args[0] == "yes":
	    self.setZeroMbr(1)

    def readKickstart(self, file):
	handlers = { 
		     "authconfig"	: self.doAuthconfig	,
		     "cdrom"		: None			,
		     "clearpart"	: self.doClearPart	,
		     "harddrive"	: None			,
		     "install"		: self.doInstall	,
		     "network"		: self.doNetwork	,
		     "lilo"		: self.doLilo		,
		     "network"		: None			,
		     "nfs"		: None			,
		     "part"		: self.definePartition	,
		     "rootpw"		: self.doRootPw		,
		     "text"		: None			,
		     "timezone"		: self.doTimezone	,
		     "upgrade"		: self.doUpgrade	,
		     "xdisplay"		: None			,
		     "zerombr"		: self.doZeroMbr	,
		   }

	for n in open(file).readlines():
	    n = n[:len(n) - 1]	    # chop

	    args = isys.parseArgv(n)
	    if not args or args[0][0] == '#': continue

	    cmd = args[0]
	    if handlers[cmd]: handlers[cmd](args[1:])

    def doClearPart(self, args):
	if args[0] == '--linux':
	    clear = FSEDIT_CLEAR_LINUX
	elif args[0] == '--all':
	    clear = FSEDIT_CLEAR_ALL
	self.setClearParts(clear)

    def definePartition(self, args):
	# we just set up the desired partitions -- magic in our base class 
	# does the actual partitioning (no, you don't want to know the 
	# details)
	size = 0
	grow = 0
	maxSize = 0

	(args, extra) = isys.getopt(args, '', [ 'size=', 'maxsize=', 
					'grow' ])

	for n in args:
	    (str, arg) = n
	    if str == '--size':
		size = int(arg)
	    elif str == '--maxsize':
		maxSize = int(arg)
	    elif str == '--grow':
		grow = 1

	self.partitions.append((extra[0], size, maxSize, grow))

        self.addToSkipList("partition")
        self.addToSkipList("format")

    def __init__(self, file):
	InstallClass.__init__(self)
	self.addToSkipList("bootdisk")
        self.addToSkipList("welcome")
	self.partitions = []

	self.installType = "install"
	self.readKickstart(file)

	self.setGroups(["Base"])
	self.addToSkipList("package-selection")

        # need to take care of:
	#[ "lilo", "mouse", "network", "complete",
	  #"package-selection", "bootdisk", "partition", "format",
	  #"dependencies", "language", "keyboard",
	  # "mouse" ].index(type)
