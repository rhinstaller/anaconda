# this is the prototypical class for workstation, server, and kickstart 
# installs
#
# The interface to InstallClass is *public* -- ISVs/OEMs can customize the
# install by creating a new derived type of this class.

# putting these here is a bit of a hack, but we can't switch between
# newtfsedit and gnomefsedit right now, so we have to put up with this
FSEDIT_CLEAR_LINUX  = (1 << 1)
FSEDIT_CLEAR_ALL    = (1 << 2)
FSEDIT_USE_EXISTING = (1 << 3)

import gettext
from xf86config import XF86Config

cat = gettext.Catalog ("anaconda", "/usr/share/locale")
_ = cat.gettext

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
	    ddruid.attempt (attempt, "Junk Argument", self.clearParts)
	    return 1
	except:
	    # life's a female dog <shrug> -- we should log something though
	    # <double-shrug>
	    self.skipPartitioning = 0
	    self.clearPartText = None
	    pass

	return 0

    # look in mouse.py for a list of valid mouse names -- use the LONG names
    def setMouseType(self, name, device = None, emulateThreeButtons = 0):
	self.mouse = (name, device, emulateThreeButtons)

    def setLiloInformation(self, location, linear = 1, appendLine = None):
	# this throws an exception if there is a problem
	["mbr", "partition", "none"].index(location)

	self.lilo = (location, linear, appendLine)

    def setClearParts(self, clear, warningText = None):
	self.clearParts = clear
        # XXX hack for install help text in GUI mode
        if clear == FSEDIT_CLEAR_LINUX:
            self.clearType = "wkst"
        if clear == FSEDIT_CLEAR_ALL:
            self.clearType = "svr"        
	self.clearPartText = warningText

    def getLiloInformation(self):
	return self.lilo

    def setTimezoneInfo(self, timezone, asUtc = 0, asArc = 0):
	self.timezone = (timezone, asUtc, asArc)

    def getTimezoneInfo(self):
	return self.timezone

    def removeFromSkipList(self, type):
	if type == "partition":
	    self.skipPartitioning = 0
	    self.removeFromSkipList("format")
	else:
	    if self.skipSteps.has_key(type):
		del self.skipSteps[type]

    def addToSkipList(self, type):
	# this throws an exception if there is a problem
	[ "lilo", "mouse", "network", "authentication", "complete", "complete",
	  "package-selection", "bootdisk", "partition", "format", "timezone",
	  "accounts", "dependencies", "language", "keyboard", "xconfig",
	  "welcome", "installtype", "mouse", "confirm-install" ].index(type)
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

    def configureX(self, server, card, monitor, hsync, vsync, noProbe, startX):
	self.x = XF86Config(mouse = None)
	if (not noProbe):
	    self.x.probe()

	if not self.x.server:
	    self.x.setVidcard (card)

	if not self.x.monID and monitor:
	    self.x.setMonitor((monitor, (None, None)))
	elif hsync and vsync:
	    self.x.setMonitor((None, (hsync, vsync)))

	if startX:
	    self.defaultRunlevel = 5

    # Groups is a list of group names -- the full list can be found in 
    # ths comps file for each release
    def setGroups(self, groups):
	self.groups = groups

    def getGroups(self):
	return self.groups

    # This is a list of packages -- it is combined with the group list
    def setPackages(self, packages):
	self.packages = packages

    def getPackages(self):
	return self.packages

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

    def setZeroMbr(self, state):
	self.zeroMbr = state

    def getNetwork(self):
	return (self.bootProto, self.ip, self.netmask, self.gateway, 
		self.nameserver)

    def setLanguage(self, lang):
	self.language = lang

    def setKeyboard(self, kb):
	self.keyboard = kb

    def setPostScript(self, postScript, inChroot = 1):
	self.postScript = postScript
	self.postInChroot = inChroot

    def __init__(self):
	self.skipSteps = {}
	self.hostname = None
	self.lilo = ("mbr", 0, "")
	self.groups = None
	self.packages = None
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
	self.clearParts = 0
        self.clearType = None
	self.clearText = None
	self.clearPartText = None
	self.zeroMbr = 0
	self.language = None
	self.keyboard = None
	self.mouse = None
	self.x = None
	self.defaultRunlevel = None
	self.postScript = None
	self.postInChroot = 0

# we need to be able to differentiate between this and custom
class DefaultInstall(InstallClass):

    def __init__(self):
	InstallClass.__init__(self)

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
	self.addToSkipList("partition")
	self.addToSkipList("package-selection")
	self.addToSkipList("format")

	self.partitions.append(('/boot', 16, 16, 0))
	self.partitions.append(('/', 500, 500, 1))
	self.partitions.append(('swap', 64, 64, 0))
	self.setClearParts(FSEDIT_CLEAR_LINUX, 
	    warningText = _("You are about to erase any preexisting Linux "
			    "installations on your system."))

class GNOMEWorkstation(Workstation):

    def __init__(self):
	Workstation.__init__(self)
	self.setGroups(["GNOME Workstation"])
	self.addToSkipList("package-selection")

class KDEWorkstation(Workstation):

    def __init__(self):
	Workstation.__init__(self)
	self.setGroups(["KDE Workstation"])

class Server(InstallClass):

    def __init__(self):
	InstallClass.__init__(self)
	self.setHostname("localhost.localdomain")
	self.addToSkipList("lilo")
	self.addToSkipList("network")
	self.addToSkipList("package-selection")
	self.addToSkipList("authentication")
	self.addToSkipList("bootdisk")
	self.addToSkipList("partition")
	self.addToSkipList("format")

	self.partitions.append(('/boot', 16, 16, 0))
	self.partitions.append(('/', 256, 256, 0))
	self.partitions.append(('/usr', 512, 512, 1))
	self.partitions.append(('/var', 256, 256, 0))
	self.partitions.append(('/home', 512, 512, 1))
	self.partitions.append(('swap', 64, 64, 1))
	self.setClearParts(FSEDIT_CLEAR_ALL, 
	    warningText = _("You are about to erase ALL DATA on your hard " + \
			    "drive to make room for your Linux installation."))
