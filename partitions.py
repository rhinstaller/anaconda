#
# partitions.py: partition object containing partitioning info
#
# Matt Wilson <msw@redhat.com>
# Jeremy Katz <katzj@redhat.com>
# Mike Fulbright <msf@redhat.com>
# Harald Hoyer <harald@redhat.de>
#
# Copyright 2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
"""Overarching partition object."""

import parted
import iutil
import string
import os, sys

from constants import *

import fsset
import partedUtils
import partRequests

class Partitions:
    """Defines all of the partition requests and delete requests."""
    def __init__ (self, diskset = None):
        """Initializes a Partitions object.

        Can pass in the diskset if it already exists.
        """
        self.requests = []
        """A list of RequestSpec objects for all partitions."""

        self.deletes = []
        """A list of DeleteSpec objects for partitions to be deleted."""

        self.autoPartitionRequests = []
        """A list of RequestSpec objects for autopartitioning.
        These are setup by the installclass and folded into self.requests
        by auto partitioning."""

        self.autoClearPartType = CLEARPART_TYPE_NONE
        """What type of partitions should be cleared?"""

        self.autoClearPartDrives = None
        """Drives to clear partitions on (note that None is equiv to all)."""

        self.nextUniqueID = 1
        """Internal counter.  Don't touch unless you're smarter than me."""

        self.reinitializeDisks = 0
        """Should the disk label be reset on all disks?"""

        self.zeroMbr = 0
        """Should the mbr be zero'd?"""

        # partition method to be used.  not to be touched externally
        self.useAutopartitioning = 1
        self.useFdisk = 0

        # autopartitioning info becomes kickstart partition requests
        # and its useful to be able to differentiate between the two
        self.isKickstart = 0

        if diskset:
            self.setFromDisk(diskset)


    def setFromDisk(self, diskset):
        """Clear the delete list and set self.requests to reflect disk."""
        self.deletes = []
        self.requests = []
        diskset.refreshDevices()
        labels = diskset.getLabels()
        drives = diskset.disks.keys()
        drives.sort()
        for drive in drives:
            disk = diskset.disks[drive]
            part = disk.next_partition()
            while part:
                if part.type & parted.PARTITION_METADATA:
                    part = disk.next_partition(part)
                    continue

                format = None
                if part.type & parted.PARTITION_FREESPACE:
                    ptype = None
                elif part.type & parted.PARTITION_EXTENDED:
                    ptype = None
                elif part.get_flag(parted.PARTITION_RAID) == 1:
                    ptype = fsset.fileSystemTypeGet("software RAID")
                elif part.get_flag(parted.PARTITION_LVM) == 1:
                    ptype = fsset.fileSystemTypeGet("physical volume (LVM)")
                elif part.fs_type:
                    ptype = partedUtils.get_partition_file_system_type(part)
                    if part.fs_type.name == "linux-swap":
                        # XXX this is a hack
                        format = 1
                else:
                    ptype = fsset.fileSystemTypeGet("foreign")
                    
                start = part.geom.start
                end = part.geom.end
                size = partedUtils.getPartSizeMB(part)
                drive = partedUtils.get_partition_drive(part)

                spec = partRequests.PreexistingPartitionSpec(ptype,
                                                             size = size,
                                                             start = start,
                                                             end = end,
                                                             drive = drive,
                                                             format = format)
                spec.device = fsset.PartedPartitionDevice(part).getDevice()
                print spec.device, ptype

                # set label if makes sense
                if ptype and ptype.isMountable() and \
                   (ptype.getName() == "ext2" or ptype.getName() == "ext3"):
                    if spec.device in labels.keys():
                        if labels[spec.device] and len(labels[spec.device])>0:
                            spec.fslabel = labels[spec.device]

                self.addRequest(spec)
                part = disk.next_partition(part)

    def addRequest (self, request):
        """Add a new request to the list."""
        if not request.uniqueID:
            request.uniqueID = self.nextUniqueID
            self.nextUniqueID = self.nextUniqueID + 1
        self.requests.append(request)
        self.requests.sort()

        return request.uniqueID

    def addDelete (self, delete):
        """Add a new DeleteSpec to the list."""
        self.deletes.append(delete)
        self.deletes.sort()

    def removeRequest (self, request):
        """Remove a request from the list."""
        self.requests.remove(request)

    def getRequestByMountPoint(self, mount):
        """Find and return the request with the given mountpoint."""
        for request in self.requests:
            if request.mountpoint == mount:
                return request
	    
	for request in self.requests:
	    if request.type == REQUEST_LV and request.mountpoint == mount:
		return request
        return None

    def getRequestByDeviceName(self, device):
        """Find and return the request with the given device name."""
	if device is None:
	    return None
	
        for request in self.requests:
            if request.device == device:
                return request
        return None

    def getRequestByVolumeGroupName(self, volname):
        """Find and return the request with the given volume group name."""
	if volname is None:
	    return None
	
	for request in self.requests:
	    if (request.type == REQUEST_VG and
                request.volumeGroupName == volname):
		return request
        return None

    def getRequestByLogicalVolumeName(self, lvname):
        """Find and return the request with the given logical volume name."""
	if lvname is None:
	    return None
	for request in self.requests:
	    if (request.type == REQUEST_LV and
                request.logicalVolumeName == lvname):
		return request
        return None

    def getRequestByID(self, id):
        """Find and return the request with the given unique ID.

        Note that if id is a string, it will be converted to an int for you.
        """
	if type(id) == type("a string"):
	    id = int(id)
        for request in self.requests:
            if request.uniqueID == id:
                return request
        return None

    def getRaidRequests(self):
        """Find and return a list of all of the RAID requests."""
        retval = []
        for request in self.requests:
            if request.type == REQUEST_RAID:
                retval.append(request)

        return retval

    def isRaidMember(self, request):
        """Return whether or not the request is being used in a RAID device."""
        raiddev = self.getRaidRequests()
        if not raiddev or not request.device:
            return 0
        for dev in raiddev:
            if not dev.raidmembers:
                continue
            for member in dev.raidmembers:
                if request.device == self.getRequestByID(member).device:
                    return 1
        return 0

    def getLVMLVForVG(self, vgrequest):
        """Find and return a list of all of the LVs in the VG."""
        retval = []
        vgid = vgrequest.uniqueID
        for request in self.requests:
	    if request.type == REQUEST_LV:
		if request.volumeGroup == vgid:
                    retval.append(request)

        return retval
		
    def getLVMRequests(self):
        """Return a dictionary of all of the LVM bits.

        The dictionary returned is of the form vgname: [ lvrequests ]
        """
        retval = {}
        for request in self.requests:
            if request.type == REQUEST_VG:
                retval[request.volumeGroupName] = self.getLVMLVForVG(request)
	    
        return retval

    def getLVMVGRequests(self):
        """Find and return a list of all of the volume groups."""
        retval = []
        for request in self.requests:
            if request.type == REQUEST_VG:
                retval.append(request)

        return retval

    def getLVMLVRequests(self):
        """Find and return a list of all of the logical volumes."""
        retval = []
        for request in self.requests:
            if request.type == REQUEST_LV:
                retval.append(request)

        return retval

    def isLVMVolumeGroupMember(self, request):
        """Return whether or not the request is being used in an LVM device."""
	volgroups = self.getLVMVGRequests()
	if not volgroups:
	    return 0

        # XXX is it nonsensical to check if this isn't a real partition?

	for volgroup in volgroups:
	    if volgroup.physicalVolumes:
		if request.uniqueID in volgroup.physicalVolumes:
			return 1

	return 0
	    
    def getBootableRequest(self):
        """Return the name of the current 'boot' mount point."""
        bootreq = None

        if iutil.getArch() == "ia64":
            bootreq = self.getRequestByMountPoint("/boot/efi")
            return bootreq
        if not bootreq:
            bootreq = self.getRequestByMountPoint("/boot")
        if not bootreq:
            bootreq = self.getRequestByMountPoint("/")
            
        return bootreq

    def isBootable(self, request):
        """Returns if the request should be considered a 'bootable' request.

        This basically means that it should be sorted to the beginning of
        the drive to avoid cylinder problems in most cases.
        """
        bootreq = self.getBootableRequest()
        if not bootreq:
            return 0
        
        if bootreq == request:
            return 1

        if bootreq.type == REQUEST_RAID and \
           request.uniqueID in bootreq.raidmembers:
            return 1

        return 0

    def sortRequests(self):
        """Resort the requests into allocation order."""
        n = 0
        while n < len(self.requests):
            for request in self.requests:
                if (request.size and self.requests[n].size and
                    (request.size < self.requests[n].size)):
                    tmp = self.requests[n]
                    index = self.requests.index(request)
                    self.requests[n] = request
                    self.requests[index] = tmp
                elif (request.start and self.requests[n].start and
                      (request.drive == self.requests[n].drive) and
                      (request.type == self.requests[n].type) and 
                      (request.start > self.requests[n].start)):
                    tmp = self.requests[n]
                    index = self.requests.index(request)
                    self.requests[n] = request
                    self.requests[index] = tmp
                elif (request.size and self.requests[n].size and
                      (request.size == self.requests[n].size) and
                      (request.uniqueID < self.requests[n].uniqueID)):
                    tmp = self.requests[n]
                    index = self.requests.index(request)
                    self.requests[n] = request
                    self.requests[index] = tmp                
            n = n + 1

        tmp = self.getBootableRequest()

        # if raid, we want all of the contents of the bootable raid
        if tmp and tmp.type == REQUEST_RAID:
            boot = []
            for member in tmp.raidmembers:
                boot.append(self.getRequestByID(member))
        elif tmp:
            boot = [tmp]
        else:
            boot = []

        # remove the bootables from the request
        for bootable in boot:
            self.requests.pop(self.requests.index(bootable))

        # move to the front of the list
        boot.extend(self.requests)
        self.requests = boot

    def copy (self):
        """Deep copy the object."""
        new = Partitions()
        for request in self.requests:
            new.addRequest(request)
        for delete in self.deletes:
            new.addDelete(delete)
        new.autoPartitionRequests = self.autoPartitionRequests
        new.autoClearPartType = self.autoClearPartType
        new.autoClearPartDrives = self.autoClearPartDrives
        new.nextUniqueID = self.nextUniqueID
        new.useAutopartitioning = self.useAutopartitioning
        new.useFdisk = self.useFdisk
        new.reinitializeDisks = self.reinitializeDisks
        return new

    def getClearPart(self):
        """Get the kickstart directive related to the clearpart being used."""
        clearpartargs = []
        if self.autoClearPartType == CLEARPART_TYPE_LINUX:
            clearpartargs.append('--linux')
        elif self.autoClearPartType == CLEARPART_TYPE_ALL:
            clearpartargs.append('--all')
        else:
            return None

        if self.reinitializeDisks:
            clearpartargs.append('--initlabel')

        if self.autoClearPartDrives:
            drives = string.join(self.autoClearPartDrives, ',')
            clearpartargs.append('--drives=%s' % (drives))

        return "#clearpart %s\n" %(string.join(clearpartargs))
    
    def writeKS(self, f):
        """Write out the partitioning information in kickstart format."""
        f.write("# The following is the partition information you requested\n")
        f.write("# Note that any partitions you deleted are not expressed\n")
        f.write("# here so unless you clear all partitions first, this is\n")
        f.write("# not guaranteed to work\n")
        clearpart = self.getClearPart()
        if clearpart:
            f.write(clearpart)

        # two passes here, once to write out parts, once to write out raids
        # XXX what do we do with deleted partitions?
        for request in self.requests:
            args = []
            if request.type == REQUEST_RAID:
                continue

            # no fstype, no deal (same with foreigns)
            if not request.fstype or request.fstype.getName() == "foreign":
                continue

            # first argument is mountpoint, which can also be swap or
            # the unique RAID identifier.  I hate kickstart partitioning
            # syntax.  a lot.  too many special cases 
            if request.fstype.getName() == "swap":
                args.append("swap")
            elif request.fstype.getName() == "software RAID":
                # since we guarantee that uniqueIDs are ints now...
                args.append("raid.%s" % (request.uniqueID))
            elif request.mountpoint:
                args.append(request.mountpoint)
                args.append("--fstype")
                args.append(request.fstype.getName())
            else:
                continue

            # generic options
            if not request.format:
                args.append("--noformat")
            if request.badblocks:
                args.append("--badblocks")

            # preexisting only
            if request.type == REQUEST_PREEXIST and request.device:
                args.append("--onpart")
                args.append(request.device)
            # we have a billion ways to specify new partitions
            elif request.type == REQUEST_NEW:
                if request.size:
                    args.append("--size=%s" % (request.size))
                if request.grow:
                    args.append("--grow")
                if request.start:
                    args.append("--start=%s" % (request.start))
                if request.end:
                    args.append("--end=%s" % (request.end))
                if request.maxSizeMB:
                    args.append("--maxsize=%s" % (request.maxSizeMB))
                if request.drive:
                    args.append("--ondisk=%s" % (request.drive[0]))
                if request.primary:
                    args.append("--asprimary")
            else: # how the hell did we get this?
                continue

            f.write("#part %s\n" % (string.join(args)))
                
                
        for request in self.requests:
            args = []
            if request.type != REQUEST_RAID:
                continue

            # no fstype, no deal (same with foreigns)
            if not request.fstype or request.fstype.getName() == "foreign":
                continue

            # also require a raidlevel and raidmembers for raid
            if (request.raidlevel == None) or not request.raidmembers:
                continue

            # first argument is mountpoint, which can also be swap
            if request.fstype.getName() == "swap":
                args.append("swap")
            elif request.mountpoint:
                args.append(request.mountpoint)
            else:
                continue

            # generic options
            if not request.format:
                args.append("--noformat")
            if request.fstype:
                args.append("--fstype")
                args.append(request.fstype.getName())
            if request.badblocks:
                args.append("--badblocks")

            args.append("--level=%s" % (request.raidlevel))

            if request.raidspares:
                args.append("--spares=%s" % (request.raidspares))

            # silly raid member syntax
            raidmems = []
            for member in request.raidmembers:
                if (type(member) != type("")) or (member[0:5] != "raid."):
                    raidmems.append("raid.%s" % (member))
                else:
                    raidmems.append(member)
            args.append("%s" % (string.join(raidmems)))

            f.write("#raid %s\n" % (string.join(args)))

