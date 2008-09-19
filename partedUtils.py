#
# partedUtils.py: helper functions for use with parted objects
#
# Copyright (C) 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Matt Wilson <msw@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#            Mike Fulbright <msf@redhat.com>
#            Karsten Hopp <karsten@redhat.com>
#

"""Helper functions for use when dealing with parted objects."""

import parted
import math
import os, sys, string, struct, resource

from product import *
import exception
import fsset
import iutil, isys
import raid
import dmraid
import block
import lvm
import traceback
from flags import flags
from errors import *
from constants import *

import logging
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

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

def getMaxAvailPartSizeMB(part):
    """Return the maximum size this partition can grow to by looking
    at contiguous freespace partitions."""

    disk = part.disk
    maxlen = part.geom.length

    # let's look at the next partition(s) and if they're freespace,
    # they can add to our maximum size.
    np = disk.next_partition(part)
    while np:
        if np.type & parted.PARTITION_FREESPACE:
            maxlen += np.geom.length
        else:
            break
        np = disk.next_partition(np)
    return math.floor(maxlen * part.geom.dev.sector_size / 1024.0 / 1024.0)

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
    elif isEfiSystemPartition(part):
        ptype = fsset.fileSystemTypeGet("efi")
    elif isEfiSystemPartition(part):
        ptype = fsset.fileSystemTypeGet("efi")
    elif part.fs_type.name in ("fat16", "fat32"):
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
        if isEfiSystemPartition(part):
            part.set_system(parted.file_system_type_get("fat32"))
        else:
            part.set_system(fstype.getPartedFileSystemType())
    except:
        print("Failed to set partition type to ",fstype.getName())
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
    if iutil.isEfi():
        return parted.disk_type_get("gpt")
    elif iutil.isX86():
        return parted.disk_type_get("msdos")
    elif iutil.isS390():
        # the "default" type is dasd, but we don't really do dasd
        # formatting with parted and use dasdfmt directly for them
        # so if we get here, it's an fcp disk and we should write
        # an msdos partition table (#144199)
        return parted.disk_type_get("msdos")
    elif iutil.isAlpha():
        return parted.disk_type_get("bsd")
    elif iutil.isSparc():
        return parted.disk_type_get("sun")
    elif iutil.isPPC():
        ppcMachine = iutil.getPPCMachine()

        if ppcMachine == "PMac":
            return parted.disk_type_get("mac")
        else:
            return parted.disk_type_get("msdos")
    else:
        return parted.disk_type_get("msdos")

def hasGptLabel(diskset, device):
    disk = diskset.disks[device]
    return disk.type.name == "gpt"

def isEfiSystemPartition(part):
    if not part.is_active():
        return False
    return (part.disk.type.name == "gpt" and
            part.get_name() == "EFI System Partition" and
            part.get_flag(parted.PARTITION_BOOT) == 1 and
            part.fs_type.name in ("fat16", "fat32") and
            isys.readFSLabel(get_partition_name(part)) != "ANACONDA")

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
                'gpt' in archLabels[iutil.getArch()]:
            label = parted.disk_type_get('gpt')

    disk = dev.disk_new_fresh(label)
    disk.commit()
    return disk

# this is kind of crappy, but we don't really want to allow LDL formatted
# dasd to be used during the install
def checkDasdFmt(disk, intf):
    if not iutil.isS390():
        return 0

    if disk.type.name != "dasd":
        return 0

    # FIXME: there has to be a better way to check LDL vs CDL
    # how do I test ldl vs cdl?
    if disk.max_primary_partition_count > 1:
        return 0

    if intf:
        try:
            device = disk.dev.path[5:]
            devs = isys.getDasdDevPort()
            dev = "/dev/%s (%s)" %(device, devs[device])
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
                                  "layout.  To use this drive for "
                                  "the installation of %s, it must be "
                                  "re-initialized, causing the loss of "
                                  "ALL DATA on this drive.\n\n"
                                  "Would you like to re-initialize this "
                                  "drive?")
                                %(disk.dev.path[5:], disk.type.name,
                                  productName), type="custom",
                                custom_buttons = [ _("_Ignore drive"),
                                                   _("_Re-initialize drive") ],
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
        for protected in anaconda.id.partitions.protectedPartitions():
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

    device - name of device to sniff.
    """
    return isys.readFSType(device)

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
        "Red Hat Enterprise Linux AS": ("Red Hat Linux Advanced Server", ),
        "Red Hat Enterprise Linux WS": ("Red Hat Linux Advanced Workstation",),
        # FIXME: this probably shouldn't be in a release...
        "Red Hat Enterprise Linux": ("Red Hat Linux Advanced Server",
                                     "Red Hat Linux Advanced Workstation",
                                     "Red Hat Enterprise Linux AS",
                                     "Red Hat Enterprise Linux ES",
                                     "Red Hat Enterprise Linux WS"),
        "Red Hat Enterprise Linux Server": ("Red Hat Enterprise Linux AS",
                                            "Red Hat Enterprise Linux ES",
                                            "Red Hat Enterprise Linux WS",
                                            "Red Hat Enterprise Linux"),
        "Red Hat Enterprise Linux Client": ("Red Hat Enterprise Linux WS",
                                            "Red Hat Enterprise Linux Desktop",
                                            "Red Hat Enterprise Linux"),
        "Fedora Core": ("Red Hat Linux",),
        "Fedora": ("Fedora Core",)
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
    mdList = []
    exclusiveDisks = []

    dmList = None
    mpList = None

    def __init__ (self, anaconda):
        self.disks = {}
        self.initializedDisks = {}
        self.onlyPrimary = None
        self.anaconda = anaconda
        self.devicesOpen = False

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

        if iutil.isS390():
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
        if iutil.isS390():
            return
        dmraid.renameRaidSet(rs, name)

    def stopDmRaid(self):
        """Stop all of the dmraid devices associated with the DiskSet."""

        if iutil.isS390():
            return
        if DiskSet.dmList:
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

        if not iutil.isS390():
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

    def getInfo(self, readFn=lambda d: isys.readFSLabel(d)):
        """Return a dict keyed on device name, storing some sort of data
           about each device.  This is typially going to be labels or UUIDs,
           as required by readFstab.
        """
        ret = {}

        encryptedDevices = self.anaconda.id.partitions.encryptedDevices

        for drive in self.driveList():
            # Don't read labels from drives we cleared using clearpart, as
            # we don't actually remove the existing filesystems so those
            # labels will still be present (#209291).
            if drive in DiskSet.skippedDisks:
                continue

            # ignoredisk takes precedence over clearpart (#186438).
            if DiskSet.exclusiveDisks != [] and \
                    drive not in DiskSet.exclusiveDisks:
                continue

            disk = self.disks[drive]
            func = lambda part: (part.is_active() and
                                 not (part.get_flag(parted.PARTITION_RAID)
                                      or part.get_flag(parted.PARTITION_LVM)))
            parts = filter_partitions(disk, func)
            for part in parts:
                node = get_partition_name(part)
                crypto = encryptedDevices.get(node)
                if crypto and not crypto.openDevice():
                    node = crypto.getDevice()

                val = readFn(node)
                if val:
                    ret[node] = val

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
            if crypto and not crypto.openDevice():
                dev = crypto.getDevice()

            val = readFn(dev)
            if val:
                ret[dev] = val

            if crypto:
                crypto.closeDevice()

        active = lvm.vgcheckactive()
        if not active:
            lvm.vgscan()
            lvm.vgactivate()

        for (vg, lv, size, lvorigin) in lvm.lvlist():
            if lvorigin:
                continue
            node = "%s/%s" % (vg, lv)
            crypto = encryptedDevices.get(node)
            if crypto and not crypto.openDevice():
                node = crypto.getDevice()

            val = readFn("/dev/" + node)
            if val:
                ret[node] = val

            if crypto:
                crypto.closeDevice()

        if not active:
            lvm.vgdeactivate()

        return ret

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
            theDev = dev
            crypto = self.anaconda.id.partitions.encryptedDevices.get(dev)
            if crypto and not crypto.openDevice():
                theDev = "/dev/%s" % (crypto.getDevice(),)
            elif crypto:
                log.error("failed to open encrypted device %s" % dev)

            fs = isys.readFSType(theDev)
            if fs is not None:
                try:
                    isys.mount(theDev, self.anaconda.rootPath, fs, readOnly = 1)
                    found = 1
                except SystemError:
                    pass

            if found:
                if os.access (self.anaconda.rootPath + '/etc/fstab', os.R_OK):
                    relstr = getReleaseString(self.anaconda.rootPath)

                    if ((upgradeany == 1) or
                        (productMatches(relstr, productName))):
                        try:
                            label = isys.readFSLabel(theDev)
                        except:
                            label = None
            
                        # XXX we could add the "raw" dev and let caller decrypt
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
            dev = "/dev/%s/%s" %(vg, lv)
            found = 0
            theDev = dev
            node = "%s/%s" % (vg, lv)
            dmnode = "mapper/%s-%s" % (vg, lv)
            crypto = self.anaconda.id.partitions.encryptedDevices.get(dmnode)
            if crypto and not crypto.openDevice():
                theDev = "/dev/%s" % (crypto.getDevice(),)
            elif crypto:
                log.error("failed to open encrypted device %s" % dev)

            fs = isys.readFSType(theDev)
            if fs is not None:
                try:
                    isys.mount(theDev, self.anaconda.rootPath, fs, readOnly = 1)
                    found = 1
                except SystemError:
                    pass

            if found:
                if os.access (self.anaconda.rootPath + '/etc/fstab', os.R_OK):
                    relstr = getReleaseString(self.anaconda.rootPath)
                    
                    if ((upgradeany == 1) or
                        (productMatches(relstr, productName))):
                        try:
                            label = isys.readFSLabel(theDev)
                        except:
                            label = None
            
                        rootparts.append ((theDev, fs, relstr, label))
                isys.umount(self.anaconda.rootPath)

	lvm.vgdeactivate()

        # don't stop raid until after we've looked for lvm on top of it
        self.stopMdRaid()

        drives = self.disks.keys()
        drives.sort()

        protected = self.anaconda.id.partitions.protectedPartitions()

        for drive in drives:
            disk = self.disks[drive]
            part = disk.next_partition ()
            while part:
                node = get_partition_name(part)
                crypto = self.anaconda.id.partitions.encryptedDevices.get(node)
                if (part.is_active()
                    and (part.get_flag(parted.PARTITION_RAID)
                         or part.get_flag(parted.PARTITION_LVM))):
                    part = disk.next_partition(part)
                    continue
                elif part.fs_type or crypto:
                    theDev = node
                    if part.fs_type:
                        fstype = part.fs_type.name

                    if crypto and not crypto.openDevice():
                        theDev = crypto.getDevice()
                        fstype = isys.readFSType("/dev/%s" % theDev)
                    elif crypto:
                        log.error("failed to open encrypted device %s" % node)

                    if not fstype or fstype not in fsset.getUsableLinuxFs():
                        part = disk.next_partition(part)
                        continue

                    try:
                        isys.mount("/dev/%s" % (theDev,),
                                   self.anaconda.rootPath, fstype)
                        checkRoot = self.anaconda.rootPath
                    except SystemError:
                        part = disk.next_partition(part)
                        continue

                    if os.access (checkRoot + '/etc/fstab', os.R_OK):
                        relstr = getReleaseString(checkRoot)

                        if ((upgradeany == 1) or
                            (productMatches(relstr, productName))):
                            try:
                                label = isys.readFSLabel("/dev/%s" % theDev)
                            except:
                                label = None

                            rootparts.append (("/dev/%s" % (theDev,),
                                              fstype, relstr, label))

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

    def savePartitions (self):
        """Write the partition tables out to the disks."""
        for disk in self.disks.values():
            if disk.dev.path[5:].startswith("sd") and disk.get_last_partition_num() > 15:
                log.debug("not saving partition table of disk with > 15 partitions")
                del disk
                continue

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
            if iutil.isX86() and disk.type.name == "gpt" and not iutil.isEfi():
                log.debug("syncing gpt to mbr for disk %s" % (disk.dev.path,))
                iutil.execWithRedirect("gptsync", [disk.dev.path,],
                                       stdout="/tmp/gptsync.log",
                                       stderr="/tmp/gptsync.err",
                                       searchPath = 1)
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
        for disk in self.disks.keys():
            #self.disks[disk].close()
            del self.disks[disk]
        self.devicesOpen = False

    def isDisciplineFBA (self, drive):
        if not iutil.isS390():
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
            del self.disks[drive]

        w = self.anaconda.intf.progressWindow (_("Initializing"),
                             _("Please wait while formatting drive %s...\n"
                               ) % (drive,), 100)

        argList = [ "/sbin/dasdfmt",
                    "-y",
                    "-b", "4096",
                    "-d", "cdl",
                    "-F",
                    "-P",
                    "-f",
                    "/dev/%s" % (dev,)]

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
            print(__name__, "waitpid:", msg)

        os.close(fd)

        w and w.pop()
        
        if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
            return 0

        return 1

    def _askForLabelPermission(self, intf, drive, clearDevs, initAll, ks):
        #Do not try to initialize device's part. table in rescue mode
        if self.anaconda.rescue:
            self._removeDisk(drive)
            return False

        rc = 0
        if (ks and (drive in clearDevs) and initAll) or \
	    self.isDisciplineFBA(drive):
            rc = 1
        elif intf:
            deviceFile = "/dev/" + drive
            dev = parted.PedDevice.get(deviceFile)

            msg = _("The partition table on device %s (%s %-0.f MB) was unreadable.\n\n"
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

        deviceFile = "/dev/" + drive

        try:
            try:
                # FIXME: need the right fix for z/VM formatted dasd
                if iutil.isS390() and drive[:4] == "dasd" and \
                   not self.isDisciplineFBA(drive):
                    if self.dasdFmt(drive):
                        raise LabelError, drive
                    dev = parted.PedDevice.get(deviceFile)
                    disk = parted.PedDisk.new(dev)
                else:
                    disk = labelDisk(deviceFile)
            except parted.error, msg:
                log.error("parted error: %s" % (msg,))
                raise
        except:
            (type, value, tb) = sys.exc_info()
            lines = exception.formatException(type, value, tb)
            for line in lines:
                log.error(line)
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

        intf = self.anaconda.intf
        zeroMbr = self.anaconda.id.partitions.zeroMbr

        for drive in self.driveList():
            # ignoredisk takes precedence over clearpart (#186438).
            if drive in DiskSet.skippedDisks:
                continue

            if DiskSet.exclusiveDisks != [] and \
                    drive not in DiskSet.exclusiveDisks:
                continue

            if not isys.mediaPresent(drive):
                DiskSet.skippedDisks.append(drive)
                continue

            disk = None
            dev = None

            if self.initializedDisks.has_key(drive):
                if not self.disks.has_key(drive):
                    try:
                        dev = parted.PedDevice.get("/dev/%s" % (drive,))
                        disk = parted.PedDisk.new(dev)
                        self._addDisk(drive, disk)
                    except parted.error, msg:
                        self._removeDisk(drive)
                continue

            ks = False
            clearDevs = []
            initAll = False

            if self.anaconda.isKickstart:
                ks = True
                clearDevs = self.anaconda.id.ksdata.clearpart.drives
                initAll = self.anaconda.id.ksdata.clearpart.initAll

            # FIXME: need the right fix for z/VM formatted dasd
            if iutil.isS390() \
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
                    disk, dev = self._labelDevice(drive)
                except:
                    continue

            try:
                if not dev:
                    dev = parted.PedDevice.get("/dev/%s" % (drive,))
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
                        disk, dev = self._labelDevice(drive)
                    except:
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

                rc = intf.messageWindow(_("Warning"), str, 
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
                    disk, dev = self._labelDevice(drive)
                except:
                    pass
        self.devicesOpen = True

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
    

    def exceptionDisks(self, anaconda, probe=True):
        if probe:
            isys.flushDriveDict()
            self.refreshDevices()

        drives = []
        for d in isys.removableDriveDict().items():
            func = lambda p: p.is_active() and not p.get_flag(parted.PARTITION_RAID) and not p.get_flag(parted.PARTITION_LVM) and p.fs_type.name in ["ext3", "ext2", "fat16", "fat32"]

            disk = self.disks[d[0]]
            parts = filter_partitions(disk, func)

            if len(parts) == 0:
                drives.append(d)
            else:
                for part in parts:
                    name = "%s%s" % (part.disk.dev.path, part.num)
                    drives.append((os.path.basename(name), d[1]))

        return drives

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
