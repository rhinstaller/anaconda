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
import copy

import nss.nss
import parted

from pyanaconda import isys
from pyanaconda import iutil
from pyanaconda.constants import *
from pykickstart.constants import *
from pyanaconda.flags import flags
from pyanaconda import tsort
from pyanaconda.errors import *
from pyanaconda.bootloader import BootLoaderError
from pyanaconda.anaconda_log import log_method_call

from errors import *
from devices import *
from devicetree import DeviceTree
from deviceaction import *
from formats import getFormat
from formats import get_device_format_class
from formats import get_default_filesystem_type
from devicelibs.dm import name_from_dm_node
from devicelibs.crypto import generateBackupPassphrase
from devicelibs.mpath import MultipathConfigWriter
from devicelibs.edd import get_edd_dict
from devicelibs.mdraid import get_member_space
from devicelibs.mdraid import raidLevelString
from devicelibs.lvm import get_pv_space
from .partitioning import SameSizeSet
from .partitioning import TotalSizeSet
from .partitioning import doPartitioning
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

DEVICE_TYPE_LVM = 0
DEVICE_TYPE_MD = 1
DEVICE_TYPE_PARTITION = 2
DEVICE_TYPE_BTRFS = 3
DEVICE_TYPE_DISK = 4

def getDeviceType(device):
    device_types = {"partition": DEVICE_TYPE_PARTITION,
                    "lvmlv": DEVICE_TYPE_LVM,
                    "btrfs subvolume": DEVICE_TYPE_BTRFS,
                    "btrfs volume": DEVICE_TYPE_BTRFS,
                    "mdarray": DEVICE_TYPE_MD}

    use_dev = device
    if isinstance(device, LUKSDevice):
        use_dev = device.slave

    if use_dev.isDisk:
        device_type = DEVICE_TYPE_DISK
    else:
        device_type = device_types.get(use_dev.type)

    return device_type

def getRAIDLevel(device):
    # TODO: move this into StorageDevice
    use_dev = device
    if isinstance(device, LUKSDevice):
        use_dev = device.slave

    # TODO: lvm and perhaps pulling raid level from md pvs
    raid_level = None
    if hasattr(use_dev, "level"):
        raid_level = raidLevelString(use_dev.level)
    elif hasattr(use_dev, "dataLevel"):
        raid_level = use_dev.dataLevel or "single"
    elif hasattr(use_dev, "volume"):
        raid_level = use_dev.volume.dataLevel or "single"

    return raid_level

def storageInitialize(storage, ksdata, protected):
    storage.shutdown()

    # touch /dev/.in_sysinit so that /lib/udev/rules.d/65-md-incremental.rules
    # does not mess with any mdraid sets
    open("/dev/.in_sysinit", "w")

    # XXX I don't understand why I have to do this, but this is needed to
    #     populate the udev db
    iutil.execWithRedirect("udevadm", ["control", "--property=ANACONDA=1"],
                           stdout="/dev/tty5", stderr="/dev/tty5")
    udev_trigger(subsystem="block", action="change")

    # Before we set up the storage system, we need to know which disks to
    # ignore, etc.  Luckily that's all in the kickstart data.
    storage.config.update(ksdata)

    lvm.lvm_vg_blacklist = []

    # Set up the protected partitions list now.
    if protected:
        storage.config.protectedDevSpecs.extend(protected)
        storage.reset()

        if not flags.livecdInstall and not storage.protectedDevices:
            if anaconda.upgrade:
                return
            else:
                raise UnknownSourceDeviceError(protected)
    else:
        storage.reset()

    # kickstart uses all the disks
    if flags.automatedInstall:
        if not ksdata.ignoredisk.onlyuse:
            ksdata.ignoredisk.onlyuse = [d.name for d in storage.disks \
                                         if d.name not in ksdata.ignoredisk.ignoredisk]
            log.debug("onlyuse is now: %s" % (",".join(ksdata.ignoredisk.onlyuse)))

def turnOnFilesystems(storage):
    upgrade = "preupgrade" in flags.cmdline

    if not upgrade:
        if (flags.livecdInstall and not flags.imageInstall and not storage.fsset.active):
            # turn off any swaps that we didn't turn on
            # needed for live installs
            iutil.execWithRedirect("swapoff", ["-a"],
                                   stdout = "/dev/tty5", stderr="/dev/tty5")
        storage.devicetree.teardownAll()

    upgrade_migrate = False
    if upgrade:
        for d in storage.migratableDevices:
            if d.format.migrate:
                upgrade_migrate = True

    try:
        storage.doIt()
    except FSResizeError as e:
        if os.path.exists("/tmp/resize.out"):
            details = open("/tmp/resize.out", "r").read()
        else:
            details = e.args[1]

        if errorHandler.cb(e, e.args[0], details=details) == ERROR_RAISE:
            raise
    except FSMigrateError as e:
        if errorHandler.cb(e, e.args[0], e.args[1]) == ERROR_RAISE:
            raise
    except Exception as e:
        raise

    storage.turnOnSwap()
    # FIXME:  For livecd, skipRoot needs to be True.
    storage.mountFilesystems(raiseErrors=False,
                             readOnly=False,
                             skipRoot=False)
    writeEscrowPackets(storage)

def writeEscrowPackets(storage):
    escrowDevices = filter(lambda d: d.format.type == "luks" and \
                                     d.format.escrow_cert,
                           storage.devices)

    if not escrowDevices:
        return

    log.debug("escrow: writeEscrowPackets start")

    nss.nss.nss_init_nodb() # Does nothing if NSS is already initialized

    backupPassphrase = generateBackupPassphrase()
    try:
        for device in escrowDevices:
            log.debug("escrow: device %s: %s" %
                      (repr(device.path), repr(device.format.type)))
            device.format.escrow(ROOT_PATH + "/root",
                                 backupPassphrase)

    except (IOError, RuntimeError) as e:
        # TODO: real error handling
        log.error("failed to store encryption key: %s" % e)

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
        self.clearPartDevices = []
        self.initializeDisks = False
        self.protectedDevSpecs = []
        self.diskImages = {}
        self.mpathFriendlyNames = True

        # Whether clearPartitions removes scheduled/non-existent devices and
        # disklabels depends on this flag.
        self.clearNonExistent = False

    def update(self, ksdata):
        self.ignoredDisks = ksdata.ignoredisk.ignoredisk[:]
        self.exclusiveDisks = ksdata.ignoredisk.onlyuse[:]
        self.clearPartType = ksdata.clearpart.type
        self.clearPartDisks = ksdata.clearpart.drives[:]
        self.clearPartDevices = ksdata.clearpart.devices[:]
        self.initializeDisks = ksdata.clearpart.initAll
        self.zeroMbr = ksdata.zerombr.zerombr

class Storage(object):
    def __init__(self, data=None, platform=None):
        """ Create a Storage instance.

            Keyword Arguments:

                data        -   a pykickstart Handler instance
                platform    -   a Platform instance

        """
        self.data = data
        self.platform = platform
        self._bootloader = None

        self.config = StorageDiscoveryConfig()

        # storage configuration variables
        self.doAutoPart = False
        self.clearPartChoice = None
        self.encryptedAutoPart = False
        self.autoPartType = AUTOPART_TYPE_LVM
        self.encryptionPassphrase = None
        self.encryptionCipher = None
        self.escrowCertificates = {}
        self.autoPartEscrowCert = None
        self.autoPartAddBackupPassphrase = False
        self.encryptionRetrofit = False
        self.autoPartitionRequests = []
        self.eddDict = {}

        self.__luksDevs = {}
        self.size_sets = []

        self.iscsi = iscsi.iscsi()
        self.fcoe = fcoe.fcoe()
        self.zfcp = zfcp.ZFCP()
        self.dasd = dasd.DASD()

        self._nextID = 0
        self.defaultFSType = get_default_filesystem_type()
        self._dumpFile = "/tmp/storage.state"

        # these will both be empty until our reset method gets called
        self.devicetree = DeviceTree(conf=self.config,
                                     passphrase=self.encryptionPassphrase,
                                     luksDict=self.__luksDevs,
                                     iscsi=self.iscsi,
                                     dasd=self.dasd)
        self.fsset = FSSet(self.devicetree)
        self.roots = []
        self.services = set()

    def doIt(self):
        self.devicetree.processActions()
        self.doEncryptionPassphraseRetrofits()

        # now set the boot partition's flag
        if self.bootloader:
            if self.bootloader.stage2_bootable:
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

                    # GPT labeled disks should only have bootable set on the
                    # EFI system partition (parted sets the EFI System GUID on
                    # GPT partitions with the boot flag)
                    if dev.disk.format.labelType == "gpt" and \
                       dev.format.type != "efi":
                           skip = True

                    if skip:
                         log.info("not setting boot flag on %s" % dev.name)
                         continue
                    # hfs+ partitions on gpt can't be marked bootable via
                    # parted
                    if dev.disk.format.partedDisk.type == "gpt" and \
                            dev.format.type == "hfs+":
                        log.info("not setting boot flag on hfs+ partition"
                                 " %s" % dev.name)
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

        if self.data:
            self.config.update(self.data)

        if not flags.imageInstall:
            self.iscsi.startup()
            self.fcoe.startup()
            self.zfcp.startup()
            self.dasd.startup(None,
                              self.config.exclusiveDisks,
                              self.config.initializeDisks)
        clearPartType = self.config.clearPartType # save this before overriding it
        if self.data and self.data.upgrade.upgrade:
            self.config.clearPartType = CLEARPART_TYPE_NONE

        if self.dasd:
            # Reset the internal dasd list (823534)
            self.dasd.clear_device_list()

        self.devicetree.reset(conf=self.config,
                              passphrase=self.encryptionPassphrase,
                              luksDict=self.__luksDevs,
                              iscsi=self.iscsi,
                              dasd=self.dasd)
        self.devicetree.populate(cleanupOnly=cleanupOnly)
        self.config.clearPartType = clearPartType # set it back
        self.fsset = FSSet(self.devicetree)
        self.eddDict = get_edd_dict(self.partitioned)
        if self.bootloader:
            # clear out bootloader attributes that refer to devices that are
            # no longer in the tree
            self.bootloader.stage1_disk = None
            self.bootloader.stage1_device = None
            self.bootloader.stage2_device = None

        self.roots = findExistingInstallations(self.devicetree)

        self.dumpState("initial")

        self.updateBootLoaderDiskList()

    @property
    def unusedDevices(self):
        used_devices = []
        for root in self.roots:
            for device in root.mounts.values() + root.swaps:
                if device not in self.devices:
                    continue

                used_devices.extend(device.ancestors)

        for new in [d for d in self.devicetree.leaves if not d.format.exists]:
            if new in self.swaps or getattr(new.format, "mountpoint", None):
                used_devices.extend(new.ancestors)

        for device in self.partitions:
            if getattr(device, "isLogical", False):
                extended = device.disk.format.extendedPartition.path
                used_devices.append(self.devicetree.getDeviceByPath(extended))

        used = set(used_devices)
        _all = set(self.devices)
        return list(_all.difference(used))

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
    def btrfsVolumes(self):
        return sorted(self.devicetree.getDevicesByType("btrfs volume"),
                      key=lambda d: d.name)

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
        return None

    def shouldClear(self, device, **kwargs):
        clearPartType = kwargs.get("clearPartType", self.config.clearPartType)
        clearPartDisks = kwargs.get("clearPartDisks",
                                    self.config.clearPartDisks)
        clearPartDevices = kwargs.get("clearPartDevices",
                                      self.config.clearPartDevices)

        def empty_disk(device):
            empty = True
            if device.partitioned:
                partitions = self.devicetree.getChildren(device)
                empty = all([p.isMagic for p in partitions])
            else:
                empty = (device.format.type is None)

            return empty

        for disk in device.disks:
            # this will not include disks with hidden formats like multipath
            # and firmware raid member disks
            if clearPartDisks and disk.name not in clearPartDisks:
                return False

        if not self.config.clearNonExistent:
            if (device.isDisk and not device.format.exists) or \
               (not device.isDisk and not device.exists):
                return False

        # the only devices we want to clear when clearPartType is
        # CLEARPART_TYPE_NONE are uninitialized disks, or disks with no
        # partitions, in clearPartDisks, and then only when we have been asked
        # to initialize disks as needed
        if clearPartType in [CLEARPART_TYPE_NONE, None]:
            if not self.config.initializeDisks or not device.isDisk:
                return False

            if not empty_disk(device):
                return False

        if isinstance(device, PartitionDevice):
            # Never clear the special first partition on a Mac disk label, as
            # that holds the partition table itself.
            # Something similar for the third partition on a Sun disklabel.
            if device.isMagic:
                return False

            # We don't want to fool with extended partitions, freespace, &c
            if not device.isPrimary and not device.isLogical:
                return False

            if clearPartType == CLEARPART_TYPE_LINUX and \
               not device.format.linuxNative and \
               not device.getFlag(parted.PARTITION_LVM) and \
               not device.getFlag(parted.PARTITION_RAID) and \
               not device.getFlag(parted.PARTITION_SWAP):
                return False
        elif device.isDisk:
            if device.partitioned and clearPartType != CLEARPART_TYPE_ALL:
                # if clearPartType is not CLEARPART_TYPE_ALL but we'll still be
                # removing every partition from the disk, return True since we
                # will want to be able to create a new disklabel on this disk
                if not empty_disk(device):
                    return False

            # Never clear disks with hidden formats
            if device.format.hidden:
                return False

            # When clearPartType is CLEARPART_TYPE_LINUX and a disk has non-
            # linux whole-disk formatting, do not clear it. The exception is
            # the case of an uninitialized disk when we've been asked to
            # initialize disks as needed
            if clearPartType == CLEARPART_TYPE_LINUX and \
               not (self.config.initializeDisks and
                    device.format.type is None) and \
               not device.partitioned and not device.format.linuxNative:
                return False

        # Don't clear devices holding install media.
        if device.protected:
            return False

        if clearPartType == CLEARPART_TYPE_LIST and \
           device.name not in clearPartDevices:
            return False

        return True

    def recursiveRemove(self, device):
        log.debug("removing %s" % device.name)

        # XXX is there any argument for not removing incomplete devices?
        #       -- maybe some RAID devices
        devices = self.deviceDeps(device)
        while devices:
            log.debug("devices to remove: %s" % ([d.name for d in devices],))
            leaves = [d for d in devices if d.isleaf]
            log.debug("leaves to remove: %s" % ([d.name for d in leaves],))
            for leaf in leaves:
                self.destroyDevice(leaf)
                devices.remove(leaf)

        if device.isDisk:
            self.devicetree.registerAction(ActionDestroyFormat(device))
        else:
            self.destroyDevice(device)

    def clearPartitions(self):
        """ Clear partitions and dependent devices from disks.

            Arguments:

                None

            NOTES:

                - Needs some error handling

        """
        if not hasattr(self.platform, "diskLabelTypes"):
            raise StorageError("can't clear partitions without platform data")

        # Sort partitions by descending partition number to minimize confusing
        # things like multiple "destroy sda5" actions due to parted renumbering
        # partitions. This can still happen through the UI but it makes sense to
        # avoid it where possible.
        partitions = sorted(self.partitions,
                            key=lambda p: p.partedPartition.number,
                            reverse=True)
        for part in partitions:
            log.debug("clearpart: looking at %s" % part.name)
            if not self.shouldClear(part):
                continue

            self.recursiveRemove(part)
            log.debug("partitions: %s" % [p.getDeviceNodeName() for p in part.partedPartition.disk.partitions])

        # now remove any empty extended partitions
        self.removeEmptyExtendedPartitions()

        # ensure all disks have appropriate disklabels
        for disk in self.disks:
            if not self.shouldClear(disk):
                continue

            log.debug("clearpart: initializing %s" % disk.name)
            self.initializeDisk(disk)

        self.updateBootLoaderDiskList()

    def initializeDisk(self, disk):
        """ (Re)initialize a disk by creating a disklabel on it.

            The disk should not contain any partitions except perhaps for a
            magic partitions on mac and sun disklabels.
        """
        # first, remove magic mac/sun partitions from the parted Disk
        if disk.partitioned:
            magic_partitions = {"mac": 1, "sun": 3}
            if disk.format.labelType in magic_partitions:
                number = magic_partitions[disk.format.labelType]
                # remove the magic partition
                for part in disk.format.partitions:
                    if part.disk == disk and part.partedPartition.number == number:
                        log.debug("removing %s" % part.name)
                        # We can't schedule the magic partition for removal
                        # because parted will not allow us to remove it from the
                        # disk. Still, we need it out of the devicetree.
                        self.devicetree._removeDevice(part, moddisk=False)

        if disk.partitioned and disk.format.partitions:
            raise ValueError("cannot initialize a disk that has partitions")

        # remove existing formatting from the disk
        destroy_action = ActionDestroyFormat(disk)
        self.devicetree.registerAction(destroy_action)

        if self.platform:
            labelType = self.platform.bestDiskLabelType(disk)
        else:
            labelType = None

        # create a new disklabel on the disk
        newLabel = getFormat("disklabel", device=disk.path,
                             labelType=labelType)
        create_action = ActionCreateFormat(disk, format=newLabel)
        self.devicetree.registerAction(create_action)

    def removeEmptyExtendedPartitions(self):
        for disk in self.partitioned:
            log.debug("checking whether disk %s has an empty extended" % disk.name)
            extended = disk.format.extendedPartition
            logical_parts = disk.format.logicalPartitions
            log.debug("extended is %s ; logicals is %s" % (extended, [p.getDeviceNodeName() for p in logical_parts]))
            if extended and not logical_parts:
                log.debug("removing empty extended partition from %s" % disk.name)
                extended_name = devicePathToName(extended.getDeviceNodeName())
                extended = self.devicetree.getDeviceByName(extended_name)
                self.destroyDevice(extended)

    def getFreeSpace(self, disks=None, clearPartType=None):
        """ Return a dict with free space info for each disk.

            The dict values are 2-tuples: (disk_free, fs_free). fs_free is
            space available by shrinking filesystems. disk_free is space not
            allocated to any partition.

            disks and clearPartType allow specifying a set of disks other than
            self.disks and a clearPartType value other than
            self.config.clearPartType.
        """
        from size import Size
        if disks is None:
            disks = self.disks

        if clearPartType is None:
            clearPartType = self.config.clearPartType

        free = {}
        for disk in disks:
            should_clear = self.shouldClear(disk, clearPartType=clearPartType,
                                            clearPartDisks=[disk.name])
            if should_clear:
                free[disk.name] = (Size(spec="%f mb" % disk.size), 0)
                continue

            disk_free = 0
            fs_free = 0
            if disk.partitioned:
                disk_free = disk.format.free
                for partition in [p for p in self.partitions if p.disk == disk]:
                    # only check actual filesystems since lvm &c require a bunch of
                    # operations to translate free filesystem space into free disk
                    # space
                    should_clear = self.shouldClear(partition,
                                                    clearPartType=clearPartType,
                                                    clearPartDisks=[disk.name])
                    if should_clear:
                        disk_free += partition.size
                    elif hasattr(partition.format, "free"):
                        fs_free += partition.format.free
            elif hasattr(disk.format, "free"):
                fs_free = disk.format.free
            elif disk.format.type is None:
                disk_free = disk.size

            free[disk.name] = (Size(spec="%f mb" % disk_free),
                               Size(spec="%f mb" % fs_free))

        return free

    @property
    def names(self):
        return self.devicetree.names

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

        if kwargs.has_key("name"):
            name = kwargs.pop("name")
        else:
            name = "req%d" % self.nextID

        if "weight" not in kwargs:
            fmt = kwargs.get("format")
            if fmt:
                mountpoint = getattr(fmt, "mountpoint", None)

                kwargs["weight"] = self.platform.weight(mountpoint=mountpoint,
                                                        fstype=fmt.type)


        return PartitionDevice(name, *args, **kwargs)

    def newMDArray(self, *args, **kwargs):
        """ Return a new MDRaidArrayDevice instance for configuring. """
        if kwargs.has_key("fmt_type"):
            kwargs["format"] = getFormat(kwargs.pop("fmt_type"),
                                         mountpoint=kwargs.pop("mountpoint",
                                                               None),
                                         **kwargs.pop("fmt_args", {}))

        if kwargs.has_key("name"):
            name = kwargs.pop("name")
        else:
            swap = getattr(kwargs.get("format"), "type", None) == "swap"
            mountpoint = getattr(kwargs.get("format"), "mountpoint", None)
            name = self.suggestDeviceName(prefix=shortProductName,
                                          swap=swap,
                                          mountpoint=mountpoint)

        return MDRaidArrayDevice(name, *args, **kwargs)

    def newVG(self, *args, **kwargs):
        """ Return a new LVMVolumeGroupDevice instance. """
        pvs = kwargs.pop("parents", [])
        for pv in pvs:
            if pv not in self.devices:
                raise ValueError("pv is not in the device tree")

        if kwargs.has_key("name"):
            name = kwargs.pop("name")
        else:
            hostname = ""
            if self.data and self.data.network.hostname is not None:
                hostname = self.data.network.hostname

            name = self.suggestContainerName(hostname=hostname)

        if name in self.names:
            raise ValueError("name already in use")

        return LVMVolumeGroupDevice(name, pvs, *args, **kwargs)

    def newLV(self, *args, **kwargs):
        """ Return a new LVMLogicalVolumeDevice instance. """
        vg = kwargs.get("parents", [None])[0]
        mountpoint = kwargs.pop("mountpoint", None)
        if kwargs.has_key("fmt_type"):
            kwargs["format"] = getFormat(kwargs.pop("fmt_type"),
                                         mountpoint=mountpoint,
                                         **kwargs.pop("fmt_args", {}))

        if kwargs.has_key("name"):
            name = kwargs.pop("name")
            # make sure the specified name is sensible
            safe_vg_name = self.safeDeviceName(vg.name)
            full_name = "%s-%s" % (safe_vg_name, name)
            safe_name = self.safeDeviceName(full_name)
            if safe_name != full_name:
                new_name = safe_name[len(safe_vg_name)+1:]
                log.warning("using '%s' instead of specified name '%s'"
                                % (new_name, name))
                name = new_name
        else:
            if kwargs.get("format") and kwargs["format"].type == "swap":
                swap = True
            else:
                swap = False
            name = self.suggestDeviceName(parent=vg,
                                          swap=swap,
                                          mountpoint=mountpoint)

        if "%s-%s" % (vg.name, name) in self.names:
            raise ValueError("name already in use")

        return LVMLogicalVolumeDevice(name, *args, **kwargs)

    def newBTRFS(self, *args, **kwargs):
        """ Return a new BTRFSVolumeDevice or BRFSSubVolumeDevice. """
        log.debug("newBTRFS: args = %s ; kwargs = %s" % (args, kwargs))
        name = kwargs.pop("name", None)
        if args:
            name = args[0]

        mountpoint = kwargs.pop("mountpoint", None)

        fmt_args = kwargs.pop("fmt_args", {})
        fmt_args.update({"mountpoint": mountpoint})

        if kwargs.pop("subvol", False):
            dev_class = BTRFSSubVolumeDevice
            # make sure there's a valid parent device
            parents = kwargs.get("parents", [])
            if not parents or len(parents) != 1 or \
               not isinstance(parents[0], BTRFSVolumeDevice):
                raise ValueError("new btrfs subvols require a parent volume")

            # set up the subvol name, using mountpoint if necessary
            if not name:
                # for btrfs this only needs to ensure the subvol name is not
                # already in use within the parent volume
                name = self.suggestDeviceName(mountpoint=mountpoint)
            fmt_args["mountopts"] = "subvol=%s" % name
            kwargs.pop("metaDataLevel", None)
            kwargs.pop("dataLevel", None)
        else:
            dev_class = BTRFSVolumeDevice
            # set up the volume label, using hostname if necessary
            if not name:
                hostname = ""
                if self.data and self.data.network.hostname is not None:
                    hostname = self.data.network.hostname

                name = self.suggestContainerName(hostname=hostname)
            if "label" not in fmt_args:
                fmt_args["label"] = name

        # discard fmt_type since it's btrfs always
        kwargs.pop("fmt_type", None)

        # this is to avoid auto-scheduled format create actions
        device = dev_class(name, **kwargs)
        device.format = getFormat("btrfs", **fmt_args)
        return device

    def newBTRFSSubVolume(self, *args, **kwargs):
        kwargs["subvol"] = True
        return self.newBTRFS(*args, **kwargs)

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

    def resetDevice(self, device):
        """ Cancel all scheduled actions and reset formatting. """
        actions = self.devicetree.findActions(device=device)
        for action in reversed(actions):
            self.devicetree.cancelAction(action)

        # make sure any random overridden attributes are reset
        device.format = copy.copy(device.originalFormat)

    def resizeDevice(self, device, new_size):
        classes = []
        if device.resizable:
            classes.append(ActionResizeDevice)

        if device.format.resizable:
            classes.append(ActionResizeFormat)

        if not classes:
            raise ValueError("device cannot be resized")

        # if this is a shrink, schedule the format resize first
        if new_size < device.size:
            classes.reverse()

        for action_class in classes:
            self.devicetree.registerAction(action_class(device, new_size))

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

    def safeDeviceName(self, name):
        """ Convert a device name to something safe and return that.

            LVM limits lv names to 128 characters. I don't know the limits for
            the other various device types, so I'm going to pick a number so
            that we don't have to have an entire fucking library to determine
            device name limits.
        """
        max_len = 96    # No, you don't need longer names than this. Really.
        tmp = name.strip()
        tmp = tmp.replace("/", "_")
        tmp = re.sub("[^0-9a-zA-Z._-]", "", tmp)
        tmp = tmp.lstrip("_")

        if len(tmp) > max_len:
            tmp = tmp[:max_len]

        return tmp

    def suggestContainerName(self, hostname=None, prefix=""):
        """ Return a reasonable, unused device name. """
        if not prefix:
            prefix = shortProductName

        # try to create a device name incorporating the hostname
        if hostname not in (None, "", 'localhost', 'localhost.localdomain'):
            template = "%s_%s" % (prefix, hostname.split('.')[0].lower())
            template = self.safeDeviceName(template)
        else:
            template = prefix

        if flags.imageInstall:
            template = "%s_image" % template

        names = self.names
        name = template
        if name in names:
            name = None
            for i in range(100):
                tmpname = "%s%02d" % (template, i,)
                if tmpname not in names:
                    name = tmpname
                    break

            if not name:
                log.error("failed to create device name based on prefix "
                          "'%s' and hostname '%s'" % (prefix, hostname))
                raise RuntimeError("unable to find suitable device name")

        return name

    def suggestDeviceName(self, parent=None, swap=None,
                                  mountpoint=None, prefix=""):
        """ Return a suitable, unused name for a new logical volume. """
        body = ""
        if mountpoint:
            if mountpoint == "/":
                body = "root"
            else:
                body = mountpoint[1:].replace("/", "_")
        elif swap:
            body = "swap"

        if prefix:
            body = "_" + body

        template = self.safeDeviceName(prefix + body)
        names = self.names
        name = template
        def full_name(name, parent):
            full = ""
            if parent:
                full = "%s-" % parent.name
            full += name
            return full

        # also include names of any lvs in the parent for the case of the
        # temporary vg in the lvm dialogs, which can contain lvs that are
        # not yet in the devicetree and therefore not in self.names
        if full_name(name, parent) in names or not body:
            for i in range(100):
                name = "%s%02d" % (template, i)
                if full_name(name, parent) not in names:
                    break
                else:
                    name = ""

            if not name:
                log.error("failed to create device name based on parent '%s', "
                          "prefix '%s', mountpoint '%s', swap '%s'"
                          % (parent.name, prefix, mountpoint, swap))
                raise RuntimeError("unable to find suitable device name")

        return name

    def savePassphrase(self, device):
        """ Save a device's LUKS passphrase in case of reset. """
        passphrase = device.format._LUKS__passphrase
        self.__luksDevs[device.format.uuid] = passphrase
        self.devicetree._DeviceTree__luksDevs[device.format.uuid] = passphrase
        self.devicetree._DeviceTree__passphrases.append(passphrase)

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

    @property
    def fileSystemFreeSpace(self):
        mountpoints = ["/", "/usr"]
        free = 0
        btrfs_volumes = []
        for mountpoint in mountpoints:
            device = self.mountpoints.get(mountpoint)
            if not device:
                continue

            # don't count the size of btrfs volumes repeatedly when multiple
            # subvolumes are present
            if isinstance(device, BTRFSSubVolumeDevice):
                if device.volume in btrfs_volumes:
                    continue
                else:
                    btrfs_volumes.append(device.volume)

            if device.format.exists:
                free += device.format.free
            else:
                free += device.size

        return free

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
            boot = None

        if not root:
            errors.append(_("You have not defined a root partition (/), "
                            "which is required for installation of %s "
                            "to continue.") % (productName,))

        if root and root.size < 250:
            warnings.append(_("Your root partition is less than 250 "
                              "megabytes which is usually too small to "
                              "install %s.") % (productName,))

        # Prevent users from installing on s390x with (a) no /boot volume, (b) the
        # root volume on LVM, and (c) the root volume not restricted to a single
        # PV
        # NOTE: There is not really a way for users to create a / volume
        # restricted to a single PV.  The backend support is there, but there are
        # no UI hook-ups to drive that functionality, but I do not personally
        # care.  --dcantrell
        if iutil.isS390() and \
           not self.mountpoints.has_key('/boot') and \
           root.type == 'lvmlv' and not root.singlePV:
            errors.append(_("This platform requires /boot on a dedicated "
                            "partition or logical volume.  If you do not "
                            "want a /boot volume, you must place / on a "
                            "dedicated non-LVM partition."))

        # FIXME: put a check here for enough space on the filesystems. maybe?

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

        if self.bootloader and not self.bootloader.skip_bootloader:
            stage1 = self.bootloader.stage1_device
            if not stage1:
                errors.append(_("you have not created a bootloader stage1 "
                                "target device"))
            else:
                self.bootloader.is_valid_stage1_device(stage1)
                errors.extend(self.bootloader.errors)
                warnings.extend(self.bootloader.warnings)

            stage2 = self.bootloader.stage2_device
            if not stage2:
                errors.append(_("You have not created a bootable partition."))
            else:
                self.bootloader.is_valid_stage2_device(stage2)
                errors.extend(self.bootloader.errors)
                warnings.extend(self.bootloader.warnings)
                if not self.bootloader.check():
                    errors.extend(self.bootloader.errors)

            #
            # check that GPT boot disk on BIOS system has a BIOS boot partition
            #
            if self.platform.weight(fstype="biosboot") and \
               stage1 and stage1.isDisk and \
               getattr(stage1.format, "labelType", None) == "gpt":
                missing = True
                for part in [p for p in self.partitions if p.disk == stage1]:
                    if part.format.type == "biosboot":
                        missing = False
                        break

                if missing:
                    errors.append(_("Your BIOS-based system needs a special "
                                    "partition to boot with %s's new "
                                    "disk label format (GPT). To continue, "
                                    "please create a 1MB 'BIOS Boot' type "
                                    "partition.") % productName)

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

        if self.rootDevice and self.rootDevice.format.exists:
            e = self.mustFormat(self.rootDevice)
            if e:
                errors.append(e)

        return (errors, warnings)

    def isProtected(self, device):
        """ Return True is the device is protected. """
        return device.protected

    def checkNoDisks(self):
        """Check that there are valid disk devices."""
        if not self.disks:
            raise NoDisksError()

    def dumpState(self, suffix):
        """ Dump the current device list to the storage shelf. """
        key = "devices.%d.%s" % (time.time(), suffix)
        with contextlib.closing(shelve.open(self._dumpFile)) as shelf:
            shelf[key] = [d.dict for d in self.devices]

    @property
    def packages(self):
        pkgs = set()
        if self.platform:
            pkgs.update(self.platform.packages)

        if self.bootloader:
            pkgs.update(self.bootloader.packages)

        for device in self.fsset.devices:
            # this takes care of device and filesystem packages
            pkgs.update(device.packages)

        return list(pkgs)

    def write(self):
        if not os.path.isdir("%s/etc" % ROOT_PATH):
            os.mkdir("%s/etc" % ROOT_PATH)

        self.fsset.write()
        self.makeMtab()
        self.iscsi.write(self)
        self.fcoe.write()
        self.zfcp.write()
        self.dasd.write()

    def turnOnSwap(self, upgrading=None):
        self.fsset.turnOnSwap(rootPath=ROOT_PATH,
                              upgrading=upgrading)

    def mountFilesystems(self, raiseErrors=None, readOnly=None, skipRoot=False):
        self.fsset.mountFilesystems(rootPath=ROOT_PATH,
                                    raiseErrors=raiseErrors,
                                    readOnly=readOnly, skipRoot=skipRoot)

    def umountFilesystems(self, ignoreErrors=True, swapoff=True):
        self.fsset.umountFilesystems(ignoreErrors=ignoreErrors, swapoff=swapoff)

    def parseFSTab(self, chroot=None):
        self.fsset.parseFSTab(chroot=chroot)

    def mkDevRoot(self):
        self.fsset.mkDevRoot()

    def createSwapFile(self, device, size):
        self.fsset.createSwapFile(device, size)

    @property
    def bootloader(self):
        if self._bootloader is None and self.platform is not None:
            self._bootloader = self.platform.bootloaderClass(self.platform)
        return self._bootloader

    def updateBootLoaderDiskList(self):
        if not self.bootloader:
            return

        boot_disks = [d for d in self.disks if d.partitioned]
        boot_disks.sort(cmp=self.compareDisks, key=lambda d: d.name)
        self.bootloader.set_disk_list(boot_disks)

    def setUpBootLoader(self):
        """ Propagate ksdata into BootLoader. """
        if not self.bootloader or not self.data:
            log.warning("either ksdata or bootloader data missing")
            return

        if self.bootloader.skip_bootloader:
            log.info("user specified that bootloader install be skipped")
            return

        self.bootloader.stage1_disk = self.devicetree.resolveDevice(self.data.bootloader.bootDrive)
        self.bootloader.stage2_device = self.bootDevice
        try:
            self.bootloader.set_stage1_device(self.devices)
        except BootLoaderError as e:
            log.debug("failed to set bootloader stage1 device: %s" % e)

    @property
    def bootDisk(self):
        disk = None
        if self.data:
            spec = self.data.bootloader.bootDrive
            disk = self.devicetree.resolveDevice(spec)
        return disk

    @property
    def bootDevice(self):
        dev = None
        if self.fsset:
            dev = self.mountpoints.get("/boot", self.rootDevice)
        return dev

    @property
    def bootLoaderDevice(self):
        return getattr(self.bootloader, "stage1_device", None)

    @property
    def bootFSTypes(self):
        """A list of all valid filesystem types for the boot partition."""
        fstypes = []
        if self.bootloader:
            fstypes = self.bootloader.stage2_format_types
        return fstypes

    @property
    def defaultBootFSType(self):
        """The default filesystem type for the boot partition."""
        fstype = None
        if self.bootloader:
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

    def makeMtab(self):
        path = "/etc/mtab"
        target = "/proc/self/mounts"
        path = os.path.normpath("%s/%s" % (ROOT_PATH, path))

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

    def getFSType(self, mountpoint=None):
        """ Return the default filesystem type based on mountpoint. """
        fstype = self.defaultFSType
        if not mountpoint:
            # just return the default
            pass
        elif mountpoint.lower() in ("swap", "biosboot", "prepboot"):
            fstype = mountpoint.lower()
        elif mountpoint == "/boot":
            fstype = self.defaultBootFSType
        elif mountpoint == "/boot/efi":
            if iutil.isMactel():
                fstype = "hfs+"
            else:
                fstype = "efi"

        return fstype

    def setContainerMembers(self, container, factory, members=None,
                            device=None):
        """ Set up and return the container's member partitions. """
        log_members = []
        if members:
            log_members = [str(m) for m in members]
        log_method_call(self, container=container, factory=factory,
                        members=log_members, device=device)
        if factory.member_list is not None:
            # short-circuit the logic below for partitions
            return factory.member_list

        if container and container.exists:
            # don't try to modify an existing container
            return container.parents

        if factory.container_size_func is None:
            return []

        # set up member devices
        container_size = factory.device_size
        add_disks = []
        remove_disks = []

        if members is None:
            members = []

        if container:
            members = container.parents[:]
        elif members:
            # mdarray
            container = device

        # The basis for whether we are modifying a member set versus creating
        # one must be the member list, as container will be None when modifying
        # the member set of an md array.

        # XXX how can we detect/handle failure to use one or more of the disks?
        if members and device:
            # See if we need to add/remove any disks, but only if we are
            # adjusting a device. When adding a new device to a container we do
            # not want to modify the container's disk set.
            _disks = list(set([d for m in members for d in m.disks]))

            add_disks = [d for d in factory.disks if d not in _disks]
            remove_disks = [d for d in _disks if d not in factory.disks]
        elif not members:
            # new container, so use the factory's disk set
            add_disks = factory.disks

        # drop any new disks that don't have free space
        min_free = min(500, factory.size)
        add_disks = [d for d in add_disks if d.partitioned and
                                             d.format.free >= min_free]

        base_size = max(1, getFormat(factory.member_format).minSize)

        # XXX TODO: multiple member devices per disk

        # prepare already-defined member partitions for reallocation
        for member in members[:]:
            if any([d in remove_disks for d in member.disks]):
                if isinstance(member, LUKSDevice):
                    if container:
                        container.removeMember(member)
                    self.destroyDevice(member)
                    members.remove(member)
                    member = member.slave
                else:
                    if container:
                        container.removeMember(member)

                    members.remove(member)

                self.destroyDevice(member)
                continue

            if isinstance(member, LUKSDevice):
                if not factory.encrypted:
                    # encryption was toggled for the member devices
                    if container:
                        container.removeMember(member)

                    self.destroyDevice(member)
                    members.remove(member)

                    self.formatDevice(member.slave,
                                      getFormat(factory.member_format))
                    members.append(member.slave)
                    if container:
                        container.addMember(member.slave)

                member = member.slave
            elif factory.encrypted:
                # encryption was toggled for the member devices
                if container:
                    container.removeMember(member)

                members.remove(member)
                self.formatDevice(member, getFormat("luks"))
                luks_member = LUKSDevice("luks-%s" % member.name,
                                    parents=[member],
                                    format=getFormat(factory.member_format))
                self.createDevice(luks_member)
                members.append(luks_member)
                if container:
                    container.addMember(luks_member)

            member.req_base_size = base_size
            member.req_size = member.req_base_size
            member.req_grow = True

        # set up new members as needed to accommodate the device
        new_members = []
        for disk in add_disks:
            if factory.encrypted and factory.encrypt_members:
                luks_format = factory.member_format
                member_format = "luks"
            else:
                member_format = factory.member_format

            try:
                member = self.newPartition(parents=[disk], grow=True,
                                           size=base_size,
                                           fmt_type=member_format)
            except StorageError as e:
                log.error("failed to create new member partition: %s" % e)
                continue

            self.createDevice(member)
            if factory.encrypted and factory.encrypt_members:
                fmt = getFormat(luks_format)
                member = LUKSDevice("luks-%s" % member.name,
                                    parents=[member], format=fmt)
                self.createDevice(member)

            members.append(member)
            new_members.append(member)
            if container:
                container.addMember(member)

        if container:
            log.debug("using container %s with %d devices" % (container.name,
                                len(self.devicetree.getChildren(container))))
            container_size = factory.container_size_func(container, device)
            log.debug("raw container size reported as %d" % container_size)

        log.debug("adding a %s with size %d" % (factory.set_class.__name__,
                                                container_size))
        size_set = factory.set_class(members, container_size)
        self.size_sets.append(size_set)
        for member in members[:]:
            if isinstance(member, LUKSDevice):
                member = member.slave

            member.req_max_size = size_set.size

        try:
            self.allocatePartitions()
        except PartitioningError as e:
            # try to clean up by destroying all newly added members before re-
            # raising the exception
            self.__cleanUpMemberDevices(new_members, container=container)
            raise

        return members

    def allocatePartitions(self):
        """ Allocate all requested partitions. """
        try:
            doPartitioning(self)
        except StorageError as e:
            log.error("failed to allocate partitions: %s" % e)
            raise

    def getDeviceFactory(self, device_type, size, **kwargs):
        """ Return a suitable DeviceFactory instance for device_type. """
        disks = kwargs.get("disks", [])
        raid_level = kwargs.get("raid_level")
        encrypted = kwargs.get("encrypted", False)

        class_table = {DEVICE_TYPE_LVM: LVMFactory,
                       DEVICE_TYPE_BTRFS: BTRFSFactory,
                       DEVICE_TYPE_PARTITION: PartitionFactory,
                       DEVICE_TYPE_MD: MDFactory,
                       DEVICE_TYPE_DISK: DiskFactory}

        factory_class = class_table[device_type]
        log.debug("instantiating %s: %r, %s, %s, %s" % (factory_class,
                    self, size, [d.name for d in disks], raid_level))
        return factory_class(self, size, disks, raid_level, encrypted)

    def getContainer(self, factory, device=None, name=None, existing=False):
        # XXX would it be useful to implement this as a series of fallbacks
        #     instead of mutually exclusive branches?
        container = None
        if name:
            container = self.devicetree.getDeviceByName(name)
            if container and container not in factory.container_list:
                log.debug("specified container name %s is wrong type (%s)"
                            % (name, container.type))
                container = None
        elif device:
            if hasattr(device, "vg"):
                container = device.vg
            elif hasattr(device, "volume"):
                container = device.volume
        else:
            containers = [c for c in factory.container_list if not c.exists]
            if containers:
                container = containers[0]

        if container is None and existing:
            containers = [c for c in factory.container_list if c.exists]
            if containers:
                containers.sort(key=lambda c: getattr(c, "freeSpace", c.size),
                                reverse=True)
                container = containers[0]

        return container

    def __cleanUpMemberDevices(self, members, container=None):
        for member in members:
            if container:
                container.removeMember(member)

            if isinstance(member, LUKSDevice):
                self.destroyDevice(member)
                member = member.slave

            if not member.isDisk:
                self.destroyDevice(member)

    def newDevice(self, device_type, size, **kwargs):
        """ Schedule creation of a device based on a top-down specification.

            Arguments:

                device_type         an AUTOPART_TYPE constant (lvm|btrfs|plain)
                size                device's requested size

            Keyword arguments:

                mountpoint          the device's mountpoint
                fstype              the device's filesystem type, or swap
                label               filesystem label
                disks               the set of disks we can allocate from
                encrypted           boolean

                raid_level          (btrfs/md/lvm only) RAID level (string)

                name                name for new device
                container_name      name of requested container

                device              an already-defined but non-existent device
                                    to adjust instead of creating a new device


            Error handling:

                If device is None, meaning we're creating a device, the error
                handling aims to remove all evidence of the attempt to create a
                new device by removing unused container devices, reverting the
                size of container devices that contain other devices, &c.

                If the device is not None, meaning we're adjusting the size of
                a defined device, the error handling aims to revert the device
                and any container to it previous size.

                In either case, we re-raise the exception so the caller knows
                there was a failure. If we failed to clean up as described above
                we raise ErrorRecoveryFailure to alert the caller that things
                will likely be in an inconsistent state.
        """
        log_method_call(self, device_type, size, **kwargs)
        mountpoint = kwargs.get("mountpoint")
        fstype = kwargs.get("fstype")
        label = kwargs.get("label")
        disks = kwargs.get("disks")
        encrypted = kwargs.get("encrypted", self.data.autopart.encrypted)

        name = kwargs.get("name")
        container_name = kwargs.get("container_name")

        device = kwargs.get("device")

        # md, btrfs
        raid_level = kwargs.get("raid_level")

        # we can't do anything with existing devices
        if device and device.exists:
            log.info("newDevice refusing to change device %s" % device)
            return

        if not fstype:
            fstype = self.getFSType(mountpoint=mountpoint)
            if fstype == "swap":
                mountpoint = None

        if fstype == "swap" and device_type == DEVICE_TYPE_BTRFS:
            device_type = DEVICE_TYPE_PARTITION

        fmt_args = {}
        if label:
            fmt_args["label"] = label

        factory = self.getDeviceFactory(device_type, size, **kwargs)

        if not factory.disks:
            raise StorageError("no disks specified for new device")

        self.size_sets = [] # clear this since there are no growable reqs now

        container = self.getContainer(factory, device=device,
                                      name=container_name)

        # TODO: striping, mirroring, &c
        # TODO: non-partition members (pv-on-md)

        # setContainerMembers can modify these, so save them now
        old_size = None
        old_disks = []
        if device:
            old_size = device.size
            old_disks = device.disks[:]

        members = []
        if device and device.type == "mdarray":
            members = device.parents[:]

        try:
            parents = self.setContainerMembers(container, factory,
                                               members=members, device=device)
        except PartitioningError as e:
            # If this is a new device, just clean up and get out.
            if device:
                # If this is a defined device, try to clean up by reallocating
                # members as before and then get out.
                factory.disks = device.disks
                factory.size = device.size  # this should work

                if members:
                    # If this is an md array we have to reset its member set
                    # here.
                    # If there is a container device, its member set was reset
                    # in the exception handler in setContainerMembers.
                    device.parents = members

                try:
                    self.setContainerMembers(container, factory,
                                             members=members,
                                             device=device)
                except StorageError as e:
                    log.error("failed to revert device size: %s" % e)
                    raise ErrorRecoveryFailure("failed to revert container")

            raise

        # set up container
        if not container and factory.new_container_attr:
            if not parents:
                raise StorageError("not enough free space on disks")

            log.debug("creating new container")
            if container_name:
                kwa = {"name": container_name}
            else:
                kwa = {}
            try:
                container = factory.new_container(parents=parents, **kwa)
            except StorageError as e:
                log.error("failed to create new device: %s" % e)
                # Clean up by destroying the newly created member devices.
                self.__cleanUpMemberDevices(parents)
                raise

            self.createDevice(container)
        elif container and not container.exists and \
             hasattr(container, "dataLevel"):
            container.dataLevel = factory.raid_level

        if container:
            parents = [container]
            log.debug("%r" % container)

        # this will set the device's size if a device is passed in
        size = factory.set_device_size(container, device=device)
        if device:
            # We are adjusting a defined device: size, disk set, encryption,
            # raid level, fstype. The StorageDevice instance exists, but the
            # underlying device does not.
            # TODO: handle toggling of encryption for leaf device
            e = None
            try:
                factory.post_create()
            except StorageError as e:
                log.error("device post-create method failed: %s" % e)
            else:
                if device.size <= device.format.minSize:
                    e = StorageError("failed to adjust device -- not enough free space in specified disks?")

            if e:
                # Clean up by reverting the device to its previous size.
                factory.size = old_size
                factory.disks = old_disks
                try:
                    self.setContainerMembers(container, factory,
                                             members=members, device=device)
                except StorageError as e:
                    # yes, we're replacing e here.
                    log.error("failed to revert device size: %s" % e)
                    raise ErrorRecoveryFailure("failed to revert device size")

                factory.set_device_size(container, device=device)
                try:
                    factory.post_create()
                except StorageError as e:
                    # yes, we're replacing e here.
                    log.error("failed to revert device size: %s" % e)
                    raise ErrorRecoveryFailure("failed to revert device size")

                raise(e)
        elif factory.new_device_attr:
            log.debug("creating new device")
            if factory.encrypted and factory.encrypt_leaves:
                luks_fmt_type = fstype
                luks_fmt_args = fmt_args
                luks_mountpoint = mountpoint
                fstype = "luks"
                mountpoint = None
                fmt_args = {}

            def _container_post_error():
                # Clean up. If there is a container and it has other devices,
                # try to revert it. If there is a container and it has no other
                # devices, remove it. If there is not a container, remove all of
                # the parents.
                if container:
                    if container.kids:
                        factory.size = 0
                        factory.disks = container.disks
                        try:
                            self.setContainerMembers(container, factory)
                        except StorageError as e:
                            log.error("failed to revert container: %s" % e)
                            raise ErrorRecoveryFailure("failed to revert container")
                    else:
                        self.destroyDevice(container)
                        self.__cleanUpMemberDevices(container.parents)
                else:
                    self.__cleanUpMemberDevices(parents)

            if name:
                kwa = {"name": name}
            else:
                kwa = {}

            try:
                device = factory.new_device(parents=parents,
                                            size=size,
                                            fmt_type=fstype,
                                            mountpoint=mountpoint,
                                            fmt_args=fmt_args,
                                            **kwa)
            except (StorageError, ValueError) as e:
                log.error("device instance creation failed: %s" % e)
                _container_post_error()
                raise

            self.createDevice(device)
            e = None
            try:
                factory.post_create()
            except StorageError as e:
                log.error("device post-create method failed: %s" % e)
            else:
                if not device.size:
                    e = StorageError("failed to create device")

            if e:
                self.destroyDevice(device)
                _container_post_error()
                raise StorageError(e)

            if factory.encrypted and factory.encrypt_leaves:
                fmt = getFormat(luks_fmt_type,
                                mountpoint=luks_mountpoint,
                                **luks_fmt_args)
                luks_device = LUKSDevice("luks-" + device.name,
                                         parents=[device], format=fmt)
                self.createDevice(luks_device)

    def copy(self):
        new = copy.deepcopy(self)
        # go through and re-get partedPartitions from the disks since they
        # don't get deep-copied
        for partition in new.partitions:
            if not partition._partedPartition:
                continue

            # don't ask me why, but we have to update the refs in req_disks
            req_disks = []
            for disk in partition.req_disks:
                req_disks.append(new.devicetree.getDeviceByID(disk.id))

            partition.req_disks = req_disks

            p = partition.disk.format.partedDisk.getPartitionByPath(partition.path)
            partition.partedPartition = p

        return new


def mountExistingSystem(fsset, rootDevice,
                        allowDirty=None, dirtyCB=None,
                        readOnly=None):
    """ Mount filesystems specified in rootDevice's /etc/fstab file. """
    rootPath = ROOT_PATH
    if dirtyCB is None:
        dirtyCB = lambda l: False

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
    for device in fsset.mountpoints.values():
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

    if dirtyDevs and (not allowDirty or dirtyCB(dirtyDevs)):
        raise DirtyFSError("\n".join(dirtyDevs))

    fsset.mountFilesystems(rootPath=ROOT_PATH, readOnly=readOnly, skipRoot=True)


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
    def __init__(self, devicetree):
        self.devicetree = devicetree
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
                               exists=True,
                               format=getFormat(fstype,
                                                exists=True,
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

        if device is None:
            log.error("failed to resolve %s (%s) from fstab" % (devspec,
                                                                fstype))
            raise UnrecognizedFSTabEntryError()

        device.setup()
        fmt = getFormat(fstype, device=device.path, exists=True)
        if fstype != "auto" and None in (device.format.type, fmt.type):
            log.info("Unrecognized filesystem type for %s (%s)"
                     % (device.name, fstype))
            device.teardown()
            raise UnrecognizedFSTabEntryError()

        # make sure, if we're using a device from the tree, that
        # the device's format we found matches what's in the fstab
        ftype = getattr(fmt, "mountType", fmt.type)
        dtype = getattr(device.format, "mountType", device.format.type)
        if fstype != "auto" and ftype != dtype:
            log.info("fstab says %s at %s is %s" % (dtype, mountpoint, ftype))
            if fmt.testMount():
                # XXX we should probably disallow migration for this fs
                device.format = fmt
            else:
                device.teardown()
                raise FSTabTypeMismatchError("%s: detected as %s, fstab says %s"
                                             % (mountpoint, dtype, ftype))
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
            chroot = ROOT_PATH

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

                if not device:
                    continue

                if device not in self.devicetree.devices:
                    try:
                        self.devicetree._addDevice(device)
                    except ValueError:
                        # just write duplicates back out post-install
                        self.preserveLines.append(line)

    def turnOnSwap(self, rootPath="", upgrading=None):
        """ Activate the system's swap space. """
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
                except StorageError as e:
                    if errorHandler.cb(e, device) == ERROR_RAISE:
                        raise
                else:
                    break

    def mountFilesystems(self, rootPath="", readOnly=None,
                         skipRoot=False, raiseErrors=None):
        """ Mount the system's filesystems. """
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
            except Exception as e:
                if errorHandler.cb(e, device) == ERROR_RAISE:
                    raise
                else:
                    continue

            if readOnly:
                options = "%s,%s" % (options, readOnly)

            try:
                device.format.setup(options=options,
                                    chroot=rootPath)
            except Exception as e:
                log.error("error mounting %s on %s: %s"
                          % (device.path, device.format.mountpoint, e))
                if errorHandler.cb(e, device) == ERROR_RAISE:
                    raise

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

    def createSwapFile(self, device, size):
        """ Create and activate a swap file under ROOT_PATH. """
        filename = "/SWAP"
        count = 0
        basedir = os.path.normpath("%s/%s" % (ROOT_PATH,
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

    def mkDevRoot(self):
        root = self.rootDevice
        dev = "%s/%s" % (ROOT_PATH, root.path)
        if not os.path.exists("%s/dev/root" %(ROOT_PATH,)) and os.path.exists(dev):
            rdev = os.stat(dev).st_rdev
            os.mknod("%s/dev/root" % (ROOT_PATH,), stat.S_IFBLK | 0600, rdev)

    @property
    def swapDevices(self):
        swaps = []
        for device in self.devices:
            if device.format.type == "swap":
                swaps.append(device)
        return swaps

    @property
    def rootDevice(self):
        for path in ["/", ROOT_PATH]:
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

    def write(self):
        """ write out all config files based on the set of filesystems """
        # /etc/fstab
        fstab_path = os.path.normpath("%s/etc/fstab" % ROOT_PATH)
        fstab = self.fstab()
        open(fstab_path, "w").write(fstab)

        # /etc/crypttab
        crypttab_path = os.path.normpath("%s/etc/crypttab" % ROOT_PATH)
        crypttab = self.crypttab()
        origmask = os.umask(0077)
        open(crypttab_path, "w").write(crypttab)
        os.umask(origmask)

        # /etc/mdadm.conf
        mdadm_path = os.path.normpath("%s/etc/mdadm.conf" % ROOT_PATH)
        mdadm_conf = self.mdadmConf()
        if mdadm_conf:
            open(mdadm_path, "w").write(mdadm_conf)

        # /etc/multipath.conf
        multipath_conf = self.multipathConf()
        if multipath_conf:
            multipath_path = os.path.normpath("%s/etc/multipath.conf" %
                                              ROOT_PATH)
            conf_contents = multipath_conf.write(self.devicetree.mpathFriendlyNames)
            f = open(multipath_path, "w")
            f.write(conf_contents)
            f.close()
        else:
            log.info("not writing out mpath configuration")
        iutil.copy_to_sysimage("/etc/multipath/wwids")
        if self.devicetree.mpathFriendlyNames:
            iutil.copy_to_sysimage("/etc/multipath/bindings")

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
            if device.encrypted:
                options += ",x-systemd.device-timeout=0"
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


def getReleaseString():
    relName = None
    relVer = None

    try:
        relArch = iutil.execWithCapture("arch", [], root=ROOT_PATH).strip()
    except:
        relArch = None

    filename = "%s/etc/redhat-release" % ROOT_PATH
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

def findExistingInstallations(devicetree):
    if not os.path.exists(ROOT_PATH):
        iutil.mkdirChain(ROOT_PATH)

    roots = []
    for device in devicetree.leaves:
        if not device.format.linuxNative or not device.format.mountable or \
           not device.controllable:
            continue

        try:
            device.setup()
        except Exception as e:
            log.warning("setup of %s failed: %s" % (device.name, e))
            continue

        options = device.format.options + ",ro"
        try:
            device.format.mount(options=options, mountpoint=ROOT_PATH)
        except Exception as e:
            log.warning("mount of %s as %s failed: %s" % (device.name,
                                                          device.format.type,
                                                          e))
            device.teardown()
            continue

        if not os.access(ROOT_PATH + "/etc/fstab", os.R_OK):
            device.teardown(recursive=True)
            continue

        try:
            (arch, product, version) = getReleaseString()
        except ValueError:
            name = _("Linux on %s") % device.name
        else:
            # I'd like to make this finer grained, but it'd be very difficult
            # to translate.
            if not product or not version or not arch:
                name = _("Unknown Linux")
            else:
                name = _("%(product)s Linux %(version)s for %(arch)s") % \
                        {"product": product, "version": version, "arch": arch}

        (mounts, swaps) = parseFSTab(devicetree, chroot=ROOT_PATH)
        device.teardown()
        if not mounts and not swaps:
            # empty /etc/fstab. weird, but I've seen it happen.
            continue
        roots.append(Root(mounts=mounts, swaps=swaps, name=name))

    return roots

class Root(object):
    def __init__(self, mounts=None, swaps=None, name=None):
        # mountpoint key, StorageDevice value
        if not mounts:
            self.mounts = {}
        else:
            self.mounts = mounts

        # StorageDevice
        if not swaps:
            self.swaps = []
        else:
            self.swaps = swaps

        self.name = name    # eg: "Fedora Linux 16 for x86_64", "Linux on sda2"

        if not self.name and "/" in self.mounts:
            self.name = self.mounts["/"].format.uuid

    @property
    def device(self):
        return self.mounts.get("/")

def parseFSTab(devicetree, chroot=None):
    """ parse /etc/fstab and return a tuple of a mount dict and swap list """
    if not chroot or not os.path.isdir(chroot):
        chroot = ROOT_PATH

    mounts = {}
    swaps = []
    path = "%s/etc/fstab" % chroot
    if not os.access(path, os.R_OK):
        # XXX should we raise an exception instead?
        log.info("cannot open %s for read" % path)
        return (mounts, swaps)

    blkidTab = BlkidTab(chroot=chroot)
    try:
        blkidTab.parse()
        log.debug("blkid.tab devs: %s" % blkidTab.devices.keys())
    except Exception as e:
        log.info("error parsing blkid.tab: %s" % e)
        blkidTab = None

    cryptTab = CryptTab(devicetree, blkidTab=blkidTab, chroot=chroot)
    try:
        cryptTab.parse(chroot=chroot)
        log.debug("crypttab maps: %s" % cryptTab.mappings.keys())
    except Exception as e:
        log.info("error parsing crypttab: %s" % e)
        cryptTab = None

    with open(path) as f:
        log.debug("parsing %s" % path)
        for line in f.readlines():
            # strip off comments
            (line, pound, comment) = line.partition("#")
            fields = line.split(None, 4)

            if len(fields) < 5:
                continue

            (devspec, mountpoint, fstype, options, rest) = fields

            # find device in the tree
            device = devicetree.resolveDevice(devspec,
                                              cryptTab=cryptTab,
                                              blkidTab=blkidTab,
                                              options=options)

            if device is None:
                continue

            if fstype != "swap":
                mounts[mountpoint] = device
            else:
                swaps.append(device)

    return (mounts, swaps)


class DeviceFactory(object):
    type_desc = None
    member_format = None        # format type for member devices
    new_container_attr = None   # name of Storage method to create a container
    new_device_attr = None      # name of Storage method to create a device
    container_list_attr = None  # name of Storage attribute to list containers
    encrypt_members = False
    encrypt_leaves = True

    def __init__(self, storage, size, disks, raid_level, encrypted):
        self.storage = storage          # the Storage instance
        self.size = size                # the requested size for this device
        self.disks = disks              # the set of disks to allocate from
        self.raid_level = raid_level
        self.encrypted = encrypted

        # this is a list of member devices, used to short-circuit the logic in
        # setContainerMembers for case of a partition
        self.member_list = None

        # choose a size set class for member partition allocation
        if raid_level is not None and raid_level.startswith("raid"):
            self.set_class = SameSizeSet
        else:
            self.set_class = TotalSizeSet

    @property
    def container_list(self):
        """ A list of containers of the type used by this device. """
        if not self.container_list_attr:
            return []

        return getattr(self.storage, self.container_list_attr)

    def new_container(self, *args, **kwargs):
        """ Return the newly created container for this device. """
        return getattr(self.storage, self.new_container_attr)(*args, **kwargs)

    def new_device(self, *args, **kwargs):
        """ Return the newly created device. """
        return getattr(self.storage, self.new_device_attr)(*args, **kwargs)

    def post_create(self):
        """ Perform actions required after device creation. """
        pass

    def container_size_func(self, container, device=None):
        """ Return the total space needed for the specified container. """
        size = container.size
        size += self.device_size
        if device:
            size -= device.size

        return size

    @property
    def device_size(self):
        """ The total disk space required for this device. """
        return self.size

    def set_device_size(self, container, device=None):
        return self.size

class DiskFactory(DeviceFactory):
    type_desc = "disk"
    # this is to protect against changes to these settings in the base class
    encrypt_members = False
    encrypt_leaves = True

class PartitionFactory(DeviceFactory):
    type_desc = "partition"
    new_device_attr = "newPartition"
    default_size = 1

    def __init__(self, storage, size, disks, raid_level, encrypted):
        super(PartitionFactory, self).__init__(storage, size, disks, raid_level,
                                               encrypted)
        self.member_list = self.disks

    def new_device(self, *args, **kwargs):
        grow = True
        max_size = kwargs.pop("size")
        kwargs["size"] = 1

        device = self.storage.newPartition(*args,
                                           grow=grow, maxsize=max_size,
                                           **kwargs)
        return device

    def post_create(self):
        self.storage.allocatePartitions()

    def set_device_size(self, container, device=None):
        size = self.size
        if device:
            if size != device.size:
                log.info("adjusting device size from %.2f to %.2f"
                                % (device.size, size))

            base_size = max(PartitionFactory.default_size,
                            device.format.minSize)
            size = max(base_size, size)
            device.req_base_size = base_size
            device.req_size = base_size
            device.req_max_size = size
            device.req_grow = size > base_size

            # this probably belongs somewhere else but this is our chance to
            # update the disk set
            device.req_disks = self.disks[:]

        return size

class BTRFSFactory(DeviceFactory):
    type_desc = "btrfs"
    member_format = "btrfs"
    new_container_attr = "newBTRFS"
    new_device_attr = "newBTRFSSubVolume"
    container_list_attr = "btrfsVolumes"
    encrypt_members = True
    encrypt_leaves = False

    def __init__(self, storage, size, disks, raid_level, encrypted):
        super(BTRFSFactory, self).__init__(storage, size, disks, raid_level,
                                           encrypted)
        self.raid_level = raid_level or "single"

    def new_container(self, *args, **kwargs):
        """ Return the newly created container for this device. """
        kwargs["dataLevel"] = self.raid_level
        return getattr(self.storage, self.new_container_attr)(*args, **kwargs)

    def container_size_func(self, container, device=None):
        """ Return the total space needed for the specified container. """
        if container.exists:
            container_size = container.size
        else:
            container_size = sum([s.req_size for s in container.subvolumes])

        if device:
            size = self.device_size
        else:
            size = container_size + self.device_size

        return size

    @property
    def device_size(self):
        # until we get/need something better
        if self.raid_level in ("single", "raid0"):
            return self.size
        elif self.raid_level in ("raid1", "raid10"):
            return self.size * len(self.disks)

    def new_device(self, *args, **kwargs):
        kwargs["dataLevel"] = self.raid_level
        kwargs["metaDataLevel"] = self.raid_level
        return super(BTRFSFactory, self).new_device(*args, **kwargs)

class LVMFactory(DeviceFactory):
    type_desc = "lvm"
    member_format = "lvmpv"
    new_container_attr = "newVG"
    new_device_attr = "newLV"
    container_list_attr = "vgs"
    encrypt_members = True
    encrypt_leaves = False

    @property
    def device_size(self):
        size_func_kwargs = {}
        if self.raid_level in ("raid1", "raid10"):
            size_func_kwargs["mirrored"] = True
        if self.raid_level in ("raid0", "raid10"):
            size_func_kwargs["striped"] = True
        return get_pv_space(self.size, len(self.disks), **size_func_kwargs)

    def container_size_func(self, container, device=None):
        size = sum([p.size for p in container.parents])
        size -= container.freeSpace
        size += self.device_size
        if device:
            size -= get_pv_space(device.size, len(container.parents))

        return size

    def set_device_size(self, container, device=None):
        size = self.size
        free = container.freeSpace
        if device:
            free += device.size

        if free < size:
            log.info("adjusting device size from %.2f to %.2f so it fits "
                     "in container" % (size, free))
            size = free

        if device:
            if size != device.size:
                log.info("adjusting device size from %.2f to %.2f"
                                % (device.size, size))

            device.size = size

        return size

class MDFactory(DeviceFactory):
    type_desc = "md"
    member_format = "mdmember"
    new_container_attr = None
    new_device_attr = "newMDArray"

    @property
    def container_list(self):
        return []

    @property
    def device_size(self):
        return get_member_space(self.size, len(self.disks),
                                level=self.raid_level)

    def container_size_func(self, container, device=None):
        return get_member_space(self.size, len(container.parents),
                                level=self.raid_level)

    def new_device(self, *args, **kwargs):
        kwargs["level"] = self.raid_level
        kwargs["totalDevices"] = len(kwargs.get("parents"))
        kwargs["memberDevices"] = len(kwargs.get("parents"))
        return super(MDFactory, self).new_device(*args, **kwargs)
