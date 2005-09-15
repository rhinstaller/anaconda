#
# kickstart.py: kickstart install support
#
# Copyright 1999-2004 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil
import isys
import os
from installclass import BaseInstallClass
from partitioning import *
from autopart import *
from fsset import *
from flags import flags
from constants import *
import sys
import raid
import string
import partRequests
import urlgrabber.grabber as grabber
import lvm
from kickstartParser import *
from kickstartData import KickstartData

import logging
log = logging.getLogger("anaconda")

class AnacondaKSScript(Script):
    def run(self, chroot, serial, intf = None):
        scriptRoot = "/"
        if self.inChroot:
            scriptRoot = chroot

        path = scriptRoot + "/tmp/ks-script"

        f = open(path, "w")
        f.write(self.script)
        f.close()
        os.chmod(path, 0700)

        if self.logfile is not None:
            messages = self.logfile
        elif serial:
            messages = "/tmp/ks-script.log"
        else:
            messages = "/dev/tty3"

        rc = iutil.execWithRedirect(self.interp,
                                    [self.interp,"/tmp/ks-script"],
                                    stdout = messages, stderr = messages,
                                    root = scriptRoot)

        # Always log an error.  Only fail if we have a handle on the
        # windowing system and the kickstart file included --erroronfail.
        if rc != 0:
            log.error("Error code %s encountered running a kickstart %%pre/%%post script", rc)

            if self.errorOnFail:
                if intf != None:
                    intf.messageWindow(_("Scriptlet Failure"),
                                       _("There was an error running the "
                                         "scriptlet.  You may examine the "
                                         "output in %s.  This is a fatal error "
                                         "and your install will be aborted.\n\n"
                                         "Press the OK button to reboot your "
                                         "system.") % (messages,))
                sys.exit(0)

        os.unlink(path)

class AnacondaKSHandlers(KickstartHandlers):
    def __init__ (self, ksdata):
        KickstartHandlers.__init__(self, ksdata)
        self.skipSteps = []
        self.showSteps = []
        self.ksRaidMapping = {}
        self.ksUsedMembers = []
        self.ksPVMapping = {}
        self.ksVGMapping = {}
        # XXX hack to give us a starting point for RAID, LVM, etc unique IDs.
        self.ksID = 100000

    def doAuthconfig(self, id, args):
        KickstartHandlers.doAuthconfig(self, args)

    def doAutoPart(self, id, args):
        KickstartHandlers.doAutoPart(self, args)

        # sets up default autopartitioning.  use clearpart separately
        # if you want it
        id.instClass.setDefaultPartitioning(id, doClear = 0)

        id.partitions.isKickstart = 1
        self.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

    def doAutoStep(self, id, args):
        KickstartHandlers.doAutoStep(self, args)
        flags.autostep = 1
	flags.autoscreenshot = self.ksdata.autostep["autoscreenshot"]

    def doBootloader (self, id, args):
        KickstartHandlers.doBootloader(self, args)
	dict = self.ksdata.bootloader

        if dict["location"] == "none":
            location = None
        elif dict["location"] == "partition":
            location = "boot"
        else:
            location = dict["location"]

        if dict["upgrade"] and not id.getUpgrade():
            raise KickstartError, "Selected upgrade mode for bootloader but not doing an upgrade"

        if dict["upgrade"]:
            id.bootloader.kickstart = 1
            id.bootloader.doUpgradeOnly = 1

        if location is None:
            self.skipSteps.extend(["bootloadersetup", "instbootloader"])
        else:
            self.showSteps.append("bootloadersetup")
            id.instClass.setBootloader(id, location, dict["forceLBA"],
                                       dict["password"], dict["md5pass"],
                                       dict["appendLine"], dict["driveorder"])

        self.skipSteps.extend(["upgbootloader", "bootloader",
                               "bootloaderadvanced"])

    def doClearPart(self, id, args):
        KickstartHandlers.doClearPart(self, args)
        dict = self.ksdata.clearpart
        id.instClass.setClearParts(id, dict["type"], dict["drives"],
                                   dict["initAll"])

    def doDevice(self, id, args):
        KickstartHandlers.doDevice(self, args)

    def doDeviceProbe(self, id, args):
        KickstartHandlers.doDeviceProbe(self, args)

    def doDisplayMode(self, id, args):
        KickstartHandlers.doDisplayMode(self, args)

    def doDriverDisk(self, id, args):
        KickstartHandlers.doDriverDisk(self, args)

    def doFirewall(self, id, args):
        KickstartHandlers.doFirewall(self, args)
        dict = self.ksdata.firewall
	id.instClass.setFirewall(id, dict["enabled"], dict["trusts"],
                                 dict["ports"])

    def doFirstboot(self, id, args):
        KickstartHandlers.doFirstboot(self, args)
        id.firstboot = self.ksdata.firstboot

    def doIgnoreDisk(self, id, args):
	KickstartHandlers.doIgnoreDisk(self, args)
        id.instClass.setIgnoredDisks(id, self.ksdata.ignoredisk)

    def doInteractive(self, id, args):
        KickstartHandlers.doInteractive(self, args)

    def doKeyboard(self, id, args):
        KickstartHandlers.doKeyboard(self, args)
        id.instClass.setKeyboard(id, self.ksdata.keyboard)
        id.keyboard.beenset = 1
	self.skipSteps.append("keyboard")

    def doLang(self, id, args):
        KickstartHandlers.doLang(self, args)
        id.instClass.setLanguage(id, self.ksdata.lang)
	self.skipSteps.append("language")

    def doLangSupport(self, id, args):
        KickstartHandlers.doLangSupport(self, args)

    def doLogicalVolume(self, id, args):
        KickstartHandlers.doLogicalVolume(self, args)
        dict = self.ksdata.lvList[-1]

        if dict["mountpoint"] == "swap":
            filesystem = fileSystemTypeGet("swap")
            dict["mountpoint"] = None

            if dict["recommended"]:
                (dict["size"], dict["maxSizeMB"]) = iutil.swapSuggestion()
                dict["grow"] = True
        else:
            if dict["fstype"]:
                filesystem = fileSystemTypeGet(dict["fstype"])
            else:
                filesystem = fileSystemTypeGetDefault()

	# sanity check mountpoint
	if dict["mountpoint"] is not None and dict["mountpoint"][0] != '/':
	    raise KickstartValueError, "The mount point \"%s\" is not valid." % (dict["mountpoint"],)

        if not (dict["size"] or dict["percent"] or dict["preexist"]):
            raise KickstartValueError, "Size required for logical volume %s" % dict["name"]
        if dict["percent"] and dict["percent"] <= 0 or dict["percent"] > 100:
            raise KickstartValueError, "Percentage must be between 0 and 100 for logical volume %s" % dict["name"]

        vgid = self.ksVGMapping[dict["vgname"]]
	for areq in id.partitions.autoPartitionRequests:
	    if areq.type == REQUEST_LV:
		if areq.volumeGroup == vgid and areq.logicalVolumeName == dict["name"]:
		    raise KickstartValueError, "Logical volume name %(name)s already used in volume group %(vgname)s" % dict

        if not self.ksVGMapping.has_key(dict["vgname"]):
            raise KickstartValueError, "Logical volume %s specifies a non-existent volume group" % dict["name"]

        request = partRequests.LogicalVolumeRequestSpec(filesystem,
                                      format = dict["format"],
                                      mountpoint = dict["mountpoint"],
                                      size = dict["size"],
                                      percent = dict["percent"],
                                      volgroup = vgid,
                                      lvname = dict["name"],
				      grow = dict["grow"],
				      maxSizeMB = dict["maxSizeMB"],
                                      preexist = dict["preexist"],
                                      bytesPerInode = dict["bytesPerInode"])

	if dict["fsopts"]:
            request.fsopts = dict["fsopts"]

        id.instClass.addPartRequest(id.partitions, request)

    def doMediaCheck(self, id, args):
        KickstartHandlers.doMediaCheck(self, args)

    def doMethod(self, id, args):
	KickstartHandlers.doMethod(self, args)

    def doMonitor(self, id, args):
        KickstartHandlers.doMonitor(self, args)
        dict = self.ksdata.monitor
        self.skipSteps.extend(["monitor", "checkmonitorok"])
        id.instClass.setMonitor(id, dict["hsync"], dict["vsync"],
                                dict["monitor"])

    def doMouse(self, id, args):
        KickstartHandlers.doMouse(self, args)

    def doNetwork(self, id, args):
        KickstartHandlers.doNetwork(self, args)
        dict = self.ksdata.network[-1]

        id.instClass.setNetwork(id, dict["bootProto"], dict["ip"],
                                dict["netmask"], dict["ethtool"],
                                dict["device"], dict["onboot"],
                                dict["dhcpclass"], dict["essid"],
                                dict["wepkey"])

        if dict["hostname"] is not None:
            id.instClass.setHostname(id, dict["hostname"], override=1)

        if dict["nameserver"] is not None:
            id.instClass.setNameserver(id, dict["nameserver"])

        if dict["gateway"] is not None:
            id.instClass.setGateway(id, dict["gateway"])

    def doPartition(self, id, args):
        KickstartHandlers.doPartition(self, args)
        dict = self.ksdata.partitions[-1]
        uniqueID = None

        if dict["onbiosdisk"] is not None:
            dict["disk"] = isys.doGetBiosDisk(dict["onbiosdisk"])

            if dict["disk"] is not None:
                raise KickstartValueError, "Specified BIOS disk %s cannot be determined" % dict["disk"]

        if dict["mountpoint"] == "swap":
            filesystem = fileSystemTypeGet('swap')
            dict["mountpoint"] = None
            if dict["recommended"]:
                (dict["size"], dict["maxSize"]) = iutil.swapSuggestion()
                dict["grow"] = True
        # if people want to specify no mountpoint for some reason, let them
        # this is really needed for pSeries boot partitions :(
        elif dict["mountpoint"] == "None":
            dict["mountpoint"] = None
            if dict["fstype"]:
                filesystem = fileSystemTypeGet(dict["fstype"])
            else:
                filesystem = fileSystemTypeGetDefault()
        elif dict["mountpoint"] == 'appleboot':
            filesystem = fileSystemTypeGet("Apple Bootstrap")
            dict["mountpoint"] = None
        elif dict["mountpoint"] == 'prepboot':
            filesystem = fileSystemTypeGet("PPC PReP Boot")
            dict["mountpoint"] = None
        elif dict["mountpoint"].startswith("raid."):
            filesystem = fileSystemTypeGet("software RAID")
            
            if self.ksRaidMapping.has_key(dict["mountpoint"]):
                raise KickstartValueError, "Defined RAID partition %s multiple times" % dict["mountpoint"]
            
            # get a sort of hackish id
            uniqueID = self.ksID
            self.ksRaidMapping[dict["mountpoint"]] = uniqueID
            self.ksID = self.ksID + 1
            dict["mountpoint"] = None
        elif dict["mountpoint"].startswith("pv."):
            filesystem = fileSystemTypeGet("physical volume (LVM)")

            if self.ksPVMapping.has_key(dict["mountpoint"]):
                raise KickstartValueError, "Defined PV partition %s multiple times" % dict["mountpoint"]

            # get a sort of hackish id
            uniqueID = self.ksID
            self.ksPVMapping[dict["mountpoint"]] = uniqueID
            self.ksID = self.ksID + 1
            dict["mountpoint"] = None
        # XXX should we let people not do this for some reason?
        elif dict["mountpoint"] == "/boot/efi":
            filesystem = fileSystemTypeGet("vfat")
        else:
            if dict["fstype"]:
                filesystem = fileSystemTypeGet(dict["fstype"])
            else:
                filesystem = fileSystemTypeGetDefault()

        if (dict["size"] is None) and (not dict["start"] and not dict["end"]) \
            and (not dict["onPart"]):
            raise KickstartValueError, "partition requires a size specification"
        if dict["start"] and not dict["disk"]:
            raise KickstartValueError, "partition command with start cylinder requires a drive specification"
        if dict["disk"] and dict["disk"] not in isys.hardDriveDict().keys():
            raise KickstartValueError, "specified disk %s in partition command which does not exist" % dict["disk"]

        request = partRequests.PartitionSpec(filesystem,
                                        mountpoint = dict["mountpoint"],
                                        format = 1,
                                        fslabel = dict["label"],
                                        bytesPerInode = dict["bytesPerInode"])
        
        if dict["size"] is not None:
            request.size = dict["size"]
        if dict["start"]:
            request.start = dict["start"]
        if dict["end"]:
            request.end = dict["end"]
        if dict["grow"]:
            request.grow = dict["grow"]
        if dict["maxSize"]:
            request.maxSizeMB = dict["maxSize"]
        if dict["disk"]:
            request.drive = [ dict["disk"] ]
        if dict["primOnly"]:
            request.primary = dict["primOnly"]
        if dict["format"]:
            request.format = dict["format"]
        if uniqueID:
            request.uniqueID = uniqueID
        if dict["onPart"]:
            request.device = dict["onPart"]
            for areq in id.partitions.autoPartitionRequests:
                if areq.device is not None and areq.device == dict["onPart"]:
		    raise KickstartValueError, "Partition %s already used" % dict["onPart"]

        if dict["fsopts"]:
            request.fsopts = dict["fsopts"]

        id.instClass.addPartRequest(id.partitions, request)
        id.partitions.isKickstart = 1
        self.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

    def doReboot(self, id, args):
        KickstartHandlers.doReboot(self, args)
        self.skipSteps.append("complete")

    def doRaid(self, id, args):
        KickstartHandlers.doRaid(self, args)
        dict = self.ksdata.raidList[-1]

        if dict["mountpoint"] == "swap":
            filesystem = fileSystemTypeGet('swap')
            dict["mountpoint"] = None
        elif dict["mountpoint"].startswith("pv."):
            filesystem = fileSystemTypeGet("physical volume (LVM)")

            if self.ksPVMapping.has_key(dict["mountpoint"]):
                raise KickstartValueError, "Defined PV partition %s multiple times" % dict["mountpoint"]

            # get a sort of hackish id
            uniqueID = self.ksID
            self.ksPVMapping[dict["mountpoint"]] = uniqueID
            self.ksID = self.ksID + 1
            dict["mountpoint"] = None
        else:
            if dict["fstype"]:
                filesystem = fileSystemTypeGet(fstype)
            else:
                filesystem = fileSystemTypeGetDefault()

	# sanity check mountpoint
	if dict["mountpoint"] is not None and dict["mountpoint"][0] != '/':
	    raise KickstartValueError, "The mount point %s is not valid." % dict["mountpoint"]

        raidmems = []

        # get the unique ids of each of the raid members
        for member in dict["members"]:
            if member not in self.ksRaidMapping.keys():
                raise KickstartValueError, "Tried to use undefined partition %s in RAID specification" % member
	    if member in self.ksUsedMembers:
                raise KickstartValueError, "Tried to use RAID member %s in two or more RAID specifications" % member
		
            raidmems.append(self.ksRaidMapping[member])
	    self.ksUsedMembers.append(member)

        if not dict["level"] and dict["preexist"] == 0:
            raise KickstartValueError, "RAID Partition defined without RAID level"
        if len(raidmems) == 0 and dict["preexist"] == 0:
            raise KickstartValueError, "RAID Partition defined without any RAID members"

        request = partRequests.RaidRequestSpec(filesystem,
                                   mountpoint = dict["mountpoint"],
                                   raidmembers = raidmems,
                                   raidlevel = dict["level"],
                                   raidspares = dict["spares"],
                                   format = dict["format"],
                                   raidminor = dict["device"],
                                   preexist = dict["preexist"])

        if uniqueID:
            request.uniqueID = uniqueID
        if dict["preexist"] and dict["device"] is not None:
            request.device = "md%s" % dict["device"]
        if dict["fsopts"]:
            request.fsopts = dict["fsopts"]

        id.instClass.addPartRequest(id.partitions, request)

    def doRootPw(self, id, args):
        KickstartHandlers.doRootPw(self, args)
        dict = self.ksdata.rootpw
        
	id.instClass.setRootPassword(id, dict["password"], dict["isCrypted"])
	self.skipSteps.append("accounts")

    def doSELinux(self, id, args):
        KickstartHandlers.doSELinux(self, args)
        id.instClass.setSELinux(id, self.ksdata.selinux)

    def doSkipX(self, id, args):
        KickstartHandlers.doSkipX(self, args)
        self.skipSteps.extend(["checkmonitorok", "setsanex", "videocard",
                               "monitor", "xcustom", "handleX11pkgs",
                               "writexconfig"])

        if id.xsetup is not None:
            id.xsetup.skipx = 1

    def doTimezone(self, id, args):
        KickstartHandlers.doTimezone(self, args)
        dict = self.ksdata.timezone

	id.instClass.setTimezoneInfo(id, dict["timezone"], dict["isUtc"])
	self.skipSteps.append("timezone")

    def doUpgrade(self, id, args):
        KickstartHandlers.doUpgrade(self, args)
        id.setUpgrade(True)

    def doVnc(self, id, args):
        KickstartHandlers.doVnc(self, args)

    def doVolumeGroup(self, id, args):
	KickstartHandlers.doVolumeGroup(self, args)
        dict = self.ksdata.vgList[-1]

        pvs = []

        # get the unique ids of each of the physical volumes
        for pv in dict["physvols"]:
            if pv not in self.ksPVMapping.keys():
                raise KickstartValueError, "Tried to use undefined partition %s in Volume Group specification" % pv
            pvs.append(self.ksPVMapping[pv])

        if len(pvs) == 0 and not dict["preexist"]:
            raise KickstartValueError, "Volume group defined without any physical volumes"

        if dict["pesize"] not in lvm.getPossiblePhysicalExtents(floor=1024):
            raise KickstartValueError, "Volume group specified invalid pesize: %d" %(dict["pesize"],)

        # get a sort of hackish id
        uniqueID = self.ksID
        self.ksVGMapping[dict["vgname"]] = uniqueID
        self.ksID = self.ksID + 1
            
        request = partRequests.VolumeGroupRequestSpec(vgname = dict["vgname"],
                                          physvols = pvs,
                                          preexist = dict["preexist"],
                                          format = dict["format"],
                                          pesize = dict["pesize"])
        request.uniqueID = uniqueID
        id.instClass.addPartRequest(id.partitions, request)

    def doXConfig(self, id, args):
        KickstartHandlers.doXConfig(self, args)
        dict = self.ksdata.xconfig

	id.instClass.configureX(id, dict["driver"],
                                dict["videoRam"], dict["monitor"],
                                dict["hsync"], dict["vsync"],
                                dict["resolution"], dict["depth"],
                                dict["probe"], dict["startX"])
        id.instClass.setDesktop(id, dict["defaultdesktop"])
        self.skipSteps.extend(["videocard", "monitor", "xcustom",
                               "handleX11pkgs", "checkmonitorok", "setsanex"])

    def doZeroMbr(self, id, args):
        KickstartHandlers.doZeroMbr(self, args)
        id.instClass.setZeroMbr(id, 1)

    def doZFCP(self, id, args):
        KickstartHandlers.doZFCP(self, args)
        dict = self.ksdata.zfcp

        dict["devnum"] = id.zfcp.sanitizeDeviceInput(dict["devnum"])
        dict["fcplun"] = id.zfcp.sanitizeHexInput(dict["fcplun"])
        dict["scsiid"] = id.zfcp.sanitizeInput(dict["scsiid"])
        dict["scsilun"] = id.zfcp.sanitizeHexInput(dict["scsilun"])
        dict["wwpn"] = id.zfcp.sanitizeFCPLInput(dict["wwpn"])

        if id.zfcp.checkValidDevice(dict["devnum"]) == -1:
            raise KickstartValueError, "Invalid devnum specified"
        if id.zfcp.checkValidID(dict["scsiid"]) == -1:
            raise KickstartValueError, "Invalid scsiid specified"
        if id.zfcp.checkValid64BitHex(dict["wwpn"]) == -1:
            raise KickstartValueError, "Invalid wwpn specified"
        if id.zfcp.checkValidID(dict["scsilun"]) == -1:
            raise KickstartValueError, "Invalid scsilun specified"
        if id.zfcp.checkValid64BitHex(dict["fcplun"]) == -1:
            raise KickstartValueError, "Invalid fcplun specified"

        id.instClass.setZFCP(id, dict["devnum"], dict["scsiid"], dict["wwpn"],
                             dict["scsilun"], dict["fcplun"])
        self.skipSteps.append("zfcpconfig")

class VNCHandlers(KickstartHandlers):
    # We're only interested in the handler for the VNC command.
    def __init__ (self, ksdata):
        KickstartHandlers.__init__(self, ksdata)
        self.resetHandlers()
        self.handlers["vnc"] = self.doVnc

class KickstartPreParser(KickstartParser):
    def __init__ (self, ksdata, kshandlers):
        self.handler = kshandlers
        KickstartParser.__init__(self, ksdata, kshandlers)
        self.followIncludes = False

    def addScript (self, state, script):
        if state == STATE_PRE:
            s = Script (script["body"], script["interp"], script["chroot"],
                        script["log"], script["errorOnFail"])
            self.ksdata.preScripts.append(s)

    def addPackages (self, line):
        pass

    def handleCommand (self, cmd, args):
        pass

    def handlePackageHdr (self, line):
        pass

    def handleScriptHdr (self, args, script):
        if not args[0] == "%pre":
            return

        op = KSOptionParser()
        op.add_option("--erroronfail", dest="errorOnFail", action="store_true",
                      default=False)
        op.add_option("--interpreter", dest="interpreter", default="/bin/sh")
        op.add_option("--log", "--logfile", dest="log")

        (opts, extra) = op.parse_args(args=args[1:])

        script["interp"] = opts.interpreter
        script["log"] = opts.log
        script["errorOnFail"] = opts.errorOnFail
        script["chroot"] = 0

class AnacondaKSParser(KickstartParser):
    def __init__ (self, ksdata, kshandlers, id):
        self.id = id
        KickstartParser.__init__(self, ksdata, kshandlers)

    def handleCommand (self, cmd, args):
        if not self.handler:
            return

        if not self.handler.handlers.has_key(cmd):
            raise KickstartParseError, (cmd + " " + string.join (args))
        else:
            if self.handler.handlers[cmd] != None:
                self.handler.setattr("currentCmd", cmd)
                self.handler.handlers[cmd](self.id, args)

# The anaconda kickstart processor.
class Kickstart(BaseInstallClass):
    name = "kickstart"

    def __init__(self, file, serial):
        self.ksdata = None
        self.handlers = None
        self.serial = serial
        self.file = file

        BaseInstallClass.__init__(self, 0)

    # this adds a partition to the autopartition list replacing anything
    # else with this mountpoint so that you can use autopart and override /
    def addPartRequest(self, partitions, request):
        if not request.mountpoint:
            partitions.autoPartitionRequests.append(request)
            return

        for req in partitions.autoPartitionRequests:
            if req.mountpoint and req.mountpoint == request.mountpoint:
                partitions.autoPartitionRequests.remove(req)
                break
        partitions.autoPartitionRequests.append(request)            

    def runPreScripts(self, intf = None):
	log.info("Running kickstart %%pre script(s)")
	for script in self.ksdata.preScripts:
	    script.run("/", self.serial, intf)
	log.info("All kickstart %%pre script(s) have been run")

    def postAction(self, rootPath, serial, intf = None):
	log.info("Running kickstart %%post script(s)")
	for script in self.ksdata.postScripts:
	    script.run(rootPath, serial, intf)
	log.info("All kickstart %%post script(s) have been run")

    def runTracebackScripts(self):
	log.info("Running kickstart %%traceback script(s)")
	for script in self.ksdata.tracebackScripts:
	    script.run("/", self.serial)

    def setInstallData (self, id, intf = None):
        BaseInstallClass.setInstallData(self, id)
        self.setEarlySwapOn(1)
        self.id = id
        self.id.firstboot = FIRSTBOOT_SKIP

        # parse the %pre
        self.ksdata = KickstartData()
        parser = KickstartPreParser(self.ksdata, None)

        try:
            parser.readKickstart(self.file)
        except KickstartError, e:
           if intf:
               intf.kickstartErrorWindow(e.__str__())
               sys.exit(0)
           else:
               raise KickstartError, e

        # run %pre scripts
        self.runPreScripts(intf)

        # now read the kickstart file for real
        self.ksdata = KickstartData()
        self.handlers = AnacondaKSHandlers(self.ksdata)
        parser = AnacondaKSParser(self.ksdata, self.handlers, self.id)

        try:
            parser.readKickstart(self.file)
        except KickstartError, e:
            if intf:
                intf.kickstartErrorWindow(e.__str__())
                sys.exit(0)
            else:
                raise KickstartError, e

    def setSteps(self, dispatch):
        if self.ksdata.upgrade:
            from upgradeclass import InstallClass
            theUpgradeclass = InstallClass(0)
            theUpgradeclass.setSteps(dispatch)

            # we have no way to specify migrating yet
            dispatch.skipStep("upgrademigfind")
            dispatch.skipStep("upgrademigratefs")
            dispatch.skipStep("upgradecontinue")
            dispatch.skipStep("findinstall", permanent = 1)
            dispatch.skipStep("language")
            dispatch.skipStep("keyboard")
            dispatch.skipStep("welcome")
            dispatch.skipStep("betanag")
            dispatch.skipStep("installtype")
        else:
            BaseInstallClass.setSteps(self, dispatch)
            dispatch.skipStep("findrootparts")

        if self.ksdata.interactive or flags.autostep:
            dispatch.skipStep("installtype")
            dispatch.skipStep("bootdisk")

        # because these steps depend on the monitor being probed
        # properly, and will stop you if you have an unprobed monitor,
        # we should skip them for autostep
        if flags.autostep:
            dispatch.skipStep("checkmonitorok")
            dispatch.skipStep("monitor")
            return

        dispatch.skipStep("bootdisk")
        dispatch.skipStep("welcome")
        dispatch.skipStep("betanag")
        dispatch.skipStep("confirminstall")
        dispatch.skipStep("confirmupgrade")
        dispatch.skipStep("network")
        dispatch.skipStep("installtype")

        for n in self.handlers.skipSteps:
            dispatch.skipStep(n)
        for n in self.handlers.showSteps:
            dispatch.skipStep(n, skip = 0)

#
# look through ksfile and if it contains a line:
#
# %ksappend <url>
#
# pull <url> down and append to /tmp/ks.cfg. This is run before we actually
# parse the complete kickstart file.
#
# Main use is to have the ks.cfg you send to the loader be minimal, and then
# use %ksappend to pull via https anything private (like passwords, etc) in
# the second stage.
#
def pullRemainingKickstartConfig(ksfile):
    try:
	f = open(ksfile, "r")
    except:
	raise KickstartError ("Unable to open ks file %s for append" % ksfile)

    lines = f.readlines()
    f.close()

    url = None
    for l in lines:
	ll = l.strip()
	if string.find(ll, "%ksappend") == -1:
	    continue

	try:
	    (xxx, ksurl) = string.split(ll, ' ')
	except:
	    raise KickstartError ("Illegal url for %%ksappend - %s" % ll)

	log.info("Attempting to pull second part of ks.cfg from url %s" % ksurl)

	try:
	    url = grabber.urlopen (ksurl)
	except grabber.URLGrabError, e:
	    raise KickstartError ("IOError: %s" % e.strerror)
	else:
	    # sanity check result - sometimes FTP doesnt
	    # catch a file is missing
	    try:
		clen = url.info()['content-length']
	    except Exception, e:
		clen = 0

	    if clen < 1:
		raise KickstartError ("IOError: -1:File not found")

        break

    # if we got something then rewrite /tmp/ks.cfg with new information
    if url is not None:
	os.rename("/tmp/ks.cfg", "/tmp/ks.cfg-part1")

	# insert contents of original /tmp/ks.cfg w/o %ksappend line
	f = open("/tmp/ks.cfg", 'w+')
	for l in lines:
	    ll = l.strip()
	    if string.find(ll, "%ksappend") != -1:
		continue
	    f.write(l)

	# now write part we just grabbed
	f.write(url.read())
	f.close()

	# close up url and we're done
	url.close()
	
    return None

