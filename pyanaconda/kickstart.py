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

from pyanaconda.errors import ScriptError, errorHandler
from storage.deviceaction import *
from storage.devices import LUKSDevice
from storage.devicelibs.lvm import getPossiblePhysicalExtents
from storage.devicelibs.mpath import MultipathConfigWriter, MultipathTopology
from storage.devicelibs import swap
from storage.formats import getFormat
from storage.partitioning import doPartitioning
from storage.partitioning import growLVM
import storage.iscsi
import storage.fcoe
import storage.zfcp

import glob
import iutil
import isys
import os
import os.path
import tempfile
from flags import flags
from constants import *
import shlex
import sys
import urlgrabber
import pykickstart.commands as commands
from storage.devices import *
from pyanaconda import keyboard
from pyanaconda import ntp
from pyanaconda import timezone
from pyanaconda import localization
from pyanaconda import network
from pyanaconda.simpleconfig import SimpleConfigFile
from pyanaconda.users import getPassAlgo
from pyanaconda.desktop import Desktop

from pykickstart.base import KickstartCommand
from pykickstart.constants import *
from pykickstart.errors import formatErrorMsg, KickstartError, KickstartValueError
from pykickstart.parser import KickstartParser
from pykickstart.parser import Script as KSScript
from pykickstart.sections import *
from pykickstart.version import returnClassForVersion

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")
stderrLog = logging.getLogger("anaconda.stderr")
storage_log = logging.getLogger("storage")
stdoutLog = logging.getLogger("anaconda.stdout")
from anaconda_log import logger, logLevelMap, setHandlersLevel,\
    DEFAULT_TTY_LEVEL

packagesSeen = False

# deviceMatches is called early, before any multipaths can possibly be coalesced
# so it needs to know about them in some additional way: have the topology ready.
topology = None

class AnacondaKSScript(KSScript):
    def run(self, chroot):
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
            # Always log outside the chroot, we copy those logs into the
            # chroot later.
            messages = "/tmp/%s.log" % os.path.basename(path)

        rc = iutil.execWithRedirect(self.interp, ["/tmp/%s" % os.path.basename(path)],
                                    stdin = messages, stdout = messages, stderr = messages,
                                    root = scriptRoot)

        # Always log an error.  Only fail if we have a handle on the
        # windowing system and the kickstart file included --erroronfail.
        if rc != 0:
            log.error("Error code %s running the kickstart script at line %s" % (rc, self.lineno))

            if os.path.isfile(messages):
                try:
                    f = open(messages, "r")
                except IOError as e:
                    err = None
                else:
                    err = f.readlines()
                    f.close()
                    for l in err:
                        log.error("\t%s" % l)

            if self.errorOnFail:
                errorHandler.cb(ScriptError(), self.lineno, err)
                sys.exit(0)

class AnacondaInternalScript(AnacondaKSScript):
    def __init__(self, *args, **kwargs):
        AnacondaKSScript.__init__(self, *args, **kwargs)
        self._hidden = True

    def __str__(self):
        # Scripts that implement portions of anaconda (copying screenshots and
        # log files, setfilecons, etc.) should not be written to the output
        # kickstart file.
        return ""

def getEscrowCertificate(escrowCerts, url):
    if not url:
        return None

    if url in escrowCerts:
        return escrowCerts[url]

    needs_net = not url.startswith("/") and not url.startswith("file:")
    if needs_net and not network.hasActiveNetDev():
        msg = _("Escrow certificate %s requires the network.") % url
        raise KickstartError(msg)

    log.info("escrow: downloading %s" % (url,))

    try:
        f = urlgrabber.urlopen(url)
    except urlgrabber.grabber.URLGrabError as e:
        msg = _("The following error was encountered while downloading the escrow certificate:\n\n%s" % e)
        raise KickstartError(msg)

    try:
        escrowCerts[url] = f.read()
    finally:
        f.close()

    return escrowCerts[url]

def detect_multipaths():
    global topology
    mcw = MultipathConfigWriter()
    cfg = mcw.write(friendly_names=True)
    with open("/etc/multipath.conf", "w+") as mpath_cfg:
        mpath_cfg.write(cfg)
    devices = udev_get_block_devices()
    topology = MultipathTopology(devices)

def deviceMatches(spec):
    full_spec = spec
    if not full_spec.startswith("/dev/"):
        full_spec = os.path.normpath("/dev/" + full_spec)

    # the regular case
    matches = udev_resolve_glob(full_spec)
    dev = udev_resolve_devspec(full_spec)
    # udev_resolve_devspec returns None if there's no match, but we don't
    # want that ending up in the list.
    if dev and dev not in matches:
        matches.append(dev)

    # now see if any mpaths and mpath members match
    for members in topology.multipaths_iter():
        mpath_name = udev_device_get_multipath_name(members[0])
        member_names = map(udev_device_get_name, members)
        if mpath_name == spec or (dev in member_names):
            # append the entire mpath
            matches.append(mpath_name)
            matches.extend(member_names)

    return matches

def lookupAlias(devicetree, alias):
    for dev in devicetree.devices:
        if getattr(dev, "req_name", None) == alias:
            return dev

    return None

# Remove any existing formatting on a device, but do not remove the partition
# itself.  This sets up an existing device to be used in a --onpart option.
def removeExistingFormat(device, storage):
    deps = storage.deviceDeps(device)
    while deps:
        leaves = [d for d in deps if d.isleaf]
        for leaf in leaves:
            storage.destroyDevice(leaf)
            deps.remove(leaf)

    storage.devicetree.registerAction(ActionDestroyFormat(device))

###
### SUBCLASSES OF PYKICKSTART COMMAND HANDLERS
###

class Authconfig(commands.authconfig.FC3_Authconfig):
    def execute(self, *args):
        args = ["--update", "--nostart"] + shlex.split(self.authconfig)

        if not flags.automatedInstall and \
           (os.path.exists(ROOT_PATH + "/lib64/security/pam_fprintd.so") or \
            os.path.exists(ROOT_PATH + "/lib/security/pam_fprintd.so")):
            args += ["--enablefingerprint"]

        try:
            iutil.execWithRedirect("/usr/sbin/authconfig", args,
                                   stdout="/dev/tty5", stderr="/dev/tty5",
                                   root=ROOT_PATH)
        except RuntimeError as msg:
            log.error("Error running /usr/sbin/authconfig %s: %s", args, msg)

class AutoPart(commands.autopart.F18_AutoPart):
    def execute(self, storage, ksdata, instClass):
        from pyanaconda.storage.partitioning import doAutoPartition

        if not self.autopart:
            return

        # sets up default autopartitioning.  use clearpart separately
        # if you want it
        instClass.setDefaultPartitioning(storage)
        storage.doAutoPart = True

        if self.encrypted:
            storage.encryptedAutoPart = True
            storage.encryptionPassphrase = self.passphrase
            storage.encryptionCipher = self.cipher
            storage.autoPartEscrowCert = getEscrowCertificate(storage.escrowCertificates, self.escrowcert)
            storage.autoPartAddBackupPassphrase = self.backuppassphrase

        if self.type is not None:
            storage.autoPartType = self.type

        doAutoPartition(storage, ksdata)

class Bootloader(commands.bootloader.F18_Bootloader):
    def execute(self, storage, ksdata, instClass):
        if self.location == "none":
            location = None
        elif self.location == "partition":
            location = "boot"
        else:
            location = self.location

        if self.upgrade and not flags.cmdline.has_key("preupgrade"):
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Selected upgrade mode for bootloader but not doing an upgrade")

        if self.upgrade and storage.bootloader.can_update:
            storage.bootloader.update_only = True

        if not location:
            storage.bootloader.skip_bootloader = True
            return

        if self.appendLine:
            args = self.appendLine.split()
            storage.bootloader.boot_args.update(args)

        if self.password:
            if self.isCrypted:
                storage.bootloader.encrypted_password = self.password
            else:
                storage.bootloader.password = self.password

        if location:
            storage.bootloader.set_preferred_stage1_type(location)

        if self.timeout is not None:
            storage.bootloader.timeout = self.timeout

        # Throw out drives specified that don't exist.
        disk_names = [d.name for d in storage.disks
                                if not d.format.hidden and not d.protected]
        for drive in self.driveorder[:]:
            if drive not in disk_names:
                log.warning("requested drive %s in boot drive order doesn't exist" % drive)
                self.driveorder.remove(drive)

        storage.bootloader.disk_order = self.driveorder

        if self.bootDrive:
            if not self.bootDrive in disk_names:
                raise KickstartValueError, formatErrorMsg(self.lineno,
                        msg="Requested boot drive %s doesn't exist" % self.bootDrive)
        else:
            self.bootDrive = disk_names[0]

        spec = udev_resolve_devspec(self.bootDrive)
        drive = storage.devicetree.getDeviceByName(spec)
        storage.bootloader.stage1_disk = drive

        if self.leavebootorder:
            flags.leavebootorder = True

class BTRFS(commands.btrfs.F17_BTRFS):
    def execute(self, storage, ksdata, instClass):
        for b in self.btrfsList:
            b.execute(storage, ksdata, instClass)

class BTRFSData(commands.btrfs.F17_BTRFSData):
    def execute(self, storage, ksdata, instClass):
        devicetree = storage.devicetree

        storage.doAutoPart = False

        members = []

        # Get a list of all the devices that make up this volume.
        for member in self.devices:
            # if using --onpart, use original device
            member_name = ksdata.onPart.get(member, member)
            if member_name:
                dev = devicetree.getDeviceByName(member_name) or lookupAlias(devicetree, member)
            if not dev:
                dev = devicetree.resolveDevice(member)

            if dev and dev.format.type == "luks":
                try:
                    dev = devicetree.getChildren(dev)[0]
                except IndexError:
                    dev = None
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use undefined partition %s in BTRFS volume specification" % member)

            members.append(dev)

        if self.subvol:
            name = self.name
        elif self.label:
            name = self.label
        else:
            name = None

        if len(members) == 0 and not self.preexist:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="BTRFS volume defined without any member devices.  Either specify member devices or use --useexisting.")

        # allow creating btrfs vols/subvols without specifying mountpoint
        if self.mountpoint in ("none", "None"):
            self.mountpoint = ""

        # Sanity check mountpoint
        if self.mountpoint != "" and self.mountpoint[0] != '/':
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The mount point \"%s\" is not valid." % (self.mountpoint,))

        if self.preexist:
            device = devicetree.getDeviceByName(self.name)
            if not device:
                device = udev_resolve_devspec(self.name)

            if not device:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent BTRFS volume %s in btrfs command" % self.name)
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if self.mountpoint:
                    device = storage.mountpoints[self.mountpoint]
                    storage.destroyDevice(device)
            except KeyError:
                pass

            request = storage.newBTRFS(name=name,
                                       subvol=self.subvol,
                                       mountpoint=self.mountpoint,
                                       metaDataLevel=self.metaDataLevel,
                                       dataLevel=self.dataLevel,
                                       parents=members)

            storage.createDevice(request)

class ClearPart(commands.clearpart.F17_ClearPart):
    def parse(self, args):
        retval = commands.clearpart.F17_ClearPart.parse(self, args)

        if self.type is None:
            self.type = CLEARPART_TYPE_NONE

        # Do any glob expansion now, since we need to have the real list of
        # disks available before the execute methods run.
        drives = []
        for spec in self.drives:
            matched = deviceMatches(spec)
            if matched:
                drives.extend(matched)
            else:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in clearpart command" % spec)

        self.drives = drives

        # Do any glob expansion now, since we need to have the real list of
        # devices available before the execute methods run.
        devices = []
        for spec in self.devices:
            matched = deviceMatches(spec)
            if matched:
                devices.extend(matched)
            else:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent device %s in clearpart device list" % spec)

        self.devices = devices

        return retval

    def execute(self, storage, ksdata, instClass):
        storage.config.clearPartType = self.type
        storage.config.clearPartDisks = self.drives
        storage.config.clearPartDevices = self.devices

        if self.initAll:
            storage.config.initializeDisks = self.initAll

        storage.clearPartitions()

class Fcoe(commands.fcoe.F13_Fcoe):
    def parse(self, args):
        fc = commands.fcoe.F13_Fcoe.parse(self, args)

        if fc.nic not in isys.getDeviceProperties():
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent nic %s in fcoe command" % fc.nic)

        storage.fcoe.fcoe().addSan(nic=fc.nic, dcb=fc.dcb, auto_vlan=True)

        return fc

class Firewall(commands.firewall.F14_Firewall):
    def execute(self, storage, ksdata, instClass):
        args = []
        # enabled is None if neither --enable or --disable is passed
        # default to enabled if nothing has been set.
        if self.enabled == False:
            args += ["--disabled"]
        else:
            args += ["--enabled"]

        if not "ssh" in self.services and not "22:tcp" in self.ports:
            args += ["--service=ssh"]

        for dev in self.trusts:
            args += [ "--trust=%s" % (dev,) ]

        for port in self.ports:
            args += [ "--port=%s" % (port,) ]

        for service in self.services:
            args += [ "--service=%s" % (service,) ]

        cmd = "/usr/bin/firewall-offline-cmd"
        if not os.path.exists(ROOT_PATH+cmd):
            msg = _("%s is missing. Cannot setup firewall.") % (cmd,)
            raise KickstartError(msg)
        else:
            iutil.execWithRedirect(cmd, args,
                                   stdout="/dev/tty5", stderr="/dev/tty5",
                                   root=ROOT_PATH)

class Firstboot(commands.firstboot.FC3_Firstboot):
    def execute(self, *args):
        if not os.path.exists(ROOT_PATH + "/lib/systemd/system/firstboot-graphical.service"):
            return

        action = "enable"

        if self.firstboot == FIRSTBOOT_SKIP:
            action = "disable"
        elif self.firstboot == FIRSTBOOT_RECONFIG:
            f = open(ROOT_PATH + "/etc/reconfigSys", "w+")
            f.close()

        iutil.execWithRedirect("systemctl", [action, "firstboot-graphical.service"],
                               stdout="/dev/tty5", stderr="/dev/tty5",
                               root=ROOT_PATH)

class Group(commands.group.F12_Group):
    def execute(self, storage, ksdata, instClass, users):
        algo = getPassAlgo(ksdata.authconfig.authconfig)

        for grp in self.groupList:
            kwargs = grp.__dict__
            kwargs.update({"root": ROOT_PATH})
            if not users.createGroup(grp.name, **kwargs):
                log.error("Group %s already exists, not creating." % grp.name)

class IgnoreDisk(commands.ignoredisk.RHEL6_IgnoreDisk):
    def parse(self, args):
        retval = commands.ignoredisk.RHEL6_IgnoreDisk.parse(self, args)

        # See comment in ClearPart.parse
        drives = []
        for spec in self.ignoredisk:
            matched = deviceMatches(spec)
            if matched:
                drives.extend(matched)
            else:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in ignoredisk command" % spec)

        self.ignoredisk = drives

        drives = []
        for spec in self.onlyuse:
            matched = deviceMatches(spec)
            if matched:
                drives.extend(matched)
            else:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in ignoredisk command" % spec)

        self.onlyuse = drives

        return retval

class Iscsi(commands.iscsi.F17_Iscsi):
    def parse(self, args):
        tg = commands.iscsi.F17_Iscsi.parse(self, args)

        if tg.iface:
            active_ifaces = network.getActiveNetDevs()
            if tg.iface not in active_ifaces:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="network interface %s required by iscsi %s target is not up" % (tg.iface, tg.target))

        mode = storage.iscsi.iscsi().mode
        if mode == "none":
            if tg.iface:
                storage.iscsi.iscsi().create_interfaces(active_ifaces)
        elif ((mode == "bind" and not tg.iface)
              or (mode == "default" and tg.iface)):
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="iscsi --iface must be specified (binding used) either for all targets or for none")

        try:
            storage.iscsi.iscsi().addTarget(tg.ipaddr, tg.port, tg.user,
                                            tg.password, tg.user_in,
                                            tg.password_in,
                                            target=tg.target,
                                            iface=tg.iface)
            log.info("added iscsi target %s at %s via %s" %(tg.target,
                                                            tg.ipaddr,
                                                            tg.iface))
        except (IOError, ValueError) as e:
            raise KickstartValueError, formatErrorMsg(self.lineno,
                                                      msg=str(e))

        return tg

class IscsiName(commands.iscsiname.FC6_IscsiName):
    def parse(self, args):
        retval = commands.iscsiname.FC6_IscsiName.parse(self, args)

        storage.iscsi.iscsi().initiator = self.iscsiname
        return retval

class Lang(commands.lang.FC3_Lang):
    def execute(self, *args, **kwargs):
        localization.write_language_configuration(self, ROOT_PATH)

class LogVol(commands.logvol.F18_LogVol):
    def execute(self, storage, ksdata, instClass):
        for l in self.lvList:
            l.execute(storage, ksdata, instClass)

        if self.lvList:
            growLVM(storage)

class LogVolData(commands.logvol.F18_LogVolData):
    def execute(self, storage, ksdata, instClass):
        devicetree = storage.devicetree

        storage.doAutoPart = False

        if self.mountpoint == "swap":
            type = "swap"
            self.mountpoint = ""
            if self.recommended or self.hibernation:
                self.size = swap.swapSuggestion(hibernation=self.hibernation)
                self.grow = False
        else:
            if self.fstype != "":
                type = self.fstype
            else:
                type = storage.defaultFSType

        # Sanity check mountpoint
        if self.mountpoint != "" and self.mountpoint[0] != '/':
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The mount point \"%s\" is not valid." % (self.mountpoint,))

        # Check that the VG this LV is a member of has already been specified.
        vg = devicetree.getDeviceByName(self.vgname)
        if not vg:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="No volume group exists with the name \"%s\".  Specify volume groups before logical volumes." % self.vgname)

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not self.format:
            if not self.name:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--noformat used without --name")

            dev = devicetree.getDeviceByName("%s-%s" % (vg.name, self.name))
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No preexisting logical volume with the name \"%s\" was found." % self.name)

            if self.resize:
                if self.size < dev.currentSize:
                    # shrink
                    try:
                        devicetree.registerAction(ActionResizeFormat(dev, self.size))
                        devicetree.registerAction(ActionResizeDevice(dev, self.size))
                    except ValueError:
                        raise KickstartValueError(formatErrorMsg(self.lineno,
                                msg="Invalid target size (%d) for device %s" % (self.size, dev.name)))
                else:
                    # grow
                    try:
                        devicetree.registerAction(ActionResizeDevice(dev, self.size))
                        devicetree.registerAction(ActionResizeFormat(dev, self.size))
                    except ValueError:
                        raise KickstartValueError(formatErrorMsg(self.lineno,
                                msg="Invalid target size (%d) for device %s" % (self.size, dev.name)))

            dev.format.mountpoint = self.mountpoint
            dev.format.mountopts = self.fsopts
            return

        # Make sure this LV name is not already used in the requested VG.
        if not self.preexist:
            tmp = devicetree.getDeviceByName("%s-%s" % (vg.name, self.name))
            if tmp:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Logical volume name already used in volume group %s" % vg.name)

            # Size specification checks
            if not self.percent:
                if not self.size:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Size required")
                elif not self.grow and self.size*1024 < vg.peSize:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Logical volume size must be larger than the volume group physical extent size.")
            elif self.percent <= 0 or self.percent > 100:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Percentage must be between 0 and 100")

        # Now get a format to hold a lot of these extra values.
        format = getFormat(type,
                           mountpoint=self.mountpoint,
                           label=self.label,
                           fsprofile=self.fsprofile,
                           mountopts=self.fsopts)
        if not format.type:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % type)

        # If we were given a pre-existing LV to create a filesystem on, we need
        # to verify it and its VG exists and then schedule a new format action
        # to take place there.  Also, we only support a subset of all the
        # options on pre-existing LVs.
        if self.preexist:
            device = devicetree.getDeviceByName("%s-%s" % (vg.name, self.name))
            if not device:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent LV %s in logvol command" % self.name)

            removeExistingFormat(device, storage)

            if self.resize:
                try:
                    devicetree.registerAction(ActionResizeDevice(device, self.size))
                except ValueError:
                    raise KickstartValueError(formatErrorMsg(self.lineno,
                            msg="Invalid target size (%d) for device %s" % (self.size, device.name)))

            devicetree.registerAction(ActionCreateFormat(device, format))
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if self.mountpoint:
                    device = storage.mountpoints[self.mountpoint]
                    storage.destroyDevice(device)
            except KeyError:
                pass

            request = storage.newLV(format=format,
                                    name=self.name,
                                    parents=[vg],
                                    size=self.size,
                                    grow=self.grow,
                                    maxsize=self.maxSizeMB,
                                    percent=self.percent)

            storage.createDevice(request)

        if self.encrypted:
            if self.passphrase and not storage.encryptionPassphrase:
                storage.encryptionPassphrase = self.passphrase

            cert = getEscrowCertificate(storage.escrowCertificates, self.escrowcert)
            if self.preexist:
                luksformat = format
                device.format = getFormat("luks", passphrase=self.passphrase, device=device.path,
                                          cipher=self.cipher,
                                          escrow_cert=cert,
                                          add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = getFormat("luks", passphrase=self.passphrase,
                                           cipher=self.cipher,
                                           escrow_cert=cert,
                                           add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=request)
            storage.createDevice(luksdev)

class Logging(commands.logging.FC6_Logging):
    def execute(self, *args):
        if logger.tty_loglevel == DEFAULT_TTY_LEVEL:
            # not set from the command line
            level = logLevelMap[self.level]
            logger.tty_loglevel = level
            setHandlersLevel(log, level)
            setHandlersLevel(storage_log, level)

        if logger.remote_syslog == None and len(self.host) > 0:
            # not set from the command line, ok to use kickstart
            remote_server = self.host
            if self.port:
                remote_server = "%s:%s" %(self.host, self.port)
            logger.updateRemote(remote_server)

class Network(commands.network.F18_Network):
    def execute(self, storage, ksdata, instClass):
        network.write_network_config(storage, ksdata, instClass, ROOT_PATH)

class MultiPath(commands.multipath.FC6_MultiPath):
    def parse(self, args):
        raise NotImplementedError("The multipath kickstart command is not currently supported")

class DmRaid(commands.dmraid.FC6_DmRaid):
    def parse(self, args):
        raise NotImplementedError("The dmraid kickstart command is not currently supported")

class Partition(commands.partition.F18_Partition):
    def execute(self, storage, ksdata, instClass):
        for p in self.partitions:
            p.execute(storage, ksdata, instClass)

        if self.partitions:
            doPartitioning(storage)

class PartitionData(commands.partition.F18_PartData):
    def execute(self, storage, ksdata, instClass):
        devicetree = storage.devicetree
        kwargs = {}

        storage.doAutoPart = False

        if self.onbiosdisk != "":
            for (disk, biosdisk) in storage.eddDict.iteritems():
                if "%x" % biosdisk == self.onbiosdisk:
                    self.disk = disk
                    break

            if not self.disk:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified BIOS disk %s cannot be determined" % self.onbiosdisk)

        if self.mountpoint == "swap":
            type = "swap"
            self.mountpoint = ""
            if self.recommended or self.hibernation:
                self.size = swap.swapSuggestion(hibernation=self.hibernation)
                self.grow = False
        # if people want to specify no mountpoint for some reason, let them
        # this is really needed for pSeries boot partitions :(
        elif self.mountpoint == "None":
            self.mountpoint = ""
            if self.fstype:
                type = self.fstype
            else:
                type = storage.defaultFSType
        elif self.mountpoint == 'appleboot':
            type = "appleboot"
            self.mountpoint = ""
        elif self.mountpoint == 'prepboot':
            type = "prepboot"
            self.mountpoint = ""
        elif self.mountpoint == 'biosboot':
            type = "biosboot"
            self.mountpoint = ""
        elif self.mountpoint.startswith("raid."):
            type = "mdmember"
            kwargs["name"] = self.mountpoint
            self.mountpoint = ""

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="RAID partition defined multiple times")

            if self.onPart:
                ksdata.onPart[kwargs["name"]] = self.onPart
        elif self.mountpoint.startswith("pv."):
            type = "lvmpv"
            kwargs["name"] = self.mountpoint
            self.mountpoint = ""

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="PV partition defined multiple times")

            if self.onPart:
                ksdata.onPart[kwargs["name"]] = self.onPart
        elif self.mountpoint.startswith("btrfs."):
            type = "btrfs"
            kwargs["name"] = self.mountpoint
            self.mountpoint = ""

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="BTRFS partition defined multiple times")

            if self.onPart:
                ksdata.onPart[kwargs["name"]] = self.onPart
        elif self.mountpoint == "/boot/efi":
            if iutil.isMactel():
                type = "hfs+"
            else:
                type = "EFI System Partition"
                self.fsopts = "defaults,uid=0,gid=0,umask=0077,shortname=winnt"
        else:
            if self.fstype != "":
                type = self.fstype
            elif self.mountpoint == "/boot":
                type = storage.defaultBootFSType
            else:
                type = storage.defaultFSType

        # If this specified an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not self.format:
            if not self.onPart:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--noformat used without --onpart")

            dev = devicetree.getDeviceByName(udev_resolve_devspec(self.onPart))
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No preexisting partition with the name \"%s\" was found." % self.onPart)

            if self.resize:
                if self.size < dev.currentSize:
                    # shrink
                    try:
                        devicetree.registerAction(ActionResizeFormat(dev, self.size))
                        devicetree.registerAction(ActionResizeDevice(dev, self.size))
                    except ValueError:
                        raise KickstartValueError(formatErrorMsg(self.lineno,
                                msg="Invalid target size (%d) for device %s" % (self.size, dev.name)))
                else:
                    # grow
                    try:
                        devicetree.registerAction(ActionResizeDevice(dev, self.size))
                        devicetree.registerAction(ActionResizeFormat(dev, self.size))
                    except ValueError:
                        raise KickstartValueError(formatErrorMsg(self.lineno,
                                msg="Invalid target size (%d) for device %s" % (self.size, dev.name)))

            dev.format.mountpoint = self.mountpoint
            dev.format.mountopts = self.fsopts
            return

        # Now get a format to hold a lot of these extra values.
        kwargs["format"] = getFormat(type,
                                     mountpoint=self.mountpoint,
                                     label=self.label,
                                     fsprofile=self.fsprofile,
                                     mountopts=self.fsopts)
        if not kwargs["format"].type:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % type)

        # If we were given a specific disk to create the partition on, verify
        # that it exists first.  If it doesn't exist, see if it exists with
        # mapper/ on the front.  If that doesn't exist either, it's an error.
        if self.disk:
            names = [self.disk, "mapper/" + self.disk]
            for n in names:
                disk = devicetree.getDeviceByName(udev_resolve_devspec(n))
                # if this is a multipath member promote it to the real mpath
                if disk and disk.format.type == "multipath_member":
                    mpath_device = storage.devicetree.getChildren(disk)[0]
                    storage_log.info("kickstart: part: promoting %s to %s"
                                     % (disk.name, mpath_device.name))
                    disk = mpath_device
                if not disk:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in partition command" % n)
                if not disk.partitionable:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Cannot install to read-only media %s." % n)

                should_clear = storage.shouldClear(disk)
                if disk and (disk.partitioned or should_clear):
                    kwargs["parents"] = [disk]
                    break
                elif disk:
                    raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified unpartitioned disk %s in partition command" % self.disk)

            if not kwargs["parents"]:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent disk %s in partition command" % self.disk)

        kwargs["grow"] = self.grow
        kwargs["size"] = self.size
        kwargs["maxsize"] = self.maxSizeMB
        kwargs["primary"] = self.primOnly

        # If we were given a pre-existing partition to create a filesystem on,
        # we need to verify it exists and then schedule a new format action to
        # take place there.  Also, we only support a subset of all the options
        # on pre-existing partitions.
        if self.onPart:
            device = devicetree.getDeviceByName(udev_resolve_devspec(self.onPart))
            if not device:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specified nonexistent partition %s in partition command" % self.onPart)

            removeExistingFormat(device, storage)
            if self.resize:
                try:
                    devicetree.registerAction(ActionResizeDevice(device, self.size))
                except ValueError:
                    raise KickstartValueError(formatErrorMsg(self.lineno,
                            msg="Invalid target size (%d) for device %s" % (self.size, device.name)))

            devicetree.registerAction(ActionCreateFormat(device, kwargs["format"]))
        else:
            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if self.mountpoint:
                    device = storage.mountpoints[self.mountpoint]
                    storage.destroyDevice(device)
            except KeyError:
                pass

            request = storage.newPartition(**kwargs)
            storage.createDevice(request)

        if self.encrypted:
            if self.passphrase and not storage.encryptionPassphrase:
               storage.encryptionPassphrase = self.passphrase

            cert = getEscrowCertificate(storage.escrowCertificates, self.escrowcert)
            if self.onPart:
                luksformat = format
                device.format = getFormat("luks", passphrase=self.passphrase, device=device.path,
                                          cipher=self.cipher,
                                          escrow_cert=cert,
                                          add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = getFormat("luks", passphrase=self.passphrase,
                                           cipher=self.cipher,
                                           escrow_cert=cert,
                                           add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=request)
            storage.createDevice(luksdev)

class Raid(commands.raid.F18_Raid):
    def execute(self, storage, ksdata, instClass):
        for r in self.raidList:
            r.execute(storage, ksdata, instClass)

class RaidData(commands.raid.F18_RaidData):
    def execute(self, storage, ksdata, instClass):
        raidmems = []
        devicename = "md%d" % self.device

        devicetree = storage.devicetree
        kwargs = {}

        storage.doAutoPart = False

        if self.mountpoint == "swap":
            type = "swap"
            self.mountpoint = ""
        elif self.mountpoint.startswith("pv."):
            type = "lvmpv"
            kwargs["name"] = self.mountpoint
            ksdata.onPart[kwargs["name"]] = devicename

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="PV partition defined multiple times")

            self.mountpoint = ""
        elif self.mountpoint.startswith("btrfs."):
            type = "btrfs"
            kwargs["name"] = self.mountpoint
            ksdata.onPart[kwargs["name"]] = devicename

            if devicetree.getDeviceByName(kwargs["name"]):
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="BTRFS partition defined multiple times")

            self.mountpoint = ""
        else:
            if self.fstype != "":
                type = self.fstype
            elif self.mountpoint == "/boot" and \
                 "mdarray" in storage.bootloader.stage2_device_types:
                type = storage.defaultBootFSType
            else:
                type = storage.defaultFSType

        # Sanity check mountpoint
        if self.mountpoint != "" and self.mountpoint[0] != '/':
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The mount point is not valid.")

        # If this specifies an existing request that we should not format,
        # quit here after setting up enough information to mount it later.
        if not self.format:
            if not devicename:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--noformat used without --device")

            dev = devicetree.getDeviceByName(devicename)
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No preexisting RAID device with the name \"%s\" was found." % devicename)

            dev.format.mountpoint = self.mountpoint
            dev.format.mountopts = self.fsopts
            return

        # Get a list of all the RAID members.
        for member in self.members:
            # if member is using --onpart, use original device
            mem = ksdata.onPart.get(member, member)
            dev = devicetree.getDeviceByName(mem) or lookupAlias(devicetree, mem)
            if dev and dev.format.type == "luks":
                try:
                    dev = devicetree.getChildren(dev)[0]
                except IndexError:
                    dev = None
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use undefined partition %s in RAID specification" % mem)

            raidmems.append(dev)

        # Now get a format to hold a lot of these extra values.
        kwargs["format"] = getFormat(type,
                                     label=self.label,
                                     fsprofile=self.fsprofile,
                                     mountpoint=self.mountpoint,
                                     mountopts=self.fsopts)
        if not kwargs["format"].type:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="The \"%s\" filesystem type is not supported." % type)

        kwargs["name"] = devicename
        kwargs["level"] = self.level
        kwargs["parents"] = raidmems
        kwargs["memberDevices"] = len(raidmems) - self.spares
        kwargs["totalDevices"] = len(raidmems)

        # If we were given a pre-existing RAID to create a filesystem on,
        # we need to verify it exists and then schedule a new format action
        # to take place there.  Also, we only support a subset of all the
        # options on pre-existing RAIDs.
        if self.preexist:
            device = devicetree.getDeviceByName(devicename)
            if not device:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Specifeid nonexistent RAID %s in raid command" % devicename)

            removeExistingFormat(device, storage)
            devicetree.registerAction(ActionCreateFormat(device, kwargs["format"]))
        else:
            if devicename and devicename in [a.name for a in storage.mdarrays]:
                raise KickstartValueError(formatErrorMsg(self.lineno, msg="The Software RAID array name \"%s\" is already in use." % devicename))

            # If a previous device has claimed this mount point, delete the
            # old one.
            try:
                if self.mountpoint:
                    device = storage.mountpoints[self.mountpoint]
                    storage.destroyDevice(device)
            except KeyError:
                pass

            try:
                request = storage.newMDArray(**kwargs)
            except ValueError as e:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg=str(e))

            storage.createDevice(request)

        if self.encrypted:
            if self.passphrase and not storage.encryptionPassphrase:
               storage.encryptionPassphrase = self.passphrase

            cert = getEscrowCertificate(storage.escrowCertificates, self.escrowcert)
            if self.preexist:
                luksformat = format
                device.format = getFormat("luks", passphrase=self.passphrase, device=device.path,
                                          cipher=self.cipher,
                                          escrow_cert=cert,
                                          add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=device)
            else:
                luksformat = request.format
                request.format = getFormat("luks", passphrase=self.passphrase,
                                           cipher=self.cipher,
                                           escrow_cert=cert,
                                           add_backup_passphrase=self.backuppassphrase)
                luksdev = LUKSDevice("luks%d" % storage.nextID,
                                     format=luksformat,
                                     parents=request)
            storage.createDevice(luksdev)

class RootPw(commands.rootpw.F18_RootPw):
    def execute(self, storage, ksdata, instClass, users):
        algo = getPassAlgo(ksdata.authconfig.authconfig)
        users.setRootPassword(self.password, self.isCrypted, self.lock, algo)

class SELinux(commands.selinux.FC3_SELinux):
    def execute(self, *args):
        selinux_states = { SELINUX_DISABLED: "disabled",
                           SELINUX_ENFORCING: "enforcing",
                           SELINUX_PERMISSIVE: "permissive" }

        if self.selinux not in selinux_states:
            log.error("unknown selinux state: %s" % (self.selinux,))
            return

        try:
            selinux_cfg = SimpleConfigFile(ROOT_PATH+"/etc/selinux/config")
            selinux_cfg.read()
            selinux_cfg.set(("SELINUX", selinux_states[self.selinux]))
            selinux_cfg.write()
        except IOError as msg:
            log.error ("Error setting selinux mode: %s" % (msg,))

class Services(commands.services.FC6_Services):
    def execute(self, storage, ksdata, instClass):
        disabled = map(lambda s: s + ".service", self.disabled)
        enabled = map(lambda s: s + ".service", self.enabled)

        if disabled:
            iutil.execWithRedirect("systemctl", ["disable"] + disabled,
                                   stdout="/dev/tty5", stderr="/dev/tty5",
                                   root=ROOT_PATH)

        if enabled:
            iutil.execWithRedirect("systemctl", ["enable"] + enabled,
                                   stdout="/dev/tty5", stderr="/dev/tty5",
                                   root=ROOT_PATH)

class Timezone(commands.timezone.F18_Timezone):
    def __init__(self, *args):
        commands.timezone.F18_Timezone.__init__(self, *args)

        #TODO: Do we need to set it to False in case of dual-boot?
        #default to UTC HW clock in Anaconda
        self.isUtc = True

    def execute(self, *args):
        # write out timezone configuration
        if not timezone.is_valid_timezone(self.timezone):
            # this should never happen, but for pity's sake
            log.warning("Timezone %s set in kickstart is not valid, falling "\
                        "back to default (America/New_York)." % (self.timezone,))
            self.timezone = "America/New_York"

        timezone.write_timezone_config(self, ROOT_PATH)

        # write out NTP configuration (if set)
        if not self.nontp and self.ntpservers:
            chronyd_conf_path = os.path.normpath(ROOT_PATH + ntp.NTP_CONFIG_FILE)
            try:
                ntp.save_servers_to_config(self.ntpservers,
                                           conf_file_path=chronyd_conf_path)
            except ntp.NTPconfigError as ntperr:
                log.warning("Failed to save NTP configuration: %s" % ntperr)

class User(commands.user.F12_User):
    def execute(self, storage, ksdata, instClass, users):
        algo = getPassAlgo(ksdata.authconfig.authconfig)

        for usr in self.userList:
            kwargs = usr.__dict__
            kwargs.update({"algo": algo, "root": ROOT_PATH})
            if not users.createUser(usr.name, **kwargs):
                log.error("User %s already exists, not creating." % usr.name)

class VolGroup(commands.volgroup.FC16_VolGroup):
    def execute(self, storage, ksdata, instClass):
        for v in self.vgList:
            v.execute(storage, ksdata, instClass)

class VolGroupData(commands.volgroup.FC16_VolGroupData):
    def execute(self, storage, ksdata, instClass):
        pvs = []

        devicetree = storage.devicetree

        storage.doAutoPart = False

        # Get a list of all the physical volume devices that make up this VG.
        for pv in self.physvols:
            # if pv is using --onpart, use original device
            pv = ksdata.onPart.get(pv, pv)
            dev = devicetree.getDeviceByName(pv) or lookupAlias(devicetree, pv)
            if dev and dev.format.type == "luks":
                try:
                    dev = devicetree.getChildren(dev)[0]
                except IndexError:
                    dev = None
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="Tried to use undefined partition %s in Volume Group specification" % pv)

            pvs.append(dev)

        if len(pvs) == 0 and not self.preexist:
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Volume group defined without any physical volumes.  Either specify physical volumes or use --useexisting.")

        if self.pesize not in getPossiblePhysicalExtents(floor=1024):
            raise KickstartValueError, formatErrorMsg(self.lineno, msg="Volume group specified invalid pesize")

        # If --noformat or --useexisting was given, there's really nothing to do.
        if not self.format or self.preexist:
            if not self.vgname:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="--noformat or --useexisting used without giving a name")

            dev = devicetree.getDeviceByName(self.vgname)
            if not dev:
                raise KickstartValueError, formatErrorMsg(self.lineno, msg="No preexisting VG with the name \"%s\" was found." % self.vgname)
        elif self.vgname in [vg.name for vg in storage.vgs]:
            raise KickstartValueError(formatErrorMsg(self.lineno, msg="The volume group name \"%s\" is already in use." % self.vgname))
        else:
            request = storage.newVG(parents=pvs,
                                    name=self.vgname,
                                    peSize=self.pesize/1024.0)

            storage.createDevice(request)
            if self.reserved_space:
                request.reserved_space = self.reserved_space
            elif self.reserved_percent:
                request.reserved_percent = self.reserved_percent

class XConfig(commands.xconfig.F14_XConfig):
    def execute(self, *args):
        desktop = Desktop()
        if self.startX:
            desktop.setDefaultRunLevel(5)

        if self.defaultdesktop:
            desktop.setDefaultDesktop(self.defaultdesktop)

        # now write it out
        desktop.write()

class ZFCP(commands.zfcp.F14_ZFCP):
    def parse(self, args):
        fcp = commands.zfcp.F14_ZFCP.parse(self, args)
        try:
            storage.zfcp.ZFCP().addFCP(fcp.devnum, fcp.wwpn, fcp.fcplun)
        except ValueError as e:
            log.warning(str(e))

        return fcp

class Keyboard(commands.keyboard.F18_Keyboard):
    def execute(self, *args):
        keyboard.write_keyboard_config(self, ROOT_PATH)

    def dracutSetupArgs(self, *args):
        return keyboard.dracut_setup_args(self)

###
### HANDLERS
###

# This is just the latest entry from pykickstart.handlers.control with all the
# classes we're overriding in place of the defaults.
commandMap = {
        "auth": Authconfig,
        "authconfig": Authconfig,
        "autopart": AutoPart,
        "btrfs": BTRFS,
        "bootloader": Bootloader,
        "clearpart": ClearPart,
        "dmraid": DmRaid,
        "fcoe": Fcoe,
        "firewall": Firewall,
        "firstboot": Firstboot,
        "group": Group,
        "ignoredisk": IgnoreDisk,
        "iscsi": Iscsi,
        "iscsiname": IscsiName,
        "keyboard": Keyboard,
        "lang": Lang,
        "logging": Logging,
        "logvol": LogVol,
        "multipath": MultiPath,
        "network": Network,
        "part": Partition,
        "partition": Partition,
        "raid": Raid,
        "rootpw": RootPw,
        "selinux": SELinux,
        "services": Services,
        "timezone": Timezone,
        "user": User,
        "volgroup": VolGroup,
        "xconfig": XConfig,
        "zfcp": ZFCP,
}

dataMap = {
        "BTRFSData": BTRFSData,
        "LogVolData": LogVolData,
        "PartData": PartitionData,
        "RaidData": RaidData,
        "VolGroupData": VolGroupData,
}

superclass = returnClassForVersion()

class AnacondaKSHandler(superclass):
    def __init__ (self):
        superclass.__init__(self, commandUpdates=commandMap, dataUpdates=dataMap)
        self.onPart = {}

class AnacondaPreParser(KickstartParser):
    # A subclass of KickstartParser that only looks for %pre scripts and
    # sets them up to be run.  All other scripts and commands are ignored.
    def __init__ (self, handler, followIncludes=True, errorsAreFatal=True,
                  missingIncludeIsFatal=True):
        KickstartParser.__init__(self, handler, missingIncludeIsFatal=False)

    def handleCommand (self, lineno, args):
        pass

    def setupSections(self):
        self.registerSection(PreScriptSection(self.handler, dataObj=AnacondaKSScript))
        self.registerSection(NullSection(self.handler, sectionOpen="%post"))
        self.registerSection(NullSection(self.handler, sectionOpen="%traceback"))
        self.registerSection(NullSection(self.handler, sectionOpen="%packages"))

class AnacondaKSParser(KickstartParser):
    def __init__ (self, handler, followIncludes=True, errorsAreFatal=True,
                  missingIncludeIsFatal=True, scriptClass=AnacondaKSScript):
        self.scriptClass = scriptClass
        KickstartParser.__init__(self, handler)

    def handleCommand (self, lineno, args):
        if not self.handler:
            return

        return KickstartParser.handleCommand(self, lineno, args)

    def setupSections(self):
        self.registerSection(PreScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(PostScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(TracebackScriptSection(self.handler, dataObj=self.scriptClass))
        self.registerSection(PackageSection(self.handler))

def preScriptPass(f):
    # The first pass through kickstart file processing - look for %pre scripts
    # and run them.  This must come in a separate pass in case a script
    # generates an included file that has commands for later.
    ksparser = AnacondaPreParser(AnacondaKSHandler())

    try:
        ksparser.readKickstart(f)
    except KickstartError as e:
        errorHandler.cb(KickstartError(), e)
        sys.exit(1)

    # run %pre scripts
    runPreScripts(ksparser.handler.scripts)

def parseKickstart(f):
    # preprocessing the kickstart file has already been handled in initramfs.

    handler = AnacondaKSHandler()
    ksparser = AnacondaKSParser(handler)

    # We need this so all the /dev/disk/* stuff is set up before parsing.
    udev_trigger(subsystem="block", action="change")
    # So that drives onlined by these can be used in the ks file
    storage.iscsi.iscsi().startup()
    storage.fcoe.fcoe().startup()
    storage.zfcp.ZFCP().startup()
    # Note we do NOT call dasd.startup() here, that does not online drives, but
    # only checks if they need formatting, which requires zerombr to be known
    detect_multipaths()

    try:
        ksparser.readKickstart(f)
    except KickstartError as e:
        errorHandler.cb(KickstartError(), e)
        sys.exit(1)

    global packagesSeen
    packagesSeen = ksparser.getSection("%packages").timesSeen > 0
    return handler

def appendPostScripts(ksdata):
    scripts = ""

    # Read in all the post script snippets to a single big string.
    for fn in glob.glob("/usr/share/anaconda/post-scripts/*ks"):
        f = open(fn, "r")
        scripts += f.read()
        f.close()

    # Then parse the snippets against the existing ksdata.  We can do this
    # because pykickstart allows multiple parses to save their data into a
    # single data object.  Errors parsing the scripts are a bug in anaconda,
    # so just raise an exception.
    ksparser = AnacondaKSParser(ksdata, scriptClass=AnacondaInternalScript)
    ksparser.readKickstartFromString(scripts, reset=False)

def runPostScripts(scripts):
    postScripts = filter (lambda s: s.type == KS_SCRIPT_POST, scripts)

    if len(postScripts) == 0:
        return

    # Remove environment variables that cause problems for %post scripts.
    for var in ["LIBUSER_CONF"]:
        if os.environ.has_key(var):
            del(os.environ[var])

    log.info("Running kickstart %%post script(s)")
    map (lambda s: s.run(ROOT_PATH), postScripts)
    log.info("All kickstart %%post script(s) have been run")

def runPreScripts(scripts):
    preScripts = filter (lambda s: s.type == KS_SCRIPT_PRE, scripts)

    if len(preScripts) == 0:
        return

    log.info("Running kickstart %%pre script(s)")
    stdoutLog.info(_("Running pre-installation scripts"))

    map (lambda s: s.run("/"), preScripts)

    log.info("All kickstart %%pre script(s) have been run")

def runTracebackScripts(scripts):
    log.info("Running kickstart %%traceback script(s)")
    for script in filter (lambda s: s.type == KS_SCRIPT_TRACEBACK, scripts):
        script.run("/")
    log.info("All kickstart %%traceback script(s) have been run")

def doKickstartStorage(storage, ksdata, instClass):
    """ Setup storage state from the kickstart data """
    ksdata.clearpart.execute(storage, ksdata, instClass)
    if not [d for d in storage.disks if not d.format.hidden]:
        return
    ksdata.bootloader.execute(storage, ksdata, instClass)
    ksdata.autopart.execute(storage, ksdata, instClass)
    ksdata.partition.execute(storage, ksdata, instClass)
    ksdata.raid.execute(storage, ksdata, instClass)
    ksdata.volgroup.execute(storage, ksdata, instClass)
    ksdata.logvol.execute(storage, ksdata, instClass)
    ksdata.btrfs.execute(storage, ksdata, instClass)
    storage.setUpBootLoader()

