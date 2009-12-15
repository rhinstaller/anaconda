#
# autopart.py - auto partitioning logic
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import parted
import copy
import string, sys
import fsset
import lvm
import logging
import rhpl
from anaconda_log import logger, logFile
import cryptodev
from partitioning import *
import partedUtils
import partRequests
from constants import *
from partErrors import *

from rhpl.translate import _, N_

log = logging.getLogger("anaconda")

PARTITION_FAIL = -1
PARTITION_SUCCESS = 0

BOOT_ABOVE_1024 = -1
BOOTEFI_NOT_VFAT = -2
BOOTALPHA_NOT_BSD = -3
BOOTALPHA_NO_RESERVED_SPACE = -4
BOOTIPSERIES_TOO_HIGH = -5

DEBUG_LVM_GROW = 0

# Add another logger for the LVM debugging, since there's a lot of that.
# Set DEBUG_LVM_GROW if you want to spew all this information to the log
# file.  Otherwise it'll get ignored.
logger.addLogger ("anaconda.lvm", minLevel=logging.DEBUG)
lvmLog = logging.getLogger("anaconda.lvm")

if DEBUG_LVM_GROW:
    logger.addFileHandler (logFile, lvmLog, minLevel=logging.DEBUG)
else:
    lvmLog.setLevel (logging.CRITICAL)
    logger.addFileHandler (logFile, lvmLog, minLevel=logging.CRITICAL)

# check that our "boot" partition meets necessary constraints unless
# the request has its ignore flag set
def bootRequestCheck(requests, diskset):
    reqs = requests.getBootableRequest()
    if not reqs:
        return PARTITION_SUCCESS
    for req in reqs:
        if not req.device or req.ignoreBootConstraints:
            return PARTITION_SUCCESS
    # side effect: dev is left as the last in devs
    part = partedUtils.get_partition_by_name(diskset.disks, req.device)
    if not part:
        return PARTITION_SUCCESS

    if rhpl.getArch() == "ia64":
        if (part.fs_type.name != "FAT" and part.fs_type.name != "fat16"
            and part.fs_type.name != "fat32"):
            return BOOTEFI_NOT_VFAT
        pass
    elif rhpl.getArch() == "i386":
        if partedUtils.end_sector_to_cyl(part.geom.dev, part.geom.end) >= 1024:
            return BOOT_ABOVE_1024
    elif rhpl.getArch() == "alpha":
        return bootAlphaCheckRequirements(part)
    elif (iutil.getPPCMachine() == "pSeries" or
          iutil.getPPCMachine() == "iSeries"):
        for req in reqs:
            part = partedUtils.get_partition_by_name(diskset.disks, req.device)
            if part and ((part.geom.end * part.geom.dev.sector_size /
                          (1024.0 * 1024)) > 4096):
                return BOOTIPSERIES_TOO_HIGH
        
    return PARTITION_SUCCESS

# Alpha requires a BSD partition to boot. Since we can be called after:
#
#   - We re-attached an existing /boot partition (existing dev.drive)
#   - We create a new one from a designated disk (no dev.drive)
#   - We auto-create a new one from a designated set of disks (dev.drive
#     is a list)
#
# it's simpler to get disk the partition belong to through dev.device
# Some other tests pertaining to a partition where /boot resides are:
#
#   - There has to be at least 1 MB free at the begining of the disk
#     (or so says the aboot manual.)

def bootAlphaCheckRequirements(part):
    disk = part.disk

    # Disklabel check
    if not disk.type.name == "bsd":
        return BOOTALPHA_NOT_BSD

    # The first free space should start at the begining of the drive
    # and span for a megabyte or more.
    free = disk.next_partition()
    while free:
        if free.type & parted.PARTITION_FREESPACE:
            break
        free = disk.next_partition(free)
    if (not free or free.geom.start != 1L or
        partedUtils.getPartSizeMB(free) < 1):
        return BOOTALPHA_NO_RESERVED_SPACE

    return PARTITION_SUCCESS


def printNewRequestsCyl(diskset, newRequest):
    for req in newRequest.requests:
        if req.type != REQUEST_NEW:
            continue
        
        part = partedUtils.get_partition_by_name(diskset.disks, req.device)
##         print req
##         print "Start Cyl:%s    End Cyl: %s" % (partedUtils.start_sector_to_cyl(part.geom.dev, part.geom.start),
##                                  partedUtils.end_sector_to_cyl(part.geom.dev, part.geom.end))

def printFreespaceitem(part):
    return partedUtils.get_partition_name(part), part.geom.start, part.geom.end, partedUtils.getPartSizeMB(part)

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
                free[drive].append(part)
            part = disk.next_partition(part)
    return free


def bestPartType(disk, request):
    numPrimary = len(partedUtils.get_primary_partitions(disk))
    maxPrimary = disk.max_primary_partition_count
    if numPrimary == maxPrimary:
        raise PartitioningError, "Unable to create additional primary partitions on /dev/%s" % (disk.dev.path[5:])
    if request.primary:
        return parted.PARTITION_PRIMARY
    if ((numPrimary == (maxPrimary - 1)) and
        not disk.extended_partition and
        disk.type.check_feature(parted.DISK_TYPE_EXTENDED)):
        return parted.PARTITION_EXTENDED
    return parted.PARTITION_PRIMARY

class partlist:
    def __init__(self):
        self.parts = []

    def __str__(self):
        retval = ""
        for p in self.parts:
            retval = retval + "\t%s %s %s\n" % (partedUtils.get_partition_name(p), partedUtils.get_partition_file_system_type(p), partedUtils.getPartSizeMB(p))

        return retval

    def reset(self):
        dellist = []
        for part in self.parts:
            dellist.append(part)

        for part in dellist:
            self.parts.remove(part)
            del part
            
        self.parts = []


# first step of partitioning voodoo
# partitions with a specific start and end cylinder requested are
# placed where they were asked to go
def fitConstrained(diskset, requests, primOnly=0, newParts = None):
    for request in requests.requests:
        if request.type != REQUEST_NEW:
            continue
        if request.device:
            continue
        if primOnly and not request.primary and not requests.isBootable(request):
            continue
        if request.drive and (request.start != None):
            if not request.end and not request.size:
                raise PartitioningError, "Tried to create constrained partition without size or end"

            fsType = request.fstype.getPartedFileSystemType()
            disk = diskset.disks[request.drive[0]]
            if not disk: # this shouldn't happen
                raise PartitioningError, "Selected to put partition on non-existent disk!"

            startSec = partedUtils.start_cyl_to_sector(disk.dev, request.start)

            if request.end:
                endCyl = request.end
            elif request.size:
                endCyl = partedUtils.end_sector_to_cyl(disk.dev, ((1024L * 1024L * request.size) / disk.dev.sector_size) + startSec)

            endSec = partedUtils.end_cyl_to_sector(disk.dev, endCyl)

            if endSec > disk.dev.length:
                raise PartitioningError, "Unable to create partition which extends beyond the end of the disk."

            # XXX need to check overlaps properly here
            if startSec < 0:
                startSec = 0L

            if disk.type.check_feature(parted.DISK_TYPE_EXTENDED) and disk.extended_partition:

                if (disk.extended_partition.geom.start < startSec) and (disk.extended_partition.geom.end >= endSec):
                    partType = parted.PARTITION_LOGICAL
                    if request.primary: # they've required a primary and we can't do it
                        raise PartitioningError, "Cannot create another primary partition for %s." % request.mountpoint
                    # check to make sure we can still create more logical parts
                    if (len(partedUtils.get_logical_partitions(disk)) ==
                        partedUtils.get_max_logical_partitions(disk)):
                        raise PartitioningError, "Cannot create another logical partition for %s." % request.mountpoint
                else:
                    partType = parted.PARTITION_PRIMARY
            else:
                # XXX need a better way to do primary vs logical stuff
                ret = bestPartType(disk, request)

                if ret == parted.PARTITION_PRIMARY:
                    partType = parted.PARTITION_PRIMARY
                elif ret == parted.PARTITION_EXTENDED:
                    newp = disk.partition_new(parted.PARTITION_EXTENDED, None, startSec, endSec)
                    constraint = disk.dev.constraint_any()
                    disk.add_partition(newp, constraint)
                    disk.maximize_partition (newp, constraint)
                    newParts.parts.append(newp)
                    requests.nextUniqueID = requests.nextUniqueID + 1
                    partType = parted.PARTITION_LOGICAL
                else: # shouldn't get here
                    raise PartitioningError, "Impossible partition type to create"
            newp = disk.partition_new (partType, fsType, startSec, endSec)
            constraint = disk.dev.constraint_any ()
            try:
                disk.add_partition (newp, constraint)

            except parted.error, msg:
                raise PartitioningError, msg
            for flag in request.fstype.getPartedPartitionFlags():
                if not newp.is_flag_available(flag):
                    disk.delete_partition(newp)
                    raise PartitioningError, ("requested FileSystemType needs "
                                           "a flag that is not available.")
                newp.set_flag(flag, 1)
            request.device = fsset.PartedPartitionDevice(newp).getDevice()
            request.currentDrive = request.drive[0]
            newParts.parts.append(newp)

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

    drives.sort(isys.compareDrives)

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
        if primOnly and not request.primary and not requests.isBootable(request):
            continue
        if request.size == 0 and request.requestSize == 0:
            request.requestSize = 1
        if requests.isBootable(request):
            drives = getDriveList(request, diskset)
            numDrives = 0 # allocate bootable requests first
            # FIXME: this is a hack to make sure prep boot is even more first
            if request.fstype == fsset.fileSystemTypeGet("PPC PReP Boot"):
                numDrives = -1
            if request.fstype == fsset.fileSystemTypeGet("Apple Bootstrap"):
                numDrives = -1
        else:
            drives = getDriveList(request, diskset)
            numDrives = len(drives)
        if not todo.has_key(numDrives):
            todo[numDrives] = [ request ]
        else:
            todo[numDrives].append(request)

    number = todo.keys()
    number.sort()
    free = findFreespace(diskset)

    for num in number:
        for request in todo[num]:
#            print "\nInserting ->",request
            if requests.isBootable(request):
                isBoot = 1
            else:
                isBoot = 0
                
            largestPart = (0, None)
            drives = getDriveList(request, diskset)
            lvmLog.debug("Trying drives to find best free space out of %s" %(free,))
            for drive in drives:
                # this request is bootable and we've found a large enough
                # partition already, so we don't need to keep trying other
                # drives.  this keeps us on the first possible drive
                if isBoot and largestPart[1]:
                    break
##               print "Trying drive", drive
                disk = diskset.disks[drive]
                numPrimary = len(partedUtils.get_primary_partitions(disk))
                numLogical = len(partedUtils.get_logical_partitions(disk))

                # if there is an extended partition add it in
		if disk.extended_partition:
		    numPrimary = numPrimary + 1
		    
                maxPrimary = disk.max_primary_partition_count
                maxLogical = partedUtils.get_max_logical_partitions(disk)

                for part in free[drive]:
		    # if this is a free space outside extended partition
		    # make sure we have free primary partition slots
		    if not part.type & parted.PARTITION_LOGICAL:
			if numPrimary == maxPrimary:
			    continue
                    else:
                        if numLogical == maxLogical:
                            continue
		    
                    lvmLog.debug( "Trying partition %s" % (printFreespaceitem(part),))
                    partSize = partedUtils.getPartSizeMB(part)
                    # figure out what the request size will be given the
                    # geometry (#130885)
                    requestSectors = long((request.requestSize * 1024L * 1024L) / part.disk.dev.sector_size) - 1
                    requestSizeMB = long((requestSectors * part.disk.dev.sector_size) / 1024L / 1024L)
		    lvmLog.debug("partSize %s  request %s" % (partSize, request.requestSize))
                    if partSize >= requestSizeMB and partSize > largestPart[0]:
                        if not request.primary or (not part.type & parted.PARTITION_LOGICAL):
                            largestPart = (partSize, part)
                            if isBoot:
                                break

            if not largestPart[1]:
                # if the request has a size of zero, it can be allowed to not
                # exist without any problems
                if request.size > 0:
                    raise PartitioningError, "Not enough space left to create partition for %s" % request.mountpoint
                else:
                    request.device = None
                    request.currentDrive = None
                    continue
#                raise PartitioningError, "Can't fulfill request for partition: \n%s" %(request)

            lvmLog.debug("largestPart is %s" % (largestPart,))
            freespace = largestPart[1]
            freeStartSec = freespace.geom.start
            freeEndSec = freespace.geom.end

            dev = freespace.geom.dev
            disk = freespace.disk

            startSec = freeStartSec
            endSec = startSec + long(((request.requestSize * 1024L * 1024L) / disk.dev.sector_size)) - 1

            if endSec > freeEndSec:
                endSec = freeEndSec
            if startSec < freeStartSec:
                startSec = freeStartSec

            if freespace.type & parted.PARTITION_LOGICAL:
                partType = parted.PARTITION_LOGICAL
            else:
                # XXX need a better way to do primary vs logical stuff
                ret = bestPartType(disk, request)

                if ret == parted.PARTITION_PRIMARY:
                    partType = parted.PARTITION_PRIMARY
                elif ret == parted.PARTITION_EXTENDED:
                    newp = disk.partition_new(parted.PARTITION_EXTENDED, None, startSec, endSec)
                    constraint = dev.constraint_any()
                    disk.add_partition(newp, constraint)
                    disk.maximize_partition (newp, constraint)
                    newParts.parts.append(newp)
                    requests.nextUniqueID = requests.nextUniqueID + 1
                    partType = parted.PARTITION_LOGICAL

                    # now need to update freespace since adding extended
                    # took some space
                    found = 0
                    part = disk.next_partition()
                    while part:
                        if part.type & parted.PARTITION_FREESPACE:
                            if part.geom.start > freeStartSec and part.geom.end <= freeEndSec:
                                found = 1
                                freeStartSec = part.geom.start
                                freeEndSec = part.geom.end
                                break

                        part = disk.next_partition(part)

                    if not found:
                        raise PartitioningError, "Could not find free space after making new extended partition"

                    startSec = freeStartSec
                    endSec = startSec + long(((request.requestSize * 1024L * 1024L) / disk.dev.sector_size)) - 1

                    if endSec > freeEndSec:
                        endSec = freeEndSec
                    if startSec < freeStartSec:
                        startSec = freeStartSec

                else: # shouldn't get here
                    raise PartitioningError, "Impossible partition to create"

            fsType = request.fstype.getPartedFileSystemType()
            lvmLog.debug("creating newp with start=%s, end=%s, len=%s" % (startSec, endSec, endSec - startSec))
            newp = disk.partition_new (partType, fsType, startSec, endSec)
            constraint = dev.constraint_any ()

            try:
                disk.add_partition (newp, constraint)
            except parted.error, msg:
                raise PartitioningError, msg
            for flag in request.fstype.getPartedPartitionFlags():
                if not newp.is_flag_available(flag):
                    disk.delete_partition(newp)                    
                    raise PartitioningError, ("requested FileSystemType needs "
                                           "a flag that is not available.")
                newp.set_flag(flag, 1)

            request.device = fsset.PartedPartitionDevice(newp).getDevice()
            drive = newp.geom.dev.path[5:]
            request.currentDrive = drive
            newParts.parts.append(newp)
            free = findFreespace(diskset)

# grow logical partitions
#
# do this ONLY after all other requests have been allocated
# we just go through and adjust the size for the logical
# volumes w/o rerunning process partitions
#
def growLogicalVolumes(diskset, requests):

    if requests is None or diskset is None:
	return

    # iterate over each volume group, grow logical volumes in each
    for vgreq in requests.requests:
	if vgreq.type != REQUEST_VG:
	    continue

	lvmLog.info("In growLogicalVolumes, considering VG %s", vgreq)
	lvreqs = requests.getLVMLVForVG(vgreq)

	if lvreqs is None or len(lvreqs) < 1:
	    lvmLog.info("Apparently it had no logical volume requests, skipping.")
	    continue

	# come up with list of logvol that are growable
	growreqs = []
	for lvreq in lvreqs:
	    if lvreq.grow:
		growreqs.append(lvreq)

	# bail if none defined
        if len(growreqs) < 1:
	    lvmLog.info("No growable logical volumes defined in VG %s.", vgreq)
	    continue

	lvmLog.info("VG %s has these growable logical volumes: %s",  vgreq.volumeGroupName, reduce(lambda x,y: x + [y.uniqueID], growreqs, []))

	# get remaining free space
        if DEBUG_LVM_GROW:
	    vgfree = lvm.getVGFreeSpace(vgreq, requests, diskset)
	    lvmLog.debug("Free space in VG after initial partition formation = %s", (vgfree,))

	# store size we are starting at
	initsize = {}
	cursize = {}
	for req in growreqs:
	    size = req.getActualSize(requests, diskset)
            size = lvm.clampPVSize(size, vgreq.pesize)
	    initsize[req.logicalVolumeName] = size
	    cursize[req.logicalVolumeName] = size
            if req.maxSizeMB:
                req.maxSizeMB = lvm.clampPVSize(req.maxSizeMB, vgreq.pesize)
	    lvmLog.debug("init sizes for %s: %s",req.logicalVolumeName, size)
	    
	# now dolly out free space to all growing LVs
	bailcount = 0
	while 1:
	    nochange = 1
	    completed = []
	    for req in growreqs:
		lvmLog.debug("considering %s, start size = %s",req.logicalVolumeName, req.getStartSize())
		    
		# get remaining free space
		vgfree = lvm.getVGFreeSpace(vgreq, requests, diskset)

		lvmLog.debug("Free space in VG = %s",vgfree)
		    
		# compute fraction of remaining requests this
		# particular request represents
		totsize = 0.0
		for otherreq in growreqs:
		    if otherreq in completed:
			continue

		    lvmLog.debug("adding in %s %s %s", otherreq.logicalVolumeName, otherreq.getStartSize(), otherreq.maxSizeMB)
		    
		    size = otherreq.getActualSize(requests, diskset)
		    if otherreq.maxSizeMB:
			if size < otherreq.maxSizeMB:
			    totsize = totsize + otherreq.getStartSize()
			else:
			    lvmLog.debug("%s is now at %s, and passed maxsize of %s", otherreq.logicalVolumeName, size, otherreq.maxSizeMB)
		    else:
			totsize = totsize + otherreq.getStartSize()

		lvmLog.debug("totsize -> %s",totsize)

                # if totsize is zero we have no growable reqs left
		if totsize == 0:
		    break
		
		fraction = float(req.getStartSize())/float(totsize)

		newsize = lvm.clampPVSize(vgfree*fraction, vgreq.pesize)
                newsize += cursize[req.logicalVolumeName]

		if req.maxSizeMB:
		    newsize = min(newsize, req.maxSizeMB)
		    
		req.size = newsize
		if req.size != cursize[req.logicalVolumeName]:
		    nochange = 0

		cursize[req.logicalVolumeName] = req.size

		lvmLog.debug("Name, size, cursize, vgfree, fraction = %s %s %s %s %s", req.logicalVolumeName, req.size, cursize[req.logicalVolumeName], vgfree, fraction)

		completed.append(req)

	    if nochange:
		lvmLog.info("In growLogicalVolumes, no changes in size so breaking")
		break

	    bailcount = bailcount + 1
	    if bailcount > 10:
		lvmLog.info("In growLogicalVolumes, bailing after 10 interations.")
		break

# grow partitions
def growParts(diskset, requests, newParts):

    # returns free space segments for each drive IN SECTORS
    def getFreeSpace(diskset):
        free = findFreespace(diskset)
        freeSize = {}
        largestFree = {}

        # find out the amount of free space on each drive
        for key in free.keys():
            if len(free[key]) == 0:
                del free[key]
                continue
            freeSize[key] = 0
            largestFree[key] = 0
            for part in free[key]:
                sz = partedUtils.getPartSize(part)
                freeSize[key] += sz
                if sz > largestFree[key]:
                    largestFree[key] = sz

        return (free, freeSize, largestFree)

    ####
    # start of growParts
    ####
    newRequest = requests.copy()

##     print "new requests"
##     printNewRequestsCyl(diskset, requests)
##     print "orig requests"
##     printNewRequestsCyl(diskset, newRequest)
##     print "\n\n\n"
    
    (free, freeSize, largestFree) = getFreeSpace(diskset)

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
        return
    
##     print "new requests before looping"
##     printNewRequestsCyl(diskset, requests)
##     print "\n\n\n"

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
            cylsectors = diskset.disks[drive].dev.sectors*diskset.disks[drive].dev.heads
            
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

            thisFreeSize = getFreeSpace(diskset)[1]
            # loop over requests for this drive
            for request in growList:
                # skip if we've finished growing this request
                if request.uniqueID in grownList:
                    continue

                if drive not in freeSize.keys():
                    donegrowing = 1
#                    print "leaving inner loop because no more space on %s\n\n" % drive
                    break

##                 print "\nprocessing ID",request.uniqueID, request.mountpoint
##                 print "growSize, freeSize = ",growSize[drive], freeSize[drive]

                donegrowing = 0

                # get amount of space actually used by current allocation
                part = partedUtils.get_partition_by_name(diskset.disks, request.device)
                startSize = partedUtils.getPartSize(part)

                # compute fraction of freespace which to give to this
                # request. Weight by original request size
                percent = origSize[request.uniqueID] / (growSize[drive] * 1.0)
                growby = long(percent * thisFreeSize[drive])
                if growby < cylsectors:
                    growby = cylsectors;
                maxsect = startSize + growby

##                 print request
##                 print "percent, growby, maxsect, free", percent, growby, maxsect,freeSize[drive], startSize, lastFreeSize
##                 print "max is ",maxsect

                imposedMax = 0
                if request.maxSizeMB:
                    # round down a cylinder, see comment below
                    tmpint = request.maxSizeMB*1024.0*1024.0/sector_size
                    tmpint = long(tmpint / cylsectors)
                    maxUserSize = tmpint * cylsectors
                    if maxsect > maxUserSize:
                        maxsect = long(maxUserSize)
                        imposedMax = 1
			
		else:
		    # XXX HACK enforce silent limit for swap otherwise it
		    #     can grow up to 2TB!
		    if request.fstype.name == "swap":
			(xxxint, tmpint) = iutil.swapSuggestion(quiet=1)

			# convert to sectors
			tmpint = tmpint*1024*1024/sector_size
			tmpint = long(tmpint / cylsectors)
			maxsugswap = tmpint * cylsectors
			userstartsize = origSize[request.uniqueID]*1024*1024/sector_size
			if maxsugswap >= userstartsize:
			    maxsect = maxsugswap
			    imposedMax = 1
			    lvmLog.warning("Enforced max swap size of %s based on suggested max swap", maxsect)


                # round max fs limit down a cylinder, helps when growing
                # so we don't end up with a free cylinder at end if
                # maxlimit fell between cylinder boundaries
                tmpint = request.fstype.getMaxSizeMB()*1024.0*1024.0/sector_size
                tmpint = long(tmpint / cylsectors)
                maxFSSize = tmpint * cylsectors
                if maxsect > maxFSSize:
                    maxsect = long(maxFSSize)
                    imposedMax = 1

                maxfree = largestFree[drive]
                if maxsect > maxfree + startSize:
                    maxsect = long(maxfree) + startSize
                    imposedMax = 1

#                print "freesize, max, maxfree = ",freeSize[drive],maxsect, maxfree
#                print "freeSizeMB, maxMB = ", freeSize[drive] * sector_size/(1024.0 * 1024.0), maxsect * sector_size/(1024.0*1024.0), largestFree[drive] * sector_size/(1024.0*1024.0)
#                print "startsize = ",startSize

                min = startSize
                max = maxsect
                diff = max - min
                cur = max - (diff / 2)
                lastDiff = 0

                # binary search
##                 print "start min, max, cur, diffs = ",min,max,cur,diff,lastDiff
                inner_iter = 0
                ret = PARTITION_SUCCESS # request succeeded with initial size
                while (max != min) and (lastDiff != diff) and (inner_iter < 2000):
##                     printNewRequestsCyl(diskset, newRequest)

                    # XXX need to request in sectors preferably, more accurate
## 		    print "trying cur=%s" % cur
                    request.requestSize = (cur*sector_size)/1024.0/1024.0

                    # try adding
                    try:
                        processPartitioning(diskset, newRequest, newParts)
                        min = cur
                    except PartitioningError, msg:
                        ret = PARTITION_FAIL
                        max = cur
##                        print "!!!!!!!!!!! processPartitioning failed - %s" % msg

                    lastDiff = diff
                    diff = max - min

#                    print min, max, diff, cylsectors
#                    print diskset.diskState()

                    cur = max - (diff / 2)

                    inner_iter = inner_iter + 1
#                    print "sizes at end of loop - cur: %s min:%s max:%s diff:%s lastDiff:%s" % (cur,min,max,diff,lastDiff)

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
                    processPartitioning(diskset, newRequest, newParts)

#                print "end min, max, cur, diffs = ",min,max,cur,diff,lastDiff
#                print "%s took %s loops" % (request.mountpoint, inner_iter)
                lastFreeSize = freeSize[drive]
                (free, freeSize, largestFree) = getFreeSpace(diskset)
#                printFreespace(free)

                if ret == PARTITION_FAIL or (max == maxsect and imposedMax):
#                    print "putting ",request.uniqueID,request.mountpoint," in grownList"
                    grownList.append(request.uniqueID)
                    growSize[drive] = growSize[drive] - origSize[request.uniqueID]
                    if growSize[drive] < 0:
#                        print "growsize < 0!"
                        growSize[drive] = 0

def setPreexistParts(diskset, requests):
    for request in requests:
        if request.type != REQUEST_PREEXIST:
            continue
        if not diskset.disks.has_key(request.drive):
            lvmLog.info("pre-existing partition on non-native disk %s, ignoring" %(request.drive,))
            continue
        disk = diskset.disks[request.drive]
        part = disk.next_partition()
        while part:
            if part.geom.start == request.start and part.geom.end == request.end:
                request.device = partedUtils.get_partition_name(part)
                if request.fstype:
                    if request.fstype.getName() != request.origfstype.getName():
                        if part.is_flag_available(parted.PARTITION_RAID):
                            if request.fstype.getName() == "software RAID":
                                part.set_flag(parted.PARTITION_RAID, 1)
                            else:
                                part.set_flag(parted.PARTITION_RAID, 0)
                        if part.is_flag_available(parted.PARTITION_LVM):
                            if request.fstype.getName() == "physical volume (LVM)":
                                part.set_flag(parted.PARTITION_LVM, 1)
                            else:
                                part.set_flag(parted.PARTITION_LVM, 0)

                        partedUtils.set_partition_file_system_type(part, request.fstype)
                            
                break
            part = disk.next_partition(part)

def deletePart(diskset, delete):
    disk = diskset.disks[delete.drive]
    part = disk.next_partition()
    while part:
        if part.geom.start == delete.start and part.geom.end == delete.end:
            device = fsset.PartedPartitionDevice(part).getDevice()
            if delete.clobber:
                log.debug("removing lvm metadata from %s" %(device,))
                lvm.pvremove("/dev/%s" % (device,))
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
            extendeds[part.geom.dev.path] = None

    # Go through the list again and check for each logical partition we have.
    # If we created the extended partition on the same device as the logical
    # partition, remove it from out list, as it will be cleaned up for us
    # when the extended partition gets removed.
    dellist = []
    for part in newParts.parts:
        if (part.type & parted.PARTITION_LOGICAL
            and extendeds.has_key(part.geom.dev.path)):
            dellist.append(part)

    for part in dellist:
        newParts.parts.remove(part)

    # Finally, remove all of the partitions we added in the last try from
    # the disks.  We'll start again from there.
    for part in newParts.parts:
        part.disk.delete_partition(part)

    newParts.reset()

    for request in requests.requests:
        if request.type == REQUEST_NEW:
            request.device = None

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
    try:
        fitConstrained(diskset, requests, 1, newParts)
    except PartitioningError, msg:
        raise PartitioningError, _("Could not allocate cylinder-based partitions as primary partitions.\n") + str(msg)

    try:
        fitSized(diskset, requests, 1, newParts)
    except PartitioningError, msg:
        raise PartitioningError, _("Could not allocate partitions as primary partitions.\n") + str(msg)

    try:
        fitConstrained(diskset, requests, 0, newParts)
    except PartitioningError, msg:
        raise PartitioningError, _("Could not allocate cylinder-based partitions.\n") + str(msg)

    # Don't need to handle the exception here since we leave the message alone.
    fitSized(diskset, requests, 0, newParts)

    for request in requests.requests:
        # set the unique identifier for raid and lvm devices
        if request.type == REQUEST_RAID and not request.device:
            request.device = str(request.uniqueID)
        if request.type == REQUEST_VG and not request.device:
            request.device = str(request.uniqueID)
        # anything better we can use for the logical volume?
        if request.type == REQUEST_LV and not request.device:
            request.device = str(request.uniqueID)

        if not request.device:
            raise PartitioningError, "Unsatisfied partition request\n%s" % request

    # get the sizes for raid devices, vgs, and logical volumes
    for request in requests.requests:
        if request.type == REQUEST_RAID:
            request.size = request.getActualSize(requests, diskset)
        if request.type == REQUEST_VG:
            request.size = request.getActualSize(requests, diskset)
        if request.type == REQUEST_LV:
	    if request.grow:
		request.setSize(request.getStartSize())
	    else:
		request.size = request.getActualSize(requests, diskset)

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
            if isinstance(delete, partRequests.DeleteSpec):
                deletePart(diskset, delete)
            # FIXME: do we need to do anything with other types of deletes??

    newParts = partlist()

    try:
        processPartitioning(diskset, requests, newParts)
    except PartitioningError, msg:
        raise PartitioningError, "Partitioning failed: %s" % msg

    growParts(diskset, requests, newParts)

    newParts.reset()

    ret = bootRequestCheck(requests, diskset)

    if ret == BOOTALPHA_NOT_BSD:
        raise PartitioningWarning, _("Boot partition %s doesn't belong to a BSD disk label. SRM won't be able to boot from this partition. Use a partition belonging to a BSD disk label or change this device disk label to BSD.") %(requests.getBootableRequest()[0].mountpoint,)
    elif ret == BOOTALPHA_NO_RESERVED_SPACE:
        raise PartitioningWarning, _("Boot partition %s doesn't belong to a disk with enough free space at its beginning for the bootloader to live on. Make sure that there's at least 5MB of free space at the beginning of the disk that contains /boot") %(requests.getBootableRequest()[0].mountpoint,)
    elif ret == BOOTEFI_NOT_VFAT:
        raise PartitioningError, _("Boot partition %s isn't a VFAT partition.  EFI won't be able to boot from this partition.") %(requests.getBootableRequest()[0].mountpoint,)
    elif ret == BOOTIPSERIES_TOO_HIGH:
        raise PartitioningError, _("Boot partition isn't located early enough on the disk.  OpenFirmware won't be able to boot this installation.")
    elif ret == BOOT_ABOVE_1024:
        # we can't make boot disks anymore and this isn't much of a problem
        # for "modern" hardware. (#122535)
        pass
    elif ret != PARTITION_SUCCESS:
        # more specific message?
        raise PartitioningWarning, _("Boot partition %s may not meet booting constraints for your architecture.") %(requests.getBootableRequest()[0].mountpoint,)
#        raise PartitioningWarning, _("Boot partition %s may not meet booting constraints for your architecture.  Creation of a boot disk is highly encouraged.") %(requests.getBootableRequest()[0].mountpoint,)

    # now grow the logical partitions
    growLogicalVolumes(diskset, requests)
    
    # make sure our logical volumes still fit
    #
    # XXXX should make all this used lvm.getVGFreeSpace() and
    # lvm.getVGUsedSpace() at some point
    #
    
    vgused = {}
    for request in requests.requests:
        if request.type == REQUEST_LV:
            size = int(request.getActualSize(requests, diskset))
            if vgused.has_key(request.volumeGroup):
                vgused[request.volumeGroup] = (vgused[request.volumeGroup] +
                                               size)
            else:
                vgused[request.volumeGroup] = size
	    
    for vg in vgused.keys():
        request = requests.getRequestByID(vg)
	lvmLog.info("Used size vs. available for vg %s:  %s %s", request.volumeGroupName, vgused[vg], request.getActualSize(requests, diskset))
        if vgused[vg] > request.getActualSize(requests, diskset):
            raise PartitioningError, _("Adding this partition would not "
                                       "leave enough disk space for already "
                                       "allocated logical volumes in "
                                       "%s." % (request.volumeGroupName))

# given clearpart specification execute it
# probably want to reset diskset and partition request lists before calling
# this the first time
def doClearPartAction(anaconda, partitions, diskset):
    type = partitions.autoClearPartType
    cleardrives = partitions.autoClearPartDrives
    initAll = partitions.reinitializeDisks

    if type == CLEARPART_TYPE_LINUX:
        linuxOnly = 1
    elif type == CLEARPART_TYPE_ALL:
        linuxOnly = 0
    elif type == CLEARPART_TYPE_NONE:
        return
    else:
        raise ValueError, "Invalid clear part type in doClearPartAction"
        
    drives = diskset.disks.keys()
    drives.sort()

    for drive in drives:
        # skip drives not in clear drive list
        if (cleardrives and len(cleardrives) > 0 and not drive in cleardrives) or \
           drive in diskset.skippedDisks:
            continue
        disk = diskset.disks[drive]
        part = disk.next_partition()
        while part:
            if (not part.is_active() or (part.type == parted.PARTITION_EXTENDED) or
               (part.disk.type.name == "mac" and part.num == 1 and part.get_name() == "Apple")):
                part = disk.next_partition(part)
                continue
            if part.fs_type:
                ptype = partedUtils.get_partition_file_system_type(part)
            else:
                ptype = None
            # we want to do the clearing if
            # 1) clearAll is set
            # 2) there's a fsystem on the partition and it's a "native" fs
            # 3) there's not fsystem but the numeric id of partition is native
            # 4) the ptable doesn't support numeric ids, but it appears to be
            #    a RAID or LVM device (#107319)
            # 5) the drive contains protected partitions and initAll is set
            if ((linuxOnly == 0) or (ptype and ptype.isLinuxNativeFS()) or 
                (initAll and \
                 partedUtils.hasProtectedPartitions(drive, anaconda)) or
                (not ptype and
                 partedUtils.isLinuxNativeByNumtype(part.native_type)) or 
                ((part.native_type == -1) and # the ptable doesn't have types
                 ((part.is_flag_available(parted.PARTITION_RAID) and part.get_flag(parted.PARTITION_RAID)) or  # this is a RAID
                  (part.is_flag_available(parted.PARTITION_LVM) and part.get_flag(parted.PARTITION_LVM)) or # or an LVM
                  (iutil.isMactel() and not ptype)))): # or we're on a mactel and have a blank partition from bootcamp #FIXME: this could be dangerous...
                old = partitions.getRequestByDeviceName(partedUtils.get_partition_name(part))
                if old.getProtected():
                    part = disk.next_partition(part)
                    continue

                # for PV, set a flag to remove lvm metadata in deletePart
                # and do not create dependent delete requests (VGs, LVs)
                # because they would be processed (in doMetaDeletes) after
                # lvm metadata had been removed and thus fail
                if old.fstype.getName() == "physical volume (LVM)":
                    clobber = True
                else:
                    clobber = False
                partitions.deleteDependentRequests(old, justRemove=clobber)
                partitions.removeRequest(old)

                drive = partedUtils.get_partition_drive(part)
                delete = partRequests.DeleteSpec(drive, part.geom.start,
                                                 part.geom.end, clobber=clobber)
                partitions.addDelete(delete)

            # ia64 autopartitioning is strange as /boot/efi is vfat --
            # if linuxonly and have an msdos partition and it has the
            # bootable flag set, do not delete it and make it our
            # /boot/efi as it could contain system utils.
            # doesn't apply on kickstart installs or if no boot flag
            if ((rhpl.getArch() == "ia64") and (linuxOnly == 1)
                and (not anaconda.isKickstart) and
                part.is_flag_available(parted.PARTITION_BOOT)):
                if part.fs_type and (part.fs_type.name == "FAT"
                                     or part.fs_type.name == "fat16"
                                     or part.fs_type.name == "fat32"):
                    if part.get_flag(parted.PARTITION_BOOT):
                        req = partitions.getRequestByDeviceName(partedUtils.get_partition_name(part))
                        req.mountpoint = "/boot/efi"
                        req.format = 0

                        request = None
                        for req in partitions.autoPartitionRequests:
                            if req.mountpoint == "/boot/efi":
                                request = req
                                break
                        if request:
                            partitions.autoPartitionRequests.remove(request)
            # hey, what do you know, pseries is weird too.  *grumble*
            elif (((iutil.getPPCMachine() == "pSeries") or
                   (iutil.getPPCMachine() == "iSeries"))
                  and (linuxOnly == 1)
                  and (not anaconda.isKickstart) and
                  part.is_flag_available(parted.PARTITION_BOOT) and
                  (part.native_type == 0x41) and
                  part.get_flag(parted.PARTITION_BOOT)):
                req = partitions.getRequestByDeviceName(partedUtils.get_partition_name(part))                
                req.mountpoint = None
                req.format = 0
                request = None
                for req in partitions.autoPartitionRequests:
                    if req.fstype == fsset.fileSystemTypeGet("PPC PReP Boot"):
                        request = req
                        break
                if request:
                    partitions.autoPartitionRequests.remove(request)
                
            part = disk.next_partition(part)

    # set the diskset up
    try:
        doPartitioning(diskset, partitions, doRefresh = 1)
    except PartitioningError: # if we get an error here, it isn't overly relevant
        pass

    for drive in drives:
        if (cleardrives and len(cleardrives) > 0 and not drive in cleardrives) or \
           drive in diskset.skippedDisks:
            continue

        disk = diskset.disks[drive]
        ext = disk.extended_partition
        # if the extended is empty, blow it away
        if ext and len(partedUtils.get_logical_partitions(disk)) == 0:
            delete = partRequests.DeleteSpec(drive, ext.geom.start,
                                             ext.geom.end)
            old = partitions.getRequestByDeviceName(partedUtils.get_partition_name(ext))
            partitions.removeRequest(old)
            partitions.addDelete(delete)
            deletePart(diskset, delete)
            continue
    
def doAutoPartition(anaconda):
    instClass = anaconda.id.instClass
    diskset = anaconda.id.diskset
    partitions = anaconda.id.partitions

    if anaconda.isKickstart:
	partitions.setProtected(anaconda.dispatch)

    if anaconda.dir == DISPATCH_BACK:
        diskset.refreshDevices()
        partitions.setFromDisk(diskset)
        partitions.setProtected(anaconda.dispatch)
        partitions.autoPartitionRequests = []
        return

    # if no auto partition info in instclass we bail
    if len(partitions.autoPartitionRequests) < 1:
        #return DISPATCH_NOOP
        # XXX if we noop, then we fail later steps... let's just make it
        # the workstation default.  should instead just never get here
        # if no autopart info
        instClass.setDefaultPartitioning(partitions, doClear = 0)

    # reset drive and request info to original state
    # XXX only do this if we're dirty
##     id.diskset.refreshDevices()
##     id.partrequests = PartitionRequests(id.diskset)
    doClearPartAction(anaconda, partitions, diskset)

    # XXX clearpartdrives is overloaded as drives we want to use for linux
    drives = []
    initial_free = findFreespace(diskset)
    if partitions.autoClearPartDrives:
      for drive in partitions.autoClearPartDrives:
        free = 0
        for f in initial_free[drive]:
            size = f.geom.end - f.geom.start
            # don't count any partition smaller than 1M
            if (size > 2048):
                free += size
        for req in partitions.deletes:
            if isinstance(req, partRequests.DeleteSpec) and req.drive == drive:
                size = req.end - req.start
                # don't count any partition smaller than 1M
                if (size > 2048):
                    free += size

        # If there's less than 10M free, forget it.
        if free > 20480:
            drives.append(drive)
    del initial_free

    for request in partitions.autoPartitionRequests:
        if (isinstance(request, partRequests.PartitionSpec) and
            request.device):
            # get the preexisting partition they want to use
            req = partitions.getRequestByDeviceName(request.device)
            if not req or not req.type or req.type != REQUEST_PREEXIST:
                anaconda.intf.messageWindow(_("Requested Partition Does Not Exist"),
                                   _("Unable to locate partition %s to use "
                                     "for %s.\n\n"
                                     "Press 'OK' to reboot your system.")
                                   % (request.device, request.mountpoint),
				   custom_icon='error')
                sys.exit(0)

            # now go through and set things from the request to the
            # preexisting partition's request... ladeda
            if request.fslabel:
                req.fslabel = request.fslabel
            if request.mountpoint:
                req.mountpoint = request.mountpoint
            if request.badblocks:
                req.badblocks = request.badblocks
            if request.uniqueID:  # for raid to work
                req.uniqueID = request.uniqueID
            if request.fsopts:
                req.fsopts = request.fsopts
            if not request.format:
                req.format = 0
            else:
                req.format = 1
                req.fstype = request.fstype
        # XXX whee!  lots of cut and paste code lies below
        elif (isinstance(request, partRequests.RaidRequestSpec) and
              request.preexist == 1):
            req = partitions.getRequestByDeviceName(request.device)
            if not req or req.preexist == 0:
                 anaconda.intf.messageWindow(_("Requested Raid Device Does Not Exist"),
                                    _("Unable to locate raid device %s to use "
                                      "for %s.\n\n"
                                      "Press 'OK' to reboot your system.")
                                    % (request.device,
                                       request.mountpoint),
                                    custom_icon='error')
                 sys.exit(0)

            # now go through and set things from the request to the
            # preexisting partition's request... ladeda
            if request.mountpoint:
                req.mountpoint = request.mountpoint
            if request.badblocks:
                req.badblocks = request.badblocks
            if request.uniqueID:  # for raid to work
                req.uniqueID = request.uniqueID
            if request.fsopts:
                req.fsopts = request.fsopts
            if not request.format:
                req.format = 0
            else:
                req.format = 1
                req.fstype = request.fstype
            # XXX not copying the raid bits because they should be handled
            # automagically (actually, people probably aren't specifying them)
                
        elif (isinstance(request, partRequests.VolumeGroupRequestSpec) and
              request.preexist == 1):
            # get the preexisting partition they want to use
            req = partitions.getRequestByVolumeGroupName(request.volumeGroupName)
            if not req or req.preexist == 0 or req.format == 1:
                 anaconda.intf.messageWindow(_("Requested Volume Group Does Not Exist"),
                                    _("Unable to locate volume group %s to use "
                                      "for %s.\n\n"
                                      "Press 'OK' to reboot your system.")
                                   % (request.volumeGroupName,
                                      request.mountpoint),
                                    custom_icon='error')
                 sys.exit(0)

            oldid = None
            # now go through and set things from the request to the
            # preexisting partition's request... ladeda
            if request.physicalVolumes:
                req.physicalVolumes = request.physicalVolumes
            if request.pesize:
                req.pesize = request.pesize
            if request.uniqueID:  # for raid to work
                oldid = req.uniqueID
                req.uniqueID = request.uniqueID
            if request.fsopts:
                req.fsopts = request.fsopts
            if not request.format:
                req.format = 0
            else:
                req.format = 1

            # we also need to go through and remap everything which we
            # previously found to our new id.  yay!
            if oldid is not None:
                for lv in partitions.getLVMLVForVGID(oldid):
                    lv.volumeGroup = req.uniqueID


        elif (isinstance(request, partRequests.LogicalVolumeRequestSpec) and
              request.preexist == 1):
            # get the preexisting partition they want to use
            req = partitions.getRequestByLogicalVolumeName(request.logicalVolumeName)
            if not req or req.preexist == 0:
                anaconda.intf.messageWindow(_("Requested Logical Volume Does Not Exist"),
                                   _("Unable to locate logical volume %s to use "
                                     "for %s.\n\n"
                                     "Press 'OK' to reboot your system.")
                                   % (request.logicalVolumeName,
                                      request.mountpoint),
				   custom_icon='error')
                sys.exit(0)

            # now go through and set things from the request to the
            # preexisting partition's request... ladeda
            if request.volumeGroup:
                req.volumeGroup = request.volumeGroup
            if request.mountpoint:
                req.mountpoint = request.mountpoint
            if request.uniqueID:  # for raid to work
                req.uniqueID = request.uniqueID
            if request.fsopts:
                req.fsopts = request.fsopts
            if not request.format:
                req.format = 0
            else:
                req.format = 1
                req.fstype = request.fstype
        else:
            req = copy.copy(request)

            if req.type == REQUEST_NEW and not req.drive:
                req.drive = drives

            # this is kind of a hack, but if we're doing autopart encryption
            # and the request is a PV, encrypt it
            if partitions.autoEncrypt and req.type == REQUEST_NEW and \
               isinstance(req.fstype, fsset.lvmPhysicalVolumeDummyFileSystem):
                req.encryption = cryptodev.LUKSDevice(passphrase=partitions.encryptionPassphrase, format=1)

            # if this is a multidrive request, we need to create one per drive
            if req.type == REQUEST_NEW and req.multidrive:
                if not req.drive:
                    req.drive = diskset.disks.keys()
                    
                for drive in req.drive:
                    r = copy.copy(req)
                    r.encryption = copy.deepcopy(req.encryption)
                    r.drive = [ drive ]
                    partitions.addRequest(r)
                continue

            if (isinstance(req, partRequests.VolumeGroupRequestSpec)):
                # if the number of physical volumes requested is zero, then
                # add _all_ physical volumes we can find
                if ((len(req.physicalVolumes) == 0)
                    or (not req.physicalVolumes)):
                    req.physicalVolumes = []
                    for r in partitions.requests:
                        if isinstance(r.fstype,
                                      fsset.lvmPhysicalVolumeDummyFileSystem):
                            valid = 0
                            if ((not partitions.autoClearPartDrives) or
                                len(partitions.autoClearPartDrives) == 0):
                                valid = 1
                            else:
                                if (isinstance(r, partRequests.PartitionSpec) and r.drive):
                                    for d in r.drive:
                                        if d in partitions.autoClearPartDrives:
                                            valid = 1
                                            break

                            if isinstance(r, partRequests.PartitionSpec):
                                if not r.multidrive:
                                    valid = 0

                            if valid:
                                req.physicalVolumes.append(r.uniqueID)
                    # FIXME: this is a hack so that autopartition'd vgs
                    # can have a unique name
                    if req.autoname == 1 and req.volumeGroupName == "lvm":
                        n = lvm.createSuggestedVGName(partitions)
                        req.volumeGroupName = n

            if (isinstance(req, partRequests.LogicalVolumeRequestSpec)):
                # if the volgroup is set to a string, we probably need
                # to find that volgroup and use it's id
                if type(req.volumeGroup) == type(""):
                    r = None
                    if req.volumeGroup == "lvm":
                        for p in partitions.requests:
                            if isinstance(p, partRequests.VolumeGroupRequestSpec) and p.autoname == 1:
                                r = p
                                break
                    else:
                        r = partitions.getRequestByVolumeGroupName(req.volumeGroup)
                    if r is not None:
                        req.volumeGroup = r.uniqueID
                    else:
                        raise RuntimeError, "Unable to find the volume group for logical volume %s" %(req.logicalVolumeName,)
                        
            partitions.addRequest(req)

    # Remove all preexisting VG requests that reference nonexistant PV
    # requests.  These VGs should only be present on installs where we're
    # using preexisting partitions that already have LVM information.  We
    # need to do the same thing for preexisting RAID requests, as well.
    removeReqs = []

    for req in partitions.requests:
        if isinstance(req, partRequests.VolumeGroupRequestSpec):
            lst = req.physicalVolumes
        elif isinstance(req, partRequests.RaidRequestSpec):
            lst = req.raidmembers
        else:
            continue

        if len(filter (lambda id: partitions.getRequestByID(id) != None, lst)) == 0:
            removeReqs.append(req)

    for req in removeReqs:
        partitions.removeRequest(req)

    removeReqs = []

    # Now that we've removed bad VGs, remove all LVs that would have
    # resided on those VGs.
    for req in filter (lambda r: isinstance(r, partRequests.LogicalVolumeRequestSpec), partitions.requests):
        if partitions.getRequestByID(req.volumeGroup) == None:
            removeReqs.append(req)

    for req in removeReqs:
        partitions.removeRequest(req)

    # sanity checks for the auto partitioning requests; mostly only useful
    # for kickstart as our installclass defaults SHOULD be sane
    for req in partitions.requests:
        errors = req.sanityCheckRequest(partitions)
        if errors:
            anaconda.intf.messageWindow(_("Automatic Partitioning Errors"),
                               _("The following errors occurred with your "
                                 "partitioning:\n\n%s\n\n"
                                 "Press 'OK' to reboot your system.") %
                               (errors,), custom_icon='error')
            sys.exit(0)

    try:
        doPartitioning(diskset, partitions, doRefresh = 0)
    except PartitioningWarning, msg:
        if not anaconda.isKickstart:
            anaconda.intf.messageWindow(_("Warnings During Automatic Partitioning"),
                           _("Following warnings occurred during automatic "
                           "partitioning:\n\n%s") % (msg.value,),
			       custom_icon='warning')
        else:
            lvmLog.warning(msg.value)
    except PartitioningError, msg:
        # restore drives to original state
        diskset.refreshDevices()
        partitions.setFromDisk(diskset)
        partitions.setProtected(anaconda.dispatch)
        if not anaconda.isKickstart:
            extra = ""
            anaconda.dispatch.skipStep("partition", skip = 0)
        else:
            extra = _("\n\nPress 'OK' to reboot your system.")
        anaconda.intf.messageWindow(_("Error Partitioning"),
               _("Could not allocate requested partitions: \n\n"
                 "%s.%s") % (msg.value, extra), custom_icon='error')


        if anaconda.isKickstart:
            sys.exit(0)

    # now do a full check of the requests
    (errors, warnings) = partitions.sanityCheckAllRequests(diskset)
    if warnings:
        for warning in warnings:
            lvmLog.warning(warning)
    if errors:
        errortxt = string.join(errors, '\n')
        if anaconda.isKickstart:
            extra = _("\n\nPress 'OK' to reboot your system.")
        else:
            extra = _("\n\nPress 'OK' to choose a different partitioning option.")

        anaconda.intf.messageWindow(_("Automatic Partitioning Errors"),
                           _("The following errors occurred with your "
                             "partitioning:\n\n%s\n\n"
			     "This can happen if there is not enough "
			     "space on your hard drive(s) for the "
			     "installation.%s")
                           % (errortxt, extra),
			   custom_icon='error')
	#
	# XXX if in kickstart we reboot
	#
	if anaconda.isKickstart:
	    anaconda.intf.messageWindow(_("Unrecoverable Error"),
			       _("Your system will now be rebooted."))
	    sys.exit(0)
        return DISPATCH_BACK

def autoCreatePartitionRequests(autoreq):
    """Return a list of requests created with a shorthand notation.

    Mainly used by installclasses; make a list of tuples of the form
    (mntpt, fstype, minsize, maxsize, grow, format, asvol)
    mntpt = None for non-mountable, otherwise is mount point
    fstype = None to use default, otherwise a string
    minsize = smallest size
    maxsize = max size, or None means no max
    grow = 0 or 1, should partition be grown
    format = 0 or 1, whether to format
    asvol = 0 or 1, whether or not it should be a logical volume (ignored)
    """
    
    requests = []
    for (mntpt, fstype, minsize, maxsize, grow, format, asvol) in autoreq:
        if fstype:
            ptype = fsset.fileSystemTypeGet(fstype)
        else:
            ptype = fsset.fileSystemTypeGetDefault()
            
        newrequest = partRequests.PartitionSpec(ptype,
                                                mountpoint = mntpt,
                                                size = minsize,
                                                maxSizeMB = maxsize,
                                                grow = grow,
                                                format = format)
        
        requests.append(newrequest)

    return requests

def autoCreateLVMPartitionRequests(autoreq):
    """Return a list of requests created with a shorthand notation using LVM.

    Mainly used by installclasses; make a list of tuples of the form
    (mntpt, fstype, minsize, maxsize, grow, format)
    mntpt = None for non-mountable, otherwise is mount point
    fstype = None to use default, otherwise a string
    minsize = smallest size
    maxsize = max size, or None means no max
    grow = 0 or 1, should partition be grown
    format = 0 or 1, whether to format
    asvol = 0 or 1, whether or not it should be a logical volume
    """

    requests = []
    nr = partRequests.PartitionSpec(fsset.fileSystemTypeGet("physical volume (LVM)"),
                                    mountpoint = None,
                                    size = 0,
                                    maxSizeMB = None,
                                    grow = 1,
                                    format = 1,
                                    multidrive = 1)

    requests.append(nr)
    nr = partRequests.VolumeGroupRequestSpec(fstype = None,
                                             vgname = "lvm",
                                             physvols = [],
                                             format = 1)
    nr.autoname = 1
    requests.append(nr)

    volnum = 0
    for (mntpt, fstype, minsize, maxsize, grow, format, asvol) in autoreq:
        if fstype:
            ptype = fsset.fileSystemTypeGet(fstype)
        else:
            ptype = fsset.fileSystemTypeGetDefault()

        if not asvol:
            newrequest = partRequests.PartitionSpec(ptype,
                                                    mountpoint = mntpt,
                                                    size = minsize,
                                                    maxSizeMB = maxsize,
                                                    grow = grow,
                                                    format = format)
        else:
            newrequest = partRequests.LogicalVolumeRequestSpec(ptype,
                                                               mountpoint = mntpt,
                                                               size = minsize,
                                                               maxSizeMB = maxsize,
                                                               grow = grow,
                                                               format = format,
                                                               lvname = "LogVol%02d" %(volnum,),
                                                               volgroup = "lvm")
            volnum += 1

        
        requests.append(newrequest)

    return requests

def getAutopartitionBoot():
    """Return the proper shorthand for the boot dir (arch dependent)."""
    if rhpl.getArch() == "ia64":
        return [ ("/boot/efi", "vfat", 100, None, 0, 1, 0) ]
    elif (iutil.getPPCMachine() == "pSeries"):
        return [ (None, "PPC PReP Boot", 4, None, 0, 1, 0),
                 ("/boot", None, 100, None, 0, 1, 0) ]
    elif (iutil.getPPCMachine() == "iSeries") and not iutil.hasiSeriesNativeStorage():
        return [ (None, "PPC PReP Boot", 16, None, 0, 1, 0) ]
    elif (iutil.getPPCMachine() == "iSeries") and iutil.hasiSeriesNativeStorage():
        return []
    elif (iutil.getPPCMachine() == "PMac") and iutil.getPPCMacGen() == "NewWorld":
        return [ ( None, "Apple Bootstrap", 1, 1, 0, 1, 0), 
                 ("/boot", None, 100, None, 0, 1, 0) ]
    else:
        return [ ("/boot", None, 100, None, 0, 1, 0) ]

def queryAutoPartitionOK(anaconda):
    type = anaconda.id.partitions.autoClearPartType
    drives = anaconda.id.partitions.autoClearPartDrives

    if type == CLEARPART_TYPE_LINUX:
        msg = CLEARPART_TYPE_LINUX_WARNING_MSG
    elif type == CLEARPART_TYPE_ALL:
        msg = CLEARPART_TYPE_ALL_WARNING_MSG
    elif type == CLEARPART_TYPE_NONE:
        return 1
    else:
        raise ValueError, "Invalid clear part type in queryAutoPartitionOK"

    drvstr = "\n\n"
    if drives == None:
        drives = anaconda.id.diskset.disks.keys()

    drives.sort()
    width = 44
    for drive in drives:
        deviceFile = isys.makeDevInode(drive, "/dev/" + drive)
        dev = parted.PedDevice.get(deviceFile)
        str = "%s (%s %-0.f MB)" % (drive, dev.model, partedUtils.getDeviceSizeMB (dev))
        if len (str) <= width:
            drvstr = drvstr + str + "\n"
        else:
            while len (str) > 0:
               drvstr = drvstr + str[:width] + "\n"
               str = str[width:]
    
    rc = anaconda.intf.messageWindow(_("Warning"), _(msg) % drvstr, type="yesno", default="no", custom_icon ="warning")

    return rc


# XXX hack but these are common strings to TUI and GUI
PARTMETHOD_TYPE_DESCR_TEXT = N_("Automatic Partitioning sets partitions "
                               "based on the selected installation type. "
                               "You also "
                               "can customize the partitions once they "
                               "have been created.\n\n"
                               "The manual disk partitioning tool, Disk Druid, "
                               "allows you "
                               "to create partitions in an interactive "
                               "environment. You can set the file system "
                               "types, mount points, partition sizes, and more.")

AUTOPART_DISK_CHOICE_DESCR_TEXT = N_("Before automatic partitioning can be "
                                     "set up by the installation program, you "
                                     "must choose how to use the space on "
                                     "your hard drives.")

CLEARPART_TYPE_ALL_DESCR_TEXT = N_("Remove all partitions on this system")
CLEARPART_TYPE_LINUX_DESCR_TEXT = N_("Remove all Linux partitions on this system")
CLEARPART_TYPE_NONE_DESCR_TEXT = N_("Keep all partitions and use existing free space")

CLEARPART_TYPE_ALL_WARNING_MSG = N_("You have chosen to remove "
                                    "all partitions (ALL DATA) on the "
                                    "following drives:%s\nAre you sure you "
                                    "want to do this?")
CLEARPART_TYPE_LINUX_WARNING_MSG = N_("You have chosen to "
                                      "remove all Linux partitions "
                                      "(and ALL DATA on them) on the "
                                      "following drives:%s\n"
                                      "Are you sure you want to do this?")
