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

    def addToSkipList(self, type):
	# this throws an exception if there is a problem
	[ "lilo", "mouse", "hostname", "network", "authentication", "complete",
	  "package-selection", "bootdisk", "install-pause" ].index(type)
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
	self.lilo = None
	self.groups = None
	self.makeBootdisk = 0
	self.setAuthentication(1, 1, 0)

# custom installs are easy :-)
class CustomInstall(InstallClass):

    def __init__(self):
	InstallClass.__init__(self)

# GNOME and KDE installs are derived from this
class Workstation(InstallClass):

    def __init__(self):
	InstallClass.__init__(self)
	self.setLiloInformation("mbr")
	self.setHostname("localhost.localdomain")
	self.setGroups(["Workstation"])
	self.addToSkipList("lilo")
	self.addToSkipList("hostname")
	self.addToSkipList("network")
	self.addToSkipList("package-selection")
	self.addToSkipList("authentication")
	self.addToSkipList("bootdisk")
