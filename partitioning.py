#
# partitioning.py: partitioning and other disk management
#
# Matt Wilson <msw@redhat.com>
# Jeremy Katz <katzj@redhat.com>
# Mike Fulbright <msf@redhat.com>
# Harald Hoyer <harald@redhat.de>
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

import isys
import parted
import raid
import fsset
import os
import sys
import string
import iutil
import partedUtils
import raid
from translate import _
from log import log
from constants import *
from flags import flags
from partErrors import *
import partRequests

def query_is_linux_native_by_numtype(numtype):
    linuxtypes = [0x82, 0x83, 0x8e, 0xfd]

    for t in linuxtypes:
        if int(numtype) == t:
            return 1

    return 0

# returns a list of the actual raid device requests
def get_lvm_volume_groups(requests):
    raidRequests = []
    for request in requests:
        if request.type == REQUEST_VG:
            raidRequests.append(request)
            
    return raidRequests

# returns a list of the actual raid device requests
def get_raid_devices(requests):
    raidRequests = []
    for request in requests:
        if request.type == REQUEST_RAID:
            raidRequests.append(request)
            
    return raidRequests

def register_raid_device(mdname, newdevices, newlevel, newnumActive):
    for dev, devices, level, numActive in partedUtils.DiskSet.mdList:
        if mdname == dev:
            if (devices != newdevices or level != newlevel or
                numActive != newnumActive):
                raise ValueError, "%s is already in the mdList!" % (mdname,)
            else:
                return
    partedUtils.DiskSet.mdList.append((mdname, newdevices[:], newlevel,
                                       newnumActive))

def lookup_raid_device(mdname):
    for dev, devices, level, numActive in partedUtils.DiskSet.mdList:
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
        for part in partedUtils.get_raid_partitions(disk):
            partname = partedUtils.get_partition_name(part)
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
                rc.append((partname, partedUtils.getPartSizeMB(part), 0))
            elif used == 2:
                rc.append((partname, partedUtils.getPartSizeMB(part), 1))
    return rc

# returns a list of tuples of lvm partitions which can be used or are used
# with whether they're used (0 if not, 1 if so)   eg (part, size, used)
def get_available_lvm_partitions(diskset, requests, request):
    rc = []
    drives = diskset.disks.keys()
    drives.sort()
    volgroups = get_lvm_volume_groups(requests.requests)
    for drive in drives:
        disk = diskset.disks[drive]
        for part in partedUtils.get_lvm_partitions(disk):
            partname = partedUtils.get_partition_name(part)
	    partrequest = requests.getRequestByDeviceName(partname)
	    used = 0
	    for volgroup in volgroups:
		if volgroup.physicalVolumes:
		    if partrequest.uniqueID in volgroup.physicalVolumes:
			if request and request.uniqueID and volgroup.uniqueID == request.uniqueID:
			    used = 2
			else:
			    used = 1

		if used:
		    break

	    if used == 0:
		rc.append((partname, partedUtils.getPartSizeMB(part), 0))
            elif used == 2:
                rc.append((partname, partedUtils.getPartSizeMB(part), 1))
    return rc

def get_lvm_volume_group_size(request, requests, diskset):
	# got to add up all of physical volumes to get total size
	if request.physicalVolumes is None:
	    return 0
	totalspace = 0
	for physvolid in request.physicalVolumes:
	    pvreq = requests.getRequestByID(physvolid)
	    part = partedUtils.get_partition_by_name(diskset.disks,
                                                     pvreq.device)
	    totalspace = totalspace + part.geom.length * part.geom.disk.dev.sector_size

	return totalspace
    

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
        part = partedUtils.get_partition_by_name(diskset.disks, device)
        partsize =  part.geom.length * part.geom.disk.dev.sector_size

        if raid.isRaid0(raidlevel):
            sum = sum + partsize
        else:
            if not smallest:
                smallest = partsize
            elif partsize < smallest:
                smallest = partsize

    if raid.isRaid0(raidlevel):
        return sum
    elif raid.isRaid1(raidlevel):
        return smallest
    elif raid.isRaid5(raidlevel):
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
	    elif string.find(mntpt, ' ') > -1:
		passed = 0
                
        if not passed:
            return _("The mount point is invalid.  Mount points must start "
                     "with '/' and cannot end with '/', and must contain "
                     "printable characters and no spaces.")
        else:
            return None
    else:
        if (fstype and fstype.isMountable() and
            (reqtype == REQUEST_NEW or reqtype == REQUEST_RAID or reqtype ==
	     REQUEST_VG or reqtype == REQUEST_LV)):
            return _("Please specify a mount point for this partition.")
        else:
            # its an existing partition so don't force a mount point
            return None

# XXX ermm, this function is silly... just check the name not using the req
def isVolumeGroupNameInUse(reqpartitions, req):
    volname = req.volumeGroupName
    if not volname:
        return None

    lvmrequests = reqpartitions.getLVMRequests()
    if not lvmrequests:
	return None

    if volname in lvmrequests.keys():
	return 1

    return 0
	
def isLogicalVolumeNameInUse(reqpartitions, req):
    logvolname = req.logicalVolumeName
    if not logvolname:
        return None

    lvmrequests = reqpartitions.getLVMRequests()
    if not lvmrequests:
	return None

    for vgname in lvmrequests.keys():
	vgrequest = reqpartitions.getRequestByDeviceName(vgname)
	if not lvmrequests[vgname]:
	    continue
	for lvrequest in lvmrequests[vgname]:
	    lvname = lvrequest.logicalVolumeName
	    if not lvname:
		continue
	    
	    if lvname == logvolname:
		return 1

    return 0

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
    if newrequest.size and newrequest.size > newrequest.fstype.getMaxSizeMB():
        return (_("The size of the %s partition (size = %s MB) "
                  "exceeds the maximum size of %s MB.")
                % (newrequest.fstype.getName(), newrequest.size,
                   newrequest.fstype.getMaxSizeMB()))

    if (newrequest.size and newrequest.maxSizeMB
        and (newrequest.size > newrequest.maxSizeMB)):
        return (_("The size of the requested partition (size = %s MB) "
                 "exceeds the maximum size of %s MB.")
                % (newrequest.size, newrequest.maxSizeMB))

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
        # XXX 390 can't have boot on raid
        if ((newraid.mountpoint == "/boot" or newraid.mountpoint == "/")
            and not raid.isRaid1(newraid.raidlevel)):
            return _("Bootable partitions can only be on RAID1 devices.")

    minmembers = raid.get_raid_min_members(newraid.raidlevel)
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
    if req.type == REQUEST_VG:
	if req.size != None:
	    thissize = req.size
	else:
	    thissize = 0
    if req.type == REQUEST_RAID:
        # XXX duplicate the hack below.  
        if req.size != None:
            thissize = req.size
        else:
            thissize = 0
    else:
        part = partedUtils.get_partition_by_name(diskset.disks, req.device)
        if not part:
            # XXX hack for kickstart which ends up calling this
            # before allocating the partitions
            if req.size:
                thissize = req.size
            else:
                thissize = 0
        else:
            thissize = partedUtils.getPartSizeMB(part)
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
    # XXX 390 can't have boot on RAID
    if (bootreq and (bootreq.type == REQUEST_RAID) and
        (not raid.isRaid1(bootreq.raidlevel))):
        errors.append(_("Bootable partitions can only be on RAID1 devices."))

    # can't have bootable partition on LV
    if (bootreq and (bootreq.type == REQUEST_LV)):
        errors.append(_("Bootable partitions can not be on a logical volume."))
        
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
    for partition in partedUtils.get_logical_partitions(part.geom.disk):
        request = requests.getRequestByDeviceName(partedUtils.get_partition_name(partition))
        requests.removeRequest(request)
        if request.type == REQUEST_PREEXIST:
            drive = partedUtils.get_partition_drive(partition)
            delete = partRequests.DeleteSpec(drive, partition.geom.start,
                                             partition.geom.end)
            requests.addDelete(delete)



def partitionObjectsInitialize(diskset, partitions, dir, intf):
    if iutil.getArch() == "s390":
        partitions.useAutopartitioning = 0
        partitions.useFdisk = 1
            
    if dir == DISPATCH_BACK:
        diskset.closeDevices()
        return

    # read in drive info
    diskset.refreshDevices(intf, partitions.reinitializeDisks,
                           partitions.zeroMbr)

    diskset.checkNoDisks(intf)

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
    if iutil.getArch() == "s390":
        dispatch.skipStep("fdasd", skip = not partitions.useFdisk)
    else:
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
            
        newrequest = partRequests.PartitionSpec(ptype,
                                                mountpoint = mntpt,
                                                size = minsize,
                                                maxSizeMB = maxsize,
                                                grow = grow,
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

        device = partedUtils.get_partition_name(part)
        request = requestlist.getRequestByDeviceName(device)

        if request:
            if request.type == REQUEST_PROTECTED:
                return _("the partition in use by the installer.")

            if requestlist.isRaidMember(request):
                return _("a partition which is a member of a RAID array.")
        
        part = disk.next_partition(part)
    return None
        
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
        if entry:
            fsset.add (entry)
        else:
            raise RuntimeError, ("Managed to not get an entry back from "
                                 "request.toEntry")
        
    if iutil.memInstalled() > isys.EARLY_SWAP_RAM:
        return
    # XXX this attribute is probably going away
    if not partitions.isKickstart:
        rc = intf.messageWindow(_("Low Memory"),
                            _("As you don't have much memory in this "
                              "machine, we need to turn on swap space "
                              "immediately. To do this we'll have to "
                              "write your new partition table to the disk "
                              "immediately. Is that okay?"), "okcancel")
    else:
        rc = 0
        
    if rc:
        fsset.setActive(diskSet)
        diskSet.savePartitions ()
        fsset.formatSwap(instPath)
        fsset.turnOnSwap(instPath)

    return



