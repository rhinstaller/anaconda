#
# Copyright (C) 2015  Red Hat, Inc.
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
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

"""
This module provides functions related to autopartitioning that are installer
specific.

"""

import parted
from decimal import Decimal

from blivet import util
from blivet.size import Size
from blivet.devices.partition import PartitionDevice
from blivet.devices.luks import LUKSDevice
from blivet.errors import NoDisksError, NotEnoughFreeSpaceError
from blivet.formats import getFormat
from blivet.partitioning import getFreeRegions

from pyanaconda.i18n import _
from pykickstart.constants import AUTOPART_TYPE_BTRFS, AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP, AUTOPART_TYPE_PLAIN

import logging
log = logging.getLogger("anaconda")

# maximum ratio of swap size to disk size (10 %)
MAX_SWAP_DISK_RATIO = Decimal('0.1')

def swap_suggestion(quiet=False, hibernation=False, disk_space=None):
    """
    Suggest the size of the swap partition that will be created.

    :param quiet: whether to log size information or not
    :type quiet: bool
    :param hibernation: calculate swap size big enough for hibernation
    :type hibernation: bool
    :param disk_space: how much disk space is available
    :type disk_space: :class:`~.size.Size`
    :return: calculated swap size

    """

    mem = util.total_memory()
    mem = ((mem / 16) + 1) * 16
    if not quiet:
        log.info("Detected %s of memory", mem)

    sixtyfour_GiB = Size("64 GiB")

    # the succeeding if-statement implements the following formula for
    # suggested swap size.
    #
    # swap(mem) = 2 * mem, if mem < 2 GiB
    #           = mem,     if 2 GiB <= mem < 8 GiB
    #           = mem / 2, if 8 GIB <= mem < 64 GiB
    #           = 4 GiB,   if mem >= 64 GiB
    if mem < Size("2 GiB"):
        swap = 2 * mem

    elif mem < Size("8 GiB"):
        swap = mem

    elif mem < sixtyfour_GiB:
        swap = mem / 2

    else:
        swap = Size("4 GiB")

    if hibernation:
        if mem <= sixtyfour_GiB:
            swap = mem + swap
        else:
            log.info("Ignoring --hibernation option on systems with %s of RAM or more", sixtyfour_GiB)

    if disk_space is not None and not hibernation:
        max_swap = disk_space * MAX_SWAP_DISK_RATIO
        if swap > max_swap:
            log.info("Suggested swap size (%(swap)s) exceeds %(percent)d %% of "
                     "disk space, using %(percent)d %% of disk space (%(size)s) "
                     "instead.", {"percent": MAX_SWAP_DISK_RATIO*100,
                                  "swap": swap,
                                  "size": max_swap})
            swap = max_swap

    if not quiet:
        log.info("Swap attempt of %s", swap)

    return swap

def _getCandidateDisks(storage):
    """ Return a list of disks to be used for autopart.

        Disks must be partitioned and have a single free region large enough
        for a default-sized (500MiB) partition. They must also be in
        :attr:`StorageDiscoveryConfig.clearPartDisks` if it is non-empty.

        :param storage: a Blivet instance
        :type storage: :class:`~.Blivet`
        :returns: a list of partitioned disks with at least 500MiB of free space
        :rtype: list of :class:`~.devices.StorageDevice`
    """
    disks = []
    for disk in storage.partitioned:
        if storage.config.clearPartDisks and \
           (disk.name not in storage.config.clearPartDisks):
            continue

        part = disk.format.firstPartition
        while part:
            if not part.type & parted.PARTITION_FREESPACE:
                part = part.nextPartition()
                continue

            if Size(part.getLength(unit="B")) > PartitionDevice.defaultSize:
                disks.append(disk)
                break

            part = part.nextPartition()

    return disks

def _scheduleImplicitPartitions(storage, disks, min_luks_entropy=0):
    """ Schedule creation of a lvm/btrfs member partitions for autopart.

        We create one such partition on each disk. They are not allocated until
        later (in :func:`doPartitioning`).

        :param storage: a :class:`~.Blivet` instance
        :type storage: :class:`~.Blivet`
        :param disks: list of partitioned disks with free space
        :type disks: list of :class:`~.devices.StorageDevice`
        :param min_luks_entropy: minimum entropy in bits required for
                                 luks format creation
        :type min_luks_entropy: int
        :returns: list of newly created (unallocated) partitions
        :rtype: list of :class:`~.devices.PartitionDevice`
    """
    # create a separate pv or btrfs partition for each disk with free space
    devs = []

    # only schedule the partitions if either lvm or btrfs autopart was chosen
    if storage.autoPartType == AUTOPART_TYPE_PLAIN:
        return devs

    for disk in disks:
        if storage.encryptedAutoPart:
            fmt_type = "luks"
            fmt_args = {"passphrase": storage.encryptionPassphrase,
                        "cipher": storage.encryptionCipher,
                        "escrow_cert": storage.autoPartEscrowCert,
                        "add_backup_passphrase": storage.autoPartAddBackupPassphrase,
                        "min_luks_entropy": min_luks_entropy}
        else:
            if storage.autoPartType in (AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP):
                fmt_type = "lvmpv"
            else:
                fmt_type = "btrfs"
            fmt_args = {}
        part = storage.newPartition(fmt_type=fmt_type,
                                                fmt_args=fmt_args,
                                                grow=True,
                                                parents=[disk])
        storage.createDevice(part)
        devs.append(part)

    return devs

def _schedulePartitions(storage, disks, implicit_devices, min_luks_entropy=0):
    """ Schedule creation of autopart partitions.

        This only schedules the requests for actual partitions.

        :param storage: a :class:`~.Blivet` instance
        :type storage: :class:`~.Blivet`
        :param disks: list of partitioned disks with free space
        :type disks: list of :class:`~.devices.StorageDevice`
        :param min_luks_entropy: minimum entropy in bits required for
                                 luks format creation
        :type min_luks_entropy: int
        :returns: None
        :rtype: None
    """
    # basis for requests with requiredSpace is the sum of the sizes of the
    # two largest free regions
    all_free = (Size(reg.getLength(unit="B")) for reg in getFreeRegions(disks))
    all_free = sorted(all_free, reverse=True)
    if not all_free:
        # this should never happen since we've already filtered the disks
        # to those with at least 500MiB free
        log.error("no free space on disks %s", [d.name for d in disks])
        return

    free = all_free[0]
    if len(all_free) > 1:
        free += all_free[1]

    # The boot disk must be set at this point. See if any platform-specific
    # stage1 device we might allocate already exists on the boot disk.
    stage1_device = None
    for device in storage.devices:
        if storage.bootloader.stage1_disk not in device.disks:
            continue

        if storage.bootloader.is_valid_stage1_device(device, early=True):
            stage1_device = device
            break

    #
    # First pass is for partitions only. We'll do LVs later.
    #
    for request in storage.autoPartitionRequests:
        if ((request.lv and
             storage.autoPartType in (AUTOPART_TYPE_LVM,
                                      AUTOPART_TYPE_LVM_THINP)) or
            (request.btr and storage.autoPartType == AUTOPART_TYPE_BTRFS)):
            continue

        if request.requiredSpace and request.requiredSpace > free:
            continue

        elif request.fstype in ("prepboot", "efi", "macefi", "hfs+") and \
             (storage.bootloader.skip_bootloader or stage1_device):
            # there should never be a need for more than one of these
            # partitions, so skip them.
            log.info("skipping unneeded stage1 %s request", request.fstype)
            log.debug("%s", request)

            if request.fstype in ["efi", "macefi"] and stage1_device:
                # Set the mountpoint for the existing EFI boot partition
                stage1_device.format.mountpoint = "/boot/efi"

            log.debug("%s", stage1_device)
            continue
        elif request.fstype == "biosboot":
            is_gpt = (stage1_device and
                      getattr(stage1_device.format, "labelType", None) == "gpt")
            has_bios_boot = (stage1_device and
                             any([p.format.type == "biosboot"
                                    for p in storage.partitions
                                        if p.disk == stage1_device]))
            if (storage.bootloader.skip_bootloader or
                not (stage1_device and stage1_device.isDisk and
                    is_gpt and not has_bios_boot)):
                # there should never be a need for more than one of these
                # partitions, so skip them.
                log.info("skipping unneeded stage1 %s request", request.fstype)
                log.debug("%s", request)
                log.debug("%s", stage1_device)
                continue

        if request.size > all_free[0]:
            # no big enough free space for the requested partition
            raise NotEnoughFreeSpaceError(_("No big enough free space on disks for "
                                            "automatic partitioning"))

        if request.encrypted and storage.encryptedAutoPart:
            fmt_type = "luks"
            fmt_args = {"passphrase": storage.encryptionPassphrase,
                        "cipher": storage.encryptionCipher,
                        "escrow_cert": storage.autoPartEscrowCert,
                        "add_backup_passphrase": storage.autoPartAddBackupPassphrase,
                        "min_luks_entropy": min_luks_entropy}
        else:
            fmt_type = request.fstype
            fmt_args = {}

        dev = storage.newPartition(fmt_type=fmt_type,
                                            fmt_args=fmt_args,
                                            size=request.size,
                                            grow=request.grow,
                                            maxsize=request.maxSize,
                                            mountpoint=request.mountpoint,
                                            parents=disks,
                                            weight=request.weight)

        # schedule the device for creation
        storage.createDevice(dev)

        if request.encrypted and storage.encryptedAutoPart:
            luks_fmt = getFormat(request.fstype,
                                 device=dev.path,
                                 mountpoint=request.mountpoint)
            luks_dev = LUKSDevice("luks-%s" % dev.name,
                                  fmt=luks_fmt,
                                  size=dev.size,
                                  parents=dev)
            storage.createDevice(luks_dev)

        if storage.autoPartType in (AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP,
                                    AUTOPART_TYPE_BTRFS):
            # doing LVM/BTRFS -- make sure the newly created partition fits in some
            # free space together with one of the implicitly requested partitions
            smallest_implicit = sorted(implicit_devices, key=lambda d: d.size)[0]
            if (request.size + smallest_implicit.size) > all_free[0]:
                # not enough space to allocate the smallest implicit partition
                # and the request, make the implicit partition smaller with
                # fixed size in order to make space for the request
                new_size = all_free[0] - request.size

                # subtract the size from the biggest free region and reorder the
                # list
                all_free[0] -= request.size
                all_free.sort(reverse=True)

                if new_size > Size(0):
                    smallest_implicit.size = new_size
                else:
                    implicit_devices.remove(smallest_implicit)
                    storage.destroyDevice(smallest_implicit)

    return implicit_devices

def _scheduleVolumes(storage, devs):
    """ Schedule creation of autopart lvm/btrfs volumes.

        Schedules encryption of member devices if requested, schedules creation
        of the container (:class:`~.devices.LVMVolumeGroupDevice` or
        :class:`~.devices.BTRFSVolumeDevice`) then schedules creation of the
        autopart volume requests.

        :param storage: a :class:`~.Blivet` instance
        :type storage: :class:`~.Blivet`
        :param devs: list of member partitions
        :type devs: list of :class:`~.devices.PartitionDevice`
        :returns: None
        :rtype: None

        If an appropriate bootloader stage1 device exists on the boot drive, any
        autopart request to create another one will be skipped/discarded.
    """
    if not devs:
        return

    if storage.autoPartType in (AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP):
        new_container = storage.newVG
        new_volume = storage.newLV
        format_name = "lvmpv"
    else:
        new_container = storage.newBTRFS
        new_volume = storage.newBTRFS
        format_name = "btrfs"

    if storage.encryptedAutoPart:
        pvs = []
        for dev in devs:
            pv = LUKSDevice("luks-%s" % dev.name,
                            fmt=getFormat(format_name, device=dev.path),
                            size=dev.size,
                            parents=dev)
            pvs.append(pv)
            storage.createDevice(pv)
    else:
        pvs = devs

    # create a vg containing all of the autopart pvs
    container = new_container(parents=pvs)
    storage.createDevice(container)

    #
    # Convert storage.autoPartitionRequests into Device instances and
    # schedule them for creation.
    #
    # Second pass, for LVs only.
    pool = None
    for request in storage.autoPartitionRequests:
        btr = storage.autoPartType == AUTOPART_TYPE_BTRFS and request.btr
        lv = (storage.autoPartType in (AUTOPART_TYPE_LVM,
                                       AUTOPART_TYPE_LVM_THINP) and request.lv)
        thinlv = (storage.autoPartType == AUTOPART_TYPE_LVM_THINP and
                  request.lv and request.thin)
        if thinlv and pool is None:
            # create a single thin pool in the vg
            pool = storage.newLV(parents=[container], thin_pool=True, grow=True)
            storage.createDevice(pool)

        if not btr and not lv and not thinlv:
            continue

        # required space isn't relevant on btrfs
        if (lv or thinlv) and \
           request.requiredSpace and request.requiredSpace > container.size:
            continue

        if request.fstype is None:
            if btr:
                # btrfs volumes can only contain btrfs filesystems
                request.fstype = "btrfs"
            else:
                request.fstype = storage.defaultFSType

        kwargs = {"mountpoint": request.mountpoint,
                  "fmt_type": request.fstype}
        if lv or thinlv:
            if thinlv:
                parents = [pool]
            else:
                parents = [container]

            kwargs.update({"parents": parents,
                           "grow": request.grow,
                           "maxsize": request.maxSize,
                           "size": request.size,
                           "thin_volume": thinlv})
        else:
            kwargs.update({"parents": [container],
                           "size": request.size,
                           "subvol": True})

        dev = new_volume(**kwargs)

        # schedule the device for creation
        storage.createDevice(dev)

def doAutoPartition(storage, data, min_luks_entropy=0):
    """ Perform automatic partitioning.

        :param storage: a :class:`~.Blivet` instance
        :type storage: :class:`~.Blivet`
        :param data: kickstart data
        :type data: :class:`pykickstart.BaseHandler`
        :param min_luks_entropy: minimum entropy in bits required for
                                 luks format creation
        :type min_luks_entropy: int

        :attr:`Blivet.doAutoPart` controls whether this method creates the
        automatic partitioning layout. :attr:`Blivet.autoPartType` controls
        which variant of autopart used. It uses one of the pykickstart
        AUTOPART_TYPE_* constants. The set of eligible disks is defined in
        :attr:`StorageDiscoveryConfig.clearPartDisks`.

        .. note::

            Clearing of partitions is handled separately, in
            :meth:`~.Blivet.clearPartitions`.
    """
    # pylint: disable=unused-argument
    log.debug("doAutoPart: %s", storage.doAutoPart)
    log.debug("encryptedAutoPart: %s", storage.encryptedAutoPart)
    log.debug("autoPartType: %s", storage.autoPartType)
    log.debug("clearPartType: %s", storage.config.clearPartType)
    log.debug("clearPartDisks: %s", storage.config.clearPartDisks)
    log.debug("autoPartitionRequests:\n%s", "".join([str(p) for p in storage.autoPartitionRequests]))
    log.debug("storage.disks: %s", [d.name for d in storage.disks])
    log.debug("storage.partitioned: %s", [d.name for d in storage.partitioned])
    log.debug("all names: %s", [d.name for d in storage.devices])
    log.debug("boot disk: %s", getattr(storage.bootDisk, "name", None))

    disks = []
    devs = []

    if not storage.doAutoPart:
        return

    if not storage.partitioned:
        raise NoDisksError(_("No usable disks selected"))

    disks = _getCandidateDisks(storage)
    devs = _scheduleImplicitPartitions(storage, disks, min_luks_entropy)
    log.debug("candidate disks: %s", disks)
    log.debug("devs: %s", devs)

    if disks == []:
        raise NotEnoughFreeSpaceError(_("Not enough free space on disks for "
                                      "automatic partitioning"))

    devs = _schedulePartitions(storage, disks, devs, min_luks_entropy=min_luks_entropy)

    # run the autopart function to allocate and grow partitions
    doPartitioning(storage)
    _scheduleVolumes(storage, devs)

    # grow LVs
    growLVM(storage)

    storage.setUpBootLoader()

    # only newly added swaps should appear in the fstab
    new_swaps = (dev for dev in storage.swaps if not dev.format.exists)
    storage.setFstabSwaps(new_swaps)
