# this is the prototypical class for workstation, server, and kickstart 
# installs
#
# The interface to InstallClass is *public* -- ISVs/OEMs can customize the
# install by creating a new derived type of this class.

FSEDIT_CLEAR_LINUX  = (1 << 0)
FSEDIT_CLEAR_ALL    = (1 << 2)
FSEDIT_USE_EXISTING = (1 << 3)

class InstallClass:

    # ummm, HACK
    def finishPartitioning(self, ddruid):
	if not self.partitions: return

	attempt = []
	swapCount = 0

	for (mntpoint, size, maxsize, grow) in self.partitions:
	    type = 0x83
	    if (mntpoint == "swap"):
		mntpoint = "Swap%04d-auto" % swapCount
		swapCount = swapCount + 1
		type = 0x82

	    attempt.append((mntpoint, size, type, grow, -1))

	try:
	    ddruid.attempt (attempt, "Junk Argument", self.createParts)
	    return 1
	except:
	    # life's a female dog <shrug> -- we should log something though
	    # <double-shrug>
	    self.skipPartitioning = 0
	    pass

	return 0

    # look in mouse.py for a list of valid mouse names -- use the LONG names
    def setMouseType(self, name, device = None, emulateThreeButtons = 0):
	self.mouse = (name, device, emulateThreeButtons)

    def setLiloInformation(self, location, linear = 1, appendLine = None):
	# this throws an exception if there is a problem
	["mbr", "partition", "none"].index(location)

	self.lilo = (location, linear, appendLine)

    def setClearPart(self, clear):
	self.clearPart = clear

    def getLiloInformation(self):
	return self.lilo

    def setTimezoneInfo(self, timezone, asUtc = 0, asArc = 0):
	self.timezone = (timezone, asUtc, asArc)

    def getTimezoneInfo(self):
	return self.timezone

    def addToSkipList(self, type):
	# this throws an exception if there is a problem
	[ "lilo", "mouse", "network", "authentication", "complete",
	  "package-selection", "bootdisk", "partition", "format", "timezone",
	  "accounts", "dependencies", "language", "keyboard",
	  "welcome", "installtype", "mouse" ].index(type)
	if type == "partition":
	    self.skipPartitioning = 1
	else:
	    self.skipSteps[type] = 1

    def setHostname(self, hostname):
	self.hostname = hostname

    def getHostname(self):
	return self.hostname

    def setAuthentication(self, useShadow, useMd5, useNIS = 0, nisDomain = "",
			  nisBroadcast = 0, nisServer = ""):
	self.auth = ( useShadow, useMd5, useNIS, nisDomain, nisBroadcast,
		      nisServer)

    def getAuthentication(self):
	return self.auth

    def skipStep(self, step):
	return self.skipSteps.has_key(step)

    # Groups is a list of group names -- the full list can be found in 
    # ths comps file for each release
    def setGroups(self, groups):
	self.groups = groups

    def getGroups(self):
	return self.groups

    def doRootPw(self, pw, isCrypted = 0):
	self.rootPassword = pw

    def getMakeBootdisk(self):
	return self.makeBootdisk

    def setNetwork(self, bootproto, ip, netmask, gateway, nameserver):
	self.bootProto = bootproto
	self.ip = ip
	self.netmask = netmask
	self.gateway = gateway
	self.nameserver = nameserver

    def getNetwork(self):
	return (self.bootProto, self.ip, self.netmask, self.gateway, 
		self.nameserver)

    def __init__(self):
	self.skipSteps = {}
	self.hostname = None
	self.lilo = ("mbr", 0, "")
	self.groups = None
	self.makeBootdisk = 0
	self.timezone = None
	self.setAuthentication(1, 1, 0)
	self.rootPassword = None
	self.installType = None
	self.bootProto = None
	self.ip = ""
	self.netmask = ""
	self.gateway = ""
	self.nameserver = ""
	self.partitions = []
	self.skipPartitioning = 0
	self.clearPart = 0

# custom installs are easy :-)
class CustomInstall(InstallClass):

    def __init__(self):
	InstallClass.__init__(self)

# GNOME and KDE installs are derived from this
class Workstation(InstallClass):

    def __init__(self):
	InstallClass.__init__(self)
	self.setHostname("localhost.localdomain")
	self.addToSkipList("lilo")
	self.addToSkipList("network")
	self.addToSkipList("authentication")
	self.addToSkipList("bootdisk")

class GNOMEWorkstation(Workstation):

    def __init__(self):
	Workstation.__init__(self)
	self.setGroups(["Base"])
	self.addToSkipList("package-selection")

class KDEWorkstation(Workstation):

    def __init__(self):
	Workstation.__init__(self)
	self.setGroups(["Base"])

class Server(InstallClass):

    def __init__(self):
	InstallClass.__init__(self)
	self.setHostname("localhost.localdomain")
	self.addToSkipList("lilo")
	self.addToSkipList("network")
	self.addToSkipList("package-selection")
	self.addToSkipList("authentication")
	self.addToSkipList("bootdisk")

