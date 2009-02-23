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

import os
import copy
from operator import add, sub

# XXX temporary
import sys
sys.path.insert(0, "/root/pyparted/src")
sys.path.insert(1, "/root/pyparted/src/.libs")
import parted

from errors import *
from deviceaction import *
from pykickstart.constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")


def clearPartitions(storage, clearPartType=CLEARPART_TYPE_NONE,
                    clearPartDisks=[]):
    """ Clear partitions and dependent devices from disks.

        Arguments:

            deviceTree -- a DeviceTree instance

        Keyword arguments:

            clearPartType -- a pykickstart CLEARPART_TYPE_* constant
            clearPartDisks -- a list of basenames of disks to consider

        NOTES:

            - Needs some error handling, especially for the parted bits.
            - Should use device actions instead of dev.destroy, &c

    """
    if not clearPartType or clearPartType == CLEARPART_TYPE_NONE:
        # not much to do -- just remove any empty extended partitions
        removeEmptyExtendedPartitions(deviceTree)
        return

    # we are only interested in partitions that physically exist
    partitions = [p for p in storage.partitions if p.exists]
    disks = []  # a list of disks from which we've removed partitions

    for part in partitions:
        log.debug("clearpart: looking at %s" % part.name)
        clear = False   # whether or not we will clear this partition

        # if we got a list of disks to clear, make sure this one's on it
        if clearPartDisks and not part.disk.name in clearPartDisks:
            continue

        # we don't want to fool with extended partitions, freespace, &c
        if part.partType not in (parted.PARTITION_NORMAL,
                                 parted.PARTITION_LOGICAL):
            continue

        if clearPartType == CLEARPART_TYPE_ALL:
            clear = True
        else:
            if part.format and part.format.linuxNative:
                clear = True
            elif part.partedPartition.getFlag(parted.PARTITION_LVM) or \
                 part.partedPartition.getFlag(parted.PARTITION_RAID) or \
                 part.partedPartition.getFlag(parted.PARTITION_SWAP):
                clear = True

        # TODO: do platform-specific checks on ia64, pSeries, iSeries, mac

        if not clear:
            continue

        log.debug("clearing %s" % part.name)

        # XXX is there any argument for not removing incomplete devices?
        #       -- maybe some RAID devices
        devices = storage.deviceDeps(part)
        while devices:
            log.debug("devices to remove: %s" % ([d.name for d in devices],))
            leaves = [d for d in devices if d.isleaf]
            log.debug("leaves to remove: %s" % ([d.name for d in leaves],))
            for leaf in leaves:
                action = ActionDestroyDevice(leaf)
                deviceTree.registerAction(action)
                devices.remove(leaf)

        # XXX can/should this be moved into PartitionDevice?
        part.partedPartition.disk.removePartition(part.partedPartition)
        log.debug("partitions: %s" % [p.getDeviceNodeName() for p in part.partedPartition.disk.partitions])
        disk_name = os.path.basename(part.partedPartition.disk.device.path)
        if disk_name not in disks:
            disks.append(disk_name)

        action = ActionDestroyDevice(part)
        deviceTree.registerAction(action)

    # now remove any empty extended partitions
    removeEmptyExtendedPartitions(deviceTree)


def removeEmptyExtendedPartitions(storage):
    for disk in storage.disks:
        log.debug("checking whether disk %s has an empty extended" % disk.name)
        extended = disk.partedDisk.getExtendedPartition()
        logical_parts = disk.partedDisk.getLogicalPartitions()
        log.debug("extended is %s ; logicals is %s" % (extended, [p.getDeviceNodeName() for p in logical_parts]))
        if extended and not logical_parts:
            log.debug("removing empty extended partition from %s" % disk.name)
            extended_name = extended.getDeviceNodeName()
            extended = storage.devicetree.getDeviceByName(extended_name)
            storage.devicetree.registerAction(ActionDestroyDevice(extended))
            #disk.partedDisk.removePartition(extended.partedPartition)


def partitionCompare(part1, part2):
    """ More specifically defined partitions come first.

        < 1 => x < y
          0 => x == y
        > 1 => x > y
    """
    ret = 0

    # bootable partitions to the front
    ret -= cmp(part1.req_bootable, part2.req_bootable) * 1000

    # more specific disk specs to the front of the list
    ret += cmp(len(part1.parents), len(part2.parents)) * 500

    # primary-only to the front of the list
    ret -= cmp(part1.req_primary, part2.req_primary) * 200

    # larger requests go to the front of the list
    ret -= cmp(part1.size, part2.size) * 100

    # fixed size requests to the front
    ret += cmp(part1.req_grow, part2.req_grow) * 50

    # potentially larger growable requests go to the front
    if part1.req_grow and part2.req_grow:
        if not part1.req_max_size and part2.req_max_size:
            ret -= 25
        elif part1.req_max_size and not part2.req_max_size:
            ret += 25
        else:
            ret -= cmp(part1.req_max_size, part2.req_max_size) * 25

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

    if primary_count == disk.maxPrimaryPartitionCount and \
       extended and logical_count < max_logicals:
        part_type = parted.PARTITION_LOGICAL
    elif primary_count == (disk.maxPrimaryPartitionCount - 1) and \
         not extended and supports_extended:
        # last chance to create an extended partition
        part_type = parted.PARTITION_EXTENDED
    elif no_primary and extended and logical_count < max_logicals:
        # create a logical even though we could presumably create a
        # primary instead
        part_type = parted.PARTITION_LOGICAL
    elif not no_primary:
        # XXX there is a possiblity that the only remaining free space on
        #     the disk lies within the extended partition, but we will
        #     try to create a primary first
        part_type = parted.PARTITION_NORMAL

    return part_type

def getBestFreeSpaceRegion(disk, part_type, req_size,
                           boot=None, best_free=None):
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

    """
    log.debug("getBestFreeSpaceRegion: disk=%s part_type=%d req_size=%dMB boot=%s best=%s" % (disk.device.path, part_type, req_size, boot, best_free))
    extended = disk.getExtendedPartition()
    for _range in disk.getFreeSpaceRegions():
        if extended:
            # find out if there is any overlap between this region and the
            # extended partition
            log.debug("looking for intersection between extended (%d-%d) and free (%d-%d)" % (extended.geometry.start, extended.geometry.end, _range.start, _range.end))

            # parted.Geometry.overlapsWith can handle this
            try:
                free_geom = extended.geometry.intersect(_range)
            except ArithmeticError, e:
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

        log.debug("current free range is %d-%d (%dMB)" % (free_geom.start,
                                                          free_geom.end,
                                                          free_geom.getSize()))
        free_size = free_geom.getSize()

        if req_size <= free_size:
            if not best_free or free_geom.length > best_free.length:
                best_free = free_geom

                if boot:
                    # if this is a bootable partition we want to
                    # use the first freespace region large enough
                    # to satisfy the request
                    break

    return best_free

def doPartitioning(storage, exclusiveDisks=[]):
    """ Allocate and grow partitions.

        When this function returns without error, all PartitionDevice
        instances must have their parents set to the disk they are
        allocated on, and their partedPartition attribute set to the
        appropriate parted.Partition instance from their containing
        disk. All req_xxxx attributes must be unchanged.

        Arguments:

            storage -- the Storage instance

        Keyword arguments:

            exclusiveDisks -- a list of basenames of disks to use

    """
    disks = storage.disks
    partitions = storage.partitions
    if exclusiveDisks:
        # only use specified disks
        disks = [d for d in disks if d.name in exclusiveDisks]

    # FIXME: make sure non-existent partitions have empty parents list
    allocatePartitions(disks, partitions)
    growPartitions(disks, partitions)

    # XXX hack -- if we created any extended partitions we need to add
    #             them to the tree now
    for disk in disks:
        extended = disk.partedDisk.getExtendedPartition()
        if extended.getDeviceNodeName() in [p.name for p in partitions]:
            # this extended partition is preexisting
            continue

        device = PartitionDevice(extended.getDeviceNodeName(),
                                 parents=disk)
        device.setPartedPartition(extended)
        storage.addDevice(device)

def allocatePartitions(disks, partitions):
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
    log.debug("allocatePartitions: disks=%s ; partitions=%s" % (disks,
                                                                partitions))
    new_partitions = [p for p in partitions if not p.exists]
    new_partitions.sort(cmp=partitionCompare)

    # XXX is this needed anymore?
    partedDisks = {}
    for disk in disks:
        if disk.path not in partedDisks.keys():
            partedDisks[disk.path] = disk.partedDisk #.duplicate()

    # remove all newly added partitions from the disk
    log.debug("removing all non-preexisting from disk(s)")
    for _part in new_partitions:
        if _part.partedPartition:
            #_part.disk.partedDisk.removePartition(_part.partedPartition)
            partedDisk = partedDisks[_part.disk.partedDisk.device.path]
            #log.debug("removing part %s (%s) from disk %s (%s)" % (_part.partedPartition.path, [p.path for p in _part.partedPartition.disk.partitions], partedDisk.device.path, [p.path for p in partedDisk.partitions]))
            partedDisk.removePartition(_part.partedPartition)
            # remove empty extended so it doesn't interfere
            extended = partedDisk.getExtendedPartition()
            if extended and not partedDisk.getLogicalPartitions():
                log.debug("removing empty extended partition")
                #partedDisk.minimizeExtendedPartition()
                partedDisk.removePartition(extended)

    for _part in new_partitions:
        # obtain the set of candidate disks
        req_disks = []
        if _part.disk:
            # we have a already selected a disk for this request
            req_disks = [_part.disk]
        elif _part.req_disks:
            # use the requested disk set
            req_disks = _part.req_disks
        else:
            # no disks specified means any disk will do
            req_disks = disks

        log.debug("allocating partition: %s ; disks: %s ; boot: %s ; primary: %s ; size: %dMB ; grow: %s ; max_size: %s" % (_part.name, req_disks, _part.req_bootable, _part.req_primary, _part.req_size, _part.req_grow, _part.req_max_size))
        free = None
        # loop through disks
        for _disk in req_disks:
            disk = partedDisks[_disk.path]
            #for p in disk.partitions:
            #    log.debug("disk %s: part %s" % (disk.device.path, p.path))
            sectorSize = disk.device.physicalSectorSize
            part_type = parted.PARTITION_NORMAL
            best = None

            # TODO: On alpha we are supposed to reserve either one or two
            #       MB at the beginning of each disk. Awesome.
            #         -- maybe we do not care about alpha...

            log.debug("checking freespace on %s" % _disk.name)

            part_type = getNextPartitionType(disk)
            if part_type is None:
                # can't allocate any more partitions on this disk
                log.debug("no free partition slots on %s" % _disk.name)
                continue

            if _part.req_primary and part_type != parted.PARTITION_NORMAL:
                # we need a primary slot and none are free on this disk
                log.debug("no primary slots available on %s" % _disk.name)
                continue

            best = getBestFreeSpaceRegion(disk,
                                          part_type,
                                          _part.req_size,
                                          best_free=free,
                                          boot=_part.req_bootable)
            
            if best == free and not _part.req_primary and \
               part_type == parted.PARTITION_NORMAL:
                # see if we can do better with a logical partition
                log.debug("not enough free space for primary -- trying logical")
                part_type = getNextPartitionType(disk, no_primary=True)
                if part_type:
                    free = getBestFreeSpaceRegion(disk,
                                                  part_type,
                                                  _part.req_size,
                                                  best_free=free,
                                                  boot=_part.req_bootable)
            else:
                free = best

            if free and _part.req_bootable:
                # if this is a bootable partition we want to
                # use the first freespace region large enough
                # to satisfy the request
                log.debug("found free space for bootable request")
                break

        if free is None:
            raise PartitioningError("not enough free space on disks")

        # create the extended partition if needed
        # TODO: move to a function (disk, free)
        if part_type == parted.PARTITION_EXTENDED:
            log.debug("creating extended partition")
            geometry = parted.Geometry(device=disk.device,
                                       start=free.start,
                                       length=free.length,
                                       end=free.end)
            extended = parted.Partition(disk=disk,
                                        type=parted.PARTITION_EXTENDED,
                                        geometry=geometry)
            constraint = parted.Constraint(device=disk.device)
            # FIXME: we should add this to the tree as well
            disk.addPartition(extended, constraint)

            # end proposed function

            # now the extended partition exists, so set type to logical
            part_type = parted.PARTITION_LOGICAL

            # recalculate freespace
            log.debug("recalculating free space")
            free = getBestFreeSpaceRegion(disk,
                                          part_type,
                                          _part.req_size,
                                          boot=_part.req_bootable)
            if not free:
                raise PartitioningError("not enough free space after "
                                        "creating extended partition")

        # create minimum geometry for this request
        # req_size is in MB
        length = (_part.req_size * (1024 * 1024)) / sectorSize
        new_geom = parted.Geometry(device=disk.device,
                                   start=free.start,
                                   length=length)

        # create the partition and add it to the disk
        partition = parted.Partition(disk=disk,
                                     type=part_type,
                                     geometry=new_geom)
        disk.addPartition(partition=partition,
                          constraint=disk.device.getConstraint())
#                          constraint=parted.Constraint(device=disk.device))
        log.debug("created partition %s of %dMB and added it to %s" % (partition.getDeviceNodeName(), partition.getSize(), disk))
        _part.setPartedPartition(partition)
        _part.disk = _disk


def growPartitions(disks, partitions):
    """ Grow all growable partition requests.

        All requests should know what disk they will be on by the time
        this function is called. This is reflected in the
        PartitionDevice's disk attribute. Note that the req_disks
        attribute remains unchanged.

        The total available free space is summed up for each disk and
        partition requests are allocated a maximum percentage of the
        available free space on their disk based on their own base size.

        Each attempted size means calling allocatePartitions again with
        one request's size having changed.

        After taking into account several factors that may limit the
        maximum size of a requested partition, we arrive at a firm
        maximum number of sectors by which a request can potentially grow.

        An initial attempt is made to allocate the full maximum size. If
        this fails, we begin a rough binary search with a maximum of three
        iterations to settle on a new size.

        TODO: Call disk.maximizePartition for each growable partition that
              has not been allocated its full share of the free space upon
              termination of each disk's loop iteration. Any detected
              maximum size can be specified via a parted Constraint.

        Arguments:

            disks -- a list of all usable disks (DiskDevice instances)
            partitions -- a list of all partitions (PartitionDevice
                          instances)
    """
    log.debug("growPartitions: disks=%s, partitions=%s" % ([d.name for d in disks], [p.name for p in partitions]))
    all_growable = [p for p in partitions if p.req_grow]

    # sort requests by base size in decreasing order
    all_growable.sort(key=lambda p: p.req_size, reverse=True)

    log.debug("growable requests are %s" % [p.name for p in all_growable])

    for disk in disks:
        log.debug("growing requests on %s" % disk.name)
        sectorSize = disk.partedDisk.device.physicalSectorSize
        # get a list of free space regions on the disk
        free = disk.partedDisk.getFreeSpaceRegions()
        # sort the free regions in decreasing order of size
        free.sort(key=lambda r: r.length, reverse=True)
        disk_free = reduce(lambda x,y: x + y, [f.length for f in free])

        # make a list of partitions currently allocated on this disk
        # -- they're already sorted
        growable = []
        disk_total = 0
        for part in all_growable:
            #log.debug("checking if part %s (%s) is on this disk" % (part.name,
            #                                                        part.disk.name))
            if part.disk == disk:
                growable.append(part)
                disk_total += (part.req_size * (1024 * 1024)) / sectorSize

        # now we loop through the partitions...
        for part in growable:
            # calculate max number of sectors this request can grow
            sectors = (part.req_size * (1024 * 1024)) / sectorSize
            share = float(sectors) / float(disk_total)
            max_grow = share * disk_free
            max_mb = (max_grow * sectorSize) / (1024 * 1024)
            log.debug("%s: base_size=%dMB, max_size=%sMB" % (part.name,
                                                             part.req_base_size,
                                                             part.req_max_size))
            log.debug("%s: %dMB (%d sectors, or %d%% of %d)" % (part.name,
                                                                max_mb,
                                                                max_grow,
                                                                share * 100,
                                                                disk_free))

            log.debug("checking constraints on max size...")
            # don't grow beyond the request's maximum size
            if part.req_max_size:
                log.debug("max_size: %dMB" % part.req_max_size)
                # FIXME: round down to nearest cylinder boundary
                max_sect = (part.req_max_size * (1024 * 1024)) / sectorSize
                if max_sect < sectors + max_grow:
                    max_grow = (max_sect - sectors)

            # don't grow beyond the resident filesystem's max size
            if part.format and getattr(part.format, 'maxsize', 0):
                log.debug("format maxsize: %dMB" % part.format.maxsize)
                # FIXME: round down to nearest cylinder boundary
                max_sect = (part.format.maxsize * (1024 * 1024)) / sectorSize
                if max_sect < sectors + max_grow:
                    max_grow = (max_sect - sectors)

            # we can only grow as much as the largest free region on the disk
            if free[0].length < max_grow:
                log.debug("largest free region: %d sectors (%dMB)" % (free[0].length, free[0].getSize()))
                # FIXME: round down to nearest cylinder boundary
                max_grow = free[0].length

            # Now, we try to grow this partition as close to max_grow
            # sectors as we can.
            #
            # We could call allocatePartitions after modifying this
            # request and saving the original value of part.req_size,
            # or we could try to use disk.maximizePartition().
            req_sectors = (part.req_size * 1024 * 1024) / sectorSize
            max_sectors = req_sectors + max_grow
            max_size = (max_sectors * sectorSize) / (1024 * 1024)
            orig_size = part.req_size
            # try the max size to begin with
            log.debug("attempting to allocate maximum size: %dMB" % max_size)
            part.req_size = max_size
            try:
                allocatePartitions(disks, partitions)
            except PartitioningError, e:
                log.debug("max size attempt failed: %s (%dMB)" % (part.name,
                                                                  max_size))
                part.req_size = orig_size
            else:
                continue

            log.debug("starting binary search: size=%d max_size=%d" % (part.req_size, max_size))
            count = 0
            op_func = add
            increment = max_grow
            last_good_size = part.req_size
            last_outcome = None
            while part.req_size < max_size and count < 3:
                last_size = part.req_size
                increment /= 2
                sectors = op_func(sectors, increment)
                part.req_size = (sectors * sectorSize) / (1024 * 1024)
                log.debug("attempting size=%dMB" % part.req_size)
                count += 1
                try:
                    allocatePartitions(disks, partitions)
                except PartitioningError, e:
                    log.debug("attempt at %dMB failed" % part.req_size)
                    op_func = sub
                    last_outcome = False
                else:
                    last_good_size = part.req_size
                    last_outcome = True

            if not last_outcome:
                part.req_size = last_good_size
                log.debug("backing up to size=%dMB" % part.req_size)
                try:
                    allocatePartitions(disks, partitions)
                except PartitioningError, e:
                    raise PartitioningError("failed to grow partitions")

            # TODO: call disk.maximizePartition with max_size as the
            #       constraint, in case it can grab some more free space


    # reset all requests to their original requested size
    for part in partitions:
        if part.exists:
            continue
        part.req_size = part.req_base_size

def growLVM(tree):
    """ Grow LVs according to the sizes of the PVs. """
    vgs = tree.getDevicesByType("lvm vg")
    for vg in vgs:
        total_free = vg.freeSpace
        if not total_free:
            log.debug("vg %s has no free space" % vg.name)
            continue

        # figure out how much to grow each LV
        grow_amounts = {}
        lv_total = vg.size - total_free

        # This first loop is to calculate percentage-based growth
        # amounts. These are based on total free space.
        for lv in lvs:
            if not lv.req_grow or not lv.req_percent:
                continue

            portion = (lv_req_percent * 0.01)
            # clamp growth amount to a multiple of vg extent size
            grow = vg.align(portion * vg.vgFree)
            new_size = lv.req_size + grow
            if lv.req_max_size and new_size > lv.req_max_size:
                # clamp growth amount to a multiple of vg extent size
                grow -= align(new_size - lv.req_max_size)

            # clamp growth amount to a multiple of vg extent size
            grow_amounts[lv.name] = vg.align(grow)
            total_free -= grow

        # This second loop is to calculate non-percentage-based growth
        # amounts. These are based on free space remaining after
        # calculating percentage-based growth amounts.
        for lv in lvs:
            if not lv.req_grow or lv.req_percent:
                continue

            portion = float(lv.req_size) / float(lv_total)
            # clamp growth amount to a multiple of vg extent size
            grow = vg.align(portion * total_free)
            new_size = lv.req_size + grow
            if lv.req_max_size and new_size > lv.req_max_size:
                # clamp growth amount to a multiple of vg extent size
                grow -= vg.align(new_size - lv.req_max_size)

            grow_amounts[lv.name] = grow

        if not grow_amounts:
            log.debug("no growable lvs in vg %s" % vg.name)
            continue

        # now grow the lvs by the amounts we've calculated above
        for lv in lvs:
            if lv.name not in grow_amounts.keys():
                continue
            lv.size = new_size

        # now there shouldn't be any free space left, but if there is we
        # should allocate it to one of the LVs
        vg_free = vg.freeSpace
        log.debug("vg %s still has %dMB free" % (vg.name, vg_free))



