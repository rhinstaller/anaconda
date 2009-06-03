#
# partRequests.py: partition request objects and management thereof
#
# Matt Wilson <msw@redhat.com>
# Jeremy Katz <katzj@redhat.com>
# Mike Fulbright <msf@redhat.com>
# Harald Hoyer <harald@redhat.de>
#
# Copyright 2002-2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
"""Partition request objects and management thereof."""

import parted
import iutil
import string
import os, sys, math

from constants import *
from rhpl.translate import _

import fsset
import raid
import lvm
import partedUtils
import partIntfHelpers
import rhpl

import logging
log = logging.getLogger("anaconda")

class DeleteSpec:
    """Defines a preexisting partition which is intended to be removed."""
    
    def __init__(self, drive, start, end, clobber=False):
        """Initializes a DeleteSpec.

        drive is the text form of the drive
        start is the start sector of the deleted partition
        end is the end sector of the deleted partition
        clobber - remove metadata from partition
        """
        
        self.drive = drive
        self.start = start
        self.end = end
        self.clobber = clobber

    def __str__(self):
        return "drive: %s  start: %s  end: %s" %(self.drive, self.start,
                                                 self.end)

class DeleteLogicalVolumeSpec:
    """Defines a preexisting logical volume which is intended to be removed."""

    def __init__(self, name, vg):
        """Initializes a DeleteLogicalVolumeSpec.

        name is the name of the lv
        vg is the name of the volume group
        """

        self.name = name
        self.vg = vg
        self.deleted = 0

    def __str__(self):
        return "lvname: %s  vgname: %s" %(self.name, self.vg)

    def beenDeleted(self):
        return self.deleted

    def setDeleted(self, val):
        self.deleted = val

class DeleteVolumeGroupSpec:
    """Defines a preexisting volume group which is intended to be removed."""

    def __init__(self, name):
        """Initializes a DeleteVolumeGroupSpec

        name is the name of the volume group
        """

        self.name = name
        self.deleted = 0

    def __str__(self):
        return "vgname: %s" %(self.name,)

    def beenDeleted(self):
        return self.deleted

    def setDeleted(self, val):
        self.deleted = val

class DeleteRAIDSpec:
    """Defines a preexisting RAID device which is intended to be removed."""

    def __init__(self, minor):
        """Initializes a DeleteRAIDSpec.

        minor is the minor of the RAID device being removed
        """

        self.minor = minor

    def __str__(self):
        return "minor: %s" %(self.minor,)

class RequestSpec:
    """Generic Request specification."""
    def __init__(self, fstype, size = None, mountpoint = None, format = None,
                 badblocks = None, preexist = 0, fslabel = None,
                 migrate = None, origfstype = None, bytesPerInode = 4096):
        """Create a generic RequestSpec.

        This should probably never be externally used.
        """

        self.fstype = fstype
        self.mountpoint = mountpoint
        self.size = size
        self.format = format
        self.badblocks = badblocks

        self.migrate = migrate
        self.origfstype = origfstype
        self.fslabel = fslabel
        self.fsopts = None

        if bytesPerInode == None:
            self.bytesPerInode = 4096
        else:
            self.bytesPerInode = bytesPerInode

        self.device = None
        """what we currently think the device is"""

        self.uniqueID = None
        """uniqueID is an integer and *MUST* be unique."""

        self.ignoreBootConstraints = 0
        """Booting constraints should be ignored for this request."""

        self.preexist = preexist
        """Did this partition exist before we started playing with things?"""

        self.protected = 0
        """Is this partitiion 'protected', ie does it contain install media."""

        self.dev = None
        """A Device() as defined in fsset.py to correspond to this request."""

        self.encryption = None
        """ An optional LUKSDevice describing block device encryption """

    def __str__(self):
        if self.fstype:
            fsname = self.fstype.getName()
        else:
            fsname = "None"

        str = ("Generic Request -- mountpoint: %(mount)s  uniqueID: %(id)s\n"
               "  type: %(fstype)s  format: %(format)s  badblocks: %(bb)s\n"
               "  device: %(dev)s  migrate: %(migrate)s  fslabel: %(fslabel)s\n"
               "  bytesPerInode:  %(bytesPerInode)s  options: '%(fsopts)s'" % 
               {"mount": self.mountpoint, "id": self.uniqueID,
                "fstype": fsname, "format": self.format, "bb": self.badblocks,
                "dev": self.device, "migrate": self.migrate,
                "fslabel": self.fslabel, "bytesPerInode": self.bytesPerInode,
                "fsopts": self.fsopts})
        return str

    def getActualSize(self, partitions, diskset):
        """Return the actual size allocated for the request in megabytes."""

        sys.stderr.write("WARNING: Abstract RequestSpec.getActualSize() called\n")
        import traceback
        traceback.print_stack()

    def getDevice(self, partitions):
        """Return a device to solidify."""

        sys.stderr.write("WARNING: Abstract RequestSpec.getDevice() called\n")
        import traceback
        traceback.print_stack()

    def isEncrypted(self, partitions, parentOnly = False):
        if self.encryption:
            return True
        return False

    def toEntry(self, partitions):
        """Turn a request into a fsset entry and return the entry."""
        device = self.getDevice(partitions)

        # pin down our partitions so that we can reread the table
        device.solidify()

        if self.fstype.getName() == "swap":
            mountpoint = "swap"
        else:
            mountpoint = self.mountpoint

        entry = fsset.FileSystemSetEntry(device, mountpoint, self.fstype,
                                         origfsystem=self.origfstype,
                                         bytesPerInode=self.bytesPerInode,
                                         options=self.fsopts)
        if self.format:
            entry.setFormat(self.format)

        if self.migrate:
            entry.setMigrate(self.migrate)
        elif rhpl.getArch() == "ia64" \
                and entry.getMountPoint() == "/boot/efi" \
                and isinstance(self.origfstype, fsset.FATFileSystem) \
                and not entry.getFormat():
            entry.setMigrate(1)

        if self.badblocks:
            entry.setBadblocks(self.badblocks)

        if self.fslabel:
            entry.setLabel(self.fslabel)

        return entry

    def setProtected(self, val):
        """Set the protected value for this partition."""
        self.protected = val

    def getProtected(self):
        """Return the protected value for this partition."""
        return self.protected

    def getPreExisting(self):
        """Return whether the partition existed before we started playing."""
        return self.preexist

    def doMountPointLinuxFSChecks(self):
        """Return an error string if the mountpoint is not valid for Linux FS."""
        mustbeonroot = ('/bin','/dev','/sbin','/etc','/lib','/root',
                        '/mnt', 'lost+found', '/proc')
        mustbeonlinuxfs = ('/', '/boot', '/var', '/tmp', '/usr', '/home',
                           '/usr/share', '/usr/lib' )

	# these are symlinks so you cant make them mount points
	otherexcept = ('/var/mail', '/usr/bin/X11', '/usr/lib/X11', '/usr/tmp')

        if not self.mountpoint:
            return None

        if self.fstype is None:
            return None

        if self.fstype.isMountable():    
            if self.mountpoint in mustbeonroot:
                return _("This mount point is invalid.  The %s directory must "
                         "be on the / file system.") % (self.mountpoint,)
	    elif self.mountpoint in otherexcept:
                return _("The mount point %s cannot be used.  It must "
			 "be a symbolic link for proper system "
			 "operation.  Please select a different "
			 "mount point.") % (self.mountpoint,)
		
        if not self.fstype.isLinuxNativeFS():
            if self.mountpoint in mustbeonlinuxfs:
                return _("This mount point must be on a linux file system.")

        return None

    # requestSkipList is a list of uids for requests to ignore when
    # looking for a conflict on the mount point name.  Used in lvm
    # editting code in disk druid, for example.
    def isMountPointInUse(self, partitions, requestSkipList=None):
        """Return whether my mountpoint is in use by another request."""
        mntpt = self.mountpoint
        if not mntpt:
            return None

        if partitions and partitions.requests:
            for request in partitions.requests:
		if requestSkipList is not None and request.uniqueID in requestSkipList:
		    continue

                if request.mountpoint == mntpt:
                    if (not self.uniqueID or
                        request.uniqueID != self.uniqueID):
                        return _("The mount point \"%s\" is already in use, "
                                 "please choose a different mount point."
                                 %(mntpt))
        return None

    def doSizeSanityCheck(self):
        """Sanity check that the size of the request is sane."""
        if not self.fstype:
            return None

        if not self.format:
            return None

        if self.size and self.size > self.fstype.getMaxSizeMB():
            return (_("The size of the %s partition (%10.2f MB) "
                      "exceeds the maximum size of %10.2f MB.")
                    % (self.fstype.getName(), self.size,
                       self.fstype.getMaxSizeMB()))
        
        return None

    # set skipMntPtExistCheck to non-zero if you want to handle this
    # check yourself. Used in lvm volume group editting code, for example.
    def sanityCheckRequest(self, partitions, skipMntPtExistCheck=0):
        """Run the basic sanity checks on the request."""
        # see if mount point is valid if its a new partition request
        mntpt = self.mountpoint
        fstype = self.fstype
        preexist = self.preexist
        format = self.format

        rc = self.doSizeSanityCheck()
        if rc:
            return rc

        rc = partIntfHelpers.sanityCheckMountPoint(mntpt, fstype, preexist, format)
        if rc:
            return rc

	if not skipMntPtExistCheck:
	    rc = self.isMountPointInUse(partitions)
	    if rc:
		return rc

        rc = self.doMountPointLinuxFSChecks()
        if rc:
            return rc

        return None
        

    def formatByDefault(self):
        """Return whether or not the request should be formatted by default."""
        def inExceptionList(mntpt):
            exceptlist = ['/home', '/usr/local', '/opt', '/var/www']
            for q in exceptlist:
                if os.path.commonprefix([mntpt, q]) == q:
                    return 1
            return 0

        # check first to see if its a Linux filesystem or not
        formatlist = ['/boot', '/var', '/tmp', '/usr']

        if not self.fstype:
            return 0

        if not self.fstype.isLinuxNativeFS():
            return 0

        if self.fstype.isMountable():
            mntpt = self.mountpoint
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
            if self.fstype.getName() == "swap":
                return 1

        # be safe for anything else and default to off
        return 0
        

# XXX preexistings store start/end as sectors, new store as cylinders. ICK
class PartitionSpec(RequestSpec):
    """Object to define a requested partition."""

    # XXX eep, still a few too many options but a lot better
    def __init__(self, fstype, size = None, mountpoint = None,
                 preexist = 0, migrate = None, grow = 0, maxSizeMB = None,
                 start = None, end = None, drive = None, primary = None,
                 format = None, multidrive = None, bytesPerInode = 4096,
                 fslabel = None):
        """Create a new PartitionSpec object.

        fstype is the fsset filesystem type.
        size is the requested size (in megabytes).
        mountpoint is the mountpoint.
        grow is whether or not the partition is growable.
        maxSizeMB is the maximum size of the partition in megabytes.
        start is the starting cylinder/sector (new/preexist).
        end is the ending cylinder/sector (new/preexist).
        drive is the drive the partition goes on.
        primary is whether or not the partition should be forced as primary.
        format is whether or not the partition should be formatted.
        preexist is whether this partition is preexisting.
        migrate is whether or not the partition should be migrated.
        multidrive specifies if this is a request that should be replicated
            across _all_ of the drives in drive
        bytesPerInode is the size of the inodes on the filesystem.
        fslabel is the label to give to the filesystem.
        """

        # if it's preexisting, the original fstype should be set
        if preexist == 1:
            origfs = fstype
        else:
            origfs = None
        
        RequestSpec.__init__(self, fstype = fstype, size = size,
                             mountpoint = mountpoint, format = format,
                             preexist = preexist, migrate = None,
                             origfstype = origfs, bytesPerInode = bytesPerInode,
                             fslabel = fslabel)
        self.type = REQUEST_NEW

        self.grow = grow
        self.maxSizeMB = maxSizeMB
        self.requestSize = size
        self.start = start
        self.end = end

        self.drive = drive
        self.primary = primary
        self.multidrive = multidrive

        # should be able to map this from the device =\
        self.currentDrive = None
        """Drive that this request will currently end up on."""        


    def __str__(self):
        if self.fstype:
            fsname = self.fstype.getName()
        else:
            fsname = "None"

        if self.origfstype:
            oldfs = self.origfstype.getName()
        else:
            oldfs = "None"

        if self.preexist == 0:
            pre = "New"
        else:
            pre = "Existing"

        if self.encryption is None:
            crypto = "None"
        else:
            crypto = self.encryption.getScheme()

        str = ("%(n)s Part Request -- mountpoint: %(mount)s uniqueID: %(id)s\n"
               "  type: %(fstype)s  format: %(format)s  badblocks: %(bb)s\n"
               "  device: %(dev)s drive: %(drive)s  primary: %(primary)s\n"
               "  size: %(size)s  grow: %(grow)s  maxsize: %(max)s\n"
               "  start: %(start)s  end: %(end)s  migrate: %(migrate)s  "
               "  fslabel: %(fslabel)s  origfstype: %(origfs)s\n"
               "  bytesPerInode: %(bytesPerInode)s  options: '%(fsopts)s'"
               "  encryption: %(encryption)s" %
               {"n": pre, "mount": self.mountpoint, "id": self.uniqueID,
                "fstype": fsname, "format": self.format, "dev": self.device,
                "drive": self.drive, "primary": self.primary,
                "size": self.size, "grow": self.grow, "max": self.maxSizeMB,
                "start": self.start, "end": self.end, "bb": self.badblocks,
                "migrate": self.migrate, "fslabel": self.fslabel,
                "origfs": oldfs, "bytesPerInode": self.bytesPerInode,
                "fsopts": self.fsopts, "encryption": crypto})
        return str


    def getDevice(self, partitions):
        """Return a device to solidify."""
        self.dev = fsset.PartitionDevice(self.device,
                                         encryption=self.encryption)
        return self.dev

    def getActualSize(self, partitions, diskset):
        """Return the actual size allocated for the request in megabytes."""
        part = partedUtils.get_partition_by_name(diskset.disks, self.device)
        if not part:
            # XXX kickstart might still call this before allocating the partitions
            raise RuntimeError, "Checking the size of a partition which hasn't been allocated yet"
        return partedUtils.getPartSizeMB(part)

    def doSizeSanityCheck(self):
        """Sanity check that the size of the partition is sane."""
        if not self.fstype:
            return None
        if not self.format:
            return None
        ret = RequestSpec.doSizeSanityCheck(self)
        if ret is not None:
            return ret

        if (self.size and self.maxSizeMB
            and (self.size > self.maxSizeMB)):
            return (_("The size of the requested partition (size = %s MB) "
                     "exceeds the maximum size of %s MB.")
                    % (self.size, self.maxSizeMB))

        if self.size and self.size < 0:
            return _("The size of the requested partition is "
                     "negative! (size = %s MB)") % (self.size)

        if self.start and self.start < 1:
            return _("Partitions can't start below the first cylinder.")

        if self.end and self.end < 1:
            return _("Partitions can't end on a negative cylinder.")

        return None

class NewPartitionSpec(PartitionSpec):
    """Object to define a NEW requested partition."""

    # XXX eep, still a few too many options but a lot better
    def __init__(self, fstype, size = None, mountpoint = None,
                 grow = 0, maxSizeMB = None,
                 start = None, end = None,
                 drive = None, primary = None, format = None):
        """Create a new NewPartitionSpec object.

        fstype is the fsset filesystem type.
        size is the requested size (in megabytes).
        mountpoint is the mountpoint.
        grow is whether or not the partition is growable.
        maxSizeMB is the maximum size of the partition in megabytes.
        start is the starting cylinder.
        end is the ending cylinder.
        drive is the drive the partition goes on.
        primary is whether or not the partition should be forced as primary.
        format is whether or not the partition should be formatted.
        """

        PartitionSpec.__init__(self, fstype = fstype, size = size,
                               mountpoint = mountpoint, grow = grow,
                               maxSizeMB = maxSizeMB, start = start,
                               end = end, drive = drive, primary = primary,
                               format = format, preexist = 0)
        self.type = REQUEST_NEW

class PreexistingPartitionSpec(PartitionSpec):
    """Request to represent partitions which already existed."""
    
    def __init__(self, fstype, size = None, start = None, end = None,
                 drive = None, format = None, migrate = None,
                 mountpoint = None):
        """Create a new PreexistingPartitionSpec object.

        fstype is the fsset filesystem type.
        size is the size (in megabytes).
        start is the starting sector.
        end is the ending sector.
        drive is the drive which the partition is on.
        format is whether or not the partition should be formatted.
        migrate is whether or not the partition fs should be migrated.
        mountpoint is the mountpoint.
        """

        PartitionSpec.__init__(self, fstype = fstype, size = size,
                               start = start, end = end, drive = drive,
                               format = format, migrate = migrate,
                               mountpoint = mountpoint, preexist = 1)
        self.type = REQUEST_PREEXIST

class RaidRequestSpec(RequestSpec):
    """Request to represent RAID devices."""
    
    def __init__(self, fstype, format = None, mountpoint = None,
                 raidlevel = None, raidmembers = None,
                 raidspares = None, raidminor = None, fslabel = None,
                 preexist = 0, chunksize = None, bytesPerInode=4096):
        """Create a new RaidRequestSpec object.

        fstype is the fsset filesystem type.
        format is whether or not the partition should be formatted.
        mountpoint is the mountpoint.
        raidlevel is the raidlevel (as 'RAID0', 'RAID1', 'RAID5').
        chunksize is the chunksize which should be used.
        raidmembers is list of ids corresponding to the members of the RAID.
        raidspares is the number of spares to setup.
        raidminor is the minor of the device which should be used.
        bytesPerInode is the size of the inodes on the filesystem.
        fslabel is the label of the filesystem.
        """

        # if it's preexisting, the original fstype should be set
        if preexist == 1:
            origfs = fstype
        else:
            origfs = None

        RequestSpec.__init__(self, fstype = fstype, format = format,
                             mountpoint = mountpoint, preexist = preexist,
                             origfstype = origfs, bytesPerInode=bytesPerInode,
                             fslabel=fslabel)
        self.type = REQUEST_RAID
        

        self.raidlevel = raidlevel
        self.raidmembers = raidmembers
        self.raidspares = raidspares
        self.raidminor = raidminor
        self.chunksize = chunksize

    def __str__(self):
        if self.fstype:
            fsname = self.fstype.getName()
        else:
            fsname = "None"
        raidmem = []
        if self.raidmembers:
            for i in self.raidmembers:
                raidmem.append(i)

        if self.encryption is None:
            crypto = "None"
        else:
            crypto = self.encryption.getScheme()
                
        str = ("RAID Request -- mountpoint: %(mount)s  uniqueID: %(id)s\n"
               "  type: %(fstype)s  format: %(format)s  badblocks: %(bb)s\n"
               "  raidlevel: %(level)s  raidspares: %(spares)s\n"
               "  raidmembers: %(members)s  bytesPerInode: %(bytesPerInode)s"
               "  encryption: %(encryption)s" %
               {"mount": self.mountpoint, "id": self.uniqueID,
                "fstype": fsname, "format": self.format, "bb": self.badblocks,
                "level": self.raidlevel, "spares": self.raidspares,
                "members": self.raidmembers, "encryption": crypto,
                "bytesPerInode": self.bytesPerInode})
        return str
    
    def getDevice(self, partitions):
        """Return a device which can be solidified."""
        # Alway return a new device for minor changing
        raidmems = []
        for member in self.raidmembers:
            request = partitions.getRequestByID(member)
            raidmems.append(request.getDevice(partitions))
        self.dev = fsset.RAIDDevice(int(self.raidlevel[4:]),
                                    raidmems, minor = self.raidminor,
                                    spares = self.raidspares,
                                    existing = self.preexist,
                                    chunksize = self.chunksize,
                                    encryption = self.encryption)
        return self.dev

    def isEncrypted(self, partitions, parentOnly = False):
        if RequestSpec.isEncrypted(self, partitions) is True:
            return True
        if parentOnly:
            return False
        for member in self.raidmembers:
            if partitions.getRequestByID(member).isEncrypted(partitions):
                return True
        return False

    def getActualSize(self, partitions, diskset):
        """Return the actual size allocated for the request in megabytes."""

        # this seems like a check which should never fail...
        if not self.raidmembers or not self.raidlevel:
            return 0
        nummembers = len(self.raidmembers) - self.raidspares
        smallest = None
        sum = 0
        for member in self.raidmembers:
            req = partitions.getRequestByID(member)
            partsize = req.getActualSize(partitions, diskset)

            if raid.isRaid0(self.raidlevel):
                sum = sum + partsize
            else:
                if not smallest:
                    smallest = partsize
                elif partsize < smallest:
                    smallest = partsize

        if raid.isRaid0(self.raidlevel):
            return sum
        elif raid.isRaid1(self.raidlevel):
            return smallest
        elif raid.isRaid5(self.raidlevel):
            return (nummembers-1) * smallest
        elif raid.isRaid6(self.raidlevel):
            return (nummembers-2) * smallest
        elif raid.isRaid10(self.raidlevel):
            return (nummembers/2) * smallest
        else:
            raise ValueError, "Invalid raidlevel in RaidRequest.getActualSize"
        

    # do RAID specific sanity checks; this is an internal function
    def sanityCheckRaid(self, partitions):
        if not self.raidmembers or not self.raidlevel:
            return _("No members in RAID request, or not RAID "
                     "level specified.")
        # XXX fix this code to look to see if there is a bootable partition
        bootreq = partitions.getBootableRequest()
        if not bootreq and self.mountpoint:
            # XXX 390 can't have boot on raid
            if (self.mountpoint in partitions.getBootableMountpoints()
                 and not raid.isRaid1(self.raidlevel)):
                return _("Bootable partitions can only be on RAID1 devices.")

        minmembers = raid.get_raid_min_members(self.raidlevel)
        if len(self.raidmembers) < minmembers:
            return _("A RAID device of type %s "
                     "requires at least %s members.") % (self.raidlevel,
                                                         minmembers)

        if len(self.raidmembers) > 27:
            return "RAID devices are limited to 27 members."

        if self.raidspares:
            if (len(self.raidmembers) - self.raidspares) < minmembers:
                return _("This RAID device can have a maximum of %s spares. "
                         "To have more spares you will need to add members to "
                         "the RAID device.") % (len(self.raidmembers)
                                                - minmembers )
        return None

    def sanityCheckRequest(self, partitions):
        """Run the basic sanity checks on the request."""
        rc = self.sanityCheckRaid(partitions)
        if rc:
            return rc
        return RequestSpec.sanityCheckRequest(self, partitions)

class VolumeGroupRequestSpec(RequestSpec):
    """Request to represent volume group devices."""
    
    def __init__(self, fstype =None, format = None,
                 vgname = None, physvols = None,
                 pesize = 32768, preexist = 0,
                 preexist_size = 0):
        """Create a new VolumeGroupRequestSpec object.

        fstype is the fsset filesystem type.
        format is whether or not the volume group should be created.
        vgname is the name of the volume group.
        physvols is a list of the ids for the physical volumes in the vg.
        pesize is the size of a physical extent in kilobytes.
        preexist is whether the volume group is preexisting.
        preexist_size is the size of a preexisting VG read from /proc
            (note that this is unclamped)
        """

        if not fstype:
            fstype = fsset.fileSystemTypeGet("volume group (LVM)")
        RequestSpec.__init__(self, fstype = fstype, format = format)
        self.type = REQUEST_VG

        self.volumeGroupName = vgname
        self.physicalVolumes = physvols
        self.pesize = pesize
        self.preexist = preexist

        # FIXME: this is a hack so that we can set the vg name automagically
        # with autopartitioning to not conflict with existing vgs
        self.autoname = 0

        if preexist and preexist_size:
            self.preexist_size = preexist_size
            log.debug("VolumeGroupRequestSpec('%s').preexist_size is %s" % (vgname, preexist_size))
        else:
            self.preexist_size = None

    def __str__(self):
        physvols = []
        if self.physicalVolumes:
            for i in self.physicalVolumes:
                physvols.append(i)
                
        str = ("VG Request -- name: %(vgname)s  uniqueID: %(id)s\n"
               "  format: %(format)s pesize: %(pesize)s  \n"
               "  physvols: %(physvol)s" %
               {"vgname": self.volumeGroupName, "id": self.uniqueID,
                "format": self.format, "physvol": physvols,
                "pesize": self.pesize})
        return str
    
    def getDevice(self, partitions):
        """Return a device which can be solidified."""
        if self.dev:
            # FIXME: this warning can probably be removed post-beta            
            log.warning("getting self.dev more than once for %s" %(self,))
            return self.dev
        
        pvs = []
        for pv in self.physicalVolumes:
            r = partitions.getRequestByID(pv)
            # a size of zero implies we did autopartitioning of
            # pvs everywhere we could
            if (r.size > 0) or (r.device is not None):
                pvs.append(r.getDevice(partitions))
        self.dev = fsset.VolumeGroupDevice(self.volumeGroupName, pvs,
                                           self.pesize,
                                           existing = self.preexist)
        return self.dev

    def isEncrypted(self, partitions, parentOnly = False):
        if RequestSpec.isEncrypted(self, partitions) is True:
            return True
        if parentOnly:
            return False
        for pvid in self.physicalVolumes:
            pv = partitions.getRequestByID(pvid)
            if pv.isEncrypted(partitions):
                return True
        return False

    def getActualSize(self, partitions, diskset):
        """Return the actual size allocated for the request in megabytes."""

        # if we have a preexisting size, use it
        if self.preexist and self.preexist_size:
            totalspace = lvm.clampPVSize(self.preexist_size, self.pesize)
            log.debug("using preexisting size of %s for volume group %s" % (self.preexist_size, self.volumeGroupName))
        else:
            totalspace = 0
            log.debug("no preexisting size for volume group %s" % (self.volumeGroupName))
            for pvid in self.physicalVolumes:
                pvreq = partitions.getRequestByID(pvid)
                size = pvreq.getActualSize(partitions, diskset)
                clamped = lvm.clampPVSize(size, self.pesize)
                if long(size) == clamped:
                    # If clamping reserves only less than 1MB for lvm metadata,
                    # reserve one more PE.
                    clamped = clamped - (self.pesize / 1024)

                log.debug("  got pv.size of %s, clamped to %s" % (size,clamped))
                totalspace = totalspace + clamped
            log.debug("  total space: %s" % (totalspace,))

        return totalspace

class PartialVolumeGroupSpec:
    """Request to represent partial volume group devices."""
    # note, these are just used as placeholders so we don't collide on names
    
    def __init__(self, vgname = None):
        """Create a new PartialVolumeGroupSpec object.

        vgname is the name of the volume group.
        """

        self.volumeGroupName = vgname

    def __str__(self):
        str = ("Partial VG Request -- name: %(vgname)s" %
               {"vgname": self.volumeGroupName})
        return str
    
class LogicalVolumeRequestSpec(RequestSpec):
    """Request to represent logical volume devices."""
    
    def __init__(self, fstype, format = None, mountpoint = None,
                 size = None, volgroup = None, lvname = None,
                 preexist = 0, percent = None, grow=0, maxSizeMB=0,
		 bytesPerInode = 4096, fslabel = None):
        """Create a new VolumeGroupRequestSpec object.

        fstype is the fsset filesystem type.
        format is whether or not the volume group should be created.
        mountpoint is the mountpoint for the request.
        size is the size of the request in MB.
        volgroup is the request ID of the volume group.
        lvname is the name of the logical volume.
        preexist is whether the logical volume previously existed or not.
        percent is the percentage of the volume group's space this should use.
	grow is whether or not to use free space remaining.
	maxSizeMB is max size to grow to.
	bytesPerInode is the size of the inodes on the partition.
        fslabel is the label of the filesystem on the logical volume.
        """

        # if it's preexisting, the original fstype should be set
        if preexist == 1:
            origfs = fstype
        else:
            origfs = None

        if bytesPerInode == None:
            self.bytesPerInode = 4096
        else:
            self.bytesPerInode = bytesPerInode

	RequestSpec.__init__(self, fstype = fstype, format = format,
			     mountpoint = mountpoint, size = size,
			     preexist = preexist, origfstype = origfs,
			     bytesPerInode = bytesPerInode, fslabel = fslabel)
	    
        self.type = REQUEST_LV

        self.logicalVolumeName = lvname
        self.volumeGroup = volgroup
        self.percent = percent
        self.grow = grow
        self.maxSizeMB = maxSizeMB
        self.startSize = size
	
        if not percent and not size and not preexist:
            raise RuntimeError, "Error with Volume Group:Logical Volume %s:%s - Logical Volume must specify either percentage of vgsize or size" % (volgroup, lvname)

	if percent and grow:
            raise RuntimeError, "Error with Volume Group:Logical Volume %s:%s - Logical Volume cannot grow if percentage given" % (volgroup, lvname)
	    

    def __str__(self):
        if self.fstype:
            fsname = self.fstype.getName()
        else:
            fsname = "None"

        if self.size is not None:
            size = self.size
        else:
            size = "%s percent" %(self.percent,)
        
        if self.encryption is None:
            crypto = "None"
        else:
            crypto = self.encryption.getScheme()

        str = ("LV Request -- mountpoint: %(mount)s  uniqueID: %(id)s\n"
               "  type: %(fstype)s  format: %(format)s  badblocks: %(bb)s\n"
               "  size: %(size)s  lvname: %(lvname)s  volgroup: %(vgid)s\n"
               "  bytesPerInode: %(bytesPerInode)s  options: '%(fsopts)s'"
               "  encryption: %(encryption)s" %
               {"mount": self.mountpoint, "id": self.uniqueID,
                "fstype": fsname, "format": self.format, "bb": self.badblocks,
                "lvname": self.logicalVolumeName, "vgid": self.volumeGroup,
		"size": size, "bytesPerInode": self.bytesPerInode,
                "fsopts": self.fsopts, "encryption": crypto})
        return str
    
    def getDevice(self, partitions):
        """Return a device which can be solidified."""
        vg = partitions.getRequestByID(self.volumeGroup)
        vgname = vg.volumeGroupName
        self.dev = fsset.LogicalVolumeDevice(vgname, self.size,
                                             self.logicalVolumeName,
                                             vg = vg,
                                             existing = self.preexist,
                                             encryption = self.encryption)
        return self.dev

    def isEncrypted(self, partitions, parentOnly = False):
        if RequestSpec.isEncrypted(self, partitions) is True:
            return True
        if parentOnly:
            return False
        vg = partitions.getRequestByID(self.volumeGroup)
        if vg.isEncrypted(partitions):
            return True
        return False

    def getActualSize(self, partitions, diskset, pesize=None):
        """Return the actual size allocated for the request in megabytes."""
        retval = 0
        vgreq = partitions.getRequestByID(self.volumeGroup)

        if not pesize:
            pesize = vgreq.pesize

        if self.percent:
	    vgsize = vgreq.getActualSize(partitions, diskset)
	    lvsize = int(self.percent * 0.01 * vgsize)
	    #lvsize = lvm.clampLVSizeRequest(lvsize, vgreq.pesize)
            retval = lvsize
        else:
            retval = self.size

        # lvm tools round up lvolums using the volume group pv size.
        # If the logical volume is preexisting do NOT touch it.
        if not self.preexist:
            retval = lvm.clampLVSizeRequest(retval, pesize)

        return retval

    def getStartSize(self):
        """Return the starting size allocated for the request in megabytes."""
	return self.startSize

    def setSize(self, size):
	"""Set the size (in MB) of request (does not clamp to PE however)

	size - size in MB
	"""
	if self.percent:
	    self.percent = None

	self.size = size

    def sanityCheckRequest(self, partitions, skipMntPtExistCheck=0, pesize=32768):
        """Run the basic sanity checks on the request."""
        if not self.grow and not self.percent and self.size*1024 < pesize:
            return _("Logical volume size must be larger than the volume "
                     "group's physical extent size.")

        return RequestSpec.sanityCheckRequest(self, partitions, skipMntPtExistCheck)
