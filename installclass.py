# this is the prototypical class for workstation, server, and kickstart 
# installs
#
# The interface to InstallClass is *public* -- ISVs/OEMs can customize the
# install by creating a new derived type of this class.

class InstallClass:

    # look in mouse.py for a list of valid mouse names -- use the LONG names
    def setMouseType(self, name, device = None, emulateThreeButtons = 0):
	self.mouse = (name, device, emulateThreeButtons)

    def setLiloInformation(self, location, linear = 1, appendLine = None):
	# this throws an exception if there is a problem
	["mbr", "partition", "none"].index(location)

	self.lilo = (location, linear, appendLine)

    def getLiloInformation(self):
	return self.lilo

    def setTimezoneInfo(self, timezone, asUtc = 0, asArc = 0):
	self.timezone = (timezone, asUtc, asArc)

    def getTimezoneInfo(self):
	return self.timezone

    def addToSkipList(self, type):
	# this throws an exception if there is a problem
	[ "lilo", "mouse", "network", "authentication", "complete",
	  "package-selection", "bootdisk", "partition", "format",
	  "accounts", "dependencies", "language", "keyboard",
	  "welcome", "installtype", "mouse" ].index(type)
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

    def getMakeBootdisk(self):
	return self.makeBootdisk

    def __init__(self):
	self.skipSteps = {}
	self.hostname = None
	self.lilo = ("mbr", 0, "")
	self.groups = None
	self.makeBootdisk = 0
	self.timezone = None
	self.setAuthentication(1, 1, 0)

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
	self.addToSkipList("package-selection")
	self.addToSkipList("authentication")
	self.addToSkipList("bootdisk")

class GNOMEWorkstation(Workstation):

    def __init__(self):
	Workstation.__init__(self)
	self.setGroups(["Base"])

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

class Kickstart(InstallClass):
    def __init__(self):
	InstallClass.__init__(self)
	self.addToSkipList("lilo")
	self.addToSkipList("bootdisk")
        self.addToSkipList("installtype")
        self.addToSkipList("welcome")

        # need to take care of:
	#[ "lilo", "mouse", "network", "authentication", "complete",
	  #"package-selection", "bootdisk", "partition", "format",
	  #"accounts", "dependencies", "language", "keyboard",
	  #"installtype", "mouse" ].index(type)
