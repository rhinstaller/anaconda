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
import os, sys, string, struct, resource

from product import *
import fsset
import iutil, isys
import raid
import rhpl
import dmraid
import block
import lvm
from flags import flags
from partErrors import *

from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

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

    drive = partition.geom.dev.path[5:]
    if (drive.startswith("cciss") or drive.startswith("ida") or
            drive.startswith("rd") or drive.startswith("sx8") or
            drive.startswith("mapper")):
        sep = "p"
    else:
        sep = ""
    return "%s%s%d" % (partition.geom.dev.path[5:], sep, partition.num)


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
    elif (part.get_flag(parted.PARTITION_BOOT) == 1 and
          getPartSizeMB(part) <= 1 and part.fs_type.name == "hfs"):
        ptype = fsset.fileSystemTypeGet("Apple Bootstrap")
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
    if rhpl.getArch() == "i386":
        return parted.disk_type_get("msdos")
    elif rhpl.getArch() == "ia64":
        return parted.disk_type_get("gpt")
    elif rhpl.getArch() == "s390":
        # the "default" type is dasd, but we don't really do dasd
        # formatting with parted and use dasdfmt directly for them
        # so if we get here, it's an fcp disk and we should write
        # an msdos partition table (#144199)
        return parted.disk_type_get("msdos")
    elif rhpl.getArch() == "alpha":
        return parted.disk_type_get("bsd")
    elif rhpl.getArch() == "sparc":
        return parted.disk_type_get("sun")
    elif rhpl.getArch() == "ppc":
        ppcMachine = iutil.getPPCMachine()

        if ppcMachine == "PMac":
            return parted.disk_type_get("mac")
        elif ppcMachine == "Pegasos":
            return parted.disk_type_get("amiga")
        else:
            return parted.disk_type_get("msdos")
    else:
        return parted.disk_type_get("msdos")

archLabels = {'i386': ['msdos', 'gpt'],
              's390': ['dasd', 'msdos'],
              'alpha': ['bsd', 'msdos'],
              'sparc': ['sun'],
              'ia64': ['msdos', 'gpt'],
              'ppc': ['msdos', 'mac', 'amiga', 'gpt'],
              'x86_64': ['msdos', 'gpt']}

def labelDisk(deviceFile, forceLabelType=None):
    dev = parted.PedDevice.get(deviceFile)
    label = getDefaultDiskType()

    if not forceLabelType is None:
        label = forceLabelType
    else:
        if label.name == 'msdos' and \
                dev.length > (2L**41) / dev.sector_size and \
                'gpt' in archLabels[rhpl.getArch()]:
            label = parted.disk_type_get('gpt')

    # remove metadata from partitions
    try:
        disk = parted.PedDisk.new(dev)
    except parted.error, msg:
        log.debug("parted error: %s" % (msg,))
    else:    
        part = disk.next_partition()
        while part:
            if (not part.is_active() or (part.type == parted.PARTITION_EXTENDED) or
               (part.disk.type.name == "mac" and part.num == 1 and part.get_name() == "Apple")):
                part = disk.next_partition(part)
                continue
            device = fsset.PartedPartitionDevice(part).getDevice()
            log.debug("removing lvm metadata from %s" %(device,))
            lvm.pvremove("/dev/%s" % (device,))
            part = disk.next_partition(part)

    disk = dev.disk_new_fresh(label)
    disk.commit()
    return disk

# this is kind of crappy, but we don't really want to allow LDL formatted
# dasd to be used during the install
def checkDasdFmt(disk, intf):
    if rhpl.getArch() != "s390":
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
            devnode = disk.dev.path[5:]
            dev = "/dev/%s (%s)" % (devnode, devs[devnode],)
        except Exception, e:
            log.critical("exception getting dasd dev ports: %s" %(e,))
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
    arch = rhpl.getArch()
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

def hasProtectedPartitions(drive, anaconda):
    rc = False
    if anaconda is None:
        return rc

    try:
        for protected in anaconda.method.protectedPartitions():
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

    pagesize = resource.getpagesize()
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
	    log.error("Tried to read pagesize for %s in sniffFilesystemType and only read %s", dev, len(buf))
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
            if fsset.ext4FileSystem.probe(dev):
                return "ext4"
            else:
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

def getReleaseString(mountpoint):
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
        "Red Hat Enterprise Linux Server": ("Red Hat Enterprise Linux Client release 5",
                                            "Red Hat Enterprise Linux Server release 5"),
        "Red Hat Enterprise Linux Client": ("Red Hat Enterprise Linux Client release 5",
                                            "Red Hat Enterprise Linux Server release 5"),
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

def dmNodeNameOfLV(volgroup, logvol):
    return "mapper/%s-%s" % (volgroup.replace("-", "--"), logvol.replace("-", "--"))

class DiskSet:
    """The disks in the system."""

    skippedDisks = []
    exclusiveDisks = []
    mdList = []
    dmList = None
    mpList = None
    clearedDisks = []

    def __init__ (self, anaconda = None):
        self.disks = {}
        self.initializedDisks = {}
        self.onlyPrimary = None
        self.anaconda = anaconda

    def onlyPrimaryParts(self):
        for disk in self.disks.values():
            if disk.type.check_feature(parted.DISK_TYPE_EXTENDED):
                return 0

        return 1

    def startMPath(self):
        """Start all of the dm multipath devices associated with the DiskSet."""

        if not DiskSet.mpList is None and DiskSet.mpList.__len__() > 0:
            return

        log.debug("starting mpaths")
        log.debug("self.driveList(): %s" % (self.driveList(),))
        log.debug("DiskSet.skippedDisks: %s" % (DiskSet.skippedDisks,))
        driveList = filter(lambda x: x not in DiskSet.skippedDisks,
                self.driveList())
        log.debug("DiskSet.skippedDisks: %s" % (DiskSet.skippedDisks,))

        mpList = dmraid.startAllMPath(driveList)
        DiskSet.mpList = mpList
        log.debug("done starting mpaths.  Drivelist: %s" % \
            (self.driveList(),))

    def renameMPath(self, mp, name):
        dmraid.renameMPath(mp, name)
 
    def stopMPath(self):
        """Stop all of the mpath devices associated with the DiskSet."""

        if DiskSet.mpList:
            dmraid.stopAllMPath(DiskSet.mpList)
            DiskSet.mpList = None

    def startDmRaid(self):
        """Start all of the dmraid devices associated with the DiskSet."""

        if rhpl.getArch() in ('s390', 's390x'):
            return
        if not DiskSet.dmList is None:
            return

        log.debug("starting dmraids")
        log.debug("self.driveList(): %s" % (self.driveList(),))
        log.debug("DiskSet.skippedDisks: %s" % (DiskSet.skippedDisks,))
        driveList = filter(lambda x: x not in DiskSet.skippedDisks,
                self.driveList())
        log.debug("DiskSet.skippedDisks: %s" % (DiskSet.skippedDisks,))

        dmList = dmraid.startAllRaid(driveList)
        DiskSet.dmList = dmList
        log.debug("done starting dmraids.  Drivelist: %s" % \
            (self.driveList(),))

    def renameDmRaid(self, rs, name):
        if rhpl.getArch() in ('s390', 's390x'):
            return
        dmraid.renameRaidSet(rs, name)

    def stopDmRaid(self):
        """Stop all of the dmraid devices associated with the DiskSet."""

        if rhpl.getArch() in ('s390', 's390x'):
            return
        if DiskSet.dmList or []:
            dmraid.stopAllRaid(DiskSet.dmList)
            DiskSet.dmList = None

    def startMdRaid(self):
        """Start all of the md raid devices associated with the DiskSet."""

        testList = []
        testList.extend(DiskSet.skippedDisks)

        for mp in DiskSet.mpList or []:
            for m in mp.members:
                disk = m.split('/')[-1]
                testList.append(disk)

        if not rhpl.getArch() in ('s390','s390x'):
            for rs in DiskSet.dmList or []:
                for m in rs.members:
                    if isinstance(m, block.RaidDev):
                        disk = m.rd.device.path.split('/')[-1]
                        testList.append(disk)

        driveList = filter(lambda x: x not in testList, self.driveList())
        DiskSet.mdList.extend(raid.startAllRaid(driveList))

    def stopMdRaid(self):
        """Stop all of the md raid devices associated with the DiskSet."""

        raid.stopAllRaid(DiskSet.mdList)

        while DiskSet.mdList:
            DiskSet.mdList.pop()

    def getLabels(self):
        """Return a list of all of the labels used on partitions."""
        labels = {}

        try:
            encryptedDevices = self.anaconda.id.partitions.encryptedDevices
        except:
            encryptedDevices = {}
        
        drives = self.disks.keys()
        drives.sort()

        for drive in drives:
            if drive in DiskSet.clearedDisks:
                continue
            disk = self.disks[drive]
            func = lambda part: (part.is_active() and
                                 not (part.get_flag(parted.PARTITION_RAID)
                                      or part.get_flag(parted.PARTITION_LVM)))
            parts = filter_partitions(disk, func)
            for part in parts:
                node = get_partition_name(part)
                crypto = encryptedDevices.get(node)
                mknode = 1
                prefix = ""
                if crypto and not crypto.openDevice():
                    node = crypto.getDevice()
                    mknode = 0
                    prefix = "/dev/"

                label = isys.readFSLabel(prefix + node, makeDevNode = mknode)
                if label:
                    labels[node] = label

                if crypto:
                    crypto.closeDevice()

        # not doing this right now, because we should _always_ have a
        # partition table of some kind on dmraid.
        if False:
            for rs in DiskSet.dmList or [] + DiskSet.mpList or []:
                label = isys.readFSLabel(rs.name)
                if label:
                    labels[rs.name] = label

        for dev, devices, level, numActive in DiskSet.mdList:
            crypto = encryptedDevices.get(dev)
            mknode = 1
            prefix = ""
            if crypto and not crypto.openDevice():
                dev = crypto.getDevice()
                mknode = 0
                prefix = "/dev/"

            label = isys.readFSLabel(prefix + dev, makeDevNode = mknode)
            if label:
                labels[dev] = label

            if crypto:
                crypto.closeDevice()

        for (vg, lv, size, lvorigin) in lvm.lvlist():
            if lvorigin:
                continue
            prefix = "/dev/"
            dev = "%s/%s" % (vg, lv)
            crypto = encryptedDevices.get(dmNodeNameOfLV(vg, lv))
            if crypto and not crypto.openDevice():
                dev = crypto.getDevice()
            label = isys.readFSLabel(prefix + dev, makeDevNode = 0)
            if label:
                labels[dev] = label

            if crypto:
                crypto.closeDevice()

        return labels

    def findExistingRootPartitions(self, upgradeany = 0):
        """Return a list of all of the partitions which look like a root fs."""
        rootparts = []

        self.startMPath()
        self.startDmRaid()
        self.startMdRaid()

        for dev, crypto in self.anaconda.id.partitions.encryptedDevices.items():
            # FIXME: order these so LVM and RAID always work on the first try
            if crypto.openDevice():
                log.error("failed to open encrypted device %s" % (dev,))

        if flags.cmdline.has_key("upgradeany"):
            upgradeany = 1

        for dev, devices, level, numActive in self.mdList:
            (errno, msg) = (None, None)
            found = 0
            theDev = "/dev/%s" % (dev,)
            crypto = self.anaconda.id.partitions.encryptedDevices.get(dev)
            if crypto and not crypto.openDevice():
                theDev = "/dev/%s" % (crypto.getDevice(),)
            elif crypto:
                log.error("failed to open encrypted device %s" % dev)
                crypto = None

            for fs in fsset.getFStoTry(theDev):
                try:
                    isys.mount(theDev, self.anaconda.rootPath, fs, readOnly = 1)
                    found = 1
                    break
                except SystemError, (errno, msg):
                    pass

            if found:
                if os.access (self.anaconda.rootPath + '/etc/fstab', os.R_OK):
                    relstr = getReleaseString(self.anaconda.rootPath)

                    if ((upgradeany == 1) or
                        (productMatches(relstr, productName))):
                        try:
                            label = isys.readFSLabel(theDev, makeDevNode=0)
                        except:
                            label = None
            
                        rootparts.append ((theDev, fs, relstr, label))
                isys.umount(self.anaconda.rootPath)

        # now, look for candidate lvm roots
	lvm.vgscan()
	lvm.vgactivate()

        for dev, crypto in self.anaconda.id.partitions.encryptedDevices.items():
            # FIXME: order these so LVM and RAID always work on the first try
            if crypto.openDevice():
                log.error("failed to open encrypted device %s" % (dev,))

        for (vg, lv, size, lvorigin) in lvm.lvlist():
            if lvorigin:
                continue
            theDev = "/dev/%s/%s" %(vg, lv)
            found = 0
            dmnode = "mapper/%s-%s" % (vg, lv)
            crypto = self.anaconda.id.partitions.encryptedDevices.get(dmnode)
            if crypto and not crypto.openDevice():
                theDev = "/dev/%s" % (crypto.getDevice(),)
            elif crypto:
                log.error("failed to open encrypted device %s" % dev)
                crypto = None

            for fs in fsset.getFStoTry(theDev):
                try:
                    isys.mount(theDev, self.anaconda.rootPath, fs, readOnly = 1)
                    found = 1
                    break
                except SystemError:
                    pass

            if found:
                if os.access (self.anaconda.rootPath + '/etc/fstab', os.R_OK):
                    relstr = getReleaseString(self.anaconda.rootPath)
                    
                    if ((upgradeany == 1) or
                        (productMatches(relstr, productName))):
                        try:
                            label = isys.readFSLabel(theDev, makeDevNode=0)
                        except:
                            label = None
            
                        rootparts.append ((theDev, fs, relstr, label))
                isys.umount(self.anaconda.rootPath)

	lvm.vgdeactivate()

        # don't stop raid until after we've looked for lvm on top of it
        self.stopMdRaid()

        drives = self.disks.keys()
        drives.sort()

        for drive in drives:
            disk = self.disks[drive]
            part = disk.next_partition ()
            while part:
                node = get_partition_name(part)
                crypto = self.anaconda.id.partitions.encryptedDevices.get(node)
                if (part.is_active()
                    and (part.get_flag(parted.PARTITION_RAID)
                         or part.get_flag(parted.PARTITION_LVM))):
                    pass
                elif part.fs_type or crypto:
                    theDev = node
                    if part.fs_type:
                        fstype = part.fs_type.name

                    # parted doesn't tell ext4 from ext3 for us
                    if fstype == "ext3": 
                        fstype = sniffFilesystemType("/dev/%s" % theDev)

                    if crypto and not crypto.openDevice():
                        theDev = crypto.getDevice()
                        fstype = sniffFilesystemType("/dev/%s" % theDev)
                    elif crypto:
                        log.error("failed to open encrypted device %s" % node)
                        crypto = None

                    if not fstype or fstype not in fsset.getUsableLinuxFs():
                        part = disk.next_partition(part)
                        continue

                    # In hard drive ISO method, don't try to mount the
                    # protected partitions because that'll throw up a
                    # useless error message.
                    protected = self.anaconda.method.protectedPartitions()

                    if protected and theDev in protected:
                        part = disk.next_partition(part)
                        continue

		    try:
			isys.mount(theDev, self.anaconda.rootPath, fstype)
		    except SystemError, (errno, msg):
                        part = disk.next_partition(part)
			continue
		    if os.access (self.anaconda.rootPath + '/etc/fstab', os.R_OK):
                        relstr = getReleaseString(self.anaconda.rootPath)

                        if ((upgradeany == 1) or
                            (productMatches(relstr, productName))):
                            try:
                                label = isys.readFSLabel("/dev/%s" % theDev, makeDevNode=0)
                            except:
                                label = None
            
                            rootparts.append ((theDev, fstype,
                                               relstr, label))
		    isys.umount(self.anaconda.rootPath)
                    
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
            log.info("disk.commit() for %s" % (disk.dev.path,))
            try:
                disk.commit()
            except:
                # if this fails, remove the disk so we don't use it later
                # Basically if we get here, badness has happened and we want
                # to prevent tracebacks from ruining the day any more.
                del disk
                continue

            # FIXME: this belongs in parted itself, but let's do a hack...
            if iutil.isMactel() and disk.type.name == "gpt" and \
                    os.path.exists("/usr/sbin/gptsync"):
                iutil.execWithRedirect("/usr/sbin/gptsync", [disk.dev.path],
                                       stdout="/dev/tty5", stderr="/dev/tty5")
            del disk
        self.refreshDevices()

    def _addDisk(self, drive, disk):
        log.debug("adding drive %s to disk list" % (drive,))
        self.initializedDisks[drive] = True
        self.disks[drive] = disk

    def _removeDisk(self, drive, addSkip=True):
        msg = "removing drive %s from disk lists" % (drive,)
        if addSkip:
            msg += "; adding to skip list"
        log.debug(msg)

        if self.disks.has_key(drive):
            del self.disks[drive]
        if addSkip:
            if self.initializedDisks.has_key(drive):
                del self.initializedDisks[drive]
            DiskSet.skippedDisks.append(drive)

    def refreshDevices (self):
        """Reread the state of the disks as they are on disk."""
        self.closeDevices()
        self.disks = {}
        self.openDevices()

    def closeDevices (self):
        """Close all of the disks which are open."""
        self.stopDmRaid()
        self.stopMPath()
        for drive in self.disks.keys():
            #self.disks[drive].close()
            self._removeDisk(drive, addSkip=False)

    def isDisciplineFBA (self, drive):
        if rhpl.getArch() != "s390":
            return False

        drive = drive.replace('/dev/', '')

        if drive.startswith("dasd"):
            discipline = "/sys/block/%s/device/discipline" % (drive,)
            if os.path.isfile(discipline):
                try:
                    fp = open(discipline, "r")
                    lines = fp.readlines()
                    fp.close()

                    if len(lines) == 1:
                        if lines[0].strip() == "FBA":
                            return True
                except:
                    log.error("failed to check discipline of %s" % (drive,))
                    pass

        return False

    def dasdFmt (self, drive = None):
        """Format dasd devices (s390)."""

        if self.disks.has_key(drive):
            self._removeDisk(drive, addSkip=False)

        w = self.anaconda.intf.progressWindow (_("Initializing"),
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
            log.critical("failed to exec %s", argList)
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

    def _askForLabelPermission(self, intf, drive, clearDevs, initAll, ks):
        # if anaconda is None here, we are called from labelFactory
        # XXX FIXME this test is terrible.
        if self.anaconda is not None:
            rc = 0
            if (ks and (drive in clearDevs) and initAll) or \
                self.isDisciplineFBA(drive):
                rc = 1
            else:
                if not intf:
                    self._removeDisk(drive)
                    return False

                if rhpl.getArch() == "s390" \
                        and drive[:4] == "dasd" \
                        and isys.getDasdState(drive):
                    devs = isys.getDasdDevPort()
                    msg = \
                     _("The partition table on device %s (%s) was unreadable. "
                       "To create new partitions it must be initialized, "
                       "causing the loss of ALL DATA on this drive.\n\n"
                       "This operation will override any previous "
                       "installation choices about which drives to "
                       "ignore.\n\n"
                       "Would you like to initialize this drive, "
                       "erasing ALL DATA?") % (drive, devs[drive])

                else:
                    deviceFile = isys.makeDevInode(drive, "/dev/" + drive)
                    dev = parted.PedDevice.get(deviceFile)

                    msg = _("The partition table on device %s (%s %-0.f MB) was unreadable.\n"
                            "To create new partitions it must be initialized, "
                            "causing the loss of ALL DATA on this drive.\n\n"
                            "This operation will override any previous "
                            "installation choices about which drives to "
                            "ignore.\n\n"
                            "Would you like to initialize this drive, "
                            "erasing ALL DATA?") % (drive, dev.model, getDeviceSizeMB (dev),)

                rc = intf.messageWindow(_("Warning"), msg, type="yesno")

            if rc != 0:
                return True
        
        self._removeDisk(drive)
        return False

    def _labelDevice(self, drive):
        log.info("Reinitializing label for drive %s" % (drive,))

        deviceFile = isys.makeDevInode(drive, "/dev/" + drive)

        try:
            try:
                # FIXME: need the right fix for z/VM formatted dasd
                if rhpl.getArch() == "s390" and drive[:4] == "dasd" and \
                   not self.isDisciplineFBA(drive):
                    if self.dasdFmt(drive):
                        raise LabelError, drive

                    dev = parted.PedDevice.get(deviceFile)
                    disk = parted.PedDisk.new(dev)
                else:
                    disk = labelDisk(deviceFile)
            except parted.error, msg:
                log.debug("parted error: %s" % (msg,))
                raise
        except:
            self._removeDisk(drive)
            raise LabelError, drive

        self._addDisk(drive, disk)
        return disk, dev

    def openDevices (self):
        """Open the disks on the system and skip unopenable devices."""

        if self.disks:
            return
        self.startMPath()
        self.startDmRaid()

        if self.anaconda is None:
            intf = None
            zeroMbr = None
        else:
            intf = self.anaconda.intf
            zeroMbr = self.anaconda.id.partitions.zeroMbr

        for drive in self.driveList():
            # ignoredisk takes precedence over clearpart (#186438).
            if (DiskSet.exclusiveDisks != [] and drive not in DiskSet.exclusiveDisks) or drive in DiskSet.skippedDisks:
                continue
            deviceFile = isys.makeDevInode(drive, "/dev/" + drive)
            if not isys.mediaPresent(drive) or isys.deviceIsReadOnly(drive):
                self._removeDisk(drive)
                continue

            disk = None
            dev = None

            if self.initializedDisks.has_key(drive):
                if not self.disks.has_key(drive):
                    try:
                        dev = parted.PedDevice.get(deviceFile)
                        disk = parted.PedDisk.new(dev)
                        self._addDisk(drive, disk)
                    except parted.error, msg:
                        self._removeDisk(drive)
                continue

            ks = False
            clearDevs = []
            initAll = False
            if self.anaconda is not None:
                if self.anaconda.isKickstart:
                    ks = True
                    clearDevs = self.anaconda.id.ksdata.clearpart["drives"]
                    initAll = self.anaconda.id.ksdata.clearpart["initAll"]

            # FIXME: need the right fix for z/VM formatted dasd
            if rhpl.getArch() == "s390" \
                    and drive[:4] == "dasd" \
                    and isys.getDasdState(drive):
                try:
                    if not self._askForLabelPermission(intf, drive, clearDevs,
                            initAll, ks):
                        raise LabelError, drive

                    disk, dev = self._labelDevice(drive)
                except:
                    continue

            if initAll and ((clearDevs is None) or (len(clearDevs) == 0) \
                       or (drive in clearDevs)) and not flags.test \
                       and not hasProtectedPartitions(drive, self.anaconda):
                try:
                    DiskSet.clearedDisks.append(drive)
                    disk, dev = self._labelDevice(drive)
                except:
                    continue

            try:
                if not dev:
                    dev = parted.PedDevice.get(deviceFile)
                    disk = None
            except parted.error, msg:
                log.debug("parted error: %s" % (msg,))
                self._removeDisk(drive, disk)
                continue

            try:
                if not disk:
                    disk = parted.PedDisk.new(dev)
                    self._addDisk(drive, disk)
            except parted.error, msg:
                recreate = 0
                if zeroMbr:
                    log.error("zeroMBR was set and invalid partition table "
                              "found on %s" % (dev.path[5:]))
                    recreate = 1
                else:
                    if not self._askForLabelPermission(intf, drive, clearDevs,
                            initAll, ks):
                        continue

                    recreate = 1

                if recreate == 1 and not flags.test:
                    try:
                        DiskSet.clearedDisks.append(drive)
                        disk, dev = self._labelDevice(drive)
                    except:
                        continue

            filter_partitions(disk, validateFsType)

            # check for more than 15 partitions (libata limit)
            if drive.startswith('sd') and disk.get_last_partition_num() > 15:
                rc = intf.messageWindow(_("Warning"),
                                       _("The drive /dev/%s has more than 15 "
                                         "partitions on it.  The SCSI "
                                         "subsystem in the Linux kernel does "
                                         "not allow for more than 15 partitons "
                                         "at this time.  You will not be able "
                                         "to make changes to the partitioning "
                                         "of this disk or use any partitions "
                                         "beyond /dev/%s15 in %s")
                                        % (drive, drive, productName),
                                        type="custom",
                                        custom_buttons = [_("_Reboot"),
                                                          _("_Continue")],
                                        custom_icon="warning")
                if rc == 0:
                    sys.exit(0)

            # check that their partition table is valid for their architecture
            ret = checkDiskLabel(disk, intf)
            if ret == 1:
                self._removeDisk(drive)
            elif ret == -1:
                try:
                    DiskSet.clearedDisks.append(drive)
                    disk, dev = self._labelDevice(drive)
                except:
                    pass

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

    def checkNoDisks(self):
        """Check that there are valid disk devices."""
        if len(self.disks.keys()) == 0:
            self.anaconda.intf.messageWindow(_("No Drives Found"),
                               _("An error has occurred - no valid devices were "
                                 "found on which to create new file systems. "
                                 "Please check your hardware for the cause "
                                 "of this problem."))
            return True
        return False
    



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
    0xbf: "Solaris",
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
    "xvd": 11,
    "vd": 11,
}
