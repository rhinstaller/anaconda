#
# kickstart.py: kickstart install support
#
# Copyright 1999-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil
import isys
import os
from installclass import BaseInstallClass, availableClasses, getBaseInstallClass
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
import warnings
from pykickstart.constants import *
from pykickstart.errors import *
from pykickstart.parser import *
from pykickstart.version import returnClassForVersion
from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")
from anaconda_log import logger, logLevelMap

class AnacondaKSScript(Script):
    def run(self, chroot, serial, intf = None):
        import tempfile
        import os.path

        if self.inChroot:
            scriptRoot = chroot
        else:
            scriptRoot = "/"

        (fd, path) = tempfile.mkstemp("", "ks-script-", scriptRoot + "/tmp")

        os.write(fd, self.script)
        os.close(fd)
        os.chmod(path, 0700)

        if self.logfile is not None:
            messages = self.logfile
        elif serial:
            messages = "%s.log" % path
        else:
            messages = "/dev/tty3"

        rc = iutil.execWithRedirect(self.interp, ["/tmp/%s" % os.path.basename(path)],
                                    stdin = messages, stdout = messages, stderr = messages,
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

        if serial or self.logfile is not None:
            os.chmod("%s" % messages, 0600)

superclass = returnClassForVersion()

class AnacondaKSHandler(superclass):
    def __init__ (self, anaconda):
        superclass.__init__(self)

        self.permanentSkipSteps = []
        self.skipSteps = []
        self.showSteps = []
        self.ksRaidMapping = {}
        self.ksUsedMembers = []
        self.ksPVMapping = {}
        self.ksVGMapping = {}
        # XXX hack to give us a starting point for RAID, LVM, etc unique IDs.
        self.ksID = 100000

        self.anaconda = anaconda
        self.id = self.anaconda.id

    class Authconfig(superclass.Authconfig):
        def parse(self, args):
            superclass.Authconfig.parse(self, args)
            self.handler.id.auth = self.authconfig

    class AutoPart(superclass.AutoPart):
        def parse(self, args):
            superclass.AutoPart.parse(self, args)

            # sets up default autopartitioning.  use clearpart separately
            # if you want it
            self.handler.id.instClass.setDefaultPartitioning(self.handler.id, doClear = 0)

            self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

    class AutoStep(superclass.AutoStep):
        def parse(self, args):
            superclass.AutoStep.parse(self, args)
            flags.autostep = 1
            flags.autoscreenshot = self.autoscreenshot

    class Bootloader(superclass.Bootloader):
        def parse(self, args):
            superclass.Bootloader.parse(self, args)

            if self.location == "none":
                location = None
            elif self.location == "partition":
                location = "boot"
            else:
                location = self.location

            if self.upgrade and not self.handler.id.getUpgrade():
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Selected upgrade mode for bootloader but not doing an upgrade")

            if self.upgrade:
                self.handler.id.bootloader.kickstart = 1
                self.handler.id.bootloader.doUpgradeOnly = 1

            if location is None:
                self.handler.permanentSkipSteps.extend(["bootloadersetup", "instbootloader"])
            else:
                self.handler.showSteps.append("bootloader")
                self.handler.id.instClass.setBootloader(self.handler.id, location, self.forceLBA,
                                                        self.password, self.md5pass,
                                                        self.appendLine, self.driveorder)

            self.handler.permanentSkipSteps.extend(["upgbootloader", "bootloader",
                                                    "bootloaderadvanced"])

    class ClearPart(superclass.ClearPart):
        def parse(self, args):
            superclass.ClearPart.parse(self, args)

            hds = isys.hardDriveDict().keys()
            for disk in self.drives:
                if disk not in hds:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in clearpart command" % disk)

            self.handler.id.instClass.setClearParts(self.handler.id, self.type,
                                                    drives=self.drives, initAll=self.initAll)

    class Firewall(superclass.Firewall):
        def parse(self, args):
            superclass.Firewall.parse(self, args)

            self.handler.id.instClass.setFirewall(self.handler.id, self.enabled,
                                                  self.trusts, self.ports)

    class Firstboot(superclass.Firstboot):
        def parse(self, args):
            superclass.Firstboot.parse(self, args)
            self.handler.id.firstboot = self.firstboot

    class IgnoreDisk(superclass.IgnoreDisk):
        def parse(self, args):
            superclass.IgnoreDisk.parse(self, args)
            self.handler.id.instClass.setIgnoredDisks(self.handler.id, self.ignoredisk)

    class Iscsi(superclass.Iscsi):
        def parse(self, args):
            superclass.Iscsi.parse(self, args)

            for target in self.iscsi:
                if self.handler.id.iscsi.addTarget(target.ipaddr, target.port, target.user, target.password):
                    log.info("added iscsi target: %s" %(target.ipaddr,))

            # FIXME: flush the drive dict so we figure drives out again
            isys.flushDriveDict()

    class IscsiName(superclass.IscsiName):
        def parse(self, args):
            superclass.IscsiName.parse(self, args)

            self.handler.id.iscsi.initiator = self.iscsiname
            self.handler.id.iscsi.startup()
            # FIXME: flush the drive dict so we figure drives out again        
            isys.flushDriveDict()

    class Keyboard(superclass.Keyboard):
        def parse(self, args):
            superclass.Keyboard.parse(self, args)
            self.handler.id.instClass.setKeyboard(self.handler.id, self.keyboard)
            self.handler.id.keyboard.beenset = 1
            self.handler.skipSteps.append("keyboard")

    class Lang(superclass.Lang):
        def parse(self, args):
            superclass.Lang.parse(self, args)
            self.handler.id.instClass.setLanguage(self.handler.id, self.lang)
            self.handler.skipSteps.append("language")

    class LogVol(superclass.LogVol):
        def parse(self, args):
            superclass.LogVol.parse(self, args)

            lvd = self.lvList[-1]

            if lvd.mountpoint == "swap":
                filesystem = fileSystemTypeGet("swap")
                lvd.mountpoint = ""

                if lvd.recommended:
                    (lvd.size, lvd.maxSizeMB) = iutil.swapSuggestion()
                    lvd.grow = True
            else:
                if lvd.fstype != "":
                    filesystem = fileSystemTypeGet(lvd.fstype)
                else:
                    filesystem = fileSystemTypeGetDefault()

            # sanity check mountpoint
            if lvd.mountpoint != "" and lvd.mountpoint[0] != '/':
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="The mount point \"%s\" is not valid." % (lvd.mountpoint,))

            try:
                vgid = self.handler.ksVGMapping[lvd.vgname]
            except KeyError:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No volume group exists with the name '%s'.  Specify volume groups before logical volumes." % lvd.vgname)

            for areq in self.handler.id.partitions.autoPartitionRequests:
                if areq.type == REQUEST_LV:
                    if areq.volumeGroup == vgid and areq.logicalVolumeName == lvd.name:
                        raise KickstartValueError, formatErrorMsg(self.lineno, msg="Logical volume name already used in volume group %s" % lvd.vgname)
                elif areq.type == REQUEST_VG and areq.uniqueID == vgid:
                    # Store a reference to the VG so we can do the PE size check.
                    vg = areq

            if not self.handler.ksVGMapping.has_key(lvd.vgname):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Logical volume specifies a non-existent volume group" % lvd.name)

            if lvd.percent == 0 and not lvd.preexist:
                if lvd.size == 0:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Size required")
                elif not lvd.grow and lvd.size*1024 < vg.pesize:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Logical volume size must be larger than the volume group physical extent size.")
            elif (lvd.percent <= 0 or lvd.percent > 100) and not lvd.preexist:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Percentage must be between 0 and 100")

            request = partRequests.LogicalVolumeRequestSpec(filesystem,
                                          format = lvd.format,
                                          mountpoint = lvd.mountpoint,
                                          size = lvd.size,
                                          percent = lvd.percent,
                                          volgroup = vgid,
                                          lvname = lvd.name,
                                          grow = lvd.grow,
                                          maxSizeMB = lvd.maxSizeMB,
                                          preexist = lvd.preexist,
                                          bytesPerInode = lvd.bytesPerInode)

            if lvd.fsopts != "":
                request.fsopts = lvd.fsopts

            self.handler.id.instClass.addPartRequest(self.handler.id.partitions, request)
            self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

    class Logging(superclass.Logging):
        def parse(self, args):
            superclass.Logging.parse(self, args)

            log.setHandlersLevel(logLevelMap[self.level])

            if self.host != "" and self.port != "":
                logger.addSysLogHandler(log, self.host, port=int(self.port))
            elif self.host != "":
                logger.addSysLogHandler(log, self.host)

    class Monitor(superclass.Monitor):
        def parse(self, args):
            superclass.Monitor.parse(self, args)
            self.handler.skipSteps.extend(["monitor", "checkmonitorok"])
            self.handler.id.instClass.setMonitor(self.handler.id, self.hsync,
                                                 self.vsync, self.monitor)

    class Network(superclass.Network):
        def parse(self, args):
            superclass.Network.parse(self, args)

            nd = self.network[-1]

            try:
                self.handler.id.instClass.setNetwork(self.handler.id, nd.bootProto, nd.ip,
                                                     nd.netmask, nd.ethtool, nd.device,
                                                     nd.onboot, nd.dhcpclass, nd.essid, nd.wepkey)
            except KeyError:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="The provided network interface %s does not exist" % nd.device)

            if nd.hostname != "":
                self.handler.id.instClass.setHostname(self.handler.id, nd.hostname, override=1)

            if nd.nameserver != "":
                self.handler.id.instClass.setNameserver(self.handler.id, nd.nameserver)

            if nd.gateway != "":
                self.handler.id.instClass.setGateway(self.handler.id, nd.gateway)

    class MultiPath(superclass.MultiPath):
        def parse(self, args):
            superclass.MultiPath.parse(self, args)

            from partedUtils import DiskSet
            ds = DiskSet(self.handler.anaconda)
            ds.startMPath()

            mpath = self.mpaths[-1]
            log.debug("Searching for mpath '%s'" % (mpath.name,))
            for mp in DiskSet.mpList or []:
                it = True
                for dev in mpath.devices:
                    dev = dev.split('/')[-1]
                    log.debug("mpath '%s' has members %s" % (mp.name, list(mp.members)))
                    if not dev in mp.members:
                        log.debug("mpath '%s' does not have device %s, skipping" \
                            % (mp.name, dev))
                        it = False
                if it:
                    log.debug("found mpath '%s', changing name to %s" \
                        % (mp.name, mpath.name))
                    newname = mpath.name
                    ds.renameMPath(mp, newname)
                    return
            ds.startMPath()

    class DmRaid(superclass.DmRaid):
        def parse(self, args):
            superclass.DmRaid.parse(self, args)

            from partedUtils import DiskSet
            ds = DiskSet(self.handler.anaconda)
            ds.startDmRaid()

            raid = self.dmraids[-1]
            log.debug("Searching for dmraid '%s'" % (raid.name,))
            for rs in DiskSet.dmList or []:
                it = True
                for dev in raid.devices:
                    dev = dev.split('/')[-1]
                    log.debug("dmraid '%s' has members %s" % (rs.name, list(rs.members)))
                    if not dev in rs.members:
                        log.debug("dmraid '%s' does not have device %s, skipping" \
                            % (rs.name, dev))
                        it = False
                if it:
                    log.debug("found dmraid '%s', changing name to %s" \
                        % (rs.name, raid.name))
                    # why doesn't rs.name go through the setter here?
                    newname = raid.name
                    ds.renameDmRaid(rs, newname)
                    return
            ds.startDmRaid()

    class Partition(superclass.Partition):
        def parse(self, args):
            superclass.Partition.parse(self, args)

            pd = self.partitions[-1]
            uniqueID = None

            if pd.onbiosdisk != "":
                pd.disk = isys.doGetBiosDisk(pd.onbiosdisk)

                if pd.disk == "":
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified BIOS disk %s cannot be determined" % pd.onbiosdisk)

            if pd.mountpoint == "swap":
                filesystem = fileSystemTypeGet('swap')
                pd.mountpoint = ""
                if pd.recommended:
                    (pd.size, pd.maxSizeMB) = iutil.swapSuggestion()
                    pd.grow = True
            # if people want to specify no mountpoint for some reason, let them
            # this is really needed for pSeries boot partitions :(
            elif pd.mountpoint == "None":
                pd.mountpoint = ""
                if pd.fstype:
                    filesystem = fileSystemTypeGet(pd.fstype)
                else:
                    filesystem = fileSystemTypeGetDefault()
            elif pd.mountpoint == 'appleboot':
                filesystem = fileSystemTypeGet("Apple Bootstrap")
                pd.mountpoint = ""
            elif pd.mountpoint == 'prepboot':
                filesystem = fileSystemTypeGet("PPC PReP Boot")
                pd.mountpoint = ""
            elif pd.mountpoint.startswith("raid."):
                filesystem = fileSystemTypeGet("software RAID")
                
                if self.handler.ksRaidMapping.has_key(pd.mountpoint):
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Defined RAID partition multiple times")
                
                # get a sort of hackish id
                uniqueID = self.handler.ksID
                self.handler.ksRaidMapping[pd.mountpoint] = uniqueID
                self.handler.ksID += 1
                pd.mountpoint = ""
            elif pd.mountpoint.startswith("pv."):
                filesystem = fileSystemTypeGet("physical volume (LVM)")

                if self.handler.ksPVMapping.has_key(pd.mountpoint):
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Defined PV partition multiple times")

                # get a sort of hackish id
                uniqueID = self.handler.ksID
                self.handler.ksPVMapping[pd.mountpoint] = uniqueID
                self.handler.ksID += 1
                pd.mountpoint = ""
            # XXX should we let people not do this for some reason?
            elif pd.mountpoint == "/boot/efi":
                filesystem = fileSystemTypeGet("vfat")
            else:
                if pd.fstype != "":
                    filesystem = fileSystemTypeGet(pd.fstype)
                else:
                    filesystem = fileSystemTypeGetDefault()

            if pd.size is None and (pd.start == 0 and pd.end == 0) and pd.onPart == "":
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Partition requires a size specification")
            if pd.start != 0 and pd.disk == "":
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Partition command with start cylinder requires a drive specification")
            hds = isys.hardDriveDict()
            if not hds.has_key(pd.disk) and hds.has_key('mapper/'+pd.disk):
                pd.disk = 'mapper/' + pd.disk
            if pd.disk != "" and pd.disk not in hds.keys():
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in partition command" % pd.disk)

            request = partRequests.PartitionSpec(filesystem,
                                                 mountpoint = pd.mountpoint,
                                                 format = pd.format,
                                                 fslabel = pd.label,
                                                 bytesPerInode = pd.bytesPerInode)
            
            if pd.size is not None:
                request.size = pd.size
            if pd.start != 0:
                request.start = pd.start
            if pd.end != 0:
                request.end = pd.end
            if pd.grow:
                request.grow = pd.grow
            if pd.maxSizeMB != 0:
                request.maxSizeMB = pd.maxSizeMB
            if pd.disk != "":
                request.drive = [ pd.disk ]
            if pd.primOnly:
                request.primary = pd.primOnly
            if uniqueID:
                request.uniqueID = uniqueID
            if pd.onPart != "":
                request.device = pd.onPart
                for areq in self.handler.id.partitions.autoPartitionRequests:
                    if areq.device is not None and areq.device == pd.onPart:
                        raise KickstartValueError, formatErrorMsg(self.lineno, "Partition already used")

            if pd.fsopts != "":
                request.fsopts = pd.fsopts

            self.handler.id.instClass.addPartRequest(self.handler.id.partitions, request)
            self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

    class Reboot(superclass.Reboot):
        def parse(self, args):
            superclass.Reboot.parse(self, args)
            self.handler.skipSteps.append("complete")

    class Raid(superclass.Raid):
        def parse(self, args):
            superclass.Raid.parse(self, args)

            rd = self.raidList[-1]

            uniqueID = None

            if rd.mountpoint == "swap":
                filesystem = fileSystemTypeGet('swap')
                rd.mountpoint = ""
            elif rd.mountpoint.startswith("pv."):
                filesystem = fileSystemTypeGet("physical volume (LVM)")

                if self.handler.ksPVMapping.has_key(rd.mountpoint):
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Defined PV partition multiple times")

                # get a sort of hackish id
                uniqueID = self.handler.ksID
                self.handler.ksPVMapping[rd.mountpoint] = uniqueID
                self.handler.ksID += 1
                rd.mountpoint = ""
            else:
                if rd.fstype != "":
                    filesystem = fileSystemTypeGet(rd.fstype)
                else:
                    filesystem = fileSystemTypeGetDefault()

            # sanity check mountpoint
            if rd.mountpoint != "" and rd.mountpoint[0] != '/':
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="The mount point is not valid.")

            raidmems = []

            # get the unique ids of each of the raid members
            for member in rd.members:
                if member not in self.handler.ksRaidMapping.keys():
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use undefined partition %s in RAID specification" % member)
                if member in self.handler.ksUsedMembers:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use RAID member %s in two or more RAID specifications" % member)
                    
                raidmems.append(self.handler.ksRaidMapping[member])
                self.handler.ksUsedMembers.append(member)

            if rd.level == "" and not rd.preexist:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="RAID Partition defined without RAID level")
            if len(raidmems) == 0 and not rd.preexist:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="RAID Partition defined without any RAID members")

            request = partRequests.RaidRequestSpec(filesystem,
                                                   mountpoint = rd.mountpoint,
                                                   raidmembers = raidmems,
                                                   raidlevel = rd.level,
                                                   raidspares = rd.spares,
                                                   format = rd.format,
                                                   raidminor = rd.device,
                                                   preexist = rd.preexist)

            if uniqueID is not None:
                request.uniqueID = uniqueID
            if rd.preexist and rd.device != "":
                request.device = "md%s" % rd.device
            if rd.fsopts != "":
                request.fsopts = rd.fsopts

            self.handler.id.instClass.addPartRequest(self.handler.id.partitions, request)
            self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

    class RootPw(superclass.RootPw):
        def parse(self, args):
            superclass.RootPw.parse(self, args)

            self.handler.id.rootPassword["password"] = self.password
            self.handler.id.rootPassword["isCrypted"] = self.isCrypted
            self.handler.skipSteps.append("accounts")

    class SELinux(superclass.SELinux):
        def parse(self, args):
            superclass.SELinux.parse(self, args)
            self.handler.id.instClass.setSELinux(self.handler.id, self.selinux)

    class SkipX(superclass.SkipX):
        def parse(self, args):
            superclass.SkipX.parse(self, args)

            self.handler.skipSteps.extend(["checkmonitorok", "setsanex", "videocard",
                                           "monitor", "xcustom", "writexconfig"])

            if self.handler.id.xsetup is not None:
                self.handler.id.xsetup.skipx = 1

    class Timezone(superclass.Timezone):
        def parse(self, args):
            superclass.Timezone.parse(self, args)

            self.handler.id.instClass.setTimezoneInfo(self.handler.id, self.timezone, self.isUtc)
            self.handler.skipSteps.append("timezone")

    class Upgrade(superclass.Upgrade):
        def parse(self, args):
            superclass.Upgrade.parse(self, args)
            self.handler.id.setUpgrade(self.upgrade)

    class VolGroup(superclass.VolGroup):
        def parse(self, args):
            superclass.VolGroup.parse(self, args)

            vgd = self.vgList[-1]
            pvs = []

            # get the unique ids of each of the physical volumes
            for pv in vgd.physvols:
                if pv not in self.handler.ksPVMapping.keys():
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use undefined partition %s in Volume Group specification" % pv)
                pvs.append(self.handler.ksPVMapping[pv])

            if len(pvs) == 0 and not vgd.preexist:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Volume group defined without any physical volumes.  Either specify physical volumes or use --useexisting.")

            if vgd.pesize not in lvm.getPossiblePhysicalExtents(floor=1024):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Volume group specified invalid pesize")

            # get a sort of hackish id
            uniqueID = self.handler.ksID
            self.handler.ksVGMapping[vgd.vgname] = uniqueID
            self.handler.ksID += 1
                
            request = partRequests.VolumeGroupRequestSpec(vgname = vgd.vgname,
                                                          physvols = pvs,
                                                          preexist = vgd.preexist,
                                                          format = vgd.format,
                                                          pesize = vgd.pesize)
            request.uniqueID = uniqueID
            self.handler.id.instClass.addPartRequest(self.handler.id.partitions, request)

    class XConfig(superclass.XConfig):
        def parse(self, args):
            superclass.XConfig.parse(self, args)

            self.handler.id.instClass.configureX(self.handler.id, self.driver, self.videoRam,
                                                 self.resolution, self.depth,
                                                 self.startX)
            self.handler.id.instClass.setDesktop(self.handler.id, self.defaultdesktop)
            self.handler.skipSteps.extend(["videocard", "monitor", "xcustom",
                                           "checkmonitorok", "setsanex"])

    class ZeroMbr(superclass.ZeroMbr):
        def parse(self, args):
            superclass.ZeroMbr.parse(self, args)
            self.handler.id.instClass.setZeroMbr(self.handler.id, 1)

    class ZFCP(superclass.ZFCP):
        def parse(self, args):
            superclass.ZFCP.parse(self, args)
            for fcp in self.zfcp:
                self.handler.id.zfcp.addFCP(fcp.devnum, fcp.wwpn, fcp.fcplun)

class VNCHandler(superclass):
    # We're only interested in the handler for the VNC command.
    def __init__(self, anaconda=None):
        superclass.__init__(self)
        self.empty()
        self.registerCommand(superclass.Vnc(), ["vnc"])

class KickstartPreParser(KickstartParser):
    def __init__ (self, handler, followIncludes=True,
                  errorsAreFatal=True, missingIncludeIsFatal=True):
        KickstartParser.__init__(self, handler, missingIncludeIsFatal=False)

    def addScript (self):
        if self._state == STATE_PRE:
            s = AnacondaKSScript (self._script["body"], self._script["interp"],
			          self._script["chroot"], self._script["log"],
				  self._script["errorOnFail"])
            self.handler.scripts.append(s)

    def addPackages (self, line):
        pass

    def handleCommand (self, lineno, args):
        pass

    def handlePackageHdr (self, lineno, args):
        pass

    def handleScriptHdr (self, lineno, args):
        if not args[0] == "%pre":
            return

        op = KSOptionParser(lineno=lineno)
        op.add_option("--erroronfail", dest="errorOnFail", action="store_true",
                      default=False)
        op.add_option("--interpreter", dest="interpreter", default="/bin/sh")
        op.add_option("--log", "--logfile", dest="log")

        (opts, extra) = op.parse_args(args=args[1:])

        self._script["interp"] = opts.interpreter
        self._script["log"] = opts.log
        self._script["errorOnFail"] = opts.errorOnFail
        self._script["chroot"] = False

class AnacondaKSParser(KickstartParser):
    def __init__ (self, handler, followIncludes=True,
                  errorsAreFatal=True, missingIncludeIsFatal=True):
        KickstartParser.__init__(self, handler)
        self.sawPackageSection = False

    # Map old broken Everything group to the new futuristic package globs
    def addPackages (self, line):
        if line[0] == '@' and line[1:].lower().strip() == "everything":
            warnings.warn("The Everything group syntax is deprecated.  It may be removed from future releases, which will result in an error from kickstart.  Please use an asterisk on its own line instead.", DeprecationWarning)
            KickstartParser.addPackages(self, "*")
        else:
            KickstartParser.addPackages(self, line)

    def addScript (self):
        if string.join(self._script["body"]).strip() == "":
            return

        s = AnacondaKSScript (self._script["body"], self._script["interp"],
                              self._script["chroot"], self._script["log"],
                              self._script["errorOnFail"], self._script["type"])

        self.handler.scripts.append(s)

    def handlePackageHdr (self, lineno, args):
        self.sawPackageSection = True
        KickstartParser.handlePackageHdr (self, lineno, args)

    def handleCommand (self, lineno, args):
        if not self.handler:
            return

        KickstartParser.handleCommand(self, lineno, args)

cobject = getBaseInstallClass()

# The anaconda kickstart processor.
class Kickstart(cobject):
    name = "kickstart"

    def __init__(self, file, serial):
        self.ksparser = None
        self.serial = serial
        self.file = file

        cobject.__init__(self, 0)

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

    def runPreScripts(self, anaconda):
        preScripts = filter (lambda s: s.type == KS_SCRIPT_PRE,
                             self.ksparser.handler.scripts)

        if len(preScripts) == 0:
            return

	log.info("Running kickstart %%pre script(s)")
        if anaconda.intf is not None:
            w = anaconda.intf.waitWindow(_("Running..."),
                                _("Running pre-install scripts"))
        
        map (lambda s: s.run("/", self.serial, anaconda.intf), preScripts)

	log.info("All kickstart %%pre script(s) have been run")
        if anaconda.intf is not None:
            w.pop()

    def postAction(self, anaconda, serial):
        postScripts = filter (lambda s: s.type == KS_SCRIPT_POST,
                              self.ksparser.handler.scripts)

        if len(postScripts) == 0:
            return

        # Remove environment variables that cause problems for %post scripts.
        for var in ["LIBUSER_CONF"]:
            if os.environ.has_key(var):
                del(os.environ[var])

	log.info("Running kickstart %%post script(s)")
        if anaconda.intf is not None:
            w = anaconda.intf.waitWindow(_("Running..."),
                                _("Running post-install scripts"))
            
        map (lambda s: s.run(anaconda.rootPath, serial, anaconda.intf), postScripts)

	log.info("All kickstart %%post script(s) have been run")
        if anaconda.intf is not None:
            w.pop()

    def runTracebackScripts(self):
	log.info("Running kickstart %%traceback script(s)")
	for script in filter (lambda s: s.type == KS_SCRIPT_TRACEBACK,
                              self.ksparser.handler.scripts):
	    script.run("/", self.serial)
        log.info("All kickstart %%traceback script(s) have been run")

    def setInstallData (self, anaconda):
        BaseInstallClass.setInstallData(self, anaconda)
        self.setEarlySwapOn(1)
        self.anaconda = anaconda
        self.id = self.anaconda.id
        self.id.firstboot = FIRSTBOOT_SKIP

        # make sure our disks are alive
        from partedUtils import DiskSet
        ds = DiskSet(self.anaconda)
        ds.startMPath()
        ds.startDmRaid()

        # parse the %pre
        self.ksparser = KickstartPreParser(AnacondaKSHandler(anaconda))

        try:
            self.ksparser.readKickstart(self.file)
        except KickstartError, e:
           if anaconda.intf:
               anaconda.intf.kickstartErrorWindow(e.__str__())
               sys.exit(0)
           else:
               raise KickstartError, e

        # run %pre scripts
        self.runPreScripts(anaconda)

        # now read the kickstart file for real
        self.handler = AnacondaKSHandler(anaconda)
        self.ksparser = AnacondaKSParser(self.handler)

        try:
            self.ksparser.readKickstart(self.file)
        except KickstartError, e:
            if anaconda.intf:
                anaconda.intf.kickstartErrorWindow(e.__str__())
                sys.exit(0)
            else:
                raise KickstartError, e

        self.id.setKsdata(self.handler)

    def _havePackages(self):
        return len(self.handler.packages.groupList) > 0 or \
               len(self.handler.packages.packageList) > 0 or \
               len(self.handler.packages.excludedList) > 0

    def setSteps(self, anaconda):
        dispatch = anaconda.dispatch
        if self.handler.upgrade.upgrade:
            from upgradeclass import InstallClass
            theUpgradeclass = InstallClass(0)
            theUpgradeclass.setSteps(anaconda)

            # we have no way to specify migrating yet
            dispatch.skipStep("upgrademigfind")
            dispatch.skipStep("upgrademigratefs")
            dispatch.skipStep("upgradecontinue")
            dispatch.skipStep("findinstall", permanent = 1)
            dispatch.skipStep("language")
            dispatch.skipStep("keyboard")
            dispatch.skipStep("betanag")
            dispatch.skipStep("installtype")
        else:
            cobject.setSteps(self, anaconda)
            dispatch.skipStep("findrootparts")

        if self.handler.interactive.interactive or flags.autostep:
            dispatch.skipStep("installtype")
            dispatch.skipStep("bootdisk")

        # because these steps depend on the monitor being probed
        # properly, and will stop you if you have an unprobed monitor,
        # we should skip them for autostep
        if flags.autostep:
            dispatch.skipStep("monitor")
            return

        dispatch.skipStep("bootdisk")
        dispatch.skipStep("betanag")
        dispatch.skipStep("regkey")
        dispatch.skipStep("installtype")
        dispatch.skipStep("tasksel")            
        dispatch.skipStep("network")

        # Don't show confirmation screens on non-interactive installs.
        if not self.handler.interactive.interactive:
            dispatch.skipStep("confirminstall")
            dispatch.skipStep("confirmupgrade")
            dispatch.skipStep("welcome")

        # Make sure to automatically reboot even in interactive if told to.
        if self.handler.interactive.interactive and self.handler.reboot.action != KS_WAIT:
            dispatch.skipStep("complete")

        # If the package section included anything, skip group selection unless
        # they're in interactive.
        if self.handler.upgrade.upgrade:
            self.handler.skipSteps.append("group-selection")

            # Special check for this, since it doesn't make any sense.
            if self._havePackages():
                warnings.warn("Ignoring contents of %packages section due to upgrade.")
        elif self._havePackages():
            if self.handler.interactive.interactive:
                self.handler.showSteps.append("group-selection")
            else:
                self.handler.skipSteps.append("group-selection")
        else:
            if self.ksparser.sawPackageSection:
                self.handler.skipSteps.append("group-selection")
            else:
                self.handler.showSteps.append("group-selection")

        if not self.handler.interactive.interactive:
            for n in self.handler.skipSteps:
                dispatch.skipStep(n)
            for n in self.handler.permanentSkipSteps:
                dispatch.skipStep(n, permanent=1)
        for n in self.handler.showSteps:
            dispatch.skipStep(n, skip = 0)

    def setPackageSelection(self, anaconda, *args):
        for pkg in self.handler.packages.packageList:
            num = anaconda.backend.selectPackage(pkg)
            if self.handler.packages.handleMissing == KS_MISSING_IGNORE:
                continue
            if num > 0:
                continue
            rc = anaconda.intf.messageWindow(_("Missing Package"),
                                    _("You have specified that the "
                                      "package '%s' should be installed.  "
                                      "This package does not exist. "
                                      "Would you like to continue or "
                                      "abort your installation?") %(pkg,),
                                    type="custom",
                                    custom_buttons=[_("_Abort"),
                                                    _("_Continue")])
            if rc == 0:
                sys.exit(1)
            else:
                pass

    def setGroupSelection(self, anaconda, *args):
        # If there wasn't even an empty packages section, use the default
        # group selections.  Otherwise, select whatever was given (even if
        # it's nothing).
        if not self.ksparser.sawPackageSection:
            cobject.setGroupSelection(self, anaconda)
            return

        anaconda.backend.selectGroup("Core")

        if self.handler.packages.addBase:
            anaconda.backend.selectGroup("Base")
        else:
            log.warning("not adding Base group")

        for grp in self.handler.packages.groupList:
            num = anaconda.backend.selectGroup(grp)
            if self.handler.packages.handleMissing == KS_MISSING_IGNORE:
                continue
            if num > 0:
                continue
            rc = anaconda.intf.messageWindow(_("Missing Group"),
                                    _("You have specified that the "
                                      "group '%s' should be installed. "
                                      "This group does not exist. "
                                      "Would you like to continue or "
                                      "abort your installation?")
                                    %(grp,),
                                    type="custom",
                                    custom_buttons=[_("_Abort"),
                                                    _("_Continue")])
            if rc == 0:
                sys.exit(1)
            else:
                pass

        map(anaconda.backend.deselectPackage, self.handler.packages.excludedList)

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

