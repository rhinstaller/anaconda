#
# autopart.py - auto partitioning logic
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import parted
import math
from fsset import *
from partitioning import *

PARTITION_FAIL = -1
PARTITION_SUCCESS = 0

def findFreespace(diskset):
    free = {}
    for drive in diskset.disks.keys():
        disk = diskset.disks[drive]
        free[drive] = []
        part = disk.next_partition()
        while part:
            if part.type & parted.PARTITION_FREESPACE:
                free[drive].append(part)
            part = disk.next_partition(part)
    return free


def bestPartType(disk, request):
    numPrimary = len(get_primary_partitions(disk))
    if numPrimary == 4:
        # raise an error?
        return PARTITION_FAIL
    if request.primary:
        return parted.PARTITION_PRIMARY
    if numPrimary == 3 and not disk.extended_partition:
        return parted.PARTITION_EXTENDED
    return parted.PARTITION_PRIMARY


# first step of partitioning voodoo
# partitions with a specific start and end cylinder requested are
# placed where they were asked to go
def fitConstrained(diskset, requests, primOnly=0):
    for request in requests.requests:
        if request.type != REQUEST_NEW:
            continue
        if request.device:
            continue
        if primOnly and not request.primary:
            continue
        if request.drive and (request.start != None):
            if not request.end and not request.size:
                raise PartitioningError, "Tried to create constrained partition without size or end"

            fsType = request.fstype.getPartedFileSystemType()
            disk = diskset.disks[request.drive]
            if not disk: # this shouldn't happen
                raise PartitioningError, "Selected to put partition on non-existent disk!"

            startSec = start_cyl_to_sector(disk.dev, request.start)

            if request.end:
                endCyl = request.end
            elif request.size:
                endCyl = end_sector_to_cyl(disk.dev, ((1024 * 1024 * request.size) / disk.dev.sector_size) + startSec)
            
            endSec = end_cyl_to_sector(disk.dev, endCyl)

            # XXX need to check overlaps properly here
            if startSec < 0:
                startSec = 0L

            if disk.type.check_feature(parted.DISK_TYPE_EXTENDED) and disk.extended_partition:
                
                if (disk.extended_part.geom.start < startSec) and (disk.extended_part.geom.end > endSec):
                    partType = parted.PARTITION_LOGICAL
                    if request.primary: # they've required a primary and we can't do it
                        return PARTITION_FAIL
            else:
                # XXX need a better way to do primary vs logical stuff
                ret = bestPartType(disk, request)
                if ret == PARTITION_FAIL:
                    return ret
                if ret == parted.PARTITION_PRIMARY:
                    partType = parted.PARTITION_PRIMARY
                elif ret == parted.PARTITION_EXTENDED:
                    newp = disk.partition_new(parted.PARTITION_EXTENDED, None, startSec, endSec)
                    constraint = disk.constraint_any()
                    disk.maximize_partition (newp, constraint)
                    partType = parted.PARTITION_LOGICAL
                else: # shouldn't get here
                    raise PartitioningError, "Impossible partition type to create"
            newp = disk.partition_new (partType, fsType, startSec, endSec)
            constraint = disk.constraint_any ()
            try:
                disk.add_partition (newp, constraint)
                status = 1
            except parted.error, msg:
                return PARTITION_FAIL
#                raise PartitioningError, msg
            for flag in request.fstype.getPartedPartitionFlags():
                if not newp.is_flag_available(flag):
                    raise PartitioningError, ("requested FileSystemType needs "
                                           "a flag that is not available.")
                newp.set_flag(flag, 1)
            request.device = PartedPartitionDevice(newp).getDevice()
            request.currentDrive = request.drive

    return PARTITION_SUCCESS


# fit partitions of a specific size with or without a specific disk
# into the freespace
def fitSized(diskset, requests, primOnly = 0):
    todo = {}

    for request in requests.requests:
        if request.type != REQUEST_NEW:
            continue
        if request.device:
            continue
        if primOnly and not request.primary:
            continue
        if not request.drive:
            request.drive = diskset.disks.keys()
        if type(request.drive) != type([]):
            request.drive = [ request.drive ]
        if not todo.has_key(len(request.drive)):
            todo[len(request.drive)] = [ request ]
        else:
            todo[len(request.drive)].append(request)


    number = todo.keys()
    number.sort()
    free = findFreespace(diskset)

    for num in number:
        for request in todo[num]:
            largestPart = (0, None)
            request.drive.sort()
            for drive in request.drive:
                disk = diskset.disks[drive]        

                for part in free[drive]:
                    partSize = getPartSize(part)
                    if partSize >= request.requestSize and partSize > largestPart[0]:
                        if not request.primary or (not part.type & parted.PARTITION_LOGICAL):
                            largestPart = (partSize, part)

            if not largestPart[1]:
                return PARTITION_FAIL
#                raise PartitioningError, "Can't fulfill request for partition: \n%s" %(request)

            freespace = largestPart[1]
            disk = freespace.geom.disk
            startSec = freespace.geom.start + 1
            endSec = startSec + ((request.requestSize * 1024L * 1024L) / disk.dev.sector_size) - 1

            if endSec > freespace.geom.end:
                endSec = freespace.geom.end
            if startSec < freespace.geom.start:
                startSec = freespace.geom.start

            if freespace.type & parted.PARTITION_LOGICAL:
                partType = parted.PARTITION_LOGICAL
            else:
                # XXX need a better way to do primary vs logical stuff
                ret = bestPartType(disk, request)
                if ret == PARTITION_FAIL:
                    return ret
                if ret == parted.PARTITION_PRIMARY:
                    partType = parted.PARTITION_PRIMARY
                elif ret == parted.PARTITION_EXTENDED:
                    newp = disk.partition_new(parted.PARTITION_EXTENDED, None, startSec, endSec)
                    constraint = disk.constraint_any()
                    disk.add_partition(newp, constraint)
                    disk.maximize_partition (newp, constraint)
                    partType = parted.PARTITION_LOGICAL
                else: # shouldn't get here
                    raise PartitioningError, "Impossible partition to create"

            fsType = request.fstype.getPartedFileSystemType()

            newp = disk.partition_new (partType, fsType, startSec, endSec)
            constraint = disk.constraint_any ()
            try:
                disk.add_partition (newp, constraint)
            except parted.error, msg:
                raise PartitioningError, msg
            for flag in request.fstype.getPartedPartitionFlags():
                if not newp.is_flag_available(flag):
                    raise PartitioningError, ("requested FileSystemType needs "
                                           "a flag that is not available.")
                newp.set_flag(flag, 1)
            request.device = PartedPartitionDevice(newp).getDevice()
            drive = newp.geom.disk.dev.path[5:]
            request.currentDrive = drive
            free[drive].remove(freespace)
            part = disk.next_partition(newp)
            if part and part.type & parted.PARTITION_FREESPACE:
                free[drive].append(part)
    return PARTITION_SUCCESS


# grow partitions
def growParts(diskset, requests):
#    print "growing"
    newRequest = requests.copy()

    free = findFreespace(diskset)
    freeSize = {}

    # find out the amount of free space on each drive
    for key in free.keys():
        if len(free[key]) == 0:
            del free[key]
            continue
        freeSize[key] = 0
        for part in free[key]:
            freeSize[key] = freeSize[key] + getPartSize(part)

    print freeSize

    # find growable partitions and find out the size of the growable parts
    growable = {}
    growSize = {}
    for request in newRequest.requests:
        if request.grow:
            if not growable.has_key(request.currentDrive):
                growable[request.currentDrive] = [ request ]
                growSize[request.currentDrive] = request.size
            else:
                growable[request.currentDrive].append(request)
                growSize[request.currentDrive] = growSize[request.currentDrive] + request.requestSize

    # there aren't any drives with growable partitions, this is easy!
    if not growable.keys():
        return PARTITION_SUCCESS

    for drive in growable.keys():
        # no free space on this drive, so can't grow any of its parts
        if not free.has_key(drive):
            continue

        # process each request
        for request in growable[drive]:
            percent = request.size / (growSize[drive] * 1.0)
            
            request.drive = request.currentDrive
            
            max = int(percent * freeSize[drive]) + request.size
            if max > request.maxSize:
                max = request.maxSize
            if max > request.fstype.getMaxSize():
                max = request.fstype.getMaxSize()

            min = request.requestSize
            diff = max - min
            cur = max - (diff / 2)
            lastDiff = 0

            # binary search
            while (max != min) and (lastDiff != diff):
                request.requestSize = cur

                # try adding
                ret = processPartitioning(diskset, newRequest)
#                print diskset.diskState()

                if ret == PARTITION_SUCCESS:
                    min = cur
                else:
                    max = cur

                lastDiff = diff
                diff = max - min
                cur = max - (diff / 2)


            # we could have failed on the last try, in which case we
            # should go back to the smaller size
            if ret == PARTITION_FAIL:
                request.requestSize = min
                # XXX this can't fail (?)
                processPartitioning(diskset, newRequest)

    return PARTITION_SUCCESS


def setPreexistParts(diskset, requests):
    for request in requests:
        if request.type != REQUEST_PREEXIST:
            continue
        disk = diskset.disks[request.drive]
        part = disk.next_partition()
        while part:
            if part.geom.start == request.start and part.geom.end == request.end:
                request.device = get_partition_name(part)
                break
            part = disk.next_partition(part)


def deletePart(diskset, delete):
    disk = diskset.disks[delete.drive]
    part = disk.next_partition()
    while part:
        if part.geom.start == delete.start and part.geom.end == delete.end:
            disk.delete_partition(part)
            return
        part = disk.next_partition(part)
    

def processPartitioning(diskset, requests):
    # reset disk to original state
    diskset.refreshDevices()
    for request in requests.requests:
        if request.type == REQUEST_NEW:
            request.device = None

    # XXX - handle delete requests
    for delete in requests.deletes:
        deletePart(diskset, delete)

    setPreexistParts(diskset, requests.requests)

    # sort requests by size
    requests.sortRequests()
    
    # partitioning algorithm in simplistic terms
    #
    # we want to allocate partitions such that the most specifically
    # spelled out partitions get what they want first in order to ensure
    # they don't get preempted.  first conflict found returns an error
    # which must be handled by the caller by saying that the partition
    # add is impossible (XXX can we get an impossible situation after delete?)
    #
    # potentially confusing terms
    # type == primary vs logical
    #
    # order to allocate:
    # start and end cylinders given (note that start + size & !grow is equivalent)
    # drive, partnum
    # drive, type
    # drive
    # priority partition (/boot or /)
    # size

    # run through with primary only constraints first
    ret = fitConstrained(diskset, requests, 1)
    if ret == PARTITION_FAIL:
        return (ret, "Could not allocate cylinder-based partitions as primary partitions")

    ret = fitSized(diskset, requests, 1)
    if ret == PARTITION_FAIL:
        return (ret, "Could not allocate partitions as primary partitions")

    ret = fitConstrained(diskset, requests)
    if ret == PARTITION_FAIL:
        return (ret, "Could not allocate cylinder-based partitions")

    ret = fitSized(diskset, requests)
    if ret == PARTITION_FAIL:
        return (ret, "Could not allocate partitions")

    for request in requests.requests:
        # set the unique identifier for raid devices
        if request.type == REQUEST_RAID and not request.device:
            request.device = str(requests.maxcontainer)
            requests.maxcontainer = requests.maxcontainer + 1

        if request.type == REQUEST_RAID:
            request.size = get_raid_device_size(request)
        
        if not request.device:
#            return PARTITION_FAIL
            raise PartitioningError, "Unsatisfied partition request\n%s" %(request)

    return (PARTITION_SUCCESS, "success")

##     print "disk layout after everything is done"
##     print diskset.diskState()


def doPartitioning(diskset, requests):
    for request in requests.requests:
        request.requestSize = request.size

    (ret, msg) = processPartitioning(diskset, requests)

    if ret == PARTITION_FAIL:
        raise PartitioningError, "Partitioning failed: %s" %(msg)

    ret = growParts(diskset, requests)

    if ret == PARTITION_SUCCESS:
        return

    raise PartitioningError, "Growing partitions failed"
    
