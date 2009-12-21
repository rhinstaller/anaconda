# this is the prototypical class for workstation, server, and kickstart 
# installs
#
# The interface to BaseInstallClass is *public* -- ISVs/OEMs can customize the
# install by creating a new derived type of this class.
#
# Copyright 1999-2006 Red Hat, Inc.
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
import rhpl

from instdata import InstallData
from partitioning import *
from autopart import getAutopartitionBoot, autoCreatePartitionRequests, autoCreateLVMPartitionRequests

from rhpl.translate import _, N_

import logging
log = logging.getLogger("anaconda")

from flags import flags
from constants import *

class BaseInstallClass:
    # default to not being hidden
    hidden = 0
    pixmap = None
    showMinimal = 1
    showLoginChoice = 0
    _description = ""
    _descriptionFields = ()
    name = "base"
    pkgstext = ""
    # default to showing the upgrade option
    showUpgrade = 1 # FIXME: no upgrade for now while doing yum work

    # list of of (txt, grplist) tuples for task selection screen
    tasks = []

    # dict of repoid: (baseurl, mirrorurl) tuples for additional repos
    repos = {}
    
    # don't select this class by default
    default = 0

    # don't force text mode
    forceTextMode = 0

    # allow additional software repositories beyond the base to be configured
    allowExtraRepos = True

    # by default, place this under the "install" category; it gets it's
    # own toplevel category otherwise
    parentClass = ( _("Install on System"), "install.png" )

    # we can use a different install data class
    installDataClass = InstallData

    # install key related bits
    skipkeytext = None
    instkeyname = None
    allowinstkeyskip = True
    instkeydesc = None
    installkey = None
    skipkey = False

    def _get_description(self):
        return _(self._description) % self._descriptionFields
    description = property(_get_description)

    def postAction(self, anaconda, serial):
	pass

    def setBootloader(self, id, location=None, forceLBA=0, password=None,
                      md5pass=None, appendLine="", driveorder = [], hvArgs=""):
        if appendLine:
            id.bootloader.args.set(appendLine)
        id.bootloader.setForceLBA(forceLBA)
        if password:
            id.bootloader.setPassword(password, isCrypted = 0)
        if md5pass:
            id.bootloader.setPassword(md5pass)
        if location != None:
            id.bootloader.defaultDevice = location
        else:
            id.bootloader.defaultDevice = -1
        if hvArgs:
            id.bootloader.hvArgs = hvArgs

        # XXX throw out drives specified that don't exist.  anything else
        # seems silly
        if driveorder and len(driveorder) > 0:
            new = []
            for drive in driveorder:
                if drive in id.bootloader.drivelist:
                    new.append(drive)
                else:
                    log.warning("requested drive %s in boot drive order "
                                "doesn't exist" %(drive,))
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

    def setClearParts(self, id, clear, drives = None, initAll = False):
	id.partitions.autoClearPartType = clear
        id.partitions.autoClearPartDrives = drives
        if initAll:
            id.partitions.reinitializeDisks = initAll

    def setSteps(self, dispatch):
	dispatch.setStepList(
		 "language",
		 "keyboard",
		 "welcome",
                 "findrootparts",
		 "betanag",
		 "installtype",
                 "partitionobjinit",
                 "parttype",
                 "autopartitionexecute",
                 "partition",
		 "partitiondone",
		 "bootloadersetup",                 
		 "bootloader",
                 "reipl",
                 "networkdevicecheck",
		 "network",
		 "timezone",
		 "accounts",
                 "reposetup",
                 "basepkgsel",
		 "tasksel",                                  
		 "postselection",
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
                 "writeregkey",
                 "methodcomplete",
                 "copylogs",
                 "setfilecon",
		 "complete"
		)

	if not BETANAG:
	    dispatch.skipStep("betanag", permanent=1)

        if rhpl.getArch() != "i386" and rhpl.getArch() != "x86_64":
            dispatch.skipStep("bootloader", permanent=1)

        # allow install classes to turn off the upgrade 
        if self.showUpgrade == 0:
            dispatch.skipStep("findrootparts", skip = 1)

        # 'noupgrade' can be used on the command line to force not looking
        # for partitions to upgrade.  useful in some cases...
        if flags.cmdline.has_key("noupgrade"):
            dispatch.skipStep("findrootparts", skip = 1)

        # upgrade will also always force looking for an upgrade. 
        if flags.cmdline.has_key("upgrade"):
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
	    dispatch.skipStep("writexconfig", permanent = 1)

    # modifies the uri from installmethod.getMethodUri() to take into
    # account any installclass specific things including multiple base
    # repositories.  takes a string, returns a list of strings
    def getPackagePaths(self, uri):
        return { "base": uri }

    def handleRegKey(self, key, intf):
        pass

    def setPackageSelection(self, anaconda):
	pass

    def setGroupSelection(self, anaconda):
	pass

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

    def setAuthentication(self, id, authStr):
        id.auth = authStr

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

                if bootProto == "query":
                    id.network.query = True
                else:
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

    def setLanguageDefault(self, id, default):
	id.instLanguage.setDefault(default)

    def setLanguage(self, id, nick):
	id.instLanguage.setRuntimeLanguage(nick)

    def setDesktop(self, id, desktop):
	id.desktop.setDefaultDesktop (desktop)

    def setSELinux(self, id, sel):
        id.security.setSELinux(sel)

    def setFirewall(self, id, enable = 1, trusts = [], ports = []):
	id.firewall.enabled = enable
	id.firewall.trustdevs = trusts

	for port in ports:
	    id.firewall.portlist.append (port)
        
    def setMiscXSettings(self, id, depth = None, resolution = None,
                         desktop = None, runlevel = None):

        if depth:
            availableDepths = id.xsetup.xserver.hwstate.available_color_depths()
            if depth not in availableDepths:
                log.warning("Requested depth %s not available, falling back "
                            "to %s" %(depth, availableDepths[-1]))
                depth = availableDepths[-1]
            id.xsetup.xserver.hwstate.set_colordepth(depth)

        if resolution:
            availableRes = id.xsetup.xserver.hwstate.available_resolutions()
            if resolution not in availableRes:
                 log.warning("Requested resolution %s is not supported, "
                             "falling back to %s. To avoid this you may need "
                             "to specify the videocard and monitor specs on "
                             "the xconfig ks directive if they were not probed "
                             "correctly." %(resolution, availableRes[-1]))
		 resolution = availableRes[-1]
            id.xsetup.xserver.hwstate.set_resolution(resolution)

        if not resolution and not depth:
            # choose a sane default
            log.warning("resolution and depth not specified, trying to be sane")
            id.xsetup.xserver.hwstate.choose_sane_default()

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
                log.warning("Couldnt lookup monitor type %s." % usemon)
                pass
        else:
            monname = "Unprobed Monitor"

        if not setmonitor and hsync and vsync:
            id.monitor.setSpecs(hsync, vsync)
            setmonitor = 1

        if not setmonitor:
             # fall back to standard VGA
             log.warning("Could not probe monitor, and no fallback specified.")
             log.warning("Falling back to Generic VGA monitor")

             try:
                 hsync = "31.5-37.9"
                 vsync = "50.0-61.0"
                 monname = "Unprobed Monitor"
                 id.monitor.setSpecs(hsync, vsync)
             except:
                 raise RuntimeError, "Could not probe monitor and fallback failed."

        # shove into hw state object, force it to recompute available modes
        id.xsetup.xserver.hwstate.monitor = id.monitor
        id.xsetup.xserver.hwstate.set_monitor_name(monname)
        id.xsetup.xserver.hwstate.set_hsync(hsync)
        id.xsetup.xserver.hwstate.set_vsync(vsync)
        id.xsetup.xserver.hwstate.recalc_mode()

    def setVideoCard(self, id, driver = None, videoRam = None):
        primary = id.videocard.primaryCard()

        # rhpxl no longer gives us a list of drivers, so always just trust
        # what the user gave us.
        if driver:
            log.info("Setting video card driver to user value of %s" % driver)
            primary.setDriver(driver)
            id.xsetup.xserver.hwstate.set_videocard_name(primary.getDescription())
            id.xsetup.xserver.hwstate.set_videocard_driver(driver)

        if videoRam:
            # FIXME: this required casting is ugly
            primary.setVideoRam(str(videoRam))
            id.xsetup.xserver.hwstate.set_videocard_ram(int(videoRam))

    def configureX(self, id, driver = None, videoRam = None, resolution = None, depth = None, startX = 0):
        self.setVideoCard(id, driver, videoRam)

        if startX:
            rl = 5
        else:
            rl = 3
        self.setMiscXSettings(id, depth, resolution, runlevel = rl)

    def setMouse(self, id, mouseType, device = None, emulThree = -1):
        import rhpxl.mouse as mouse

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


    def setInstallData(self, anaconda):
	anaconda.id.reset()
	anaconda.id.instClass = self

	# Classes should call these on __init__ to set up install data
	#id.setKeyboard()
	#id.setLanguage()
	#id.setNetwork()
	#id.setFirewall()
	#id.setLanguageDefault()
	#id.setTimezone()
	#id.setAuthentication()
	#id.setHostname()
	#id.setDesktop()
	#id.setMouse()

	# These are callbacks used to let classes configure packages
	#id.setPackageSelection()
	#id.setGroupSelection()

    def __init__(self, expert):
	pass

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
    elif os.access("/mnt/source/RHupdates/installclasses", os.R_OK):
        path = "/mnt/source/RHupdates/installclasses"
    elif os.access("/tmp/updates/installclasses", os.R_OK):
        path = "/tmp/updates/installclasses"
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
                if obj.arch != rhpl.getArch ():
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

def getBaseInstallClass():
    # figure out what installclass we should base on. this is largely needed
    # due to nonsense about how things like upgrades and kickstart are
    # implemented as installclasses :/
    allavail = availableClasses(showHidden = 1)
    avail = availableClasses(showHidden = 0)
    if len(avail) == 1:
        (cname, cobject, clogo) = avail[0]
        log.info("using only installclass %s" %(cname,))
        return cobject
    elif len(allavail) == 1:
        (cname, cobject, clogo) = allavail[0]
        log.info("using only installclass %s" %(cname,))
        return cobject
    else:
        cobject = BaseInstallClass
        log.info("using baseinstallclass as base")
        return BaseInstallClass

baseclass = getBaseInstallClass()

# we need to be able to differentiate between this and custom
class DefaultInstall(baseclass):
    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

