#
# partitioning.py: partitioning and other disk management
#
# Matt Wilson <msw@redhat.com>
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

if __name__ == "__main__":
    import sys
    sys.path.append ("isys")
    sys.path.append ("balkan")

import isys
import parted
import math
import raid
import fsset
import os
from translate import _
from log import log

# different types of partition requests
# REQUEST_PREEXIST is a placeholder for a pre-existing partition on the system
# REQUEST_NEW is a request for a partition which will be automatically
#              created based on various constraints on size, drive, etc
# REQUEST_RAID is a request for a raid device
# REQUEST_PROTECTED is a preexisting partition which can't change
#              (harddrive install, harddrive with the isos on it)
#
REQUEST_PREEXIST = 1
REQUEST_NEW = 2
REQUEST_RAID = 4
REQUEST_PROTECTED = 8

fsTypes = {}

fs_type = parted.file_system_type_get_next ()
while fs_type:
    fsTypes[fs_type.name] = fs_type
    fs_type = parted.file_system_type_get_next (fs_type)

class PartitioningError:
    def __init__ (self, value):
        self.value = value

    def __str__ (self):
        return self.value

def get_flags (part):
    string=""
    if not part.is_active ():
        return string
    first=1
    flag = parted.partition_flag_next (0)
    while flag:
        if part.get_flag (flag):
            string = string + parted.partition_flag_get_name (flag)
            if first:
                first = 0
            else:
                string = string + ", "
        flag = parted.partition_flag_next (flag)
    return string

def start_sector_to_cyl(device, sector):
    return int(math.floor((float(sector)
                           / (device.heads * device.sectors)) + 1))

def end_sector_to_cyl(device, sector):
    return int(math.ceil(float((sector + 1))
                         / (device.heads * device.sectors)))

def start_cyl_to_sector(device, cyl):
    return long((cyl - 1) * (device.heads * device.sectors))

def end_cyl_to_sector(device, cyl):
    return long(((cyl) * (device.heads * device.sectors)) - 1)

def getPartSize(partition):
    return partition.geom.length * partition.geom.disk.dev.sector_size / 1024.0 / 1024.0

def get_partition_name(partition):
    if (partition.geom.disk.dev.type == parted.DEVICE_DAC960
        or partition.geom.disk.dev.type == parted.DEVICE_CPQARRAY):
        return "%sp%d" % (partition.geom.disk.dev.path[5:],
                          partition.num)
    return "%s%d" % (partition.geom.disk.dev.path[5:],
                     partition.num)

def get_partition_file_system_type(part):
    if part.fs_type.name == "linux-swap":
        ptype = fsset.fileSystemTypeGet("swap")
    elif part.fs_type.name == "FAT":
        ptype = fsset.fileSystemTypeGet("vfat")
    else:
        try:
            ptype = fsset.fileSystemTypeGet(part.fs_type.name)
        except:
            ptype = fsset.fileSystemTypeGet("foreign")

    return ptype
    

def get_partition_drive(partition):
    return "%s" %(partition.geom.disk.dev.path[5:])

def get_logical_partitions(disk):
    rc = []
    part = disk.next_partition ()
    while part:
        if part.type & parted.PARTITION_FREESPACE or part.type & parted.PARTITION_METADATA:
            part = disk.next_partition(part)
            continue
        if part.type & parted.PARTITION_LOGICAL:
            rc.append(part)
        part = disk.next_partition (part)

    return rc

def get_primary_partitions(disk):
    rc = []
    part = disk.next_partition()
    while part:
        if part.type & parted.PARTITION_FREESPACE or part.type & parted.PARTITION_METADATA:
            part = disk.next_partition(part)
            continue
        if part.type == parted.PARTITION_PRIMARY:
            rc.append(part)
        part = disk.next_partition(part)

    return rc

# returns a list of partitions which can make up RAID devices
def get_raid_partitions(disk):
    rc = []
    part = disk.next_partition()
    while part:

        if part.type & (parted.PARTITION_METADATA | parted.PARTITION_FREESPACE | parted.PARTITION_EXTENDED):
            part = disk.next_partition(part)
            continue
        
        if part.get_flag(parted.PARTITION_RAID) == 1:
            rc.append(part)
        part = disk.next_partition(part)

    return rc


# returns a list of the actual raid device requests
def get_raid_devices(requests):
    raidRequests = []
    for request in requests:
        if request.type == REQUEST_RAID:
            raidRequests.append(request)
            
    return raidRequests


# returns a list of tuples of raid partitions which can be used or are used
# with whether they're used (0 if not, 1 if so)   eg (part, used)
def get_available_raid_partitions(diskset, requests, request):
    rc = []
    drives = diskset.disks.keys()
    raiddevs = get_raid_devices(requests)
    drives.sort()
    for drive in drives:
        disk = diskset.disks[drive]
        for part in get_raid_partitions(disk):
            used = 0
            for raid in raiddevs:
                if raid.raidmembers:
                    for raidmem in raid.raidmembers:
                        if get_partition_name(part) == get_partition_name(raidmem.partition):
                            if raid.device == request.device:
                                used = 2
                            else:
                                used = 1
                            break
                if used:
                    break

            if not used:
                rc.append((part, 0))
            elif used == 2:
                rc.append((part, 1))
    return rc


# return minimum numer of raid members required for a raid level
def get_raid_min_members(raidlevel):
    if raidlevel == "RAID0":
        return 2
    elif raidlevel == "RAID1":
        return 2
    elif raidlevel == "RAID5":
        return 3
    else:
        raise ValueError, "invalid raidlevel in get_raid_min_members"

# return max num of spares available for raidlevel and total num of members
def get_raid_max_spares(raidlevel, nummembers):
    if raidlevel == "RAID0":
        return 0
    elif raidlevel == "RAID1" or raidlevel == "RAID5":
        return max(0, nummembers - get_raid_min_members(raidlevel))
    else:
        raise ValueError, "invalid raidlevel in get_raid_max_spares"

def get_raid_device_size(raidrequest):
    if not raidrequest.raidmembers or not raidrequest.raidlevel:
        return 0
    
    raidlevel = raidrequest.raidlevel
    nummembers = len(raidrequest.raidmembers) - raidrequest.raidspares
    smallest = None
    sum = 0
    for member in raidrequest.raidmembers:
        part = member.partition
        partsize =  part.geom.length * part.geom.disk.dev.sector_size

        if raidlevel == "RAID0":
            sum = sum + partsize
        else:
            if not smallest:
                smallest = partsize
            elif partsize < smallest:
                smallest = partsize

    if raidlevel == "RAID0":
        return sum
    elif raidlevel == "RAID1":
        return smallest
    elif raidlevel == "RAID5":
        return (nummembers-1) * smallest
    else:
        raise ValueError, "Invalid raidlevel in get_raid_device_size()"
    
# sanityCheckMountPoint
def sanityCheckMountPoint(mntpt, fstype, reqtype):
    if mntpt:
        passed = 1
        if not mntpt:
            passed = 0
        else:
            if mntpt[0] != '/' or (len(mntpt) > 1 and mntpt[-1:] == '/'):
                passed = 0
                
        if not passed:
            return _("The mount point is invalid.  Mount points must start "
                     "with '/' and cannot end with '/', and must contain "
                     "printable characters.")
        else:
            return None
    else:
        if fstype and fstype.isMountable() and reqtype == REQUEST_NEW:
            return _("Please specify a mount point for this partition.")
        else:
            # its an existing partition so don't force a mount point
            return None

def isMountPointInUse(reqpartitions, newrequest):
    mntpt = newrequest.mountpoint
    if not mntpt:
        return None
    
    if reqpartitions and reqpartitions.requests:
        for request in reqpartitions.requests:
            if request.mountpoint == mntpt:
                used = 0
                if not newrequest.device or request.device != newrequest.device:
                        used = 1                

                if used:
                    return _("The mount point %s is already in use, please "
                             "choose a different mount point." %(mntpt))
    return None

def doMountPointLinuxFSChecks(newrequest):
    mustbeonroot = ['/bin','/dev','/sbin','/etc','/lib','/root','/mnt']
    mustbeonlinuxfs = ['/', '/boot', '/var', '/tmp', '/usr', '/home']

    if not newrequest.mountpoint:
        return None

    if newrequest.fstype.isLinuxNativeFS():
        if newrequest.mountpoint in mustbeonroot:
            return _("This mount point is invalid.  This directory must "
                     "be on the / filesystem.")

    else:
        if newrequest.mountpoint in mustbeonlinuxfs:
            return _("This mount point must be on a linux filesystem.")
        
    return None
    
def doPartitionSizeCheck(newrequest):
    if not newrequest.fstype:
        return None

    # XXX need to figure out the size for partitions specified by cyl range
    if newrequest.size and newrequest.size > newrequest.fstype.getMaxSize():
        return _("The size of the %s partition (size = %s MB) exceeds the maximum size of %s MB.") %(newrequest.fstype.getName(), newrequest.size, newrequest.fstype.getMaxSize())

    if newrequest.size and newrequest.maxSize and (newrequest.size > newrequest.maxSize):
        return _("The size of the requested partition (size = %s MB) exceeds the maximum size of %s MB.") %(newrequest.size, newrequest.maxSize)

    if newrequest.size and newrequest.size < 0:
        return _("The size of the requested partition is negative! (size = %s MB)") %(newrequest.size)

    if newrequest.start and newrequest.start < 1:
        return _("Partitions can't start below the first cylinder.")

    if newrequest.end and newrequest.end < 1:
        return _("Partitions can't end on a negative cylinder.")

    return None


# returns error string if something not right about request
def sanityCheckPartitionRequest(reqpartitions, newrequest):
    # see if mount point is valid if its a new partition request
    mntpt = newrequest.mountpoint
    fstype = newrequest.fstype
    reqtype = newrequest.type

    rc = doPartitionSizeCheck(newrequest)
    if rc:
        return rc

    rc = sanityCheckMountPoint(mntpt, fstype, reqtype)
    if rc:
        return rc

    rc = isMountPointInUse(reqpartitions, newrequest)
    if rc:
        return rc
    
    rc = doMountPointLinuxFSChecks(newrequest)
    if rc:
        return rc
    
    return None

# return error string is something not right about raid request
def sanityCheckRaidRequest(reqpartitions, newraid):
    if not newraid.raidmembers or not newraid.raidlevel:
        return _("No members in RAID request, or not RAID level specified.")
    
    for member in newraid.raidmembers:
        part = member.partition
        if part.get_flag(parted.PARTITION_RAID) != 1:
            return _("Some members of RAID request are not RAID partitions.")

    rc = sanityCheckPartitionRequest(reqpartitions, newraid)
    if rc:
        return rc

    # XXX fix this code to look to see if there is a bootable partition
    bootreq = reqpartitions.getBootableRequest()
    if not bootreq and newraid.mountpoint:
        if (newraid.mountpoint == "/boot" or newraid.mountpoint == "/") and newraid.raidlevel != "RAID1":
            return _("Bootable partitions can only be on RAID1 devices.")

    minmembers = get_raid_min_members(newraid.raidlevel)
    if len(newraid.raidmembers) < minmembers:
        return _("A RAID device of type %s requires at least %s members.") % (newraid.raidlevel, minmembers)

    if newraid.raidspares:
        if (len(newraid.raidmembers) - newraid.raidspares) < minmembers:
            return _("This RAID device can have a maximum of %s spares. "
                     "To have more spares you will need to add members to "
                     "the RAID device.") % (len(newraid.raidmembers) - minmembers )
    return None


class DeleteSpec:
    def __init__(self, drive, start, end):
        self.drive = drive
        self.start = start
        self.end = end

    def __str__(self):
        return "drive: %s  start: %s  end: %s" %(self.drive, self.start, self.end)


class PartitionSpec:
    def __init__(self, fstype, requesttype = REQUEST_NEW,
                 size = None, grow = 0, maxSize = None,
                 mountpoint = None,
                 start = None, end = None, partnum = None,
                 drive = None, primary = None, secondary = None,
                 format = None, options = None,
                 constraint = None,
                 raidmembers = None, raidlevel = None, 
                 raidspares = None):
        #
        # requesttype: REQUEST_PREEXIST or REQUEST_NEW or REQUEST_RAID
        #
        # XXX: unenforced requirements for a partition spec
        # must have (size) || (start && end)
        #           fs_type, mountpoint
        #           if partnum, require drive
        self.type = requesttype
        self.fstype = fstype
        self.size = size
        self.grow = grow
        self.maxSize = maxSize
        self.mountpoint = mountpoint
        self.start = start
        self.end = end
        self.partnum = partnum
        self.drive = drive
        self.primary = primary
        self.secondary = secondary
        self.format = format
        self.options = options
        self.constraint = constraint
        self.partition = None
        self.requestSize = size
        # XXX these are PartedPartitionDevice, should be requests        
        self.raidmembers = raidmembers
        self.raidlevel = raidlevel
        self.raidspares = raidspares
        
        # device is what we currently think the device is
        # realDevice is used by partitions which are pre-existing
        self.device = None
        self.realDevice = None

        # there has to be a way to go from device -> drive... but for now
        self.currentDrive = None

        # unique id for each request
        self.uniqueID = None

    def __str__(self):
        if self.fstype:
            fsname = self.fstype.getName()
        else:
            fsname = "None"
        raidmem = []
        if self.raidmembers:
            for i in self.raidmembers:
                raidmem.append(get_partition_name(i.partition))
                
        return "mountpoint: %s   type: %s   uniqueID:%s\n" %(self.mountpoint, fsname, self.uniqueID) +\
               "  size: %sM   requestSize: %sM  grow: %s   max: %s\n" %(self.size, self.requestSize, self.grow, self.maxSize) +\
               "  start: %s   end: %s   partnum: %s\n" %(self.start, self.end, self.partnum) +\
               "  drive: %s   primary: %s  secondary: %s\n" %(self.drive, self.primary, self.secondary) +\
               "  format: %s, options: %s" %(self.format, self.options) +\
               "  device: %s, realDevice: %s\n" %(self.device, self.realDevice)+\
               "  raidlevel: %s" % (self.raidlevel)+\
               "  raidspares: %s" % (self.raidspares)+\
               "  raidmembers: %s" % (raidmem)

    # turn a partition request into a fsset entry
    def toEntry(self):
        if self.type == REQUEST_RAID:
            device = fsset.RAIDDevice(int(self.raidlevel[-1:]),
                                      self.raidmembers,
                                      spares = self.raidspares)
        else:
            device = fsset.PartitionDevice(self.device)

        # pin down our partitions so that we can reread the table
        device.solidify()
        
        if self.fstype.getName() == "swap":
            mountpoint = "swap"
        else:
            mountpoint = self.mountpoint

        entry = fsset.FileSystemSetEntry(device, mountpoint, self.fstype)
        if self.format:
            entry.setFormat(self.format)
        return entry

class PartitionRequests:
    def __init__ (self, diskset = None):
        self.requests = []
        self.deletes = []
        # identifier used for raid partitions
        self.nextUniqueID = 1
        if diskset:
            self.setFromDisk(diskset)


    def setFromDisk(self, diskset):
        self.deletes = []
        diskset.refreshDevices()
        drives = diskset.disks.keys()
        drives.sort()
        for drive in drives:
            disk = diskset.disks[drive]
            part = disk.next_partition()
            while part:
                if part.type & parted.PARTITION_METADATA:
                    part = disk.next_partition(part)
                    continue

                format = 0
                if part.type & parted.PARTITION_FREESPACE:
                    ptype = None
                elif part.type & parted.PARTITION_EXTENDED:
                    ptype = None
                elif part.get_flag(parted.PARTITION_RAID) == 1:
                    ptype = None
                elif part.fs_type:
                    ptype = get_partition_file_system_type(part)
                    if part.fs_type.name == "linux-swap":
                        # XXX this is a hack
                        format = 1
                else:
                    ptype = None
                    
                start = part.geom.start
                end = part.geom.end
                size = getPartSize(part)
                drive = part.geom.disk.dev.path[5:]
                
                spec = PartitionSpec(ptype, requesttype = REQUEST_PREEXIST,
                                     start = start, end = end, size = size,
                                     drive = drive, format = format)
                spec.device = fsset.PartedPartitionDevice(part).getDevice()

                self.addRequest(spec)
                part = disk.next_partition(part)

    def addRequest (self, request):
        request.uniqueID = self.nextUniqueID + 1
        self.nextUniqueID = self.nextUniqueID + 1
        self.requests.append(request)
        self.requests.sort()

    def addDelete (self, delete):
        self.deletes.append(delete)
        self.deletes.sort()

    def removeRequest (self, request):
        self.requests.remove(request)

    def getRequestByMountPoint(self, mount):
        for request in self.requests:
            if request.mountpoint == mount:
                return request
        return None

    def getRequestByDeviceName(self, device):
        for request in self.requests:
            if request.device == device:
                return request
        return None

    def getRaidRequests(self):
        retval = []
        for request in self.requests:
            if request.type == REQUEST_RAID:
                retval.append(request)

        return retval

    def isRaidMember(self, request):
        raiddev = self.getRaidRequests()
        if not raiddev or not request.device:
            return 0
        for dev in raiddev:
            if not dev.raidmembers:
                continue
            for member in dev.raidmembers:
                if request.device == get_partition_name(member.partition):
                    return 1
        return 0

    # return name of boot mount point in current requests
    def getBootableRequest(self):
        bootreq = self.getRequestByMountPoint("/boot")
        if not bootreq:
            bootreq = self.getRequestByMountPoint("/")
            
        return bootreq

    def sortRequests(self):
        n = 0
        while n < len(self.requests):
            for request in self.requests:
                if request.size < self.requests[n].size:
                    tmp = self.requests[n]
                    index = self.requests.index(request)
                    self.requests[n] = request
                    self.requests[index] = tmp
            n = n + 1

    def copy (self):
        new = PartitionRequests()
        for request in self.requests:
            new.addRequest(request)
        for delete in self.deletes:
            new.addDelete(delete)
        return new
        

class DiskSet:
    skippedDisks = []
    def __init__ (self):
        self.disks = {}

    def getLabels(self):
        labels = {}
        
        drives = self.disks.keys()
        drives.sort()

        for drive in drives:
            disk = self.disks[drive]
            part = disk.next_partition ()
            while part:
                if part.fs_type and (part.fs_type.name == "ext2"
                                     or part.fs_type.name == "ext3"):
                    node = get_partition_name(part)
                    label = isys.readExt2Label(node)
                    if label:
                        labels[node] = label
                part = disk.next_partition(part)

        return labels

    def findExistingRootPartitions(self, intf):
        rootparts = []

        drives = self.disks.keys()
        drives.sort()
        
        mdList = raid.startAllRaid(drives)

        for dev in mdList:
            if not fsset.isValidExt2 (dev):
                continue

            try:
                isys.mount(dev, '/mnt/sysimage', readOnly = 1)
            except SystemError, (errno, msg):
                intf.messageWindow(_("Error"),
                                   _("Error mounting filesystem "
                                     "on %s: %s") % (dev, msg))
                continue
            if os.access ('/mnt/sysimage/etc/fstab', os.R_OK):
                rootparts.append ((dev, "ext2"))
            isys.umount('/mnt/sysimage')

        raid.stopAllRaid(mdList)
        
        drives = self.disks.keys()
        drives.sort()

        for drive in drives:
            disk = self.disks[drive]
            part = disk.next_partition ()
            while part:
                if part.fs_type and (part.fs_type.name == "ext2"
                                     or part.fs_type.name == "ext3"):
                    node = get_partition_name(part)
		    try:
			isys.mount(node, '/mnt/sysimage')
		    except SystemError, (errno, msg):
			intf.messageWindow(_("Error"),
                                           _("Error mounting filesystem on "
                                             "%s: %s") % (node, msg))
                        part = disk.next_partition(part)
			continue
		    if os.access ('/mnt/sysimage/etc/fstab', os.R_OK):
			rootparts.append ((node, "ext2"))
		    isys.umount('/mnt/sysimage')
                if part.fs_type and (part.fs_type.name == "DOS"):
                    try:
                        isys.mount(node, '/mnt/sysimage', fstype = "vfat",
                                   readOnly = 1)
                    except:
			log("failed to mount vfat filesystem on %s\n" 
                            % dev)
                        part = disk.next_partition(part)
			continue
                        
		    if os.access('/mnt/sysimage/redhat.img', os.R_OK):
                        rootparts.append((node, "vfat"))

		    isys.umount('/mnt/sysimage')
                    
                part = disk.next_partition(part)
        return rootparts

    def driveList (self):
	drives = isys.hardDriveDict().keys()
	drives.sort (isys.compareDrives)
	return drives

    def drivesByName (self):
	return isys.hardDriveDict()

    def addPartition (self, device, type, spec):
        if not self.disks.has_key (device):
            raise PartitioningError, ("unknown device passed to "
                                      "addPartition: %s" % (device,))
        disk = self.disks[device]

        part = disk.next_partition ()
        status = 0
        while part:
            if (part.type == parted.PARTITION_FREESPACE
                and part.geom.length >= spec.size):
                newp = disk.partition_new (type, spec.fs_type,
                                           part.geom.start,
                                           part.geom.start + spec.size)
                constraint = disk.constraint_any ()
                try:
                    disk.add_partition (newp, constraint)
                    status = 1
                    break
                except parted.error, msg:
                    raise PartitioningError, msg
            part = disk.next_partition (part)
        if not status:
            raise PartitioningError, ("Not enough free space on %s to create "
                                      "new partition" % (device,))
        return newp
    
    def deleteAllPartitions (self):
        for disk in self.disks.values():
            disk.delete_all ()

    def savePartitions (self):
        for disk in self.disks.values():
            disk.write()
            del disk
        self.refreshDevices()

    def refreshDevices (self):
        self.disks = {}
        self.openDevices()

    def openDevices (self):
        if self.disks:
            return
        for drive in self.driveList ():
            if drive in DiskSet.skippedDisks:
                continue
	    deviceFile = '/dev/' + drive
	    if not os.access(deviceFile, os.R_OK):
		deviceFile = isys.makeDevInode(drive)
            try:
                dev = parted.PedDevice.get (deviceFile)
            except parted.error, msg:
                DiskSet.skippedDisks.append(drive)
                continue
            try:
                disk = parted.PedDisk.open(dev)
                self.disks[drive] = disk
            except parted.error, msg:
                DiskSet.skippedDisks.append(drive)

    def partitionTypes (self):
        rc = []
        drives = self.disks.keys()
        drives.sort

        for drive in drives:
            disk = self.disks[drive]
            part = disk.next_partition ()
            while part:
                if part.type in (parted.PARTITION_PRIMARY,
                                 parted.PARTITION_LOGICAL):
                    device = get_partition_name(part)
                    if part.fs_type:
                        ptype = part.fs_type.name
                    else:
                        ptype = None
                    rc.append (device, ptype)
                part = disk.next_partition (part)
      
        return rc

    def diskState (self):
        rc = ""
        for disk in self.disks.values():
            rc = rc + ("%s: %s length %ld, maximum "
                       "primary partitions: %d\n" %
                       (disk.dev.path,
                        disk.dev.model,
                        disk.dev.length,
                        disk.max_primary_partition_count))

            part = disk.next_partition()
            if part:
                rc = rc + ("Device    Type         Filesystem   Start      "
                           "End        Length        Flags\n")
                rc = rc + ("------    ----         ----------   -----      "
                           "---        ------        -----\n")
            while part:
                if not part.type & parted.PARTITION_METADATA:
                    device = ""
                    fs_type_name = ""
                    if part.num > 0:
                        device = get_partition_name(part)
                    if part.fs_type:
                        fs_type_name = part.fs_type.name
                    flags = get_flags (part)
                    rc = rc + ("%-9s %-12s %-12s %-10ld %-10ld %-10ld %7s\n"
                               % (device, part.type_name, fs_type_name,
                              part.geom.start, part.geom.end, part.geom.length,
                              flags))
                part = disk.next_partition(part)
        return rc

def partitionMethodSetup(id, dispatch):

    # turn on/off step based on 3 paths:
    #  - use fdisk, then set mount points
    #  - use autopartitioning, then set mount points
    #  - use interactive partitioning tool, continue

    dispatch.skipStep("autopartition", skip = not id.useAutopartitioning)
    dispatch.skipStep("autopartitionexecute",skip = not id.useAutopartitioning)
    dispatch.skipStep("fdisk", skip = not id.useFdisk)
        
    # read in drive info
    id.diskset = DiskSet()
    id.partrequests = PartitionRequests(id.diskset)

    protected = dispatch.method.protectedPartitions()
    if protected:
        for device in protected:
            request = id.partrequests.getRequestByDeviceName(device)
            request.type = REQUEST_PROTECTED
