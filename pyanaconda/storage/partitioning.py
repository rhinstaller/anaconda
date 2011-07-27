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

def _schedulePVs(storage, disks):
    """ Schedule creation of an lvm pv partition on each disk in disks. """
    # create a separate pv partition for each disk with free space
    devs = []

    # only schedule PVs if there are LV autopart reqs
    if not storage.lvmAutoPart:
        return devs

    for disk in disks:
        if storage.encryptedAutoPart:
            fmt_type = "luks"
            fmt_args = {"escrow_cert": storage.autoPartEscrowCert,
                        "add_backup_passphrase": storage.autoPartAddBackupPassphrase}
        else:
            fmt_type = "lvmpv"
            fmt_args = {}
        part = storage.newPartition(fmt_type=fmt_type,
                                                fmt_args=fmt_args,
                                                grow=True,
                                                disks=[disk])
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

    #
    # First pass is for partitions only. We'll do LVs later.
    #
    for request in storage.autoPartitionRequests:
        if request.asVol and storage.lvmAutoPart:
            continue

        if request.requiredSpace and request.requiredSpace > free:
            continue

        if request.fstype is None:
            request.fstype = storage.defaultFSType
        elif request.fstype in ("prepboot", "efi") and \
                storage.bootLoaderDevice:
            # there should never be a need for more than one of these
            # partitions, so skip them.
            log.info("skipping unneeded stage1 request")
            continue
        elif request.fstype == "biosboot" and storage.anaconda:
            boot_disk = storage.anaconda.bootloader.stage1_drive
            if boot_disk and boot_disk.format.labelType != "gpt":
                # biosboot is only needed for gpt disklabels on non-efi x86
                log.info("skipping bios boot request for msdos disklabel")
                continue

            gpt_check = getattr(storage.anaconda.bootloader,
                                "_gpt_disk_has_bios_boot",
                                None)
            if gpt_check and gpt_check(boot_disk):
                # there's already a bios boot partition on the gpt boot disk
                log.info("skipping bios boot request since boot disk has one")
                continue

        # This is a little unfortunate but let the backend dictate the rootfstype
        # so that things like live installs can do the right thing
        if request.mountpoint == "/" and storage.liveImage:
            request.fstype = storage.liveImage.format.type

        if request.encrypted and storage.encryptedAutoPart:
            fstype = "luks"
        else:
            fstype = request.fstype

        dev = storage.newPartition(fmt_type=fstype,
                                            size=request.size,
                                            grow=request.grow,
                                            maxsize=request.maxSize,
                                            mountpoint=request.mountpoint,
                                            disks=disks,
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

def _scheduleLVs(storage, devs):
    """ Schedule creation of autopart lvm lvs. """
    if not devs:
        return

    if storage.encryptedAutoPart:
        pvs = []
        for dev in devs:
            pv = LUKSDevice("luks-%s" % dev.name,
                            format=getFormat("lvmpv", device=dev.path),
                            size=dev.size,
                            parents=dev)
            pvs.append(pv)
            storage.createDevice(pv)
    else:
        pvs = devs

    # create a vg containing all of the autopart pvs
    vg = storage.newVG(pvs=pvs)
    storage.createDevice(vg)

    initialVGSize = vg.size

    #
    # Convert storage.autoPartitionRequests into Device instances and
    # schedule them for creation.
    #
    # Second pass, for LVs only.
    for request in storage.autoPartitionRequests:
        if not request.asVol or not storage.lvmAutoPart:
            continue

        if request.requiredSpace and request.requiredSpace > initialVGSize:
            continue

        if request.fstype is None:
            request.fstype = storage.defaultFSType

        # This is a little unfortunate but let the backend dictate the rootfstype
        # so that things like live installs can do the right thing
        if request.mountpoint == "/" and storage.liveImage:
            request.fstype = storage.liveImage.format.type

        # FIXME: move this to a function and handle exceptions
        dev = storage.newLV(vg=vg,
                            fmt_type=request.fstype,
                            mountpoint=request.mountpoint,
                            grow=request.grow,
                            maxsize=request.maxSize,
                            size=request.size,
                            singlePV=request.singlePV)

        # schedule the device for creation
        storage.createDevice(dev)


def doAutoPartition(anaconda):
    log.debug("doAutoPartition(%s)" % anaconda)
    log.debug("doAutoPart: %s" % anaconda.storage.doAutoPart)
    log.debug("encryptedAutoPart: %s" % anaconda.storage.encryptedAutoPart)
    log.debug("lvmAutoPart: %s" % anaconda.storage.lvmAutoPart)
    log.debug("clearPartType: %s" % anaconda.storage.config.clearPartType)
    log.debug("clearPartDisks: %s" % anaconda.storage.config.clearPartDisks)
    log.debug("autoPartitionRequests: %s" % anaconda.storage.autoPartitionRequests)
    log.debug("storage.disks: %s" % [d.name for d in anaconda.storage.disks])
    log.debug("storage.partitioned: %s" % [d.name for d in anaconda.storage.partitioned])
    log.debug("all names: %s" % [d.name for d in anaconda.storage.devices])
    if anaconda.dir == DISPATCH_BACK:
        return

    disks = []
    devs = []

    if anaconda.storage.doAutoPart:
        clearPartitions(anaconda.storage, bootloader=anaconda.bootloader)
        # update the bootloader's drive list to add disks which have their
        # whole disk format replaced by a disklabel. Make sure to keep any
        # previous boot order selection from clearpart_gui or kickstart
        anaconda.bootloader.clear_drive_list()

    if anaconda.storage.doAutoPart:
        disks = _getCandidateDisks(anaconda.storage)
        devs = _schedulePVs(anaconda.storage, disks)

        if disks == []:
            if anaconda.ksdata:
                msg = _("Could not find enough free space for automatic "
                        "partitioning.  Press 'OK' to exit the installer.")
            else:
                msg = _("Could not find enough free space for automatic "
                        "partitioning, please use another partitioning method.")

            anaconda.intf.messageWindow(_("Error Partitioning"), msg,
                                        custom_icon='error')

            if anaconda.ksdata:
                sys.exit(0)

            anaconda.storage.reset()
            return DISPATCH_BACK

        _schedulePartitions(anaconda.storage, disks)

    # run the autopart function to allocate and grow partitions
    try:
        doPartitioning(anaconda.storage, bootloader=anaconda.bootloader)

        if anaconda.storage.doAutoPart:
            _scheduleLVs(anaconda.storage, devs)

        # grow LVs
        growLVM(anaconda.storage)
    except PartitioningWarning as msg:
        if not anaconda.ksdata:
            anaconda.intf.messageWindow(_("Warnings During Automatic "
                                          "Partitioning"),
                           _("Following warnings occurred during automatic "
                           "partitioning:\n\n%s") % (msg,),
                           custom_icon='warning')
        else:
            log.warning(msg)
    except PartitioningError as msg:
        # restore drives to original state
        anaconda.storage.reset()

        extra = ""
        if anaconda.ksdata:
            extra = _("\n\nPress 'OK' to exit the installer.")
        else:
            anaconda.dispatch.request_steps_gently("partition")
        anaconda.intf.messageWindow(_("Error Partitioning"),
               _("Could not allocate requested partitions: \n\n"
                 "%(msg)s.%(extra)s") % {'msg': msg, 'extra': extra},
               custom_icon='error')

        if anaconda.ksdata:
            sys.exit(0)
        else:
            return DISPATCH_BACK

    # now do a full check of the requests
    (errors, warnings) = anaconda.storage.sanityCheck()
    if warnings:
        for warning in warnings:
            log.warning(warning)
    if errors:
        errortxt = "\n".join(errors)
        if anaconda.ksdata:
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
        if anaconda.ksdata:
            anaconda.intf.messageWindow(_("Unrecoverable Error"),
                               _("The system will now reboot."))
            sys.exit(0)
        anaconda.storage.reset()
        return DISPATCH_BACK

def shouldClear(device, clearPartType, clearPartDisks=None):
    if clearPartType not in [CLEARPART_TYPE_LINUX, CLEARPART_TYPE_ALL]:
        return False

    if isinstance(device, PartitionDevice):
        # Never clear the special first partition on a Mac disk label, as that
        # holds the partition table itself.
        # Something similar for the third partition on a Sun disklabel.
        if device.disk.format.partedDisk.type == "mac" and \
           device.partedPartition.number == 1:
            return False
        elif device.disk.format.labelType == "sun" and \
             device.partedPartition.number == 3:
            return False

        # If we got a list of disks to clear, make sure this one's on it
        if clearPartDisks and device.disk.name not in clearPartDisks:
            return False

        # We don't want to fool with extended partitions, freespace, &c
        if device.partType not in [parted.PARTITION_NORMAL,
                                   parted.PARTITION_LOGICAL]:
            return False

        if clearPartType == CLEARPART_TYPE_LINUX and \
           not device.format.linuxNative and \
           not device.getFlag(parted.PARTITION_LVM) and \
           not device.getFlag(parted.PARTITION_RAID) and \
           not device.getFlag(parted.PARTITION_SWAP):
            return False
    elif device.isDisk and not device.partitioned:
        # If we got a list of disks to clear, make sure this one's on it
        if clearPartDisks and device.name not in clearPartDisks:
            return False

        # Never clear disks with hidden formats
        if device.format.hidden:
            return False

        if clearPartType == CLEARPART_TYPE_LINUX and \
           not device.format.linuxNative:
            return False

    # Don't clear devices holding install media.
    if device.protected:
        return False

    return True

def clearPartitions(storage, bootloader=None):
    """ Clear partitions and dependent devices from disks.

        Arguments:

            storage -- a storage.Storage instance

        Keyword arguments:

            bootloader -- a BootLoader instance

        NOTES:

            - Needs some error handling, especially for the parted bits.

    """
    if storage.config.clearPartType in (None, CLEARPART_TYPE_NONE):
        # not much to do
        return

    if not hasattr(storage.platform, "diskLabelTypes"):
        raise StorageError("can't clear partitions without platform data")

    # we are only interested in partitions that physically exist
    partitions = [p for p in storage.partitions if p.exists]
    # Sort partitions by descending partition number to minimize confusing
    # things like multiple "destroy sda5" actions due to parted renumbering
    # partitions. This can still happen through the UI but it makes sense to
    # avoid it where possible.
    partitions.sort(key=lambda p: p.partedPartition.number, reverse=True)
    for part in partitions:
        log.debug("clearpart: looking at %s" % part.name)
        if not shouldClear(part, storage.config.clearPartType, storage.config.clearPartDisks):
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

    for disk in [d for d in storage.disks if d not in storage.partitioned]:
        # clear any whole-disk formats that need clearing
        if shouldClear(disk, storage.config.clearPartType, storage.config.clearPartDisks):
            log.debug("clearing %s" % disk.name)
            devices = storage.deviceDeps(disk)
            while devices:
                log.debug("devices to remove: %s" % ([d.name for d in devices],))
                leaves = [d for d in devices if d.isleaf]
                log.debug("leaves to remove: %s" % ([d.name for d in leaves],))
                for leaf in leaves:
                    storage.destroyDevice(leaf)
                    devices.remove(leaf)

            destroy_action = ActionDestroyFormat(disk)
            labelType = storage.platform.bestDiskLabelType(disk)
            newLabel = getFormat("disklabel", device=disk.path,
                                 labelType=labelType)
            create_action = ActionCreateFormat(disk, format=newLabel)
            storage.devicetree.registerAction(destroy_action)
            storage.devicetree.registerAction(create_action)

    # now remove any empty extended partitions
    removeEmptyExtendedPartitions(storage)

    # make sure that the the boot device has the correct disklabel type if
    # we're going to completely clear it.
    for disk in storage.partitioned:
        if not bootloader or not bootloader.stage1_drive:
            break

        if disk != bootloader.stage1_drive:
            continue

        if storage.config.clearPartType != CLEARPART_TYPE_ALL or \
           (storage.config.clearPartDisks and
            disk.name not in storage.config.clearPartDisks):
            continue

        # don't reinitialize the disklabel if the disk contains install media
        # or pvs from inconsistent vgs
        if filter(lambda p: p.dependsOn(disk), storage.protectedDevices):
            continue

        nativeLabelType = storage.platform.bestDiskLabelType(disk)
        if disk.format.labelType == nativeLabelType:
            continue

        magic_partitions = {"mac": 1, "sun": 3}
        if disk.format.labelType in magic_partitions:
            number = magic_partitions[disk.format.labelType]
            # remove the magic partition
            for part in storage.partitions:
                if part.disk == disk and part.partedPartition.number == number:
                    log.debug("clearing %s" % part.name)
                    # We can't schedule the magic partition for removal
                    # because parted will not allow us to remove it from the
                    # disk. Still, we need it out of the devicetree.
                    storage.devicetree._removeDevice(part, moddisk=False)

        destroy_action = ActionDestroyFormat(disk)
        newLabel = getFormat("disklabel", device=disk.path,
                             labelType=nativeLabelType)
        create_action = ActionCreateFormat(disk, format=newLabel)
        storage.devicetree.registerAction(destroy_action)
        storage.devicetree.registerAction(create_action)

def removeEmptyExtendedPartitions(storage):
    for disk in storage.partitioned:
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
            raise PartitioningError("unable to allocate aligned partition")

    new_geom = parted.Geometry(device=disklabel.partedDevice,
                               start=start,
                               end=end)

    max_length = disklabel.partedDisk.maxPartitionLength
    if max_length and new_geom.length > max_length:
        raise PartitioningError("requested size exceeds maximum allowed")

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

def doPartitioning(storage, bootloader=None):
    """ Allocate and grow partitions.

        When this function returns without error, all PartitionDevice
        instances must have their parents set to the disk they are
        allocated on, and their partedPartition attribute set to the
        appropriate parted.Partition instance from their containing
        disk. All req_xxxx attributes must be unchanged.

        Arguments:

            storage - Main anaconda Storage instance

        Keyword/Optional Arguments:

            bootloader - BootLoader instance

    """
    if not hasattr(storage.platform, "diskLabelTypes"):
        raise StorageError("can't allocate partitions without platform data")

    disks = storage.partitioned
    if storage.config.exclusiveDisks:
        disks = [d for d in disks if d.name in storage.config.exclusiveDisks]

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

    try:
        storage.bootDevice.req_bootable = True
    except AttributeError:
        # there's no stage2 device. hopefully it's temporary.
        pass

    removeNewPartitions(disks, partitions)
    free = getFreeRegions(disks)
    allocatePartitions(storage, disks, partitions, free, bootloader=bootloader)
    growPartitions(disks, partitions, free)

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

    # make sure the stage1_device gets updated
    if storage.anaconda:
        storage.anaconda.bootloader.stage1_device = None

def allocatePartitions(storage, disks, partitions, freespace, bootloader=None):
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
        if _part.disk:
            # we have a already selected a disk for this request
            req_disks = [_part.disk]
        elif _part.req_disks:
            # use the requested disk set
            req_disks = _part.req_disks
        else:
            # no disks specified means any disk will do
            req_disks = disks

        # sort the disks, making sure the boot disk is first
        req_disks.sort(key=lambda d: d.name, cmp=storage.compareDisks)
        boot_index = None
        for disk in req_disks:
            if bootloader and disk == bootloader.stage1_drive:
                boot_index = req_disks.index(disk)

        if boot_index is not None and len(req_disks) > 1:
            boot_disk = req_disks.pop(boot_index)
            req_disks.insert(0, boot_disk)

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

            problem = _part.checkSize()
            if problem < 0:
                raise PartitioningError("partition is too small for %s formatting "
                                        "(allowable size is %d MB to %d MB)"
                                        % (problem, _part.format.name,
                                           _part.format.minSize,
                                           _part.format.maxSize))
            elif problem > 0:
                raise PartitioningError("partition is too large for %s formatting "
                                        "(allowable size is %d MB to %d MB)"
                                        % (problem, _part.format.name,
                                           _part.format.minSize,
                                           _part.format.maxSize))

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
                if _part.req_grow:
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
                            temp_part = addPartition(disklabel,
                                                     best,
                                                     new_part_type,
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

                    log.debug("total growth: %d sectors" % new_growth)

                    # update the chosen free region unless the previous
                    # choice yielded greater total growth
                    if new_growth < growth:
                        log.debug("keeping old free: %d < %d" % (new_growth,
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
            raise PartitioningError("not enough free space on disks")

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
                raise PartitioningError("not enough free space after "
                                        "creating extended partition")

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
        self.done = not device.req_grow     # can we grow this request more?
        self.base = 0                       # base sectors

    @property
    def growable(self):
        """ True if this request is growable. """
        return self.device.req_grow

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

    def growRequests(self):
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
            log.debug("%d requests and %d (%dMB) left in chunk" %
                        (self.remaining, self.pool, self.lengthToSize(self.pool)))
            for p in self.requests:
                if p.done:
                    continue

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
        s += ("start = %(start)d  end = %(end)d\n"
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
            raise ValueError("DiskChunk requests must be of type "
                             "PartitionRequest")

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
                raise PartitioningError("partitions allocated outside "
                                        "disklabel limits")

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
        super(VGChunk, self).__init__(self.vg.extents, requests=requests)

    def addRequest(self, req):
        """ Add a Request to this chunk. """
        if not isinstance(req, LVRequest):
            raise ValueError("VGChunk requests must be of type "
                             "LVRequest")

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

def growPartitions(disks, partitions, free):
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

    log.debug("growable partitions are %s" % [p.name for p in all_growable])

    for disk in disks:
        log.debug("growing partitions on %s" % disk.name)
        sector_size = disk.format.partedDevice.sectorSize

        # find any extended partition on this disk
        extended_geometry = getattr(disk.format.extendedPartition,
                                    "geometry",
                                    None)  # parted.Geometry

        # list of free space regions on this disk prior to partition allocation
        disk_free = [f for f in free if f.device.path == disk.path]
        if not disk_free:
            log.debug("no free space on %s" % disk.name)
            continue

        chunks = getDiskChunks(disk, partitions, disk_free)
        log.debug("disk %s has %d chunks" % (disk.name, len(chunks)))
        # grow the partitions in each chunk as a group
        for chunk in chunks:
            if not chunk.hasGrowable:
                # no growable partitions in this chunk
                continue

            chunk.growRequests()

            # recalculate partition geometries
            disklabel = disk.format
            start = chunk.geometry.start
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
            raise PartitioningError("not enough space for LVM requests")
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

