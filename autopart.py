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
import fsset
from partitioning import *
from constants import *
from translate import _, N_

PARTITION_FAIL = -1
PARTITION_SUCCESS = 0

CLEARPART_TYPE_LINUX = 1
CLEARPART_TYPE_ALL   = 2
CLEARPART_TYPE_NONE  = 3

def printNewRequestsCyl(diskset, newRequest):
    for req in newRequest.requests:
        if req.type != REQUEST_NEW:
            continue
        
        part = get_partition_by_name(diskset.disks, req.device)
        print req
        print "Start Cyl:%s    End Cyl: %s" % (start_sector_to_cyl(part.geom.disk.dev, part.geom.start),
                                 end_sector_to_cyl(part.geom.disk.dev, part.geom.end))

def printFreespaceitem(part):
    return get_partition_name(part), part.geom.start, part.geom.end, getPartSizeMB(part)

def printFreespace(free):
    print "Free Space Summary:"
    for drive in free.keys():
        print "On drive ",drive
        for part in free[drive]:
            print "Freespace:", printFreespaceitem(part)
        

def findFreespace(diskset):
    free = {}
    for drive in diskset.disks.keys():
        disk = diskset.disks[drive]
        free[drive] = []
        part = disk.next_partition()
        while part:
            if part.type & parted.PARTITION_FREESPACE:
#                print "found free", printFreespaceitem(part)
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

class partlist:
    def __init__(self):
        self.parts = []

    def __str__(self):
        retval = ""
        for p in self.parts:
            retval = retval + "\t%s %s %s\n" % (get_partition_name(p), get_partition_file_system_type(p), getPartSizeMB(p))

        return retval


# first step of partitioning voodoo
# partitions with a specific start and end cylinder requested are
# placed where they were asked to go
def fitConstrained(diskset, requests, primOnly=0, newParts = None):
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
            disk = diskset.disks[request.drive[0]]
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
                    newParts.parts.append(newp)
                    requests.nextUniqueID = requests.nextUniqueID + 1
                    partType = parted.PARTITION_LOGICAL
                else: # shouldn't get here
                    raise PartitioningError, "Impossible partition type to create"
            newp = disk.partition_new (partType, fsType, startSec, endSec)
            constraint = disk.constraint_any ()
            try:
                disk.add_partition (newp, constraint)

            except parted.error, msg:
                return PARTITION_FAIL
#                raise PartitioningError, msg
            for flag in request.fstype.getPartedPartitionFlags():
                if not newp.is_flag_available(flag):
                    raise PartitioningError, ("requested FileSystemType needs "
                                           "a flag that is not available.")
                newp.set_flag(flag, 1)
            request.device = fsset.PartedPartitionDevice(newp).getDevice()
            request.currentDrive = request.drive[0]
            newParts.parts.append(newp)

    return PARTITION_SUCCESS


# get the list of the "best" drives to try to use...
# if currentdrive is set, use that, else use the drive list, or use
# all the drives
def getDriveList(request, diskset):
    if request.currentDrive:
        drives = request.currentDrive
    elif request.drive:
        drives = request.drive
    else:
        drives = diskset.disks.keys()

    if not type(drives) == type([]):
        drives = [ drives ]

    return drives
    

# fit partitions of a specific size with or without a specific disk
# into the freespace
def fitSized(diskset, requests, primOnly = 0, newParts = None):
    todo = {}

    for request in requests.requests:
        if request.type != REQUEST_NEW:
            continue
        if request.device:
            continue
        if primOnly and not request.primary:
            continue
        drives = getDriveList(request, diskset)
        if not todo.has_key(len(drives)):
            todo[len(drives)] = [ request ]
        else:
            todo[len(drives)].append(request)

    number = todo.keys()
    number.sort()
    free = findFreespace(diskset)

    for num in number:
        for request in todo[num]:
#            print "\nInserting ->",request
            largestPart = (0, None)
            drives = getDriveList(request, diskset)
            drives.sort()
#            print "Trying drives to find best free space out of", free
            for drive in drives:
#                print "Trying drive", drive
                disk = diskset.disks[drive]

                for part in free[drive]:
#                    print "Trying partition", printFreespaceitem(part)
                    partSize = getPartSize(part)
                    if partSize >= request.requestSize and partSize > largestPart[0]:
                        if not request.primary or (not part.type & parted.PARTITION_LOGICAL):
                            largestPart = (partSize, part)

            if not largestPart[1]:
                return PARTITION_FAIL
#                raise PartitioningError, "Can't fulfill request for partition: \n%s" %(request)

#            print "largestPart is",largestPart
            freespace = largestPart[1]
            disk = freespace.geom.disk
            startSec = freespace.geom.start + 1
            endSec = startSec + long(((request.requestSize * 1024L * 1024L) / disk.dev.sector_size)) - 1

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
                    newParts.parts.append(newp)
                    requests.nextUniqueID = requests.nextUniqueID + 1
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

            request.device = fsset.PartedPartitionDevice(newp).getDevice()
            drive = newp.geom.disk.dev.path[5:]
            request.currentDrive = drive

            newParts.parts.append(newp)
            free = findFreespace(diskset)

    return PARTITION_SUCCESS


# grow partitions
def growParts(diskset, requests, newParts):

    # returns free space segments for each drive IN SECTORS
    def getFreeSpace(diskset):
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

        return (free, freeSize)

    ####
    # start of growParts
    ####
    newRequest = requests.copy()

#    print "new requests"
#    printNewRequestsCyl(diskset, requests)
#    print "orig requests"
#    printNewRequestsCyl(diskset, newRequest)
#    print "\n\n\n"
    
    (free, freeSize) = getFreeSpace(diskset)

    # find growable partitions
    growable = {}
    growSize = {}
    origSize = {}
    for request in newRequest.requests:
        if request.type != REQUEST_NEW or not request.grow:
            continue

        origSize[request.uniqueID] = request.requestSize
        if not growable.has_key(request.currentDrive):
            growable[request.currentDrive] = [ request ]
        else:
            growable[request.currentDrive].append(request)

    # there aren't any drives with growable partitions, this is easy!
    if not growable.keys():
        return PARTITION_SUCCESS
    
#    print "new requests before looping"
#    printNewRequestsCyl(diskset, requests)
#    print "\n\n\n"

    # loop over all drives, grow all growable partitions one at a time
    grownList = []
    for drive in growable.keys():
        # no free space on this drive, so can't grow any of its parts
        if not free.has_key(drive):
            continue

        # process each request
        # grow all growable partitions on this drive until all can grow no more
        donegrowing = 0
        outer_iter = 0
        lastFreeSize = None
        while not donegrowing and outer_iter < 20:
            # if less than one sector left, we're done
#            if drive not in freeSize.keys() or freeSize[drive] == lastFreeSize:
            if drive not in freeSize.keys():
#                print "leaving outer loop because no more space on %s\n\n" % drive
                break
##             print "\nAt start:"
##             print drive,freeSize.keys()
##             print freeSize[drive], lastFreeSize
##             print "\n"

##             print diskset.diskState()
            
            
            outer_iter = outer_iter + 1
            donegrowing = 1

            # pull out list of requests we want to grow on this drive
            growList = growable[drive]

            sector_size = diskset.disks[drive].dev.sector_size
            
            # sort in order of request size, consider biggest first
            n = 0
            while n < len(growList):
                for request in growList:
                    if request.size < growList[n].size:
                        tmp = growList[n]
                        index = growList.index(request)
                        growList[n] = request
                        growList[index] = tmp
                n = n + 1

            # recalculate the total size of growable requests for this drive
            # NOTE - we add up the ORIGINAL requested sizes, not grown sizes
            growSize[drive] = 0
            for request in growList:
                if request.uniqueID in grownList:
                    continue
                growSize[drive] = growSize[drive] + origSize[request.uniqueID]

            # loop over requests for this drive
            for request in growList:
                # skip if we've finished growing this request
                if request.uniqueID in grownList:
                    continue

                if drive not in freeSize.keys():
                    donegrowing = 1
#                    print "leaving inner loop because no more space on %s\n\n" % drive
                    break

#                print "\nprocessing ID",request.uniqueID, request.mountpoint
#                print "growSize, freeSize = ",growSize[drive], freeSize[drive]

                donegrowing = 0

                # get amount of space actually used by current allocation
                part = get_partition_by_name(diskset.disks, request.device)
                startSize = getPartSize(part)

                # compute fraction of freespace which to give to this
                # request. Weight by original request size
                percent = origSize[request.uniqueID] / (growSize[drive] * 1.0)
                maxsect = long(percent * freeSize[drive]) + startSize

#                print "percent, maxsect, free", percent,maxsect,freeSize[drive]
#                print "max is ",maxsect
                imposedMax = 0
                if request.maxSize: 
                    maxFSSize = request.maxSize*1024.0*1024.0/sector_size
                    if maxsect > maxFSSize:
                        maxsect = long(maxFSSize)
                        imposedMax = 1

                maxuserSize = request.fstype.getMaxSize()*1024.0*1024.0/sector_size
                if maxsect > maxuserSize:
                    maxsect = long(maxuserSize)
                    imposedMax = 1

#                print "freesize, max = ",freeSize[drive],maxsect
#                print "startsize = ",startSize

                min = startSize
                max = maxsect
                diff = max - min
                cur = max - (diff / 2)
                lastDiff = 0

                # binary search
#                print "start min, max, cur, diffs = ",min,max,cur,diff,lastDiff
                inner_iter = 0
                while (max != min) and (lastDiff != diff) and (inner_iter < 2000):
#                    printNewRequestsCyl(diskset, newRequest)

                    # XXX need to request in sectors preferably, more accurate
                    request.requestSize = (cur*sector_size)/1024.0/1024.0

                    # try adding
                    (ret, msg) = processPartitioning(diskset, newRequest, newParts)
                    if ret == PARTITION_SUCCESS:
                        min = cur
                    else:
                        max = cur

                    lastDiff = diff
                    diff = max - min
                    cur = max - (diff / 2)

                    inner_iter = inner_iter + 1
##                     print diskset.diskState()
##                     print "sizes",min,max,diff,lastDiff

#                freeSize[drive] = freeSize[drive] - (min - startSize)
#                print "shrinking freeSize to ",freeSize[drive], lastFreeSize
#                if freeSize[drive] < 0:
#                    print "freesize < 0!"
#                    freeSize[drive] = 0
                
                # we could have failed on the last try, in which case we
                # should go back to the smaller size
                if ret == PARTITION_FAIL:
#                    print "growing finally failed at size", min
                    request.requestSize = min*sector_size/1024.0/1024.0
                    # XXX this can't fail (?)
                    (retxxx, msgxxx) = processPartitioning(diskset, newRequest, newParts)

#                print "end min, max, cur, diffs = ",min,max,cur,diff,lastDiff
#                print "%s took %s loops" % (request.mountpoint, inner_iter)
                lastFreeSize = freeSize[drive]
                (free, freeSize) = getFreeSpace(diskset)
#                printFreespace(free)

                if ret == PARTITION_FAIL or (max == maxsect and imposedMax):
#                    print "putting ",request.uniqueID,request.mountpoint," in grownList"
                    grownList.append(request.uniqueID)
                    growSize[drive] = growSize[drive] - origSize[request.uniqueID]
                    if growSize[drive] < 0:
#                        print "growsize < 0!"
                        growSize[drive] = 0

    return PARTITION_SUCCESS


def setPreexistParts(diskset, requests, newParts):
    for request in requests:
        if request.type != REQUEST_PREEXIST or request.type != REQUEST_PROTECTED:
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

def processPartitioning(diskset, requests, newParts):
    # collect a hash of all the devices that we have created extended
    # partitions on.  When we remove these extended partitions the logicals
    # (all of which we created) will be destroyed along with it.
    extendeds = {}

    for part in newParts.parts:
        if part.type == parted.PARTITION_EXTENDED:
            extendeds[part.geom.disk.dev.path] = None

    # Go through the list again and check for each logical partition we have.
    # If we created the extended partition on the same device as the logical
    # partition, remove it from out list, as it will be cleaned up for us
    # when the extended partition gets removed.
    for part in newParts.parts:
        if (part.type & parted.PARTITION_LOGICAL
            and extendeds.has_key(part.geom.disk.dev.path)):
            newParts.parts.remove(part)

    # Finally, remove all of the partitions we added in the last try from
    # the disks.  We'll start again from there.
    for part in newParts.parts:
        disk = part.geom.disk
        if part.type & parted.PARTITION_LOGICAL:
            del part
            continue
        disk.delete_partition(part)
        del part
    newParts.parts = []

    for request in requests.requests:
        if request.type == REQUEST_NEW:
            request.device = None

    setPreexistParts(diskset, requests.requests, newParts)
    
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
    ret = fitConstrained(diskset, requests, 1, newParts)
    if ret == PARTITION_FAIL:
        return (ret, "Could not allocate cylinder-based partitions as primary partitions")
    ret = fitSized(diskset, requests, 1, newParts)
    if ret == PARTITION_FAIL:
        return (ret, "Could not allocate partitions as primary partitions")
    ret = fitConstrained(diskset, requests, 0, newParts)
    if ret == PARTITION_FAIL:
        return (ret, "Could not allocate cylinder-based partitions")
    ret = fitSized(diskset, requests, 0, newParts)
    if ret == PARTITION_FAIL:
        return (ret, "Could not allocate partitions")
    for request in requests.requests:
        # set the unique identifier for raid devices
        if request.type == REQUEST_RAID and not request.device:
            request.device = str(requests.nextUniqueID)
            requests.nextUniqueID = requests.nextUniqueID + 1

        if request.type == REQUEST_RAID:
            request.size = get_raid_device_size(request) / 1024 / 1024
        
        if not request.device:
#            return PARTITION_FAIL
            raise PartitioningError, "Unsatisfied partition request\n%s" %(request)

    return (PARTITION_SUCCESS, "success")

##     print "disk layout after everything is done"
##     print diskset.diskState()

def doPartitioning(diskset, requests, doRefresh = 1):
    for request in requests.requests:
        request.requestSize = request.size
        request.currentDrive = None

    if doRefresh:
        diskset.refreshDevices()
        # XXX - handle delete requests
        for delete in requests.deletes:
            deletePart(diskset, delete)

    newParts = partlist()
    (ret, msg) = processPartitioning(diskset, requests, newParts)

    if ret == PARTITION_FAIL:
        raise PartitioningError, "Partitioning failed: %s" %(msg)

    ret = growParts(diskset, requests, newParts)

    for part in newParts.parts:
        del part

    if ret == PARTITION_SUCCESS:
        return

    raise PartitioningError, "Growing partitions failed"

# given clearpart specification execute it
# probably want to reset diskset and partition request lists before calling
# this the first time
def doClearPartAction(id, type, cleardrives):
    if type == CLEARPART_TYPE_LINUX:
        linuxOnly = 1
    elif type == CLEARPART_TYPE_ALL:
        linuxOnly = 0
    elif type == CLEARPART_TYPE_NONE:
        return
    else:
        raise ValueError, "Invalid clear part type in doClearPartAction"
        
    drives = id.diskset.disks.keys()
    drives.sort()

    for drive in drives:
        # skip drives not in clear drive list
        if cleardrives and len(cleardrives) > 0 and not drive in cleardrives:
            continue
        disk = id.diskset.disks[drive]
        part = disk.next_partition()
        while part:
            if (part.type & parted.PARTITION_FREESPACE) or (part.type & parted.PARTITION_METADATA):
                part = disk.next_partition(part)
                continue
            if part.fs_type:
                ptype = get_partition_file_system_type(part)
            else:
                ptype = None
            if (linuxOnly == 0) or (ptype and (ptype.isLinuxNativeFS())):
                old = id.partrequests.getRequestByDeviceName(get_partition_name(part))
                id.partrequests.removeRequest(old)

                drive = part.geom.disk.dev.path[5:]
                delete = DeleteSpec(drive, part.geom.start, part.geom.end)
                id.partrequests.addDelete(delete)
            part = disk.next_partition(part)


    # set the diskset up
    doPartitioning(id.diskset, id.partrequests, doRefresh = 1)
    for drive in drives:
        if cleardrives and len(cleardrives) > 0 and not drive in cleardrives:
            continue

        disk = id.diskset.disks[drive]
        ext = disk.extended_partition
        if ext and len(get_logical_partitions(disk)) == 0:
            delete = DeleteSpec(drive, ext.geom.start, ext.geom.end)
            old = id.partrequests.getRequestByDeviceName(get_partition_name(ext))
            id.partrequests.removeRequest(old)
            id.partrequests.addDelete(delete)
            deletePart(id.diskset, delete)
            continue
    
def doAutoPartition(dir, id, intf):

    if dir == DISPATCH_BACK:
        id.diskset.refreshDevices()
        id.partrequests.setFromDisk(id.diskset)
        return
    
    # if no auto partition info in instclass we bail
    if len(id.autoPartitionRequests) < 1:
        return DISPATCH_NOOP

    # reset drive and request info to original state
    # XXX only do this if we're dirty
##     id.diskset.refreshDevices()
##     id.partrequests = PartitionRequests(id.diskset)

    doClearPartAction(id, id.autoClearPartType, id.autoClearPartDrives)

    for request in id.autoPartitionRequests:
        id.partrequests.addRequest(request)

    try:
        doPartitioning(id.diskset, id.partrequests, doRefresh = 0)
    except PartitioningError, msg:
        # restore drives to original state
        id.diskset.refreshDevices()
        id.partrequests = PartitionRequests(id.diskset)
        intf.messageWindow(_("Error Partitioning"),
               _("Could not allocated requested partitions: %s.") % (msg.value))
