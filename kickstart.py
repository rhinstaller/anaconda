import isys
from installclass import InstallClass
import getopt
import sys

class Kickstart(InstallClass):

    def setRootPassword(self, args):
	InstallClass.setRootPassword(self, args[0])
	self.addToSkipList("accounts")

    def authconfig(self, args):
	(args, extra) = getopt.getopt(args, '',
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

    def setupLilo(self, args):
	(args, extra) = getopt.getopt(args, '',
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

    def setTimezone(self, args):
	(args, extra) = getopt.getopt(args, '',
		[ 'utc' ])

	isUtc = 0
	
	for n in args:
	    (str, arg) = n
	    if str == '--utc':
		isUtc = 1

	self.setTimezoneInfo(extra[0], asUtc = isUtc)

	self.addToSkipList("timezone")

    def readKickstart(self, file):
	handlers = { "nfs"		: None			,
		     "cdrom"		: None			,
		     "authconfig"	: self.authconfig	,
		     "network"		: None			,
		     "rootpw"		: self.setRootPassword	,
		     "timezone"		: self.setTimezone	,
		     "lilo"		: self.setupLilo	,
		   }

	for n in open(file).readlines():
	    n = n[:len(n) - 1]	    # chop

	    args = isys.parseArgv(n)
	    if not args or args[0][0] == '#': continue

	    cmd = args[0]
	    if handlers[cmd]: handlers[cmd](args[1:])
	    
    def __init__(self, file):
	InstallClass.__init__(self)
	self.addToSkipList("bootdisk")
        self.addToSkipList("welcome")

	self.readKickstart(file)
	self.installType = "install"

	self.setGroups(["Base"])
	self.addToSkipList("package-selection")

        # need to take care of:
	#[ "lilo", "mouse", "network", "complete",
	  #"package-selection", "bootdisk", "partition", "format",
	  #"dependencies", "language", "keyboard",
	  # "mouse" ].index(type)
