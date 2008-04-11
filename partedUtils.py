#
# partedUtils.py: helper functions for use with parted objects
#
# Matt Wilson <msw@redhat.com>
# Jeremy Katz <katzj@redhat.com>
# Mike Fulbright <msf@redhat.com>
# Karsten Hopp <karsten@redhat.com>
#
# Copyright 2002-2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
"""Helper functions for use when dealing with parted objects."""

import parted
import math
import os, sys, string, struct

from product import *
import fsset
import iutil, isys
import raid
import lvm
from flags import flags
from partErrors import *

from rhpl.log import log
from rhpl.translate import _

fsTypes = {}

fs_type = parted.file_system_type_get_next ()
while fs_type:
    fsTypes[fs_type.name] = fs_type
    fs_type = parted.file_system_type_get_next (fs_type)



def get_flags (part):
    """Retrieve a list of strings representing the flags on the partition."""
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
    """Return the closest cylinder (round down) to sector on device."""
    return int(math.floor((float(sector)
                           / (device.heads * device.sectors)) + 1))

def end_sector_to_cyl(device, sector):
    """Return the closest cylinder (round up) to sector on device."""    
    return int(math.ceil(float((sector + 1))
                         / (device.heads * device.sectors)))

def start_cyl_to_sector(device, cyl):
    "Return the sector corresponding to cylinder as a starting cylinder."
    return long((cyl - 1) * (device.heads * device.sectors))

def end_cyl_to_sector(device, cyl):
    "Return the sector corresponding to cylinder as a ending cylinder."    
    return long(((cyl) * (device.heads * device.sectors)) - 1)

def getPartSize(partition):
    """Return the size of partition in sectors."""
    return partition.geom.length

def getPartSizeMB(partition):
    """Return the size of partition in megabytes."""
    return (partition.geom.length * partition.geom.dev.sector_size
            / 1024.0 / 1024.0)

def getDeviceSizeMB(dev):
    """Return the size of dev in megabytes."""
    return (float(dev.heads * dev.cylinders * dev.sectors) / (1024 * 1024)
            * dev.sector_size)

def get_partition_by_name(disks, partname):
    """Return the parted part object associated with partname.  

    Arguments:
    disks -- Dictionary of diskname->PedDisk objects
    partname -- Name of partition to find

    Return:
    PedPartition object with name partname.  None if no such partition.
    """
    for diskname in disks.keys():
        disk = disks[diskname]
        part = disk.next_partition()
        while part:
            if get_partition_name(part) == partname:
                return part

            part = disk.next_partition(part)

    return None

def get_partition_name(partition):
    """Return the device name for the PedPartition partition."""
    if (partition.geom.dev.type == parted.DEVICE_DAC960
        or partition.geom.dev.type == parted.DEVICE_CPQARRAY):
        return "%sp%d" % (partition.geom.dev.path[5:],
                          partition.num)
    if (parted.__dict__.has_key("DEVICE_SX8") and
        partition.geom.dev.type == parted.DEVICE_SX8):
        return "%sp%d" % (partition.geom.dev.path[5:],
                          partition.num)
                          
    return "%s%d" % (partition.geom.dev.path[5:],
                     partition.num)


def get_partition_file_system_type(part):
    """Return the file system type of the PedPartition part.

    Arguments:
    part -- PedPartition object

    Return:
    Filesystem object (as defined in fsset.py)
    """
    if part.fs_type is None and part.native_type == 0x41:
        ptype = fsset.fileSystemTypeGet("PPC PReP Boot")
    elif part.fs_type == None:
        return None
    elif part.fs_type.name == "linux-swap":
        ptype = fsset.fileSystemTypeGet("swap")
    elif (part.fs_type.name == "FAT" or part.fs_type.name == "fat16"
          or part.fs_type.name == "fat32"):
        ptype = fsset.fileSystemTypeGet("vfat")
    else:
        try:
            ptype = fsset.fileSystemTypeGet(part.fs_type.name)
        except:
            ptype = fsset.fileSystemTypeGet("foreign")

    return ptype


def set_partition_file_system_type(part, fstype):
    """Set partition type of part to PedFileSystemType implied by fstype."""
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
    """Return the device name for disk that PedPartition partition is on."""
    return "%s" %(partition.geom.dev.path[5:])

def get_max_logical_partitions(disk):
    if not disk.type.check_feature(parted.DISK_TYPE_EXTENDED):
        return 0
    dev = disk.dev.path[5:]
    for key in max_logical_partition_count.keys():
        if dev.startswith(key):
            return max_logical_partition_count[key]
    # FIXME: if we don't know about it, should we pretend it can't have
    # logicals?  probably safer to just use something reasonable
    return 11

def map_foreign_to_fsname(type):
    """Return the partition type associated with the numeric type.""" 
    if type in allPartitionTypesDict.keys():
        return allPartitionTypesDict[type]
    else:
        return _("Foreign")

def filter_partitions(disk, func):
    rc = []
    part = disk.next_partition ()
    while part:
        if func(part):
            rc.append(part)
        part = disk.next_partition (part)

    return rc

def get_all_partitions(disk):
    """Return a list of all PedPartition objects on disk."""
    func = lambda part: part.is_active()
    return filter_partitions(disk, func)

def get_logical_partitions(disk):
    """Return a list of logical PedPartition objects on disk."""
    func = lambda part: (part.is_active()
                         and part.type & parted.PARTITION_LOGICAL)
    return filter_partitions(disk, func)

def get_primary_partitions(disk):
    """Return a list of primary PedPartition objects on disk."""
    func = lambda part: part.type == parted.PARTITION_PRIMARY
    return filter_partitions(disk, func)

def get_raid_partitions(disk):
    """Return a list of RAID-type PedPartition objects on disk."""
    func = lambda part: (part.is_active()
                         and part.get_flag(parted.PARTITION_RAID) == 1)
    return filter_partitions(disk, func)

def get_lvm_partitions(disk):
    """Return a list of physical volume-type PedPartition objects on disk."""
    func = lambda part: (part.is_active()
                         and part.get_flag(parted.PARTITION_LVM) == 1)
    return filter_partitions(disk, func)


def getDefaultDiskType():
    """Get the default partition table type for this architecture."""
    if iutil.getArch() == "i386":
        return parted.disk_type_get("msdos")
    elif iutil.getArch() == "ia64":
        return parted.disk_type_get("gpt")
    elif iutil.getArch() == "s390":
        # the "default" type is dasd, but we don't really do dasd
        # formatting with parted and use dasdfmt directly for them
        # so if we get here, it's an fcp disk and we should write
        # an msdos partition table (#144199)
        return parted.disk_type_get("msdos")
    elif iutil.getArch() == "alpha":
        return parted.disk_type_get("bsd")
    elif iutil.getArch() == "sparc":
        return parted.disk_type_get("sun")
    elif iutil.getArch() == "ppc":
        if iutil.getPPCMachine() == "PMac":
            return parted.disk_type_get("mac")
        else:
            return parted.disk_type_get("msdos")
    else:
        return parted.disk_type_get("msdos")

archLabels = {'i386': ['msdos'],
              's390': ['dasd', 'msdos'],
              'alpha': ['bsd', 'msdos'],
              'sparc': ['sun'],
              'ia64': ['msdos', 'gpt'],
              'ppc': ['msdos', 'mac'],
              'x86_64': ['msdos']}

# this is kind of crappy, but we don't really want to allow LDL formatted
# dasd to be used during the install
def checkDasdFmt(disk, intf):
    if iutil.getArch() != "s390":
        return 0

    if disk.type.name != "dasd":
        return 0

    # FIXME: there has to be a better way to check LDL vs CDL
    # how do I test ldl vs cdl?
    if disk.max_primary_partition_count > 1:
        return 0

    if intf:
        try:
            devs = isys.getDasdDevPort()
            dev = "/dev/%s (%s)" %(disk.dev.path[5:], devs[device])
        except Exception, e:
            log("exception getting dasd dev ports: %s" %(e,))
            dev = "/dev/%s" %(disk.dev.path[5:],)
        
        rc = intf.messageWindow(_("Warning"),
                       _("The device %s is LDL formatted instead of "
                         "CDL formatted.  LDL formatted DASDs are not "
                         "supported for usage during an install of %s.  "
                         "If you wish to use this disk for installation, "
                         "it must be re-initialized causing the loss of "
                         "ALL DATA on this drive.\n\n"
                         "Would you like to reformat this DASD using CDL "
                         "format?")
                        %(dev, productName), type = "yesno")
        if rc == 0:
            return 1
        else:
            return -1
    else:
        return 1
    

def checkDiskLabel(disk, intf):
    """Check that the disk label on disk is valid for this machine type."""
    arch = iutil.getArch()
    if arch in archLabels.keys():
        if disk.type.name in archLabels[arch]:
            # this is kind of a hack since we don't want LDL to be used
            return checkDasdFmt(disk, intf)
    else:
        if disk.type.name == "msdos":
            return 0

    if intf:
        rc = intf.messageWindow(_("Warning"),
                                _("/dev/%s currently has a %s partition "
                                  "layout.  To use this disk for "
                                  "the installation of %s, it must be "
                                  "re-initialized, causing the loss of "
                                  "ALL DATA on this drive.\n\n"
                                  "Would you like to format this "
                                  "drive?")
                                %(disk.dev.path[5:], disk.type.name,
                                  productName), type="custom",
                                custom_buttons = [ _("_Ignore drive"),
                                                   _("_Format drive") ],
                                custom_icon="question")

        if rc == 0:
            return 1
        else:
            return -1
    else:
        return 1

def hasProtectedPartitions(drive, dispatch):
    rc = False
    if anaconda is None:
        return rc

    try:
        for protected in dispatch.method.protectedPartitions():
            if protected.startswith(drive):
                part = protected[len(drive):]
                if part[0] == "p":
                    part = part[1:]
                if part.isdigit():
                    rc = True
                    break
    except:
        pass

    return rc

# attempt to associate a parted filesystem type on a partition that
# didn't probe as one type or another.
def validateFsType(part):
    # we only care about primary and logical partitions
    if not part.type in (parted.PARTITION_PRIMARY,
                         parted.PARTITION_LOGICAL):
        return
    # if the partition already has a type, no need to search
    if part.fs_type:
        return
    
    # first fsystem to probe wins, so sort the types into a preferred
    # order.
    fsnames = fsTypes.keys()
    goodTypes = ['ext3', 'ext2']
    badTypes = ['linux-swap',]
    for fstype in goodTypes:
        fsnames.remove(fstype)
    fsnames = goodTypes + fsnames
    for fstype in badTypes:
        fsnames.remove(fstype)
    fsnames.extend(badTypes)

    # now check each type, and set the partition system accordingly.
    for fsname in fsnames:
        fstype = fsTypes[fsname]
        if fstype.probe_specific(part.geom) != None:
            # XXX verify that this will not modify system type
            # in the case where a user does not modify partitions
            part.set_system(fstype)
            return
            
def isLinuxNativeByNumtype(numtype):
    """Check if the type is a 'Linux native' filesystem."""
    linuxtypes = [0x82, 0x83, 0x8e, 0xfd]

    for t in linuxtypes:
        if int(numtype) == t:
            return 1

    return 0

def sniffFilesystemType(device):
    """Sniff to determine the type of fs on device.  

    device - name of device to sniff.  we try to create it if it doesn't exist.
    """

    if os.access(device, os.O_RDONLY):
        dev = device
    else:
        dev = "/tmp/" + device
        if not os.access(dev, os.O_RDONLY):
            try:
                isys.makeDevInode(device, dev)
            except:
                pass

    pagesize = isys.getpagesize()
    if pagesize > 2048:
        num = pagesize
    else:
        num = 2048
    try:
        fd = os.open(dev, os.O_RDONLY)
        buf = os.read(fd, num)
        os.close(fd)
    except:
        return None

    if len(buf) < pagesize:
	try:
	    log("Tried to read pagesize for %s in sniffFilesystemType and only read %s", dev, len(buf))
	except:
	    pass
	return None

    # physical volumes start with HM (see linux/lvm.h
    # and LVM/ver/tools/lib/pv_copy.c)
    if buf.startswith("HM"):
        return "physical volume (LVM)"
    # sniff for LVM2 label.  see LVM/ver/lib/label/label.[ch] for a
    # description of the label and LVM/ver/lib/format_text/layout.h 
    for sec in range(0, 4):
        off = (sec * 512) + 24
        if buf[off:].startswith("LVM2"):
            return "physical volume (LVM)"

    try:
        isys.raidsbFromDevice(dev)
        return "software RAID"
    except:
        pass

    # ext2 check
    if struct.unpack("<H", buf[1080:1082]) == (0xef53,):
        if isys.ext2HasJournal(dev, makeDevNode = 0):
            return "ext3"
        else:
            return "ext2"

    # xfs signature
    if buf.startswith("XFSB"):
        return "xfs"

    # 2.6 doesn't support version 0, so we don't like SWAP-SPACE
    if (buf[pagesize - 10:] == "SWAPSPACE2"):
        return "swap"

    if fsset.isValidReiserFS(dev):
        return "reiserfs"

    if fsset.isValidJFS(dev):
        return "jfs"

    # FIXME:  we don't look for vfat

    return None

def getRedHatReleaseString(mountpoint):
    if os.access(mountpoint + "/etc/redhat-release", os.R_OK):
        f = open(mountpoint + "/etc/redhat-release", "r")
        try:
            lines = f.readlines()
        except IOError:
            try:
                f.close()
            except:
                pass
            return ""
        f.close()
        # return the first line with the newline at the end stripped
        if len(lines) == 0:
            return ""
	relstr = string.strip(lines[0][:-1])

        # get the release name and version
        # assumes that form is something
        # like "Red Hat Linux release 6.2 (Zoot)"
        if relstr.find("release") != -1:
            try:
                idx = relstr.find("release")
                prod = relstr[:idx - 1]

                ver = ""
                for a in relstr[idx + 8:]:
                    if a in string.digits + ".":
                        ver = ver + a
                    else:
                        break

                    relstr = prod + " " + ver
            except:
                pass # don't worry, just use the relstr as we have it
        return relstr
    return ""

def productMatches(oldproduct, newproduct):
    """Determine if this is a reasonable product to upgrade old product"""
    if oldproduct.startswith(newproduct):
        return 1

    productUpgrades = {
        "Red Hat Enterprise Linux AS": ("Red Hat Linux Advanced Server", ),
        "Red Hat Enterprise Linux WS": ("Red Hat Linux Advanced Workstation",),
        # FIXME: this probably shouldn't be in a release...
        "Red Hat Enterprise Linux": ("Red Hat Linux Advanced Server",
                                     "Red Hat Linux Advanced Workstation",
                                     "Red Hat Enterprise Linux AS",
                                     "Red Hat Enterprise Linux ES",
                                     "Red Hat Enterprise Linux WS"),
        "Fedora Core": ("Red Hat Linux",)
        }

    if productUpgrades.has_key(newproduct):
        acceptable = productUpgrades[newproduct]
    else:
        acceptable = ()

    for p in acceptable:
        if oldproduct.startswith(p):
            return 1

    return 0

class DiskSet:
    """The disks in the system."""

    skippedDisks = []
    exclusiveDisks = []
    mdList = []
    clearedDisks = []

    def __init__ (self):
        self.disks = {}
        self.onlyPrimary = None
        self.dispatch = dispatch #dispatch is in __builtins__

    def onlyPrimaryParts(self):
        for disk in self.disks.values():
            if disk.type.check_feature(parted.DISK_TYPE_EXTENDED):
                return 0

        return 1
        

    def startAllRaid(self):
        """Start all of the raid devices associated with the DiskSet."""
        driveList = []
        origDriveList = self.driveList()
        for drive in origDriveList:
            if not drive in DiskSet.skippedDisks:
                driveList.append(drive)
        DiskSet.mdList.extend(raid.startAllRaid(driveList))

    def stopAllRaid(self):
        """Stop all of the raid devices associated with the DiskSet."""
        raid.stopAllRaid(DiskSet.mdList)
        while DiskSet.mdList:
            DiskSet.mdList.pop()

    def getLabels(self):
        """Return a list of all of the labels used on partitions."""
        labels = {}
        
        drives = self.disks.keys()
        drives.sort()

        for drive in drives:
            # Don't read labels from drives we cleared using clearpart, as
            # we don't actually remove the existing filesystems so those
            # labels will still be present (#209291).
            if drive in DiskSet.clearedDisks:
                continue

            disk = self.disks[drive]
            func = lambda part: (part.is_active() and
                                 not (part.get_flag(parted.PARTITION_RAID)
                                      or part.get_flag(parted.PARTITION_LVM)))
            parts = filter_partitions(disk, func)
            for part in parts:
                node = get_partition_name(part)
                label = isys.readFSLabel(node)
                if label:
                    labels[node] = label

        for dev, devices, level, numActive in DiskSet.mdList:
            label = isys.readFSLabel(dev)
            if label:
                labels[dev] = label

        return labels

    def findExistingRootPartitions(self, intf, mountpoint, upgradeany = 0):
        """Return a list of all of the partitions which look like a root fs."""
        rootparts = []

        self.startAllRaid()

        for dev, devices, level, numActive in self.mdList:
            (errno, msg) = (None, None)
            found = 0
            for fs in fsset.getFStoTry(dev):
                try:
                    isys.mount(dev, mountpoint, fs, readOnly = 1)
                    found = 1
                    break
                except SystemError, (errno, msg):
                    pass

            if found:
                if os.access (mountpoint + '/etc/fstab', os.R_OK):
                    relstr = getRedHatReleaseString(mountpoint)
                    cmdline = open('/proc/cmdline', 'r').read()
                    
                    if ((cmdline.find("upgradeany") != -1) or
                        (upgradeany == 1) or
                        (productMatches(relstr, productName))):
                        rootparts.append ((dev, fs, relstr))
                isys.umount(mountpoint)

        # now, look for candidate lvm roots
	lvm.vgscan()
	lvm.vgactivate()

        for (vg, lv, size) in lvm.lvlist():
            dev = "/dev/%s/%s" %(vg, lv)
            found = 0
            for fs in fsset.getFStoTry(dev):
                try:
                    isys.mount(dev, mountpoint, fs, readOnly = 1)
                    found = 1
                    break
                except SystemError:
                    pass

            if found:
                if os.access (mountpoint + '/etc/fstab', os.R_OK):
                    relstr = getRedHatReleaseString(mountpoint)
                    cmdline = open('/proc/cmdline', 'r').read()
                    
                    if ((cmdline.find("upgradeany") != -1) or
                        (upgradeany == 1) or
                        (productMatches(relstr, productName))):
                        rootparts.append ((dev, fs, relstr))
                isys.umount(mountpoint)

	lvm.vgdeactivate()

        # don't stop raid until after we've looked for lvm on top of it
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
                    pass
                elif (part.fs_type and
                      part.fs_type.name in fsset.getUsableLinuxFs()):
                    node = get_partition_name(part)
		    try:
			isys.mount(node, mountpoint, part.fs_type.name)
		    except SystemError, (errno, msg):
                        part = disk.next_partition(part)
			continue
		    if os.access (mountpoint + '/etc/fstab', os.R_OK):
                        relstr = getRedHatReleaseString(mountpoint)
                        cmdline = open('/proc/cmdline', 'r').read()

                        if ((cmdline.find("upgradeany") != -1) or
                            (upgradeany == 1) or
                            (productMatches(relstr, productName))):
                            rootparts.append ((node, part.fs_type.name,
                                               relstr))
		    isys.umount(mountpoint)
                    
                part = disk.next_partition(part)
        return rootparts

    def driveList (self):
        """Return the list of drives on the system."""
	drives = isys.hardDriveDict().keys()
	drives.sort (isys.compareDrives)
	return drives

    def drivesByName (self):
        """Return a dictionary of the drives on the system."""
	return isys.hardDriveDict()

    def addPartition (self, device, type, spec):
        """Add a new partition to the device. - UNUSED."""
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
                constraint = disk.dev.constraint_any ()
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
        """Delete all partitions from all disks. - UNUSED."""
        for disk in self.disks.values():
            disk.delete_all ()

    def savePartitions (self):
        """Write the partition tables out to the disks."""
        for disk in self.disks.values():
            disk.commit()
            #disk.close()
            del disk
        self.refreshDevices()

    def refreshDevices (self, intf = None, initAll = 0,
                        zeroMbr = 0, clearDevs = []):
        """Reread the state of the disks as they are on disk."""
        self.closeDevices()
        self.disks = {}
        self.openDevices(intf, initAll, zeroMbr, clearDevs)

    def closeDevices (self):
        """Close all of the disks which are open."""
        for disk in self.disks.keys():
            #self.disks[disk].close()
            del self.disks[disk]

    def dasdFmt (self, intf = None, drive = None):
        """Format dasd devices (s390)."""

        if self.disks.has_key(drive):
            del self.disks[drive]

        w = intf.progressWindow (_("Initializing"),
                             _("Please wait while formatting drive %s...\n"
                               ) % (drive,), 100)
        try:
            isys.makeDevInode(drive, '/tmp/' + drive)
        except:
            pass

        argList = [ "/sbin/dasdfmt",
                    "-y",
                    "-b", "4096",
                    "-d", "cdl",
                    "-P",
                    "-F",
                    "-f",
                    "/tmp/%s" % drive]
        
        fd = os.open("/dev/null", os.O_RDWR | os.O_CREAT | os.O_APPEND)
        p = os.pipe()
        childpid = os.fork()
        if not childpid:
            os.close(p[0])
            os.dup2(p[1], 1)
            os.dup2(fd, 2)
            os.close(p[1])
            os.close(fd)
            os.execv(argList[0], argList)
            log("failed to exec %s", argList)
            os._exit(1)
			    
        os.close(p[1])

        num = ''
        sync = 0
        s = 'a'
        while s:
            try:
                s = os.read(p[0], 1)
                os.write(fd, s)

                if s != '\n':
                    try:
                        num = num + s
                    except:
                        pass
                else:
                    if num:
                        val = string.split(num)
                        if (val[0] == 'cyl'):
                            # printf("cyl %5d of %5d |  %3d%%\n",
                            val = int(val[5][:-1])
                            w and w.set(val)
                            # sync every 10%
                            if sync + 10 <= val:
                                isys.sync()
                                sync = val
                    num = ''
            except OSError, args:
                (errno, str) = args
                if (errno != 4):
                    raise IOError, args

        try:
            (pid, status) = os.waitpid(childpid, 0)
        except OSError, (num, msg):
            print __name__, "waitpid:", msg

        os.close(fd)

        w and w.pop()
        
        if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
            return 0

        return 1

    def openDevices (self, intf = None, initAll = 0,
                     zeroMbr = 0, clearDevs = []):
        """Open the disks on the system and skip unopenable devices."""
        if self.disks:
            return
        for drive in self.driveList ():
            # ignoredisk takes precedence over clearpart (#186438).
            if (DiskSet.exclusiveDisks != [] and drive not in DiskSet.exclusiveDisks) or drive in DiskSet.skippedDisks:
                continue
            deviceFile = isys.makeDevInode(drive)
            if isys.driveIsRemovable(drive) and not flags.expert:
                DiskSet.skippedDisks.append(drive)
                continue
            # FIXME: need the right fix for z/VM formatted dasd
            if iutil.getArch() == "s390" and drive[:4] == "dasd" and isys.getDasdState(drive):
                devs = isys.getDasdDevPort()
                if intf is None:
                    DiskSet.skippedDisks.append(drive)
                    continue

                if flags.runks == 1 and flags.display_mode == 'c':
                    rc = 1
                else:
                    rc = intf.messageWindow(_("Warning"),
                      _("The partition table on device %s (%s) was unreadable. "
                        "To create new partitions it must be initialized, "
                        "causing the loss of ALL DATA on this drive.\n\n"
                        "This operation will override any previous "
                        "installation choices about which drives to "
                        "ignore.\n\n"
                        "Would you like to initialize this drive, "
                        "erasing ALL DATA?")
                      % (drive, devs[drive]), type = "yesno")

                if rc == 0:
                    DiskSet.skippedDisks.append(drive)
                    continue
                else:
                    if (self.dasdFmt(intf, drive)):
                        DiskSet.skippedDisks.append(drive)
                        continue
                
            try:
                dev = parted.PedDevice.get (deviceFile)
            except parted.error, msg:
                DiskSet.skippedDisks.append(drive)
                continue
            
            if (initAll and ((clearDevs is None) or (len(clearDevs) == 0)
                             or drive in clearDevs) and not flags.test) \
                             and not hasProtectedPartitions(drive, self.dispatch):
                if iutil.getArch() == "s390" and drive[:4] == "dasd":
                    if (intf is None or self.dasdFmt(intf, drive)):
                        DiskSet.skippedDisks.append(drive)
                        continue                    
                else:
                    try:
                        disk = dev.disk_new_fresh(getDefaultDiskType())
                        disk.commit()
                        self.disks[drive] = disk
                        DiskSet.clearedDisks.append(drive)
                    except parted.error, msg:
                        DiskSet.skippedDisks.append(drive)
                        continue
                
            try:
                disk = parted.PedDisk.new(dev)
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
                    if iutil.getArch() == "s390" and drive[:4] == "dasd":
                         devs = isys.getDasdDevPort()
                         format = drive + " (" + devs[drive] + ")"
                    else:
                         format = drive

                    if iutil.getArch() == "s390" and drive[:4] == "dasd" and flags.runks == 1 and flags.display_mode == 'c':
                         rc = 1
                    else:
                         rc = intf.messageWindow(_("Warning"),
                           _("The partition table on device %s was unreadable. "
                             "To create new partitions it must be initialized, "
                             "causing the loss of ALL DATA on this drive.\n\n"
                             "This operation will override any previous "
                             "installation choices about which drives to "
                             "ignore.\n\n"
                             "Would you like to initialize this drive, "
                             "erasing ALL DATA?") % (format,), type = "yesno")

                    if rc == 0:
                        DiskSet.skippedDisks.append(drive)
                        continue
                    else:
                        recreate = 1

                if recreate == 1 and not flags.test:
                    if iutil.getArch() == "s390" and drive[:4] == "dasd":
                        if (intf is None or self.dasdFmt(intf, drive)):
                            DiskSet.skippedDisks.append(drive)
                            continue
                    else:                    
                        try:
                            disk = dev.disk_new_fresh(getDefaultDiskType())
                            disk.commit()
                            DiskSet.clearedDisks.append(drive)
                        except parted.error, msg:
                            DiskSet.skippedDisks.append(drive)
                            continue
                    try:
                        disk = parted.PedDisk.new(dev)
                        self.disks[drive] = disk
                    except parted.error, msg:
                        DiskSet.skippedDisks.append(drive)
                        continue

            filter_partitions(disk, validateFsType)

            # check for more than 15 partitions (libata limit)
            if drive.startswith('sd') and disk.get_last_partition_num() > 15:
                str = _("The drive /dev/%s has more than 15 partitions on it.  "
                        "The SCSI subsystem in the Linux kernel does not "
                        "allow for more than 15 partitons at this time.  You "
                        "will not be able to make changes to the partitioning "
                        "of this disk or use any partitions beyond /dev/%s15 "
                        "in %s") % (drive, drive, productName)

                if intf is not None:
                    rc = intf.messageWindow(_("Warning"), str, 
                                        type="custom",
                                        custom_buttons = [_("_Reboot"),
                                                          _("_Continue")],
                                        custom_icon="warning")
                    if rc == 0:
                        sys.exit(0)
                else:
                    log(str)
                    sys.exit(0)

            # check that their partition table is valid for their architecture
            ret = checkDiskLabel(disk, intf)
            if ret == 1:
                DiskSet.skippedDisks.append(drive)
                continue
            elif ret == -1:
                if iutil.getArch() == "s390" and drive[:4] == "dasd":
                    if (intf is None or self.dasdFmt(intf, drive)):
                        DiskSet.skippedDisks.append(drive)
                        continue                    
                else:
                    try:
                        disk = dev.disk_new_fresh(getDefaultDiskType())
                        disk.commit()
                        DiskSet.clearedDisks.append(drive)
                    except parted.error, msg:
                        DiskSet.skippedDisks.append(drive)
                        continue
                try:
                    disk = parted.PedDisk.new(dev)
                    self.disks[drive] = disk
                except parted.error, msg:
                    DiskSet.skippedDisks.append(drive)
                    continue

    def partitionTypes (self):
        """Return list of (partition, partition type) tuples for all parts."""
        rc = []
        drives = self.disks.keys()
        drives.sort()

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
        """Print out current disk state.  DEBUG."""
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
                    partFlags = get_flags (part)
                    rc = rc + ("%-9s %-12s %-12s %-10ld %-10ld %-10ld %7s\n"
                               % (device, part.type_name, fs_type_name,
                              part.geom.start, part.geom.end, part.geom.length,
                              partFlags))
                part = disk.next_partition(part)
        return rc

    def checkNoDisks(self, intf):
        """Check that there are valid disk devices."""
        if len(self.disks.keys()) == 0:
            intf.messageWindow(_("No Drives Found"),
                               _("An error has occurred - no valid devices were "
                                 "found on which to create new file systems. "
                                 "Please check your hardware for the cause "
                                 "of this problem."))
            sys.exit(0)

    



# XXX is this all of the possibilities?
dosPartitionTypes = [ 1, 6, 7, 11, 12, 14, 15 ]

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

max_logical_partition_count = {
    "hd": 59,
    "sd": 11,
    "ataraid/": 11,
    "rd/": 3,
    "cciss/": 11,
    "i2o/": 11,
    "iseries/vd": 3,
    "ida/": 11,
    "sx8/": 11,
}
