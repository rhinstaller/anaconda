# this is the prototypical class for workstation, server, and kickstart 
# installs
#
# The interface to BaseInstallClass is *public* -- ISVs/OEMs can customize the
# install by creating a new derived type of this class.
#
# Copyright 1999-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os, iutil
import string
import language

from instdata import InstallData
from partitioning import *

from rhpl.log import log
from rhpl.translate import _, N_

from constants import BETANAG

class BaseInstallClass:
    # default to not being hidden
    hidden = 0
    pixmap = None
    showMinimal = 0
    showLoginChoice = 0
    description = None
    
    # don't select this class by default
    default = 0

    # don't force text mode
    forceTextMode = 0

    # by default, place this under the "install" category; it gets it's
    # own toplevel category otherwise
    parentClass = ( _("Install on System"), "install.png" )

    # we can use a different install data class
    installDataClass = InstallData

    def postAction(self, rootPath, serial):
	pass

    def setBootloader(self, id, useLilo=0, location=None, linear=1,
                      forceLBA=0, password=None, md5pass=None,
                      appendLine=""):
        if useLilo:
            id.bootloader.useGrubVal = 0
        if appendLine:
            id.bootloader.args.set(appendLine)
        id.bootloader.setForceLBA(forceLBA)
        id.bootloader.useLinear = linear
        if password:
            id.bootloader.setPassword(password, isCrypted = 0)
        if md5pass:
            id.bootloader.setPassword(md5pass)
        if location != None:
            id.bootloader.defaultDevice = location
        else:
            id.bootloader.defaultDevice = -1
        
    def setClearParts(self, id, clear, drives = None, warningText = None,
                      initAll = 0):
	id.partitions.autoClearPartType = clear
        id.partitions.autoClearPartDrives = drives
        if initAll:
            id.partitions.reinitializeDisks = initAll
        # XXX hack for install help text in GUI mode
        if clear == CLEARPART_TYPE_LINUX:
            self.clearType = "wkst"
        if clear == CLEARPART_TYPE_ALL:
            self.clearType = "svr"
	self.clearPartText = warningText

    def setSteps(self, dispatch):
	dispatch.setStepList(
		 "language",
		 "keyboard",
		 "mouse",
		 "welcome",
                 "findrootparts",
		 "betanag",
		 "installtype",
                 "partitionmethod",
                 "partitionobjinit",
                 "partitionmethodsetup",
                 "autopartition",
                 "autopartitionexecute",
                 "fdisk",
                 "fdasd",
                 "partition",
		 "partitiondone",
		 "bootloadersetup",                 
		 "bootloader",
                 "networkdevicecheck",
		 "network",
		 "firewall",
		 "languagesupport",
		 "timezone",
		 "accounts",
		 "authentication",
		 "readcomps",
                 "selectlangpackages",
		 "package-selection",
                 "handleX11pkgs",
		 "checkdeps",
		 "dependencies",
		 "videocard",
		 "monitor",
		 "xcustom",
		 "confirminstall",
		 "install",
		 "enablefilesystems",
                 "migratefilesystems",
                 "setuptime",
                 "preinstallconfig",
		 "installpackages",
                 "postinstallconfig",
		 "writeconfig",
                 "firstboot",
		 "instbootloader",
                 "dopostaction",
		 "writexconfig",
		 "writeksconfig",
		 "bootdisk",
                 "methodcomplete",
		 "complete"
		)

	if not BETANAG:
	    dispatch.skipStep("betanag")

        # XXX ugh, this badly needs some clean up
        if (iutil.getArch() == "alpha" or iutil.getArch() == "ia64" or
            iutil.getArch() == "sparc" or iutil.getArch() == "ppc"):
	    dispatch.skipStep("bootdisk")
            dispatch.skipStep("bootloader")
            dispatch.skipStep("fdasd", permanent = 1)
	elif iutil.getArch() == "s390":
	    dispatch.skipStep("keyboard", permanent = 1)
	    dispatch.skipStep("mouse", permanent = 1)
	    dispatch.skipStep("partitionmethod", permanent = 1)
	    dispatch.skipStep("autopartition", permanent = 1)
	    dispatch.skipStep("autopartitionexecute", permanent = 1)
	    dispatch.skipStep("fdisk", permanent = 1)
	    dispatch.skipStep("handleX11pkgs", permanent = 1)
	    dispatch.skipStep("videocard", permanent = 1)
	    dispatch.skipStep("monitor", permanent = 1)
	    dispatch.skipStep("xcustom", permanent = 1)
	    dispatch.skipStep("writexconfig", permanent = 1)
	    dispatch.skipStep("bootdisk", permanent = 1)
	else:
	    dispatch.skipStep("fdasd", permanent = 1)

    # This is called after the hdlist is read in.
    def setPackageSelection(self, hdlist):
	pass

    # This is called after the comps is read in (after setPackageSelection()).
    # It can both select groups, change the default selection for groups, and
    # change which groups are hidden.
    def setGroupSelection(self, comps):
	pass

    # this is a utility function designed to be called from setGroupSelection()
    # it hides all of the groups not in the "groups" list
    def showGroups(self, comps, groups):
	groupSet = {}

	for group in groups:
	    if type(group) == type("a"):
		groupSet[group] = None
	    else:
		(group, val) = group
		groupSet[group] = val
	    
	for comp in comps:
	    if groupSet.has_key(comp.name):
		comp.hidden = 0

		# do nothing if groupSet[comp.name] == None
		if groupSet[comp.name] == 1:
		    comp.select()
		elif groupSet[comp.name] == 0:
		    comp.unselect(0)
	    else:
		comp.hidden = 1

    def getMakeBootdisk(self):
	return self.makeBootdisk

    def setMakeBootdisk(self, state):
	self.makeBootdisk = state 

    def setZeroMbr(self, id, zeroMbr):
        id.partitions.zeroMbr = zeroMbr

    def setEarlySwapOn(self, state = 0):
	self.earlySwapOn = state

    def setKeyboard(self, id, kb):
	id.keyboard.set(kb)

        # activate the keyboard changes
#        id.keyboard.activate()

	# XXX
        #apply (todo.x.setKeyboard, xkb)

	## hack - apply to instclass preset if present as well
	#if (todo.instClass.x):
	#apply (todo.instClass.x.setKeyboard, xkb)

    def setHostname(self, id, hostname):
	id.network.setHostname(hostname);

    def setNameserver(self, id, nameserver):
        id.network.setDNS(nameserver)

    def setGateway(self, id, gateway):
        id.network.setGateway(gateway)

    def setTimezoneInfo(self, id, timezone, asUtc = 0, asArc = 0):
	id.timezone.setTimezoneInfo(timezone, asUtc, asArc)

    def setRootPassword(self, id, pw, isCrypted = 0):
	id.rootPassword.set(pw, isCrypted)

    def setAuthentication(self, id, useShadow, useMd5,
                          useNIS = 0, nisDomain = "",  nisBroadcast = 0,
                          nisServer = "",
                          useLdap = 0, useLdapauth = 0, ldapServer = "",
                          ldapBasedn = "", useldapTls = 0,
                          useKrb5 = 0, krb5Realm = "", krb5Kdc = "",
                          krb5Admin = "",
                          useHesiod = 0, hesiodLhs = "", hesiodRhs = "",
                          useSamba = 0, sambaServer= "", sambaWorkgroup = "",
                          enableCache = 0):

        id.auth.useShadow = useShadow
        id.auth.useMD5 = useMd5

        id.auth.useNIS = useNIS
        id.auth.nisDomain = nisDomain
        id.auth.nisuseBroadcast = nisBroadcast
        id.auth.nisServer = nisServer

        id.auth.useLdap = useLdap
        id.auth.useLdapauth = useLdapauth
        id.auth.ldapServer = ldapServer
        id.auth.ldapBasedn = ldapBasedn
        id.auth.ldapTLS = useldapTls

        id.auth.useKrb5 = useKrb5
        id.auth.krb5Realm = krb5Realm
        id.auth.krb5Kdc = krb5Kdc
        id.auth.krb5Admin = krb5Admin

        id.auth.useHesiod = useHesiod
        id.auth.hesiodLhs = hesiodLhs
        id.auth.hesiodRhs = hesiodRhs

        id.auth.useSamba = useSamba
        id.auth.sambaServer = sambaServer
        id.auth.sambaWorkgroup = sambaWorkgroup

        id.auth.enableCache = enableCache

    def setNetwork(self, id, bootProto, ip, netmask, device = None):
	if bootProto:
	    devices = id.network.available ()
	    if (devices and bootProto):
		if not device:
		    list = devices.keys ()
		    list.sort()
		    device = list[0]
		dev = devices[device]
                dev.set (("bootproto", bootProto))
                dev.set (("onboot", "yes"))
                if bootProto == "static":
                    if (ip):
                        dev.set (("ipaddr", ip))
                    if (netmask):
                        dev.set (("netmask", netmask))

    def setLanguageSupport(self, id, langlist):
	if len (langlist) == 0:
	    id.langSupport.setSupported(id.langSupport.getAllSupported())
	else:
	    newlist = []
	    for lang in langlist:
		newlist.append(id.langSupport.getLangNameByNick(lang))

            default = id.langSupport.getDefault()
            if default not in newlist:
                newlist.append(default)
                
	    id.langSupport.setSupported(newlist)

    def setLanguageDefault(self, id, default):
	id.langSupport.setDefault(id.langSupport.getLangNameByNick(default))

    def setLanguage(self, id, lang):
	instLangName = id.instLanguage.getLangNameByNick(lang)
	id.instLanguage.setRuntimeLanguage(instLangName)

    def setDesktop(self, id, desktop):
	id.desktop.setDefaultDesktop (desktop)

    def setFirewall(self, id, enable = -1, policy = 1, trusts = [], ports = "",
		    dhcp = 0, ssh = 0, telnet = 0, smtp = 0, http = 0,
		    ftp = 0):
	id.firewall.enabled = enable
	id.firewall.policy = policy
	id.firewall.trustdevs = trusts
	id.firewall.portlist = ports
	id.firewall.dhcp = dhcp
	id.firewall.ssh = ssh
	id.firewall.telnet = telnet
	id.firewall.smtp = smtp
	id.firewall.http = http
	id.firewall.ftp = ftp


    def configureX(self, id, server = None, card = None, videoRam = None, monitorName = None, hsync = None, vsync = None, resolution = None, depth = None, noProbe = 0, startX = 0):
        import rhpl.videocard as videocard
        import rhpl.monitor as monitor
	import rhpl.xhwstate as xhwstate
	import xsetup

        # XXX they could have sensitive hardware, but we need this info =\
        videohw = videocard.VideoCardInfo()
        if videohw:
            id.setVideoCard(videohw)
            
        if (not noProbe):
            monitorhw = monitor.MonitorInfo()

            if monitorhw:
                id.setMonitor(monitorhw)

        if id.videocard and not id.videocard.primaryCard().getXServer():
            if (card != None):
                vc = id.videocard.locateVidcardByName(card)
            elif (server != None):
                vc = id.videocard.locateVidcardByServer(server)
            else:
                raise RuntimeError, "Could not probe video card and no fallback specified"
            id.videocard.setVidcard(vc)

	tmpram = None
	if videoRam != None:
	    if type(videoRam) == type(1024):
		tmpram = videoRam
	    else:
		tmpram = string.atoi(videoRam)
	    
        if tmpram in id.videocard.possible_ram_sizes():
            id.videocard.primaryCard().setVideoRam(str(tmpram))

        if id.monitor.getMonitorID() != "Unprobed Monitor":
	    usemon = id.monitor.getMonitorName()
        elif monitorName:
            usemon = monitorName
        else:
            usemon = None

        setmonitor = 0
        if usemon:
            try:
                (model, eisa, vert, horiz) = id.monitor.lookupMonitorByName(usemon)
		if id.monitor.getMonitorID() != "DDCPROBED":
		    useid = model
		else:
		    useid = "DDCPROBED"
		    
                id.monitor.setSpecs(horiz, vert, id=useid, name=model)
                setmonitor = 1
            except:
                log("Couldnt lookup monitor type %s." % usemon)
                pass

        if not setmonitor and hsync and vsync:
            id.monitor.setSpecs(hsync, vsync)
            setmonitor = 1

        if not setmonitor:
             # fall back to standard VGA
             log("Could not probe monitor, and no fallback specified.")
             log("Falling back to Generic VGA monitor")

             try:
                 id.monitor.setSpecs("31.5-37.9", "50.0-61.0")
             except:
                 raise RuntimeError, "Could not probe monitor and fallback failed."
             
        if startX:
            id.desktop.setDefaultRunLevel(5)
        else:
            id.desktop.setDefaultRunLevel(3)

        xcfg = xhwstate.XF86HardwareState(defcard=id.videocard, defmon=id.monitor)
	availableDepths = xcfg.available_color_depths()

        if resolution and depth:
	    if depth not in availableDepths:
                raise RuntimeError, "Invalid depth specified"
            # XXX should we fallback to our "best possible" here?

	    xcfg.set_colordepth(depth)
	    availableRes = xcfg.available_resolutions()
	    
	    if resolution not in availableRes:
                 fbres = availableRes[-1]
                 log("Resolution requested %s is not supported.",resolution)
		 log("Falling back to %s.", fbres)
		 log("To avoid this you may need to specify the videocard and ")
		 log("monitor specs on the xconfig ks directive if they were ")
		 log("not probed correctly.")
		 resolution = fbres
		 
	    xcfg.set_resolution(resolution)
        else:
	    # pick something sane
	    xcfg.choose_sane_default()

	xsetup = xsetup.XSetup(xcfg)
        id.setXSetup(xsetup)


    def setMouse(self, id, mouseType, device = None, emulThree = -1):
        import rhpl.mouse as mouse

        # blindly trust what we're told
        mouse = mouse.Mouse(skipProbe = 1)
        mouseName = mouse.mouseToMouse()[mouseType]
        mouse.set(mouseName, emulThree, device)
        id.setMouse(mouse)
    

    def setInstallData(self, id):
	id.reset()
	id.instClass = self

	# Classes should call these on __init__ to set up install data
	#id.setKeyboard()
	#id.setLanguage()
	#id.setNetwork()
	#id.setFirewall()
	#id.setLanguageSupport()
	#id.setLanguageDefault()
	#id.setTimezone()
	#id.setRootPassword()
	#id.setAuthentication()
	#id.setHostname()
	#id.setDesktop()
	#id.setMouse()

	# These are callbacks used to let classes configure packages
	#id.setPackageSelection()
	#id.setGroupSelection()

    def __init__(self, expert):
	pass

# we need to be able to differentiate between this and custom
class DefaultInstall(BaseInstallClass):
    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

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
	cmd = "import %s\nif %s.__dict__.has_key('InstallClass'): obj = %s.InstallClass\n" % (mainName, mainName, mainName)
	exec(cmd)

	if obj:
	    if obj.__dict__.has_key('sortPriority'):
		sortOrder = obj.sortPriority
	    else:
		sortOrder = 0

	    if obj.__dict__.has_key('arch'):
                if obj.arch != iutil.getArch ():
                    obj.hidden = 1
                
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
