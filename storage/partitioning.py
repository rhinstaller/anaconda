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

from constants import *

from errors import *
from deviceaction import *
from devices import PartitionDevice, LUKSDevice, devicePathToName

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("storage")

def _createFreeSpacePartitions(anaconda):
    # get a list of disks that have at least one free space region of at
    # least 100MB
    disks = []
    for disk in anaconda.id.storage.disks:
        if anaconda.id.storage.clearPartDisks and \
           (disk.name not in anaconda.id.storage.clearPartDisks):
            continue

        part = disk.format.firstPartition
        while part:
            if not part.type & parted.PARTITION_FREESPACE:
                part = part.nextPartition()
                continue

            if part.getSize(unit="MB") > 100:
                disks.append(disk)
                break

            part = part.nextPartition()

    # create a separate pv partition for each disk with free space
    devs = []
    for disk in disks:
        if anaconda.id.storage.encryptedAutoPart:
            fmt_type = "luks"
            fmt_args = {"escrow_cert": anaconda.id.storage.autoPartEscrowCert,
                        "add_backup_passphrase": anaconda.id.storage.autoPartAddBackupPassphrase}
        else:
            fmt_type = "lvmpv"
            fmt_args = {}
        part = anaconda.id.storage.newPartition(fmt_type=fmt_type,
                                                fmt_args=fmt_args,
                                                size=1,
                                                grow=True,
                                                disks=[disk])
        anaconda.id.storage.createDevice(part)
        devs.append(part)

    return (disks, devs)

def _schedulePartitions(anaconda, disks):
    #
    # Convert storage.autoPartitionRequests into Device instances and
    # schedule them for creation
    #
    # First pass is for partitions only. We'll do LVs later.
    #
    for request in anaconda.id.storage.autoPartitionRequests:
        if request.asVol:
            continue

        if request.fstype is None:
            request.fstype = anaconda.id.storage.defaultFSType
        # This is a little unfortunate but let the backend dictate the rootfstype
        # so that things like live installs can do the right thing
        if request.mountpoint == "/" and anaconda.backend.rootFsType != None:
            request.fstype = anaconda.backend.rootFsType

        dev = anaconda.id.storage.newPartition(fmt_type=request.fstype,
                                               size=request.size,
                                               grow=request.grow,
                                               maxsize=request.maxSize,
                                               mountpoint=request.mountpoint,
                                               disks=disks,
                                               weight=request.weight)

        # schedule the device for creation
        anaconda.id.storage.createDevice(dev)

    # make sure preexisting broken lvm/raid configs get out of the way
    return

def _scheduleLVs(anaconda, devs):
    if anaconda.id.storage.encryptedAutoPart:
        pvs = []
        for dev in devs:
            pv = LUKSDevice("luks-%s" % dev.name,
                            format=getFormat("lvmpv", device=dev.path),
                            size=dev.size,
                            parents=dev)
            pvs.append(pv)
            anaconda.id.storage.createDevice(pv)
    else:
        pvs = devs

    # create a vg containing all of the autopart pvs
    vg = anaconda.id.storage.newVG(pvs=pvs)
    anaconda.id.storage.createDevice(vg)

    initialVGSize = vg.size

    #
    # Convert storage.autoPartitionRequests into Device instances and
    # schedule them for creation.
    #
    # Second pass, for LVs only.
    for request in anaconda.id.storage.autoPartitionRequests:
        if not request.asVol:
            continue

        if request.requiredSpace and request.requiredSpace > initialVGSize:
            continue

        if request.fstype is None:
            request.fstype = anaconda.id.storage.defaultFSType

        # This is a little unfortunate but let the backend dictate the rootfstype
        # so that things like live installs can do the right thing
        if request.mountpoint == "/" and anaconda.backend.rootFsType != None:
            request.fstype = anaconda.backend.rootFsType

        # FIXME: move this to a function and handle exceptions
        dev = anaconda.id.storage.newLV(vg=vg,
                                        fmt_type=request.fstype,
                                        mountpoint=request.mountpoint,
                                        grow=request.grow,
                                        maxsize=request.maxSize,
                                        size=request.size)

        # schedule the device for creation
        anaconda.id.storage.createDevice(dev)


def doAutoPartition(anaconda):
    log.debug("doAutoPartition(%s)" % anaconda)
    log.debug("doAutoPart: %s" % anaconda.id.storage.doAutoPart)
    log.debug("clearPartType: %s" % anaconda.id.storage.clearPartType)
    log.debug("clearPartDisks: %s" % anaconda.id.storage.clearPartDisks)
    log.debug("autoPartitionRequests: %s" % anaconda.id.storage.autoPartitionRequests)
    log.debug("storage.disks: %s" % anaconda.id.storage.disks)
    log.debug("all names: %s" % [d.name for d in anaconda.id.storage.devices])
    if anaconda.dir == DISPATCH_BACK:
        anaconda.id.storage.reset()
        return

    disks = []
    devs = []

    if anaconda.id.storage.doAutoPart:
        clearPartitions(anaconda.id.storage)

    if anaconda.id.storage.doAutoPart:
        (disks, devs) = _createFreeSpacePartitions(anaconda)

        if disks == []:
            if anaconda.isKickstart:
                msg = _("Could not find enough free space for automatic "
                        "partitioning.  Press 'OK' to exit the installer.")
            else:
                msg = _("Could not find enough free space for automatic "
                        "partitioning, please use another partitioning method.")

            anaconda.intf.messageWindow(_("Error Partitioning"), msg,
                                        custom_icon='error')

            if anaconda.isKickstart:
                sys.exit(0)

            anaconda.id.storage.reset()
            return DISPATCH_BACK

        _schedulePartitions(anaconda, disks)

    # sanity check the individual devices
    log.warning("not sanity checking devices because I don't know how yet")

    # run the autopart function to allocate and grow partitions
    try:
        doPartitioning(anaconda.id.storage,
                       exclusiveDisks=anaconda.id.storage.clearPartDisks)

        if anaconda.id.storage.doAutoPart:
            _scheduleLVs(anaconda, devs)

        # grow LVs
        growLVM(anaconda.id.storage)
    except PartitioningWarning as msg:
        if not anaconda.isKickstart:
            anaconda.intf.messageWindow(_("Warnings During Automatic "
                                          "Partitioning"),
                           _("Following warnings occurred during automatic "
                           "partitioning:\n\n%s") % (msg,),
                           custom_icon='warning')
        else:
            log.warning(msg)
    except PartitioningError as msg:
        # restore drives to original state
        anaconda.id.storage.reset()
        if not anaconda.isKickstart:
            extra = ""
            anaconda.dispatch.skipStep("partition", skip = 0)
        else:
            extra = _("\n\nPress 'OK' to exit the installer.")
        anaconda.intf.messageWindow(_("Error Partitioning"),
               _("Could not allocate requested partitions: \n\n"
                 "%(msg)s.%(extra)s") % {'msg': msg, 'extra': extra},
               custom_icon='error')

        if anaconda.isKickstart:
            sys.exit(0)
        else:
            return

    # sanity check the collection of devices
    log.warning("not sanity checking storage config because I don't know how yet")
    # now do a full check of the requests
    (errors, warnings) = anaconda.id.storage.sanityCheck()
    if warnings:
        for warning in warnings:
            log.warning(warning)
    if errors:
        errortxt = "\n".join(errors)
        if anaconda.isKickstart:
            extra = _("\n\nPress 'OK' to exit the installer.")
        else:
            extra = _("\n\nPress 'OK' to choose a different partitioning option.")

        anaconda.intf.messageWindow(_("Automatic Partitioning Errors"),
                           _("The following errors occurred with your "
                             "partitioning:\n\n%(errortxt)s\n\n"
                             "This can happen if there is not enough "
                             "space on your hard drive(s) for the "
                             "installation. %(extra)s")
                           % {'errortxt': errortxt, 'extra': extra},
                           custom_icon='error')
        #
        # XXX if in kickstart we reboot
        #
        if anaconda.isKickstart:
            anaconda.intf.messageWindow(_("Unrecoverable Error"),
                               _("The system will now reboot."))
            sys.exit(0)
        anaconda.id.storage.reset()
        return DISPATCH_BACK

def shouldClear(part, clearPartType, clearPartDisks=None):
    if not isinstance(part, PartitionDevice):
        return False

    if not clearPartType in [CLEARPART_TYPE_LINUX, CLEARPART_TYPE_ALL]:
        return False

    # Never clear the special first partition on a Mac disk label, as that
    # holds the partition table itself.
    if part.disk.format.partedDisk.type == "mac" and \
       part.partedPartition.number == 1 and \
       part.partedPartition.name == "Apple":
        return False

    # If we got a list of disks to clear, make sure this one's on it
    if clearPartDisks and part.disk.name not in clearPartDisks:
        return False

    # Don't clear partitions holding install media.
    if part.protected:
        return False

    # We don't want to fool with extended partitions, freespace, &c
    if part.partType not in [parted.PARTITION_NORMAL, parted.PARTITION_LOGICAL]:
        return False

    if clearPartType == CLEARPART_TYPE_LINUX and \
       not part.format.linuxNative and \
       not part.getFlag(parted.PARTITION_LVM) and \
       not part.getFlag(parted.PARTITION_RAID) and \
       not part.getFlag(parted.PARTITION_SWAP):
        return False

    # TODO: do platform-specific checks on ia64, pSeries, iSeries, mac

    return True

def clearPartitions(storage):
    """ Clear partitions and dependent devices from disks.

        Arguments:

            storage -- a storage.Storage instance

        Keyword arguments:

            None

        NOTES:

            - Needs some error handling, especially for the parted bits.

    """
    if storage.clearPartType is None or storage.clearPartType == CLEARPART_TYPE_NONE:
        # not much to do
        return

    # we are only interested in partitions that physically exist
    partitions = [p for p in storage.partitions if p.exists]
    # Sort partitions by descending partition number to minimize confusing
    # things like multiple "destroy sda5" actions due to parted renumbering
    # partitions. This can still happen through the UI but it makes sense to
    # avoid it where possible.
    partitions.sort(key=lambda p: p.partedPartition.number, reverse=True)
    for part in partitions:
        log.debug("clearpart: looking at %s" % part.name)
        if not shouldClear(part, storage.clearPartType, storage.clearPartDisks):
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
                storage.destroyDevice(leaf)
                devices.remove(leaf)

        log.debug("partitions: %s" % [p.getDeviceNodeName() for p in part.partedPartition.disk.partitions])
        storage.destroyDevice(part)

    # now remove any empty extended partitions
    removeEmptyExtendedPartitions(storage)


def removeEmptyExtendedPartitions(storage):
    for disk in storage.disks:
        log.debug("checking whether disk %s has an empty extended" % disk.name)
        extended = disk.format.extendedPartition
        logical_parts = disk.format.logicalPartitions
        log.debug("extended is %s ; logicals is %s" % (extended, [p.getDeviceNodeName() for p in logical_parts]))
        if extended and not logical_parts:
            log.debug("removing empty extended partition from %s" % disk.name)
            extended_name = devicePathToName(extended.getDeviceNodeName())
            extended = storage.devicetree.getDeviceByName(extended_name)
            storage.destroyDevice(extended)
            #disk.partedDisk.removePartition(extended.partedPartition)


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

    # bootable partitions to the front
    ret -= cmp(part1.req_bootable, part2.req_bootable) * 1000

    # more specific disk specs to the front of the list
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
        ret -= cmp(part1.format.mountpoint, part2.format.mountpoint) * 10

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

def getDiskAlignment(disk):
    """ Return a minimal alignment for the specified disk.

        Arguments:

            disk -- a parted.Disk instance

    """
    return parted.Alignment(offset=0, grainSize=1)

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

def addPartition(disk, free, part_type, size):
    """ Return new partition after adding it to the specified disk.

        Arguments:

            disk -- disk to add partition to (parted.Disk instance)
            free -- where to add the partition (parted.Geometry instance)
            part_type -- partition type (parted.PARTITION_* constant)
            size -- size (in MB) of the new partition

        The new partition will be aligned.

        Return value is a parted.Partition instance.

    """
    _a = getDiskAlignment(disk)
    start = free.start
    if not _a.isAligned(free, start):
        start = _a.alignNearest(free, start)
        log.debug("adjusted start sector from %d to %d" % (free.start, start))

    if part_type == parted.PARTITION_EXTENDED:
        end = free.end
    else:
        # size is in MB
        length = sizeToSectors(size, disk.device.physicalSectorSize)
        end = start + length
        if not _a.isAligned(free, end):
            end = _a.alignNearest(free, end)
            log.debug("adjusted length from %d to %d" % (length, end - start))

    new_geom = parted.Geometry(device=disk.device,
                               start=start,
                               end=end)

    # create the partition and add it to the disk
    partition = parted.Partition(disk=disk,
                                 type=part_type,
                                 geometry=new_geom)
    constraint = parted.Constraint(exactGeom=new_geom)
    disk.addPartition(partition=partition, constraint=constraint)
    return partition

def doPartitioning(storage, exclusiveDisks=None):
    """ Allocate and grow partitions.

        When this function returns without error, all PartitionDevice
        instances must have their parents set to the disk they are
        allocated on, and their partedPartition attribute set to the
        appropriate parted.Partition instance from their containing
        disk. All req_xxxx attributes must be unchanged.

        Arguments:

            storage - Main anaconda Storage instance

        Keyword arguments:

            exclusiveDisks -- list of names of disks to use

    """
    anaconda = storage.anaconda
    disks = storage.disks
    if exclusiveDisks:
        disks = [d for d in disks if d.name in exclusiveDisks]

    for disk in disks:
        disk.setup()

    partitions = storage.partitions[:]
    for part in storage.partitions:
        part.req_bootable = False

        if part.exists or \
           (storage.deviceImmutable(part) and part.partedPartition):
            # if the partition is preexisting or part of a complex device
            # then we shouldn't modify it
            partitions.remove(part)
            continue

        if not part.exists:
            # start over with flexible-size requests
            part.req_size = part.req_base_size

    # FIXME: isn't there a better place for this to happen?
    try:
        bootDev = anaconda.platform.bootDevice()
    except DeviceError:
        bootDev = None

    if bootDev:
        bootDev.req_bootable = True

    # turn off cylinder alignment
    if parted.isAlignToCylinders():
        parted.toggleAlignToCylinders()

    # FIXME: make sure non-existent partitions have empty parents list
    allocatePartitions(disks, partitions)
    growPartitions(disks, partitions)
    # The number and thus the name of partitions may have changed now,
    # allocatePartitions() takes care of this for new partitions, but not
    # for pre-existing ones, so we update the name of all partitions here
    for part in storage.partitions:
        # needed because of XXX hack below
        if part.isExtended:
            continue
        part.updateName()

    # XXX hack -- if we created any extended partitions we need to add
    #             them to the tree now
    for disk in disks:
        extended = disk.format.extendedPartition
        if not extended:
            # remove any obsolete extended partitions
            for part in storage.partitions:
                if part.disk == disk and part.isExtended:
                    storage.devicetree._removeDevice(part, moddisk=False)
            continue

        extendedName = devicePathToName(extended.getDeviceNodeName())
        # remove any obsolete extended partitions
        for part in storage.partitions:
            if part.disk == disk and part.isExtended and \
               part.name != extendedName:
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
    log.debug("allocatePartitions: disks=%s ; partitions=%s" %
                ([d.name for d in disks],
                 ["%s(id %d)" % (p.name, p.id) for p in partitions]))
    new_partitions = [p for p in partitions if not p.exists]
    new_partitions.sort(cmp=partitionCompare)

    # XXX is this needed anymore?
    disklabels = {}
    for disk in disks:
        if disk.path not in disklabels.keys():
            disklabels[disk.path] = disk.format

    removeNewPartitions(disks, new_partitions)

    for _part in new_partitions:
        if _part.partedPartition and _part.isExtended:
            # ignore new extendeds as they are implicit requests
            continue

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

        log.debug("allocating partition: %s ; id: %d ; disks: %s ;\n"
                  "boot: %s ; primary: %s ; size: %dMB ; grow: %s ; "
                  "max_size: %s" % (_part.name, _part.id, req_disks,
                                    _part.req_bootable, _part.req_primary,
                                    _part.req_size, _part.req_grow,
                                    _part.req_max_size))
        free = None
        use_disk = None
        part_type = None
        # loop through disks
        for _disk in req_disks:
            disklabel = disklabels[_disk.path]
            #for p in disk.partitions:
            #    log.debug("disk %s: part %s" % (disk.device.path, p.path))
            sectorSize = disklabel.partedDevice.physicalSectorSize
            best = None

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
                                          best_free=free,
                                          boot=_part.req_bootable,
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
                                                  best_free=free,
                                                  boot=_part.req_bootable,
                                                  grow=_part.req_grow)

            if best and free != best:
                # now we know we are choosing a new free space,
                # so update the disk and part type
                log.debug("updating use_disk to %s (%s), type: %s"
                            % (_disk, _disk.name, new_part_type))
                part_type = new_part_type
                use_disk = _disk
                log.debug("new free: %s (%d-%d / %dMB)" % (best,
                                                           best.start,
                                                           best.end,
                                                           best.getSize()))
                free = best

            # For platforms with a fake boot partition (like Apple Bootstrap or
            # PReP) and multiple disks, we need to ensure the /boot partition
            # ends up on the same disk as the fake one.
            mountpoint = getattr(_part.format, "mountpoint", "")
            if not mountpoint:
                mountpoint = ""

            if free and (_part.req_bootable or mountpoint.startswith("/boot")):
                # if this is a bootable partition we want to
                # use the first freespace region large enough
                # to satisfy the request
                log.debug("found free space for bootable request")
                break

        if free is None:
            raise PartitioningError("not enough free space on disks")

        _disk = use_disk
        disklabel = _disk.format

        # create the extended partition if needed
        # TODO: move to a function (disk, free)
        if part_type == parted.PARTITION_EXTENDED:
            log.debug("creating extended partition")
            addPartition(disklabel.partedDisk, free, part_type, None)

            # now the extended partition exists, so set type to logical
            part_type = parted.PARTITION_LOGICAL

            # recalculate freespace
            log.debug("recalculating free space")
            free = getBestFreeSpaceRegion(disklabel.partedDisk,
                                          part_type,
                                          _part.req_size,
                                          boot=_part.req_bootable,
                                          grow=_part.req_grow)
            if not free:
                raise PartitioningError("not enough free space after "
                                        "creating extended partition")

        partition = addPartition(disklabel.partedDisk, free,
                                 part_type, _part.req_size)
        log.debug("created partition %s of %dMB and added it to %s" %
                (partition.getDeviceNodeName(), partition.getSize(),
                 disklabel.device))

        # this one sets the name
        _part.partedPartition = partition
        _part.disk = _disk

        # parted modifies the partition in the process of adding it to
        # the disk, so we need to grab the latest version...
        _part.partedPartition = disklabel.partedDisk.getPartitionByPath(_part.path)

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

        Arguments:

            disks -- a list of all usable disks (DiskDevice instances)
            partitions -- a list of all partitions (PartitionDevice
                          instances)
    """
    log.debug("growPartitions: disks=%s, partitions=%s" %
            ([d.name for d in disks],
             ["%s(id %d)" % (p.name, p.id) for p in partitions]))
    all_growable = [p for p in partitions if p.req_grow]
    if not all_growable:
        return

    # sort requests by base size in decreasing order
    all_growable.sort(key=lambda p: p.req_size, reverse=True)

    log.debug("growable requests are %s" %
                ["%s(id %d)" % (p.name, p.id) for p in all_growable])

    for disk in disks:
        log.debug("growing requests on %s" % disk.name)
        for p in disk.format.partitions:
            log.debug("  %s: %s (%dMB)" % (disk.name, p.getDeviceNodeName(),
                                         p.getSize()))
        sectorSize = disk.format.partedDevice.physicalSectorSize
        # get a list of free space regions on the disk
        free = disk.format.partedDisk.getFreeSpaceRegions()
        if not free:
            log.debug("no free space on %s" % disk.name)
            continue

        # sort the free regions in decreasing order of size
        free.sort(key=lambda r: r.length, reverse=True)
        disk_free = reduce(lambda x,y: x + y, [f.length for f in free])
        log.debug("total free: %d sectors ; largest: %d sectors (%dMB)"
                    % (disk_free, free[0].length, free[0].getSize()))

        # make a list of partitions currently allocated on this disk
        # -- they're already sorted
        growable = []
        disk_total = 0
        for part in all_growable:
            #log.debug("checking if part %s (%s) is on this disk" % (part.name,
            #                                                        part.disk.name))
            if part.disk == disk:
                growable.append(part)
                disk_total += part.partedPartition.geometry.length
                log.debug("add %s (%dMB/%d sectors) to growable total"
                            % (part.name, part.partedPartition.getSize(),
                                part.partedPartition.geometry.length))
                log.debug("growable total is now %d sectors" % disk_total)

        # now we loop through the partitions...
        # this first loop is to identify obvious chunks of free space that
        # will be left over due to max size
        leftover = 0
        limited = {}
        unlimited_total = 0
        for part in growable:
            # calculate max number of sectors this request can grow
            req_sectors = part.partedPartition.geometry.length
            share = float(req_sectors) / float(disk_total)
            max_grow = (share * disk_free)
            max_sectors = req_sectors + max_grow
            limited[id(part)] = False

            if part.req_max_size:
                req_max_sect = sizeToSectors(part.req_max_size, sectorSize)
                if req_max_sect < max_sectors:
                    mb = sectorsToSize(max_sectors - req_max_sect, sectorSize)

                    log.debug("adding %dMB to leftovers from %s"
                                % (mb, part.name))
                    leftover += (max_sectors - req_max_sect)
                    limited[id(part)] = True

            if not limited[id(part)]:
                unlimited_total += req_sectors

        # now we loop through the partitions...
        for part in growable:
            # calculate max number of sectors this request can grow
            req_sectors = part.partedPartition.geometry.length
            share = float(req_sectors) / float(disk_total)
            max_grow = (share * disk_free)
            if not limited[id(part)]:
                leftover_share = float(req_sectors) / float(unlimited_total)
                max_grow += leftover_share * leftover
            max_sectors = req_sectors + max_grow
            max_mb = sectorsToSize(max_sectors, sectorSize)

            log.debug("%s: base_size=%dMB, max_size=%sMB" %
                    (part.name, part.req_base_size,  part.req_max_size))
            log.debug("%s: current_size=%dMB (%d sectors)" %
                    (part.name, part.partedPartition.getSize(),
                        part.partedPartition.geometry.length))
            log.debug("%s: %dMB (%d sectors, or %d%% of %d)" %
                    (part.name, max_mb, max_sectors, share * 100, disk_free))

            log.debug("checking constraints on max size...")
            # don't grow beyond the request's maximum size
            if part.req_max_size:
                log.debug("max_size: %dMB" % part.req_max_size)
                req_max_sect = sizeToSectors(part.req_max_size, sectorSize)
                if req_max_sect < max_sectors:
                    max_grow -= (max_sectors - req_max_sect)
                    max_sectors = req_sectors + max_grow

            # don't grow beyond the resident filesystem's max size
            if part.format.maxSize > 0:
                log.debug("format maxsize: %dMB" % part.format.maxSize)
                fs_max_sect = sizeToSectors(part.format.maxSize, sectorSize)
                if fs_max_sect < max_sectors:
                    max_grow -= (max_sectors - fs_max_sect)
                    max_sectors = req_sectors + max_grow

            # we can only grow as much as the largest free region on the disk
            if free[0].length < max_grow:
                log.debug("largest free region: %d sectors (%dMB)" %
                        (free[0].length, free[0].getSize()))
                max_grow = free[0].length
                max_sectors = req_sectors + max_grow

            # Now, we try to grow this partition as close to max_grow
            # sectors as we can.
            #
            # We could call allocatePartitions after modifying this
            # request and saving the original value of part.req_size,
            # or we could try to use disk.maximizePartition().
            max_size = sectorsToSize(max_sectors, sectorSize)
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
            while count < 3:
                last_size = part.req_size
                increment /= 2
                req_sectors = op_func(req_sectors, increment)
                part.req_size = sectorsToSize(req_sectors, sectorSize)
                log.debug("attempting size=%dMB" % part.req_size)
                count += 1
                try:
                    allocatePartitions(disks, partitions)
                except PartitioningError, e:
                    log.debug("attempt at %dMB failed" % part.req_size)
                    op_func = sub
                    last_outcome = False
                else:
                    op_func = add
                    last_good_size = part.req_size
                    last_outcome = True

            if not last_outcome:
                part.req_size = last_good_size
                log.debug("backing up to size=%dMB" % part.req_size)
                try:
                    allocatePartitions(disks, partitions)
                except PartitioningError, e:
                    raise PartitioningError("failed to grow partitions")

    # reset all requests to their original requested size
    for part in partitions:
        if part.exists:
            continue
        part.req_size = part.req_base_size

def hasFreeDiskSpace(storage, exclusiveDisks=None):
    """Returns True if there is at least 100Mb of free usable space in any of
       the disks.  False otherwise.

    """
    # FIXME: This function needs to be implemented.  It is used, at least, by
    # iw/partition_gui.py.  It should be implemented after the new
    # doPartitioning code is commited for fedora 13.  Since it returns True
    # the user will always be able to access the create partition screen. If
    # no partition can be created, the user will go back to the previous
    # storage state after seeing a warning message.
    return True


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
        if not total_free:
            log.debug("vg %s has no free space" % vg.name)
            continue

        log.debug("vg %s: %dMB free ; lvs: %s" % (vg.name, vg.freeSpace,
                                                  [l.lvname for l in vg.lvs]))

        # figure out how much to grow each LV
        grow_amounts = {}
        lv_total = vg.size - total_free
        log.debug("used: %dMB ; vg.size: %dMB" % (lv_total, vg.size))

        # This first loop is to calculate percentage-based growth
        # amounts. These are based on total free space.
        lvs = vg.lvs
        lvs.sort(cmp=lvCompare)
        for lv in lvs:
            if not lv.req_grow or not lv.req_percent:
                continue

            portion = (lv.req_percent * 0.01)
            grow = portion * vg.vgFree
            new_size = lv.req_size + grow
            if lv.req_max_size and new_size > lv.req_max_size:
                grow -= (new_size - lv.req_max_size)

            if lv.format.maxSize and lv.format.maxSize < new_size:
                grow -= (new_size - lv.format.maxSize)

            # clamp growth amount to a multiple of vg extent size
            grow_amounts[lv.name] = vg.align(grow)
            total_free -= grow
            lv_total += grow

        # This second loop is to calculate non-percentage-based growth
        # amounts. These are based on free space remaining after
        # calculating percentage-based growth amounts.

        # keep a tab on space not allocated due to format or requested
        # maximums -- we'll dole it out to subsequent requests
        leftover = 0
        for lv in lvs:
            log.debug("checking lv %s: req_grow: %s ; req_percent: %s"
                      % (lv.name, lv.req_grow, lv.req_percent))
            if not lv.req_grow or lv.req_percent:
                continue

            portion = float(lv.req_size) / float(lv_total)
            grow = portion * total_free
            log.debug("grow is %dMB" % grow)

            todo = lvs[lvs.index(lv):]
            unallocated = reduce(lambda x,y: x+y,
                                 [l.req_size for l in todo
                                  if l.req_grow and not l.req_percent])
            extra_portion = float(lv.req_size) / float(unallocated)
            extra = extra_portion * leftover
            log.debug("%s getting %dMB (%d%%) of %dMB leftover space"
                      % (lv.name, extra, extra_portion * 100, leftover))
            leftover -= extra
            grow += extra
            log.debug("grow is now %dMB" % grow)
            max_size = lv.req_size + grow
            if lv.req_max_size and max_size > lv.req_max_size:
                max_size = lv.req_max_size

            if lv.format.maxSize and max_size > lv.format.maxSize:
                max_size = lv.format.maxSize

            log.debug("max size is %dMB" % max_size)
            max_size = max_size
            leftover += (lv.req_size + grow) - max_size
            grow = max_size - lv.req_size
            log.debug("lv %s gets %dMB" % (lv.name, vg.align(grow)))
            grow_amounts[lv.name] = vg.align(grow)

        if not grow_amounts:
            log.debug("no growable lvs in vg %s" % vg.name)
            continue

        # now grow the lvs by the amounts we've calculated above
        for lv in lvs:
            if lv.name not in grow_amounts.keys():
                continue
            lv.size += grow_amounts[lv.name]

        # now there shouldn't be any free space left, but if there is we
        # should allocate it to one of the LVs
        vg_free = vg.freeSpace
        log.debug("vg %s has %dMB free" % (vg.name, vg_free))
        if vg_free:
            for lv in lvs:
                if not lv.req_grow:
                    continue

                if lv.req_max_size and lv.size == lv.req_max_size:
                    continue

                if lv.format.maxSize and lv.size == lv.format.maxSize:
                    continue

                # first come, first served
                projected = lv.size + vg.freeSpace
                if lv.req_max_size and projected > lv.req_max_size:
                    projected = lv.req_max_size

                if lv.format.maxSize and projected > lv.format.maxSize:
                    projected = lv.format.maxSize

                log.debug("giving leftover %dMB to %s" % (projected - lv.size,
                                                          lv.name))
                lv.size = projected

