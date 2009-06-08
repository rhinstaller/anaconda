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

from storage.deviceaction import *
from storage.devices import LUKSDevice
from storage.devicelibs.lvm import getPossiblePhysicalExtents
from storage.formats import getFormat
from storage.partitioning import clearPartitions

from errors import *
import iutil
import isys
import os
import tempfile
from flags import flags
from constants import *
import sys
import string
import urlgrabber.grabber as grabber
import warnings
import upgrade
import pykickstart.commands as commands
from storage.devices import *
import zonetab
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
        retval = commands.authconfig.FC3_Authconfig.parse(self, args)
        self.handler.id.auth = self.authconfig
        return retval

class AutoPart(commands.autopart.F9_AutoPart):
    def parse(self, args):
        retval = commands.autopart.F9_AutoPart.parse(self, args)

        # sets up default autopartitioning.  use clearpart separately
        # if you want it
        self.handler.id.instClass.setDefaultPartitioning(self.handler.id.storage, self.handler.anaconda.platform)
        self.handler.id.storage.doAutoPart = True

        if self.encrypted:
            self.handler.id.storage.encryptedAutoPart = True
            self.handler.id.storage.encryptionPassphrase = self.passphrase

        self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
        return retval

class AutoStep(commands.autostep.FC3_AutoStep):
    def parse(self, args):
        retval = commands.autostep.FC3_AutoStep.parse(self, args)
        flags.autostep = 1
        flags.autoscreenshot = self.autoscreenshot
        return retval

class Bootloader(commands.bootloader.F12_Bootloader):
    def parse(self, args):
        retval = commands.bootloader.F12_Bootloader.parse(self, args)

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
            # XXX I don't like that we are supposed to have scanned the
            #     storage devices already and yet we cannot know about
            #     ignoredDisks, exclusiveDisks, or iscsi disks before we
            #     have processed the kickstart config file.
            hds = [d.name for d in self.handler.id.storage.disks]
            for disk in self.driveorder:
                if disk not in hds:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in driveorder command" % disk)

        if location is None:
            self.handler.permanentSkipSteps.extend(["bootloadersetup", "instbootloader"])
        else:
            self.handler.showSteps.append("bootloader")

            if self.appendLine:
                self.handler.id.bootloader.args.set(self.appendLine)

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
        return retval

class ClearPart(commands.clearpart.FC3_ClearPart):
    def parse(self, args):
        retval = commands.clearpart.FC3_ClearPart.parse(self, args)

        if self.type is None:
            self.type = CLEARPART_TYPE_NONE

        hds = map(udev_device_get_name, udev_get_block_devices())
        for disk in self.drives:
            if disk not in hds:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in clearpart command" % disk)

        # If doing the early kickstart processing, we will not yet have an
        # instdata attribute.  That's okay because we pull the lists right
        # out of this class instead of the instdata.
        if not self.handler.id:
            return retval

        self.handler.id.storage.clearPartType = self.type
        self.handler.id.storage.clearPartDisks = self.drives
        if self.initAll:
            self.handler.id.storage.reinitializeDisks = self.initAll

        clearPartitions(self.handler.id.storage)

        return retval

class Firewall(commands.firewall.F10_Firewall):
    def parse(self, args):
        retval = commands.firewall.F10_Firewall.parse(self, args)
        self.handler.id.firewall.enabled = self.enabled
        self.handler.id.firewall.trustdevs = self.trusts

        for port in self.ports:
            self.handler.id.firewall.portlist.append (port)

        for svc in self.services:
            self.handler.id.firewall.servicelist.append (svc)

        return retval

class Firstboot(commands.firstboot.FC3_Firstboot):
    def parse(self, args):
        retval = commands.firstboot.FC3_Firstboot.parse(self, args)
        self.handler.id.firstboot = self.firstboot
        return retval

class IgnoreDisk(commands.ignoredisk.F8_IgnoreDisk):
    def parse(self, args):
        retval = commands.ignoredisk.F8_IgnoreDisk.parse(self, args)

        # If doing the early kickstart processing, we will not yet have
        # an instdata attribute.  That's okay because we pull the lists
        # right out of this class instead of the instdata.
        if not self.handler.id:
            return retval

        for drive in self.ignoredisk:
            if not drive in self.handler.id.storage.ignoredDisks:
                self.handler.id.storage.ignoredDisks.append(drive)

        for drive in self.onlyuse:
            if not drive in self.handler.id.storage.exclusiveDisks:
                self.handler.id.storage.exclusiveDisks.append(drive)

        return retval

class Iscsi(commands.iscsi.F10_Iscsi):
    def parse(self, args):
        retval = commands.iscsi.F10_Iscsi.parse(self, args)

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

        return retval

class IscsiName(commands.iscsiname.FC6_IscsiName):
    def parse(self, args):
        retval = commands.iscsiname.FC6_IscsiName.parse(self, args)

        self.handler.id.iscsi.initiator = self.iscsiname
        return retval

class Keyboard(commands.keyboard.FC3_Keyboard):
    def parse(self, args):
        retval = commands.keyboard.FC3_Keyboard.parse(self, args)
        self.handler.id.keyboard.set(self.keyboard)
        self.handler.id.keyboard.beenset = 1
        self.handler.skipSteps.append("keyboard")
        return retval

class Lang(commands.lang.FC3_Lang):
    def parse(self, args):
        retval = commands.lang.FC3_Lang.parse(self, args)
        self.handler.id.instLanguage.setRuntimeLanguage(self.lang)
        self.handler.skipSteps.append("language")
        return retval

class LogVol(commands.logvol.F9_LogVol):
    def parse(self, args):
        lvd = commands.logvol.F9_LogVol.parse(self, args)

        storage = self.handler.id.storage
        devicetree = storage.devicetree

        storage.doAutoPart = False

        if lvd.mountpoint == "swap":
            type = "swap"
            lvd.mountpoint = ""
            if lvd.recommended:
                (lvd.size, lvd.maxSizeMB) = iutil.swapSuggestion()
                lvd.grow = True
        else:
            if lvd.fstype != "":
                type = lvd.fstype
            else:
                type = storage.defaultFSType

        # Sanity check mountpoint
        if lvd.mountpoint != "" and lvd.mountpoint[0] != '/':
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The mount point \"%s\" is not valid." % (lvd.mountpoint,))

        # Check that the VG this LV is a member of has already been specified.
        vg = devicetree.getDeviceByName(lvd.vgname)
        if not vg:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="No volume group exists with the name \"%s\".  Specify volume groups before logical volumes." % lvd.vgname)

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not lvd.format:
            if not lvd.name:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--noformat used without --name")

            dev = devicetree.getDeviceByName("%s-%s" % (vg.name, lvd.name))
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No preexisting logical volume with the name \"%s\" was found." % lvd.name)

            dev.format.mountpoint = lvd.mountpoint
            dev.format.mountopts = lvd.fsopts
            self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
            return lvd

        # Make sure this LV name is not already used in the requested VG.
        if not lvd.preexist:
            tmp = devicetree.getDeviceByName("%s-%s" % (vg.name, lvd.name))
            if tmp:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Logical volume name already used in volume group %s" % vg.name)

            # Size specification checks
            if not lvd.percent:
                if not lvd.size:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Size required")
                elif not lvd.grow and lvd.size*1024 < vg.peSize:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Logical volume size must be larger than the volume group physical extent size.")
            elif lvd.percent <= 0 or lvd.percent > 100:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Percentage must be between 0 and 100")

        # Now get a format to hold a lot of these extra values.
        format = getFormat(type,
                           mountpoint=lvd.mountpoint,
                           mountopts=lvd.fsopts)
        if not format:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % type)

        # If we were given a pre-existing LV to create a filesystem on, we need
        # to verify it and its VG exists and then schedule a new format action
        # to take place there.  Also, we only support a subset of all the
        # options on pre-existing LVs.
        if lvd.preexist:
            device = devicetree.getDeviceByName("%s-%s" % (vg.name, lvd.name))
            if not device:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent LV %s in logvol command" % lvd.name)

            devicetree.registerAction(ActionCreateFormat(device, format))
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if lvd.mountpoint:
                    device = storage.fsset.mountpoints[lvd.mountpoint]
                    storage.destroyDevice(device)
            except KeyError:
                pass

            request = storage.newLV(format=format,
                                    name=lvd.name,
                                    vg=vg,
                                    size=lvd.size,
                                    grow=lvd.grow,
                                    maxsize=lvd.maxSizeMB,
                                    percent=lvd.percent)

            # FIXME: no way to specify an fsprofile right now
            # if lvd.fsprofile:
            #     request.format.fsprofile = lvd.fsprofile

            storage.createDevice(request)

        if lvd.encrypted:
            if lvd.passphrase and not storage.encryptionPassphrase:
                storage.encryptionPassphrase = lvd.passphrase

            if lvd.preexist:
                luksformat = format
                device.format = getFormat("luks", passphrase=lvd.passphrase, device=device.path)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = getFormat("luks", passphrase=lvd.passphrase, device=request.path)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=request)
            storage.createDevice(luksdev)

        self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
        return lvd

class Logging(commands.logging.FC6_Logging):
    def parse(self, args):
        retval = commands.logging.FC6_Logging.parse(self, args)

        log.setHandlersLevel(logLevelMap[self.level])

        if self.host != "" and self.port != "":
            logger.addSysLogHandler(log, self.host, port=int(self.port))
        elif self.host != "":
            logger.addSysLogHandler(log, self.host)

        return retval

class Network(commands.network.F8_Network):
    def parse(self, args):
        nd = commands.network.F8_Network.parse(self, args)

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

        return nd

class MultiPath(commands.multipath.FC6_MultiPath):
    def parse(self, args):
        raise NotImplementedError("The multipath kickstart command is not currently supported")

class DmRaid(commands.dmraid.FC6_DmRaid):
    def parse(self, args):
        raise NotImplementedError("The dmraid kickstart command is not currently supported")

class Partition(commands.partition.F11_Partition):
    def parse(self, args):
        pd = commands.partition.F11_Partition.parse(self, args)

        storage = self.handler.id.storage
        devicetree = storage.devicetree
        kwargs = {}

        storage.doAutoPart = False

        if pd.onbiosdisk != "":
            pd.disk = isys.doGetBiosDisk(pd.onbiosdisk)

            if pd.disk == "":
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified BIOS disk %s cannot be determined" % pd.onbiosdisk)

        if pd.mountpoint == "swap":
            type = "swap"
            pd.mountpoint = ""
            if pd.recommended:
                (pd.size, pd.maxSizeMB) = iutil.swapSuggestion()
                pd.grow = True
        # if people want to specify no mountpoint for some reason, let them
        # this is really needed for pSeries boot partitions :(
        elif pd.mountpoint == "None":
            pd.mountpoint = ""
            if pd.fstype:
                type = pd.fstype
            else:
                type = storage.defaultFSType
        elif pd.mountpoint == 'appleboot':
            type = "Apple Bootstrap"
            pd.mountpoint = ""
            kwargs["weight"] = self.handler.anaconda.platform.weight(fstype="appleboot")
        elif pd.mountpoint == 'prepboot':
            type = "PPC PReP Boot"
            pd.mountpoint = ""
            kwargs["weight"] = self.handler.anaconda.platform.weight(fstype="prepboot")
        elif pd.mountpoint.startswith("raid."):
            type = "mdmember"
            kwargs["name"] = pd.mountpoint

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="RAID partition defined multiple times")

            # store "raid." alias for other ks partitioning commands
            if pd.onPart:
                self.handler.onPart[kwargs["name"]] = pd.onPart
            pd.mountpoint = ""
        elif pd.mountpoint.startswith("pv."):
            type = "lvmpv"
            kwargs["name"] = pd.mountpoint

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="PV partition defined multiple times")

            # store "pv." alias for other ks partitioning commands
            if pd.onPart:
                self.handler.onPart[kwargs["name"]] = pd.onPart
            pd.mountpoint = ""
        elif pd.mountpoint == "/boot/efi":
            type = "EFI System Partition"
            pd.fsopts = "defaults,uid=0,gid=0,umask=0077,shortname=winnt"
            kwargs["weight"] = self.handler.anaconda.platform.weight(fstype="efi")
        elif pd.mountpoint == "/boot":
            type = self.handler.anaconda.platform.bootFSType
        else:
            if pd.fstype != "":
                type = pd.fstype
            else:
                type = storage.defaultFSType

        # If this specified an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not pd.format:
            if not pd.onPart:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--noformat used without --onpart")

            dev = devicetree.getDeviceByName(pd.onPart)
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No preexisting partition with the name \"%s\" was found." % pd.onPart)

            dev.format.mountpoint = pd.mountpoint
            dev.format.mountopts = pd.fsopts
            self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
            return pd

        # Size specification checks.
        if not pd.size and not pd.onPart:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Partition requires a size specification")

        # Now get a format to hold a lot of these extra values.
        kwargs["format"] = getFormat(type,
                                     mountpoint=pd.mountpoint,
                                     label=pd.label,
                                     mountopts=pd.fsopts)
        if not kwargs["format"]:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % type)

        # If we were given a specific disk to create the partition on, verify
        # that it exists first.  If it doesn't exist, see if it exists with
        # mapper/ on the front.  If that doesn't exist either, it's an error.
        if pd.disk:
            disk = devicetree.getDeviceByName(pd.disk)
            if not disk:
                pd.disk = "mapper/%s" % pd.disk
                disk = devicetree.getDeviceByName(pd.disk)

                if not disk:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in partition command" % pd.disk)

            kwargs["disks"] = [disk]

        kwargs["grow"] = pd.grow
        kwargs["size"] = pd.size
        kwargs["maxsize"] = pd.maxSizeMB
        kwargs["primary"] = pd.primOnly

        # If we were given a pre-existing partition to create a filesystem on,
        # we need to verify it exists and then schedule a new format action to
        # take place there.  Also, we only support a subset of all the options
        # on pre-existing partitions.
        if pd.onPart:
            device = devicetree.getDeviceByName(pd.onPart)
            if not device:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent partition %s in partition command" % pd.onPart)

            devicetree.registerAction(ActionCreateFormat(device, kwargs["format"]))
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if pd.mountpoint:
                    device = storage.fsset.mountpoints[pd.mountpoint]
                    storage.destroyDevice(device)
            except KeyError:
                pass

            request = storage.newPartition(**kwargs)

            # FIXME: no way to specify an fsprofile right now
            # if pd.fsprofile:
            #     request.format.fsprofile = pd.fsprofile

            storage.createDevice(request)

        if pd.encrypted:
            if pd.passphrase and not storage.encryptionPassphrase:
               storage.encryptionPassphrase = pd.passphrase

            if pd.preexist:
                luksformat = format
                device.format = getFormat("luks", passphrase=pd.passphrase, device=device.path)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = getFormat("luks", passphrase=pd.passphrase, device=request.path)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=request)
            storage.createDevice(luksdev)

        self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
        return pd

class Reboot(commands.reboot.FC6_Reboot):
    def parse(self, args):
        retval = commands.reboot.FC6_Reboot.parse(self, args)
        self.handler.skipSteps.append("complete")
        return retval

class Raid(commands.raid.F9_Raid):
    def parse(self, args):
        rd = commands.raid.F9_Raid.parse(self, args)
        raidmems = []
        devicename = "md%d" % rd.device

        storage = self.handler.id.storage
        devicetree = storage.devicetree
        kwargs = {}

        storage.doAutoPart = False

        if rd.mountpoint == "swap":
            type = "swap"
            rd.mountpoint = ""
        elif rd.mountpoint.startswith("pv."):
            type = "lvmpv"
            kwargs["name"] = rd.mountpoint
            self.handler.onPart[kwargs["name"]] = devicename

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="PV partition defined multiple times")

            rd.mountpoint = ""
        elif rd.mountpoint == "/boot" and self.handler.anaconda.platform.supportsMdRaidBoot:
            type = self.handler.anaconda.platform.bootFSType
        else:
            if rd.fstype != "":
                type = rd.fstype
            else:
                type = storage.defaultFSType

        # Sanity check mountpoint
        if rd.mountpoint != "" and rd.mountpoint[0] != '/':
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The mount point is not valid.")

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not rd.format:
            if not devicename:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--noformat used without --device")

            dev = devicetree.getDeviceByName(devicename)
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No preexisting RAID device with the name \"%s\" was found." % devicename)

            dev.format.mountpoint = rd.mountpoint
            dev.format.mountopts = rd.fsopts
            self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
            return rd

        # Get a list of all the RAID members.
        for member in rd.members:
            # if member is using --onpart, use original device
            member = self.handler.onPart.get(member, member)
            dev = devicetree.getDeviceByName(member)
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use undefined partition %s in RAID specification" % member)

            raidmems.append(dev)

        if not rd.preexist:
            if len(raidmems) == 0:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="RAID Partition defined without any RAID members")

            if rd.level == "":
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="RAID Partition defined without RAID level")

        # Now get a format to hold a lot of these extra values.
        kwargs["format"] = getFormat(type,
                                     mountpoint=rd.mountpoint,
                                     mountopts=rd.fsopts)
        if not kwargs["format"]:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % type)

        kwargs["name"] = devicename
        kwargs["level"] = rd.level
        kwargs["parents"] = raidmems
        kwargs["memberDevices"] = len(raidmems)
        kwargs["totalDevices"] = kwargs["memberDevices"]+rd.spares

        # If we were given a pre-existing RAID to create a filesystem on,
        # we need to verify it exists and then schedule a new format action
        # to take place there.  Also, we only support a subset of all the
        # options on pre-existing RAIDs.
        if rd.preexist:
            device = devicetree.getDeviceByName(devicename)
            if not device:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specifeid nonexistent RAID %s in raid command" % devicename)

            devicetree.registerAction(ActionCreateFormat(device, kwargs["format"]))
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if rd.mountpoint:
                    device = storage.fsset.mountpoints[rd.mountpoint]
                    storage.destroyDevice(device)
            except KeyError:
                pass

            request = storage.newMDArray(**kwargs)

            # FIXME: no way to specify an fsprofile right now
            # if pd.fsprofile:
            #     request.format.fsprofile = pd.fsprofile

            storage.createDevice(request)

        if rd.encrypted:
            if rd.passphrase and not storage.encryptionPassphrase:
               storage.encryptionPassphrase = rd.passphrase

            if rd.preexist:
                luksformat = format
                device.format = getFormat("luks", passphrase=rd.passphrase, device=device.path)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = getFormat("luks", passphrase=rd.passphrase, device=request.path)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=request)
            storage.createDevice(luksdev)

        self.handler.skipSteps.extend(["partition", "zfcpconfig", "parttype"])
        return rd

class RootPw(commands.rootpw.F8_RootPw):
    def parse(self, args):
        retval = commands.rootpw.F8_RootPw.parse(self, args)

        self.handler.id.rootPassword["password"] = self.password
        self.handler.id.rootPassword["isCrypted"] = self.isCrypted
        self.handler.id.rootPassword["lock"] = self.lock
        self.handler.skipSteps.append("accounts")
        return retval

class SELinux(commands.selinux.FC3_SELinux):
    def parse(self, args):
        retval = commands.selinux.FC3_SELinux.parse(self, args)
        self.handler.id.security.setSELinux(self.selinux)
        return retval

class SkipX(commands.skipx.FC3_SkipX):
    def parse(self, args):
        retval = commands.skipx.FC3_SkipX.parse(self, args)

        self.handler.skipSteps.extend(["setsanex", "videocard", "xcustom"])

        if self.handler.id.desktop is not None:
            self.handler.id.desktop.setDefaultRunLevel(3)

        return retval

class Timezone(commands.timezone.FC6_Timezone):
    def parse(self, args):
        retval = commands.timezone.FC6_Timezone.parse(self, args)

        # check validity
        tab = zonetab.ZoneTab()
        if self.timezone not in (entry.tz.replace(' ','_') for entry in
                                 tab.getEntries()):
            log.warning("Timezone %s set in kickstart is not valid, will ask" % (self.timezone,))
            return retval

        self.handler.id.timezone.setTimezoneInfo(self.timezone, self.isUtc)
        self.handler.skipSteps.append("timezone")
        return retval

class Upgrade(commands.upgrade.F11_Upgrade):
    def parse(self, args):
        retval = commands.upgrade.F11_Upgrade.parse(self, args)
        self.handler.id.setUpgrade(self.upgrade)
        return retval

class VolGroup(commands.volgroup.FC3_VolGroup):
    def parse(self, args):
        vgd = commands.volgroup.FC3_VolGroup.parse(self, args)
        pvs = []

        storage = self.handler.id.storage
        devicetree = storage.devicetree

        storage.doAutoPart = False

        # Get a list of all the physical volume devices that make up this VG.
        for pv in vgd.physvols:
            # if pv is using --onpart, use original device
            pv = self.handler.onPart.get(pv, pv)
            dev = devicetree.getDeviceByName(pv)
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use undefined partition %s in Volume Group specification" % pv)

            pvs.append(dev)

        if len(pvs) == 0 and not vgd.preexist:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Volume group defined without any physical volumes.  Either specify physical volumes or use --useexisting.")

        if vgd.pesize not in getPossiblePhysicalExtents(floor=1024):
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Volume group specified invalid pesize")

        # If --noformat or --useexisting was given, there's really nothing to do.
        if not vgd.format or vgd.preexist:
            if not vgd.vgname:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--noformat or --useexisting used without giving a name")

            dev = devicetree.getDeviceByName(vgd.vgname)
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No preexisting VG with the name \"%s\" was found." % vgd.vgname)
        else:
            request = storage.newVG(pvs=pvs,
                                    name=vgd.vgname,
                                    peSize=vgd.pesize/1024.0)

            storage.createDevice(request)

        return vgd

class XConfig(commands.xconfig.F10_XConfig):
    def parse(self, args):
        retval = commands.xconfig.F10_XConfig.parse(self, args)

        if self.startX:
            self.handler.id.desktop.setDefaultRunLevel(5)

        if self.defaultdesktop:
            self.handler.id.desktop.setDefaultDesktop(self.defaultdesktop)

        return retval

class ZeroMbr(commands.zerombr.FC3_ZeroMbr):
    def parse(self, args):
        retval = commands.zerombr.FC3_ZeroMbr.parse(self, args)
        self.handler.id.storage.zeroMbr = 1
        return retval

class ZFCP(commands.zfcp.FC3_ZFCP):
    def parse(self, args):
        retval = commands.zfcp.FC3_ZFCP.parse(self, args)
        for fcp in self.zfcp:
            self.handler.id.zfcp.addFCP(fcp.devnum, fcp.wwpn, fcp.fcplun)

        isys.flushDriveDict()
        return retval


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
        "driverdisk": commands.driverdisk.F12_DriverDisk,
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
        "repo": commands.repo.F11_Repo,
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
    # This handler class processes all kickstart commands.  It is used in the
    # second parsing pass - when we do all the real work.
    def __init__ (self, anaconda):
        superclass.__init__(self, mapping=commandMap)
        self.packages = AnacondaKSPackages()

        self.permanentSkipSteps = []
        self.skipSteps = []
        self.showSteps = []
        self.anaconda = anaconda
        self.id = self.anaconda.id
        self.onPart = {}

class EarlyKSHandler(superclass):
    # This handler class only processes a couple kickstart commands.  It is
    # used very early on in anaconda, when we don't yet have an interface
    # and are looking for (1) what sort of interface we need to set up, and
    # (2) what to ignore when we initialize storage.
    def __init__(self, anaconda):
        superclass.__init__(self, mapping=commandMap)

        self.anaconda = anaconda
        self.id = self.anaconda.id

        self.maskAllExcept(["vnc", "displaymode", "text", "cmdline",
                            "graphical", "rescue", "ignoredisk", "clearpart"])

class AnacondaPreParser(KickstartParser):
    # A subclass of KickstartParser that only looks for %pre scripts and
    # sets them up to be run.  All other scripts and commands are ignored.
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

def preScriptPass(anaconda, file):
    # The second pass through kickstart file processing - look for %pre scripts
    # and run them.  This must come in a separate pass in case a script
    # generates an included file that has commands for later.
    ksparser = AnacondaPreParser(AnacondaKSHandler(anaconda))

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

def earlyCommandPass(anaconda, file):
    # The first pass through kickstart file processing - look for the subset
    # of commands listed in EarlyKSHandler and set attributes based on those.
    # This has to be a separate pass because it needs to take place before
    # anaconda even knows what interface to run.
    try:
        file = preprocessKickstart(file)
    except KickstartError, msg:
        stdoutLog.critical(_("Error processing %%ksappend lines: %s") % msg)
        sys.exit(1)
    except Exception, e:
        stdoutLog.critical(_("Unknown error processing %%ksappend lines: %s") % e)
        sys.exit(1)

    handler = EarlyKSHandler(anaconda)
    ksparser = KickstartParser(handler, missingIncludeIsFatal=False)

    # We don't have an intf by now, so the best we can do is just print the
    # exception out.
    try:
        ksparser.readKickstart(file)
    except KickstartError, e:
        print _("The following error was found while parsing your "
                "kickstart configuration:\n\n%s") % e
        sys.exit(1)

    # And return the handler object so we can get information out of it.
    return handler

def fullCommandPass(anaconda, file, earlyKS):
    # We need to make sure storage is active before the rest of the kickstart
    # file is processed.  But before we initialize storage, we have to tell it
    # which disks to avoid, and we only get that information from the earlier
    # processing of the kickstart file.
    import storage
    anaconda.id.storage.ignoredDisks = earlyKS.ignoredisk.ignoredisk
    anaconda.id.storage.exclusiveDisks = earlyKS.ignoredisk.onlyuse

    if earlyKS.clearpart.type is not None:
        anaconda.id.storage.clearPartType = earlyKS.clearpart.type
        anaconda.id.storage.clearPartDisks = earlyKS.clearpart.drives
        if earlyKS.clearpart.initAll:
            anaconda.id.storage.reinitializeDisks = earlyKS.clearpart.initAll

    storage.storageInitialize(anaconda)

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
    dispatch.skipStep("network")

    # Storage is initialized for us right when kickstart processing starts.
    dispatch.skipStep("storageinit")

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
        ksdata.skipSteps.extend(["tasksel", "group-selection"])

        # Special check for this, since it doesn't make any sense.
        if ksdata.packages.seen:
            warnings.warn("Ignoring contents of %packages section due to upgrade.")
    elif havePackages(ksdata.packages):
        if interactive:
            ksdata.showSteps.extend(["tasksel", "group-selection"])
        else:
            ksdata.skipSteps.extend(["tasksel", "group-selection"])
    else:
        if ksdata.packages.seen:
            ksdata.skipSteps.extend(["tasksel", "group-selection"])
        else:
            ksdata.showSteps.extend(["tasksel", "group-selection"])

    if not interactive:
        for n in ksdata.skipSteps:
            dispatch.skipStep(n)
        for n in ksdata.permanentSkipSteps:
            dispatch.skipStep(n, permanent=1)
    for n in ksdata.showSteps:
        dispatch.skipStep(n, skip = 0)

    # Text mode doesn't have all the steps that graphical mode does, so we
    # can't stop and prompt for missing information.  Make sure we've got
    # everything that would be provided by a missing section now and error
    # out if we don't.
    if anaconda.id.displayMode == "t":
        missingSteps = [("bootloader", "Bootloader configuration"),
                        ("group-selection", "Package selection")]
        errors = []

        for (step, msg) in missingSteps:
            if not dispatch.stepInSkipList(step):
                errors.append(msg)

        if len(errors) > 0:
            anaconda.intf.kickstartErrorWindow(_("Your kickstart file is missing "
                "required information that anaconda cannot prompt for.  Please "
                "add the following sections and try again:\n%s") % ", ".join(errors))
            sys.exit(0)
