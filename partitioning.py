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
import sys
import string
import iutil
from translate import _
from log import log
from constants import *
from flags import flags

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

# when clearing partitions, what do we clear
CLEARPART_TYPE_LINUX = 1
CLEARPART_TYPE_ALL   = 2
CLEARPART_TYPE_NONE  = 3

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

class PartitioningWarning:
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
    return partition.geom.length 

def getPartSizeMB(partition):
    return (partition.geom.length * partition.geom.disk.dev.sector_size
            / 1024.0 / 1024.0)

def getDeviceSizeMB(dev):
    return (float(dev.heads * dev.cylinders * dev.sectors) / (1024 * 1024)
            * dev.sector_size)

def get_partition_by_name(disks, partname):
    for diskname in disks.keys():
        disk = disks[diskname]
        part = disk.next_partition()
        while part:
            if get_partition_name(part) == partname:
               return part

            part = disk.next_partition(part)

    return None

def get_partition_name(partition):
    if (partition.geom.disk.dev.type == parted.DEVICE_DAC960
        or partition.geom.disk.dev.type == parted.DEVICE_CPQARRAY):
        return "%sp%d" % (partition.geom.disk.dev.path[5:],
                          partition.num)
    return "%s%d" % (partition.geom.disk.dev.path[5:],
                     partition.num)

def get_partition_file_system_type(part):
    if part.fs_type == None:
        return None
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

def set_partition_file_system_type(part, fstype):
    if fstype == None:
        return
    try:
        for flag in fstype.getPartedPartitionFlags():
            if not part.is_flag_available(flag):
                raise PartitioningError, ("requested FileSystemType needs "
                                          "a flag that is not available.")
            part.set_flag(flag, 1)
        part.set_system(fstype.getPartedFileSystemType())
    except:
        print "Failed to set partition type to ",fstype.getName()
        pass

def get_partition_drive(partition):
    return "%s" %(partition.geom.disk.dev.path[5:])

def map_foreign_to_fsname(type):
    if type in allPartitionTypesDict.keys():
        return allPartitionTypesDict[type]
    else:
        return _("Foreign")

def query_is_linux_native_by_numtype(numtype):
    linuxtypes = [0x82, 0x83, 0xfd]

    for t in linuxtypes:
        if int(numtype) == t:
            return 1

    return 0

def filter_partitions(disk, func):
    rc = []
    part = disk.next_partition ()
    while part:
        if func(part):
            rc.append(part)
        part = disk.next_partition (part)

    return rc

def get_logical_partitions(disk):
    func = lambda part: (part.is_active()
                         and part.type & parted.PARTITION_LOGICAL)
    return filter_partitions(disk, func)

def get_primary_partitions(disk):
    func = lambda part: part.type == parted.PARTITION_PRIMARY
    return filter_partitions(disk, func)

# returns a list of partitions which can make up RAID devices
def get_raid_partitions(disk):
    func = lambda part: (part.is_active()
                         and part.get_flag(parted.PARTITION_RAID) == 1)
    return filter_partitions(disk, func)

# returns a list of the actual raid device requests
def get_raid_devices(requests):
    raidRequests = []
    for request in requests:
        if request.type == REQUEST_RAID:
            raidRequests.append(request)
            
    return raidRequests

def register_raid_device(mdname, newdevices, newlevel, newnumActive):
    for dev, devices, level, numActive in DiskSet.mdList:
        if mdname == dev:
            if (devices != newdevices or level != newlevel or
                numActive != newnumActive):
                raise ValueError, "%s is already in the mdList!" % (mdname,)
            else:
                return
    DiskSet.mdList.append((mdname, newdevices[:], newlevel, newnumActive))

def lookup_raid_device(mdname):
    for dev, devices, level, numActive in DiskSet.mdList:
        if mdname == dev:
            return (dev, devices, level, numActive)
    raise KeyError, "md device not found"

# returns a list of tuples of raid partitions which can be used or are used
# with whether they're used (0 if not, 1 if so)   eg (part, size, used)
def get_available_raid_partitions(diskset, requests, request):
    rc = []
    drives = diskset.disks.keys()
    raiddevs = get_raid_devices(requests.requests)
    drives.sort()
    for drive in drives:
        disk = diskset.disks[drive]
        for part in get_raid_partitions(disk):
            partname = get_partition_name(part)
            used = 0
            for raid in raiddevs:
                if raid.raidmembers:
                    for raidmem in raid.raidmembers:
                        if partname == requests.getRequestByID(raidmem).device:
                            if raid.device == request.device:
                                used = 2
                            else:
                                used = 1
                            break
                if used:
                    break

            if not used:
                rc.append((partname, getPartSizeMB(part), 0))
            elif used == 2:
                rc.append((partname, getPartSizeMB(part), 1))
    return rc

# set of functions to determine if the given level is RAIDX or X
def isRaid5(raidlevel):
    if raidlevel == "RAID5":
        return 1
    elif raidlevel == 5:
        return 1
    elif raidlevel == "5":
        return 1
    return 0

def isRaid1(raidlevel):
    if raidlevel == "RAID1":
        return 1
    elif raidlevel == 1:
        return 1
    elif raidlevel == "1":
        return 1
    return 0

def isRaid0(raidlevel):
    if raidlevel == "RAID0":
        return 1
    elif raidlevel == 0:
        return 1
    elif raidlevel == "0":
        return 1
    return 0


# return minimum numer of raid members required for a raid level
def get_raid_min_members(raidlevel):
    if isRaid0(raidlevel):
        return 2
    elif isRaid1(raidlevel):
        return 2
    elif isRaid5(raidlevel):
        return 3
    else:
        raise ValueError, "invalid raidlevel in get_raid_min_members"

# return max num of spares available for raidlevel and total num of members
def get_raid_max_spares(raidlevel, nummembers):
    if isRaid0(raidlevel):
        return 0
    elif isRaid1(raidlevel) or isRaid5(raidlevel):
        return max(0, nummembers - get_raid_min_members(raidlevel))
    else:
        raise ValueError, "invalid raidlevel in get_raid_max_spares"

def get_raid_device_size(raidrequest, partitions, diskset):
    if not raidrequest.raidmembers or not raidrequest.raidlevel:
        return 0
    
    raidlevel = raidrequest.raidlevel
    nummembers = len(raidrequest.raidmembers) - raidrequest.raidspares
    smallest = None
    sum = 0
    for member in raidrequest.raidmembers:
        req = partitions.getRequestByID(member)
        device = req.device
        part = get_partition_by_name(diskset.disks, device)
        partsize =  part.geom.length * part.geom.disk.dev.sector_size

        if isRaid0(raidlevel):
            sum = sum + partsize
        else:
            if not smallest:
                smallest = partsize
            elif partsize < smallest:
                smallest = partsize

    if isRaid0(raidlevel):
        return sum
    elif isRaid1(raidlevel):
        return smallest
    elif isRaid5(raidlevel):
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
        if (fstype and fstype.isMountable() and
            (reqtype == REQUEST_NEW or reqtype == REQUEST_RAID)):
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
                if (not newrequest.device
                    or request.device != newrequest.device):
                        used = 1                

                if used:
                    return _("The mount point %s is already in use, please "
                             "choose a different mount point." %(mntpt))
    return None

# figure out whether we should format by default
def isFormatOnByDefault(request):
    def inExceptionList(mntpt):
        exceptlist = ['/home', '/usr/local', '/opt', '/var/www']
        for q in exceptlist:
            if os.path.commonprefix([mntpt, q]) == q:
                return 1
        return 0
        
    # check first to see if its a Linux filesystem or not
    formatlist = ['/boot', '/var', '/tmp', '/usr']

    if not request.fstype:
        return 0

    if not request.fstype.isLinuxNativeFS():
        return 0

    if request.fstype.isMountable():
        mntpt = request.mountpoint
        if mntpt == "/":
            return 1

        if mntpt in formatlist:
            return 1
        
        for p in formatlist:
            if os.path.commonprefix([mntpt, p]) == p:
                if inExceptionList(mntpt):
                    return 0
                else:
                    return 1

        return 0
    else:
        if request.fstype.getName() == "swap":
            return 1

    # be safe for anything else and default to off
    return 0

def doMountPointLinuxFSChecks(newrequest):
    mustbeonroot = ['/bin','/dev','/sbin','/etc','/lib','/root','/mnt', 'lost+found', '/proc']
    mustbeonlinuxfs = ['/', '/boot', '/var', '/tmp', '/usr', '/home']

    if not newrequest.mountpoint:
        return None

    if newrequest.fstype == None:
        return None

    if newrequest.fstype.isMountable():    
        if newrequest.mountpoint in mustbeonroot:
            return _("This mount point is invalid.  This directory must "
                     "be on the / filesystem.")
        
    if not newrequest.fstype.isLinuxNativeFS():
        if newrequest.mountpoint in mustbeonlinuxfs:
            return _("This mount point must be on a linux filesystem.")

    return None
    
def doPartitionSizeCheck(newrequest):
    if not newrequest.fstype:
        return None

    if not newrequest.format:
        return None

    # XXX need to figure out the size for partitions specified by cyl range
    if newrequest.size and newrequest.size > newrequest.fstype.getMaxSize():
        return (_("The size of the %s partition (size = %s MB) "
                  "exceeds the maximum size of %s MB.")
                % (newrequest.fstype.getName(), newrequest.size,
                   newrequest.fstype.getMaxSize()))

    if (newrequest.size and newrequest.maxSize
        and (newrequest.size > newrequest.maxSize)):
        return (_("The size of the requested partition (size = %s MB) "
                 "exceeds the maximum size of %s MB.")
                % (newrequest.size, newrequest.maxSize))

    if newrequest.size and newrequest.size < 0:
        return _("The size of the requested partition is "
                 "negative! (size = %s MB)") % (newrequest.size)

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
def sanityCheckRaidRequest(reqpartitions, newraid, doPartitionCheck = 1):
    if not newraid.raidmembers or not newraid.raidlevel:
        return _("No members in RAID request, or not RAID level specified.")

    # XXX fix this sanity case
##     for member in newraid.raidmembers:
##         part = member.partition
##         if part.get_flag(parted.PARTITION_RAID) != 1:
##             return _("Some members of RAID request are not RAID partitions.")

    if doPartitionCheck:
        rc = sanityCheckPartitionRequest(reqpartitions, newraid)
        if rc:
            return rc

    # XXX fix this code to look to see if there is a bootable partition
    bootreq = reqpartitions.getBootableRequest()
    if not bootreq and newraid.mountpoint:
        if ((newraid.mountpoint == "/boot" or newraid.mountpoint == "/")
            and not isRaid1(newraid.raidlevel)):
            return _("Bootable partitions can only be on RAID1 devices.")

    minmembers = get_raid_min_members(newraid.raidlevel)
    if len(newraid.raidmembers) < minmembers:
        return _("A RAID device of type %s "
                 "requires at least %s members.") % (newraid.raidlevel,
                                                     minmembers)

    if newraid.raidspares:
        if (len(newraid.raidmembers) - newraid.raidspares) < minmembers:
            return _("This RAID device can have a maximum of %s spares. "
                     "To have more spares you will need to add members to "
                     "the RAID device.") % (len(newraid.raidmembers)
                                            - minmembers )
    return None

# return the actual size being used by the request in megabytes
def requestSize(req, diskset):
    if req.type == REQUEST_RAID:
        thissize = req.size
    else:
        part = get_partition_by_name(diskset.disks, req.device)
        if not part:
            # XXX hack for kickstart which ends up calling this
            # before allocating the partitions
            if req.size:
                thissize = req.size
            else:
                thissize = 0
        else:
            thissize = getPartSizeMB(part)
    return thissize

# this function is called at the end of partitioning so that we
# can make sure you don't have anything silly (like no /, a really small /,
# etc).  returns (errors, warnings) where each is a list of strings or None
# if there are none
# if baseChecks is set, the basic sanity tests which the UI runs prior to
# accepting a partition will be run on the requests
def sanityCheckAllRequests(requests, diskset, baseChecks = 0):
    checkSizes = [('/usr', 250), ('/tmp', 50), ('/var', 50),
                  ('/home', 100), ('/boot', 20)]
    warnings = []
    errors = []

    slash = requests.getRequestByMountPoint('/')
    if not slash:
        errors.append(_("You have not defined a root partition (/), which is required for installation of Red Hat Linux to continue."))

    if slash and requestSize(slash, diskset) < 250:
        warnings.append(_("Your root partition is less than 250 megabytes which is usually too small to install Red Hat Linux."))

    if iutil.getArch() == "ia64":
        bootreq = requests.getRequestByMountPoint("/boot/efi")
        if not bootreq or requestSize(bootreq, diskset) < 50:
            errors.append(_("You must create a /boot/efi partition of type "
                            "FAT and a size of 50 megabytes."))

    for (mount, size) in checkSizes:
        req = requests.getRequestByMountPoint(mount)
        if not req:
            continue
        if requestSize(req, diskset) < size:
            warnings.append(_("Your %s partition is less than %s megabytes which is lower than recommended for a normal Red Hat Linux install.") %(mount, size))

    foundSwap = 0
    swapSize = 0
    for request in requests.requests:
        if request.fstype and request.fstype.getName() == "swap":
            foundSwap = foundSwap + 1
            swapSize = swapSize + requestSize(request, diskset)
        if baseChecks:
            rc = doPartitionSizeCheck(request)
            if rc:
                warnings.append(rc)
            rc = doMountPointLinuxFSChecks(request)
            if rc:
                errors.append(rc)
            if request.type == REQUEST_RAID:
                rc = sanityCheckRaidRequest(requests, request, 0)
                if rc:
                    errors.append(rc)

    bootreq = requests.getBootableRequest()
    if (bootreq and (bootreq.type == REQUEST_RAID) and
        (not isRaid1(bootreq.raidlevel))):
        errors.append(_("Bootable partitions can only be on RAID1 devices."))
                
        
    if foundSwap == 0:
        warnings.append(_("You have not specified a swap partition.  Although not strictly required in all cases, it will significantly improve performance for most installations."))

    # XXX number of swaps not exported from kernel and could change
    if foundSwap >= 32:
        warnings.append(_("You have specified more than 32 swap devices.  The kernel for Red Hat Linux only supports 32 swap devices."))

    mem = iutil.memInstalled(corrected = 0)
    rem = mem % 16384
    if rem:
        mem = mem + (16384 - rem)
    mem = mem / 1024

    if foundSwap and (swapSize < (mem - 8)) and (mem < 1024):
        warnings.append(_("You have allocated less swap space (%dM) than available RAM (%dM) on your system.  This could negatively impact performance.") %(swapSize, mem))

    if warnings == []:
        warnings = None
    if errors == []:
        errors = None

    return (errors, warnings)

# create nice text formatted list of pre-existing partitions which will be
# formatted
def getPreExistFormatWarnings(partitions, diskset):

    devs = []
    for request in partitions.requests:
        if request.type == REQUEST_PREEXIST and request.device:
            devs.append(request.device)

    devs.sort()
    
    rc = []
    for dev in devs:
        request = partitions.getRequestByDeviceName(dev)
        if request.format:
            if request.fstype.isMountable():
                mntpt = request.mountpoint
            else:
                mntpt = ""
                
            rc.append((request.device, request.fstype.getName(), mntpt))

    if len(rc) == 0:
        return None
    else:
        return rc
            


# add delete specs to requests for all logical partitions in part
def deleteAllLogicalPartitions(part, requests):
    for partition in get_logical_partitions(part.geom.disk):
        request = requests.getRequestByDeviceName(get_partition_name(partition))
        requests.removeRequest(request)
        if request.type == REQUEST_PREEXIST:
            drive = get_partition_drive(partition)
            delete = DeleteSpec(drive, partition.geom.start, partition.geom.end)
            requests.addDelete(delete)

# get the default partition table type for our architecture
def getDefaultDiskType():
    if iutil.getArch() == "i386":
        return parted.disk_type_get("msdos")
    elif iutil.getArch() == "ia64":
        return parted.disk_type_get("GPT")
    else:
        # XXX fix me for alpha at least
        return parted.disk_type_get("msdos")

archLabels = {'i386': ['msdos'],
              'alpha': ['bsd'],
              'ia64': ['msdos', 'GPT']}

def checkDiskLabel(disk, intf):
    arch = iutil.getArch()
    if arch in archLabels.keys():
        if disk.type.name in archLabels[arch]:
            return 0
    else:
        if disk.type.name == "msdos":
            return 0

    if intf:
        rc = intf.messageWindow(_("Warning"),
                       _("The partition table on device /dev/%s is of an "
                         "unexpected type for your architecture.  To use this "
                         "disk for installation of Red Hat Linux, it must be "
                         "re-initialized causing the loss of ALL DATA on this "
                         "drive.\n\n"
                         "Would you like to initialize this drive?")
                       % (disk.dev.path[5:]), type = "yesno")
        if rc == 0:
            return 1
        else:
            return -1
    else:
        return 1

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
                 mountpoint = None, origfstype = None,
                 start = None, end = None, partnum = None,
                 drive = None, primary = None,
                 format = None, options = None, 
                 constraint = None, migrate = None,
                 raidmembers = None, raidlevel = None, 
                 raidspares = None, badblocks = None, fslabel = None):
        #
        # requesttype: REQUEST_PREEXIST or REQUEST_NEW or REQUEST_RAID
        #
        # XXX: unenforced requirements for a partition spec
        # must have (size) || (start && end)
        #           fs_type, mountpoint
        #           if partnum, require drive
        #
        # Some notes:
        #   format  - if is 1, format.
        #   migrate - if is 1, convert from origfstype to fstype.
        #
        self.type = requesttype
        self.fstype = fstype
        self.origfstype = origfstype
        self.size = size
        self.grow = grow
        self.maxSize = maxSize
        self.mountpoint = mountpoint
        self.start = start
        self.end = end
        self.partnum = partnum
        self.drive = drive
        self.primary = primary
        self.format = format
        self.badblocks = badblocks
        self.migrate = migrate
        self.options = options
        self.constraint = constraint
        self.partition = None
        self.requestSize = size
        # note that the raidmembers are the unique id of the requests
        self.raidmembers = raidmembers
        self.raidlevel = raidlevel
        self.raidspares = raidspares

        # fs label (if pre-existing, otherwise None)
        self.fslabel = fslabel
        
        # device is what we currently think the device is
        # realDevice is used by partitions which are pre-existing
        self.device = None
        self.realDevice = None

        # there has to be a way to go from device -> drive... but for now
        self.currentDrive = None

        # unique id for each request
        self.uniqueID = None

        # ignore booting constraints for this request
        self.ignoreBootConstraints = 0

    def __str__(self):
        if self.fstype:
            fsname = self.fstype.getName()
        else:
            fsname = "None"
        raidmem = []
        if self.raidmembers:
            for i in self.raidmembers:
                raidmem.append(i)
                
        return "mountpoint: %s   type: %s   uniqueID:%s\n" %(self.mountpoint, fsname, self.uniqueID) +\
               "  size: %sM   requestSize: %sM  grow: %s   max: %s\n" %(self.size, self.requestSize, self.grow, self.maxSize) +\
               "  start: %s   end: %s   partnum: %s\n" %(self.start, self.end, self.partnum) +\
               "  drive: %s   primary: %s  \n" %(self.drive, self.primary) +\
               "  format: %s, options: %s" %(self.format, self.options) +\
               "  device: %s, currentDrive: %s\n" %(self.device, self.currentDrive)+\
               "  raidlevel: %s" % (self.raidlevel)+\
               "  raidspares: %s" % (self.raidspares)+\
               "  raidmembers: %s" % (raidmem)

    # turn a partition request into a fsset entry
    def toEntry(self, partitions):
        if self.type == REQUEST_RAID:
            raidmems = []
            for member in self.raidmembers:
                raidmems.append(partitions.getRequestByID(member).device)
            device = fsset.RAIDDevice(int(self.raidlevel[-1:]),
                                      raidmems,
                                      spares = self.raidspares)
        else:
            device = fsset.PartitionDevice(self.device)

        # pin down our partitions so that we can reread the table
        device.solidify()
        
        if self.fstype.getName() == "swap":
            mountpoint = "swap"
        else:
            mountpoint = self.mountpoint

        entry = fsset.FileSystemSetEntry(device, mountpoint, self.fstype,
                                         origfsystem=self.origfstype)
        if self.format:
            entry.setFormat(self.format)

        if self.migrate:
            entry.setMigrate(self.migrate)

        if self.badblocks:
            entry.setBadblocks(self.badblocks)
            
        return entry

class Partitions:
    def __init__ (self, diskset = None):
        # requests for partitions including preexisting partitions
        # a list of PartitionSpec objects
        self.requests = []

        # preexisting partitions which should be deleted
        # a list of DeleteSpec objects
        self.deletes = []

        # auto partitioning requests
        # a list of PartitionSpec objects
        # these are set by the installclass and then folded into self.requests
        self.autoPartitionRequests = []

        # CLEARPART_TYPE_LINUX, CLEARPART_TYPE_ALL, CLEARPART_TYPE_NONE
        # used by installclasses to say which partitions to clear
        self.autoClearPartType = CLEARPART_TYPE_NONE

        # drives to clear partitions on (following self.autoClearPartType)
        # note that None clears ALL drives 
        self.autoClearPartDrives = None

        # internal counter... if you use it as an ID, increment it to avoid
        # problems later on
        self.nextUniqueID = 1

        # reinitialize all partitions to default labels?
        self.reinitializeDisks = 0

        # zero mbr flag for kickstart
        self.zeroMbr = 0

        # partition method
        self.useAutopartitioning = 1
        self.useFdisk = 0

        # autopartitioning info becomes kickstart partition requests
        # and its useful to be able to differentiate between the two
        self.isKickstart = 0

        if diskset:
            self.setFromDisk(diskset)


    # clear out the delete list and initialize all partitions which
    # currently exist on the disk
    def setFromDisk(self, diskset):
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
                elif part.fs_type:
                    ptype = get_partition_file_system_type(part)
                    if part.fs_type.name == "linux-swap":
                        # XXX this is a hack
                        format = 1
                else:
                    ptype = fsset.fileSystemTypeGet("foreign")
                    
                start = part.geom.start
                end = part.geom.end
                size = getPartSizeMB(part)
                drive = get_partition_drive(part)
                
                spec = PartitionSpec(ptype, origfstype = ptype,
                                     requesttype = REQUEST_PREEXIST,
                                     start = start, end = end, size = size,
                                     drive = drive, format = format)
                spec.device = fsset.PartedPartitionDevice(part).getDevice()

                # set label if makes sense
                if ptype and ptype.isMountable() and \
                   (ptype.getName() == "ext2" or ptype.getName() == "ext3"):
                    if spec.device in labels.keys():
                        if labels[spec.device] and len(labels[spec.device])>0:
                            spec.fslabel = labels[spec.device]

                self.addRequest(spec)
                part = disk.next_partition(part)

    def addRequest (self, request):
#        print "adding %s" %(self.nextUniqueID)
        if not request.uniqueID:
            request.uniqueID = self.nextUniqueID
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

    def getRequestByID(self, id):
        for request in self.requests:
            if request.uniqueID == id:
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
                if request.device == self.getRequestByID(member).device:
                    return 1
        return 0

    # return name of boot mount point in current requests
    def getBootableRequest(self):
        bootreq = None

        if iutil.getArch() == "ia64":
            bootreq = self.getRequestByMountPoint("/boot/efi")
            return bootreq
        if not bootreq:
            bootreq = self.getRequestByMountPoint("/boot")
        if not bootreq:
            bootreq = self.getRequestByMountPoint("/")
            
        return bootreq

    # returns if request is a "bootable"
    # returns 0 if not, returns 1 if it is returned by getBootableRequest
    # or is a member of the RAID request returned by getBootableRequest
    def isBootable(self, request):
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
                if ((type(request.uniqueID) != type("")) or 
                    (request.uniqueID[0:5] != "raid.")):
                    args.append("raid.%s" % (request.uniqueID))
                else:
                    args.append("%s" % (request.uniqueID))
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
                if request.maxSize:
                    args.append("--maxsize=%s" % (request.maxSize))
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

class DiskSet:
    skippedDisks = []
    mdList = []
    def __init__ (self):
        self.disks = {}

    def startAllRaid(self):
        driveList = []
        origDriveList = self.driveList()
        for drive in origDriveList:
            if not drive in DiskSet.skippedDisks:
                driveList.append(drive)
        DiskSet.mdList.extend(raid.startAllRaid(driveList))

    def stopAllRaid(self):
        raid.stopAllRaid(DiskSet.mdList)
        while DiskSet.mdList:
            DiskSet.mdList.pop()

    def getLabels(self):
        labels = {}
        
        drives = self.disks.keys()
        drives.sort()

        for drive in drives:
            disk = self.disks[drive]
            func = lambda part: (part.is_active() and
                                 not (part.get_flag(parted.PARTITION_RAID)
                                      or part.get_flag(parted.PARTITION_LVM))
                                 and part.fs_type
                                 and (part.fs_type.name == "ext2"
                                      or part.fs_type.name == "ext3"))
            parts = filter_partitions(disk, func)
            for part in parts:
                node = get_partition_name(part)
                label = isys.readExt2Label(node)
                if label:
                    labels[node] = label

        for dev, devices, level, numActive in DiskSet.mdList:
            label = isys.readExt2Label(dev)
            if label:
                labels[dev] = label

        return labels

    def findExistingRootPartitions(self, intf):
        rootparts = []

        self.startAllRaid()

        for dev, devices, level, numActive in self.mdList:
            # XXX multifsify.
            # XXX NOTE!  reiserfs isn't supported on software raid devices.
            if not fsset.isValidExt2 (dev):
                continue

            try:
                isys.mount(dev, '/mnt/sysimage', readOnly = 1)
            except SystemError, (errno, msg):
                try:
                    isys.mount(dev, '/mnt/sysimage', "ext3", readOnly = 1)
                except SystemError, (errno, msg):
                    intf.messageWindow(_("Error"),
                                       _("Error mounting filesystem "
                                         "on %s: %s") % (dev, msg))
                    continue
            if os.access ('/mnt/sysimage/etc/fstab', os.R_OK):
                rootparts.append ((dev, "ext2"))
            isys.umount('/mnt/sysimage')

        self.stopAllRaid()

        drives = self.disks.keys()
        drives.sort()

        for drive in drives:
            disk = self.disks[drive]
            part = disk.next_partition ()
            while part:
                if (part.is_active()
                    and (part.get_flag(parted.PARTITION_RAID)
                         or part.get_flag(parted.PARTITION_LVM))):
                    # skip RAID and LVM partitions.
                    # XXX check for raid superblocks on non-autoraid partitions
                    #  (#32562)
                    pass
                elif part.fs_type and (part.fs_type.name == "ext2"
                                     or part.fs_type.name == "ext3"
                                     or part.fs_type.name == "reiserfs"):
                    node = get_partition_name(part)
		    try:
			isys.mount(node, '/mnt/sysimage', part.fs_type.name)
		    except SystemError, (errno, msg):
			intf.messageWindow(_("Error"),
                                           _("Error mounting filesystem on "
                                             "%s: %s") % (node, msg))
                        part = disk.next_partition(part)
			continue
		    if os.access ('/mnt/sysimage/etc/fstab', os.R_OK):
			rootparts.append ((node, part.fs_type.name))
		    isys.umount('/mnt/sysimage')
                elif part.fs_type and (part.fs_type.name == "FAT"):
                    node = get_partition_name(part)
                    try:
                        isys.mount(node, '/mnt/sysimage', fstype = "vfat",
                                   readOnly = 1)
                    except:
			log("failed to mount vfat filesystem on %s\n" 
                            % node)
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

    def refreshDevices (self, intf = None, initAll = 0, zeroMbr = 0):
        self.disks = {}
        self.openDevices(intf, initAll, zeroMbr)

    def closeDevices (self):
        for disk in self.disks.keys():
            del self.disks[disk]

    def openDevices (self, intf = None, initAll = 0, zeroMbr = 0):
        if self.disks:
            return
        for drive in self.driveList ():
            if drive in DiskSet.skippedDisks and not initAll:
                continue
            deviceFile = isys.makeDevInode(drive)
            if isys.driveIsRemovable(drive) and not flags.expert:
                DiskSet.skippedDisks.append(drive)
                continue
            try:
                dev = parted.PedDevice.get (deviceFile)
            except parted.error, msg:
                DiskSet.skippedDisks.append(drive)
                continue
            if initAll and not flags.test:
                try:
                    dev.disk_create(getDefaultDiskType())
                    disk = parted.PedDisk.open(dev)
                    self.disks[drive] = disk
                except parted.error, msg:
                    DiskSet.skippedDisks.append(drive)
                continue
                
            try:
                disk = parted.PedDisk.open(dev)
                self.disks[drive] = disk
            except parted.error, msg:
                recreate = 0
                if zeroMbr:
                    log("zeroMBR was set and invalid partition table found "
                        "on %s" % (dev.path[5:]))
                    recreate = 1
                elif not intf:
                    DiskSet.skippedDisks.append(drive)
                    continue
                else:
                    rc = intf.messageWindow(_("Warning"),
                             _("The partition table on device %s was unreadable. "
                               "To create new partitions it must be initialized, "
                               "causing the loss of ALL DATA on this drive.\n\n"
                               "Would you like to initialize this drive?")
                                           % (drive,), type = "yesno")
                    if rc == 0:
                        DiskSet.skippedDisks.append(drive)
                        continue
                    else:
                        recreate = 1
                if recreate == 1 and not flags.test:
                    try:
                        dev.disk_create(getDefaultDiskType())
                        disk = parted.PedDisk.open(dev)
                        self.disks[drive] = disk
                    except parted.error, msg:
                        DiskSet.skippedDisks.append(drive)
                        continue

            # check that their partition table is valid for their architecture
            ret = checkDiskLabel(disk, intf)
            if ret == 1:
                DiskSet.skippedDisks.append(drive)
                continue
            elif ret == -1:
                try:
                    dev.disk_create(getDefaultDiskType())
                    disk = parted.PedDisk.open(dev)
                    self.disks[drive] = disk
                except parted.error, msg:
                    DiskSet.skippedDisks.append(drive)
                    continue

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
                    rc.append((device, ptype))
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

def checkNoDisks(diskset, intf):
    if len(diskset.disks.keys()) == 0:
        intf.messageWindow(_("No Drives Found"),
                           _("An error has occurred - no valid devices were "
                             "found on which to create new filesystems. "
                             "Please check your hardware for the cause "
                             "of this problem."))
        sys.exit(0)

def partitionObjectsInitialize(diskset, partitions, dir, intf):
    if dir == DISPATCH_BACK:
        diskset.closeDevices()
        return

    # read in drive info
    diskset.refreshDevices(intf, partitions.reinitializeDisks,
                           partitions.zeroMbr)

    checkNoDisks(diskset, intf)

    partitions.setFromDisk(diskset)

# set the protected partitions
def setProtected(partitions, dispatch):
    protected = dispatch.method.protectedPartitions()
    if protected:
        for device in protected:
            log("%s is a protected partition" % (device))
            request = partitions.getRequestByDeviceName(device)
            request.type = REQUEST_PROTECTED

def partitionMethodSetup(partitions, dispatch):

    # turn on/off step based on 3 paths:
    #  - use fdisk, then set mount points
    #  - use autopartitioning, then set mount points
    #  - use interactive partitioning tool, continue

    dispatch.skipStep("autopartition",
                      skip = not partitions.useAutopartitioning)
    dispatch.skipStep("autopartitionexecute",
                      skip = not partitions.useAutopartitioning)
    dispatch.skipStep("fdisk", skip = not partitions.useFdisk)

    setProtected(partitions, dispatch)

    
# shorthand mainly for installclasses
#
# make a list of tuples of the form:
#    (mntpt, fstype, minsize, maxsize, grow, format)
#
# mntpt = None for non-mountable, otherwise is mount point
# fstype = None to use default, otherwise a string
# minsize = smallest size
# maxsize = max size, or None means no max
# grow = 0 or 1, should partition be grown
# format = 0 or 1, whether to format
#
def autoCreatePartitionRequests(autoreq):
    requests = []
    for (mntpt, fstype, minsize, maxsize, grow, format) in autoreq:
        if fstype:
            ptype = fsset.fileSystemTypeGet(fstype)
        else:
            ptype = fsset.fileSystemTypeGetDefault()
            
        newrequest = PartitionSpec(ptype,
                                   mountpoint = mntpt,
                                   size = minsize,
                                   maxSize = maxsize,
                                   grow = grow,
                                   requesttype = REQUEST_NEW,
                                   format = format)
        
        requests.append(newrequest)

    return requests

# returns shorthand (see above) request for the "boot" dir
# depends on arch 
def getAutopartitionBoot():
    if iutil.getArch() == "ia64":
        return ("/boot/efi", "vfat", 100, None, 0, 1)
    else:
        return ("/boot", None, 50, None, 0, 1)
        

def confirmDeleteRequest(intf, request):
    if request.device:
        if request.type == REQUEST_RAID:
            errmsg = _("You are about to delete a RAID device.\n\n"
                       "Are you sure?")
        else:
            errmsg = _("You are about to delete the /dev/%s partition.\n\n"
                       "Are you sure?" % request.device)
            
    else:
        errmsg = _("Are you sure you want to delete this partition?")

    rc = intf.messageWindow(_("Confirm Delete"), errmsg, type="yesno")
    return rc

def confirmResetPartitionState(intf):
    rc = intf.messageWindow(_("Confirm Reset"),
                            _("Are you sure you want to reset the "
                              "partition table to its original state?"),
                            type="yesno")
    return rc

# does this partition contain partitions we can't delete?
def containsImmutablePart(part, requestlist):
    if not part or (type(part) == type("RAID")) or (type(part) == type(1)):
        return None
    
    if not part.type & parted.PARTITION_EXTENDED:
        return None

    disk = part.geom.disk
    while part:
        if not part.is_active():
            part = disk.next_partition(part)
            continue

        device = get_partition_name(part)
        request = requestlist.getRequestByDeviceName(device)

        if request:
            if request.type == REQUEST_PROTECTED:
                return _("the partition in use by the installer.")

            if requestlist.isRaidMember(request):
                return _("a partition which is a member of a RAID array.")
        
        part = disk.next_partition(part)
#
# handle deleting a partition - pass in the list of requests and the
# partition to be deleted
#
def doDeletePartitionByRequest(intf, requestlist, partition):
    if partition == None:
        intf.messageWindow(_("Unable To Remove"),
                           _("You must first select a partition to remove."))
        return 0
    elif type(partition) == type("RAID"):
        device = partition
    elif partition.type & parted.PARTITION_FREESPACE:
        intf.messageWindow(_("Unable To Remove"),
                           _("You cannot remove free space."))
        return 0
    else:
        device = get_partition_name(partition)

    ret = containsImmutablePart(partition, requestlist)
    if ret:
        intf.messageWindow(_("Unable To Remove"),
                           _("You cannot remove this "
                             "partition, as it is an extended partition "
                             "which contains %s") %(ret))
        return 0
        

    # see if device is in our partition requests, remove
    request = requestlist.getRequestByDeviceName(device)
    if request:
        if request.type == REQUEST_PROTECTED:
            intf.messageWindow(_("Unable To Remove"),
                               _("You cannot remove this "
                                 "partition, as it is holding the data for "
                                 "the hard drive install."))
            return 0

        if requestlist.isRaidMember(request):
            intf.messageWindow(_("Unable To Remove"),
                               _("You cannot remove this "
                                 "partition, as it is part of a RAID device."))
            return 0

        if confirmDeleteRequest(intf, request):
            requestlist.removeRequest(request)
        else:
            return 0

        if request.type == REQUEST_PREEXIST:
            # get the drive
            drive = get_partition_drive(partition)

            if partition.type & parted.PARTITION_EXTENDED:
                deleteAllLogicalPartitions(partition, requestlist)

            delete = DeleteSpec(drive, partition.geom.start,
                                partition.geom.end)
            requestlist.addDelete(delete)
    else: # is this a extended partition we made?
        if partition.type & parted.PARTITION_EXTENDED:
            deleteAllLogicalPartitions(partition, requestlist)
        else:
            raise ValueError, "Deleting a non-existent partition"

    del partition
    return 1


def doEditPartitionByRequest(intf, requestlist, part):
    if part == None:
        intf.messageWindow(_("Unable To Edit"),
                           _("You must select a partition to edit"))

        return (None, None)
    elif type(part) == type("RAID"):
        request = requestlist.getRequestByDeviceName(part)

        return ("RAID", request)
    elif part.type & parted.PARTITION_FREESPACE:
        request = PartitionSpec(fsset.fileSystemTypeGetDefault(), REQUEST_NEW,
                                start = start_sector_to_cyl(part.geom.disk.dev,
                                                            part.geom.start),
                                end = end_sector_to_cyl(part.geom.disk.dev,
                                                        part.geom.end),
                                drive = [ get_partition_drive(part) ])

        return ("NEW", request)
    elif part.type & parted.PARTITION_EXTENDED:
        return (None, None)

    ret = containsImmutablePart(part, requestlist)
    if ret:
        intf.messageWindow(_("Unable To Edit"),
                           _("You cannot edit this "
                             "partition, as it is an extended partition "
                             "which contains %s") %(ret))
        return 0

    request = requestlist.getRequestByDeviceName(get_partition_name(part))
    if request:
        if requestlist.isRaidMember(request):
            intf.messageWindow( _("Unable to Edit"),
                               _("You cannot edit this partition "
                                 "as it is part of a RAID device"))
            return (None, None)

        return ("PARTITION", request)
    else: # shouldn't ever happen
        raise ValueError, ("Trying to edit non-existent partition %s"
                           % (get_partition_name(part)))
    
    
def partitioningComplete(bl, fsset, diskSet, partitions, intf, instPath, dir):
    if dir == DISPATCH_BACK and fsset.isActive():
        rc = intf.messageWindow(_("Installation cannot continue."),
                                _("The partitioning options you have chosen "
                                  "have already been activated. You can "
                                  "no longer return to the disk editing "
                                  "screen. Would you like to continue "
                                  "with the installation process?"),
                                type = "yesno")
        if rc == 0:
            sys.exit(0)
        return DISPATCH_FORWARD
        
    fsset.reset()
    for request in partitions.requests:
        # XXX improve sanity checking
        if (not request.fstype or (request.fstype.isMountable()
                                   and not request.mountpoint)):
            continue
        entry = request.toEntry(partitions)
        fsset.add (entry)
    if iutil.memInstalled() > isys.EARLY_SWAP_RAM:
        return
    rc = intf.messageWindow(_("Low Memory"),
                            _("As you don't have much memory in this "
                              "machine, we need to turn on swap space "
                              "immediately. To do this we'll have to "
                              "write your new partition table to the disk "
                              "immediately. Is that okay?"), "okcancel")
    if rc:
        fsset.setActive(diskSet)
        diskSet.savePartitions ()
        fsset.formatSwap(instPath)
        fsset.turnOnSwap(instPath)

def checkForSwapNoMatch(intf, diskset, partitions):
    for request in partitions.requests:
        if not request.device or not request.fstype:
            continue
        
        part = get_partition_by_name(diskset.disks, request.device)
        if (part and (not part.type & parted.PARTITION_FREESPACE) and (part.native_type == 0x82) and (request.fstype and request.fstype.getName() != "swap") and (not request.format)):
            rc = intf.messageWindow(_("Format as Swap?"),
                                    _("/dev/%s has a partition type of 0x82 "
                                      "(Linux swap) but does not appear to "
                                      "be formatted as a Linux swap "
                                      "partition.\n\n"
                                      "Would you like to format this "
                                      "partition as a swap partition?")
                                    % (request.device), type = "yesno")
            if rc == 1:
                request.format = 1
                request.fstype = fsset.fileSystemTypeGet("swap")
                if request.fstype.getName() == "software RAID":
                    part.set_flag(parted.PARTITION_RAID, 1)
                else:
                    part.set_flag(parted.PARTITION_RAID, 0)
                    
                set_partition_file_system_type(part, request.fstype)


def queryFormatPreExisting(intf):
    rc = intf.messageWindow(_("Format?"),
                            _("You have chosen to format a pre-existing "
                              "partition.  This will destroy all data "
                              "that was previously on it.\n\n"
                              "Are you sure you want to do this?"),
                            type = "yesno", default = "no")
    return rc

def queryNoFormatPreExisting(intf):
    txt = _("You have chosen not to format a pre-existing "
            "partition which is being mounted under a "
            "system directory.  Unless you have particular "
            "needs to preserve data on this partition, it is highly "
            "recommended you format this partition to "
            "guarantee the data formerly on the partition "
            "does not corrupt your new installation.\n\n"
            "Are you sure you want to do this?")

    rc = intf.messageWindow(_("Format?"), txt, type = "yesno", default = "no")
    return rc

def partitionSanityErrors(intf, errors):
    rc = 1
    if errors:
        errorstr = string.join(errors, "\n\n")
        rc = intf.messageWindow(_("Error with Partitioning"),
                                _("The following critical errors exist "
                                  "with your requested partitioning "
                                  "scheme. "
                                  "These errors must be corrected prior "
                                  "to continuing with your install of "
                                  "Red Hat Linux.\n\n%s") %(errorstr))    
    return rc


def partitionSanityWarnings(intf, warnings):
    rc = 1
    if warnings:
        warningstr = string.join(warnings, "\n\n")
        rc = intf.messageWindow(_("Partitioning Warning"),
                                     _("The following warnings exist with "
                                       "your requested partition scheme.\n\n%s"
                                       "\n\nWould you like to continue with "
                                       "your requested partitioning "
                                       "scheme?") % (warningstr),
                                     type="yesno")
    return rc

def partitionPreExistFormatWarnings(intf, warnings):
    rc = 1
    if warnings:

        labelstr1 = _("The following pre-existing partitions have been "
                      "selected to be formatted, destroying all data.")

        labelstr2 = _("Select 'Yes' to continue and format these "
                      "partitions, or 'No' to go back and change these "
                      "settings.")
        commentstr = ""
        for (dev, type, mntpt) in warnings:
            commentstr = commentstr + "/dev/%s %s %s\n" % (dev,type,mntpt)
        rc = intf.messageWindow(_("Format Warning"), "%s\n\n%s\n\n%s" %
                                (labelstr1, labelstr2, commentstr),
                                type="yesno")
    return rc

# XXX is this all of the possibilities?
dosPartitionTypes = [ 1, 6, 11, 12, 14, 15 ]

# master list of partition types
allPartitionTypesDict = {
    0 : "Empty",
    1: "DOS 12-bit FAT",
    2: "XENIX root",
    3: "XENIX usr",
    4: "DOS 16-bit <32M",
    5: "Extended",
    6: "DOS 16-bit >=32M",
    7: "NTFS/HPFS",
    8: "AIX",
    9: "AIX bootable",
    10: "OS/2 Boot Manager",
    0xb: "Win95 FAT32",
    0xc: "Win95 FAT32",
    0xe: "Win95 FAT16",
    0xf: "Win95 Ext'd",
    0x10: "OPUS",
    0x11: "Hidden FAT12",
    0x12: "Compaq Setup",
    0x14: "Hidden FAT16 <32M",
    0x16: "Hidden FAT16",
    0x17: "Hidden HPFS/NTFS",
    0x18: "AST SmartSleep",
    0x1b: "Hidden Win95 FAT32",
    0x1c: "Hidden Win95 FAT32 (LBA)",
    0x1e: "Hidden Win95 FAT16 (LBA)",
    0x24: "NEC_DOS",
    0x39: "Plan 9",
    0x40: "Venix 80286",
    0x41: "PPC_PReP Boot",
    0x42: "SFS",
    0x4d: "QNX4.x",
    0x4e: "QNX4.x 2nd part",
    0x4f: "QNX4.x 2nd part",
    0x51: "Novell?",
    0x52: "Microport",
    0x63: "GNU HURD",
    0x64: "Novell Netware 286",
    0x65: "Novell Netware 386",
    0x75: "PC/IX",
    0x80: "Old MINIX",
    0x81: "Linux/MINIX",
    0x82: "Linux swap",
    0x83: "Linux native",
    0x84: "OS/2 hidden C:",
    0x85: "Linux Extended",
    0x86: "NTFS volume set",
    0x87: "NTFS volume set",
    0x8e: "Linux LVM",
    0x93: "Amoeba",
    0x94: "Amoeba BBT",
    0x9f: "BSD/OS",
    0xa0: "IBM Thinkpad hibernation",
    0xa5: "BSD/386",
    0xa6: "OpenBSD",
    0xb7: "BSDI fs",
    0xb8: "BSDI swap",
    0xc7: "Syrinx",
    0xdb: "CP/M",
    0xde: "Dell Utility",
    0xe1: "DOS access",
    0xe3: "DOS R/O",
    0xeb: "BEOS",
    0xee: "EFI GPT",    
    0xef: "EFI (FAT-12/16/32)",
    0xf2: "DOS secondary",
    0xfd: "Linux RAID",
    0xff: "BBT"
    }
