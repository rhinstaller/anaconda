# __init__.py
# Entry point for anaconda's storage configuration module.
#
# Copyright (C) 2009  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Dave Lehman <dlehman@redhat.com>
#

import os
import time
import stat
import errno
import sys
import statvfs

import nss.nss
import parted

from pyanaconda import isys
from pyanaconda import iutil
from pyanaconda.constants import *
from pykickstart.constants import *
from pyanaconda.flags import flags

from errors import *
from devices import *
from devicetree import DeviceTree
from deviceaction import *
from formats import getFormat
from formats import get_device_format_class
from formats import get_default_filesystem_type
from devicelibs.lvm import safeLvmName
from devicelibs.dm import name_from_dm_node
from devicelibs.crypto import generateBackupPassphrase
from devicelibs.mpath import MultipathConfigWriter
from devicelibs.edd import get_edd_dict
from udev import *
import iscsi
import fcoe
import zfcp
import dasd

import shelve
import contextlib

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")

def storageInitialize(anaconda):
    storage = anaconda.storage

    storage.shutdown()

    if anaconda.dir == DISPATCH_BACK:
        return

    # touch /dev/.in_sysinit so that /lib/udev/rules.d/65-md-incremental.rules
    # does not mess with any mdraid sets
    open("/dev/.in_sysinit", "w")

    # XXX I don't understand why I have to do this, but this is needed to
    #     populate the udev db
    udev_trigger(subsystem="block", action="change")

    # Before we set up the storage system, we need to know which disks to
    # ignore, etc.  Luckily that's all in the kickstart data.
    if anaconda.ksdata:
        anaconda.storage.config.zeroMbr = anaconda.ksdata.zerombr.zerombr
        anaconda.storage.config.ignoreDiskInteractive = anaconda.ksdata.ignoredisk.interactive
        anaconda.storage.config.ignoredDisks = anaconda.ksdata.ignoredisk.ignoredisk
        anaconda.storage.config.exclusiveDisks = anaconda.ksdata.ignoredisk.onlyuse

        if anaconda.ksdata.clearpart.type is not None:
            anaconda.storage.config.clearPartType = anaconda.ksdata.clearpart.type
            anaconda.storage.config.clearPartDisks = anaconda.ksdata.clearpart.drives
            if anaconda.ksdata.clearpart.initAll:
                anaconda.storage.config.reinitializeDisks = anaconda.ksdata.clearpart.initAll

    anaconda.intf.resetInitializeDiskQuestion()
    anaconda.intf.resetReinitInconsistentLVMQuestion()
    lvm.lvm_vg_blacklist = []

    # Set up the protected partitions list now.
    if anaconda.protected:
        storage.config.protectedDevSpecs.extend(anaconda.protected)
        storage.reset()

        if not flags.livecdInstall and not storage.protectedDevices:
            if anaconda.upgrade:
                return
            else:
                anaconda.intf.messageWindow(_("Unknown Device"),
                    _("The installation source given by device %s "
                      "could not be found.  Please check your "
                      "parameters and try again.") % anaconda.protected,
                    type="custom", custom_buttons = [_("_Exit installer")])
                sys.exit(1)
    else:
        storage.reset()

    if not storage.disks:
        rc = anaconda.intf.messageWindow(_("No disks found"),
                _("No usable disks have been found."),
                type="custom",
                custom_buttons = [_("Back"), _("_Exit installer")],
                default=0)
        if rc == 0:
            return DISPATCH_BACK
        sys.exit(1)

# dispatch.py helper function
def storageComplete(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        rc = anaconda.intf.messageWindow(_("Installation cannot continue."),
                                _("The storage configuration you have "
                                  "chosen has already been activated. You "
                                  "can no longer return to the disk editing "
                                  "screen. Would you like to continue with "
                                  "the installation process?"),
                                type = "yesno")
        if rc == 0:
            sys.exit(0)
        return DISPATCH_FORWARD

    devs = anaconda.storage.devicetree.getDevicesByType("luks/dm-crypt")
    existing_luks = False
    new_luks = False
    for dev in devs:
        if dev.exists:
            existing_luks = True
        else:
            new_luks = True

    if (anaconda.storage.encryptedAutoPart or new_luks) and \
       not anaconda.storage.encryptionPassphrase:
        while True:
            (passphrase, retrofit) = anaconda.intf.getLuksPassphrase(preexist=existing_luks)
            if passphrase:
                anaconda.storage.encryptionPassphrase = passphrase
                anaconda.storage.encryptionRetrofit = retrofit
                break
            else:
                rc = anaconda.intf.messageWindow(_("Encrypt device?"),
                            _("You specified block device encryption "
                              "should be enabled, but you have not "
                              "supplied a passphrase. If you do not "
                              "go back and provide a passphrase, "
                              "block device encryption will be "
                              "disabled."),
                              type="custom",
                              custom_buttons=[_("Back"), _("Continue")],
                              default=0)
                if rc == 1:
                    log.info("user elected to not encrypt any devices.")
                    undoEncryption(anaconda.storage)
                    anaconda.storage.encryptedAutoPart = False
                    break

    if anaconda.storage.encryptionPassphrase:
        for dev in anaconda.storage.devices:
            if dev.format.type == "luks" and not dev.format.exists and \
               not dev.format.hasKey:
                dev.format.passphrase = anaconda.storage.encryptionPassphrase

    map(lambda d: anaconda.storage.services.update(d.services),
        anaconda.storage.devices)

    if anaconda.ksdata:
        return

    # Prevent users from installing on s390x with (a) no /boot volume, (b) the
    # root volume on LVM, and (c) the root volume not restricted to a single
    # PV
    # NOTE: There is not really a way for users to create a / volume
    # restricted to a single PV.  The backend support is there, but there are
    # no UI hook-ups to drive that functionality, but I do not personally
    # care.  --dcantrell
    if iutil.isS390() and \
       not anaconda.storage.mountpoints.has_key('/boot') and \
       anaconda.storage.mountpoints['/'].type == 'lvmlv' and \
       not anaconda.storage.mountpoints['/'].singlePV:
        rc = anaconda.intf.messageWindow(_("Missing /boot Volume"),
                                         _("This platform requires /boot on "
                                           "a dedicated partition or logical "
                                           "volume.  If you do not want a "
                                           "/boot volume, you must place / "
                                           "on a dedicated non-LVM "
                                           "partition."),
                                         type="custom", custom_icon="error",
                                         custom_buttons=[_("Go _back"),
                                                         _("_Exit installer")],
                                         default=0)
        if rc == 0:
            return DISPATCH_BACK
        sys.exit(1)

    rc = anaconda.intf.messageWindow(_("Confirm"),
                                _("The partitioning options you have selected "
                                  "will now be written to disk.  Any "
                                  "data on deleted or reformatted partitions "
                                  "will be lost."),
                                type = "custom", custom_icon="warning",
                                custom_buttons=[_("Go _Back"),
                                                _("_Write Changes to Disk")],
                                default = 0)

    # Make sure that all is down, even the disks that we setup after popluate.
    anaconda.storage.devicetree.teardownAll()

    if rc == 0:
        return DISPATCH_BACK

def writeEscrowPackets(anaconda):
    escrowDevices = filter(lambda d: d.format.type == "luks" and \
                                     d.format.escrow_cert,
                           anaconda.storage.devices)

    if not escrowDevices:
        return

    log.debug("escrow: writeEscrowPackets start")

    wait_win = anaconda.intf.waitWindow(_("Running..."),
                                        _("Storing encryption keys"))

    nss.nss.nss_init_nodb() # Does nothing if NSS is already initialized

    backupPassphrase = generateBackupPassphrase()
    try:
        for device in escrowDevices:
            log.debug("escrow: device %s: %s" %
                      (repr(device.path), repr(device.format.type)))
            device.format.escrow(anaconda.rootPath + "/root",
                                 backupPassphrase)

        wait_win.pop()
    except (IOError, RuntimeError) as e:
        wait_win.pop()
        anaconda.intf.messageWindow(_("Error"),
                                    _("Error storing an encryption key: "
                                      "%s\n") % str(e), type="custom",
                                    custom_icon="error",
                                    custom_buttons=[_("_Exit installer")])
        sys.exit(1)

    log.debug("escrow: writeEscrowPackets done")


def undoEncryption(storage):
    for device in storage.devicetree.getDevicesByType("luks/dm-crypt"):
        if device.exists:
            continue

        slave = device.slave
        format = device.format

        # set any devices that depended on the luks device to now depend on
        # the former slave device
        for child in storage.devicetree.getChildren(device):
            child.parents.remove(device)
            device.removeChild()
            child.parents.append(slave)

        storage.devicetree.registerAction(ActionDestroyFormat(device))
        storage.devicetree.registerAction(ActionDestroyDevice(device))
        storage.devicetree.registerAction(ActionDestroyFormat(slave))
        storage.devicetree.registerAction(ActionCreateFormat(slave, format))

class StorageDiscoveryConfig(object):
    def __init__(self):
        # storage configuration variables
        self.ignoreDiskInteractive = False
        self.ignoredDisks = []
        self.exclusiveDisks = []
        self.clearPartType = None
        self.clearPartDisks = []
        self.reinitializeDisks = False
        self.zeroMbr = None
        self.protectedDevSpecs = []
        self.diskImages = {}
        self.mpathFriendlyNames = True

    def writeKS(self, f):
        # clearpart
        if self.clearPartType is None or self.clearPartType == CLEARPART_TYPE_NONE:
            args = ["--none"]
        elif self.clearPartType == CLEARPART_TYPE_LINUX:
            args = ["--linux"]
        else:
            args = ["--all"]

        if self.clearPartDisks:
            args += ["--drives=%s" % ",".join(self.clearPartDisks)]
        if self.reinitializeDisks:
            args += ["--initlabel"]

        f.write("#clearpart %s\n" % " ".join(args))

        # ignoredisks
        if self.ignoreDiskInteractive:
            f.write("#ignoredisk --interactive\n")
        elif self.ignoredDisks:
            f.write("#ignoredisk --drives=%s\n" % ",".join(self.ignoredDisks))
        elif self.exclusiveDisks:
            f.write("#ignoredisk --only-use=%s\n" % ",".join(self.exclusiveDisks))


class Storage(object):
    def __init__(self, anaconda=None, intf=None, platform=None):
        """ Create a Storage instance.

            Keyword Arguments:

                anaconda    -   an Anaconda instance
                intf        -   an InstallInterface instance
                platform    -   a Platform instance

            All arguments are optional. An Anaconda instance will contain
            an InstallInterface and a Platform instance, so it makes sense
            to pass in either an Anaconda instance or as many of the other
            two as is desired. Explicitly passed intf or platform will take
            precedence over those in the Anaconda instance.

        """
        self.anaconda = anaconda
        self._intf = intf
        self._platform = platform

        self.config = StorageDiscoveryConfig()

        # storage configuration variables
        self.doAutoPart = False
        self.clearPartChoice = None
        self.encryptedAutoPart = False
        self.lvmAutoPart = True
        self.encryptionPassphrase = None
        self.escrowCertificates = {}
        self.autoPartEscrowCert = None
        self.autoPartAddBackupPassphrase = False
        self.encryptionRetrofit = False
        self.autoPartitionRequests = []
        self.eddDict = {}

        self.__luksDevs = {}

        self.iscsi = iscsi.iscsi()
        self.fcoe = fcoe.fcoe()
        self.zfcp = zfcp.ZFCP()
        self.dasd = dasd.DASD()

        self._nextID = 0
        self.defaultFSType = get_default_filesystem_type()
        self._dumpFile = "/tmp/storage.state"

        # these will both be empty until our reset method gets called
        self.devicetree = DeviceTree(intf=self.intf,
                                     conf=self.config,
                                     passphrase=self.encryptionPassphrase,
                                     luksDict=self.__luksDevs,
                                     iscsi=self.iscsi,
                                     dasd=self.dasd)
        self.fsset = FSSet(self.devicetree, getattr(anaconda, "rootPath", ""))
        self.services = set()

    def doIt(self):
        self.devicetree.processActions()
        self.doEncryptionPassphraseRetrofits()

        # now set the boot partition's flag
        if self.anaconda:
            if self.anaconda.bootloader.stage2_bootable:
                boot = self.bootDevice
            else:
                boot = self.bootLoaderDevice

            if boot.type == "mdarray":
                bootDevs = boot.parents
            else:
                bootDevs = [boot]

            for dev in bootDevs:
                if hasattr(dev, "bootable"):
                    # Dos labels can only have one partition marked as active
                    # and unmarking ie the windows partition is not a good idea
                    skip = False
                    if dev.disk.format.partedDisk.type == "msdos":
                        for p in dev.disk.format.partedDisk.partitions:
                            if p.type == parted.PARTITION_NORMAL and \
                               p.getFlag(parted.PARTITION_BOOT):
                                skip = True
                                break
                    if skip:
                         log.info("not setting boot flag on %s as there is"
                                  "another active partition" % dev.name)
                         continue
                    log.info("setting boot flag on %s" % dev.name)
                    dev.bootable = True

                    # Set the boot partition's name on disk labels that support it
                    if dev.partedPartition.disk.supportsFeature(parted.DISK_TYPE_PARTITION_NAME):
                        ped_partition = dev.partedPartition.getPedPartition()
                        ped_partition.set_name(dev.format.name)

                    dev.disk.setup()
                    dev.disk.format.commitToDisk()

        self.dumpState("final")

    @property
    def nextID(self):
        id = self._nextID
        self._nextID += 1
        return id

    def shutdown(self):
        try:
            self.devicetree.teardownAll()
        except Exception as e:
            log.error("failure tearing down device tree: %s" % e)

    def reset(self, cleanupOnly=False):
        """ Reset storage configuration to reflect actual system state.

            This should rescan from scratch but not clobber user-obtained
            information like passphrases, iscsi config, &c

        """
        # save passphrases for luks devices so we don't have to reprompt
        self.encryptionPassphrase = None
        for device in self.devices:
            if device.format.type == "luks" and device.format.exists:
                self.__luksDevs[device.format.uuid] = device.format._LUKS__passphrase

        prog = None
        if self.intf:
            prog = self.intf.progressWindow(_("Examining Devices"),
                                            _("Examining storage devices"),
                                            100, 0.03, pulse=True)
        if not flags.imageInstall:
            self.iscsi.startup(self.intf)
            self.fcoe.startup(self.intf)
            self.zfcp.startup(self.intf)
            self.dasd.startup(self.intf,
                              self.config.exclusiveDisks,
                              self.config.zeroMbr)
        clearPartType = self.config.clearPartType # save this before overriding it
        if getattr(self.anaconda, "upgrade", False):
            self.config.clearPartType = CLEARPART_TYPE_NONE

        self.devicetree = DeviceTree(intf=self.intf,
                                     conf=self.config,
                                     passphrase=self.encryptionPassphrase,
                                     luksDict=self.__luksDevs,
                                     iscsi=self.iscsi,
                                     dasd=self.dasd)
        self.devicetree.populate(progressWindow=prog,
                                 cleanupOnly=cleanupOnly)
        self.config.clearPartType = clearPartType # set it back
        self.fsset = FSSet(self.devicetree,
                           getattr(self.anaconda, "rootPath", ""))
        self.eddDict = get_edd_dict(self.partitioned)
        if hasattr(self.anaconda, "rootParts") and \
           hasattr(self.anaconda, "upgradeRoot"):
            self.anaconda.rootParts = None
            self.anaconda.upgradeRoot = None
        if self.anaconda:
            self.anaconda.bootloader.clear_drive_list()
        self.dumpState("initial")
        if prog:
            prog.pop()

    @property
    def devices(self):
        """ A list of all the devices in the device tree. """
        devices = self.devicetree.devices
        devices.sort(key=lambda d: d.name)
        return devices

    @property
    def disks(self):
        """ A list of the disks in the device tree.

            Ignored disks are not included, as are disks with no media present.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        disks = []
        for device in self.devicetree.devices:
            if device.isDisk:
                if not device.mediaPresent:
                    log.info("Skipping disk: %s: No media present" % device.name)
                    continue
                disks.append(device)
        disks.sort(key=lambda d: d.name, cmp=self.compareDisks)
        return disks

    @property
    def partitioned(self):
        """ A list of the partitioned devices in the device tree.

            Ignored devices are not included, nor disks with no media present.

            Devices of types for which partitioning is not supported are also
            not included.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        partitioned = []
        for device in self.devicetree.devices:
            if not device.partitioned:
                continue

            if not device.mediaPresent:
                log.info("Skipping device: %s: No media present" % device.name)
                continue

            partitioned.append(device)

        partitioned.sort(key=lambda d: d.name)
        return partitioned

    @property
    def partitions(self):
        """ A list of the partitions in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        partitions = self.devicetree.getDevicesByInstance(PartitionDevice)
        partitions.sort(key=lambda d: d.name)
        return partitions

    @property
    def vgs(self):
        """ A list of the LVM Volume Groups in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        vgs = self.devicetree.getDevicesByType("lvmvg")
        vgs.sort(key=lambda d: d.name)
        return vgs

    @property
    def lvs(self):
        """ A list of the LVM Logical Volumes in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        lvs = self.devicetree.getDevicesByType("lvmlv")
        lvs.sort(key=lambda d: d.name)
        return lvs

    @property
    def pvs(self):
        """ A list of the LVM Physical Volumes in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        devices = self.devicetree.devices
        pvs = [d for d in devices if d.format.type == "lvmpv"]
        pvs.sort(key=lambda d: d.name)
        return pvs

    def unusedPVs(self, vg=None):
        unused = []
        for pv in self.pvs:
            used = False
            for _vg in self.vgs:
                if _vg.dependsOn(pv) and _vg != vg:
                    used = True
                    break
                elif _vg == vg:
                    break
            if not used:
                unused.append(pv)
        return unused

    @property
    def mdarrays(self):
        """ A list of the MD arrays in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        arrays = self.devicetree.getDevicesByType("mdarray")
        arrays.sort(key=lambda d: d.name)
        return arrays

    @property
    def mdcontainers(self):
        """ A list of the MD containers in the device tree. """
        arrays = self.devicetree.getDevicesByType("mdcontainer")
        arrays.sort(key=lambda d: d.name)
        return arrays

    @property
    def mdmembers(self):
        """ A list of the MD member devices in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        devices = self.devicetree.devices
        members = [d for d in devices if d.format.type == "mdmember"]
        members.sort(key=lambda d: d.name)
        return members

    def unusedMDMembers(self, array=None):
        unused = []
        for member in self.mdmembers:
            used = False
            for _array in self.mdarrays + self.mdcontainers:
                if _array.dependsOn(member) and _array != array:
                    used = True
                    break
                elif _array == array:
                    break
            if not used:
                unused.append(member)
        return unused

    @property
    def unusedMDMinors(self):
        """ Return a list of unused minors for use in RAID. """
        raidMinors = range(0,32)
        for array in self.mdarrays + self.mdcontainers:
            if array.minor is not None and array.minor in raidMinors:
                raidMinors.remove(array.minor)
        return raidMinors

    @property
    def swaps(self):
        """ A list of the swap devices in the device tree.

            This is based on the current state of the device tree and
            does not necessarily reflect the actual on-disk state of the
            system's disks.
        """
        devices = self.devicetree.devices
        swaps = [d for d in devices if d.format.type == "swap"]
        swaps.sort(key=lambda d: d.name)
        return swaps

    @property
    def protectedDevices(self):
        devices = self.devicetree.devices
        protected = [d for d in devices if d.protected]
        protected.sort(key=lambda d: d.name)
        return protected

    @property
    def liveImage(self):
        """ The OS image used by live installs. """
        _image = None
        if flags.livecdInstall and hasattr(self.anaconda, "methodstr"):
            _image = self.devicetree.getDeviceByPath(self.anaconda.methodstr[9:])
        return _image

    @property
    def intf(self):
        _intf = self._intf
        if not _intf:
            _intf = getattr(self.anaconda, "intf", None)
        return _intf

    @property
    def platform(self):
        _platform = self._platform
        if not _platform:
            _platform = getattr(self.anaconda, "platform", None)
        return _platform

    def exceptionDisks(self):
        """ Return a list of removable devices to save exceptions to.

            FIXME: This raises the problem that the device tree can be
                   in a state that does not reflect that actual current
                   state of the system at any given point.

                   We need a way to provide direct scanning of disks,
                   partitions, and filesystems without relying on the
                   larger objects' correctness.

                   Also, we need to find devices that have just been made
                   available for the purpose of storing the exception
                   report.
        """
        # When a usb is connected from before the start of the installation,
        # it is not correctly detected.
        udev_trigger(subsystem="block", action="change")
        self.reset()

        dests = []

        for disk in self.disks:
            if not disk.removable and \
                    disk.format is not None  and \
                    disk.format.mountable:
                dests.append([disk.path, disk.name])

        for part in self.partitions:
            if not part.disk.removable:
                continue

            elif part.partedPartition.active and \
                    not part.partedPartition.getFlag(parted.PARTITION_RAID) and \
                    not part.partedPartition.getFlag(parted.PARTITION_LVM) and \
                    part.format is not None and part.format.mountable:
                dests.append([part.path, part.name])

        return dests

    def deviceImmutable(self, device, ignoreProtected=False):
        """ Return any reason the device cannot be modified/removed.

            Return False if the device can be removed.

            Devices that cannot be removed include:

                - protected partitions
                - devices that are part of an md array or lvm vg
                - extended partition containing logical partitions that
                  meet any of the above criteria

        """
        if not isinstance(device, Device):
            raise ValueError("arg1 (%s) must be a Device instance" % device)

        if not ignoreProtected and device.protected and \
           not getattr(device.format, "inconsistentVG", False):
            return _("This partition is holding the data for the hard "
                      "drive install.")
        elif isinstance(device, PartitionDevice) and device.isProtected:
            # LDL formatted DASDs always have one partition, you'd have to
            # reformat the DASD in CDL mode to get rid of it
            return _("You cannot delete a partition of a LDL formatted "
                     "DASD.")
        elif device.format.type == "mdmember":
            for array in self.mdarrays + self.mdcontainers:
                if array.dependsOn(device):
                    if array.minor is not None:
                        return _("This device is part of the RAID "
                                 "device %s.") % (array.path,)
                    else:
                        return _("This device is part of a RAID device.")
        elif device.format.type == "lvmpv":
            if device.format.inconsistentVG:
                return _("This device is part of an inconsistent LVM "
                         "Volume Group.")
            for vg in self.vgs:
                if vg.dependsOn(device):
                    if vg.name is not None:
                        return _("This device is part of the LVM "
                                 "volume group '%s'.") % (vg.name,)
                    else:
                        return _("This device is part of a LVM volume "
                                 "group.")
        elif device.format.type == "luks":
            try:
                luksdev = self.devicetree.getChildren(device)[0]
            except IndexError:
                pass
            else:
                return self.deviceImmutable(luksdev)
        elif isinstance(device, PartitionDevice) and device.isExtended:
            reasons = {}
            for dep in self.deviceDeps(device):
                reason = self.deviceImmutable(dep)
                if reason:
                    reasons[dep.path] = reason
            if reasons:
                msg =  _("This device is an extended partition which "
                         "contains logical partitions that cannot be "
                         "deleted:\n\n")
                for dev in reasons:
                    msg += "%s: %s" % (dev, reasons[dev])
                return msg

        return False

    def deviceDeps(self, device):
        return self.devicetree.getDependentDevices(device)

    def newPartition(self, *args, **kwargs):
        """ Return a new PartitionDevice instance for configuring. """
        if kwargs.has_key("fmt_type"):
            kwargs["format"] = getFormat(kwargs.pop("fmt_type"),
                                         mountpoint=kwargs.pop("mountpoint",
                                                               None),
                                         **kwargs.pop("fmt_args", {}))

        if kwargs.has_key("disks"):
            parents = kwargs.pop("disks")
            if isinstance(parents, Device):
                kwargs["parents"] = [parents]
            else:
                kwargs["parents"] = parents

        if kwargs.has_key("name"):
            name = kwargs.pop("name")
        else:
            name = "req%d" % self.nextID

        return PartitionDevice(name, *args, **kwargs)

    def newMDArray(self, *args, **kwargs):
        """ Return a new MDRaidArrayDevice instance for configuring. """
        if kwargs.has_key("fmt_type"):
            kwargs["format"] = getFormat(kwargs.pop("fmt_type"),
                                         mountpoint=kwargs.pop("mountpoint",
                                                               None))

        if kwargs.has_key("minor"):
            kwargs["minor"] = int(kwargs["minor"])
        else:
            kwargs["minor"] = self.unusedMDMinors[0]

        if kwargs.has_key("name"):
            name = kwargs.pop("name")
        else:
            name = "md%d" % kwargs["minor"]

        return MDRaidArrayDevice(name, *args, **kwargs)

    def newVG(self, *args, **kwargs):
        """ Return a new LVMVolumeGroupDevice instance. """
        pvs = kwargs.pop("pvs", [])
        for pv in pvs:
            if pv not in self.devices:
                raise ValueError("pv is not in the device tree")

        if kwargs.has_key("name"):
            name = kwargs.pop("name")
        else:
            hostname = ""
            if hasattr(self.anaconda, "network"):
                hostname = self.anaconda.network.hostname
            name = self.createSuggestedVGName(hostname=hostname)

        if name in [d.name for d in self.devices]:
            raise ValueError("name already in use")

        return LVMVolumeGroupDevice(name, pvs, *args, **kwargs)

    def newLV(self, *args, **kwargs):
        """ Return a new LVMLogicalVolumeDevice instance. """
        if kwargs.has_key("vg"):
            vg = kwargs.pop("vg")

        mountpoint = kwargs.pop("mountpoint", None)
        if kwargs.has_key("fmt_type"):
            kwargs["format"] = getFormat(kwargs.pop("fmt_type"),
                                         mountpoint=mountpoint)

        if kwargs.has_key("name"):
            name = kwargs.pop("name")
        else:
            if kwargs.get("format") and kwargs["format"].type == "swap":
                swap = True
            else:
                swap = False
            name = self.createSuggestedLVName(vg,
                                              swap=swap,
                                              mountpoint=mountpoint)

        if name in [d.name for d in self.devices]:
            raise ValueError("name already in use")

        return LVMLogicalVolumeDevice(name, vg, *args, **kwargs)

    def createDevice(self, device):
        """ Schedule creation of a device.

            TODO: We could do some things here like assign the next
                  available raid minor if one isn't already set.
        """
        self.devicetree.registerAction(ActionCreateDevice(device))
        if device.format.type:
            self.devicetree.registerAction(ActionCreateFormat(device))

    def destroyDevice(self, device):
        """ Schedule destruction of a device. """
        if device.format.exists and device.format.type:
            # schedule destruction of any formatting while we're at it
            self.devicetree.registerAction(ActionDestroyFormat(device))

        action = ActionDestroyDevice(device)
        self.devicetree.registerAction(action)

    def formatDevice(self, device, format):
        """ Schedule formatting of a device. """
        self.devicetree.registerAction(ActionDestroyFormat(device))
        self.devicetree.registerAction(ActionCreateFormat(device, format))

    def formatByDefault(self, device):
        """Return whether the device should be reformatted by default."""
        formatlist = ['/boot', '/var', '/tmp', '/usr']
        exceptlist = ['/home', '/usr/local', '/opt', '/var/www']

        if not device.format.linuxNative:
            return False

        if device.format.mountable:
            if not device.format.mountpoint:
                return False

            if device.format.mountpoint == "/" or \
               device.format.mountpoint in formatlist:
                return True

            for p in formatlist:
                if device.format.mountpoint.startswith(p):
                    for q in exceptlist:
                        if device.format.mountpoint.startswith(q):
                            return False
                    return True
        elif device.format.type == "swap":
            return True

        # be safe for anything else and default to off
        return False

    def mustFormat(self, device):
        """ Return a string explaining why the device must be reformatted.

            Return None if the device need not be reformatted.
        """
        if device.format.mountable and device.format.mountpoint == "/":
            return _("You must create a new filesystem on the root device.")

        return None

    def extendedPartitionsSupported(self):
        """ Return whether any disks support extended partitions."""
        for disk in self.partitioned:
            if disk.format.partedDisk.supportsFeature(parted.DISK_TYPE_EXTENDED):
                return True
        return False

    def createSuggestedVGName(self, hostname=None):
        """ Return a reasonable, unused VG name. """
        # try to create a volume group name incorporating the hostname
        if hostname not in (None, "", 'localhost', 'localhost.localdomain'):
            template = "vg_%s" % (hostname.split('.')[0].lower(),)
            vgtemplate = safeLvmName(template)
        elif flags.imageInstall:
            vgtemplate = "vg_image"
        else:
            vgtemplate = "VolGroup"

        vgnames = [vg.name for vg in self.vgs]
        if vgtemplate not in vgnames and \
                vgtemplate not in lvm.lvm_vg_blacklist:
            return vgtemplate
        else:
            i = 0
            while 1:
                tmpname = "%s%02d" % (vgtemplate, i,)
                if not tmpname in vgnames and \
                        tmpname not in lvm.lvm_vg_blacklist:
                    break

                i += 1
                if i > 99:
                    tmpname = ""

            return tmpname

    def createSuggestedLVName(self, vg, swap=None, mountpoint=None):
        """ Return a suitable, unused name for a new logical volume. """
        # FIXME: this is not at all guaranteed to work
        if mountpoint:
            # try to incorporate the mountpoint into the name
            if mountpoint == '/':
                lvtemplate = 'lv_root'
            else:
                if mountpoint.startswith("/"):
                    template = "lv_%s" % mountpoint[1:]
                else:
                    template = "lv_%s" % (mountpoint,)

                lvtemplate = safeLvmName(template)
        else:
            if swap:
                if len([s for s in self.swaps if s in vg.lvs]):
                    idx = len([s for s in self.swaps if s in vg.lvs])
                    while True:
                        lvtemplate = "lv_swap%02d" % idx
                        if lvtemplate in [lv.lvname for lv in vg.lvs]:
                            idx += 1
                        else:
                            break
                else:
                    lvtemplate = "lv_swap"
            else:
                idx = len(vg.lvs)
                while True:
                    lvtemplate = "LogVol%02d" % idx
                    if lvtemplate in [l.lvname for l in vg.lvs]:
                        idx += 1
                    else:
                        break

        return lvtemplate

    def doEncryptionPassphraseRetrofits(self):
        """ Add the global passphrase to all preexisting LUKS devices.

            This establishes a common passphrase for all encrypted devices
            in the system so that users only have to enter one passphrase
            during system boot.
        """
        if not self.encryptionRetrofit:
            return

        for device in self.devices:
            if device.format.type == "luks" and \
               device.format._LUKS__passphrase != self.encryptionPassphrase:
                log.info("adding new passphrase to preexisting encrypted "
                         "device %s" % device.path)
                try:
                    device.format.addPassphrase(self.encryptionPassphrase)
                except CryptoError:
                    log.error("failed to add new passphrase to existing "
                              "device %s" % device.path)

    def setupDiskImages(self):
        self.devicetree.setDiskImages(self.config.diskImages)
        self.devicetree.setupDiskImages()

    def sanityCheck(self):
        """ Run a series of tests to verify the storage configuration.

            This function is called at the end of partitioning so that
            we can make sure you don't have anything silly (like no /,
            a really small /, etc).  Returns (errors, warnings) where
            each is a list of strings.
        """
        checkSizes = [('/usr', 250), ('/tmp', 50), ('/var', 384),
                      ('/home', 100), ('/boot', 75)]
        warnings = []
        errors = []

        mustbeonlinuxfs = ['/', '/var', '/tmp', '/usr', '/home', '/usr/share', '/usr/lib']
        mustbeonroot = ['/bin','/dev','/sbin','/etc','/lib','/root', '/mnt', 'lost+found', '/proc']

        filesystems = self.mountpoints
        root = self.fsset.rootDevice
        swaps = self.fsset.swapDevices
        try:
            boot = self.bootDevice
        except (DeviceError, AttributeError):
            # AttributeError means we have no anaconda or platform. it's ok.
            boot = None

        if not root:
            errors.append(_("You have not defined a root partition (/), "
                            "which is required for installation of %s "
                            "to continue.") % (productName,))

        if root and root.size < 250:
            warnings.append(_("Your root partition is less than 250 "
                              "megabytes which is usually too small to "
                              "install %s.") % (productName,))

        if (root and
            hasattr(self.anaconda, "backend") and
            root.size < self.anaconda.backend.getMinimumSizeMB("/")):
            if flags.livecdInstall:
                live = " Live"
            else:
                live = ""
            errors.append(_("Your / partition is less than %(min)s "
                            "MB which is lower than recommended "
                            "for a normal %(productName)s%(live)s install.")
                          % {'min': self.anaconda.backend.getMinimumSizeMB("/"),
                             'productName': productName,
                             'live': live})

        # livecds have to have the rootfs type match up
        if (root and
            self.liveImage and
            root.format.type != self.liveImage.format.type):
            errors.append(_("Your / partition does not match the "
                            "the live image you are installing from.  "
                            "It must be formatted as %s.")
                          % (self.liveImage.format.type,))

        for (mount, size) in checkSizes:
            if mount in filesystems and filesystems[mount].size < size:
                warnings.append(_("Your %(mount)s partition is less than "
                                  "%(size)s megabytes which is lower than "
                                  "recommended for a normal %(productName)s "
                                  "install.")
                                % {'mount': mount, 'size': size,
                                   'productName': productName})

        for (mount, device) in filesystems.items():
            problem = filesystems[mount].checkSize()
            if problem < 0:
                errors.append(_("Your %(mount)s partition is too small for %(format)s formatting "
                                "(allowable size is %(minSize)d MB to %(maxSize)d MB)")
                              % {"mount": mount, "format": device.format.name,
                                 "minSize": device.minSize, "maxSize": device.maxSize})
            elif problem > 0:
                errors.append(_("Your %(mount)s partition is too large for %(format)s formatting "
                                "(allowable size is %(minSize)d MB to %(maxSize)d MB)")
                              % {"mount":mount, "format": device.format.name,
                                 "minSize": device.minSize, "maxSize": device.maxSize})

        usb_disks = []
        firewire_disks = []
        for disk in self.disks:
            if isys.driveUsesModule(disk.name, ["usb-storage", "ub"]):
                usb_disks.append(disk)
            elif isys.driveUsesModule(disk.name, ["sbp2", "firewire-sbp2"]):
                firewire_disks.append(disk)

        uses_usb = False
        uses_firewire = False
        for device in filesystems.values():
            for disk in usb_disks:
                if device.dependsOn(disk):
                    uses_usb = True
                    break

            for disk in firewire_disks:
                if device.dependsOn(disk):
                    uses_firewire = True
                    break

        if uses_usb:
            warnings.append(_("Installing on a USB device.  This may "
                              "or may not produce a working system."))
        if uses_firewire:
            warnings.append(_("Installing on a FireWire device.  This may "
                              "or may not produce a working system."))

        if self.anaconda and self.anaconda.dispatch.step_enabled('instbootloader'):
            stage1 = self.anaconda.bootloader.stage1_device
            if not stage1:
                errors.append(_("you have not created a bootloader stage1 "
                                "target device"))
            else:
                self.anaconda.bootloader.is_valid_stage1_device(stage1)
                errors.extend(self.anaconda.bootloader.errors)
                warnings.extend(self.anaconda.bootloader.warnings)

            stage2 = self.anaconda.bootloader.stage2_device
            if not stage2:
                errors.append(_("You have not created a bootable partition."))
            else:
                self.anaconda.bootloader.is_valid_stage2_device(stage2)
                errors.extend(self.anaconda.bootloader.errors)
                warnings.extend(self.anaconda.bootloader.warnings)

        if not swaps:
            from pyanaconda.storage.size import Size

            installed = Size(spec="%s kb" % iutil.memInstalled())
            required = Size(spec="%s kb" % isys.EARLY_SWAP_RAM)

            if installed < required:
                errors.append(_("You have not specified a swap partition.  "
                                "%(requiredMem)s MB of memory is required to continue installation "
                                "without a swap partition, but you only have %(installedMem)s MB.")
                              % {"requiredMem": int(required.convertTo(spec="MB")),
                                 "installedMem": int(installed.convertTo(spec="MB"))})
            else:
                warnings.append(_("You have not specified a swap partition.  "
                                  "Although not strictly required in all cases, "
                                  "it will significantly improve performance "
                                  "for most installations."))
        no_uuid = [s for s in swaps if s.format.exists and not s.format.uuid]
        if no_uuid:
            warnings.append(_("At least one of your swap devices does not have "
                              "a UUID, which is common in swap space created "
                              "using older versions of mkswap. These devices "
                              "will be referred to by device path in "
                              "/etc/fstab, which is not ideal since device "
                              "paths can change under a variety of "
                              "circumstances. "))

        for (mountpoint, dev) in filesystems.items():
            if mountpoint in mustbeonroot:
                errors.append(_("This mount point is invalid.  The %s directory must "
                                "be on the / file system.") % mountpoint)

            if mountpoint in mustbeonlinuxfs and (not dev.format.mountable or not dev.format.linuxNative):
                errors.append(_("The mount point %s must be on a linux file system.") % mountpoint)

        return (errors, warnings)

    def isProtected(self, device):
        """ Return True is the device is protected. """
        return device.protected

    def checkNoDisks(self):
        """Check that there are valid disk devices."""
        if not self.disks and self.intf:
            self.intf.messageWindow(_("No Drives Found"),
                               _("An error has occurred - no valid devices were "
                                 "found on which to create new file systems. "
                                 "Please check your hardware for the cause "
                                 "of this problem."))
            return True
        return False

    def dumpState(self, suffix):
        """ Dump the current device list to the storage shelf. """
        key = "devices.%d.%s" % (time.time(), suffix)
        with contextlib.closing(shelve.open(self._dumpFile)) as shelf:
            shelf[key] = [d.dict for d in self.devices]

    def write(self, instPath):
        self.fsset.write(instPath)
        self.makeMtab(root=instPath)
        self.iscsi.write(instPath, self)
        self.fcoe.write(instPath)
        self.zfcp.write(instPath)
        self.dasd.write(instPath)

    def writeKS(self, f):
        def useExisting(lst):
            foundCreateDevice = False
            foundCreateFormat = False

            for l in lst:
                if isinstance(l, ActionCreateDevice):
                    foundCreateDevice = True
                elif isinstance(l, ActionCreateFormat):
                    foundCreateFormat = True

            return (foundCreateFormat and not foundCreateDevice)

        log.warning("Storage.writeKS not completely implemented")
        f.write("# The following is the partition information you requested\n")
        f.write("# Note that any partitions you deleted are not expressed\n")
        f.write("# here so unless you clear all partitions first, this is\n")
        f.write("# not guaranteed to work\n")

        self.config.writeKS(f)

        # the various partitioning commands
        dict = {}
        actions = filter(lambda x: x.device.format.type != "luks",
                         self.devicetree.findActions(type="create"))

        for action in actions:
            if dict.has_key(action.device.path):
                dict[action.device.path].append(action)
            else:
                dict[action.device.path] = [action]

        for device in [d for d in self.devices if d.format.type != "luks"]:
            # If there's no action for the given device, it must be one
            # we are reusing.
            if not dict.has_key(device.path):
                noformat = True
                preexisting = True
            else:
                noformat = False
                preexisting = useExisting(dict[device.path])

            device.writeKS(f, preexisting=preexisting, noformat=noformat)
            f.write("\n")

        self.iscsi.writeKS(f)
        self.fcoe.writeKS(f)
        self.zfcp.writeKS(f)
        f.write("\n")

    def turnOnSwap(self, upgrading=None):
        self.fsset.turnOnSwap(intf=self.intf,
                              rootPath=getattr(self.anaconda, "rootPath", ""),
                              upgrading=upgrading)

    def mountFilesystems(self, raiseErrors=None, readOnly=None, skipRoot=False):
        self.fsset.mountFilesystems(intf=self.intf,
                                    rootPath=getattr(self.anaconda,
                                                     "rootPath", ""),
                                    raiseErrors=raiseErrors,
                                    readOnly=readOnly, skipRoot=skipRoot)

    def umountFilesystems(self, ignoreErrors=True, swapoff=True):
        self.fsset.umountFilesystems(ignoreErrors=ignoreErrors, swapoff=swapoff)

    def parseFSTab(self):
        self.fsset.parseFSTab()

    def mkDevRoot(self):
        self.fsset.mkDevRoot()

    def createSwapFile(self, device, size):
        self.fsset.createSwapFile(device, size)

    @property
    def bootDevice(self):
        dev = None
        if self.anaconda:
            dev = self.anaconda.bootloader.stage2_device
        return dev

    @property
    def bootLoaderDevice(self):
        dev = None
        if self.anaconda:
            dev = self.anaconda.bootloader.stage1_device
        return dev

    @property
    def bootFSTypes(self):
        """A list of all valid filesystem types for the boot partition."""
        fstypes = []
        if self.anaconda:
            fstypes = self.anaconda.bootloader.stage2_format_types
        return fstypes

    @property
    def defaultBootFSType(self):
        """The default filesystem type for the boot partition."""
        fstype = None
        if self.anaconda:
            fstype = self.bootFSTypes[0]
        return fstype

    @property
    def mountpoints(self):
        return self.fsset.mountpoints

    @property
    def migratableDevices(self):
        return self.fsset.migratableDevices

    @property
    def rootDevice(self):
        return self.fsset.rootDevice

    def makeMtab(self, root=None):
        path = "/etc/mtab"
        target = "/proc/self/mounts"
        if root and root != "/" and os.path.isdir(root):
            path = os.path.normpath("%s/%s" % (root, path))

        if os.path.islink(path):
            # return early if the mtab symlink is already how we like it
            current_target = os.path.normpath(os.path.dirname(path) +
                                              "/" + os.readlink(path))
            if current_target == target:
                return

        if os.path.exists(path):
            os.unlink(path)

        os.symlink(target, path)

    def compareDisks(self, first, second):
        if self.eddDict.has_key(first) and self.eddDict.has_key(second):
            one = self.eddDict[first]
            two = self.eddDict[second]
            if (one < two):
                return -1
            elif (one > two):
                return 1

        # if one is in the BIOS and the other not prefer the one in the BIOS
        if self.eddDict.has_key(first):
            return -1
        if self.eddDict.has_key(second):
            return 1

        if first.startswith("hd"):
            type1 = 0
        elif first.startswith("sd"):
            type1 = 1
        elif (first.startswith("vd") or first.startswith("xvd")):
            type1 = -1
        else:
            type1 = 2

        if second.startswith("hd"):
            type2 = 0
        elif second.startswith("sd"):
            type2 = 1
        elif (second.startswith("vd") or second.startswith("xvd")):
            type2 = -1
        else:
            type2 = 2

        if (type1 < type2):
            return -1
        elif (type1 > type2):
            return 1
        else:
            len1 = len(first)
            len2 = len(second)

            if (len1 < len2):
                return -1
            elif (len1 > len2):
                return 1
            else:
                if (first < second):
                    return -1
                elif (first > second):
                    return 1

        return 0

def getReleaseString(mountpoint):
    relArch = None
    relName = None
    relVer = None

    import rpm
    iutil.resetRpmDb(mountpoint)
    ts = rpm.TransactionSet(mountpoint)

    # We get the arch from the initscripts package, but the version and name
    # must come from reading the release file.
    try:
        # pylint: disable-msg=E1101
        mi = ts.dbMatch('provides', 'initscripts')
    except Exception:
        # This could happen in a variety of cases, but the biggest one is we're
        # examining an installed system that doesn't use RPM.  Raise an
        # exception for the caller to handle.
        raise ValueError

    for h in mi:
        relArch = h['arch']
        break

    filename = "%s/etc/redhat-release" % mountpoint
    if os.access(filename, os.R_OK):
        with open(filename) as f:
            try:
                relstr = f.readline().strip()
            except (IOError, AttributeError):
                relstr = ""

        # get the release name and version
        # assumes that form is something
        # like "Red Hat Linux release 6.2 (Zoot)"
        (product, sep, version) = relstr.partition(" release ")
        if sep:
            relName = product
            relVer = version.split()[0]

    return (relArch, relName, relVer)

def findExistingRootDevices(anaconda, upgradeany=False):
    """ Return a tuple of:
        list of all root filesystems in the device tree.
        list of previous installs that cannot be upgraded.
    """
    rootDevs = []
    notUpgradable = []

    if not os.path.exists(anaconda.rootPath):
        iutil.mkdirChain(anaconda.rootPath)

    roots = []
    for device in anaconda.storage.devicetree.leaves:
        if not device.format.linuxNative or not device.format.mountable:
            continue

        if device.protected:
            # can't upgrade the part holding hd: media so why look at it?
            continue

        try:
            device.setup()
        except Exception as e:
            log.warning("setup of %s failed: %s" % (device.name, e))
            continue

        try:
            device.format.mount(options="ro", mountpoint=anaconda.rootPath)
        except Exception as e:
            log.warning("mount of %s as %s failed: %s" % (device.name,
                                                          device.format.type,
                                                          e))
            device.teardown()
            continue

        if os.access(anaconda.rootPath + "/etc/fstab", os.R_OK):
            try:
                (arch, product, version) = getReleaseString(anaconda.rootPath)
            except ValueError:
                # This likely isn't our product, so don't even count it as
                # notUpgradable.
                continue
            if arch is None:
                # we failed to determine the arch (for instance when there is a
                # corrupted rpm database on the target system)
                continue

            if upgradeany or \
               anaconda.instClass.productUpgradable(arch, product, version):
                rootDevs.append((device, "%s %s" % (product, version)))
            else:
                notUpgradable.append((product, version, device.name))
                log.info("product %s version %s found on %s is not upgradable"
                         % notUpgradable[-1])

        # this handles unmounting the filesystem
        device.teardown(recursive=True)

    return (rootDevs, notUpgradable)

def mountExistingSystem(anaconda, rootEnt,
                        allowDirty=None, warnDirty=None,
                        readOnly=None):
    """ Mount filesystems specified in rootDevice's /etc/fstab file. """
    rootDevice = rootEnt[0]
    rootPath = anaconda.rootPath
    fsset = anaconda.storage.fsset
    if readOnly:
        readOnly = "ro"
    else:
        readOnly = ""

    if rootDevice.protected and os.path.ismount("/mnt/install/isodir"):
        isys.mount("/mnt/install/isodir",
                   rootPath,
                   fstype=rootDevice.format.type,
                   bindMount=True)
    else:
        rootDevice.setup()
        rootDevice.format.mount(chroot=rootPath,
                                mountpoint="/",
                                options=readOnly)

    fsset.parseFSTab()

    # check for dirty filesystems
    dirtyDevs = []
    for device in fsset.devices:
        if not hasattr(device.format, "isDirty"):
            continue

        try:
            device.setup()
        except DeviceError as e:
            # we'll catch this in the main loop
            continue

        if device.format.isDirty:
            log.info("%s contains a dirty %s filesystem" % (device.path,
                                                            device.format.type))
            dirtyDevs.append(device.path)

    messageWindow = anaconda.intf.messageWindow
    if not allowDirty and dirtyDevs:
        messageWindow(_("Dirty File Systems"),
                      _("The following file systems for your Linux system "
                        "were not unmounted cleanly.  Please boot your "
                        "Linux installation, let the file systems be "
                        "checked and shut down cleanly to upgrade.\n"
                        "%s") % "\n".join(dirtyDevs))
        anaconda.storage.devicetree.teardownAll()
        sys.exit(0)
    elif warnDirty and dirtyDevs:
        rc = messageWindow(_("Dirty File Systems"),
                           _("The following file systems for your Linux "
                             "system were not unmounted cleanly.  Would "
                             "you like to mount them anyway?\n"
                             "%s") % "\n".join(dirtyDevs),
                             type = "yesno")
        if rc == 0:
            return -1

    fsset.mountFilesystems(intf=anaconda.intf, rootPath=anaconda.rootPath,
                           readOnly=readOnly, skipRoot=True)


class BlkidTab(object):
    """ Dictionary-like interface to blkid.tab with device path keys """
    def __init__(self, chroot=""):
        self.chroot = chroot
        self.devices = {}

    def parse(self):
        path = "%s/etc/blkid/blkid.tab" % self.chroot
        log.debug("parsing %s" % path)
        with open(path) as f:
            for line in f.readlines():
                # this is pretty ugly, but an XML parser is more work than
                # is justifiable for this purpose
                if not line.startswith("<device "):
                    continue

                line = line[len("<device "):-len("</device>\n")]
                (data, sep, device) = line.partition(">")
                if not device:
                    continue

                self.devices[device] = {}
                for pair in data.split():
                    try:
                        (key, value) = pair.split("=")
                    except ValueError:
                        continue

                    self.devices[device][key] = value[1:-1] # strip off quotes

    def __getitem__(self, key):
        return self.devices[key]

    def get(self, key, default=None):
        return self.devices.get(key, default)


class CryptTab(object):
    """ Dictionary-like interface to crypttab entries with map name keys """
    def __init__(self, devicetree, blkidTab=None, chroot=""):
        self.devicetree = devicetree
        self.blkidTab = blkidTab
        self.chroot = chroot
        self.mappings = {}

    def parse(self, chroot=""):
        """ Parse /etc/crypttab from an existing installation. """
        if not chroot or not os.path.isdir(chroot):
            chroot = ""

        path = "%s/etc/crypttab" % chroot
        log.debug("parsing %s" % path)
        with open(path) as f:
            if not self.blkidTab:
                try:
                    self.blkidTab = BlkidTab(chroot=chroot)
                    self.blkidTab.parse()
                except Exception:
                    self.blkidTab = None

            for line in f.readlines():
                (line, pound, comment) = line.partition("#")
                fields = line.split()
                if not 2 <= len(fields) <= 4:
                    continue
                elif len(fields) == 2:
                    fields.extend(['none', ''])
                elif len(fields) == 3:
                    fields.append('')

                (name, devspec, keyfile, options) = fields

                # resolve devspec to a device in the tree
                device = self.devicetree.resolveDevice(devspec,
                                                       blkidTab=self.blkidTab)
                if device:
                    self.mappings[name] = {"device": device,
                                           "keyfile": keyfile,
                                           "options": options}

    def populate(self):
        """ Populate the instance based on the device tree's contents. """
        for device in self.devicetree.devices:
            # XXX should we put them all in there or just the ones that
            #     are part of a device containing swap or a filesystem?
            #
            #       Put them all in here -- we can filter from FSSet
            if device.format.type != "luks":
                continue

            key_file = device.format.keyFile
            if not key_file:
                key_file = "none"

            options = device.format.options
            if not options:
                options = ""

            self.mappings[device.format.mapName] = {"device": device,
                                                    "keyfile": key_file,
                                                    "options": options}

    def crypttab(self):
        """ Write out /etc/crypttab """
        crypttab = ""
        for name in self.mappings:
            entry = self[name]
            crypttab += "%s UUID=%s %s %s\n" % (name,
                                                entry['device'].format.uuid,
                                                entry['keyfile'],
                                                entry['options'])
        return crypttab                       

    def __getitem__(self, key):
        return self.mappings[key]

    def get(self, key, default=None):
        return self.mappings.get(key, default)

def get_containing_device(path, devicetree):
    """ Return the device that a path resides on. """
    if not os.path.exists(path):
        return None

    st = os.stat(path)
    major = os.major(st.st_dev)
    minor = os.minor(st.st_dev)
    link = "/sys/dev/block/%s:%s" % (major, minor)
    if not os.path.exists(link):
        return None

    try:
        device_name = os.path.basename(os.readlink(link))
    except Exception:
        return None

    if device_name.startswith("dm-"):
        # have I told you lately that I love you, device-mapper?
        device_name = name_from_dm_node(device_name)

    return devicetree.getDeviceByName(device_name)


class FSSet(object):
    """ A class to represent a set of filesystems. """
    def __init__(self, devicetree, rootpath):
        self.devicetree = devicetree
        self.rootpath = rootpath
        self.cryptTab = None
        self.blkidTab = None
        self.origFStab = None
        self.active = False
        self._dev = None
        self._devpts = None
        self._sysfs = None
        self._proc = None
        self._devshm = None
        self._usb = None
        self._selinux = None
        self.preserveLines = []     # lines we just ignore and preserve

    @property
    def sysfs(self):
        if not self._sysfs:
            self._sysfs = NoDevice(format=getFormat("sysfs",
                                                    device="sys",
                                                    mountpoint="/sys"))
        return self._sysfs

    @property
    def dev(self):
        if not self._dev:
            self._dev = DirectoryDevice("/dev", format=getFormat("bind",
                                                                 device="/dev",
                                                                 mountpoint="/dev",
                                                                 exists=True),
                                        exists=True)

        return self._dev

    @property
    def devpts(self):
        if not self._devpts:
            self._devpts = NoDevice(format=getFormat("devpts",
                                                     device="devpts",
                                                     mountpoint="/dev/pts"))
        return self._devpts

    @property
    def proc(self):
        if not self._proc:
            self._proc = NoDevice(format=getFormat("proc",
                                                   device="proc",
                                                   mountpoint="/proc"))
        return self._proc

    @property
    def devshm(self):
        if not self._devshm:
            self._devshm = NoDevice(format=getFormat("tmpfs",
                                                     device="tmpfs",
                                                     mountpoint="/dev/shm"))
        return self._devshm

    @property
    def usb(self):
        if not self._usb:
            self._usb = NoDevice(format=getFormat("usbfs",
                                                  device="usbfs",
                                                  mountpoint="/proc/bus/usb"))
        return self._usb

    @property
    def selinux(self):
        if not self._selinux:
            self._selinux = NoDevice(format=getFormat("selinuxfs",
                                                      device="selinuxfs",
                                                      mountpoint="/sys/fs/selinux"))
        return self._selinux

    @property
    def devices(self):
        return sorted(self.devicetree.devices, key=lambda d: d.path)

    @property
    def mountpoints(self):
        filesystems = {}
        for device in self.devices:
            if device.format.mountable and device.format.mountpoint:
                filesystems[device.format.mountpoint] = device
        return filesystems

    def _parseOneLine(self, (devspec, mountpoint, fstype, options, dump, passno)):
        # no sense in doing any legwork for a noauto entry
        if "noauto" in options.split(","):
            log.info("ignoring noauto entry")
            raise UnrecognizedFSTabEntryError()

        # find device in the tree
        device = self.devicetree.resolveDevice(devspec,
                                               cryptTab=self.cryptTab,
                                               blkidTab=self.blkidTab)

        if device:
            # fall through to the bottom of this block
            pass
        elif devspec.startswith("/dev/loop"):
            # FIXME: create devices.LoopDevice
            log.warning("completely ignoring your loop mount")
        elif ":" in devspec and fstype.startswith("nfs"):
            # NFS -- preserve but otherwise ignore
            device = NFSDevice(devspec,
                               format=getFormat(fstype,
                                                device=devspec))
        elif devspec.startswith("/") and fstype == "swap":
            # swap file
            device = FileDevice(devspec,
                                parents=get_containing_device(devspec, self.devicetree),
                                format=getFormat(fstype,
                                                 device=devspec,
                                                 exists=True),
                                exists=True)
        elif fstype == "bind" or "bind" in options:
            # bind mount... set fstype so later comparison won't
            # turn up false positives
            fstype = "bind"

            # This is probably not going to do anything useful, so we'll
            # make sure to try again from FSSet.mountFilesystems. The bind
            # mount targets should be accessible by the time we try to do
            # the bind mount from there.
            parents = get_containing_device(devspec, self.devicetree)
            device = DirectoryDevice(devspec, parents=parents, exists=True)
            device.format = getFormat("bind",
                                      device=device.path,
                                      exists=True)
        elif mountpoint in ("/proc", "/sys", "/dev/shm", "/dev/pts",
                            "/sys/fs/selinux", "/proc/bus/usb"):
            # drop these now -- we'll recreate later
            return None
        else:
            # nodev filesystem -- preserve or drop completely?
            format = getFormat(fstype)
            if devspec == "none" or \
               isinstance(format, get_device_format_class("nodev")):
                device = NoDevice(format=format)
            else:
                device = StorageDevice(devspec, format=format)

        if device is None:
            log.error("failed to resolve %s (%s) from fstab" % (devspec,
                                                                fstype))
            raise UnrecognizedFSTabEntryError()

        fmt = getFormat(fstype, device=device.path)
        if fstype != "auto" and None in (device.format.type, fmt.type):
            log.info("Unrecognized filesystem type for %s (%s)"
                     % (device.name, fstype))
            raise UnrecognizedFSTabEntryError()

        # make sure, if we're using a device from the tree, that
        # the device's format we found matches what's in the fstab
        ftype = getattr(fmt, "mountType", fmt.type)
        dtype = getattr(device.format, "mountType", device.format.type)
        if fstype != "auto" and ftype != dtype:
            raise StorageError("scanned format (%s) differs from fstab "
                        "format (%s)" % (dtype, ftype))
        del ftype
        del dtype

        if device.format.mountable:
            device.format.mountpoint = mountpoint
            device.format.mountopts = options

        # is this useful?
        try:
            device.format.options = options
        except AttributeError:
            pass

        return device

    def parseFSTab(self, chroot=None):
        """ parse /etc/fstab

            preconditions:
                all storage devices have been scanned, including filesystems
            postconditions:

            FIXME: control which exceptions we raise

            XXX do we care about bind mounts?
                how about nodev mounts?
                loop mounts?
        """
        if not chroot or not os.path.isdir(chroot):
            chroot = self.rootpath

        path = "%s/etc/fstab" % chroot
        if not os.access(path, os.R_OK):
            # XXX should we raise an exception instead?
            log.info("cannot open %s for read" % path)
            return

        blkidTab = BlkidTab(chroot=chroot)
        try:
            blkidTab.parse()
            log.debug("blkid.tab devs: %s" % blkidTab.devices.keys())
        except Exception as e:
            log.info("error parsing blkid.tab: %s" % e)
            blkidTab = None

        cryptTab = CryptTab(self.devicetree, blkidTab=blkidTab, chroot=chroot)
        try:
            cryptTab.parse(chroot=chroot)
            log.debug("crypttab maps: %s" % cryptTab.mappings.keys())
        except Exception as e:
            log.info("error parsing crypttab: %s" % e)
            cryptTab = None

        self.blkidTab = blkidTab
        self.cryptTab = cryptTab

        with open(path) as f:
            log.debug("parsing %s" % path)

            lines = f.readlines()

            # save the original file
            self.origFStab = ''.join(lines)

            for line in lines:
                # strip off comments
                (line, pound, comment) = line.partition("#")
                fields = line.split()

                if not 4 <= len(fields) <= 6:
                    continue
                elif len(fields) == 4:
                    fields.extend([0, 0])
                elif len(fields) == 5:
                    fields.append(0)

                (devspec, mountpoint, fstype, options, dump, passno) = fields

                try:
                    device = self._parseOneLine((devspec, mountpoint, fstype, options, dump, passno))
                except UnrecognizedFSTabEntryError:
                    # just write the line back out as-is after upgrade
                    self.preserveLines.append(line)
                    continue
                except Exception as e:
                    raise Exception("fstab entry %s is malformed: %s" % (devspec, e))

                if not device:
                    continue

                if device not in self.devicetree.devices:
                    try:
                        self.devicetree._addDevice(device)
                    except ValueError:
                        # just write duplicates back out post-install
                        self.preserveLines.append(line)

    def turnOnSwap(self, intf=None, rootPath="", upgrading=None):
        def swapErrorDialog(msg, device):
            if not intf:
                # can't show a dialog? ignore this busted device.
                ret = 0
            else:
                buttons = [_("Skip"), _("Format"), _("_Exit")]
                ret = intf.messageWindow(_("Error"), msg, type="custom",
                                         custom_buttons=buttons,
                                         custom_icon="warning")

            if ret == 0:
                self.devicetree._removeDevice(device)
                return False
            elif ret == 1:
                device.format.create(force=True)
                return True
            else:
                sys.exit(0)

        for device in self.swapDevices:
            if isinstance(device, FileDevice):
                # set up FileDevices' parents now that they are accessible
                targetDir = "%s/%s" % (rootPath, device.path)
                parent = get_containing_device(targetDir, self.devicetree)
                if not parent:
                    log.error("cannot determine which device contains "
                              "directory %s" % device.path)
                    device.parents = []
                    self.devicetree._removeDevice(device)
                    continue
                else:
                    device.parents = [parent]

            while True:
                try:
                    device.setup()
                    device.format.setup()
                except OldSwapError:
                    msg = _("The swap device:\n\n     %s\n\n"
                            "is an old-style Linux swap partition.  If "
                            "you want to use this device for swap space, "
                            "you must reformat as a new-style Linux swap "
                            "partition.") \
                          % device.path

                    if swapErrorDialog(msg, device):
                        continue
                except SuspendError:
                    if upgrading:
                        msg = _("The swap device:\n\n     %s\n\n"
                                "in your /etc/fstab file is currently in "
                                "use as a software suspend device, "
                                "which means your system is hibernating. "
                                "To perform an upgrade, please shut down "
                                "your system rather than hibernating it.") \
                              % device.path
                    else:
                        msg = _("The swap device:\n\n     %s\n\n"
                                "in your /etc/fstab file is currently in "
                                "use as a software suspend device, "
                                "which means your system is hibernating. "
                                "If you are performing a new install, "
                                "make sure the installer is set "
                                "to format all swap devices.") \
                              % device.path

                    if swapErrorDialog(msg, device):
                        continue
                except UnknownSwapError:
                    msg = _("The swap device:\n\n     %s\n\n"
                            "does not contain a supported swap volume.  In "
                            "order to continue installation, you will need "
                            "to format the device or skip it.") \
                          % device.path

                    if swapErrorDialog(msg, device):
                        continue
                except DeviceError as (msg, name):
                    if intf:
                        if upgrading:
                            err = _("Error enabling swap device %(name)s: "
                                    "%(msg)s\n\n"
                                    "The /etc/fstab on your upgrade partition "
                                    "does not reference a valid swap "
                                    "device.\n\nPress OK to exit the "
                                    "installer") % {'name': name, 'msg': msg}
                        else:
                            err = _("Error enabling swap device %(name)s: "
                                    "%(msg)s\n\n"
                                    "This most likely means this swap "
                                    "device has not been initialized.\n\n"
                                    "Press OK to exit the installer.") % \
                                  {'name': name, 'msg': msg}
                        intf.messageWindow(_("Error"), err)
                    sys.exit(0)

                break

    def mountFilesystems(self, intf=None, rootPath="", readOnly=None,
                         skipRoot=False, raiseErrors=None):
        devices = self.mountpoints.values() + self.swapDevices
        devices.extend([self.dev, self.devshm, self.devpts, self.sysfs,
                        self.proc, self.selinux, self.usb])
        devices.sort(key=lambda d: getattr(d.format, "mountpoint", None))

        for device in devices:
            if not device.format.mountable or not device.format.mountpoint:
                continue

            if skipRoot and device.format.mountpoint == "/":
                continue

            options = device.format.options
            if "noauto" in options.split(","):
                continue

            if device.format.type == "bind" and device != self.dev:
                # set up the DirectoryDevice's parents now that they are
                # accessible
                #
                # -- bind formats' device and mountpoint are always both
                #    under the chroot. no exceptions. none, damn it.
                targetDir = "%s/%s" % (rootPath, device.path)
                parent = get_containing_device(targetDir, self.devicetree)
                if not parent:
                    log.error("cannot determine which device contains "
                              "directory %s" % device.path)
                    device.parents = []
                    self.devicetree._removeDevice(device)
                    continue
                else:
                    device.parents = [parent]

            try:
                device.setup()
            except Exception as msg:
                # FIXME: need an error popup
                continue

            if readOnly:
                options = "%s,%s" % (options, readOnly)

            try:
                device.format.setup(options=options,
                                    chroot=rootPath)
            except OSError as e:
                log.error("OSError: (%d) %s" % (e.errno, e.strerror))

                if intf:
                    if e.errno == errno.EEXIST:
                        intf.messageWindow(_("Invalid mount point"),
                                           _("An error occurred when trying "
                                             "to create %s.  Some element of "
                                             "this path is not a directory. "
                                             "This is a fatal error and the "
                                             "install cannot continue.\n\n"
                                             "Press <Enter> to exit the "
                                             "installer.")
                                           % (device.format.mountpoint,))
                    else:
                        na = {'mountpoint': device.format.mountpoint,
                              'msg': e.strerror}
                        intf.messageWindow(_("Invalid mount point"),
                                           _("An error occurred when trying "
                                             "to create %(mountpoint)s: "
                                             "%(msg)s.  This is "
                                             "a fatal error and the install "
                                             "cannot continue.\n\n"
                                             "Press <Enter> to exit the "
                                             "installer.") % na)
                sys.exit(0)
            except SystemError as (num, msg):
                log.error("SystemError: (%d) %s" % (num, msg) )

                if raiseErrors:
                    raise
                if intf and not device.format.linuxNative:
                    na = {'path': device.path,
                          'mountpoint': device.format.mountpoint}
                    ret = intf.messageWindow(_("Unable to mount filesystem"),
                                             _("An error occurred mounting "
                                             "device %(path)s as "
                                             "%(mountpoint)s.  You may "
                                             "continue installation, but "
                                             "there may be problems.") % na,
                                             type="custom",
                                             custom_icon="warning",
                                             custom_buttons=[_("_Exit installer"),
                                                            _("_Continue")])

                    if ret == 0:
                        sys.exit(0)
                    else:
                        continue

                sys.exit(0)
            except FSError as msg:
                log.error("FSError: %s" % msg)

                if intf:
                    na = {'path': device.path,
                          'mountpoint': device.format.mountpoint,
                          'msg': msg}
                    intf.messageWindow(_("Unable to mount filesystem"),
                                       _("An error occurred mounting "
                                         "device %(path)s as %(mountpoint)s: "
                                         "%(msg)s. This is "
                                         "a fatal error and the install "
                                         "cannot continue.\n\n"
                                         "Press <Enter> to exit the "
                                         "installer.") % na)
                sys.exit(0)

        self.active = True

    def umountFilesystems(self, ignoreErrors=True, swapoff=True):
        """ unmount filesystems, except swap if swapoff == False """
        devices = self.mountpoints.values() + self.swapDevices
        devices.extend([self.dev, self.devshm, self.devpts, self.sysfs,
                        self.proc, self.usb, self.selinux])
        devices.sort(key=lambda d: getattr(d.format, "mountpoint", None))
        devices.reverse()
        for device in devices:
            if (not device.format.mountable) or \
               (device.format.type == "swap" and not swapoff):
                continue

            device.format.teardown()
            device.teardown()

        self.active = False

    def createSwapFile(self, device, size, rootPath=None):
        """ Create and activate a swap file under rootPath. """
        if not rootPath:
            rootPath = self.rootpath

        filename = "/SWAP"
        count = 0
        basedir = os.path.normpath("%s/%s" % (rootPath,
                                              device.format.mountpoint))
        while os.path.exists("%s/%s" % (basedir, filename)) or \
              self.devicetree.getDeviceByName(filename):
            file = os.path.normpath("%s/%s" % (basedir, filename))
            count += 1
            filename = "/SWAP-%d" % count

        dev = FileDevice(filename,
                         size=size,
                         parents=[device],
                         format=getFormat("swap", device=filename))
        dev.create()
        dev.setup()
        dev.format.create()
        dev.format.setup()
        # nasty, nasty
        self.devicetree._addDevice(dev)

    def mkDevRoot(self, instPath=None):
        if not instPath:
            instPath = self.rootpath

        root = self.rootDevice
        dev = "%s/%s" % (instPath, root.path)
        if not os.path.exists("%s/dev/root" %(instPath,)) and os.path.exists(dev):
            rdev = os.stat(dev).st_rdev
            os.mknod("%s/dev/root" % (instPath,), stat.S_IFBLK | 0600, rdev)

    @property
    def swapDevices(self):
        swaps = []
        for device in self.devices:
            if device.format.type == "swap":
                swaps.append(device)
        return swaps

    @property
    def rootDevice(self):
        for path in ["/", self.rootpath]:
            for device in self.devices:
                try:
                    mountpoint = device.format.mountpoint
                except AttributeError:
                    mountpoint = None

                if mountpoint == path:
                    return device

    @property
    def migratableDevices(self):
        """ List of devices whose filesystems can be migrated. """
        migratable = []
        for device in self.devices:
            if device.format.migratable and device.format.exists:
                migratable.append(device)

        return migratable

    def write(self, instPath=None):
        """ write out all config files based on the set of filesystems """
        if not instPath:
            instPath = self.rootpath

        # /etc/fstab
        fstab_path = os.path.normpath("%s/etc/fstab" % instPath)
        fstab = self.fstab()
        open(fstab_path, "w").write(fstab)

        # /etc/crypttab
        crypttab_path = os.path.normpath("%s/etc/crypttab" % instPath)
        crypttab = self.crypttab()
        origmask = os.umask(0077)
        open(crypttab_path, "w").write(crypttab)
        os.umask(origmask)

        # /etc/mdadm.conf
        mdadm_path = os.path.normpath("%s/etc/mdadm.conf" % instPath)
        mdadm_conf = self.mdadmConf()
        if mdadm_conf:
            open(mdadm_path, "w").write(mdadm_conf)

        # /etc/multipath.conf
        multipath_conf = self.multipathConf()
        if multipath_conf:
            multipath_path = os.path.normpath("%s/etc/multipath.conf" %
                                              instPath)
            conf_contents = multipath_conf.write(self.devicetree.mpathFriendlyNames)
            f = open(multipath_path, "w")
            f.write(conf_contents)
            f.close()
        else:
            log.info("not writing out mpath configuration")
        iutil.copy_to_sysimage("/etc/multipath/wwids", root_path=instPath)

    def crypttab(self):
        # if we are upgrading, do we want to update crypttab?
        # gut reaction says no, but plymouth needs the names to be very
        # specific for passphrase prompting
        if not self.cryptTab:
            self.cryptTab = CryptTab(self.devicetree)
            self.cryptTab.populate()

        devices = self.mountpoints.values() + self.swapDevices

        # prune crypttab -- only mappings required by one or more entries
        for name in self.cryptTab.mappings.keys():
            keep = False
            mapInfo = self.cryptTab[name]
            cryptoDev = mapInfo['device']
            for device in devices:
                if device == cryptoDev or device.dependsOn(cryptoDev):
                    keep = True
                    break

            if not keep:
                del self.cryptTab.mappings[name]

        return self.cryptTab.crypttab()

    def mdadmConf(self):
        """ Return the contents of mdadm.conf. """
        arrays = self.devicetree.getDevicesByType("mdarray")
        arrays.extend(self.devicetree.getDevicesByType("mdbiosraidarray"))
        arrays.extend(self.devicetree.getDevicesByType("mdcontainer"))
        # Sort it, this not only looks nicer, but this will also put
        # containers (which get md0, md1, etc.) before their members
        # (which get md127, md126, etc.). and lame as it is mdadm will not
        # assemble the whole stack in one go unless listed in the proper order
        # in mdadm.conf
        arrays.sort(key=lambda d: d.path)
        if not arrays:
            return ""

        conf = "# mdadm.conf written out by anaconda\n"
        conf += "MAILADDR root\n"
        conf += "AUTO +imsm +1.x -all\n"
        devices = self.mountpoints.values() + self.swapDevices
        for array in arrays:
            for device in devices:
                if device == array or device.dependsOn(array):
                    conf += array.mdadmConfEntry
                    break

        return conf

    def multipathConf(self):
        """ Return the contents of multipath.conf. """
        mpaths = self.devicetree.getDevicesByType("dm-multipath")
        if not mpaths:
            return None
        mpaths.sort(key=lambda d: d.name)
        config = MultipathConfigWriter()
        whitelist = []
        for mpath in mpaths:
            config.addMultipathDevice(mpath)
            whitelist.append(mpath.name)
            whitelist.extend([d.name for d in mpath.parents])

        # blacklist everything we're not using and let the
        # sysadmin sort it out.
        for d in self.devicetree.devices:
            if not d.name in whitelist:
                config.addBlacklistDevice(d)

        return config

    def fstab (self):
        format = "%-23s %-23s %-7s %-15s %d %d\n"
        fstab = """
#
# /etc/fstab
# Created by anaconda on %s
#
# Accessible filesystems, by reference, are maintained under '/dev/disk'
# See man pages fstab(5), findfs(8), mount(8) and/or blkid(8) for more info
#
""" % time.asctime()

        devices = sorted(self.mountpoints.values(),
                         key=lambda d: d.format.mountpoint)
        devices += self.swapDevices
        netdevs = self.devicetree.getDevicesByInstance(NetworkStorageDevice)
        for device in devices:
            # why the hell do we put swap in the fstab, anyway?
            if not device.format.mountable and device.format.type != "swap":
                continue

            # Don't write out lines for optical devices, either.
            if isinstance(device, OpticalDevice):
                continue

            fstype = getattr(device.format, "mountType", device.format.type)
            if fstype == "swap":
                mountpoint = "swap"
                options = device.format.options
            else:
                mountpoint = device.format.mountpoint
                options = device.format.options
                if not mountpoint:
                    log.warning("%s filesystem on %s has no mountpoint" % \
                                                            (fstype,
                                                             device.path))
                    continue

            options = options or "defaults"
            for netdev in netdevs:
                if device.dependsOn(netdev):
                    options = options + ",_netdev"
                    break
            devspec = device.fstabSpec
            dump = device.format.dump
            if device.format.check and mountpoint == "/":
                passno = 1
            elif device.format.check:
                passno = 2
            else:
                passno = 0
            fstab = fstab + device.fstabComment
            fstab = fstab + format % (devspec, mountpoint, fstype,
                                      options, dump, passno)

        # now, write out any lines we were unable to process because of
        # unrecognized filesystems or unresolveable device specifications
        for line in self.preserveLines:
            fstab += line

        return fstab
