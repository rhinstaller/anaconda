#
# fstab.py: filesystem management
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

import string
import isys
import iutil
import os
import errno
import parted
import sys
import struct
import partitioning
import types
from log import log
from translate import _, N_

defaultMountPoints = ['/', '/home', '/tmp', '/usr', '/var', '/usr/share']

if iutil.getArch() == "ia64":
    defaultMountPoints.insert(1, '/boot/efi')
else:
    defaultMountPoints.insert(1, '/boot')

fileSystemTypes = {}

if (iutil.getArch() != "s390" and iutil.getArch() != "s390x"):
    availRaidLevels = ['RAID0', 'RAID1', 'RAID5']
else:    
    availRaidLevels = ['RAID0', 'RAID5']

def fileSystemTypeGetDefault():
    if fileSystemTypeGet('ext3').isSupported():
        return fileSystemTypeGet('ext3')
    elif fileSystemTypeGet('ext2').isSupported():
        return fileSystemTypeGet('ext2')
    else:
        raise ValueError, "You have neither ext3 or ext2 support in your kernel!"


def fileSystemTypeGet(key):
    return fileSystemTypes[key]

def fileSystemTypeRegister(klass):
    fileSystemTypes[klass.getName()] = klass

def fileSystemTypeGetTypes():
    return fileSystemTypes.copy()

def mountCompare(a, b):
    one = a.mountpoint
    two = b.mountpoint
    if one < two:
        return -1
    elif two > one:
        return 1
    return 0

def devify(device):
    if device != "none" and device[0] != '/':
        return "/dev/" + device
    return device

class LabelFactory:
    def __init__(self):
        self.labels = None

    def createLabel(self, mountpoint):
        if self.labels == None:

            self.labels = {}
            diskset = partitioning.DiskSet()            
            diskset.openDevices()
            diskset.stopAllRaid()
            diskset.startAllRaid()
            labels = diskset.getLabels()
            del diskset
            self.reserveLabels(labels)
        
        if len(mountpoint) > 16:
            mountpoint = mountpoint[0:16]
        count = 0
        while self.labels.has_key(mountpoint):
            count = count + 1
            s = "%s" % count
            if (len(mountpoint) + len(s)) <= 16:
                mountpoint = mountpoint + s
            else:
                strip = len(mountpoint) + len(s) - 16
                mountpoint = mountpoint[0:len(mountpoint) - strip] + s
        self.labels[mountpoint] = 1

        return mountpoint

    def reserveLabels(self, labels):
        if self.labels == None:
            self.labels = {}
        for device, label in labels.items():
            self.labels[label] = 1

labelFactory = LabelFactory()

class FileSystemType:
    kernelFilesystems = {}
    def __init__(self):
        self.deviceArguments = {}
        self.formattable = 0
        self.checked = 0
        self.name = ""
        self.linuxnativefs = 0
        self.partedFileSystemType = None
        self.partedPartitionFlags = []
        self.maxSize = 2 * 1024 * 1024
        self.supported = -1
        self.defaultOptions = "defaults"
        self.migratetofs = None
        self.extraFormatArgs = []

    def mount(self, device, mountpoint, readOnly=0):
        if not self.isMountable():
            return
        iutil.mkdirChain(mountpoint)
        isys.mount(device, mountpoint, fstype = self.getName(), 
                   readOnly = readOnly)

    def umount(self, device, path):
        isys.umount(path, removeDir = 0)

    def getName(self):
        return self.name

    def registerDeviceArgumentFunction(self, klass, function):
        self.deviceArguments[klass] = function

    def badblocksDevice(self, entry, windowCreator, chroot='/'):
        if windowCreator:
            w = windowCreator(_("Checking for Bad Blocks"),
                              _("Checking for bad blocks on /dev/%s...")
                         % (entry.device.getDevice(),))
        else:
            w = None
        
        devicePath = entry.device.setupDevice(chroot)
        if (iutil.getArch() != "s390" and iutil.getArch() != "s390x"):
            args = [ "badblocks", "-vv", devicePath ]
        else:
            args = [ "badblocks", devicePath ]
        
        rc = iutil.execWithRedirect("/usr/sbin/badblocks", args,
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")

        w and w.pop()
        
        if rc:
            raise SystemError        
        
    def formatDevice(self, entry, progress, chroot='/'):
        if self.isFormattable():
            raise RuntimeError, "formatDevice method not defined"

    def migrateFileSystem(self, device, message, chroot='/'):
        if self.isMigratable():
            raise RuntimeError, "migrateFileSystem method not defined"

    def labelDevice(self, entry, chroot):
        pass
            
    def isFormattable(self):
        return self.formattable

    def isLinuxNativeFS(self):
        return self.linuxnativefs

    def readProcFilesystems(self):
        f = open("/proc/filesystems", 'r')
        if not f:
            pass
        lines = f.readlines()
        for line in lines:
            fields = string.split(line)
            if fields[0] == "nodev":
                fsystem = fields[1]
            else:
                fsystem = fields[0]
            FileSystemType.kernelFilesystems[fsystem] = None

    def isMountable(self):
        if not FileSystemType.kernelFilesystems:
            self.readProcFilesystems()

        return FileSystemType.kernelFilesystems.has_key(self.getName())

    def isSupported(self):
        if self.supported == -1:
            return self.isMountable()
        return self.supported
        
    def isChecked(self):
        return self.checked

    def getDeviceArgs(self, device):
        deviceArgsFunction = self.deviceArguments.get(device.__class__)
        if not deviceArgsFunction:
            return []
        return deviceArgsFunction(device)

    def getPartedFileSystemType(self):
        return self.partedFileSystemType

    def getPartedPartitionFlags(self):
        return self.partedPartitionFlags

    # note that this returns the maximum size of a filesystem in megabytes
    def getMaxSize(self):
        return self.maxSize

    def getDefaultOptions(self, mountpoint):
        return self.defaultOptions

    def getMigratableFSTargets(self):
        retval = []
        if not self.migratetofs:
            return retval

        for fs in self.migratetofs:
            if fileSystemTypeGet(fs).isSupported():
                retval.append(fs)
                
        return retval

    def isMigratable(self):
        if len(self.getMigratableFSTargets()) > 0:
            return 1
        else:
            return 0

class reiserfsFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("reiserfs")
        self.formattable = 1
        self.checked = 1
        self.linuxnativefs = 1
        # this is totally, 100% unsupported.  Boot with "linux reiserfs"
        # at the boot: prompt will let you make new reiserfs filesystems
        # in the installer.  Bugs filed when you use this will be closed
        # WONTFIX.
        try:
            f = open("/proc/cmdline")
            line = f.readline()
            if string.find(line, " reiserfs") != -1:
                self.supported = 1
            else:
                self.supported = 0
            del f
        except:
            self.supported = 0
        self.name = "reiserfs"

        self.maxSize = 2 * 1024 * 1024


    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)

        p = os.pipe()
        os.write(p[1], "y\n")
        os.close(p[1])

        rc = iutil.execWithRedirect("/usr/sbin/mkreiserfs",
                                    ["mkreiserfs", devicePath ],
                                    stdin = p[0],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")

        if rc:
            raise SystemError
                                  
fileSystemTypeRegister(reiserfsFileSystem())

class extFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = None
        self.formattable = 1
        self.checked = 1
        self.linuxnativefs = 1
        self.maxSize = 2 * 1024 * 1024

    def labelDevice(self, entry, chroot):
        devicePath = entry.device.setupDevice(chroot)
        label = labelFactory.createLabel(entry.mountpoint)
        rc = iutil.execWithRedirect("/usr/sbin/e2label",
                                    ["e2label", devicePath, label],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")
        if rc:
            raise SystemError
        if entry.device.getName() != "RAIDDevice":
            entry.setLabel(label)
        
    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)
        devArgs = self.getDeviceArgs(entry.device)
        args = [ "/usr/sbin/mke2fs", devicePath]
        args.extend(devArgs)
        args.extend(self.extraFormatArgs)
        if iutil.getArch() == "s390" or iutil.getArch() == "s390x" :
            args.extend(['-b', '4096'])

        rc = ext2FormatFilesystem(args, "/dev/tty5",
                                  progress,
                                  entry.mountpoint)
        if rc:
            raise SystemError

    # this is only for ext3 filesystems, but migration is a method
    # of the ext2 fstype
    def removeForcedFsck(self, entry, message, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)

        # if no journal, don't turn off the fsck
        if not isys.ext2HasJournal(devicePath, makeDevNode = 0):
            return

        rc = iutil.execWithRedirect("/usr/sbin/tune2fs",
                                    ["tunefs", "-c0", "-i0", devicePath],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")

class ext2FileSystem(extFileSystem):
    def __init__(self):
        extFileSystem.__init__(self)
        self.name = "ext2"
        self.partedFileSystemType = parted.file_system_type_get("ext2")
        self.migratetofs = ['ext3']


    def migrateFileSystem(self, entry, message, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)

        if not entry.fsystem or not entry.origfsystem:
            raise RuntimeError, ("Trying to migrate fs w/o fsystem or "
                                 "origfsystem set")
        if entry.fsystem.getName() != "ext3":
            raise RuntimeError, ("Trying to migrate ext2 to something other "
                                 "than ext3")

        # if journal already exists skip
        if isys.ext2HasJournal(devicePath, makeDevNode = 0):
            log("Skipping migration of %s, has a journal already.\n" % devicePath)
            return

        rc = iutil.execWithRedirect("/usr/sbin/tune2fs",
                                    ["tunefs", "-j", devicePath ],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")

        if rc:
            raise SystemError

        # XXX this should never happen, but appears to have done
        # so several times based on reports in bugzilla.
        # At least we can avoid leaving them with a system which won't boot
        if not isys.ext2HasJournal(devicePath, makeDevNode = 0):
            log("Migration of %s attempted but no journal exists after "
                "running tune2fs.\n" % (devicePath))
            if message:
                rc = message(_("Error"),
                        _("An error occurred migrating %s to ext3.  It is "
                          "possible to continue without migrating this "
                          "filesystem if desired.\n\n"
                          "Would you like to continue without migrating %s?")
                             % (devicePath, devicePath), type = "yesno")
                if rc == 0:
                    sys.exit(0)
            entry.fsystem = entry.origfsystem
        else:
            extFileSystem.removeForcedFsck(self, entry, message, chroot)


fileSystemTypeRegister(ext2FileSystem())

class ext3FileSystem(extFileSystem):
    def __init__(self):
        extFileSystem.__init__(self)
        self.name = "ext3"
        self.extraFormatArgs = [ "-j" ]
        self.partedFileSystemType = parted.file_system_type_get("ext3")

    def mount(self, device, mountpoint, readOnly=0):
        if not self.isMountable():
            return
        iutil.mkdirChain(mountpoint)
        # tricky - mount the filesystem as ext2, it makes the install
        # faster
        try:
            isys.mount(device, mountpoint, fstype = "ext2", 
                       readOnly = readOnly)
        except OSError:
            isys.mount(device, mountpoint, fstype = "ext3", 
                       readOnly = readOnly)
        except SystemError:
            isys.mount(device, mountpoint, fstype = "ext3", 
                       readOnly = readOnly)

    def formatDevice(self, entry, progress, chroot='/'):
        extFileSystem.formatDevice(self, entry, progress, chroot)
        extFileSystem.removeForcedFsck(self, entry, progress, chroot)

fileSystemTypeRegister(ext3FileSystem())

class raidMemberDummyFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("ext2")
        self.partedPartitionFlags = [ parted.PARTITION_RAID ]
        self.formattable = 1
        self.checked = 0
        self.linuxnativefs = 1
        self.name = "software RAID"
        self.maxSize = 2 * 1024 * 1024
        self.supported = 1

    def formatDevice(self, entry, progress, chroot='/'):
        # mkraid did all we need to format this partition...
        pass
    
#if not (iutil.getArch() == "s390" or iutil.getArch() == "s390x"):
fileSystemTypeRegister(raidMemberDummyFileSystem())

class swapFileSystem(FileSystemType):
    enabledSwaps = {}
    
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("linux-swap")
        self.formattable = 1
        self.name = "swap"
        self.maxSize = 2 * 1024
        self.linuxnativefs = 1
        self.supported = 1

    def mount(self, device, mountpoint, readOnly=0):
        isys.swapon (device)

    def umount(self, device, path):
        # unfortunately, turning off swap is bad.
        raise RuntimeError, "unable to turn off swap"
    
    def formatDevice(self, entry, progress, chroot='/'):
        file = entry.device.setupDevice(chroot)
        rc = iutil.execWithRedirect ("/usr/sbin/mkswap",
                                     [ "mkswap", '-v1', file ],
                                     stdout = None, stderr = None,
                                     searchPath = 1)
        if rc:
            raise SystemError

fileSystemTypeRegister(swapFileSystem())

class FATFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("FAT")
        self.formattable = 1
        self.checked = 0
        self.maxSize = 2 * 1024
        self.name = "vfat"

    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)
        devArgs = self.getDeviceArgs(entry.device)
        args = [ "mkdosfs", devicePath ]
        args.extend(devArgs)
        
        rc = iutil.execWithRedirect("/usr/sbin/mkdosfs", args,
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")
        if rc:
            raise SystemError
        
fileSystemTypeRegister(FATFileSystem())

class ForeignFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.formattable = 0
        self.checked = 0
        self.name = "foreign"

    def formatDevice(self, entry, progress, chroot='/'):
        return

fileSystemTypeRegister(ForeignFileSystem())

class PsudoFileSystem(FileSystemType):
    def __init__(self, name):
        FileSystemType.__init__(self)
        self.formattable = 0
        self.checked = 0
        self.name = name
        self.supported = 0

class ProcFileSystem(PsudoFileSystem):
    def __init__(self):
        PsudoFileSystem.__init__(self, "proc")

fileSystemTypeRegister(ProcFileSystem())

class DevptsFileSystem(PsudoFileSystem):
    def __init__(self):
        PsudoFileSystem.__init__(self, "devpts")
        self.defaultOptions = "gid=5,mode=620"

fileSystemTypeRegister(DevptsFileSystem())

class DevshmFileSystem(PsudoFileSystem):
    def __init__(self):
        PsudoFileSystem.__init__(self, "tmpfs")

    def isMountable(self):
        return 0
    
fileSystemTypeRegister(DevshmFileSystem())

class AutoFileSystem(PsudoFileSystem):
    def __init__(self):
        PsudoFileSystem.__init__(self, "auto")
        
fileSystemTypeRegister(AutoFileSystem())

class FileSystemSet:
    def __init__(self):
        self.messageWindow = None
        self.progressWindow = None
        self.waitWindow = None
        self.mountcount = 0
        self.migratedfs = 0
        self.reset()

    def isActive(self):
        return self.mountcount != 0
        
    def registerMessageWindow(self, method):
        self.messageWindow = method
        
    def registerProgressWindow(self, method):
        self.progressWindow = method

    def registerWaitWindow(self, method):
        self.waitWindow = method

    def reset (self):
        self.entries = []
        proc = FileSystemSetEntry(Device(), '/proc', fileSystemTypeGet("proc"))
        self.add(proc)
        pts = FileSystemSetEntry(Device(), '/dev/pts',
                                 fileSystemTypeGet("devpts"), "gid=5,mode=620")
        self.add(pts)
        shm = FileSystemSetEntry(Device(), '/dev/shm', fileSystemTypeGet("tmpfs"))

    def verify (self):
        for entry in self.entries:
            if type(entry.__dict__) != type({}):
                raise RuntimeError, "fsset internals inconsistent"

    def add (self, entry):
        # remove any existing duplicate entries
        for existing in self.entries:
            if (existing.device.getDevice() == entry.device.getDevice()
                and existing.mountpoint == entry.mountpoint):
                self.remove(existing)
        # XXX debuggin'
##         log ("fsset at %s\n"
##              "adding entry for %s\n"
##              "entry object %s, class __dict__ is %s",
##              self, entry.mountpoint, entry,
##              isys.printObject(entry.__dict__))
        self.entries.append(entry)
        self.entries.sort (mountCompare)

    def remove (self, entry):
        self.entries.remove(entry)

    def getEntryByMountPoint(self, mount):
        for entry in self.entries:
            if entry.mountpoint == mount:
                return entry
        return None

    def getEntryByDeviceName(self, dev):
        for entry in self.entries:
            if entry.device.getDevice() == dev:
                return entry
        return None

    def copy (self):
        new = FileSystemSet()
        for entry in self.entries:
            new.add (entry)
        return new
    
    def fstab (self):
	format = "%-23s %-23s %-7s %-15s %d %d\n"
        fstab = ""
        for entry in self.entries:
            if entry.mountpoint:
                if entry.getLabel():
                    device = "LABEL=%s" % (entry.getLabel(),)
                else:
                    device = devify(entry.device.getDevice())
                fstab = fstab + entry.device.getComment()
                fstab = fstab + format % (device, entry.mountpoint,
                                          entry.fsystem.getName(),
                                          entry.options, entry.fsck,
                                          entry.order)
        return fstab

    def raidtab(self):
        # set up raidtab...
        raidtab = ""
        for entry in self.entries:
            if entry.device.getName() == "RAIDDevice":
                raidtab = raidtab + entry.device.raidTab()

        return raidtab

    def write (self, prefix):
        f = open (prefix + "/etc/fstab", "w")
        f.write (self.fstab())
        f.close ()

        raidtab = self.raidtab()

        if raidtab:
            f = open (prefix + "/etc/raidtab", "w")
            f.write (raidtab)
            f.close ()

        # touch mtab
        open (prefix + "/etc/mtab", "w+")
        f.close ()

    def restoreMigratedFstab(self, prefix):
        if not self.migratedfs:
            return

        fname = prefix + "/etc/fstab"
        if os.access(fname + ".rpmsave", os.R_OK):
            os.rename(fname + ".rpmsave", fname)

    def migratewrite(self, prefix):
        if not self.migratedfs:
            return
        
        fname = prefix + "/etc/fstab"
        f = open (fname, "r")
        lines = f.readlines()
        f.close()

        perms = os.stat(fname)[0] & 0777
        os.rename(fname, fname + ".rpmsave")
        f = open (fname, "w+")
        os.chmod(fname, perms)
        
        for line in lines:
            fields = string.split(line)

            # try to be smart like in fsset.py::readFstab()
            if not fields or line[0] == "#":
                f.write(line)
                continue
            
            if len (fields) < 4 or len (fields) > 6:
                f.write(line)
                continue
                
            if string.find(fields[3], "noauto") != -1:
                f.write(line)
                continue
            
            mntpt = fields[1]
            entry = self.getEntryByMountPoint(mntpt)
            if not entry or not entry.getMigrate():
                f.write(line)
            elif entry.origfsystem.getName() != fields[2]:
                f.write(line)
            else:
                fields[2] = entry.fsystem.getName()
                newline = "%-23s %-23s %-7s %-15s %s %s\n" % (fields[0],
                                                              fields[1],
                                                              fields[2],
                                                              fields[3],
                                                              fields[4],
                                                              fields[5])
                f.write(newline)

        f.close()
        
    def rootOnLoop (self):
        for entry in self.entries:
            if (entry.mountpoint == '/'
                and entry.device.getName() == "LoopbackDevice"):
                return 1
        return 0

    def bootloaderChoices(self, diskSet):
	mntDict = {}

        for entry in self.entries:
	    mntDict[entry.mountpoint] = entry.device

#        if iutil.getArch() == "s390" or iutil.getArch() == "s390x" :
#	    return [ ( "/dev/dasda", "DASD" ) ]
        
        if iutil.getArch() == "ia64" and mntDict.has_key("/boot/efi"):
            bootDev = mntDict['/boot/efi']
	elif mntDict.has_key("/boot"):
	    bootDev = mntDict['/boot']
	else:
	    bootDev = mntDict['/']

	if bootDev.getName() == "LoopbackDevice":
	    return None
	elif bootDev.getName() == "RAIDDevice":
	    return [ ( bootDev.device, "RAID Device" ) ]
	
	return [ (diskSet.driveList()[0], N_("Master Boot Record (MBR)") ),
		 (bootDev.device,	  N_("First sector of boot partition"))
	       ]

    # set active partition on disks
    # if an active partition is set, leave it alone; if none set
    # set either our boot partition or the first partition on the drive active
    def setActive(self, diskset):
        choices = self.bootloaderChoices(diskset)
        if not choices:
            bootDev = None
        elif len(choices) == 1:
            bootDev = self.bootloaderChoices(diskset)[0][0]
        else:
            bootDev = self.bootloaderChoices(diskset)[1][0]

        # stupid itanium
        if iutil.getArch() == "ia64":
            part = partitioning.get_partition_by_name(diskset.disks, bootDev)
            if part and part.is_flag_available(parted.PARTITION_BOOT):
                part.set_flag(parted.PARTITION_BOOT, 1)
            return
        
        for drive in diskset.disks.keys():
            foundActive = 0
            bootPart = None
            disk = diskset.disks[drive]
            part = disk.next_partition()
            while part:
                if not part.is_active():
                    part = disk.next_partition(part)
                    continue

                if not part.is_flag_available(parted.PARTITION_BOOT):
                    foundActive = 1
                    part = None
                    continue

                if part.get_flag(parted.PARTITION_BOOT):
                    foundActive = 1
                    part = None
                    continue

                if not bootPart:
                    bootPart = part

                if partitioning.get_partition_name(part) == bootDev:
                    bootPart = part
                
                part = disk.next_partition(part)

            if bootPart and not foundActive:
                bootPart.set_flag(parted.PARTITION_BOOT, 1)

            if bootPart:
                del bootPart

    def formatSwap (self, chroot):
        for entry in self.entries:
            if (not entry.fsystem or not entry.fsystem.getName() == "swap"
                or not entry.getFormat() or entry.isMounted()):
                continue
            try:
                self.formatEntry(entry, chroot)
            except SystemError:
                if self.messageWindow:
                    self.messageWindow(_("Error"),
                                       _("An error occurred trying to "
                                         "initialize swap on device %s.  This "
                                         "problem is serious, and the install "
                                         "cannot continue.\n\n"
                                         "Press Enter to reboot your system.")
                                       % (entry.device.getDevice(),))
                sys.exit(0)
                    
                
    def turnOnSwap (self, chroot):
        for entry in self.entries:
            if (entry.fsystem and entry.fsystem.getName() == "swap"
                and not entry.isMounted()):
                try:
                    entry.mount(chroot)
                    self.mountcount = self.mountcount + 1
                except SystemError, (num, msg):
                    if self.messageWindow:
                        self.messageWindow(_("Error"), 
                                           _("Error enabling swap device %s: "
                                             "%s\n\n"
                                             "This most likely means this "
                                             "swap partition has not been "
                                             "initialized."
                                             "\n\n"
                                             "Press OK to reboot your "
                                             "system.")
                                           % (entry.device.getDevice(), msg))
                    sys.exit(0)

    def labelEntry(self, entry, chroot):
        entry.fsystem.labelDevice(entry, chroot)
    
    def formatEntry(self, entry, chroot):
        entry.fsystem.formatDevice(entry, self.progressWindow, chroot)

    def badblocksEntry(self, entry, chroot):
        entry.fsystem.badblocksDevice(entry, self.waitWindow, chroot)
        
    def getMigratableEntries(self):
        retval = []
        for entry in self.entries:
            if entry.origfsystem and entry.origfsystem.isMigratable():
                retval.append(entry)

        return retval
    
    def formattablePartitions(self):
        list = []
        for entry in self.entries:
            if entry.fsystem.isFormattable():
                list.append (entry)
        return list

    def checkBadblocks(self, chroot='/'):
        for entry in self.entries:
            if (not entry.fsystem.isFormattable() or not entry.getBadblocks()
                or entry.isMounted()):
                continue
            try:
                self.badblocksEntry(entry, chroot)
            except SystemError:
                if self.messageWindow:
                    self.messageWindow(_("Error"),
                                       _("An error occurred searching for "
                                         "bad blocks on %s.  This problem is "
                                         "serious, and the install cannot "
                                         "continue.\n\n"
                                         "Press Enter to reboot your system.")
                                       % (entry.device.getDevice(),))
                sys.exit(0)

    def makeFilesystems (self, chroot='/'):
        formatted = []
        for entry in self.entries:
            if (not entry.fsystem.isFormattable() or not entry.getFormat()
                or entry.isMounted()):
                continue
            try:
                self.formatEntry(entry, chroot)
                formatted.append(entry)
            except SystemError:
                if self.messageWindow:
                    self.messageWindow(_("Error"),
                                       _("An error occurred trying to "
                                         "format %s.  This problem is "
                                         "serious, and the install cannot "
                                         "continue.\n\n"
                                         "Press Enter to reboot your system.")
                                       % (entry.device.getDevice(),))
                sys.exit(0)

        for entry in formatted:
            try:
                self.labelEntry(entry, chroot)
            except SystemError:
                # should be OK, we'll still use the device name to mount.
                pass

    def haveMigratedFilesystems(self):
        return self.migratedfs

    def migrateFilesystems (self, chroot='/'):
        if self.migratedfs:
            return
        
        for entry in self.entries:
            if not entry.origfsystem:
                continue

            if not entry.origfsystem.isMigratable() or not entry.getMigrate():
                continue
            try: 
                entry.origfsystem.migrateFileSystem(entry, self.messageWindow,
                                                    chroot)
            except SystemError:
                if self.messageWindow:
                    self.messageWindow(_("Error"),
                                       _("An error occurred trying to "
                                         "migrate %s.  This problem is "
                                         "serious, and the install cannot "
                                         "continue.\n\n"
                                         "Press Enter to reboot your system.")
                                       % (entry.device.getDevice(),))
                sys.exit(0)

        self.migratedfs = 1

    def mountFilesystems(self, instPath = '/', raiseErrors = 0, readOnly = 0):
	for entry in self.entries:
            if not entry.fsystem.isMountable():
		continue
            try:
                entry.mount(instPath)
                self.mountcount = self.mountcount + 1
            except OSError, (num, msg):
                if self.messageWindow:
                    if num == errno.EEXIST:
                        self.messageWindow(_("Invalid mount point"),
                                           _("An error occurred when trying "
                                             "to create %s.  Some element of "
                                             "this path is not a directory. "
                                             "This is a fatal error and the "
                                             "install cannot continue.\n\n"
                                             "Press Enter to reboot your "
                                             "system.") % (entry.mountpoint,))
                    else:
                        self.messageWindow(_("Invalid mount point"),
                                           _("An error occurred when trying "
                                             "to create %s: %s.  This is "
                                             "a fatal error and the install "
                                             "cannot continue.\n\n"
                                             "Press Enter to reboot your "
                                             "system.") % (entry.mountpoint,
                                                           msg))
                sys.exit(0)
            except SystemError, (num, msg):
                if raiseErrors:
                    raise SystemError, (num, msg)
                if self.messageWindow:
                    self.messageWindow(_("Error"), 
                                       _("Error mounting device %s as %s: "
                                         "%s\n\n"
                                         "This most likely means this "
                                         "partition has not been formatted."
                                         "\n\n"
                                         "Press OK to reboot your system.")
                                       % (entry.device.getDevice(),
                                          entry.mountpoint, msg))
                sys.exit(0)

    def filesystemSpace(self, chroot='/'):
	space = []
        # XXX limit to ext[23] etc?
        for entry in self.entries:
            if not entry.isMounted():
                continue
            path = "%s/%s" % (chroot, entry.mountpoint)
            try:
                space.append((entry.mountpoint, isys.fsSpaceAvailable(path)))
            except SystemError:
                pass

        def spaceSort(a, b):
            (m1, s1) = a
            (m2, s2) = b

            if (s1 > s2):
                return -1
            elif s1 < s2:
                return 1

            return 0

	space.sort(spaceSort)
	return space

    def hasDirtyFilesystems(self):
	if self.rootOnLoop():
            entry = self.getEntryByMountPoint('/')
            mountLoopbackRoot(entry.device.host[5:], skipMount = 1)
	    dirty = isys.ext2IsDirty("loop1")
	    unmountLoopbackRoot(skipMount = 1)
	    if dirty: return 1

	for entry in self.entries:
            # XXX - multifsify, virtualize isdirty per fstype
	    if entry.fsystem.getName() != "ext2": continue
	    if entry.getFormat(): continue

	    if isys.ext2IsDirty(entry.device.getDevice()): return 1

	return 0

    def umountFilesystems(self, instPath, ignoreErrors = 0):
        # XXX remove special case
        try:
            isys.umount(instPath + '/proc/bus/usb', removeDir = 0)
            log("Umount USB OK")
        except:
#           log("Umount USB Fail")
            pass

        reverse = self.entries
        reverse.reverse()

	for entry in reverse:
            entry.umount(instPath)

class FileSystemSetEntry:
    def __init__ (self, device, mountpoint,
                  fsystem=None, options=None,
                  origfsystem=None, migrate=0,
                  order=-1, fsck=-1, format=0,
                  badblocks = 0):
        if not fsystem:
            fsystem = fileSystemTypeGet("ext2")
        self.device = device
        self.mountpoint = mountpoint
        self.fsystem = fsystem
        self.origfsystem = origfsystem
        self.migrate = migrate
        if options:
            self.options = options
        else:
            self.options = fsystem.getDefaultOptions(mountpoint)
        self.mountcount = 0
        self.label = None
        if fsck == -1:
            self.fsck = fsystem.isChecked()
        else:
            self.fsck = fsck
        if order == -1:
            if mountpoint == '/':
                self.order = 1
            elif self.fsck:
                self.order = 2
            else:
                self.order = 0
        else:
            self.order = order
        if format and not fsystem.isFormattable():
            raise RuntimeError, ("file system type %s is not formattable, "
                                 "but has been added to fsset with format "
                                 "flag on" % fsystem.getName())
        self.format = format
        self.badblocks = badblocks

    def mount(self, chroot='/', devPrefix='/tmp'):
        device = self.device.setupDevice(chroot, devPrefix=devPrefix)
        self.fsystem.mount(device, "%s/%s" % (chroot, self.mountpoint))
        self.mountcount = self.mountcount + 1

    def umount(self, chroot='/'):
        if self.mountcount > 0:
            try:
                self.fsystem.umount(self.device, "%s/%s" % (chroot,
                                                            self.mountpoint))
                self.mountcount = self.mountcount - 1
            except RuntimeError:
                pass

    def setFileSystemType(self, fstype):
        self.fsystem = fstype
        
    def setBadblocks(self, state):
        self.badblocks = state

    def getBadblocks(self):
        return self.badblocks
        
    def setFormat (self, state):
        if self.migrate and state:
            raise ValueError, "Trying to set format bit on when migrate is set!"
        self.format = state

    def getFormat (self):
        return self.format

    def setMigrate (self, state):
        if self.format and state:
            raise ValueError, "Trying to set migrate bit on when format is set!"

        self.migrate = state

    def getMigrate (self):
        return self.migrate

    def isMounted (self):
        return self.mountcount > 0

    def getLabel (self):
        return self.label

    def setLabel (self, label):
        self.label = label

class Device:
    def __init__(self):
        self.device = "none"
        self.fsoptions = {}
        self.label = None
        self.isSetup = 0

    def getComment (self):
        return ""

    def getDevice (self, asBoot = 0):
        return self.device

    def setupDevice (self, chroot='/', devPrefix='/tmp'):
        return self.device

    def cleanupDevice (self, chroot, devPrefix='/tmp'):
        pass

    def solidify (self):
        pass

    def getName(self):
        return self.__class__.__name__

class RAIDDevice(Device):
    # XXX usedMajors does not take in account any EXISTING md device
    #     on the system for installs.  We need to examine all partitions
    #     to investigate which minors are really available.
    usedMajors = {}

    # members is a list of Device based instances that will be
    # a part of this raid device
    def __init__(self, level, members, minor=-1, spares=0, existing=0):
        Device.__init__(self)
        self.level = level
        self.members = members
        self.spares = spares
        self.numDisks = len(members) - spares
        self.isSetup = existing

        if len(members) < spares:
            raise RuntimeError, ("you requiested more spare devices "
                                 "than online devices!")

        if level == 5:
            if self.numDisks < 3:
                raise RuntimeError, "RAID 5 requires at least 3 online members"
        
        # there are 32 major md devices, 0...31
        if minor == -1:
            for I in range(32):
                if not RAIDDevice.usedMajors.has_key(I):
                    minor = I
                    break

            if minor == -1:
                raise RuntimeError, ("Unable to allocate minor number for "
                                     "raid device")

        RAIDDevice.usedMajors[minor] = None
        self.device = "md" + str(minor)
        self.minor = minor

        # make sure the list of raid members is sorted
        self.members.sort()

    def __del__ (self):
        del RAIDDevice.usedMajors[self.minor]

    def ext2Args (self):
        if self.level == 5:
            return [ '-R', 'stride=%d' % ((self.numDisks - 1) * 16) ]
        elif self.level == 0:
            return [ '-R', 'stride=%d' % (self.numDisks * 16) ]
        return []

    def raidTab (self, devPrefix='/dev'):
        entry = ""
        entry = entry + "raiddev		    %s/%s\n" % (devPrefix,
                                                                self.device,)
        entry = entry + "raid-level		    %d\n" % (self.level,)
        entry = entry + "nr-raid-disks		    %d\n" % (self.numDisks,)
        entry = entry + "chunk-size		    64k\n"
        entry = entry + "persistent-superblock	    1\n"
        entry = entry + "nr-spare-disks		    %d\n" % (self.spares,)
        i = 0
        for device in self.members[:self.numDisks]:
            entry = entry + "    device	    %s/%s\n" % (devPrefix,
                                                        device)
            entry = entry + "    raid-disk     %d\n" % (i,)
            i = i + 1
        i = 0
        for device in self.members[self.numDisks:]:
            entry = entry + "    device	    %s/%s\n" % (devPrefix,
                                                        device)
            entry = entry + "    spare-disk     %d\n" % (i,)
            i = i + 1
        return entry

    def setupDevice (self, chroot, devPrefix='/tmp'):
        node = "%s/%s" % (devPrefix, self.device)
        isys.makeDevInode(self.device, node)

        if not self.isSetup:
            raidtab = '/tmp/raidtab.%s' % (self.device,)
            f = open(raidtab, 'w')
            f.write(self.raidTab('/tmp'))
            f.close()
            for device in self.members:
                PartitionDevice(device).setupDevice(chroot,
                                                    devPrefix=devPrefix)
            iutil.execWithRedirect ("/usr/sbin/mkraid", 
                                    ('mkraid', '--really-force',
                                     '--configfile', raidtab, node),
                                    stderr="/dev/tty5", stdout="/dev/tty5")
            partitioning.register_raid_device(self.device, self.members[:],
                                              self.level, self.numDisks)
            self.isSetup = 1
        return node

    def getDevice (self, asBoot = 0):
        if not asBoot:
            return self.device
        else:
            return self.members[0]

    def solidify(self):
        return
        
ext2 = fileSystemTypeGet("ext2")
ext2.registerDeviceArgumentFunction(RAIDDevice, RAIDDevice.ext2Args)

class LVMDevice(Device):
    def __init__(self):
        Device.__init__(self)
    
class PartitionDevice(Device):
    def __init__(self, partition):
        Device.__init__(self)
        if type(partition) != types.StringType:
            raise ValueError, "partition must be a string"
        self.device = partition

    def setupDevice(self, chroot, devPrefix='/tmp'):
        path = '%s/%s' % (devPrefix, self.getDevice(),)
        isys.makeDevInode(self.getDevice(), path)
        return path

class PartedPartitionDevice(PartitionDevice):
    def __init__(self, partition):
        Device.__init__(self)
        self.device = None
        self.partition = partition

    def getDevice(self, asBoot = 0):
        if not self.partition:
            return self.device
        
        return partitioning.get_partition_name(self.partition)

    def solidify(self):
        # drop reference on the parted partition object and note
        # the current minor number allocation
        self.device = self.getDevice()
        self.partition = None
        
class SwapFileDevice(Device):
    def __init__(self, file):
        Device.__init__(self)
        self.device = file
        self.size = 0

    def setSize (self, size):
        self.size = size

    def setupDevice (self, chroot, devPrefix='/tmp'):
        file = os.path.normpath(chroot + self.getDevice())
        if not os.access(file, os.R_OK):
            if self.size:
                isys.ddfile(file, self.size, None)
            else:
                raise SystemError, (0, "swap file creation necessary, but "
                                    "required size is unknown.")
        return file

# This is a device that describes a swap file that is sitting on
# the loopback filesystem host for partitionless installs.
# The piggypath is the place where the loopback file host filesystem
# will be mounted
class PiggybackSwapFileDevice(SwapFileDevice):
    def __init__(self, piggypath, file):
        SwapFileDevice.__init__(self, file)
        self.piggypath = piggypath
        
    def setupDevice(self, chroot, devPrefix='/tmp'):
        return SwapFileDevice.setupDevice(self, self.piggypath, devPrefix)

class LoopbackDevice(Device):
    def __init__(self, hostPartition, hostFs):
        Device.__init__(self)
        self.host = "/dev/" + hostPartition
        self.hostfs = hostFs
        self.device = "loop1"

    def setupDevice(self, chroot, devPrefix='/tmp/'):
        if not self.isSetup:
            isys.mount(self.host[5:], "/mnt/loophost", fstype = "vfat")
            self.device = allocateLoopback("/mnt/loophost/redhat.img")
            if not self.device:
                raise SystemError, "Unable to allocate loopback device"
            self.isSetup = 1
            path = '%s/%s' % (devPrefix, self.getDevice())
        else:
            path = '%s/%s' % (devPrefix, self.getDevice())
            isys.makeDevInode(self.getDevice(), path)
        path = os.path.normpath(path)
        return path

    def getComment (self):
        return "# LOOP1: %s %s /redhat.img\n" % (self.host, self.hostfs)

def makeDevice(dev):
    if dev[:2] == "md":
        try:
            mdname, devices, level, numActive = \
                    partitioning.lookup_raid_device(dev)
            device = RAIDDevice(level, devices,
                                minor=int(mdname[2:]),
                                spares=len(devices) - numActive,
                                existing=1)
        except KeyError:
            device = PartitionDevice(dev)
    else:
        device = PartitionDevice(dev)
    return device

# XXX fix RAID
def readFstab (path):
    fsset = FileSystemSet()

    # first, we look at all the disks on the systems and get any ext2/3
    # labels off of the filesystem.
    # temporary, to get the labels
    diskset = partitioning.DiskSet()
    diskset.openDevices()
    labels = diskset.getLabels()

    labelToDevice = {}
    for device, label in labels.items():
	labelToDevice[label] = device

    # mark these labels found on the system as used so the factory
    # doesn't give them to another device
    labelFactory.reserveLabels(labels)
    
    loopIndex = {}

    f = open (path, "r")
    lines = f.readlines ()
    f.close

    for line in lines:
	fields = string.split (line)

	if not fields: continue

        # pick up the magic comment in fstab that tells us which
        # device is the loop host in a partionless upgrade
	if fields[0] == "#" and len(fields) > 4 and fields[1][:4] == "LOOP":
	    device = string.lower(fields[1])
	    if device[len(device) - 1] == ":":
		device = device[:len(device) - 1]
	    realDevice = fields[2]
	    if realDevice[:5] == "/dev/":
		realDevice = realDevice[5:]
	    loopIndex[device] = (realDevice, fields[3])

	if line[0] == "#":
	    # skip all comments
	    continue

	# all valid fstab entries have 6 fields
	if len (fields) < 4 or len (fields) > 6: continue

        # if we don't support mounting the filesystem, continue
        if not fileSystemTypes.has_key(fields[2]):
	    continue
	if string.find(fields[3], "noauto") != -1: continue

        fsystem = fileSystemTypeGet(fields[2])
        label = None


	if fields[0] == "none":
            device = Device()
        elif len(fields) >= 6 and fields[0][:6] == "LABEL=":
            label = fields[0][6:]
            if labelToDevice.has_key(label):
                device = makeDevice(labelToDevice[label])
            else:
                log ("Warning: fstab file has LABEL=%s, but this label "
                     "could not be found on any filesystem", label)
                # bad luck, skip this entry.
                continue
	elif (fields[2] == "swap" and fields[0][:5] != "/dev/"):
	    # swap files
	    file = fields[0]

	    if file[:15] == "/initrd/loopfs/":
		file = file[14:]
                device = PiggybackSwapFileDevice("/mnt/loophost", file)
            else:
                device = SwapFileDevice(file)
        elif fields[0][:9] == "/dev/loop":
	    # look up this loop device in the index to find the
            # partition that houses the filesystem image
            # XXX currently we assume /dev/loop1
	    if loopIndex.has_key(device):
		(dev, fs) = loopIndex[device]
                device = LoopbackDevice(dev, fs)
	elif fields[0][:5] == "/dev/":
            device = makeDevice(fields[0][5:])
	else:
            continue
        
        entry = FileSystemSetEntry(device, fields[1], fsystem, fields[3],
                                   origfsystem=fsystem)
        if label:
            entry.setLabel(label)
        fsset.add(entry)
    return fsset

def isValidExt2(device):
    file = '/tmp/' + device
    isys.makeDevInode(device, file)
    try:
	fd = os.open(file, os.O_RDONLY)
    except:
	return 0

    buf = os.read(fd, 2048)
    os.close(fd)

    if len(buf) != 2048:
	return 0

    if struct.unpack("H", buf[1080:1082]) == (0xef53,):
	return 1

    return 0

def allocateLoopback(file):
    found = 1
    for i in range(8):
        dev = "loop%d" % (i,)
        path = "/tmp/loop%d" % (i,)
        isys.makeDevInode(dev, path)
        try:
            isys.losetup(path, file)
            found = 1
        except SystemError:
            continue
        break
    if found:
        return dev
    return None

_loopbackRootDevice = None
def mountLoopbackRoot(device, skipMount=0):
    global _loopbackRootDevice
    isys.mount(device, '/mnt/loophost', fstype = "vfat")
    _loopbackRootDevice = allocateLoopback("/mnt/loophost/redhat.img")
    if not skipMount:
        isys.mount(_loopbackRootDevice, '/mnt/sysimage')
    
def unmountLoopbackRoot(skipMount=0):
    global _loopbackRootDevice
    if not skipMount:
        isys.umount('/mnt/sysimage')
    path = '/tmp/' + _loopbackRootDevice
    isys.makeDevInode(_loopbackRootDevice, path)
    isys.unlosetup(path)
    isys.umount('/mnt/loophost')

def ext2FormatFilesystem(argList, messageFile, windowCreator, mntpoint):
    if windowCreator:
        w = windowCreator(_("Formatting"),
                          _("Formatting %s filesystem...") % (mntpoint,), 100)
    else:
        w = None

    fd = os.open(messageFile, os.O_RDWR | os.O_CREAT | os.O_APPEND)
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
        sys.exit(1)
			    
    os.close(p[1])

    # ignoring SIGCHLD would be cleaner then ignoring EINTR, but
    # we can't use signal() in this thread?

    s = 'a'
    while s and s != '\b':
        try:
            s = os.read(p[0], 1)
        except OSError, args:
            (num, str) = args
            if (num != 4):
                raise IOError, args

        os.write(fd, s)

    num = ''
    sync = 0
    while s:
        try:
            s = os.read(p[0], 1)
            os.write(fd, s)

            if s != '\b':
                try:
                    num = num + s
                except:
                    pass
            else:
                if num and len(num):
                    l = string.split(num, '/')
                    try:
                        val = (int(l[0]) * 100) / int(l[1])
                    except IndexError:
                        pass
                    except TypeError:
                        pass
                    else:
                        w and w.set(val)
                        # sync every 10%
                        if sync + 10 < val:
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

if __name__ == "__main__":
    log.open("foo")
    
    fsset = readFstab("fstab")

    print fsset.fstab()
    print fsset.rootOnLoop()
    
    sys.exit(0)
    fsset = FileSystemSet()
    proc = FileSystemSetEntry(Device(), '/proc', 'proc')
    fsset.add(proc)
    devpts = FileSystemSetEntry(Device(), '/dev/pts', 'devpts')
    fsset.add(devpts)

    device = LoopbackDevice("hda1", "vfat")
    mountpoint = FileSystemSetEntry (device, '/')
    fsset.add(mountpoint)

    device = SwapFileDevice("/SWAP")
    mountpoint = FileSystemSetEntry (device, "swap", "swap")
    fsset.add(mountpoint)
    
    print fsset.fstab()
