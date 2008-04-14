# this is the prototypical class for workstation, server, and kickstart 
# installs
#
# The interface to BaseInstallClass is *public* -- ISVs/OEMs can customize the
# install by creating a new derived type of this class.
#
# Copyright 1999-2007 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os, sys, iutil
import string
import language

from instdata import InstallData
from partitioning import *
from autopart import getAutopartitionBoot, autoCreatePartitionRequests, autoCreateLVMPartitionRequests

from rhpl.log import log
from rhpl.translate import _, N_

from constants import BETANAG

class BaseInstallClass:
    # default to not being hidden
    hidden = 0
    pixmap = None
    showMinimal = 1
    showLoginChoice = 0
    description = None
    name = "base"
    pkgstext = ""
    # default to showing the upgrade option
    showUpgrade = 1

#     pkgstext = _("\tDesktop shell (GNOME)\n"
#                  "\tOffice suite (OpenOffice)\n"
#                  "\tWeb browser (Mozilla) \n"
#                  "\tEmail (Evolution)\n"
#                  "\tInstant messaging\n"
#                  "\tSound and video applications\n"
#                  "\tGames\n"
#                  "\tSoftware Development Tools\n"
#                  "\tAdministration Tools\n")
    
    
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
                      appendLine="", driveorder = []):
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

        # XXX throw out drives specified that don't exist.  anything else
        # seems silly
        if driveorder and len(driveorder) > 0:
            new = []
            for drive in driveorder:
                if drive in id.bootloader.drivelist:
                    new.append(drive)
                else:
                    log("requested drive %s in boot drive order doesn't "
                        "exist" %(drive,))
            id.bootloader.drivelist = new

    def setIgnoredDisks(self, id, drives):
        diskset = id.diskset
        for drive in drives:
            if not drive in diskset.skippedDisks:
                diskset.skippedDisks.append(drive)

    def setExclusiveDisks(self, id, drives):
        diskset = id.diskset
        for drive in drives:
            if not drive in diskset.exclusiveDisks:
                diskset.exclusiveDisks.append(drive)

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
#		 "checkmonitorok",
#		 "monitor",
#		 "setsanex",
		 "welcome",
                 "findrootparts",
		 "betanag",
		 "installtype",
		 "zfcpconfig",
                 "partitionmethod",
                 "partitionobjinit",
                 "partitionmethodsetup",
                 "autopartition",
                 "autopartitionexecute",
                 "fdisk",
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
		 "readcomps",
                 "selectlangpackages",
		 "package-selection",
                 "handleX11pkgs",
		 "checkdeps",
		 "dependencies",
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
                 "copylogs",
                 "setfilecon",
		 "complete"
		)

	if not BETANAG:
	    dispatch.skipStep("betanag", permanent=1)

	if iutil.getArch() != "s390":
            dispatch.skipStep("zfcpconfig")

        if iutil.getArch() != "i386" or 1:
            dispatch.skipStep("bootdisk")

	# see if we need to write out a rescue boot floppy
	if iutil.getArch() == "i386":
	    import floppy
            if not floppy.hasFloppyDevice():
		dispatch.skipStep("bootdisk")
            
        if iutil.getArch() != "i386" and iutil.getArch() != "x86_64":
            dispatch.skipStep("bootloader")

        # allow install classes to turn off the upgrade 
        if self.showUpgrade == 0:
            dispatch.skipStep("findrootparts", skip = 1)

        # 'noupgrade' can be used on the command line to force not looking
        # for partitions to upgrade.  useful in some cases...
        cmdline = open("/proc/cmdline", "r").read()
        cmdline = cmdline.split()
        if "noupgrade" in cmdline:
            dispatch.skipStep("findrootparts", skip = 1)

        # upgrade will also always force looking for an upgrade. 
        if "upgrade" in cmdline:
            dispatch.skipStep("findrootparts", skip = 0)

        # if there's only one install class, it doesn't make much sense
        # to show it
        if len(availableClasses()) < 2:
            dispatch.skipStep("installtype", permanent=1)

    # called from anaconda so that we can skip steps in the headless case
    # in a perfect world, the steps would be able to figure this out
    # themselves by looking at instdata.headless.  but c'est la vie.
    def setAsHeadless(self, dispatch, isHeadless = 0):
        if isHeadless == 0:
            pass
        else:
	    dispatch.skipStep("keyboard", permanent = 1)
#	    dispatch.skipStep("mouse", permanent = 1)
	    dispatch.skipStep("handleX11pkgs", permanent = 1)
	    dispatch.skipStep("videocard", permanent = 1)
	    dispatch.skipStep("monitor", permanent = 1)
	    dispatch.skipStep("xcustom", permanent = 1)
	    dispatch.skipStep("writexconfig", permanent = 1)

    # This is called after the hdlist is read in.
    def setPackageSelection(self, hdlist, intf):
	pass

    # This is called after the comps is read in (after setPackageSelection()).
    # It can both select groups, change the default selection for groups, and
    # change which groups are hidden.
    def setGroupSelection(self, grpset, intf):
	pass

    def setZFCP(self, id, devnum, scsiid, wwpn, scsilun, fcplun):
        id.zfcp.fcpdevices.append( (devnum, scsiid, wwpn, scsilun, fcplun) )

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

    def setHostname(self, id, hostname, override = 0):
	id.network.setHostname(hostname);
        id.network.overrideDHCPhostname = override

    def setNameserver(self, id, nameserver):
        id.network.setDNS(nameserver)

    def setGateway(self, id, gateway):
        id.network.setGateway(gateway)

    def setTimezoneInfo(self, id, timezone, asUtc = 0, asArc = 0):
	id.timezone.setTimezoneInfo(timezone, asUtc, asArc)

    def setRootPassword(self, id, pw, isCrypted = 0):
	id.rootPassword.set(pw, isCrypted)

    def setAuthentication(self, id, useShadow, salt,
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
        id.auth.salt = salt

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

    def setNetwork(self, id, bootProto, ip, netmask, ethtool, device = None, onboot = 1, dhcpclass = None, essid = None, wepkey = None):
	if bootProto:
	    devices = id.network.netdevices
            firstdev = id.network.getFirstDeviceName()
	    if (devices and bootProto):
		if not device:
                    if devices.has_key(firstdev):
                        device = firstdev
                    else:
                        list = devices.keys ()
                        list.sort()
                        device = list[0]
                dev = devices[device]
                dev.set (("bootproto", bootProto))
                dev.set (("dhcpclass", dhcpclass))
		if onboot:
		    dev.set (("onboot", "yes"))
		else:
		    dev.set (("onboot", "no"))
                if bootProto == "static":
                    if (ip):
                        dev.set (("ipaddr", ip))
                    if (netmask):
                        dev.set (("netmask", netmask))
                if ethtool:
                    dev.set (("ethtool_opts", ethtool))
                if isys.isWireless(device):
                    if essid:
                        dev.set(("essid", essid))
                    if wepkey:
                        dev.set(("wepkey", wepkey))

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

    def setSELinux(self, id, sel):
        id.security.setSELinux(sel)

    def setFirewall(self, id, enable = 1, trusts = [], ports = []):
	id.firewall.enabled = enable
	id.firewall.trustdevs = trusts
        # this is a little ugly, but we want to let setting a service
        # like --ssh enable the service in case they're doing an interactive
        # kickstart install
        for port in ports:
            found = 0
            for s in id.firewall.services:
                p = s.get_ports()
                # don't worry about the ones that are more than one,
                # this is really for legacy use only
                if len(p) > 1:
                    continue
                if p[0] == port:
                    s.set_enabled(1)
                    found = 1
                    break

            if not found:
                id.firewall.portlist.append(port)
        
    def setMiscXSettings(self, id, depth = None, resolution = None,
                         desktop = None, runlevel = None):

        if depth:
            availableDepths = id.xsetup.xhwstate.available_color_depths()
            if depth not in availableDepths:
                log("Requested depth %s not available, falling back to %s"
                    %(depth, availableDepths[-1]))
                depth = availableDepths[-1]
            id.xsetup.xhwstate.set_colordepth(depth)

        if resolution:
            availableRes = id.xsetup.xhwstate.available_resolutions()
            if resolution not in availableRes:
                 log("Requested resolution %s is not supported, falling "
                     "back to %s. To avoid this you may need to specify the "
                     "videocard and monitor specs on the xconfig ks "
                     "directive if they were not probed correctly."
                     %(resolution, availableRes[-1]))
		 resolution = availableRes[-1]
            id.xsetup.xhwstate.set_resolution(resolution)

        if not resolution and not depth:
            # choose a sane default
            log("resolution and depth not specified, trying to be sane")
            id.xsetup.xhwstate.choose_sane_default()
            
        if desktop is not None:
            id.desktop.setDefaultDesktop(desktop)
        if runlevel is not None:
            id.desktop.setDefaultRunLevel(runlevel)

    def setMonitor(self, id, hsync = None, vsync = None, monitorName = None):
        if monitorName:
            usemon = monitorName
        elif id.monitor.getMonitorID() != "Unprobed Monitor":
	    usemon = id.monitor.getMonitorName()
        else:
            usemon = None

        setmonitor = 0
        if usemon:
            monname = usemon
            try:
                (model, eisa, vert, horiz) = id.monitor.lookupMonitorByName(usemon)
		if id.monitor.getMonitorID() != "DDCPROBED":
		    useid = model
		else:
		    useid = "DDCPROBED"

                if not vsync:
                    vsync = vert
                if not hsync:
                    hsync = horiz
		    
                id.monitor.setSpecs(hsync, vsync, id=useid, name=model)
                setmonitor = 1
            except:
                log("Couldnt lookup monitor type %s." % usemon)
                pass
        else:
            monname = "Unprobed Monitor"

        if not setmonitor and hsync and vsync:
            id.monitor.setSpecs(hsync, vsync)
            setmonitor = 1

        if not setmonitor:
             # fall back to standard VGA
             log("Could not probe monitor, and no fallback specified.")
             log("Falling back to Generic VGA monitor")

             try:
                 hsync = "31.5-37.9"
                 vsync = "50.0-61.0"
                 monname = "Unprobed Monitor"
                 id.monitor.setSpecs(hsync, vsync)
             except:
                 raise RuntimeError, "Could not probe monitor and fallback failed."

        # shove into hw state object, force it to recompute available modes
        id.xsetup.xhwstate.monitor = id.monitor
        id.xsetup.xhwstate.set_monitor_name(monname)
        id.xsetup.xhwstate.set_hsync(hsync)
        id.xsetup.xhwstate.set_vsync(vsync)
        id.xsetup.xhwstate.recalc_mode()

    def setVideoCard(self, id, server = None, card = None, videoRam = None):
        # oh suck.  if on ppc, bail because nothing other than fbdev is
        # going to work all that well
        if iutil.getArch() == "ppc":
            return
        
        primary = id.videocard.primaryCard()

        if card:
            db = id.videocard.cardsDB()
            if db.has_key(card):
                vcdata = db[card]
                primary.setCardData(vcdata)
                primary.setDevID(vcdata["NAME"])
                primary.setDescription(vcdata["NAME"])

                id.xsetup.xhwstate.set_videocard_name(vcdata["NAME"])
                id.xsetup.xhwstate.set_videocard_card(vcdata["NAME"])
            else:
                raise RuntimeError, "Unknown videocard specified: %s" %(card,)

        if videoRam:
            # FIXME: this required casting is ugly
            id.videocard.primaryCard().setVideoRam(str(videoRam))
            id.xsetup.xhwstate.set_videocard_ram(int(videoRam))

        if server is not None:
            log("unable to really do anything with server right now")
            

    def configureX(self, id, server = None, card = None, videoRam = None, monitorName = None, hsync = None, vsync = None, resolution = None, depth = None, noProbe = 0, startX = 0):
        self.setVideoCard(id, server, card, videoRam)
        self.setMonitor(id, hsync, vsync, monitorName)

        if startX:
            rl = 5
        else:
            rl = 3
        self.setMiscXSettings(id, depth, resolution, runlevel = rl)

    def setMouse(self, id, mouseType, device = None, emulThree = -1):
        import rhpl.mouse as mouse

        # blindly trust what we're told
        mouse = mouse.Mouse(skipProbe = 1)
        mouseName = mouse.mouseToMouse()[mouseType]
        mouse.set(mouseName, emulThree, device)
        id.setMouse(mouse)

    def setDefaultPartitioning(self, partitions, clear = CLEARPART_TYPE_LINUX,
                               doClear = 1):
        autorequests = [ ("/", None, 1024, None, 1, 1, 1) ]

        bootreq = getAutopartitionBoot()
        if bootreq:
            autorequests.extend(bootreq)

        (minswap, maxswap) = iutil.swapSuggestion()
        autorequests.append((None, "swap", minswap, maxswap, 1, 1, 1))

        if doClear:
            partitions.autoClearPartType = clear
            partitions.autoClearPartDrives = []
        partitions.autoPartitionRequests = autoCreateLVMPartitionRequests(autorequests)
        

    def setInstallData(self, id, intf = None):
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
    elif os.access("/tmp/product/installclasses", os.R_OK):
        path = "/tmp/product/installclasses"
    else:
	path = "/usr/lib/anaconda/installclasses"

    # append the location of installclasses to the python path so we
    # can import them
    sys.path.append(path)

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
