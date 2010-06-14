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
import zonetab
from pykickstart.constants import *
from pykickstart.parser import *
from pykickstart.data import *
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

        # Always log stdout/stderr from scripts.  Using --logfile just lets you
        # pick where it goes.  The script will also be logged to program.log
        # because of execWithRedirect, and to anaconda.log if the script fails.
        if self.logfile:
            if self.inChroot:
                messages = "%s/%s" % (scriptRoot, self.logfile)
            else:
                messages = self.logfile

            d = os.path.dirname(messages)
            if not os.path.exists(d):
                os.makedirs(d)
        else:
            messages = "%s.log" % path

        if intf:
            intf.suspend()
        rc = iutil.execWithRedirect(self.interp, ["/tmp/%s" % os.path.basename(path)],
                                    stdin = messages, stdout = messages, stderr = messages,
                                    root = scriptRoot)
        if intf:
            intf.resume()

        # Always log an error.  Only fail if we have a handle on the
        # windowing system and the kickstart file included --erroronfail.
        if rc != 0:
            log.error("Error code %s running the kickstart script at line %s" % (rc, self.lineno))

            try:
                f = open(messages, "r")
                err = f.readlines()
                f.close()
                for l in err:
                    log.error("\t%s" % l)
            except:
                err = None

            if self.errorOnFail:
                if intf != None:
                    msg = _("There was an error running the kickstart "
                            "script at line %(lineno)s.  You may examine the "
                            "output in %(msgs)s.  This is a fatal error and "
                            "installation will be aborted.  Press the "
                            "OK button to exit the installer.") \
                          % {'lineno': self.lineno, 'msgs': messages}

                    if err:
                        intf.detailedMessageWindow(_("Scriptlet Failure"), msg, err)
                    else:
                        intf.messageWindow(_("Scriptlet Failure"), msg)

                sys.exit(0)

        if serial or self.logfile is not None:
            os.chmod("%s" % messages, 0600)

class AnacondaKSHandlers(KickstartHandlers):
    def __init__ (self, ksdata, anaconda):
        KickstartHandlers.__init__(self, ksdata)
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

        self.lineno = 0
        self.currentCmd = ""

    def doAuthconfig(self, args):
        KickstartHandlers.doAuthconfig(self, args)
        self.id.auth = self.ksdata.authconfig

    def doAutoPart(self, args):
        KickstartHandlers.doAutoPart(self, args)

        # sets up default autopartitioning.  use clearpart separately
        # if you want it
        self.id.instClass.setDefaultPartitioning(self.id, doClear = 0)

        if self.ksdata.encrypted:
            self.id.partitions.autoEncrypt = True
            self.id.partitions.encryptionPassphrase = self.ksdata.passphrase

        self.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

    def doAutoStep(self, args):
        KickstartHandlers.doAutoStep(self, args)
        flags.autostep = 1
        flags.autoscreenshot = self.ksdata.autostep["autoscreenshot"]

    def doBootloader (self, args):
        KickstartHandlers.doBootloader(self, args)
        dict = self.ksdata.bootloader
        self.id.bootloader.updateDriveList()

        if dict["location"] == "none":
            location = None
        elif dict["location"] == "partition":
            location = "boot"
        else:
            location = dict["location"]

        if dict["upgrade"] and not self.id.getUpgrade():
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Selected upgrade mode for bootloader but not doing an upgrade")

        if dict["upgrade"]:
            self.id.bootloader.kickstart = 1
            self.id.bootloader.doUpgradeOnly = 1

        if location is None:
            self.permanentSkipSteps.extend(["bootloadersetup", "instbootloader"])
        else:
            self.showSteps.append("bootloader")
            self.id.instClass.setBootloader(self.id, location, dict["forceLBA"],
                                            dict["password"], dict["md5pass"],
                                            dict["appendLine"], dict["driveorder"],
                                            dict["hvArgs"])

        self.permanentSkipSteps.extend(["upgbootloader", "bootloader",
                                        "bootloaderadvanced"])

    def doClearPart(self, args):
        KickstartHandlers.doClearPart(self, args)
        dict = self.ksdata.clearpart

        hds = isys.hardDriveDict().keys()
        for disk in dict["drives"]:
            if disk not in hds:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in clearpart command" % disk)

        self.id.instClass.setClearParts(self.id, dict["type"], drives=dict["drives"],
                                        initAll=dict["initAll"])

    def doFirewall(self, args):
        KickstartHandlers.doFirewall(self, args)
        dict = self.ksdata.firewall
	self.id.instClass.setFirewall(self.id, dict["enabled"], dict["trusts"],
                                      dict["ports"])

    def doFirstboot(self, args):
        KickstartHandlers.doFirstboot(self, args)
        self.id.firstboot = self.ksdata.firstboot

    def doIgnoreDisk(self, args):
	KickstartHandlers.doIgnoreDisk(self, args)
        self.id.instClass.setIgnoredDisks(self.id, 
                                          self.ksdata.ignoredisk["drives"])
        self.id.instClass.setExclusiveDisks(self.id,
                                            self.ksdata.ignoredisk["onlyuse"])

    def doIscsi(self, args):
        KickstartHandlers.doIscsi(self, args)

        for target in self.ksdata.iscsi:
            kwargs = {
                'ipaddr': target.ipaddr,
                'port': target.port,
                }
            if target.user and target.password:
                kwargs.update({
                    'user': target.user,
                    'pw': target.password
                    })
            if target.user_in and target.password_in:
                kwargs.update({
                    'user_in': target.user_in,
                    'pw_in': target.password_in
                    })

            if self.id.iscsi.addTarget(**kwargs):
                log.info("added iscsi target: %s" %(target.ipaddr,))

        # FIXME: flush the drive dict so we figure drives out again
        isys.flushDriveDict()

    def doIscsiName(self, args):
        KickstartHandlers.doIscsiName(self, args)
        self.id.iscsi.initiator = self.ksdata.iscsiname
        self.id.iscsi.startup()

    def doKey(self, args):
        KickstartHandlers.doKey(self, args)
        if self.ksdata.key == KS_INSTKEY_SKIP:
            log.info("skipping install key")
            self.skipSteps.append("regkey")
            self.id.instClass.skipkey = True
            self.id.instClass.installkey = None
        else:
            log.info("setting install key to %s" %(self.ksdata.key,))
            self.id.instClass.skipkey = False
            self.id.instClass.installkey = self.ksdata.key

    def doKeyboard(self, args):
        KickstartHandlers.doKeyboard(self, args)
        self.id.instClass.setKeyboard(self.id, self.ksdata.keyboard)
        self.id.keyboard.beenset = 1
	self.skipSteps.append("keyboard")

    def doLang(self, args):
        KickstartHandlers.doLang(self, args)
        self.id.instClass.setLanguage(self.id, self.ksdata.lang)
	self.skipSteps.append("language")

    def doLogicalVolume(self, args):
        KickstartHandlers.doLogicalVolume(self, args)
        lvd = self.ksdata.lvList[-1]

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
            vgid = self.ksVGMapping[lvd.vgname]
        except KeyError:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="No volume group exists with the name '%s'.  Specify volume groups before logical volumes." % lvd.vgname)

	for areq in self.id.partitions.autoPartitionRequests:
	    if areq.type == REQUEST_LV:
		if areq.volumeGroup == vgid and areq.logicalVolumeName == lvd.name:
		    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Logical volume name already used in volume group %s" % lvd.vgname)
            elif areq.type == REQUEST_VG and areq.uniqueID == vgid:
                # Store a reference to the VG so we can do the PE size check.
                vg = areq

        if not self.ksVGMapping.has_key(lvd.vgname):
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

        if lvd.encrypted:
            try:
                passphrase = lvd.passphrase
            except AttributeError:
                passphrase = ""

            if passphrase and not self.id.partitions.encryptionPassphrase:
                self.id.partitions.encryptionPassphrase = passphrase

            request.encryption = cryptodev.LUKSDevice(passphrase=passphrase, format=lvd.format)

        self.id.instClass.addPartRequest(self.id.partitions, request)
        self.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

    def doLogging(self, args):
        KickstartHandlers.doLogging(self, args)
        log.setHandlersLevel(logLevelMap[self.ksdata.logging["level"]])

        if self.ksdata.logging["host"] != "" and self.ksdata.logging["port"] != "":
            logger.addSysLogHandler(log, self.ksdata.logging["host"],
                                    port=int(self.ksdata.logging["port"]))
        elif self.ksdata.logging["host"] != "":
            logger.addSysLogHandler(log, self.ksdata.logging["host"])

    def doMonitor(self, args):
        KickstartHandlers.doMonitor(self, args)
        if self.id.isHeadless:
            return

        dict = self.ksdata.monitor
        self.skipSteps.extend(["monitor", "checkmonitorok"])
        self.id.instClass.setMonitor(self.id, dict["hsync"], dict["vsync"],
                                     dict["monitor"])

    def doNetwork(self, args):
        KickstartHandlers.doNetwork(self, args)
        nd = self.ksdata.network[-1]

        try:
            self.id.instClass.setNetwork(self.id, nd.bootProto, nd.ip, nd.netmask,
                                         nd.ethtool, nd.device, nd.onboot,
                                         nd.dhcpclass, nd.essid, nd.wepkey)
        except KeyError:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The provided network interface %s does not exist" % nd.device)

        if nd.hostname != "":
            self.id.instClass.setHostname(self.id, nd.hostname, override=1)

        if nd.nameserver != "":
            self.id.instClass.setNameserver(self.id, nd.nameserver)

        if nd.gateway != "":
            self.id.instClass.setGateway(self.id, nd.gateway)

    def doMultiPath(self, args):
        KickstartHandlers.doMultiPath(self, args)

        from partedUtils import DiskSet
        ds = DiskSet(self.anaconda)
        ds.startMPath()

        from bdevid import bdevid as _bdevid
        bd = _bdevid()
        bd.load("scsi")

        mpath = self.ksdata.mpaths[-1]
        for mp in DiskSet.mpList or []:
            newname = ""
            it = True
            for path in mpath.paths:
                dev = path.device
                log.debug("Searching for mpath having '%s' as a member, the scsi id or wwpn:lunid" % (dev,))
                log.debug("mpath '%s' has members %s" % (mp.name, list(mp.members)))
                if dev.find(':') != -1:
                    (wwpn, lunid) = dev.split(':')
                    if wwpn != "" and lunid != "":
                        if wwpn.startswith("0x"):
                            wwpn = wwpn[2:]
                        wwpn = wwpn.upper()
                        scsidev = iutil.getScsiDeviceByWwpnLunid(wwpn, lunid)
                        if scsidev != "":
                            dev = "/dev/%s" % scsidev
                            log.debug("'%s' is a member of the multipath device WWPN '%s' LUNID '%s'" % (dev, wwpn, lunid))
                if not dev in mp.members:
                    mpscsiid = bd.probe("/dev/mapper/%s" % mp.name)[0]['unique_id']
                    if dev != mpscsiid:
                        log.debug("mpath '%s' does not have device %s, skipping" \
                            % (mp.name, dev))
                        it = False
                    else:
                        log.debug("Recognized --device=%s as the scsi id of '%s'" % (dev, mp.name))
                        newname = path.name
                        break
                else:
                    log.debug("Recognized --device=%s as a member of '%s'" % (dev, mp.name))
                    newname = path.name
                    break
            if it and mp.name != newname:
                log.debug("found mpath '%s', changing name to %s" \
                    % (mp.name, newname))
                mpath.name = mp.name
                ds.renameMPath(mp, newname)
                bd.unload("scsi")
                return
        bd.unload("scsi")
        ds.startMPath()

    def doDmRaid(self, args):
        KickstartHandlers.doDmRaid(self, args)

        from partedUtils import DiskSet
        ds = DiskSet(self.anaconda)
        ds.startDmRaid()

        raid = self.ksdata.dmraids[-1]
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

    def doPartition(self, args):
        KickstartHandlers.doPartition(self, args)
        pd = self.ksdata.partitions[-1]
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
            
            if self.ksRaidMapping.has_key(pd.mountpoint):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Defined RAID partition multiple times")

            if pd.encrypted:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Software RAID partitions cannot be encrypted")
            
            # get a sort of hackish id
            uniqueID = self.ksID
            self.ksRaidMapping[pd.mountpoint] = uniqueID
            self.ksID += 1
            pd.mountpoint = ""
        elif pd.mountpoint.startswith("pv."):
            filesystem = fileSystemTypeGet("physical volume (LVM)")

            if self.ksPVMapping.has_key(pd.mountpoint):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Defined PV partition multiple times")

            # get a sort of hackish id
            uniqueID = self.ksID
            self.ksPVMapping[pd.mountpoint] = uniqueID
            self.ksID += 1
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
            for areq in self.id.partitions.autoPartitionRequests:
                if areq.device is not None and areq.device == pd.onPart:
		    raise KickstartValueError, formatErrorMsg(self.lineno, "Partition already used")

        if pd.fsopts != "":
            request.fsopts = pd.fsopts

        if pd.encrypted:
            try:
                passphrase = pd.passphrase
            except AttributeError:
                passphrase = ""

            if passphrase and not self.id.partitions.encryptionPassphrase:
                self.id.partitions.encryptionPassphrase = passphrase

            request.encryption = cryptodev.LUKSDevice(passphrase=passphrase, format=pd.format)

        self.id.instClass.addPartRequest(self.id.partitions, request)
        self.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

    def doReboot(self, args):
        KickstartHandlers.doReboot(self, args)
        self.skipSteps.append("complete")

    def doRaid(self, args):
        KickstartHandlers.doRaid(self, args)
        rd = self.ksdata.raidList[-1]

	uniqueID = None

        if rd.mountpoint == "swap":
            filesystem = fileSystemTypeGet('swap')
            rd.mountpoint = ""
        elif rd.mountpoint.startswith("pv."):
            filesystem = fileSystemTypeGet("physical volume (LVM)")

            if self.ksPVMapping.has_key(rd.mountpoint):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Defined PV partition multiple times")

            # get a sort of hackish id
            uniqueID = self.ksID
            self.ksPVMapping[rd.mountpoint] = uniqueID
            self.ksID += 1
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
            if member not in self.ksRaidMapping.keys():
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use undefined partition %s in RAID specification" % member)
	    if member in self.ksUsedMembers:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use RAID member %s in two or more RAID specifications" % member)
		
            raidmems.append(self.ksRaidMapping[member])
	    self.ksUsedMembers.append(member)

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

        if rd.encrypted:
            try:
                passphrase = rd.passphrase
            except AttributeError:
                passphrase = ""

            if passphrase and not self.id.partitions.encryptionPassphrase:
                self.id.partitions.encryptionPassphrase = passphrase

            request.encryption = cryptodev.LUKSDevice(passphrase=passphrase, format=rd.format)

        self.id.instClass.addPartRequest(self.id.partitions, request)
        self.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

    def doRootPw(self, args):
        KickstartHandlers.doRootPw(self, args)
        dict = self.ksdata.rootpw

        self.id.rootPassword["password"] = dict["password"]
        self.id.rootPassword["isCrypted"] = dict["isCrypted"]
        self.skipSteps.append("accounts")

    def doSELinux(self, args):
        KickstartHandlers.doSELinux(self, args)
        self.id.instClass.setSELinux(self.id, self.ksdata.selinux)

    def doSkipX(self, args):
        KickstartHandlers.doSkipX(self, args)
        self.skipSteps.extend(["checkmonitorok", "setsanex", "videocard",
                               "monitor", "xcustom", "writexconfig"])

        if self.id.xsetup is not None:
            self.id.xsetup.skipx = 1

    def doTimezone(self, args):
        KickstartHandlers.doTimezone(self, args)
        dict = self.ksdata.timezone
        # check validity
        tab = zonetab.ZoneTab()
        if dict["timezone"] not in (entry.tz.replace(' ','_') for entry in
                                 tab.getEntries()):
            log.warning("Timezone %s set in kickstart is not valid." % (dict["timezone"],))

	self.id.instClass.setTimezoneInfo(self.id, dict["timezone"], dict["isUtc"])
	self.skipSteps.append("timezone")

    def doUpgrade(self, args):
        KickstartHandlers.doUpgrade(self, args)
        self.id.setUpgrade(True)

    def doVolumeGroup(self, args):
        KickstartHandlers.doVolumeGroup(self, args)
        vgd = self.ksdata.vgList[-1]

        pvs = []

        # get the unique ids of each of the physical volumes
        for pv in vgd.physvols:
            if pv not in self.ksPVMapping.keys():
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use undefined partition %s in Volume Group specification" % pv)
            pvs.append(self.ksPVMapping[pv])

        if len(pvs) == 0 and not vgd.preexist:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Volume group defined without any physical volumes.  Either specify physical volumes or use --useexisting.")

        if vgd.pesize not in lvm.getPossiblePhysicalExtents(floor=1024):
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Volume group specified invalid pesize")

        # get a sort of hackish id
        uniqueID = self.ksID
        self.ksVGMapping[vgd.vgname] = uniqueID
        self.ksID += 1

        request = partRequests.VolumeGroupRequestSpec(vgname = vgd.vgname,
                                                      physvols = pvs,
                                                      preexist = vgd.preexist,
                                                      format = vgd.format,
                                                      pesize = vgd.pesize)
        request.uniqueID = uniqueID
        self.id.instClass.addPartRequest(self.id.partitions, request)

    def doXConfig(self, args):
        KickstartHandlers.doXConfig(self, args)
        if self.id.isHeadless:
            return

        dict = self.ksdata.xconfig

        self.id.instClass.configureX(self.id, dict["driver"], dict["videoRam"],
                                     dict["resolution"], dict["depth"],
                                     dict["startX"])
        self.id.instClass.setDesktop(self.id, dict["defaultdesktop"])
        self.skipSteps.extend(["videocard", "monitor", "xcustom",
                               "checkmonitorok", "setsanex"])

    def doZeroMbr(self, args):
        KickstartHandlers.doZeroMbr(self, args)
        self.id.instClass.setZeroMbr(self.id, 1)

    def doZFCP(self, args):
        KickstartHandlers.doZFCP(self, args)
        for fcp in self.ksdata.zfcp:
            self.id.zfcp.addFCP(fcp.devnum, fcp.wwpn, fcp.fcplun)

        isys.flushDriveDict()

class VNCHandlers(KickstartHandlers):
    # We're only interested in the handler for the VNC command and display modes.
    def __init__ (self, ksdata):
        KickstartHandlers.__init__(self, ksdata)
        self.resetHandlers()
        self.handlers["vnc"] = self.doVnc
        
        self.handlers["text"] = self.doDisplayMode
        self.handlers["cmdline"] = self.doDisplayMode
        self.handlers["graphical"] = self.doDisplayMode

class KickstartPreParser(KickstartParser):
    def __init__ (self, ksdata, kshandlers):
        self.handler = kshandlers
        KickstartParser.__init__(self, ksdata, kshandlers,
                                 missingIncludeIsFatal=False)

    def addScript (self):
        if self.state == STATE_PRE:
            s = AnacondaKSScript (self.script["body"], self.script["interp"],
			          self.script["chroot"], self.script["log"],
				  self.script["errorOnFail"])
            self.ksdata.scripts.append(s)

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

        self.script["interp"] = opts.interpreter
        self.script["log"] = opts.log
        self.script["errorOnFail"] = opts.errorOnFail
        self.script["chroot"] = False

class AnacondaKSParser(KickstartParser):
    def __init__ (self, ksdata, kshandlers):
        self.sawPackageSection = False
        KickstartParser.__init__(self, ksdata, kshandlers)

    # Map old broken Everything group to the new futuristic package globs
    def addPackages (self, line):
        if line[0] == '@' and line[1:].lower().strip() == "everything":
            warnings.warn("The Everything group syntax is deprecated.  It may be removed from future releases, which will result in an error from kickstart.  Please use an asterisk on its own line instead.", DeprecationWarning)
            KickstartParser.addPackages(self, "*")
        else:
            KickstartParser.addPackages(self, line)

    def addScript (self):
        if string.join(self.script["body"]).strip() == "":
            return

        s = AnacondaKSScript (self.script["body"], self.script["interp"],
                              self.script["chroot"], self.script["log"],
                              self.script["errorOnFail"], self.script["type"])

        self.ksdata.scripts.append(s)

    def handlePackageHdr (self, lineno, args):
        self.sawPackageSection = True
        KickstartParser.handlePackageHdr (self, lineno, args)

    def handleCommand (self, lineno, args):
        if not self.handler:
            return

        cmd = args[0]
        cmdArgs = args[1:]

        if not self.handler.handlers.has_key(cmd):
            raise KickstartParseError, formatErrorMsg(lineno)
        else:
            if self.handler.handlers[cmd] != None:
                self.handler.currentCmd = cmd
                self.handler.lineno = lineno
                self.handler.handlers[cmd](cmdArgs)

cobject = getBaseInstallClass()

# The anaconda kickstart processor.
class Kickstart(cobject):
    name = "kickstart"

    def __init__(self, file, serial):
        self.ksdata = None
        self.handlers = None
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
                             self.ksdata.scripts)

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
                              self.ksdata.scripts)

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
                              self.ksdata.scripts):
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
        self.ksdata = KickstartData()
        self.ksparser = KickstartPreParser(self.ksdata, None)

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
        self.ksdata = KickstartData()
        self.handlers = AnacondaKSHandlers(self.ksdata, anaconda)
        self.ksparser = AnacondaKSParser(self.ksdata, self.handlers)

        try:
            self.ksparser.readKickstart(self.file)
        except KickstartError, e:
            if anaconda.intf:
                anaconda.intf.kickstartErrorWindow(e.__str__())
                sys.exit(0)
            else:
                raise KickstartError, e

        self.id.setKsdata(self.ksdata)

    def _havePackages(self):
        return len(self.ksdata.groupList) > 0 or len(self.ksdata.packageList) > 0 or \
               len(self.ksdata.excludedList) > 0 or len(self.ksdata.excludedGroupList)

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
            dispatch.skipStep("betanag")
            dispatch.skipStep("installtype")
        else:
            cobject.setSteps(self, dispatch)
            dispatch.skipStep("findrootparts")

        if self.ksdata.interactive or flags.autostep:
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
        dispatch.skipStep("installtype")
        dispatch.skipStep("tasksel")            

        # Only skip the network screen if there are no devices that used
        # network --bootproto=query.
        if not self.id.network.query:
            dispatch.skipStep("network")

        # Don't show confirmation screens on non-interactive installs.
        if not self.ksdata.interactive:
            dispatch.skipStep("confirminstall")
            dispatch.skipStep("confirmupgrade")
            dispatch.skipStep("welcome")

        # Make sure to automatically reboot even in interactive if told to.
        if self.ksdata.interactive and self.ksdata.reboot["action"] != KS_WAIT:
            dispatch.skipStep("complete")

        # If the package section included anything, skip group selection unless
        # they're in interactive.
        if self.ksdata.upgrade:
            self.handlers.skipSteps.append("group-selection")

            # Special check for this, since it doesn't make any sense.
            if self._havePackages():
                warnings.warn("Ignoring contents of %packages section due to upgrade.")
        elif self._havePackages():
            if self.ksdata.interactive:
                self.handlers.showSteps.append("group-selection")
            else:
                self.handlers.skipSteps.append("group-selection")
        else:
            if self.ksparser.sawPackageSection:
                self.handlers.skipSteps.append("group-selection")
            else:
                self.handlers.showSteps.append("group-selection")

        if not self.ksdata.interactive:
            for n in self.handlers.skipSteps:
                dispatch.skipStep(n)
            for n in self.handlers.permanentSkipSteps:
                dispatch.skipStep(n, permanent=1)
        for n in self.handlers.showSteps:
            dispatch.skipStep(n, skip = 0)

    def setPackageSelection(self, anaconda, *args):
        for pkg in self.ksdata.packageList:
            num = anaconda.backend.selectPackage(pkg)
            if self.ksdata.handleMissing == KS_MISSING_IGNORE:
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

        if self.ksdata.addBase:
            anaconda.backend.selectGroup("Base")
        else:
            log.warning("not adding Base group")

        for grp in self.ksdata.groupList:
            num = anaconda.backend.selectGroup(grp)
            if self.ksdata.handleMissing == KS_MISSING_IGNORE:
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

        map(anaconda.backend.deselectPackage, self.ksdata.excludedList)
        map(anaconda.backend.removeGroupsPackages, self.ksdata.excludedGroupList)

# look through ksfile and if it contains any lines:
#
# %ksappend <url>
#
# pull <url> down and stick it in /tmp/ks.cfg in place of the %ksappend line.
# This is run before we actually parse the complete kickstart file.
#
# Main use is to have the ks.cfg you send to the loader be minimal, and then
# use %ksappend to pull via https anything private (like passwords, etc) in
# the second stage.
def pullRemainingKickstartConfig(ksfile):
    import tempfile

    # Open the input kickstart file and read it all into a list.
    try:
        inF = open(ksfile, "r")
    except:
        raise KickstartError ("Unable to open ks file %s for reading" % ksfile)

    lines = inF.readlines()
    inF.close()

    # Now open an output kickstart file that we are going to write to one
    # line at a time.
    (outF, outName) = tempfile.mkstemp("-ks.cfg", "", "/tmp")

    for l in lines:
        url = None

        ll = l.strip()
        if not ll.startswith("%ksappend"):
            os.write(outF, l)
            continue

        # Try to pull down the remote file.
        try:
            ksurl = string.split(ll, ' ')[1]
        except:
            raise KickstartError ("Illegal url for %%ksappend: %s" % ll)

	log.info("Attempting to pull additional part of ks.cfg from url %s" % ksurl)

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

        # If that worked, now write the remote file to the output kickstart
        # file in one burst.  Then close everything up to get ready to read
        # farther ahead in the input file.  This allows multiple %ksappend
        # lines to exist.
        if url is not None:
            os.write(outF, url.read())
            url.close()

    # All done - move the temp output file to the expected location.
    os.close(outF)
    os.rename(outName, "/tmp/ks.cfg")
    return None

