#
# fstab.py: filesystem management
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
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
import posix
import errno
import parted
import sys
import struct
import partitioning
import partedUtils
import raid
import lvm
import types

from rhpl.log import log
from rhpl.translate import _, N_

class BadBlocksError(Exception):
    pass

defaultMountPoints = ['/', '/home', '/tmp', '/usr', '/var', '/usr/local', '/opt']

if iutil.getArch() == "s390":
    # Many s390 have 2G DASDs, we recomment putting /usr/share on its own DASD
    defaultMountPoints.insert(4, '/usr/share')

if iutil.getArch() == "ia64":
    defaultMountPoints.insert(1, '/boot/efi')
else:
    defaultMountPoints.insert(1, '/boot')

fileSystemTypes = {}

# XXX define availraidlevels and defaultmntpts as arch characteristics
availRaidLevels = raid.getRaidLevels()

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

def getUsableLinuxFs():
    rc = []
    for fsType in fileSystemTypes.keys():
        if fileSystemTypes[fsType].isMountable() and \
               fileSystemTypes[fsType].isLinuxNativeFS():
            rc.append(fsType)

    # make sure the default is first in the list, kind of ugly
    default = fileSystemTypeGetDefault()
    defaultName = default.getName()
    if defaultName in rc:
        del rc[rc.index(defaultName)]
        rc.insert(0, defaultName)
    return rc

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

    def createLabel(self, mountpoint, maxLabelChars, kslabel = None):
        if self.labels == None:

            self.labels = {}
            diskset = partedUtils.DiskSet()            
            diskset.openDevices()
            diskset.stopAllRaid()
            diskset.startAllRaid()
            labels = diskset.getLabels()
            diskset.stopAllRaid()
            del diskset
            self.reserveLabels(labels)

        # If a label was specified in the kickstart file, return that as
        # the label - unless it's already in the reserved list.  If that's
        # the case, make a new one.
        if kslabel and kslabel not in self.labels:
           self.labels[kslabel] = 1
           return kslabel
        
        if len(mountpoint) > maxLabelChars:
            mountpoint = mountpoint[0:maxLabelChars]
        count = 0
        while self.labels.has_key(mountpoint):
            count = count + 1
            s = "%s" % count
            if (len(mountpoint) + len(s)) <= maxLabelChars:
                mountpoint = mountpoint + s
            else:
                strip = len(mountpoint) + len(s) - maxLabelChars
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
        self.maxSizeMB = 8 * 1024 * 1024
        self.supported = -1
        self.defaultOptions = "defaults"
        self.migratetofs = None
        self.extraFormatArgs = []
        self.maxLabelChars = 16
        self.packages = []

    def mount(self, device, mountpoint, readOnly=0, bindMount=0):
        if not self.isMountable():
            return
        iutil.mkdirChain(mountpoint)
        isys.mount(device, mountpoint, fstype = self.getName(), 
                   readOnly = readOnly, bindMount = bindMount)

    def umount(self, device, path):
        isys.umount(path, removeDir = 0)

    def getName(self):
        return self.name

    def getNeededPackages(self):
        return self.packages

    def registerDeviceArgumentFunction(self, klass, function):
        self.deviceArguments[klass] = function

    def badblocksDevice(self, entry, windowCreator, chroot='/'):
        if windowCreator:
            w = windowCreator(_("Checking for Bad Blocks"),
                              _("Checking for bad blocks on /dev/%s...")
                         % (entry.device.getDevice(),), 100)
        else:
            w = None
        
        devicePath = entry.device.setupDevice(chroot)
        args = [ "/usr/sbin/badblocks", "-vv", devicePath ]

        # entirely too much cutting and pasting from ext2FormatFileSystem
        fd = os.open("/dev/tty5", os.O_RDWR | os.O_CREAT | os.O_APPEND)
        p = os.pipe()
        childpid = os.fork()
        if not childpid:
            os.close(p[0])
            os.dup2(p[1], 1)
            os.dup2(p[1], 2)
            os.close(p[1])
            os.close(fd)
            os.execv(args[0], args)
            log("failed to exec %s", args)
            os._exit(1)

        os.close(p[1])

        s = 'a'
        while s and s != ':':
            try:
                s = os.read(p[0], 1)
            except OSError, args:
                (num, str) = args
                if (num != 4):
                    raise IOError, args

            os.write(fd, s)

        num = ''
	numbad = 0
        while s:
            try:
                s = os.read(p[0], 1)
                os.write(fd, s)

                if s not in ['\b', '\n']:
                    try:
                        num = num + s
                    except:
                        pass
                else:
		    if s == '\b':
			if num:
			    l = string.split(num, '/')
			    val = (long(l[0]) * 100) / long(l[1])
			    w and w.set(val)
		    else:
			try:
			    blocknum = long(num)
			    numbad = numbad + 1
			except:
			    pass

			if numbad > 0:
			    raise BadBlocksError
			    
		    num = ''
            except OSError, args:
                (num, str) = args
                if (num != 4):
                    raise IOError, args

        try:
            (pid, status) = os.waitpid(childpid, 0)
        except OSError, (num, msg):
            log("exception from waitpid in badblocks: %s %s" % (num, msg))
            status = None
        os.close(fd)

        w and w.pop()

	if numbad > 0:
	    raise BadBlocksError

        # have no clue how this would happen, but hope we're okay
        if status is None:
            return

        if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
            return

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
    def getMaxSizeMB(self):
        return self.maxSizeMB

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
                self.supported = -1
            else:
                self.supported = 0
            del f
        except:
            self.supported = 0
        self.name = "reiserfs"
        self.packages = [ "reiserfs-utils" ]

        self.maxSizeMB = 8 * 1024 * 1024


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

class xfsFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("xfs")
        self.formattable = 1
        self.checked = 1
        self.linuxnativefs = 1
        self.name = "xfs"
        self.maxSizeMB = 16 * 1024 * 1024
        self.maxLabelChars = 12
        # this is totally, 100% unsupported.  Boot with "linux xfs"
        # at the boot: prompt will let you make new xfs filesystems
        # in the installer.  Bugs filed when you use this will be closed
        # WONTFIX.
        try:
            f = open("/proc/cmdline")
            line = f.readline()
            if string.find(line, " xfs") != -1:
                self.supported = -1
            else:
                self.supported = 0
            del f
        except:
            self.supported = 0

        self.packages = [ "xfsprogs" ]
        
    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)
        
        rc = iutil.execWithRedirect("/usr/sbin/mkfs.xfs",
                                    ["mkfs.xfs", "-f", "-l", "internal",
                                     devicePath ],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")
        
        if rc:
            raise SystemError
        
    def labelDevice(self, entry, chroot):
        devicePath = entry.device.setupDevice(chroot)
        label = labelFactory.createLabel(entry.mountpoint, self.maxLabelChars,
                                         kslabel = entry.label)
        db_cmd = "label " + label
        rc = iutil.execWithRedirect("/usr/sbin/xfs_db",
                                    ["xfs_db", "-x", "-c", db_cmd,
                                     devicePath],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")
        if rc:
            raise SystemError
        entry.setLabel(label)
        
fileSystemTypeRegister(xfsFileSystem())

class jfsFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("jfs")
        self.formattable = 1
        self.checked = 1
        self.linuxnativefs = 1
        self.maxLabelChars = 16
        # this is totally, 100% unsupported.  Boot with "linux jfs"
        # at the boot: prompt will let you make new reiserfs filesystems
        # in the installer.  Bugs filed when you use this will be closed
        # WONTFIX.
        try:
            f = open("/proc/cmdline")
            line = f.readline()
            if string.find(line, " jfs") != -1:
                self.supported = -1
            else:
                self.supported = 0
            del f
        except:
            self.supported = 0

        if not os.access("/usr/sbin/mkfs.jfs", os.X_OK):
            self.supported = 0
            
        self.name = "jfs"
        self.packages = [ "jfsutils" ]

        self.maxSizeMB = 8 * 1024 * 1024

    def labelDevice(self, entry, chroot):
        devicePath = entry.device.setupDevice(chroot)
	label = labelFactory.createLabel(entry.mountpoint, self.maxLabelChars,
                                         kslabel = entry.label)
	rc = iutil.execWithRedirect("/usr/sbin/jfs_tune",
	                            ["jfs_tune", "-L", label, devicePath],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")
        if rc:
            raise SystemError
        entry.setLabel(label)

    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)

        rc = iutil.execWithRedirect("/usr/sbin/mkfs.jfs",
                                    ["mkfs.jfs", "-q",
                                     devicePath ],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")
        
        if rc:
            raise SystemError
                                  
fileSystemTypeRegister(jfsFileSystem())

class extFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = None
        self.formattable = 1
        self.checked = 1
        self.linuxnativefs = 1
        self.maxSizeMB = 8 * 1024 * 1024
        self.packages = [ "e2fsprogs" ]

    def labelDevice(self, entry, chroot):
        devicePath = entry.device.setupDevice(chroot)
        label = labelFactory.createLabel(entry.mountpoint, self.maxLabelChars,
                                         kslabel = entry.label)
        rc = iutil.execWithRedirect("/usr/sbin/e2label",
                                    ["e2label", devicePath, label],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")
        if rc:
            raise SystemError
        entry.setLabel(label)
        
    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)
        devArgs = self.getDeviceArgs(entry.device)
        args = [ "/usr/sbin/mke2fs", devicePath]

        args.extend(devArgs)
        args.extend(self.extraFormatArgs)

        rc = ext2FormatFilesystem(args, "/dev/tty5",
                                  progress,
                                  entry.mountpoint)
        if rc:
            raise SystemError

    # this is only for ext3 filesystems, but migration is a method
    # of the ext2 fstype, so it needs to be here.  FIXME should be moved
    def setExt3Options(self, entry, message, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)

        # if no journal, don't turn off the fsck
        if not isys.ext2HasJournal(devicePath, makeDevNode = 0):
            return

        rc = iutil.execWithRedirect("/usr/sbin/tune2fs",
                                    ["tunefs", "-c0", "-i0", "-Odir_index",
                                     devicePath],
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
                                    ["tune2fs", "-j", devicePath ],
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
                          "file system if desired.\n\n"
                          "Would you like to continue without migrating %s?")
                             % (devicePath, devicePath), type = "yesno")
                if rc == 0:
                    sys.exit(0)
            entry.fsystem = entry.origfsystem
        else:
            extFileSystem.setExt3Options(self, entry, message, chroot)


fileSystemTypeRegister(ext2FileSystem())

class ext3FileSystem(extFileSystem):
    def __init__(self):
        extFileSystem.__init__(self)
        self.name = "ext3"
        self.extraFormatArgs = [ "-j" ]
        self.partedFileSystemType = parted.file_system_type_get("ext3")

    def formatDevice(self, entry, progress, chroot='/'):
        extFileSystem.formatDevice(self, entry, progress, chroot)
        extFileSystem.setExt3Options(self, entry, progress, chroot)

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
        self.maxSizeMB = 8 * 1024 * 1024
        self.supported = 1

        if len(availRaidLevels) == 0:
            self.supported = 0

        self.packages = [ "mdadm" ]

    def formatDevice(self, entry, progress, chroot='/'):
        # mkraid did all we need to format this partition...
        pass
    
fileSystemTypeRegister(raidMemberDummyFileSystem())

class lvmPhysicalVolumeDummyFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("ext2")
        self.partedPartitionFlags = [ parted.PARTITION_LVM ]
        self.formattable = 1
        self.checked = 0
        self.linuxnativefs = 1
        self.name = "physical volume (LVM)"
        self.maxSizeMB = 8 * 1024 * 1024
        self.supported = 1
        self.packages = [ "lvm2" ]

    def isMountable(self):
        return 0
    
    def formatDevice(self, entry, progress, chroot='/'):
        # already done by the pvcreate during volume creation
        pass

fileSystemTypeRegister(lvmPhysicalVolumeDummyFileSystem())

class lvmVolumeGroupDummyFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("ext2")
        self.formattable = 1
        self.checked = 0
        self.linuxnativefs = 0
        self.name = "volume group (LVM)"
        self.supported = 0
        self.maxSizeMB = 8 * 1024 * 1024
        self.packages = [ "lvm2" ]

    def isMountable(self):
        return 0

    def formatDevice(self, entry, progress, chroot='/'):
        # the vgcreate already did this
        pass

fileSystemTypeRegister(lvmVolumeGroupDummyFileSystem())

class swapFileSystem(FileSystemType):
    enabledSwaps = {}
    
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("linux-swap")
        self.formattable = 1
        self.name = "swap"
        self.maxSizeMB = 8 * 1024 * 1024
        self.linuxnativefs = 1
        self.supported = 1
        

    def mount(self, device, mountpoint, readOnly=0, bindMount=0):
        pagesize = isys.getpagesize()
        buf = None
        if pagesize > 2048:
            num = pagesize
        else:
            num = 2048
        try:
            fd = os.open(dev, os.O_RDONLY)
            buf = os.read(fd, num)
            os.close(fd)
        except:
            pass

        # FIXME: we should ask if they want to reinitialize swaps that
        # are of format 0 (#122101)
        if buf is not None and len(buf) == pagesize:
            if buf[pagesize - 10:] == "SWAP-SPACE":
                log("SWAP is of format 0, skipping it")
                return
        
        isys.swapon (device)

    def umount(self, device, path):
        # unfortunately, turning off swap is bad.
        raise RuntimeError, "unable to turn off swap"
    
    def formatDevice(self, entry, progress, chroot='/'):
        file = entry.device.setupDevice(chroot)
        rc = iutil.execWithRedirect ("/usr/sbin/mkswap",
                                     [ "mkswap", '-v1', file ],
                                     stdout = "/dev/tty5",
                                     stderr = "/dev/tty5",
                                     searchPath = 1)
        if rc:
            raise SystemError

    def labelDevice(self, entry, chroot):
        file = entry.device.setupDevice(chroot)
        devName = entry.device.getDevice()
        # we'll keep the SWAP-* naming for all devs but Compaq SMART2
        # nodes (#170500)
        if devName[0:6] == "cciss/":
            swapLabel = "SW-%s" % (devName)
        else:
            swapLabel = "SWAP-%s" % (devName)
        label = labelFactory.createLabel("%s" %swapLabel, self.maxLabelChars)
        rc = iutil.execWithRedirect ("/usr/sbin/mkswap",
                                     [ "mkswap", '-v1', "-L", label, file ],
                                     stdout = "/dev/tty5",
                                     stderr = "/dev/tty5",
                                     searchPath = 1)
        if rc:
            raise SystemError
        entry.setLabel(label)

fileSystemTypeRegister(swapFileSystem())

class FATFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("fat32")
        self.formattable = 1
        self.supported = 1
        self.checked = 0
        self.maxSizeMB = 1024 * 1024
        self.name = "vfat"
        self.packages = [ "dosfstools" ]
        self.maxLabelChars = 11
        self.migratetofs = ['vfat']

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

    def labelDevice(self, entry, chroot):
        if not iutil.getArch() == 'ia64':
            return
        devicePath = entry.device.setupDevice(chroot)
        label = labelFactory.createLabel(entry.mountpoint, self.maxLabelChars,
                                         kslabel = entry.label)

        rc = iutil.execWithRedirect("/usr/sbin/dosfslabel",
                                    ["dosfslabel", devicePath, label],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5",
                                    searchPath = 1)
        newLabel = iutil.execWithCapture("/usr/sbin/dosfslabel",
                                         ["dosfslabel", devicePath],
                                         stderr = "/dev/tty5")
        newLabel = newLabel.strip()
        if label != newLabel:
            raise SystemError, "dosfslabel failed on device %s" % (devicePath,)
        entry.setLabel(label)

    def _readFstab(self, path):
        f = open (path, "r")
        lines = f.readlines ()
        f.close()

        fstab = []
        for line in lines:
            fields = string.split(line)
        
            if not fields:
                fstab.append(line)
                continue
        
            if line[0] == "#":
                fstab.append(line)
                # skip all comments
                continue
        
            # all valid fstab entries have 6 fields; if the last two are
            # missing they are assumed to be zero per fstab(5)
            if len(fields) < 4:
                fstab.append(line)
                continue
            elif len(fields) == 4:
                fields.append(0)
                fields.append(0)            
            elif len(fields) == 5:
                fields.append(0)                        
            elif len(fields) > 6:
                fstab.append(line)
                continue
            fstab.append(fields)

        return fstab

    def migrateFileSystem(self, entry, message, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)

        if not entry.fsystem or not entry.origfsystem:
            raise RuntimeError, ("Trying to migrate fs w/o fsystem or "
                                 "origfsystem set")
        if entry.fsystem.getName() != "vfat":
            raise RuntimeError, ("Trying to migrate vfat to something other "
                                 "than vfat")

        self.labelDevice(entry, chroot)

        if not entry.label:
            return

        try:
            os.stat(chroot + "/etc/fstab")
        except:
            return
        mounts = self._readFstab(chroot + "/etc/fstab")

        changed = False
        for mount in mounts:
            if type(mount) == types.ListType:
                if mount[0] == "/dev/%s" % (entry.device.getDevice(),):
                    mount[0] = "LABEL=%s" % (entry.label,)
                    changed = True

        if changed:
            os.rename(chroot + "/etc/fstab", chroot + "/etc/fstab.anaconda")
            f = open (chroot + "/etc/fstab", "w")
            for mount in mounts:
                if type(mount) == types.ListType:
                    mount = string.join(mount, "\t")
                if mount[:-1] != "\n":
                    mount += "\n"
                f.write(mount)
            f.close()

        
fileSystemTypeRegister(FATFileSystem())

class NTFSFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("ntfs")
        self.formattable = 0
        self.checked = 0
        self.name = "ntfs"

fileSystemTypeRegister(NTFSFileSystem())

class hfsFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("hfs")
        self.formattable = 1
        self.checked = 0
        self.name = "hfs"
        self.supported = 0

    def isMountable(self):
        return 0

    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)
        devArgs = self.getDeviceArgs(entry.device)
        args = [ "hformat", devicePath ]
        args.extend(devArgs)
        
        rc = iutil.execWithRedirect("/usr/bin/hformat", args,
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")
        if rc:
            raise SystemError

fileSystemTypeRegister(hfsFileSystem())

class applebootstrapFileSystem(hfsFileSystem):
    def __init__(self):
        hfsFileSystem.__init__(self)
        self.partedPartitionFlags = [ parted.PARTITION_BOOT ]
        self.maxSizeMB = 1
        self.name = "Apple Bootstrap"
        if iutil.getPPCMacGen() == "NewWorld":
            self.supported = 1
        else:
            self.supported = 0

fileSystemTypeRegister(applebootstrapFileSystem())

class prepbootFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = None
        self.partedPartitionFlags = [ parted.PARTITION_BOOT ]
        self.checked = 0
        self.name = "PPC PReP Boot"
        self.maxSizeMB = 10

        if iutil.getPPCMachine() == "iSeries":
            self.maxSizeMB = 64

        # supported for use on the pseries
        if (iutil.getPPCMachine() == "pSeries" or
            iutil.getPPCMachine() == "iSeries"):
            self.supported = 1
            self.formattable = 1
        else:
            self.supported = 0
            self.formattable = 0

    def formatDevice(self, entry, progress, chroot='/'):
        # copy and paste job from booty/bootloaderInfo.py...
        def getDiskPart(dev):
            cut = len(dev)
            if (dev.startswith('rd/') or dev.startswith('ida/') or
                dev.startswith('cciss/') or dev.startswith('i2o/')
                or dev.startswith("sx8/")):
                if dev[-2] == 'p':
                    cut = -1
                elif dev[-3] == 'p':
                    cut = -2
            else:
                if dev[-2] in string.digits:
                    cut = -2
                elif dev[-1] in string.digits:
                    cut = -1

            name = dev[:cut]

            # hack off the trailing 'p' from /dev/cciss/*, for example
            if name[-1] == 'p':
                for letter in name:
                    if letter not in string.letters and letter != "/":
                        name = name[:-1]
                        break

            if cut < 0:
                partNum = int(dev[cut:])
            else:
                partNum = None

            return (name, partNum)
        
        # FIXME: oh dear is this a hack beyond my wildest imagination.
        # parted doesn't really know how to do these, so we're going to
        # exec sfdisk and make it set the partition type.  this is bloody
        # ugly
        devicePath = entry.device.setupDevice(chroot)
        (disk, part) = getDiskPart(devicePath)
        if disk is None or part is None:
            log("oops, somehow got a bogus device for the PReP partition "
                "(%s)" %(devicePath,))
            return

        args = [ "sfdisk", "--change-id", disk, "%d" %(part,), "41" ]
        if disk.startswith("/tmp/") and not os.access(disk, os.R_OK):
            isys.makeDevInode(disk[5:], disk)
        
        log("going to run %s" %(args,))
        rc = iutil.execWithRedirect("/usr/sbin/sfdisk", args,
                                    stdout = "/dev/tty5", stderr = "/dev/tty5")
        if rc:
            raise SystemError

fileSystemTypeRegister(prepbootFileSystem())

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

class SysfsFileSystem(PsudoFileSystem):
    def __init__(self):
        PsudoFileSystem.__init__(self, "sysfs")

fileSystemTypeRegister(SysfsFileSystem())

class SelinuxfsFileSystem(PsudoFileSystem):
    def __init__(self):
        PsudoFileSystem.__init__(self, "selinuxfs")

fileSystemTypeRegister(SelinuxfsFileSystem())

class DevptsFileSystem(PsudoFileSystem):
    def __init__(self):
        PsudoFileSystem.__init__(self, "devpts")
        self.defaultOptions = "gid=5,mode=620"

    def isMountable(self):
        return 0

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

class BindFileSystem(AutoFileSystem):
    def __init__(self):
        PsudoFileSystem.__init__(self, "bind")

    def isMountable(self):
        return 1
        
fileSystemTypeRegister(BindFileSystem())        

class FileSystemSet:
    def __init__(self):
        self.messageWindow = None
        self.progressWindow = None
        self.waitWindow = None
        self.mountcount = 0
        self.migratedfs = 0
        self.reset()
        self.volumesCreated = 0

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
        sys = FileSystemSetEntry(Device(), '/sys', fileSystemTypeGet("sysfs"))
        self.add(sys)
        pts = FileSystemSetEntry(Device(), '/dev/pts',
                                 fileSystemTypeGet("devpts"), "gid=5,mode=620")
        self.add(pts)
        shm = FileSystemSetEntry(Device(), '/dev/shm', fileSystemTypeGet("tmpfs"))
        self.add(shm)

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

    def mtab (self):
        format = "%s %s %s %s 0 0\n"
        mtab = ""
        for entry in self.entries:
            if not entry.isMounted():
                continue
            if entry.mountpoint:
                # swap doesn't end up in the mtab
                if entry.fsystem.getName() == "swap":
                    continue
                if entry.options:
                    options = "rw," + entry.options
                else:
                    options = "rw"
                mtab = mtab + format % (devify(entry.device.getDevice()),
                                        entry.mountpoint,
                                        entry.fsystem.getName(),
                                        options)
        return mtab

    def raidtab(self):
        # set up raidtab...
        raidtab = ""
        for entry in self.entries:
            if entry.device.getName() == "RAIDDevice":
                raidtab = raidtab + entry.device.raidTab()

        return raidtab

    def mdadmConf(self):
        """Make the mdadm.conf file with mdadm command.

        This creates a conf file with active arrays.  In other words
        the arrays that we don't want included must be inactive.
        """
        activeArrays = iutil.execWithCapture("mdadm",
                                             ["--misc", "--detail", "--scan"],
                                             searchPath = 1)
        if len(activeArrays) == 0:
            return
        cf = """
# mdadm.conf written out by anaconda
DEVICE partitions
MAILADDR root
%s
""" % activeArrays
        return cf

    def write (self, prefix):
        f = open (prefix + "/etc/fstab", "w")
        f.write (self.fstab())
        f.close ()

        cf = self.mdadmConf()

        if cf:
            f = open (prefix + "/etc/mdadm.conf", "w")
            f.write (cf)
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
        
    # return the "boot" device
    def getBootDev(self):
	mntDict = {}
        bootDev = None
        for entry in self.entries:
	    mntDict[entry.mountpoint] = entry.device

        # FIXME: this ppc stuff feels kind of crufty -- the abstraction
        # here needs a little bit of work
        if iutil.getPPCMacGen() == "NewWorld":
            for entry in self.entries:
                if entry.fsystem.getName() == "Apple Bootstrap":
                    bootDev = entry.device
        elif (iutil.getPPCMachine() == "pSeries" or
              iutil.getPPCMachine() == "iSeries"):
            # we want the first prep partition or the first newly formatted one
            bestprep = None
            for entry in self.entries:
                if ((entry.fsystem.getName() == "PPC PReP Boot")
                    and ((bestprep is None) or
                         ((bestprep.format == 0) and (entry.format == 1)))):
                    bestprep = entry
            if bestprep:
                bootDev = bestprep.device
        elif iutil.getArch() == "ia64":
            if mntDict.has_key("/boot/efi"):
                bootDev = mntDict['/boot/efi']
	elif mntDict.has_key("/boot"):
	    bootDev = mntDict['/boot']
	else:
	    bootDev = mntDict['/']
            
        return bootDev

    def bootloaderChoices(self, diskSet, bl):
        ret = {}
        bootDev = self.getBootDev()

        if bootDev is None:
            log("no boot device set")
            return ret

	if bootDev.getName() == "RAIDDevice":
            ret['boot'] = (bootDev.device, N_("RAID Device"))
            return ret

        if iutil.getPPCMacGen() == "NewWorld":
            ret['boot'] = (bootDev.device, N_("Apple Bootstrap"))
            n = 1
            for entry in self.entries:
                if ((entry.fsystem.getName() == "Apple Bootstrap") and (
                    entry.device.getDevice() != bootDev.device)):
                    ret['boot%d' %(n,)] = (entry.device.getDevice(),
                                           N_("Apple Bootstrap"))
                    n = n + 1
            return ret
        elif (iutil.getPPCMachine() == "pSeries" or
              iutil.getPPCMachine() == "iSeries"):
            ret['boot'] = (bootDev.device, N_("PPC PReP Boot"))
            return ret
                
	ret['boot'] = (bootDev.device, N_("First sector of boot partition"))
        try:
            # we won't have this on zFCP-only zSeries systems
            ret['mbr'] = (bl.drivelist[0], N_("Master Boot Record (MBR)"))
        except:
            pass
        return ret

    # set active partition on disks
    # if an active partition is set, leave it alone; if none set
    # set either our boot partition or the first partition on the drive active
    def setActive(self, diskset):
        dev = self.getBootDev()

        if dev is None:
            return
        
        bootDev = dev.device

        # on ia64, *only* /boot/efi should be marked bootable
        # similarly, on pseries, we really only want the PReP partition active
        if (iutil.getArch() == "ia64" or iutil.getPPCMachine() == "pSeries"
            or iutil.getPPCMachine() == "iSeries"):
            part = partedUtils.get_partition_by_name(diskset.disks, bootDev)
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

                if partedUtils.get_partition_name(part) == bootDev:
                    bootPart = part
                
                part = disk.next_partition(part)

            if bootPart and not foundActive:
                bootPart.set_flag(parted.PARTITION_BOOT, 1)

            if bootPart:
                del bootPart

    def formatSwap (self, chroot):
        formatted = []
        notformatted = []
        
        for entry in self.entries:
            if (not entry.fsystem or not entry.fsystem.getName() == "swap" or
                entry.isMounted()):
                continue
            if not entry.getFormat():
                notformatted.append(entry)
                continue
            try:
                self.formatEntry(entry, chroot)
                formatted.append(entry)
            except SystemError:
                if self.messageWindow:
                    self.messageWindow(_("Error"),
                                       _("An error occurred trying to "
                                         "initialize swap on device %s.  This "
                                         "problem is serious, and the install "
                                         "cannot continue.\n\n"
                                         "Press <Enter> to reboot your system.")
                                       % (entry.device.getDevice(),))
                sys.exit(0)

        for entry in formatted:
            try:
                self.labelEntry(entry, chroot)
            except SystemError:
                # should be OK, fall back to by device
                pass

        # find if there's a label on the ones we're not formatting
        for entry in notformatted:
            dev = entry.device.getDevice()
            if not dev or dev == "none":
                continue
            try:
                label = isys.readFSLabel(dev)
            except:
                continue
            if label:
                entry.setLabel(label)
                
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
        label = entry.device.getLabel()
        if label:
            entry.setLabel(label)
        elif entry.device.doLabel is not None:
            entry.fsystem.labelDevice(entry, chroot)
    
    def formatEntry(self, entry, chroot):
        log("formatting %s as %s" %(entry.mountpoint, entry.fsystem.name))
        entry.fsystem.formatDevice(entry, self.progressWindow, chroot)

    def badblocksEntry(self, entry, chroot):
        entry.fsystem.badblocksDevice(entry, self.progressWindow, chroot)
        
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
	    except BadBlocksError:
		    log("Bad blocks detected on device %s",entry.device.getDevice())
		    if self.messageWindow:
			self.messageWindow(_("Error"),
					   _("Bad blocks have been detected on "
					     "device /dev/%s. We do "
					     "not recommend you use this device."
					     "\n\n"
					     "Press <Enter> to reboot your system") %
					   (entry.device.getDevice(),))
		    sys.exit(0)
		
            except SystemError:
                if self.messageWindow:
                    self.messageWindow(_("Error"),
                                       _("An error occurred searching for "
                                         "bad blocks on %s.  This problem is "
                                         "serious, and the install cannot "
                                         "continue.\n\n"
                                         "Press <Enter> to reboot your system.")
                                       % (entry.device.getDevice(),))
                sys.exit(0)

    def createLogicalVolumes (self, chroot='/'):
        # first set up the volume groups
        for entry in self.entries:
            if entry.fsystem.name == "volume group (LVM)":
                entry.device.setupDevice(chroot)

        # then set up the logical volumes
        for entry in self.entries:
            if isinstance(entry.device, LogicalVolumeDevice):
                entry.device.setupDevice(chroot)
        self.volumesCreated = 1


    def makeFilesystems (self, chroot='/'):
        formatted = []
        notformatted = []
        for entry in self.entries:
            if (not entry.fsystem.isFormattable() or not entry.getFormat()
                or entry.isMounted()):
                notformatted.append(entry)
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
                                         "Press <Enter> to reboot your system.")
                                       % (entry.device.getDevice(),))
                sys.exit(0)

        for entry in formatted:
            try:
                self.labelEntry(entry, chroot)
            except SystemError:
                # should be OK, we'll still use the device name to mount.
                pass

        # go through and have labels for the ones we don't format
        for entry in notformatted:
            dev = entry.device.getDevice()
            if not dev or dev == "none":
                continue
            if not entry.mountpoint or entry.mountpoint == "swap":
                continue
            try:
                label = isys.readFSLabel(dev)
            except:
                continue
            if label:
                entry.setLabel(label)
            else:
                self.labelEntry(entry, chroot)

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
                                         "Press <Enter> to reboot your system.")
                                       % (entry.device.getDevice(),))
                sys.exit(0)

        self.migratedfs = 1

    def mountFilesystems(self, instPath = '/', raiseErrors = 0, readOnly = 0):
	for entry in self.entries:
            if not entry.fsystem.isMountable():
		continue
            try:
                log("trying to mount %s on %s" %(entry.device.getDevice(), entry.mountpoint))
                entry.mount(instPath, readOnly = readOnly)
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
                                             "Press <Enter> to reboot your "
                                             "system.") % (entry.mountpoint,))
                    else:
                        self.messageWindow(_("Invalid mount point"),
                                           _("An error occurred when trying "
                                             "to create %s: %s.  This is "
                                             "a fatal error and the install "
                                             "cannot continue.\n\n"
                                             "Press <Enter> to reboot your "
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

        self.makeLVMNodes(instPath)

    def makeLVMNodes(self, instPath, trylvm1 = 0):
        # XXX hack to make the device node exist for the root fs if
        # it's a logical volume so that mkinitrd can create the initrd.
        root = self.getEntryByMountPoint("/")

        rootlvm1 = 0
        if trylvm1:
            dev = root.device.getDevice()
            # lvm1 major is 58
            if os.access("%s/dev/%s" %(instPath, dev), os.R_OK) and posix.major(os.stat("%s/dev/%s" %(instPath, dev)).st_rdev) == 58:
                rootlvm1 = 1
        
        if isinstance(root.device, LogicalVolumeDevice) or rootlvm1:
            # now make sure all of the device nodes exist.  *sigh*
            rc = iutil.execWithRedirect("lvm",
                                        ["lvm", "vgmknodes", "-v"],
                                        stdout = "/tmp/lvmout",
                                        stderr = "/tmp/lvmout",
                                        searchPath = 1)
            
            rootDev = "/dev/%s" % (root.device.getDevice(),)
            rootdir = instPath + rootDev[:string.rfind(rootDev, "/")]
            if not os.path.exists(instPath + "/dev/mapper/control"):
                iutil.makeDMNode(root=instPath)
            if not os.path.isdir(rootdir):
                os.makedirs(rootdir)
            dmdev = "/dev/mapper/" + root.device.getDevice().replace("/", "-")
            if os.path.exists(instPath + dmdev):
                os.unlink(instPath + dmdev)
            iutil.copyDeviceNode(dmdev, instPath + dmdev)
            # unlink existing so that we dtrt on upgrades
            if os.path.exists(instPath + rootDev):
                os.unlink(instPath + rootDev)
            os.symlink(dmdev, instPath + rootDev)
            if not os.path.isdir("%s/etc/lvm" %(instPath,)):
                os.makedirs("%s/etc/lvm" %(instPath,))

    def filesystemSpace(self, chroot='/'):
	space = []
        for entry in self.entries:
            if not entry.isMounted():
                continue
            # we can't put swap files on swap partitions; that's nonsense
            if entry.mountpoint == "swap":
                continue
            path = "%s/%s" % (chroot, entry.mountpoint)
            try:
                space.append((entry.mountpoint, isys.fsSpaceAvailable(path)))
            except SystemError:
                log("failed to get space available in filesystemSpace() for %s" %(entry.mountpoint,))

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

    def hasDirtyFilesystems(self, mountpoint):
        ret = []

	for entry in self.entries:
            # XXX - multifsify, virtualize isdirty per fstype
	    if entry.fsystem.getName() != "ext2": continue
	    if entry.getFormat(): continue
            if isinstance(entry.device.getDevice(), BindMountDevice): continue

            try:
                if isys.ext2IsDirty(entry.device.getDevice()):
                    log("%s is a dirty ext2 partition" % entry.device.getDevice())
                    ret.append(entry.device.getDevice())
            except Exception, e:
                log("got an exception checking %s for being dirty, hoping it's not" %(entry.device.getDevice(),))

	return ret

    def umountFilesystems(self, instPath, ignoreErrors = 0):
        # XXX remove special case
        try:
            isys.umount(instPath + '/proc/bus/usb', removeDir = 0)
            log("Umount USB OK")
        except:
#           log("Umount USB Fail")
            pass

        # take a slice so we don't modify self.entries
        reverse = self.entries[:]
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

    def mount(self, chroot='/', devPrefix='/tmp', readOnly = 0):
        device = self.device.setupDevice(chroot, devPrefix=devPrefix)

        # FIXME: we really should migrate before turnOnFilesystems.
        # but it's too late now
        if (self.migrate == 1) and (self.origfsystem is not None):
            self.origfsystem.mount(device, "%s/%s" % (chroot, self.mountpoint),
                                   readOnly = readOnly,
                                   bindMount = isinstance(self.device,
                                                          BindMountDevice))
        else:
            self.fsystem.mount(device, "%s/%s" % (chroot, self.mountpoint),
                               readOnly = readOnly,
                               bindMount = isinstance(self.device,
                                                      BindMountDevice))

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

    def getMountPoint(self):
	return self.mountpoint
        
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

    def __str__(self):
        if not self.mountpoint:
            mntpt = "None"
        else:
            mntpt = self.mountpoint
            
        str = ("fsentry -- device: %(device)s   mountpoint: %(mountpoint)s\n"
               "           fsystem: %(fsystem)s format: %(format)s\n"
               "           ismounted: %(mounted)s \n"%
               {"device": self.device.getDevice(), "mountpoint": mntpt,
                "fsystem": self.fsystem.getName(), "format": self.format,
                "mounted": self.mountcount})
        return str
        

class Device:
    def __init__(self):
        self.device = "none"
        self.fsoptions = {}
        self.label = None
        self.isSetup = 0
        self.doLabel = 1

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

    def getLabel(self):
        try:
            return isys.readFSLabel(self.setupDevice(), makeDevNode = 0)
        except:
            return ""

class DevDevice(Device):
    """Device with a device node rooted in /dev that we just always use
       the pre-created device node for."""
    def __init__(self, dev):
        Device.__init__(self)
        self.device = dev

    def getDevice(self, asBoot = 0):
        return self.device

    def setupDevice(self, chroot='/', devPrefix='/dev'):
        return "/dev/%s" %(self.getDevice(),)

class RAIDDevice(Device):
    # XXX usedMajors does not take in account any EXISTING md device
    #     on the system for installs.  We need to examine all partitions
    #     to investigate which minors are really available.
    usedMajors = {}

    # members is a list of Device based instances that will be
    # a part of this raid device
    def __init__(self, level, members, minor=-1, spares=0, existing=0,
                 chunksize = 64):
        Device.__init__(self)
        self.level = level
        self.members = members
        self.spares = spares
        self.numDisks = len(members) - spares
        self.isSetup = existing
        self.doLabel = None
        if chunksize is not None:
            self.chunksize = chunksize
        else:
            self.chunksize = 256

        if len(members) < spares:
            raise RuntimeError, ("you requiested more spare devices "
                                 "than online devices!")

        if level == 5:
            if self.numDisks < 3:
                raise RuntimeError, "RAID 5 requires at least 3 online members"
        
        # there are 32 major md devices, 0...31
        if minor == -1 or minor is None:
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

    def mdadmLine (self, devPrefix="/dev"):
        return "ARRAY %s/%s super-minor=%s\n" %(devPrefix, self.device,
                                               self.minor)

    def raidTab (self, devPrefix='/dev'):
        entry = ""
        entry = entry + "raiddev		    %s/%s\n" % (devPrefix,
                                                                self.device,)
        entry = entry + "raid-level		    %d\n" % (self.level,)
        entry = entry + "nr-raid-disks		    %d\n" % (self.numDisks,)
        entry = entry + "chunk-size		    %s\n" %(self.chunksize,)
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

    def setupDevice (self, chroot="/", devPrefix='/dev'):
        def devify(x):
            return "/dev/%s" %(x,)
        
        node = "%s/%s" % (devPrefix, self.device)
        isys.makeDevInode(self.device, node)

        if not self.isSetup:
            for device in self.members:
                PartitionDevice(device).setupDevice(chroot,
                                                    devPrefix=devPrefix)

            args = ["/usr/sbin/mdadm", "--create", "/dev/%s" %(self.device,),
                    "--run", "--chunk=%s" %(self.chunksize,),
                    "--level=%s" %(self.level,),
                    "--raid-devices=%s" %(self.numDisks,)]

            if self.spares > 0:
                args.append("--spare-devices=%s" %(self.spares,),)
            
            args.extend(map(devify, self.members))
            log("going to run: %s" %(args,))
            iutil.execWithRedirect (args[0], args,
                                    stderr="/dev/tty5", stdout="/dev/tty5")
            raid.register_raid_device(self.device, self.members[:],
                                      self.level, self.numDisks)
            self.isSetup = 1
        else:
            isys.raidstart(self.device, self.members[0])
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

class VolumeGroupDevice(Device):
    def __init__(self, name, physvols, pesize = 32768, existing = 0):
        """Creates a VolumeGroupDevice.

        name is the name of the volume group
        physvols is a list of Device objects which are the physical volumes
        pesize is the size of physical extents in kilobytes
        existing is whether this vg previously existed.
        """

        Device.__init__(self)
        self.physicalVolumes = physvols
        self.isSetup = existing
        self.name = name
        self.device = name
        self.isSetup = existing

        self.physicalextentsize = pesize

    def setupDevice (self, chroot="/", devPrefix='/tmp'):
        nodes = []
        for volume in self.physicalVolumes:
            # XXX the lvm tools are broken and will only work for /dev
            node = volume.setupDevice(chroot, devPrefix="/dev")

            # XXX I should check if the pv is set up somehow so that we
            # can have preexisting vgs and add new pvs to them.
            if not self.isSetup:
                # now make the device into a real physical volume
                # XXX I don't really belong here.   should
                # there be a PhysicalVolumeDevice(PartitionDevice) ?
                lvm.writeForceConf()
                rc = iutil.execWithRedirect("lvm",
                                            ["lvm", "pvcreate", "-ff", "-y",
                                             "-v", node],
                                            stdout = "/tmp/lvmout",
                                            stderr = "/tmp/lvmout",
                                            searchPath = 1)
                if rc:
                    raise SystemError, "pvcreate failed for %s" % (volume,)
                lvm.unlinkConf()

                lvm.wipeOtherMetadataFromPV(node)

                nodes.append(node)

        if not self.isSetup:
            # rescan now that we've recreated pvs.  ugh.
            lvm.writeForceConf()            
            lvm.vgscan()

            for (vg, lv, size) in lvm.lvlist():
                if vg == self.name:
                    log("removing obsolete LV %s/%s" % (vg, lv))
                    try:
                        lvm.lvremove(lv, vg)
                    except SystemError:
                        pass

            for (vg, size, pesize) in lvm.vglist():
                if vg == self.name:
                    log("removing obsolete VG %s" % (vg,))
                    try:
                        lvm.vgremove(self.name)
                    except SystemError:
                        pass

            # rescan now that we've tried to nuke obsolete vgs.  woo.
            lvm.writeForceConf()
            lvm.vgscan()

            args = [ "lvm", "vgcreate", "-v", "-An",
                     "-s", "%sk" %(self.physicalextentsize,),
                     self.name ]
            args.extend(nodes)
            rc = iutil.execWithRedirect(args[0], args,
                                        stdout = "/tmp/lvmout",
                                        stderr = "/tmp/lvmout",
                                        searchPath = 1)

            if rc:
                raise SystemError, "vgcreate failed for %s" %(self.name,)

            lvm.unlinkConf()
            self.isSetup = 1
        else:
            lvm.vgscan()
            lvm.vgactivate()
            
        return "/dev/%s" % (self.name,)

    def solidify(self):
        return

class LogicalVolumeDevice(Device):
    # note that size is in megabytes!
    def __init__(self, volumegroup, size, vgname, existing = 0):
        Device.__init__(self)
        self.volumeGroup = volumegroup
        self.size = size
        self.name = vgname
        self.isSetup = 0
        self.isSetup = existing
        self.doLabel = None

        # these are attributes we might want to expose.  or maybe not.
        # self.chunksize
        # self.stripes
        # self.stripesize
        # self.extents
        # self.readaheadsectors

    def setupDevice(self, chroot="/", devPrefix='/tmp'):
        if not self.isSetup:
            lvm.writeForceConf()
            rc = iutil.execWithRedirect("lvm",
                                        ["lvm", "lvcreate", "-L",
                                         "%dM" % (self.size,),
                                         "-n", self.name, "-An",
                                         self.volumeGroup],
                                        stdout = "/tmp/lvmout",
                                        stderr = "/tmp/lvmout",
                                        searchPath = 1)
            if rc:
                raise SystemError, "lvcreate failed for %s" %(self.name,)
            lvm.unlinkConf()
            self.isSetup = 1

        return "/dev/%s" % (self.getDevice(),)

    def getDevice(self, asBoot = 0):
        return "%s/%s" % (self.volumeGroup, self.name)

    def solidify(self):
        return
            
    
class PartitionDevice(Device):
    def __init__(self, partition):
        Device.__init__(self)
        if type(partition) != types.StringType:
            raise ValueError, "partition must be a string"
        self.device = partition

    def setupDevice(self, chroot="/", devPrefix='/tmp'):
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
        
        return partedUtils.get_partition_name(self.partition)

    def solidify(self):
        # drop reference on the parted partition object and note
        # the current minor number allocation
        self.device = self.getDevice()
        self.partition = None

class BindMountDevice(Device):
    def __init__(self, directory):
        Device.__init__(self)
        self.device = directory

    def setupDevice(self, chroot="/", devPrefix="/tmp"):
        return chroot + self.device

    
        
class SwapFileDevice(Device):
    def __init__(self, file):
        Device.__init__(self)
        self.device = file
        self.size = 0

    def setSize (self, size):
        self.size = size

    def setupDevice (self, chroot="/", devPrefix='/tmp'):
        file = os.path.normpath(chroot + self.getDevice())
        if not os.access(file, os.R_OK):
            if self.size:
                # make sure the permissions are set properly
                fd = os.open(file, os.O_CREAT, 0600)
                os.close(fd)
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
        
    def setupDevice(self, chroot="/", devPrefix='/tmp'):
        return SwapFileDevice.setupDevice(self, self.piggypath, devPrefix)

class LoopbackDevice(Device):
    def __init__(self, hostPartition, hostFs):
        Device.__init__(self)
        self.host = "/dev/" + hostPartition
        self.hostfs = hostFs
        self.device = "loop1"

    def setupDevice(self, chroot="/", devPrefix='/tmp/'):
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
    if dev.startswith('md'):
        try:
            (mdname, devices, level, numActive) = raid.lookup_raid_device(dev)
            device = RAIDDevice(level, devices,
                                minor=int(mdname[2:]),
                                spares=len(devices) - numActive,
                                existing=1)
        except KeyError:
            device = DevDevice(dev)
    else:
        device = DevDevice(dev)        
    return device

# XXX fix RAID
def readFstab (path, intf = None):
    fsset = FileSystemSet()

    # first, we look at all the disks on the systems and get any ext2/3
    # labels off of the filesystem.
    # temporary, to get the labels
    diskset = partedUtils.DiskSet()
    diskset.openDevices()
    labels = diskset.getLabels()

    labelToDevice = {}
    for device, label in labels.items():
        if not labelToDevice.has_key(label):
            labelToDevice[label] = device
        elif intf is not None:
            intf.messageWindow(_("Duplicate Labels"),
                               _("Multiple devices on your system are "
                                 "labelled %s.  Labels across devices must be "
                                 "unique for your system to function "
                                 "properly.\n\n"
                                 "Please fix this problem and restart the "
                                 "installation process.") %(label,),
                               type="custom", custom_icon="error",
                               custom_buttons=[_("_Reboot")])
            sys.exit(0)
        else:
            log("WARNING!!! Duplicate labels for %s, but no intf so trying "
                "to continue" %(label,))
                                 

    # mark these labels found on the system as used so the factory
    # doesn't give them to another device
    labelFactory.reserveLabels(labels)
    
    loopIndex = {}

    f = open (path, "r")
    lines = f.readlines ()
    f.close()

    for line in lines:
	fields = string.split (line)

	if not fields: continue

	if line[0] == "#":
	    # skip all comments
	    continue

	# all valid fstab entries have 6 fields; if the last two are missing
        # they are assumed to be zero per fstab(5)
        if len(fields) < 4:
            continue
        elif len(fields) == 4:
            fields.append(0)
            fields.append(0)            
        elif len(fields) == 5:
            fields.append(0)                        
        elif len(fields) > 6:
            continue
	if string.find(fields[3], "noauto") != -1: continue

        # shenanigans to handle ext3,ext2 format in fstab
        fstotry = fields[2]
        if fstotry.find(","):
            fstotry = fstotry.split(",")
        else:
            fstotry = [ fstotry ]
        fsystem = None            
        for fs in fstotry:
            # if we don't support mounting the filesystem, continue
            if not fileSystemTypes.has_key(fs):
                continue
            fsystem = fileSystemTypeGet(fs)
            break
        if fsystem is None:
            continue
        
        label = None
	if fields[0] == "none":
            device = Device()
        elif ((string.find(fields[3], "bind") != -1) and
              fields[0].startswith("/")):
            # it's a bind mount, they're Weird (tm)
            device = BindMountDevice(fields[0])
            fsystem = fileSystemTypeGet("bind")
        elif len(fields) >= 6 and fields[0].startswith('LABEL='):
            label = fields[0][6:]
            if labelToDevice.has_key(label):
                device = makeDevice(labelToDevice[label])
            else:
                log ("Warning: fstab file has LABEL=%s, but this label "
                     "could not be found on any file system", label)
                # bad luck, skip this entry.
                continue
	elif fields[2] == "swap" and not fields[0].startswith('/dev/'):
	    # swap files
	    file = fields[0]

            if file.startswith('/initrd/loopfs/'):
		file = file[14:]
                device = PiggybackSwapFileDevice("/mnt/loophost", file)
            else:
                device = SwapFileDevice(file)
        elif fields[0].startswith('/dev/loop'):
	    # look up this loop device in the index to find the
            # partition that houses the filesystem image
            # XXX currently we assume /dev/loop1
	    if loopIndex.has_key(device):
		(dev, fs) = loopIndex[device]
                device = LoopbackDevice(dev, fs)
	elif fields[0].startswith('/dev/'):
            device = makeDevice(fields[0][5:])
	else:
            continue

        # if they have a filesystem being mounted as auto, we need
        # to sniff around a bit to figure out what it might be
        # if we fail at all, though, just ignore it
        if fsystem == "auto" and device.getDevice() != "none":
            try:
                tmp = partedUtils.sniffFilesystemType("/dev/%s" %(device.setupDevice(),))
                if tmp is not None:
                    fsystem = tmp
            except:
                pass

        entry = FileSystemSetEntry(device, fields[1], fsystem, fields[3],
                                   origfsystem=fsystem)
        if label:
            entry.setLabel(label)
        fsset.add(entry)
    return fsset

def getDevFD(device):
    try:
        fd = os.open(device, os.O_RDONLY)
    except:
        file = '/tmp/' + device
        try:
            isys.makeDevInode(device, file)
            fd = os.open(file, os.O_RDONLY)
        except:
            return -1
    return fd

def isValidExt2(device):
    fd = getDevFD(device)
    if fd == -1:
        return 0

    buf = os.read(fd, 2048)
    os.close(fd)

    if len(buf) != 2048:
	return 0

    if struct.unpack("<H", buf[1080:1082]) == (0xef53,):
	return 1

    return 0

def isValidXFS(device):
    fd = getDevFD(device)
    if fd == -1:
        return 0
    
    buf = os.read(fd, 4)
    os.close(fd)
    
    if len(buf) != 4:
        return 0
    
    if buf == "XFSB":
        return 1
    
    return 0

def isValidReiserFS(device):
    fd = getDevFD(device)
    if fd == -1:
        return 0

    '''
    ** reiserfs 3.5.x super block begins at offset 8K
    ** reiserfs 3.6.x super block begins at offset 64K
    All versions have a magic value of "ReIsEr" at
    offset 0x34 from start of super block
    '''
    reiserMagicVal = "ReIsEr"
    reiserMagicOffset = 0x34
    reiserSBStart = [64*1024, 8*1024]
    bufSize = 0x40  # just large enough to include the magic value
    for SBOffset in reiserSBStart:
        try:
            os.lseek(fd, SBOffset, 0)
            buf = os.read(fd, bufSize)
        except:
            buf = ""

        if len(buf) < bufSize:
            continue

        if (buf[reiserMagicOffset:reiserMagicOffset+len(reiserMagicVal)] ==
            reiserMagicVal):
            os.close(fd)
            return 1

    os.close(fd)
    return 0    

def isValidJFS(device):
    fd = getDevFD(device)
    if fd == -1:
        return 0

    try:
        os.lseek(fd, 32768, 0)
        buf = os.read(fd, 128)
    except:
        buf = ""

    os.close(fd)
    if len(buf) < 4:
        return 0

    if (buf[0:4] == "JFS1"):
	return 1

    return 0    

# this will return a list of types of filesystems which device
# looks like it could be to try mounting as
def getFStoTry(device):
    rc = []

    if isValidXFS(device):
        rc.append("xfs")

    if isValidReiserFS(device):
        rc.append("reiserfs")

    if isValidJFS(device):
        rc.append("jfs")

    if isValidExt2(device):
        if os.access(device, os.O_RDONLY):
            create = 0
        else:
            create = 1
        if isys.ext2HasJournal(device, makeDevNode = create):
            rc.append("ext3")
        rc.append("ext2")

    # FIXME: need to check for swap

    return rc

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

def ext2FormatFilesystem(argList, messageFile, windowCreator, mntpoint):
    if windowCreator:
        w = windowCreator(_("Formatting"),
                          _("Formatting %s file system...") % (mntpoint,), 100)
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
        os._exit(1)
			    
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
                    except (IndexError, TypeError):
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
        log("exception from waitpid while formatting: %s %s" %(num, msg))
        status = None
    os.close(fd)

    w and w.pop()

    # *shrug*  no clue why this would happen, but hope that things are fine
    if status is None:
        return 0
    
    if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
	return 0

    return 1

if __name__ == "__main__":
    log.open("foo")
    
    fsset = readFstab("fstab")

    print fsset.fstab()
    
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
