# partitioning.py
# Disk partitioning functions.
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

import sys
import os
from operator import add, sub, gt, lt

import parted
from pykickstart.constants import *

from pyanaconda.constants import *
from pyanaconda.errors import *

from errors import *
from deviceaction import *
from devices import PartitionDevice, LUKSDevice, devicePathToName
from formats import getFormat

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")

def _getCandidateDisks(storage):
    """ Return a list of disks with space for a default-sized partition. """
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

            if part.getSize(unit="MB") > PartitionDevice.defaultSize:
                disks.append(disk)
                break

            part = part.nextPartition()

    return disks

def _scheduleImplicitPartitions(storage, disks):
    """ Schedule creation of a lvm/btrfs partition on each disk in disks. """
    # create a separate pv or btrfs partition for each disk with free space
    devs = []

    # only schedule the partitions if either lvm or btrfs autopart was chosen
    if storage.autoPartType not in (AUTOPART_TYPE_LVM, AUTOPART_TYPE_BTRFS):
        return devs

    for disk in disks:
        if storage.encryptedAutoPart:
            fmt_type = "luks"
            fmt_args = {"passphrase": storage.encryptionPassphrase,
                        "cipher": storage.encryptionCipher,
                        "escrow_cert": storage.autoPartEscrowCert,
                        "add_backup_passphrase": storage.autoPartAddBackupPassphrase}
        else:
            if storage.autoPartType == AUTOPART_TYPE_LVM:
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

def _schedulePartitions(storage, disks):
    """ Schedule creation of autopart partitions. """
    # basis for requests with requiredSpace is the sum of the sizes of the
    # two largest free regions
    all_free = getFreeRegions(disks)
    all_free.sort(key=lambda f: f.length, reverse=True)
    if not all_free:
        # this should never happen since we've already filtered the disks
        # to those with at least 500MB free
        log.error("no free space on disks %s" % ([d.name for d in disks],))
        return

    free = all_free[0].getSize()
    if len(all_free) > 1:
        free += all_free[1].getSize()

    # The boot disk must be set at this point. See if any platform-specific
    # stage1 device we might allocate already exists on the boot disk.
    stage1_device = None
    for device in storage.devices:
        if storage.bootloader.stage1_disk not in device.disks:
            continue

        if storage.bootloader.is_valid_stage1_device(device):
            stage1_device = device
            break

    #
    # First pass is for partitions only. We'll do LVs later.
    #
    for request in storage.autoPartitionRequests:
        if (request.lv and storage.autoPartType == AUTOPART_TYPE_LVM) or \
           (request.btr and storage.autoPartType == AUTOPART_TYPE_BTRFS):
            continue

        if request.requiredSpace and request.requiredSpace > free:
            continue

        elif request.fstype in ("prepboot", "efi", "hfs+") and \
             (storage.bootloader.skip_bootloader or stage1_device):
            # there should never be a need for more than one of these
            # partitions, so skip them.
            log.info("skipping unneeded stage1 %s request" % request.fstype)
            log.debug(request)

            if request.fstype == "efi":
                # Set the mountpoint for the existing EFI boot partition
                stage1_device.format.mountpoint = "/boot/efi"

            log.debug(stage1_device)
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
                log.info("skipping unneeded stage1 %s request" % request.fstype)
                log.debug(request)
                log.debug(stage1_device)
                continue

        if request.encrypted and storage.encryptedAutoPart:
            fmt_type = "luks"
            fmt_args = {"passphrase": storage.encryptionPassphrase,
                        "cipher": storage.encryptionCipher,
                        "escrow_cert": storage.autoPartEscrowCert,
                        "add_backup_passphrase": storage.autoPartAddBackupPassphrase}
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
                                  format=luks_fmt,
                                  size=dev.size,
                                  parents=dev)
            storage.createDevice(luks_dev)

    # make sure preexisting broken lvm/raid configs get out of the way
    return

def _scheduleVolumes(storage, devs):
    """ Schedule creation of autopart lvm/btrfs volumes. """
    if not devs:
        return

    if storage.autoPartType == AUTOPART_TYPE_LVM:
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
                            format=getFormat(format_name, device=dev.path),
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
    for request in storage.autoPartitionRequests:
        btr = storage.autoPartType == AUTOPART_TYPE_BTRFS and request.btr
        lv = storage.autoPartType == AUTOPART_TYPE_LVM and request.lv

        if not btr and not lv:
            continue

        # required space isn't relevant on btrfs
        if lv and \
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
        if lv:
            kwargs.update({"parents": [container],
                           "grow": request.grow,
                           "maxsize": request.maxSize,
                           "size": request.size,
                           "singlePV": request.singlePV})
        else:
            kwargs.update({"parents": [container],
                           "size": request.size,
                           "subvol": True})

        dev = new_volume(**kwargs)

        # schedule the device for creation
        storage.createDevice(dev)

def doAutoPartition(storage, data):
    log.debug("doAutoPart: %s" % storage.doAutoPart)
    log.debug("encryptedAutoPart: %s" % storage.encryptedAutoPart)
    log.debug("autoPartType: %s" % storage.autoPartType)
    log.debug("clearPartType: %s" % storage.config.clearPartType)
    log.debug("clearPartDisks: %s" % storage.config.clearPartDisks)
    log.debug("autoPartitionRequests:\n%s" % "".join([str(p) for p in storage.autoPartitionRequests]))
    log.debug("storage.disks: %s" % [d.name for d in storage.disks])
    log.debug("storage.partitioned: %s" % [d.name for d in storage.partitioned])
    log.debug("all names: %s" % [d.name for d in storage.devices])
    log.debug("boot disk: %s" % getattr(storage.bootDisk, "name", None))

    disks = []
    devs = []

    if not storage.doAutoPart:
        return

    if not storage.partitioned:
        raise NoDisksError(_("No usable disks selected"))

    disks = _getCandidateDisks(storage)
    devs = _scheduleImplicitPartitions(storage, disks)
    log.debug("candidate disks: %s" % disks)
    log.debug("devs: %s" % devs)

    if disks == []:
        raise NotEnoughFreeSpaceError(_("Not enough free space on disks for "
                                      "automatic partitioning"))

    _schedulePartitions(storage, disks)

    # run the autopart function to allocate and grow partitions
    doPartitioning(storage)
    _scheduleVolumes(storage, devs)

    # grow LVs
    growLVM(storage)

    storage.setUpBootLoader()

    # now do a full check of the requests
    (errors, warnings) = storage.sanityCheck()
    for error in errors:
        log.error(error)
    for warning in warnings:
        log.warning(warning)
    if errors:
        raise PartitioningError("\n".join(errors))

def partitionCompare(part1, part2):
    """ More specifically defined partitions come first.

        < 1 => x < y
          0 => x == y
        > 1 => x > y
    """
    ret = 0

    if part1.req_base_weight:
        ret -= part1.req_base_weight

    if part2.req_base_weight:
        ret += part2.req_base_weight

    # more specific disk specs to the front of the list
    # req_disks being empty is equivalent to it being an infinitely long list
    if part1.req_disks and not part2.req_disks:
        ret -= 500
    elif not part1.req_disks and part2.req_disks:
        ret += 500
    else:
        ret += cmp(len(part1.req_disks), len(part2.req_disks)) * 500

    # primary-only to the front of the list
    ret -= cmp(part1.req_primary, part2.req_primary) * 200

    # fixed size requests to the front
    ret += cmp(part1.req_grow, part2.req_grow) * 100

    # larger requests go to the front of the list
    ret -= cmp(part1.req_base_size, part2.req_base_size) * 50

    # potentially larger growable requests go to the front
    if part1.req_grow and part2.req_grow:
        if not part1.req_max_size and part2.req_max_size:
            ret -= 25
        elif part1.req_max_size and not part2.req_max_size:
            ret += 25
        else:
            ret -= cmp(part1.req_max_size, part2.req_max_size) * 25

    # give a little bump based on mountpoint
    if hasattr(part1.format, "mountpoint") and \
       hasattr(part2.format, "mountpoint"):
        ret += cmp(part1.format.mountpoint, part2.format.mountpoint) * 10

    if ret > 0:
        ret = 1
    elif ret < 0:
        ret = -1

    return ret

def getNextPartitionType(disk, no_primary=None):
    """ Find the type of partition to create next on a disk.

        Return a parted partition type value representing the type of the
        next partition we will create on this disk.

        If there is only one free primary partition and we can create an
        extended partition, we do that.

        If there are free primary slots and an extended partition we will
        recommend creating a primary partition. This can be overridden
        with the keyword argument no_primary.

        Arguments:

            disk -- a parted.Disk instance representing the disk

        Keyword arguments:

            no_primary -- given a choice between primary and logical
                          partitions, prefer logical

    """
    part_type = None
    extended = disk.getExtendedPartition()
    supports_extended = disk.supportsFeature(parted.DISK_TYPE_EXTENDED)
    logical_count = len(disk.getLogicalPartitions())
    max_logicals = disk.getMaxLogicalPartitions()
    primary_count = disk.primaryPartitionCount

    if primary_count < disk.maxPrimaryPartitionCount:
        if primary_count == disk.maxPrimaryPartitionCount - 1:
            # can we make an extended partition? now's our chance.
            if not extended and supports_extended:
                part_type = parted.PARTITION_EXTENDED
            elif not extended:
                # extended partitions not supported. primary or nothing.
                if not no_primary:
                    part_type = parted.PARTITION_NORMAL
            else:
                # there is an extended and a free primary
                if not no_primary:
                    part_type = parted.PARTITION_NORMAL
                elif logical_count < max_logicals:
                    # we have an extended with logical slots, so use one.
                    part_type = parted.PARTITION_LOGICAL
        else:
            # there are two or more primary slots left. use one unless we're
            # not supposed to make primaries.
            if not no_primary:
                part_type = parted.PARTITION_NORMAL
            elif extended and logical_count < max_logicals:
                part_type = parted.PARTITION_LOGICAL
    elif extended and logical_count < max_logicals:
        part_type = parted.PARTITION_LOGICAL

    return part_type

def getBestFreeSpaceRegion(disk, part_type, req_size,
                           boot=None, best_free=None, grow=None):
    """ Return the "best" free region on the specified disk.

        For non-boot partitions, we return the largest free region on the
        disk. For boot partitions, we return the first region that is
        large enough to hold the partition.

        Partition type (parted's PARTITION_NORMAL, PARTITION_LOGICAL) is
        taken into account when locating a suitable free region.

        For locating the best region from among several disks, the keyword
        argument best_free allows the specification of a current "best"
        free region with which to compare the best from this disk. The
        overall best region is returned.

        Arguments:

            disk -- the disk (a parted.Disk instance)
            part_type -- the type of partition we want to allocate
                         (one of parted's partition type constants)
            req_size -- the requested size of the partition (in MB)

        Keyword arguments:

            boot -- indicates whether this will be a bootable partition
                    (boolean)
            best_free -- current best free region for this partition
            grow -- indicates whether this is a growable request

    """
    log.debug("getBestFreeSpaceRegion: disk=%s part_type=%d req_size=%dMB "
              "boot=%s best=%s grow=%s" %
              (disk.device.path, part_type, req_size, boot, best_free, grow))
    extended = disk.getExtendedPartition()

    for _range in disk.getFreeSpaceRegions():
        if extended:
            # find out if there is any overlap between this region and the
            # extended partition
            log.debug("looking for intersection between extended (%d-%d) and free (%d-%d)" %
                    (extended.geometry.start, extended.geometry.end, _range.start, _range.end))

            # parted.Geometry.overlapsWith can handle this
            try:
                free_geom = extended.geometry.intersect(_range)
            except ArithmeticError:
                # this freespace region does not lie within the extended
                # partition's geometry
                free_geom = None

            if (free_geom and part_type == parted.PARTITION_NORMAL) or \
               (not free_geom and part_type == parted.PARTITION_LOGICAL):
                log.debug("free region not suitable for request")
                continue

            if part_type == parted.PARTITION_NORMAL:
                # we're allocating a primary and the region is not within
                # the extended, so we use the original region
                free_geom = _range
        else:
            free_geom = _range

        if free_geom.start > disk.maxPartitionStartSector:
            log.debug("free range start sector beyond max for new partitions")
            continue

        if boot:
            free_start_mb = sectorsToSize(free_geom.start,
                                          disk.device.sectorSize)
            req_end_mb = free_start_mb + req_size
            if req_end_mb > 2*1024*1024:
                log.debug("free range position would place boot req above 2TB")
                continue

        log.debug("current free range is %d-%d (%dMB)" % (free_geom.start,
                                                          free_geom.end,
                                                          free_geom.getSize()))
        free_size = free_geom.getSize()

        # For boot partitions, we want the first suitable region we find.
        # For growable or extended partitions, we want the largest possible
        # free region.
        # For all others, we want the smallest suitable free region.
        if grow or part_type == parted.PARTITION_EXTENDED:
            op = gt
        else:
            op = lt
        if req_size <= free_size:
            if not best_free or op(free_geom.length, best_free.length):
                best_free = free_geom

                if boot:
                    # if this is a bootable partition we want to
                    # use the first freespace region large enough
                    # to satisfy the request
                    break

    return best_free

def sectorsToSize(sectors, sectorSize):
    """ Convert length in sectors to size in MB.

        Arguments:

            sectors     -   sector count
            sectorSize  -   sector size for the device, in bytes
    """
    return (sectors * sectorSize) / (1024.0 * 1024.0)

def sizeToSectors(size, sectorSize):
    """ Convert size in MB to length in sectors.

        Arguments:

            size        -   size in MB
            sectorSize  -   sector size for the device, in bytes
    """
    return (size * 1024.0 * 1024.0) / sectorSize

def removeNewPartitions(disks, partitions):
    """ Remove newly added input partitions from input disks.

        Arguments:

            disks -- list of StorageDevice instances with DiskLabel format
            partitions -- list of PartitionDevice instances

    """
    log.debug("removing all non-preexisting partitions %s from disk(s) %s"
                % (["%s(id %d)" % (p.name, p.id) for p in partitions
                                                    if not p.exists],
                   [d.name for d in disks]))
    for part in partitions:
        if part.partedPartition and part.disk in disks:
            if part.exists:
                # we're only removing partitions that don't physically exist
                continue

            if part.isExtended:
                # these get removed last
                continue

            part.disk.format.partedDisk.removePartition(part.partedPartition)
            part.partedPartition = None
            part.disk = None

    for disk in disks:
        # remove empty extended so it doesn't interfere
        extended = disk.format.extendedPartition
        if extended and not disk.format.logicalPartitions:
            log.debug("removing empty extended partition from %s" % disk.name)
            disk.format.partedDisk.removePartition(extended)

def addPartition(disklabel, free, part_type, size):
    """ Return new partition after adding it to the specified disk.

        Arguments:

            disklabel -- disklabel instance to add partition to
            free -- where to add the partition (parted.Geometry instance)
            part_type -- partition type (parted.PARTITION_* constant)
            size -- size (in MB) of the new partition

        The new partition will be aligned.

        Return value is a parted.Partition instance.

    """
    start = free.start
    if not disklabel.alignment.isAligned(free, start):
        start = disklabel.alignment.alignNearest(free, start)

    if disklabel.labelType == "sun" and start == 0:
        start = disklabel.alignment.alignUp(free, start)

    if part_type == parted.PARTITION_LOGICAL:
        # make room for logical partition's metadata
        start += disklabel.alignment.grainSize

    if start != free.start:
        log.debug("adjusted start sector from %d to %d" % (free.start, start))

    if part_type == parted.PARTITION_EXTENDED:
        end = free.end
        length = end - start + 1
    else:
        # size is in MB
        length = sizeToSectors(size, disklabel.partedDevice.sectorSize)
        end = start + length - 1

    if not disklabel.endAlignment.isAligned(free, end):
        end = disklabel.endAlignment.alignNearest(free, end)
        log.debug("adjusted length from %d to %d" % (length, end - start + 1))
        if start > end:
            raise PartitioningError(_("unable to allocate aligned partition"))

    new_geom = parted.Geometry(device=disklabel.partedDevice,
                               start=start,
                               end=end)

    max_length = disklabel.partedDisk.maxPartitionLength
    if max_length and new_geom.length > max_length:
        raise PartitioningError(_("requested size exceeds maximum allowed"))

    # create the partition and add it to the disk
    partition = parted.Partition(disk=disklabel.partedDisk,
                                 type=part_type,
                                 geometry=new_geom)
    constraint = parted.Constraint(exactGeom=new_geom)
    disklabel.partedDisk.addPartition(partition=partition,
                                      constraint=constraint)
    return partition

def getFreeRegions(disks):
    """ Return a list of free regions on the specified disks.

        Arguments:

            disks -- list of parted.Disk instances

        Return value is a list of unaligned parted.Geometry instances.

    """
    free = []
    for disk in disks:
        for f in disk.format.partedDisk.getFreeSpaceRegions():
            if f.length > 0:
                free.append(f)

    return free

def updateExtendedPartitions(storage, disks):
    # XXX hack -- if we created any extended partitions we need to add
    #             them to the tree now
    for disk in disks:
        extended = disk.format.extendedPartition
        if not extended:
            # remove any obsolete extended partitions
            for part in storage.partitions:
                if part.disk == disk and part.isExtended:
                    if part.exists:
                        storage.destroyDevice(part)
                    else:
                        storage.devicetree._removeDevice(part, moddisk=False)
            continue

        extendedName = devicePathToName(extended.getDeviceNodeName())
        # remove any obsolete extended partitions
        for part in storage.partitions:
            if part.disk == disk and part.isExtended and \
               part.partedPartition not in disk.format.partitions:
                if part.exists:
                    storage.destroyDevice(part)
                else:
                    storage.devicetree._removeDevice(part, moddisk=False)

        device = storage.devicetree.getDeviceByName(extendedName)
        if device:
            if not device.exists:
                # created by us, update partedPartition
                device.partedPartition = extended
            continue

        # This is a little odd because normally instantiating a partition
        # that does not exist means leaving self.parents empty and instead
        # populating self.req_disks. In this case, we need to skip past
        # that since this partition is already defined.
        device = PartitionDevice(extendedName, parents=disk)
        device.parents = [disk]
        device.partedPartition = extended
        # just add the device for now -- we'll handle actions at the last
        # moment to simplify things
        storage.devicetree._addDevice(device)

def doPartitioning(storage):
    """ Allocate and grow partitions.

        When this function returns without error, all PartitionDevice
        instances must have their parents set to the disk they are
        allocated on, and their partedPartition attribute set to the
        appropriate parted.Partition instance from their containing
        disk. All req_xxxx attributes must be unchanged.

        Arguments:

            storage - Main anaconda Storage instance

        Keyword/Optional Arguments:

            None

    """
    if not hasattr(storage.platform, "diskLabelTypes"):
        raise StorageError(_("can't allocate partitions without platform data"))

    disks = storage.partitioned
    if storage.config.exclusiveDisks:
        disks = [d for d in disks if d.name in storage.config.exclusiveDisks]

    for disk in disks:
        try:
            disk.setup()
        except DeviceError as (msg, name):
            log.error("failed to set up disk %s: %s" % (name, msg))
            raise PartitioningError(_("disk %s inaccessible") % disk.name)

    partitions = storage.partitions[:]
    for part in storage.partitions:
        part.req_bootable = False

        if part.exists:
            # if the partition is preexisting or part of a complex device
            # then we shouldn't modify it
            partitions.remove(part)
            continue

        if not part.exists:
            # start over with flexible-size requests
            part.req_size = part.req_base_size

    try:
        storage.bootDevice.req_bootable = True
    except AttributeError:
        # there's no stage2 device. hopefully it's temporary.
        pass

    removeNewPartitions(disks, partitions)
    free = getFreeRegions(disks)
    try:
        allocatePartitions(storage, disks, partitions, free)
        growPartitions(disks, partitions, free, size_sets=storage.size_sets)
    except Exception:
        raise
    else:
        # Mark all growable requests as no longer growable.
        for partition in storage.partitions:
            log.debug("fixing size of %s at %.2f" % (partition, partition.size))
            partition.req_grow = False
            partition.req_base_size = partition.size
            partition.req_size = partition.size
    finally:
        # these are only valid for one allocation run
        storage.size_sets = []

        # The number and thus the name of partitions may have changed now,
        # allocatePartitions() takes care of this for new partitions, but not
        # for pre-existing ones, so we update the name of all partitions here
        for part in storage.partitions:
            # leave extended partitions as-is -- we'll handle them separately
            if part.isExtended:
                continue
            part.updateName()

        updateExtendedPartitions(storage, disks)

        for part in [p for p in storage.partitions if not p.exists]:
            problem = part.checkSize()
            if problem < 0:
                raise PartitioningError(_("partition is too small for %(format)s formatting "
                                        "(allowable size is %(minSize)d MB to %(maxSize)d MB)")
                                        % {"format": part.format.name, "minSize": part.format.minSize,
                                            "maxSize": part.format.maxSize})
            elif problem > 0:
                raise PartitioningError(_("partition is too large for %(format)s formatting "
                                        "(allowable size is %(minSize)d MB to %(maxSize)d MB)")
                                        % {"format": part.format.name, "minSize": part.format.minSize,
                                            "maxSize": part.format.maxSize})

def allocatePartitions(storage, disks, partitions, freespace):
    """ Allocate partitions based on requested features.

        Non-existing partitions are sorted according to their requested
        attributes, and then allocated.

        The basic approach to sorting is that the more specifically-
        defined a request is, the earlier it will be allocated. See
        the function partitionCompare for details on the sorting
        criteria.

        The PartitionDevice instances will have their name and parents
        attributes set once they have been allocated.
    """
    log.debug("allocatePartitions: disks=%s ; partitions=%s" %
                ([d.name for d in disks],
                 ["%s(id %d)" % (p.name, p.id) for p in partitions]))

    new_partitions = [p for p in partitions if not p.exists]
    new_partitions.sort(cmp=partitionCompare)

    # the following dicts all use device path strings as keys
    disklabels = {}     # DiskLabel instances for each disk
    all_disks = {}      # StorageDevice for each disk
    for disk in disks:
        if disk.path not in disklabels.keys():
            disklabels[disk.path] = disk.format
            all_disks[disk.path] = disk

    removeNewPartitions(disks, new_partitions)

    for _part in new_partitions:
        if _part.partedPartition and _part.isExtended:
            # ignore new extendeds as they are implicit requests
            continue

        # obtain the set of candidate disks
        req_disks = []
        if _part.req_disks:
            # use the requested disk set
            req_disks = _part.req_disks
        else:
            # no disks specified means any disk will do
            req_disks = disks

        # sort the disks, making sure the boot disk is first
        req_disks.sort(key=lambda d: d.name, cmp=storage.compareDisks)
        for disk in req_disks:
            if storage.bootDisk and disk == storage.bootDisk:
                boot_index = req_disks.index(disk)
                req_disks.insert(0, req_disks.pop(boot_index))

        boot = _part.req_base_weight > 1000

        log.debug("allocating partition: %s ; id: %d ; disks: %s ;\n"
                  "boot: %s ; primary: %s ; size: %dMB ; grow: %s ; "
                  "max_size: %s" % (_part.name, _part.id,
                                    [d.name for d in req_disks],
                                    boot, _part.req_primary,
                                    _part.req_size, _part.req_grow,
                                    _part.req_max_size))
        free = None
        use_disk = None
        part_type = None
        growth = 0
        # loop through disks
        for _disk in req_disks:
            disklabel = disklabels[_disk.path]
            sectorSize = disklabel.partedDevice.sectorSize
            best = None
            current_free = free

            # for growable requests, we don't want to pass the current free
            # geometry to getBestFreeRegion -- this allows us to try the
            # best region from each disk and choose one based on the total
            # growth it allows
            if _part.req_grow:
                current_free = None

            log.debug("checking freespace on %s" % _disk.name)

            new_part_type = getNextPartitionType(disklabel.partedDisk)
            if new_part_type is None:
                # can't allocate any more partitions on this disk
                log.debug("no free partition slots on %s" % _disk.name)
                continue

            if _part.req_primary and new_part_type != parted.PARTITION_NORMAL:
                if (disklabel.partedDisk.primaryPartitionCount <
                    disklabel.partedDisk.maxPrimaryPartitionCount):
                    # don't fail to create a primary if there are only three
                    # primary partitions on the disk (#505269)
                    new_part_type = parted.PARTITION_NORMAL
                else:
                    # we need a primary slot and none are free on this disk
                    log.debug("no primary slots available on %s" % _disk.name)
                    continue

            best = getBestFreeSpaceRegion(disklabel.partedDisk,
                                          new_part_type,
                                          _part.req_size,
                                          best_free=current_free,
                                          boot=boot,
                                          grow=_part.req_grow)

            if best == free and not _part.req_primary and \
               new_part_type == parted.PARTITION_NORMAL:
                # see if we can do better with a logical partition
                log.debug("not enough free space for primary -- trying logical")
                new_part_type = getNextPartitionType(disklabel.partedDisk,
                                                     no_primary=True)
                if new_part_type:
                    best = getBestFreeSpaceRegion(disklabel.partedDisk,
                                                  new_part_type,
                                                  _part.req_size,
                                                  best_free=current_free,
                                                  boot=boot,
                                                  grow=_part.req_grow)

            if best and free != best:
                update = True
                allocated = new_partitions[:new_partitions.index(_part)+1]
                if any([p.req_grow for p in allocated]):
                    log.debug("evaluating growth potential for new layout")
                    new_growth = 0
                    for disk_path in disklabels.keys():
                        log.debug("calculating growth for disk %s" % disk_path)
                        # Now we check, for growable requests, which of the two
                        # free regions will allow for more growth.

                        # set up chunks representing the disks' layouts
                        temp_parts = []
                        for _p in new_partitions[:new_partitions.index(_part)]:
                            if _p.disk.path == disk_path:
                                temp_parts.append(_p)

                        # add the current request to the temp disk to set up
                        # its partedPartition attribute with a base geometry
                        if disk_path == _disk.path:
                            _part_type = new_part_type
                            _free = best
                            if new_part_type == parted.PARTITION_EXTENDED:
                                addPartition(disklabel, best, new_part_type,
                                             None)

                                _part_type = parted.PARTITION_LOGICAL

                                _free = getBestFreeSpaceRegion(disklabel.partedDisk,
                                                               _part_type,
                                                               _part.req_size,
                                                               boot=boot,
                                                               grow=_part.req_grow)
                                if not _free:
                                    log.info("not enough space after adding "
                                             "extended partition for growth test")
                                    if new_part_type == parted.PARTITION_EXTENDED:
                                        e = disklabel.extendedPartition
                                        disklabel.partedDisk.removePartition(e)

                                    continue

                            temp_part = addPartition(disklabel,
                                                     _free,
                                                     _part_type,
                                                     _part.req_size)
                            _part.partedPartition = temp_part
                            _part.disk = _disk
                            temp_parts.append(_part)

                        chunks = getDiskChunks(all_disks[disk_path],
                                               temp_parts, freespace)

                        # grow all growable requests
                        disk_growth = 0
                        disk_sector_size = disklabels[disk_path].partedDevice.sectorSize
                        for chunk in chunks:
                            chunk.growRequests()
                            # record the growth for this layout
                            new_growth += chunk.growth
                            disk_growth += chunk.growth
                            for req in chunk.requests:
                                log.debug("request %d (%s) growth: %d (%dMB) "
                                          "size: %dMB" %
                                          (req.device.id,
                                           req.device.name,
                                           req.growth,
                                           sectorsToSize(req.growth,
                                                         disk_sector_size),
                                           sectorsToSize(req.growth + req.base,
                                                         disk_sector_size)))
                        log.debug("disk %s growth: %d (%dMB)" %
                                        (disk_path, disk_growth,
                                         sectorsToSize(disk_growth,
                                                       disk_sector_size)))

                    disklabel.partedDisk.removePartition(temp_part)
                    _part.partedPartition = None
                    _part.disk = None

                    if new_part_type == parted.PARTITION_EXTENDED:
                        e = disklabel.extendedPartition
                        disklabel.partedDisk.removePartition(e)

                    log.debug("total growth: %d sectors" % new_growth)

                    # update the chosen free region unless the previous
                    # choice yielded greater total growth
                    if free is not None and new_growth <= growth:
                        log.debug("keeping old free: %d <= %d" % (new_growth,
                                                                  growth))
                        update = False
                    else:
                        growth = new_growth

                if update:
                    # now we know we are choosing a new free space,
                    # so update the disk and part type
                    log.debug("updating use_disk to %s, type: %s"
                                % (_disk.name, new_part_type))
                    part_type = new_part_type
                    use_disk = _disk
                    log.debug("new free: %d-%d / %dMB" % (best.start,
                                                          best.end,
                                                          best.getSize()))
                    log.debug("new free allows for %d sectors of growth" %
                                growth)
                    free = best

            if free and boot:
                # if this is a bootable partition we want to
                # use the first freespace region large enough
                # to satisfy the request
                log.debug("found free space for bootable request")
                break

        if free is None:
            raise PartitioningError(_("not enough free space on disks"))

        _disk = use_disk
        disklabel = _disk.format

        # create the extended partition if needed
        if part_type == parted.PARTITION_EXTENDED:
            log.debug("creating extended partition")
            addPartition(disklabel, free, part_type, None)

            # now the extended partition exists, so set type to logical
            part_type = parted.PARTITION_LOGICAL

            # recalculate freespace
            log.debug("recalculating free space")
            free = getBestFreeSpaceRegion(disklabel.partedDisk,
                                          part_type,
                                          _part.req_size,
                                          boot=boot,
                                          grow=_part.req_grow)
            if not free:
                raise PartitioningError(_("not enough free space after "
                                        "creating extended partition"))

        partition = addPartition(disklabel, free, part_type, _part.req_size)
        log.debug("created partition %s of %dMB and added it to %s" %
                (partition.getDeviceNodeName(), partition.getSize(),
                 disklabel.device))

        # this one sets the name
        _part.partedPartition = partition
        _part.disk = _disk

        # parted modifies the partition in the process of adding it to
        # the disk, so we need to grab the latest version...
        _part.partedPartition = disklabel.partedDisk.getPartitionByPath(_part.path)


class Request(object):
    """ A partition request.

        Request instances are used for calculating how much to grow
        partitions.
    """
    def __init__(self, device):
        """ Create a Request instance.

            Arguments:

        """
        self.device = device
        self.growth = 0                     # growth in sectors
        self.max_growth = 0                 # max growth in sectors
        self.done = not getattr(device, "req_grow", True)  # can we grow this
                                                           # request more?
        self.base = 0                       # base sectors

    @property
    def growable(self):
        """ True if this request is growable. """
        return getattr(self.device, "req_grow", True)

    @property
    def id(self):
        """ The id of the Device instance this request corresponds to. """
        return self.device.id

    def __repr__(self):
        s = ("%(type)s instance --\n"
             "id = %(id)s  name = %(name)s  growable = %(growable)s\n"
             "base = %(base)d  growth = %(growth)d  max_grow = %(max_grow)d\n"
             "done = %(done)s" %
             {"type": self.__class__.__name__, "id": self.id,
              "name": self.device.name, "growable": self.growable,
              "base": self.base, "growth": self.growth,
              "max_grow": self.max_growth, "done": self.done})
        return s


class PartitionRequest(Request):
    def __init__(self, partition):
        """ Create a PartitionRequest instance.

            Arguments:

                partition -- a PartitionDevice instance

        """
        super(PartitionRequest, self).__init__(partition)
        self.base = partition.partedPartition.geometry.length   # base sectors

        sector_size = partition.partedPartition.disk.device.sectorSize

        if partition.req_grow:
            limits = filter(lambda l: l > 0,
                        [sizeToSectors(partition.req_max_size, sector_size),
                         sizeToSectors(partition.format.maxSize, sector_size),
                         partition.partedPartition.disk.maxPartitionLength])

            if limits:
                max_sectors = min(limits)
                self.max_growth = max_sectors - self.base
                if self.max_growth <= 0:
                    # max size is less than or equal to base, so we're done
                    self.done = True


class LVRequest(Request):
    def __init__(self, lv):
        """ Create a LVRequest instance.

            Arguments:

                lv -- an LVMLogicalVolumeDevice instance

        """
        super(LVRequest, self).__init__(lv)

        # Round up to nearest pe. For growable requests this will mean that
        # first growth is to fill the remainder of any unused extent.
        self.base = lv.vg.align(lv.req_size, roundup=True) / lv.vg.peSize # pe

        if lv.req_grow:
            limits = [l / lv.vg.peSize for l in
                        [lv.vg.align(lv.req_max_size),
                         lv.vg.align(lv.format.maxSize)] if l > 0]

            if limits:
                max_units = min(limits)
                self.max_growth = max_units - self.base
                if self.max_growth <= 0:
                    # max size is less than or equal to base, so we're done
                    self.done = True


class Chunk(object):
    """ A free region from which devices will be allocated """
    def __init__(self, length, requests=None):
        """ Create a Chunk instance.

            Arguments:

                length -- the length of the chunk in allocation units


            Keyword Arguments:

                requests -- list of Request instances allocated from this chunk

        """
        if not hasattr(self, "path"):
            self.path = None
        self.length = length
        self.pool = length                  # free unit count
        self.base = 0                       # sum of growable requests' base
                                            # sizes
        self.requests = []                  # list of Request instances
        if isinstance(requests, list):
            for req in requests:
                self.addRequest(req)

        self.skip_list = []

    def __repr__(self):
        s = ("%(type)s instance --\n"
             "device = %(device)s  length = %(length)d  size = %(size)d\n"
             "remaining = %(rem)d  pool = %(pool)d" %
             {"type": self.__class__.__name__, "device": self.path,
              "length": self.length, "size": self.lengthToSize(self.length),
              "pool": self.pool, "rem": self.remaining})

        return s

    def __str__(self):
        s = "%d on %s" % (self.length, self.path)
        return s

    def addRequest(self, req):
        """ Add a Request to this chunk. """
        log.debug("adding request %d to chunk %s" % (req.device.id, self))

        self.requests.append(req)
        self.pool -= req.base

        if not req.done:
            self.base += req.base

    def reclaim(self, request, amount):
        """ Reclaim units from a request and return them to the pool. """
        log.debug("reclaim: %s %d (%d MB)" % (request, amount, self.lengthToSize(amount)))
        if request.growth < amount:
            log.error("tried to reclaim %d from request with %d of growth"
                        % (amount, request.growth))
            raise ValueError(_("cannot reclaim more than request has grown"))

        request.growth -= amount
        self.pool += amount

        # put this request in the skip list so we don't try to grow it the
        # next time we call growRequests to allocate the newly re-acquired pool
        if request not in self.skip_list:
            self.skip_list.append(request)

    @property
    def growth(self):
        """ Sum of growth for all requests in this chunk. """
        return sum(r.growth for r in self.requests)

    @property
    def hasGrowable(self):
        """ True if this chunk contains at least one growable request. """
        for req in self.requests:
            if req.growable:
                return True
        return False

    @property
    def remaining(self):
        """ Number of requests still being grown in this chunk. """
        return len([d for d in self.requests if not d.done])

    @property
    def done(self):
        """ True if we are finished growing all requests in this chunk. """
        return self.remaining == 0

    def maxGrowth(self, req):
        return req.max_growth

    def lengthToSize(self, length):
        return length

    def sizeToLength(self, size):
        return size

    def trimOverGrownRequest(self, req, base=None):
        """ Enforce max growth and return extra units to the pool. """
        max_growth = self.maxGrowth(req)
        if max_growth and req.growth >= max_growth:
            if req.growth > max_growth:
                # we've grown beyond the maximum. put some back.
                extra = req.growth - max_growth
                log.debug("taking back %d (%dMB) from %d (%s)" %
                            (extra, self.lengthToSize(extra),
                             req.device.id, req.device.name))
                self.pool += extra
                req.growth = max_growth

            # We're done growing this request, so it no longer
            # factors into the growable base used to determine
            # what fraction of the pool each request gets.
            if base is not None:
                base -= req.base
            req.done = True

        return base

    def sortRequests(self):
        pass

    def growRequests(self, uniform=False):
        """ Calculate growth amounts for requests in this chunk. """
        log.debug("Chunk.growRequests: %r" % self)

        self.sortRequests()
        for req in self.requests:
            log.debug("req: %r" % req)

        # we use this to hold the base for the next loop through the
        # chunk's requests since we want the base to be the same for
        # all requests in any given growth iteration
        new_base = self.base
        last_pool = 0 # used to track changes to the pool across iterations
        while not self.done and self.pool and last_pool != self.pool:
            last_pool = self.pool    # to keep from getting stuck
            self.base = new_base
            if uniform:
                growth = last_pool / self.remaining

            log.debug("%d requests and %d (%dMB) left in chunk" %
                        (self.remaining, self.pool, self.lengthToSize(self.pool)))
            for p in self.requests:
                if p.done or p in self.skip_list:
                    continue

                if not uniform:
                    # Each request is allocated free units from the pool
                    # based on the relative _base_ sizes of the remaining
                    # growable requests.
                    share = p.base / float(self.base)
                    growth = int(share * last_pool) # truncate, don't round

                p.growth += growth
                self.pool -= growth
                log.debug("adding %d (%dMB) to %d (%s)" %
                            (growth, self.lengthToSize(growth),
                             p.device.id, p.device.name))

                new_base = self.trimOverGrownRequest(p, base=new_base)
                log.debug("new grow amount for request %d (%s) is %d "
                          "units, or %dMB" %
                            (p.device.id, p.device.name, p.growth,
                             self.lengthToSize(p.growth)))

        if self.pool:
            # allocate any leftovers in pool to the first partition
            # that can still grow
            for p in self.requests:
                if p.done:
                    continue

                growth = self.pool
                p.growth += growth
                self.pool = 0
                log.debug("adding %d (%dMB) to %d (%s)" %
                            (growth, self.lengthToSize(growth),
                             p.device.id, p.device.name))

                self.trimOverGrownRequest(p)
                log.debug("new grow amount for request %d (%s) is %d "
                          "units, or %dMB" %
                            (p.device.id, p.device.name, p.growth,
                             self.lengthToSize(p.growth)))

                if self.pool == 0:
                    break

        # requests that were skipped over this time through are back on the
        # table next time
        self.skip_list = []


class DiskChunk(Chunk):
    """ A free region on disk from which partitions will be allocated """
    def __init__(self, geometry, requests=None):
        """ Create a Chunk instance.

            Arguments:

                geometry -- parted.Geometry instance describing the free space


            Keyword Arguments:

                requests -- list of Request instances allocated from this chunk


            Note: We will limit partition growth based on disklabel
            limitations for partition end sector, so a 10TB disk with an
            msdos disklabel will be treated like a 2TB disk.

        """
        self.geometry = geometry            # parted.Geometry
        self.sectorSize = self.geometry.device.sectorSize
        self.path = self.geometry.device.path
        super(DiskChunk, self).__init__(self.geometry.length, requests=requests)

    def __repr__(self):
        s = super(DiskChunk, self).__str__()
        s += (" start = %(start)d  end = %(end)d\n"
              "sectorSize = %(sectorSize)d\n" %
              {"start": self.geometry.start, "end": self.geometry.end,
               "sectorSize": self.sectorSize})
        return s

    def __str__(self):
        s = "%d (%d-%d) on %s" % (self.length, self.geometry.start,
                                  self.geometry.end, self.path)
        return s

    def addRequest(self, req):
        """ Add a Request to this chunk. """
        if not isinstance(req, PartitionRequest):
            raise ValueError(_("DiskChunk requests must be of type "
                             "PartitionRequest"))

        if not self.requests:
            # when adding the first request to the chunk, adjust the pool
            # size to reflect any disklabel-specific limits on end sector
            max_sector = req.device.partedPartition.disk.maxPartitionStartSector
            chunk_end = min(max_sector, self.geometry.end)
            if chunk_end <= self.geometry.start:
                # this should clearly never be possible, but if the chunk's
                # start sector is beyond the maximum allowed end sector, we
                # cannot continue
                log.error("chunk start sector is beyond disklabel maximum")
                raise PartitioningError(_("partitions allocated outside "
                                        "disklabel limits"))

            new_pool = chunk_end - self.geometry.start + 1
            if new_pool != self.pool:
                log.debug("adjusting pool to %d based on disklabel limits"
                            % new_pool)
                self.pool = new_pool

        super(DiskChunk, self).addRequest(req)

    def maxGrowth(self, req):
        req_end = req.device.partedPartition.geometry.end
        req_start = req.device.partedPartition.geometry.start

        # Establish the current total number of sectors of growth for requests
        # that lie before this one within this chunk. We add the total count
        # to this request's end sector to obtain the end sector for this
        # request, including growth of earlier requests but not including
        # growth of this request. Maximum growth values are obtained using
        # this end sector and various values for maximum end sector.
        growth = 0
        for request in self.requests:
            if request.device.partedPartition.geometry.start < req_start:
                growth += request.growth
        req_end += growth

        # obtain the set of possible maximum sectors-of-growth values for this
        # request and use the smallest
        limits = []

        # disklabel-specific maximum sector
        max_sector = req.device.partedPartition.disk.maxPartitionStartSector
        limits.append(max_sector - req_end)

        # 2TB limit on bootable partitions, regardless of disklabel
        if req.device.req_bootable:
            limits.append(sizeToSectors(2*1024*1024, self.sectorSize) - req_end)

        # request-specific maximum (see Request.__init__, above, for details)
        if req.max_growth:
            limits.append(req.max_growth)

        max_growth = min(limits)
        return max_growth

    def lengthToSize(self, length):
        return sectorsToSize(length, self.sectorSize)

    def sizeToLength(self, size):
        return sizeToSectors(size, self.sectorSize)

    def sortRequests(self):
        # sort the partitions by start sector
        self.requests.sort(key=lambda r: r.device.partedPartition.geometry.start)


class VGChunk(Chunk):
    """ A free region in an LVM VG from which LVs will be allocated """
    def __init__(self, vg, requests=None):
        """ Create a VGChunk instance.

            Arguments:

                vg -- an LVMVolumeGroupDevice within which this chunk resides


            Keyword Arguments:

                requests -- list of Request instances allocated from this chunk

        """
        self.vg = vg
        self.path = vg.path
        usable_extents = vg.extents - (vg.reservedSpace / vg.peSize)
        super(VGChunk, self).__init__(usable_extents, requests=requests)

    def addRequest(self, req):
        """ Add a Request to this chunk. """
        if not isinstance(req, LVRequest):
            raise ValueError(_("VGChunk requests must be of type "
                             "LVRequest"))

        super(VGChunk, self).addRequest(req)

    def lengthToSize(self, length):
        return length * self.vg.peSize

    def sizeToLength(self, size):
        return size / self.vg.peSize

    def sortRequests(self):
        # sort the partitions by start sector
        self.requests.sort(key=lambda r: r.device, cmp=lvCompare)

    def growRequests(self):
        self.sortRequests()

        # grow the percentage-based requests
        last_pool = self.pool
        for req in self.requests:
            if req.done or not req.device.req_percent:
                continue

            growth = int(req.device.req_percent * 0.01 * self.length)# truncate
            req.growth += growth
            self.pool -= growth
            log.debug("adding %d (%dMB) to %d (%s)" %
                        (growth, self.lengthToSize(growth),
                         req.device.id, req.device.name))

            new_base = self.trimOverGrownRequest(req)
            log.debug("new grow amount for request %d (%s) is %d "
                      "units, or %dMB" %
                        (req.device.id, req.device.name, req.growth,
                         self.lengthToSize(req.growth)))

            # we're done with this request, so remove its base from the
            # chunk's base
            if not req.done:
                self.base -= req.base
                req.done = True

        super(VGChunk, self).growRequests()


def getDiskChunks(disk, partitions, free):
    """ Return a list of Chunk instances representing a disk.

        Arguments:

            disk -- a StorageDevice with a DiskLabel format
            partitions -- list of PartitionDevice instances
            free -- list of parted.Geometry instances representing free space

        Partitions and free regions not on the specified disk are ignored.

    """
    # list of all new partitions on this disk
    disk_parts = [p for p in partitions if p.disk == disk and not p.exists]
    disk_free = [f for f in free if f.device.path == disk.path]


    chunks = [DiskChunk(f) for f in disk_free]

    for p in disk_parts:
        if p.isExtended:
            # handle extended partitions specially since they are
            # indeed very special
            continue

        for i, f in enumerate(disk_free):
            if f.contains(p.partedPartition.geometry):
                chunks[i].addRequest(PartitionRequest(p))
                break

    return chunks

class TotalSizeSet(object):
    """ Set of device requests with a target combined size.

        This will be handled by growing the requests until the desired combined
        size has been achieved.
    """
    def __init__(self, devices, size):
        self.devices = []
        for device in devices:
            if isinstance(device, LUKSDevice):
                partition = device.slave
            else:
                partition = device

            self.devices.append(partition)

        self.size = size

        self.requests = []

        self.allocated = sum([d.req_base_size for d in self.devices])
        log.debug("set.allocated = %d" % self.allocated)

    def allocate(self, amount):
        log.debug("allocating %d to TotalSizeSet with %d/%d (%d needed)"
                    % (amount, self.allocated, self.size, self.needed))
        self.allocated += amount

    @property
    def needed(self):
        return self.size - self.allocated

    def deallocate(self, amount):
        log.debug("deallocating %d from TotalSizeSet with %d/%d (%d needed)"
                    % (amount, self.allocated, self.size, self.needed))
        self.allocated -= amount

class SameSizeSet(object):
    """ Set of device requests with a common target size. """
    def __init__(self, devices, size, grow=False, max_size=None):
        self.devices = []
        for device in devices:
            if isinstance(device, LUKSDevice):
                partition = device.slave
            else:
                partition = device

            self.devices.append(partition)

        self.size = int(size / len(devices))
        self.grow = grow
        self.max_size = max_size

        self.requests = []

def manageSizeSets(size_sets, chunks):
    growth_by_request = {}
    requests_by_device = {}
    chunks_by_request = {}
    for chunk in chunks:
        for request in chunk.requests:
            requests_by_device[request.device] = request
            chunks_by_request[request] = chunk
            growth_by_request[request] = 0

    for i in range(2):
        reclaimed = dict([(chunk, 0) for chunk in chunks])
        for ss in size_sets:
            if isinstance(ss, TotalSizeSet):
                # TotalSizeSet members are trimmed to achieve the requested
                # total size
                log.debug("set: %s %d/%d" % ([d.name for d in ss.devices],
                                              ss.allocated, ss.size))

                for device in ss.devices:
                    request = requests_by_device[device]
                    chunk = chunks_by_request[request]
                    new_growth = request.growth - growth_by_request[request]
                    ss.allocate(chunk.lengthToSize(new_growth))

                # decide how much to take back from each request
                # We may assume that all requests have the same base size.
                # We're shooting for a roughly equal distribution by trimming
                # growth from the requests that have grown the most first.
                requests = sorted([requests_by_device[d] for d in ss.devices],
                                  key=lambda r: r.growth, reverse=True)
                needed = ss.needed
                for request in requests:
                    chunk = chunks_by_request[request]
                    log.debug("%s" % request)
                    log.debug("needed: %d" % ss.needed)

                    if ss.needed < 0:
                        # it would be good to take back some from each device
                        # instead of taking all from the last one(s)
                        extra = -chunk.sizeToLength(needed) / len(ss.devices)
                        if extra > request.growth and i == 0:
                            log.debug("not reclaiming from this request")
                            continue
                        else:
                            extra = min(extra, request.growth)

                        reclaimed[chunk] += extra
                        chunk.reclaim(request, extra)
                        ss.deallocate(chunk.lengthToSize(extra))

                    if ss.needed <= 0:
                        request.done = True

            elif isinstance(ss, SameSizeSet):
                # SameSizeSet members all have the same size as the smallest
                # member
                requests = [requests_by_device[d] for d in ss.devices]
                _min_growth = min([r.growth for r in requests])
                log.debug("set: %s %d" % ([d.name for d in ss.devices], ss.size))
                log.debug("min growth is %d" % _min_growth)
                for request in requests:
                    chunk = chunks_by_request[request]
                    _max_growth = chunk.sizeToLength(ss.size) - request.base
                    log.debug("max growth for %s is %d" % (request, _max_growth))
                    min_growth = max(min(_min_growth, _max_growth), 0)
                    if request.growth > min_growth:
                        extra = request.growth - min_growth
                        reclaimed[chunk] += extra
                        chunk.reclaim(request, extra)
                        request.done = True
                    elif request.growth == min_growth:
                        request.done = True

        # store previous growth amounts so we know how much was allocated in
        # the latest growRequests call
        for request in growth_by_request.keys():
            growth_by_request[request] = request.growth

        for chunk in chunks:
            if reclaimed[chunk] and not chunk.done:
                chunk.growRequests()

def growPartitions(disks, partitions, free, size_sets=None):
    """ Grow all growable partition requests.

        Partitions have already been allocated from chunks of free space on
        the disks. This function does not modify the ordering of partitions
        or the free chunks from which they are allocated.

        Free space within a given chunk is allocated to each growable
        partition allocated from that chunk in an amount corresponding to
        the ratio of that partition's base size to the sum of the base sizes
        of all growable partitions allocated from the chunk.

        Arguments:

            disks -- a list of all usable disks (DiskDevice instances)
            partitions -- a list of all partitions (PartitionDevice instances)
            free -- a list of all free regions (parted.Geometry instances)
    """
    log.debug("growPartitions: disks=%s, partitions=%s" %
            ([d.name for d in disks],
             ["%s(id %d)" % (p.name, p.id) for p in partitions]))
    all_growable = [p for p in partitions if p.req_grow]
    if not all_growable:
        log.debug("no growable partitions")
        return

    if size_sets is None:
        size_sets = []

    log.debug("growable partitions are %s" % [p.name for p in all_growable])

    #
    # collect info about each disk and the requests it contains
    #
    chunks = []
    for disk in disks:
        sector_size = disk.format.partedDevice.sectorSize

        # list of free space regions on this disk prior to partition allocation
        disk_free = [f for f in free if f.device.path == disk.path]
        if not disk_free:
            log.debug("no free space on %s" % disk.name)
            continue

        disk_chunks = getDiskChunks(disk, partitions, disk_free)
        log.debug("disk %s has %d chunks" % (disk.name, len(disk_chunks)))
        chunks.extend(disk_chunks)

    #
    # grow the partitions in each chunk as a group
    #
    for chunk in chunks:
        if not chunk.hasGrowable:
            # no growable partitions in this chunk
            continue

        chunk.growRequests()

    # adjust set members' growth amounts as needed
    manageSizeSets(size_sets, chunks)

    for disk in disks:
        log.debug("growing partitions on %s" % disk.name)
        for chunk in chunks:
            if chunk.path != disk.path:
                continue

            if not chunk.hasGrowable:
                # no growable partitions in this chunk
                continue

            # recalculate partition geometries
            disklabel = disk.format
            start = chunk.geometry.start

            # find any extended partition on this disk
            extended_geometry = getattr(disklabel.extendedPartition,
                                        "geometry",
                                        None)  # parted.Geometry

            # align start sector as needed
            if not disklabel.alignment.isAligned(chunk.geometry, start):
                start = disklabel.alignment.alignUp(chunk.geometry, start)
            new_partitions = []
            for p in chunk.requests:
                ptype = p.device.partedPartition.type
                log.debug("partition %s (%d): %s" % (p.device.name,
                                                     p.device.id, ptype))
                if ptype == parted.PARTITION_EXTENDED:
                    continue

                # XXX since we need one metadata sector before each
                #     logical partition we burn one logical block to
                #     safely align the start of each logical partition
                if ptype == parted.PARTITION_LOGICAL:
                    start += disklabel.alignment.grainSize

                old_geometry = p.device.partedPartition.geometry
                new_length = p.base + p.growth
                end = start + new_length - 1
                # align end sector as needed
                if not disklabel.endAlignment.isAligned(chunk.geometry, end):
                    end = disklabel.endAlignment.alignDown(chunk.geometry, end)
                new_geometry = parted.Geometry(device=disklabel.partedDevice,
                                               start=start,
                                               end=end)
                log.debug("new geometry for %s: %s" % (p.device.name,
                                                       new_geometry))
                start = end + 1
                new_partition = parted.Partition(disk=disklabel.partedDisk,
                                                 type=ptype,
                                                 geometry=new_geometry)
                new_partitions.append((new_partition, p.device))

            # remove all new partitions from this chunk
            removeNewPartitions([disk], [r.device for r in chunk.requests])
            log.debug("back from removeNewPartitions")

            # adjust the extended partition as needed
            # we will ony resize an extended partition that we created
            log.debug("extended: %s" % extended_geometry)
            if extended_geometry and \
               chunk.geometry.contains(extended_geometry):
                log.debug("setting up new geometry for extended on %s" % disk.name)
                ext_start = 0
                for (partition, device) in new_partitions:
                    if partition.type != parted.PARTITION_LOGICAL:
                        continue

                    if not ext_start or partition.geometry.start < ext_start:
                        # account for the logical block difference in start
                        # sector for the extended -v- first logical
                        # (partition.geometry.start is already aligned)
                        ext_start = partition.geometry.start - disklabel.alignment.grainSize

                new_geometry = parted.Geometry(device=disklabel.partedDevice,
                                               start=ext_start,
                                               end=chunk.geometry.end)
                log.debug("new geometry for extended: %s" % new_geometry)
                new_extended = parted.Partition(disk=disklabel.partedDisk,
                                                type=parted.PARTITION_EXTENDED,
                                                geometry=new_geometry)
                ptypes = [p.type for (p, d) in new_partitions]
                for pt_idx, ptype in enumerate(ptypes):
                    if ptype == parted.PARTITION_LOGICAL:
                        new_partitions.insert(pt_idx, (new_extended, None))
                        break

            # add the partitions with their new geometries to the disk
            for (partition, device) in new_partitions:
                if device:
                    name = device.name
                else:
                    # If there was no extended partition on this disk when
                    # doPartitioning was called we won't have a
                    # PartitionDevice instance for it.
                    name = partition.getDeviceNodeName()

                log.debug("setting %s new geometry: %s" % (name,
                                                           partition.geometry))
                constraint = parted.Constraint(exactGeom=partition.geometry)
                disklabel.partedDisk.addPartition(partition=partition,
                                                  constraint=constraint)
                path = partition.path
                if device:
                    # set the device's name
                    device.partedPartition = partition
                    # without this, the path attr will be a basename. eek.
                    device.disk = disk

                    # make sure we store the disk's version of the partition
                    newpart = disklabel.partedDisk.getPartitionByPath(path)
                    device.partedPartition = newpart


def lvCompare(lv1, lv2):
    """ More specifically defined lvs come first.

        < 1 => x < y
          0 => x == y
        > 1 => x > y
    """
    ret = 0

    # larger requests go to the front of the list
    ret -= cmp(lv1.size, lv2.size) * 100

    # fixed size requests to the front
    ret += cmp(lv1.req_grow, lv2.req_grow) * 50

    # potentially larger growable requests go to the front
    if lv1.req_grow and lv2.req_grow:
        if not lv1.req_max_size and lv2.req_max_size:
            ret -= 25
        elif lv1.req_max_size and not lv2.req_max_size:
            ret += 25
        else:
            ret -= cmp(lv1.req_max_size, lv2.req_max_size) * 25

    if ret > 0:
        ret = 1
    elif ret < 0:
        ret = -1

    return ret

def growLVM(storage):
    """ Grow LVs according to the sizes of the PVs. """
    for vg in storage.vgs:
        total_free = vg.freeSpace
        if total_free < 0:
            # by now we have allocated the PVs so if there isn't enough
            # space in the VG we have a real problem
            raise PartitioningError(_("not enough space for LVM requests"))
        elif not total_free:
            log.debug("vg %s has no free space" % vg.name)
            continue

        log.debug("vg %s: %dMB free ; lvs: %s" % (vg.name, total_free,
                                                  [l.lvname for l in vg.lvs]))

        chunk = VGChunk(vg, requests=[LVRequest(l) for l in vg.lvs])
        chunk.growRequests()

        # now grow the lvs by the amounts we've calculated above
        for req in chunk.requests:
            if not req.device.req_grow:
                continue

            # Base is in pe, which means potentially rounded up by as much as
            # pesize-1. As a result, you can't just add the growth to the
            # initial size.
            req.device.size = chunk.lengthToSize(req.base + req.growth)
