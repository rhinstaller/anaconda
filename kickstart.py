#
# kickstart.py: kickstart install support
#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007
# Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from errors import *
import iutil
import isys
import os
import tempfile
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
import upgrade
import pykickstart.commands as commands
import cryptodev
from pykickstart.constants import *
from pykickstart.errors import *
from pykickstart.parser import *
from pykickstart.version import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

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
            if self.inChroot:
                messages = "%s/%s" % (scriptRoot, self.logfile)
            else:
                messages = self.logfile
        elif serial:
            messages = "%s.log" % path
        else:
            messages = "/dev/tty3"

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
            log.error("Error code %s encountered running the kickstart script at line %s" % (rc, self.lineno))

            if self.errorOnFail:
                if intf != None:
                    err = None
                    msg = _("There was an error running the kickstart "
                            "script at line %s.  You may examine the "
                            "output in %s.  This is a fatal error and "
                            "your install will be aborted.  Press the "
                            "OK button to exit the installer.") % (self.lineno, messages)

                    if self.logfile is not None and os.path.isfile(messages):
                        try:
                            f = open(messages, "r")
                            err = f.readlines()
                            f.close()
                        except:
                            pass

                    if err is None:
                        intf.messageWindow(_("Scriptlet Failure"), msg)
                    else:
                        intf.detailedMessageWindow(_("Scriptlet Failure"), msg,
                                                   err)

                sys.exit(0)

        try:
            os.unlink(path)
        except:
            pass

        if serial or self.logfile is not None:
            os.chmod("%s" % messages, 0600)

class AnacondaKSPackages(Packages):
    def __init__(self):
        Packages.__init__(self)

        # Has the %packages section been seen at all?
        self.seen = False


###
### SUBCLASSES OF PYKICKSTART COMMAND HANDLERS
###

class Authconfig(commands.authconfig.FC3_Authconfig):
    def parse(self, args):
        commands.authconfig.FC3_Authconfig.parse(self, args)
        self.handler.id.auth = self.authconfig

class AutoPart(commands.autopart.F9_AutoPart):
    def parse(self, args):
        commands.autopart.F9_AutoPart.parse(self, args)

        # sets up default autopartitioning.  use clearpart separately
        # if you want it
        self.handler.id.instClass.setDefaultPartitioning(self.handler.id, doClear = 0)

        if self.encrypted:
            self.handler.id.partitions.autoEncrypt = True
            self.handler.id.partitions.encryptionPassphrase = self.passphrase

        self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

class AutoStep(commands.autostep.FC3_AutoStep):
    def parse(self, args):
        commands.autostep.FC3_AutoStep.parse(self, args)
        flags.autostep = 1
        flags.autoscreenshot = self.autoscreenshot

class Bootloader(commands.bootloader.F8_Bootloader):
    def parse(self, args):
        commands.bootloader.F8_Bootloader.parse(self, args)

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

        if self.driveorder:
            hds = isys.hardDriveDict().keys()
            for disk in self.driveorder:
                if disk not in hds:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in driveorder command" % disk)

        if location is None:
            self.handler.permanentSkipSteps.extend(["bootloadersetup", "instbootloader"])
        else:
            self.handler.showSteps.append("bootloader")

            if self.appendLine:
                self.handler.id.bootloader.args.set(self.appendLine)

            self.handler.id.bootloader.setForceLBA(self.forceLBA)

            if self.password:
                self.handler.id.bootloader.setPassword(self.password, isCrypted = 0)

            if self.md5pass:
                self.handler.id.bootloader.setPassword(self.md5pass)

            if location != None:
                self.handler.id.bootloader.defaultDevice = location
            else:
                self.handler.id.bootloader.defaultDevice = -1

            if self.timeout:
                self.handler.id.bootloader.timeout = self.timeout

            # XXX throw out drives specified that don't exist.  anything else
            # seems silly
            if self.driveorder and len(self.driveorder) > 0:
                new = []
                for drive in self.driveorder:
                    if drive in self.handler.id.bootloader.drivelist:
                        new.append(drive)
                    else:
                        log.warning("requested drive %s in boot drive order "
                                    "doesn't exist" %(drive,))

                self.handler.id.bootloader.drivelist = new

        self.handler.permanentSkipSteps.extend(["upgbootloader", "bootloader"])

class ClearPart(commands.clearpart.FC3_ClearPart):
    def parse(self, args):
        commands.clearpart.FC3_ClearPart.parse(self, args)

        if self.type is None:
            self.type = CLEARPART_TYPE_NONE

        hds = isys.hardDriveDict().keys()
        for disk in self.drives:
            if disk not in hds:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in clearpart command" % disk)

        self.handler.id.partitions.autoClearPartType = self.type
        self.handler.id.partitions.autoClearPartDrives = self.drives
        if self.initAll:
            self.handler.id.partitions.reinitializeDisks = self.initAll

class Firewall(commands.firewall.F10_Firewall):
    def parse(self, args):
        commands.firewall.F10_Firewall.parse(self, args)
        self.handler.id.firewall.enabled = self.enabled
        self.handler.id.firewall.trustdevs = self.trusts

        for port in self.ports:
            self.handler.id.firewall.portlist.append (port)

class Firstboot(commands.firstboot.FC3_Firstboot):
    def parse(self, args):
        commands.firstboot.FC3_Firstboot.parse(self, args)
        self.handler.id.firstboot = self.firstboot

class IgnoreDisk(commands.ignoredisk.F8_IgnoreDisk):
    def parse(self, args):
        commands.ignoredisk.F8_IgnoreDisk.parse(self, args)

        diskset = self.handler.id.diskset
        for drive in self.ignoredisk:
            if not drive in diskset.skippedDisks:
                diskset.skippedDisks.append(drive)

        diskset = self.handler.id.diskset
        for drive in self.onlyuse:
            if not drive in diskset.exclusiveDisks:
                diskset.exclusiveDisks.append(drive)

class Iscsi(commands.iscsi.F10_Iscsi):
    def parse(self, args):
        commands.iscsi.F10_Iscsi.parse(self, args)

        for target in self.iscsi:
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

            if self.handler.id.iscsi.addTarget(**kwargs):
                log.info("added iscsi target: %s" %(target.ipaddr,))

        # FIXME: flush the drive dict so we figure drives out again
        isys.flushDriveDict()

class IscsiName(commands.iscsiname.FC6_IscsiName):
    def parse(self, args):
        commands.iscsiname.FC6_IscsiName.parse(self, args)

        self.handler.id.iscsi.initiator = self.iscsiname
        self.handler.id.iscsi.startIBFT()
        # FIXME: flush the drive dict so we figure drives out again
        isys.flushDriveDict()

class Keyboard(commands.keyboard.FC3_Keyboard):
    def parse(self, args):
        commands.keyboard.FC3_Keyboard.parse(self, args)
        self.handler.id.keyboard.set(self.keyboard)
        self.handler.id.keyboard.beenset = 1
        self.handler.skipSteps.append("keyboard")

class Lang(commands.lang.FC3_Lang):
    def parse(self, args):
        commands.lang.FC3_Lang.parse(self, args)
        self.handler.id.instLanguage.setRuntimeLanguage(self.lang)
        self.handler.skipSteps.append("language")

class LogVol(commands.logvol.F9_LogVol):
    def parse(self, args):
        commands.logvol.F9_LogVol.parse(self, args)

        lvd = self.lvList[-1]

        if lvd.mountpoint == "swap":
            filesystem = fileSystemTypeGet("swap")
            lvd.mountpoint = ""

            if lvd.recommended:
                (lvd.size, lvd.maxSizeMB) = iutil.swapSuggestion()
                lvd.grow = True
        else:
            if lvd.fstype != "":
                try:
                    filesystem = fileSystemTypeGet(lvd.fstype)
                except KeyError:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % lvd.fstype)
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
                                      fsprofile = lvd.fsprofile)

        if lvd.fsopts != "":
            request.fsopts = lvd.fsopts

        if lvd.encrypted:
            if lvd.passphrase and \
               not self.handler.anaconda.id.partitions.encryptionPassphrase:
                self.handler.anaconda.id.partitions.encryptionPassphrase = lvd.passphrase
            request.encryption = cryptodev.LUKSDevice(passphrase=lvd.passphrase, format=lvd.format)

        addPartRequest(self.handler.anaconda, request)
        self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

class Logging(commands.logging.FC6_Logging):
    def parse(self, args):
        commands.logging.FC6_Logging.parse(self, args)

        log.setHandlersLevel(logLevelMap[self.level])

        if self.host != "" and self.port != "":
            logger.addSysLogHandler(log, self.host, port=int(self.port))
        elif self.host != "":
            logger.addSysLogHandler(log, self.host)

class Network(commands.network.F8_Network):
    def parse(self, args):
        commands.network.F8_Network.parse(self, args)

        nd = self.network[-1]

        if nd.bootProto:
            devices = self.handler.id.network.netdevices
            if (devices and nd.bootProto):
                if not nd.device:
                    list = devices.keys ()
                    list.sort()
                    device = list[0]
                else:
                    device = nd.device

                try:
                    dev = devices[device]
                except KeyError:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="The provided network interface %s does not exist" % device)

                dev.set (("bootproto", nd.bootProto))
                dev.set (("dhcpclass", nd.dhcpclass))

                if nd.onboot:
                    dev.set (("onboot", "yes"))
                else:
                    dev.set (("onboot", "no"))

                if nd.bootProto == "static":
                    if (nd.ip):
                        dev.set (("ipaddr", nd.ip))
                    if (nd.netmask):
                        dev.set (("netmask", nd.netmask))

                if nd.ethtool:
                    dev.set (("ethtool_opts", nd.ethtool))

                if isys.isWireless(device):
                    if nd.essid:
                        dev.set(("essid", nd.essid))
                    if nd.wepkey:
                        dev.set(("wepkey", nd.wepkey))

        if nd.hostname != "":
            self.handler.id.network.setHostname(nd.hostname)
            self.handler.id.network.overrideDHCPhostname = True

        if nd.nameserver != "":
            self.handler.id.network.setDNS(nd.nameserver, device)

        if nd.gateway != "":
            self.handler.id.network.setGateway(nd.gateway, device)

class MultiPath(commands.multipath.FC6_MultiPath):
    def parse(self, args):
        commands.multipath.FC6_MultiPath.parse(self, args)

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

class DmRaid(commands.dmraid.FC6_DmRaid):
    def parse(self, args):
        commands.dmraid.FC6_DmRaid.parse(self, args)

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

class Partition(commands.partition.F9_Partition):
    def parse(self, args):
        commands.partition.F9_Partition.parse(self, args)

        pd = self.partitions[-1]
        uniqueID = None

        fsopts = ""
        if pd.fsopts:
            fsopts = pd.fsopts

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
                try:
                    filesystem = fileSystemTypeGet(pd.fstype)
                except KeyError:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % pd.fstype)
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
        elif pd.mountpoint == "/boot/efi":
            filesystem = fileSystemTypeGet("efi")
            fsopts = "defaults,uid=0,gid=0,umask=0077,shortname=winnt"
        else:
            if pd.fstype != "":
                try:
                    filesystem = fileSystemTypeGet(pd.fstype)
                except KeyError:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % pd.fstype)
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
                                             fsprofile = pd.fsprofile)
        
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

        if fsopts != "":
            request.fsopts = fsopts

        if pd.encrypted:
            if pd.passphrase and \
               not self.handler.anaconda.id.partitions.encryptionPassphrase:
                self.handler.anaconda.id.partitions.encryptionPassphrase = pd.passphrase
            request.encryption = cryptodev.LUKSDevice(passphrase=pd.passphrase, format=pd.format)

        addPartRequest(self.handler.anaconda, request)
        self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

class Reboot(commands.reboot.FC6_Reboot):
    def parse(self, args):
        commands.reboot.FC6_Reboot.parse(self, args)
        self.handler.skipSteps.append("complete")

class Raid(commands.raid.F9_Raid):
    def parse(self, args):
        commands.raid.F9_Raid.parse(self, args)

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
                try:
                    filesystem = fileSystemTypeGet(rd.fstype)
                except KeyError:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % rd.fstype)
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
                                               preexist = rd.preexist,
                                               fsprofile = rd.fsprofile)

        if uniqueID is not None:
            request.uniqueID = uniqueID
        if rd.preexist and rd.device != "":
            request.device = "md%s" % rd.device
        if rd.fsopts != "":
            request.fsopts = rd.fsopts

        if rd.encrypted:
            if rd.passphrase and \
               not self.handler.anaconda.id.partitions.encryptionPassphrase:
                self.handler.anaconda.id.partitions.encryptionPassphrase = rd.passphrase
            request.encryption = cryptodev.LUKSDevice(passphrase=rd.passphrase, format=rd.format)

        addPartRequest(self.handler.anaconda, request)
        self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])

class RootPw(commands.rootpw.F8_RootPw):
    def parse(self, args):
        commands.rootpw.F8_RootPw.parse(self, args)

        self.handler.id.rootPassword["password"] = self.password
        self.handler.id.rootPassword["isCrypted"] = self.isCrypted
        self.handler.id.rootPassword["lock"] = self.lock
        self.handler.skipSteps.append("accounts")

class SELinux(commands.selinux.FC3_SELinux):
    def parse(self, args):
        commands.selinux.FC3_SELinux.parse(self, args)
        self.handler.id.security.setSELinux(self.selinux)

class SkipX(commands.skipx.FC3_SkipX):
    def parse(self, args):
        commands.skipx.FC3_SkipX.parse(self, args)

        self.handler.skipSteps.extend(["setsanex", "videocard", "xcustom"])

        if self.handler.id.desktop is not None:
            self.handler.id.desktop.setDefaultRunLevel(3)

class Timezone(commands.timezone.FC6_Timezone):
    def parse(self, args):
        commands.timezone.FC6_Timezone.parse(self, args)

        # check validity
        f = open('/usr/share/zoneinfo/zone.tab', 'r')
        for line in f:
            line = line.strip()
            if line[0] == '#':
                continue
            fields = line.split('\t')
            if len(fields) > 2 and fields[2] == self.timezone: 
                break
        else:
            log.warning("Timezone %s set in kickstart is not valid, will ask" % (self.timezone,))
            return

        self.handler.id.timezone.setTimezoneInfo(self.timezone, self.isUtc)
        self.handler.skipSteps.append("timezone")

class Upgrade(commands.upgrade.FC3_Upgrade):
    def parse(self, args):
        commands.upgrade.FC3_Upgrade.parse(self, args)
        self.handler.id.setUpgrade(self.upgrade)

class VolGroup(commands.volgroup.FC3_VolGroup):
    def parse(self, args):
        commands.volgroup.FC3_VolGroup.parse(self, args)

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
        addPartRequest(self.handler.anaconda, request)

class XConfig(commands.xconfig.F10_XConfig):
    def parse(self, args):
        commands.xconfig.F10_XConfig.parse(self, args)

        if self.startX:
            self.handler.id.desktop.setDefaultRunLevel(5)

        if self.defaultdesktop:
            self.handler.id.desktop.setDefaultDesktop(self.defaultdesktop)

class ZeroMbr(commands.zerombr.FC3_ZeroMbr):
    def parse(self, args):
        commands.zerombr.FC3_ZeroMbr.parse(self, args)
        self.handler.id.partitions.zeroMbr = 1

class ZFCP(commands.zfcp.FC3_ZFCP):
    def parse(self, args):
        commands.zfcp.FC3_ZFCP.parse(self, args)
        for fcp in self.zfcp:
            self.handler.id.zfcp.addFCP(fcp.devnum, fcp.wwpn, fcp.fcplun)

        isys.flushDriveDict()


###
### HANDLERS
###

# This is just the latest entry from pykickstart.handlers.control with all the
# classes we're overriding in place of the defaults.
commandMap = {
        "auth": Authconfig,
        "authconfig": Authconfig,
        "autopart": AutoPart,
        "autostep": AutoStep,
        "bootloader": Bootloader,
        "cdrom": commands.method.FC6_Method,
        "clearpart": ClearPart,
        "cmdline": commands.displaymode.FC3_DisplayMode,
        "device": commands.device.F8_Device,
        "deviceprobe": commands.deviceprobe.FC3_DeviceProbe,
        "dmraid": DmRaid,
        "driverdisk": commands.driverdisk.FC3_DriverDisk,
        "firewall": Firewall,
        "firstboot": Firstboot,
        "graphical": commands.displaymode.FC3_DisplayMode,
        "halt": Reboot,
        "harddrive": commands.method.FC6_Method,
        "ignoredisk": IgnoreDisk,
        "install": Upgrade,
        "interactive": commands.interactive.FC3_Interactive,
        "iscsi": Iscsi,
        "iscsiname": IscsiName,
        "key": commands.key.F7_Key,
        "keyboard": Keyboard,
        "lang": Lang,
        "logging": Logging,
        "logvol": LogVol,
        "mediacheck": commands.mediacheck.FC4_MediaCheck,
        "monitor": commands.monitor.F10_Monitor,
        "multipath": MultiPath,
        "network": Network,
        "nfs": commands.method.FC6_Method,
        "part": Partition,
        "partition": Partition,
        "poweroff": Reboot,
        "raid": Raid,
        "reboot": Reboot,
        "repo": commands.repo.F8_Repo,
        "rescue": commands.rescue.F10_Rescue,
        "rootpw": RootPw,
        "selinux": SELinux,
        "services": commands.services.FC6_Services,
        "shutdown": Reboot,
        "skipx": SkipX,
        "text": commands.displaymode.FC3_DisplayMode,
        "timezone": Timezone,
        "updates": commands.updates.F7_Updates,
        "upgrade": Upgrade,
        "url": commands.method.FC6_Method,
        "user": commands.user.F8_User,
        "vnc": commands.vnc.FC6_Vnc,
        "volgroup": VolGroup,
        "xconfig": XConfig,
        "zerombr": ZeroMbr,
        "zfcp": ZFCP
}

superclass = returnClassForVersion()

class AnacondaKSHandler(superclass):
    def __init__ (self, anaconda):
        superclass.__init__(self, mapping=commandMap)
        self.packages = AnacondaKSPackages()

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

class VNCHandler(superclass):
    # We're only interested in the handler for the VNC command and display modes.
    def __init__(self, anaconda=None):
        superclass.__init__(self, mapping=commandMap)
        self.maskAllExcept(["vnc", "displaymode", "text", "cmdline", "graphical"])

class RescueHandler(superclass):
    # We're only interested in the handler for the rescue command
    def __init__(self, anaconda=None):
        superclass.__init__(self, mapping=commandMap)
        self.maskAllExcept(["rescue"])

class KickstartPreParser(KickstartParser):
    def __init__ (self, handler, followIncludes=True, errorsAreFatal=True,
                  missingIncludeIsFatal=True):
        KickstartParser.__init__(self, handler, missingIncludeIsFatal=False)

    def addScript (self):
        if self._script["type"] != KS_SCRIPT_PRE:
            return

        s = AnacondaKSScript (self._script["body"], type=self._script["type"],
                              interp=self._script["interp"],
                              lineno=self._script["lineno"],
                              inChroot=self._script["chroot"],
                              logfile=self._script["log"],
                              errorOnFail=self._script["errorOnFail"])
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

        KickstartParser.handleScriptHdr(self, lineno, args)

class AnacondaKSParser(KickstartParser):
    def __init__ (self, handler, followIncludes=True, errorsAreFatal=True,
                  missingIncludeIsFatal=True):
        KickstartParser.__init__(self, handler)

    def addScript (self):
        if string.join(self._script["body"]).strip() == "":
            return

        s = AnacondaKSScript (self._script["body"], type=self._script["type"],
                              interp=self._script["interp"],
                              lineno=self._script["lineno"],
                              inChroot=self._script["chroot"],
                              logfile=self._script["log"],
                              errorOnFail=self._script["errorOnFail"])
        self.handler.scripts.append(s)

    def handlePackageHdr (self, lineno, args):
        KickstartParser.handlePackageHdr (self, lineno, args)
        self.handler.packages.seen = True

    def handleCommand (self, lineno, args):
        if not self.handler:
            return

        KickstartParser.handleCommand(self, lineno, args)

# this adds a partition to the autopartition list replacing anything
# else with this mountpoint so that you can use autopart and override /
def addPartRequest(anaconda, request):
    if not request.mountpoint:
        anaconda.id.partitions.autoPartitionRequests.append(request)
        return

    for req in anaconda.id.partitions.autoPartitionRequests:
        if req.mountpoint and req.mountpoint == request.mountpoint:
            anaconda.id.partitions.autoPartitionRequests.remove(req)
            break
    anaconda.id.partitions.autoPartitionRequests.append(request)            

def processKickstartFile(anaconda, file):
    # make sure our disks are alive
    from partedUtils import DiskSet
    ds = DiskSet(anaconda)
    ds.startMPath()
    ds.startDmRaid()

    # parse the %pre
    ksparser = KickstartPreParser(AnacondaKSHandler(anaconda))

    try:
        ksparser.readKickstart(file)
    except IOError, e:
        if anaconda.intf:
            anaconda.intf.kickstartErrorWindow("Could not open kickstart file or included file named %s" % e.filename)
            sys.exit(0)
        else:
            raise
    except KickstartError, e:
       if anaconda.intf:
           anaconda.intf.kickstartErrorWindow(e.__str__())
           sys.exit(0)
       else:
           raise

    # run %pre scripts
    runPreScripts(anaconda, ksparser.handler.scripts)

    # now read the kickstart file for real
    handler = AnacondaKSHandler(anaconda)
    ksparser = AnacondaKSParser(handler)

    try:
        ksparser.readKickstart(file)
    except IOError, e:
        if anaconda.intf:
            anaconda.intf.kickstartErrorWindow("Could not open kickstart file or included file named %s" % e.filename)
            sys.exit(0)
        else:
            raise
    except KickstartError, e:
        if anaconda.intf:
            anaconda.intf.kickstartErrorWindow(e.__str__())
            sys.exit(0)
        else:
            raise

    anaconda.id.setKsdata(handler)

def runPostScripts(anaconda):
    if not anaconda.id.ksdata:
        return

    postScripts = filter (lambda s: s.type == KS_SCRIPT_POST,
                          anaconda.id.ksdata.scripts)

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
        
    map (lambda s: s.run(anaconda.rootPath, flags.serial, anaconda.intf), postScripts)

    log.info("All kickstart %%post script(s) have been run")
    if anaconda.intf is not None:
        w.pop()

def runPreScripts(anaconda, scripts):
    preScripts = filter (lambda s: s.type == KS_SCRIPT_PRE, scripts)

    if len(preScripts) == 0:
        return

    log.info("Running kickstart %%pre script(s)")
    if anaconda.intf is not None:
        w = anaconda.intf.waitWindow(_("Running..."),
                            _("Running pre-install scripts"))
    
    map (lambda s: s.run("/", flags.serial, anaconda.intf), preScripts)

    log.info("All kickstart %%pre script(s) have been run")
    if anaconda.intf is not None:
        w.pop()

def runTracebackScripts(anaconda):
    log.info("Running kickstart %%traceback script(s)")
    for script in filter (lambda s: s.type == KS_SCRIPT_TRACEBACK,
                          anaconda.id.ksdata.scripts):
        script.run("/", flags.serial)
    log.info("All kickstart %%traceback script(s) have been run")

def selectPackages(anaconda):
    ksdata = anaconda.id.ksdata
    ignoreAll = False

    # If no %packages header was seen, use the installclass's default group
    # selections.  This can also be explicitly specified with %packages
    # --default.  Otherwise, select whatever was given (even if it's nothing).
    if not ksdata.packages.seen or ksdata.packages.default:
        anaconda.id.instClass.setGroupSelection(anaconda)
        return

    for pkg in ksdata.packages.packageList:
        num = anaconda.backend.selectPackage(pkg)
        if ksdata.packages.handleMissing == KS_MISSING_IGNORE or ignoreAll:
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
                                                _("_Ignore All"),
                                                _("_Continue")])
        if rc == 0:
            sys.exit(1)
        elif rc == 1:
            ignoreAll = True

    anaconda.backend.selectGroup("Core")

    if ksdata.packages.addBase:
        anaconda.backend.selectGroup("Base")
    else:
        log.warning("not adding Base group")

    for grp in ksdata.packages.groupList:
        default = False
        optional = False

        if grp.include == GROUP_DEFAULT:
            default = True
        elif grp.include == GROUP_ALL:
            default = True
            optional = True

        try:
            anaconda.backend.selectGroup(grp.name, (default, optional))
        except NoSuchGroup, e:
            if ksdata.packages.handleMissing == KS_MISSING_IGNORE or ignoreAll:
                pass
            else:
                rc = anaconda.intf.messageWindow(_("Missing Group"),
                                        _("You have specified that the "
                                          "group '%s' should be installed. "
                                          "This group does not exist. "
                                          "Would you like to continue or "
                                          "abort your installation?")
                                        %(grp.name,),
                                        type="custom",
                                        custom_buttons=[_("_Abort"),
                                                        _("_Ignore All"),
                                                        _("_Continue")])
                if rc == 0:
                    sys.exit(1)
                elif rc == 1:
                    ignoreAll = True

    map(anaconda.backend.deselectPackage, ksdata.packages.excludedList)

def setSteps(anaconda):
    def havePackages(packages):
        return len(packages.groupList) > 0 or len(packages.packageList) > 0 or \
               len(packages.excludedList) > 0

    dispatch = anaconda.dispatch
    ksdata = anaconda.id.ksdata
    interactive = ksdata.interactive.interactive

    if ksdata.upgrade.upgrade:
        upgrade.setSteps(anaconda)

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
        anaconda.id.instClass.setSteps(anaconda)
        dispatch.skipStep("findrootparts")

    if interactive or flags.autostep:
        dispatch.skipStep("installtype")
        dispatch.skipStep("bootdisk")

    dispatch.skipStep("bootdisk")
    dispatch.skipStep("betanag")
    dispatch.skipStep("regkey")
    dispatch.skipStep("installtype")
    dispatch.skipStep("tasksel")
    dispatch.skipStep("network")

    # Don't show confirmation screens on non-interactive installs.
    if not interactive:
        dispatch.skipStep("confirminstall")
        dispatch.skipStep("confirmupgrade")
        dispatch.skipStep("welcome")

    # Make sure to automatically reboot even in interactive if told to.
    if interactive and ksdata.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
        dispatch.skipStep("complete")

    # If the package section included anything, skip group selection unless
    # they're in interactive.
    if ksdata.upgrade.upgrade:
        ksdata.skipSteps.append("group-selection")

        # Special check for this, since it doesn't make any sense.
        if ksdata.packages.seen:
            warnings.warn("Ignoring contents of %packages section due to upgrade.")
    elif havePackages(ksdata.packages):
        if interactive:
            ksdata.showSteps.append("group-selection")
        else:
            ksdata.skipSteps.append("group-selection")
    else:
        ksdata.skipSteps.append("group-selection")
        if ksdata.packages.seen:
            ksdata.skipSteps.append("group-selection")
        else:
            ksdata.showSteps.append("group-selection")

    if not interactive:
        for n in ksdata.skipSteps:
            dispatch.skipStep(n)
        for n in ksdata.permanentSkipSteps:
            dispatch.skipStep(n, permanent=1)
    for n in ksdata.showSteps:
        dispatch.skipStep(n, skip = 0)
