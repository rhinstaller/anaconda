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

from fsset import *
from translate import _

# different types of partition requests
# REQUEST_PREEXIST is a placeholder for a pre-existing partition on the system
# REQUEST_NEW is a request for a partition which will be automatically
#              created based on various constraints on size, drive, etc
#
REQUEST_PREEXIST = 1
REQUEST_NEW = 2
REQUEST_RAID = 4

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

def get_logical_partitions(disk):
    rc = []
    part = disk.next_partition ()
    while part:
        if part.type & parted.PARTITION_LOGICAL:
            rc.append(part)
        part = disk.next_partition (part)

    return rc

def get_primary_partitions(disk):
    rc = []
    part = disk.next_partition()
    while part:
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


# returns a list of raid partitions which haven't been used in a device yet
def get_available_raid_partitions(diskset, requests):
    rc = []
    drives = diskset.disks.keys()
    raiddevs = get_raid_devices(requests)
    drives.sort()
    for drive in drives:
        disk = diskset.disks[drive]
        for part in get_raid_partitions(disk):
            for raid in raiddevs:
                if raid.raidmembers and part in raid.raidmembers:
                    break
            rc.append(part)
    return rc

# return minimum numer of raid members required for a raid level
def get_raid_min_members(raidlevel):
    if raidlevel == "RAID-0":
        return 2
    elif raidlevel == "RAID-1":
        return 2
    elif raidlevel == "RAID-5":
        return 3
    else:
        raise ValueError, "invalid raidlevel in get_raid_min_members"

# return max num of spares available for raidlevel and total num of members
def get_raid_max_spares(raidlevel, nummembers):
    if raidlevel == "RAID-0":
        return 0
    elif raidlevel == "RAID-1":
        return 0
    elif raidlevel == "RAID-5":
        return max(0, nummembers - get_raid_min_members(raidlevel))
    else:
        raise ValueError, "invalid raidlevel in get_raid_max_spares"

# returns error string if something not right about request
# returns error string if something not right about request
def sanityCheck(reqpartitions, newrequest):
    # see if mount point is valid if its a new partition request
    
    mustbeonroot = ['/bin','/dev','/sbin','/etc','/lib','/root','/mnt']
    mustbeonlinuxfs = ['/', '/boot', '/var', '/tmp', '/usr', '/home']
    
    mntpt = newrequest.mountpoint
    fstype = newrequest.fstype

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
        if newrequest.fstype.isMountable() and newrequest.type == REQUEST_NEW:
            return _("Please specify a mount point for this partition.")
        else:
            # its an existing partition so don't force a mount point
            return

    # mount point is defined and is legal. now make sure its unique
    if reqpartitions and reqpartitions.requests:
        for request in reqpartitions.requests:
            if request.mountpoint == mntpt and request.start != newrequest.start:
                return _("The mount point %s is already in use, please "
                         "choose a different mount point." % (mntpt))


    # further sanity checks
    if fstype.isLinuxNativeFS():    
        if mntpt in mustbeonroot:
            return _("This mount point is invalid.  This directory must "
                     "be on the / filesystem.")

        if fstype.getName() == "linux-swap":
            if newrequest.size * 1024 > MAX_SWAP_PART_SIZE_KB:
                return _("This swap partition exceeds the maximum size of "
                         "%s MB.") % (MAX_SWAP_PART_SIZE_KB / 1024)
    else:
        if mntpt in mustbeonlinuxfs:
            return _("This mount point must be on a linux filesystem.")

    return None

class DeleteSpec:
    def __init__(self, drive, start, end):
        self.drive = drive
        self.start = start
        self.end = end


class PartitionSpec:
    def __init__(self, fstype, requesttype = REQUEST_NEW,
                 size = None, grow = 0, maxSize = 0,
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
        self.raidmembers = raidmembers
        self.raidlevel = raidlevel
        self.raidspares = raidspares
        
        # device is what we currently think the device is
        # realDevice is used by partitions which are pre-existing
        self.device = None
        self.realDevice = None

        # there has to be a way to go from device -> drive... but for now
        self.currentDrive = None

    def __str__(self):
        return "mountpoint: %s   type: %s\n" %(self.mountpoint, self.fstype.getName()) +\
               "  size: %sM   requestSize: %sM  grow: %s   max: %s\n" %(self.size, self.requestSize, self.grow, self.maxSize) +\
               "  start: %s   end: %s   partnum: %s\n" %(self.start, self.end, self.partnum) +\
               "  drive: %s   primary: %s  secondary: %s\n" %(self.drive, self.primary, self.secondary) +\
               "  format: %s, options: %s" %(self.format, self.options) +\
               "  device: %s, realDevice: %s" %(self.device, self.realDevice)+\
               "  raidlevel: %s" % (self.raidlevel)+\
               "  raidspares: %s" % (self.raidspares)

    # turn a partition request into a fsset entry
    def toEntry(self):
        if self.type == REQUEST_RAID:
            device = RAIDDevice(int(self.raidlevel[-1:]), self.raidmembers,
                                    spares = self.raidspares)
        else:
            device = PartitionDevice(self.device)

        # pin down our partitions so that we can reread the table
        device.solidify()
        
        if self.fstype.getName() == "swap":
            mountpoint = "swap"
        else:
            mountpoint = self.mountpoint

        entry = FileSystemSetEntry(device, mountpoint, self.fstype)
        if self.format:
            entry.setFormat(self.format)
        return entry

class PartitionRequests:
    def __init__ (self, diskset = None):
        self.requests = []
        self.deletes = []
        if diskset:
            self.setFromDisk(diskset)

        # identifier used for raid partitions
        self.maxcontainer = 0
            

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
                
                if part.type & parted.PARTITION_FREESPACE:
                    ptype = None
                elif part.type & parted.PARTITION_EXTENDED:
                    ptype = None
                elif part.fs_type:
                    if part.fs_type.name == "linux-swap":
                        ptype = fileSystemTypeGet("swap")
                    elif part.fs_type.name == "FAT":
                        ptype = fileSystemTypeGet("vfat")
                    else:
                        try:
                            ptype = fileSystemTypeGet(part.fs_type.name)
                        except:
                            ptype = fileSystemTypeGet("foreign")
                else:
                    ptype = None
                    
                start = part.geom.start
                end = part.geom.end
                size = getPartSize(part)
                
                spec = PartitionSpec(ptype, requesttype = REQUEST_PREEXIST,
                                     start = start, end = end, size = size)
                spec.device = PartedPartitionDevice(part).getDevice()
                self.addRequest(spec)
                part = disk.next_partition(part)

    def addRequest (self, request):
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
    def __init__ (self):
        self.disks = {}

    def getLabels(self):
        labels = {}
        
        drives = self.disks.keys()
        drives.sort

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
            isys.makeDevInode(drive, '/tmp/' + drive)
            try:
                dev = parted.PedDevice.get ('/tmp/' + drive)
            except parted.error, msg:
                raise PartitioningError, msg
            try:
                disk = parted.PedDisk.open(dev)
                self.disks[drive] = disk
            except parted.error, msg:
                raise PartitioningError, msg

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

def AutoPartition (fsset, diskset):
    from fsset import *
    diskset.deleteAllPartitions ()

    spec = PartitionSpec (fsTypes['linux-swap'], (64L * 2048L))
    diskset.addPartition (diskset.driveList()[0],
                          parted.PARTITION_PRIMARY, spec)
    
    spec = PartitionSpec (fsTypes['ext2'], (1024L * 2048L))
    diskset.addPartition (diskset.driveList()[0],
                          parted.PARTITION_PRIMARY, spec)

    device = PartitionDevice (diskset.driveList()[0] + "1")
    mountpoint = FileSystemSetEntry (device, 'swap', 'swap')
    mountpoint.setFormat(1)
    fsset.add(mountpoint)
    
    device = PartitionDevice (diskset.driveList()[0] + "2")
    mountpoint = FileSystemSetEntry (device, '/')
    mountpoint.setFormat(1)
    fsset.add(mountpoint)
    
    from log import log
    log (diskset.diskState())

if __name__ == "__main__":
    foo = DiskSet()
    foo.deleteAllPartitions ()
    print foo.diskState ()
    print '---------------------'
    spec = PartitionSpec (fsTypes['ext2'], 12060L)
    foo.addPartition ("sda", parted.PARTITION_PRIMARY, spec)
    print foo.diskState ()    
    spec = PartitionSpec (fsTypes['ext2'], 16060L)
    foo.addPartition ("sda", parted.PARTITION_PRIMARY, spec)
    print foo.diskState ()    

    spec = PartitionSpec (fsTypes['ext2'], 16060L)
    foo.addPartition ("sda", parted.PARTITION_PRIMARY, spec)
    print foo.diskState ()    

    spec = PartitionSpec (fsTypes['ext2'], 16060L)
    foo.addPartition ("sda", parted.PARTITION_PRIMARY, spec)
    print foo.diskState ()    

    spec = PartitionSpec (fsTypes['ext2'], 16060L)
    foo.addPartition ("sda", parted.PARTITION_PRIMARY, spec)
    print foo.diskState ()    

    spec = PartitionSpec (fsTypes['ext2'], 16060L)
    foo.addPartition ("sda", parted.PARTITION_PRIMARY, spec)
    print foo.diskState ()    

    spec = PartitionSpec (fsTypes['ext2'], 16060L)
    foo.addPartition ("sda", parted.PARTITION_PRIMARY, spec)
    print foo.diskState ()    

    spec = PartitionSpec (fsTypes['ext2'], 16060L)
    foo.addPartition ("sda", parted.PARTITION_PRIMARY, spec)
    print foo.diskState ()    

    spec = PartitionSpec (fsTypes['ext2'], 16060L)
    foo.addPartition ("sda", parted.PARTITION_PRIMARY, spec)
    print foo.diskState ()    
