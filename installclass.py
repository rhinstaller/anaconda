# this is the prototypical class for workstation, server, and kickstart 
# installs
#
# The interface to BaseInstallClass is *public* -- ISVs/OEMs can customize the
# install by creating a new derived type of this class.

# putting these here is a bit of a hack, but we can't switch between
# newtfsedit and gnomefsedit right now, so we have to put up with this
FSEDIT_CLEAR_LINUX  = (1 << 1)
FSEDIT_CLEAR_ALL    = (1 << 2)
FSEDIT_USE_EXISTING = (1 << 3)

import gettext_rh, os, iutil
import string
from xf86config import XF86Config
from translate import _

class BaseInstallClass:
    # default to not being hidden
    hidden = 0

    # look in mouse.py for a list of valid mouse names -- use the LONG names
    def setMouseType(self, name, device = None, emulateThreeButtons = 0):
	self.mouse = (name, device, emulateThreeButtons)

    def postAction(self, rootPath, serial):
	pass

    def setLiloInformation(self, location, linear = 1, appendLine = None):
	# this throws an exception if there is a problem
	["mbr", "partition", None].index(location)

	self.lilo = (location, linear, appendLine)

    def setClearParts(self, clear, warningText = None):
	self.clearParts = clear
        # XXX hack for install help text in GUI mode
        if clear == FSEDIT_CLEAR_LINUX:
            self.clearType = "wkst"
        if clear == FSEDIT_CLEAR_ALL:
            self.clearType = "svr"        
	self.clearPartText = warningText

    def getClearParts(self):
        return self.clearParts

    def getLiloInformation(self):
	return self.lilo

    def getFstab(self):
	return self.fstab

    def addRaidEntry(self, mntPoint, raidDev, level, devices):
	# throw an exception for bad raid levels
	[ 0, 1, 5 ].index(level)
	for device in devices:
	    found = 0

            for (otherMountPoint, sizespc, (devX, partX, primOnlyX), typespecX, fsoptsX) in self.partitions:
		if otherMountPoint == device:
		    found = 1
	    if not found:
		raise ValueError, "unknown raid device %s" % (device,)
	if mntPoint[0] != '/' and mntPoint != 'swap':
	    raise ValueError, "bad raid mount point %s" % (mntPoint,)
	if raidDev[0:2] != "md":
	    raise ValueError, "bad raid device point %s" % (raidDev,)
	if level == 5 and len(devices) < 3:
	    raise ValueError, "raid 5 arrays require at least 3 devices"
	if len(devices) < 2:
	    raise ValueError, "raid arrays require at least 2 devices"

	self.raidList.append(mntPoint, raidDev, level, devices)	

    def addNewPartition(self, mntPoint, sizespec, locspec, typespec, fsopts=None):
        (device, part, primOnly) = locspec
        
	if not device:
            device = ""
        
	if mntPoint[0] != '/' and mntPoint != 'swap' and \
		mntPoint[0:5] != "raid.":
	    raise TypeError, "bad mount point for partitioning: %s" % \
		    (mntPoint,)

	self.partitions.append((mntPoint, sizespec, (device, part, primOnly),typespec, fsopts))

    def addToFstab(self, mntpoint, dev, fstype = "ext2" , reformat = 1):
	self.fstab.append((mntpoint, (dev, fstype, reformat)))

    def setTimezoneInfo(self, timezone, asUtc = 0, asArc = 0):
	self.timezone = (timezone, asUtc, asArc)

    def getTimezoneInfo(self):
	return self.timezone

    def removeFromSkipList(self, type):
	if self.skipSteps.has_key(type):
	    del self.skipSteps[type]

    def addToSkipList(self, type):
	# this throws an exception if there is a problem
	[ "lilo", "mouse", "network", "authentication", "complete", "complete",
	  "package-selection", "bootdisk", "partition", "format", "timezone",
	  "accounts", "dependencies", "language", "keyboard", "xconfig",
	  "welcome", "custom-upgrade", "installtype", "mouse", 
	  "confirm-install" ].index(type)
	self.skipSteps[type] = 1

    def setHostname(self, hostname):
	self.hostname = hostname

    def getHostname(self):
	return self.hostname

    def setAuthentication(self, useShadow, useMd5,
                          useNIS = 0, nisDomain = "",  nisBroadcast = 0,
                          nisServer = "",
                          useLdap = 0, useLdapauth = 0, ldapServer = "",
                          ldapBasedn = "",
                          useKrb5 = 0, krb5Realm = "", krb5Kdc = "",
                          krb5Admin = "",
                          useHesiod = 0, hesiodLhs = "", hesiodRhs = ""):
        
	self.auth = ( useShadow, useMd5,
                      useNIS, nisDomain, nisBroadcast, nisServer,
                      useLdap, useLdapauth, ldapServer, ldapBasedn,
                      useKrb5, krb5Realm, krb5Kdc, krb5Admin,
                      useHesiod, hesiodLhs, hesiodRhs)

    def getAuthentication(self):
	return self.auth

    def skipStep(self, step):
	return self.skipSteps.has_key(step)

    def configureX(self, server, card, monitor, hsync, vsync, noProbe, startX):
	self.x = XF86Config(mouse = None)
	if (not noProbe):
	    self.x.probe()

	if not self.x.server:
            if (card != None):
                self.x.setVidcardByName (card)
            elif (server != None):
                self.x.setVidcardByServer (server)
            else:
                raise RuntimeError, "Could not probe video card and no fallback specified."
                

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
        hash = {}
        for package in packages:
            hash[package] = None
	self.packages = hash.keys()

    def getPackages(self):
	return self.packages

    def doRootPw(self, pw, isCrypted = 0):
	self.rootPassword = pw
	self.rootPasswordCrypted = isCrypted

    def getMakeBootdisk(self):
	return self.makeBootdisk

    def setMakeBootdisk(self, state):
	self.makeBootdisk = state 

    def setNetwork(self, bootproto, ip, netmask, gateway, nameserver,
		   device = None):
	self.bootProto = bootproto
	self.ip = ip
	self.netmask = netmask
	self.gateway = gateway
	self.nameserver = nameserver
	self.networkDevice = device

    def setZeroMbr(self, state):
	self.zeroMbr = state

    def getNetwork(self):
	return (self.bootProto, self.ip, self.netmask, self.gateway, 
		self.nameserver, self.networkDevice)

    def setEarlySwapOn(self, state = 0):
	self.earlySwapOn = state

    def setLanguage(self, lang):
	self.language = lang

    def setKeyboard(self, kb):
	self.keyboard = kb

    def setDesktop(self, desktop):
        self.desktop = desktop

    def getDesktop(self):
        return self.desktop

    def __init__(self):
	self.skipSteps = {}
	self.hostname = None
	self.lilo = ("mbr", 1, "")
	self.groups = None
	self.packages = None
	self.makeBootdisk = 0
	self.timezone = None
	self.setAuthentication(1, 1, 0)
	self.rootPassword = None
	self.rootPasswordCrypted = 0
	self.installType = None
	self.bootProto = None
	self.ip = ""
	self.networkDevice = None
	self.netmask = ""
	self.gateway = ""
	self.nameserver = ""
	self.partitions = []
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
	self.fstab = []
	self.earlySwapOn = 0
        self.desktop = ""
	self.raidList = []
        self.name = ""
        self.pixmap = ""
        self.showgroups = None

        if iutil.getArch () == "alpha":
            self.addToSkipList("bootdisk")
            self.addToSkipList("lilo")
        elif iutil.getArch () == "ia64":
            self.addToSkipList("bootdisk")
            self.addToSkipList("lilo")

# we need to be able to differentiate between this and custom
class DefaultInstall(BaseInstallClass):

    def __init__(self, expert):
	BaseInstallClass.__init__(self)

# reconfig machine w/o reinstall
class ReconfigStation(BaseInstallClass):

    def __init__(self, expert):
	BaseInstallClass.__init__(self)
	self.setHostname("localhost.localdomain")
	self.addToSkipList("lilo")
	self.addToSkipList("bootdisk")
	self.addToSkipList("partition")
	self.addToSkipList("package-selection")
	self.addToSkipList("format")
        self.addToSkipList("mouse")
        self.addToSkipList("xconfig")

allClasses = []
allClasses_hidden = []

# returns ( className, classObject, classLogo ) tuples
def availableClasses(showHidden=0):
    global allClasses
    global allClasses_hidden

    if not showHidden:
        if allClasses: return allClasses
    else:
        if allClasses_hidden: return allClasses_hidden

    if os.access("installclasses", os.R_OK):
	path = "installclasses"
    else:
	path = "/usr/lib/anaconda/installclasses"

    files = os.listdir(path)
    done = {}
    list = []
    for file in files:
	if file[0] == '.': continue
        if len (file) < 4:
	    continue
	if file[-3:] != ".py" and file[-4:-1] != ".py":
	    continue
	mainName = string.split(file, ".")[0]
	if done.has_key(mainName): continue
	done[mainName] = 1

	obj = None
	name = None
	cmd = "import %s\nif %s.__dict__.has_key('InstallClass'): obj = %s.InstallClass\n" % (mainName, mainName, mainName)
	exec(cmd)
	if obj: 
	    if obj.__dict__.has_key('sortPriority'):
		sortOrder = obj.sortPriority
	    else:
		sortOrder = 0
                
            if obj.hidden == 0 or showHidden == 1:
                list.append(((obj.name, obj, obj.pixmap), sortOrder))

    list.sort(ordering)
    for (item, priority) in list:
        if showHidden:
            allClasses_hidden.append(item)
        else:
            allClasses.append(item)

    if showHidden:
        return allClasses_hidden
    else:
        return allClasses

def ordering(first, second):
    ((name1, obj, logo), priority1) = first
    ((name2, obj, logo), priority2) = second

    if priority1 < priority2:
	return -1
    elif priority1 > priority2:
	return 1

    if name1 < name2:
	return -1
    elif name1 > name2:
	return 1

    return 0


def requireDisplayMode():
    return None
