#
# fsset.py: filesystem management
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
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
#

import math
import string
import isys
import iutil
import os
import resource
import posix
import stat
import errno
import parted
import sys
import struct
import partitions
import partedUtils
import raid
import lvm
import time
import types
from flags import flags
from constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class SuspendError(Exception):
    pass

class OldSwapError(Exception):
    pass

class ResizeError(Exception):
    pass

defaultMountPoints = ['/', '/boot', '/home', '/tmp', '/usr', '/var', '/usr/local', '/opt']

if iutil.isS390():
    # Many s390 have 2G DASDs, we recomment putting /usr/share on its own DASD
    defaultMountPoints.insert(5, '/usr/share')

if iutil.isEfi():
    defaultMountPoints.insert(2, '/boot/efi')

fileSystemTypes = {}

def fileSystemTypeGetDefault():
    if fileSystemTypeGet('ext3').isSupported():
        return fileSystemTypeGet('ext3')
    elif fileSystemTypeGet('ext2').isSupported():
        return fileSystemTypeGet('ext2')
    else:
        raise ValueError, "You have neither ext3 or ext2 support in your kernel!"


def fileSystemTypeGet(key):
    if fileSystemTypes.has_key(key):
        return fileSystemTypes[key]
    else:
        return fileSystemTypeGetDefault()

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

def devify(device):
    if device in ["proc", "devpts", "sysfs", "tmpfs"] or device.find(":") != -1:
        return device
    elif device == "sys":
        return "sysfs"
    elif device == "shm":
        return "tmpfs"
    elif device == "spufs":
        return "spufs"
    elif device != "none" and device[0] != '/':
        return "/dev/" + device
    else:
        return device

class FileSystemType:
    kernelFilesystems = {}
    lostAndFoundContext = None

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
        self.needProgram = []
        self.resizable = False
        self.supportsFsProfiles = False
        self.fsProfileSpecifier = None
        self.fsprofile = None
        self.bootable = False

    def createLabel(self, mountpoint, maxLabelChars, kslabel = None):
        # If a label was specified in the kickstart file, return that as the
        # label.
        if kslabel:
            return kslabel

        if len(mountpoint) > maxLabelChars:
            return mountpoint[0:maxLabelChars]
        else:
            return mountpoint

    def isBootable(self):
        return self.bootable

    def isResizable(self):
        return self.resizable
    def resize(self, entry, size, progress, chroot='/'):
        pass
    def getMinimumSize(self, device):
        log.warning("Unable to determinine minimal size for %s", device)
        return 1

    def isKernelFS(self):
        """Returns True if this is an in-kernel pseudo-filesystem."""
        return False

    def mount(self, device, mountpoint, readOnly=0, bindMount=0,
              instroot=""):
        if not self.isMountable():
            return
        iutil.mkdirChain("%s/%s" %(instroot, mountpoint))
        if flags.selinux:
            ret = isys.resetFileContext(mountpoint, instroot)
            log.info("set SELinux context for mountpoint %s to %s" %(mountpoint, ret))
        log.debug("mounting %s on %s/%s as %s" %(device, instroot, 
                                                 mountpoint, self.getMountName()))
        isys.mount(device, "%s/%s" %(instroot, mountpoint),
                   fstype = self.getMountName(), 
                   readOnly = readOnly, bindMount = bindMount,
                   options = self.defaultOptions)

        if flags.selinux:
            ret = isys.resetFileContext(mountpoint, instroot)
            log.info("set SELinux context for newly mounted filesystem root at %s to %s" %(mountpoint, ret))
            if FileSystemType.lostAndFoundContext is None:
                FileSystemType.lostAndFoundContext = \
                    isys.matchPathContext("/lost+found")
            isys.setFileContext("%s/lost+found" % (mountpoint,),
                FileSystemType.lostAndFoundContext, instroot)

    def umount(self, device, path):
        isys.umount(path, removeDir = 0)

    def getName(self, quoted = 0):
        """Return the name of the filesystem.  Set quoted to 1 if this
        should be quoted (ie, it's not for display)."""
        if quoted:
            if self.name.find(" ") != -1:
                return "\"%s\"" %(self.name,)
        return self.name

    def getMountName(self, quoted = 0):
        return self.getName(quoted)

    def getNeededPackages(self):
        return self.packages

    def registerDeviceArgumentFunction(self, klass, function):
        self.deviceArguments[klass] = function

    def formatDevice(self, entry, progress, chroot='/'):
        if self.isFormattable():
            raise RuntimeError, "formatDevice method not defined"

    def migrateFileSystem(self, device, message, chroot='/'):
        if self.isMigratable():
            raise RuntimeError, "migrateFileSystem method not defined"

    def labelDevice(self, entry, chroot):
        pass

    def clobberDevice(self, entry, chroot):
        pass

    def isFormattable(self):
        return self.formattable

    def isLinuxNativeFS(self):
        return self.linuxnativefs

    def setFsProfile(self, fsprofile=None):
        if not self.supportsFsProfiles:
            raise RuntimeError, "%s does not support profiles" % (self,)
        self.fsprofile = fsprofile

    def getFsProfileArgs(self):
        if not self.supportsFsProfiles:
            raise RuntimeError, "%s does not support profiles" % (self,)
        args = None 
        if self.fsprofile:
            args = []
            if self.fsProfileSpecifier:
                args.extend(self.fsProfileSpecifier)
            args.extend(self.fsprofile)
        return args

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

        return FileSystemType.kernelFilesystems.has_key(self.getMountName()) or self.getName() == "auto"

    def isSupported(self):
        # check to ensure we have the binaries they need
        for p in self.needProgram:
            if len(filter(lambda d: os.path.exists("%s/%s" %(d, p)),
                          os.environ["PATH"].split(":"))) == 0:
                return False

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
        self.bootable = True
        # this is totally, 100% unsupported.  Boot with "linux reiserfs"
        # at the boot: prompt will let you make new reiserfs filesystems
        # in the installer.  Bugs filed when you use this will be closed
        # WONTFIX.
        if flags.cmdline.has_key("reiserfs"):
            self.supported = -1
        else:
            self.supported = 0

        self.name = "reiserfs"
        self.packages = [ "reiserfs-utils" ]
        self.needProgram = [ "mkreiserfs", "reiserfstune" ]

        self.maxSizeMB = 8 * 1024 * 1024

    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)

        p = os.pipe()
        os.write(p[1], "y\n")
        os.close(p[1])

        rc = iutil.execWithRedirect("mkreiserfs",
                                    [devicePath],
                                    stdin = p[0],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5", searchPath = 1)

        if rc:
            raise SystemError

    def labelDevice(self, entry, chroot):
        devicePath = entry.device.setupDevice(chroot)
        label = self.createLabel(entry.mountpoint, self.maxLabelChars,
                                 kslabel = entry.label)
        rc = iutil.execWithRedirect("reiserfstune",
                                    ["--label", label, devicePath],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5", searchPath = 1)
        if rc:
            raise SystemError
        entry.setLabel(label)

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
        self.supported = -1
        if not os.path.exists("/sbin/mkfs.xfs") and not os.path.exists("/usr/sbin/mkfs.xfs") and not os.path.exists("/usr/sbin/xfs_admin"):
            self.supported = 0

        self.packages = [ "xfsprogs" ]
        self.needProgram = [ "mkfs.xfs", "xfs_admin" ]

    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)

        rc = iutil.execWithRedirect("mkfs.xfs", ["-f", devicePath],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5", searchPath = 1)

        if rc:
            raise SystemError

    def labelDevice(self, entry, chroot):
        devicePath = entry.device.setupDevice(chroot)
        label = self.createLabel(entry.mountpoint, self.maxLabelChars,
                                 kslabel = entry.label)
        rc = iutil.execWithRedirect("xfs_admin",
                                    ["-L", label, devicePath],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5", searchPath = 1)
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
        self.bootable = True
        # this is totally, 100% unsupported.  Boot with "linux jfs"
        # at the boot: prompt will let you make new reiserfs filesystems
        # in the installer.  Bugs filed when you use this will be closed
        # WONTFIX.
        if flags.cmdline.has_key("jfs"):
            self.supported = -1
        else:
            self.supported = 0

        self.name = "jfs"
        self.packages = [ "jfsutils" ]
        self.needProgram = [ "mkfs.jfs", "jfs_tune" ]

        self.maxSizeMB = 8 * 1024 * 1024

    def labelDevice(self, entry, chroot):
        devicePath = entry.device.setupDevice(chroot)
        label = self.createLabel(entry.mountpoint, self.maxLabelChars,
                                 kslabel = entry.label)
        rc = iutil.execWithRedirect("jfs_tune",
                                   ["-L", label, devicePath],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5", searchPath = 1)
        if rc:
            raise SystemError
        entry.setLabel(label)

    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)

        rc = iutil.execWithRedirect("mkfs.jfs",
                                    ["-q", devicePath],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5", searchPath = 1)

        if rc:
            raise SystemError

fileSystemTypeRegister(jfsFileSystem())

class gfs2FileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = None
        self.formattable = 1
        self.checked = 1
        self.linuxnativefs = 1
        if flags.cmdline.has_key("gfs2"):
            self.supported = -1
        else:
            self.supported = 0

        self.name = "gfs2"
        self.packages = [ "gfs2-utils" ]
        self.needProgram = [ "mkfs.gfs2" ]

        self.maxSizeMB = 8 * 1024 * 1024

    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)
        rc = iutil.execWithRedirect("mkfs.gfs2",
                                    ["-j", "1", "-p", "lock_nolock",
                                     "-O", devicePath],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5", searchPath = 1)

        if rc:
            raise SystemError

fileSystemTypeRegister(gfs2FileSystem())

class extFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = None
        self.formattable = 1
        self.checked = 1
        self.linuxnativefs = 1
        self.maxSizeMB = 8 * 1024 * 1024
        self.packages = [ "e2fsprogs" ]
        self.supportsFsProfiles = True
        self.fsProfileSpecifier = "-T"
        self.resizable = True
        self.bootable = True

    def resize(self, entry, size, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)

        log.info("checking %s prior to resize" %(devicePath,))
        w = None
        if progress:
            w = progress(_("Checking"),
                         _("Checking filesystem on %s...") %(devicePath),
                         100, pulse = True)

        rc = iutil.execWithPulseProgress("e2fsck", ["-f", "-p", "-C", "0", devicePath],
                                         stdout="/tmp/resize.out",
                                         stderr="/tmp/resize.out",
                                         progress = w)
        if rc >= 4:
            raise ResizeError, ("Check of %s failed: %s" %(devicePath, rc), devicePath)
        if progress:
            w.pop()
            w = progress(_("Resizing"),
                         _("Resizing filesystem on %s...") %(devicePath),
                         100, pulse = True)

        log.info("resizing %s" %(devicePath,))
        rc = iutil.execWithPulseProgress("resize2fs",
                                         ["-p", devicePath, "%sM" %(size,)],
                                         stdout="/tmp/resize.out",
                                         stderr="/tmp/resize.out",
                                         progress = w)
        if progress:
            w.pop()
        if rc:
            raise ResizeError, ("Resize of %s failed: %s" %(devicePath, rc), devicePath)

    def getMinimumSize(self, device):
        """Return the minimum filesystem size in megabytes"""
        devicePath = "/dev/%s" % (device,)

        # FIXME: it'd be nice if we didn't have to parse this out ourselves
        buf = iutil.execWithCapture("dumpe2fs",
                                    ["-h", devicePath],
                                    stderr = "/dev/tty5")
        blocks = free = bs = 0
        for l in buf.split("\n"):
            if l.startswith("Free blocks"):
                try:
                    free = l.split()[2]
                    free = int(free)
                except Exception, e:
                    log.warning("error determining free blocks on %s: %s" %(devicePath, e))
                    free = 0
            elif l.startswith("Block size"):
                try:
                    bs = l.split()[2]
                    bs = int(bs)
                except Exception, e:
                    log.warning("error determining block size of %s: %s" %(devicePath, e))
                    bs = 0
            elif l.startswith("Block count"):
                try:
                    blocks = l.split()[2]
                    blocks = int(blocks)
                except Exception, e:
                    log.warning("error determining block count of %s: %s" %(devicePath, e))
                    blocks = 0

        if free == 0 or bs == 0:
            log.warning("Unable to determinine minimal size for %s", devicePath)
            return 1

        used = math.ceil((blocks - free) * bs / 1024.0 / 1024.0)
        log.info("used size of %s is %s" %(devicePath, used))
        # FIXME: should we bump this beyond the absolute minimum?
        return used

    def labelDevice(self, entry, chroot):
        devicePath = entry.device.setupDevice(chroot)
        label = self.createLabel(entry.mountpoint, self.maxLabelChars,
                                 kslabel = entry.label)

        rc = iutil.execWithRedirect("e2label",
                                    [devicePath, label],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5", searchPath = 1)
        if rc:
            raise SystemError
        entry.setLabel(label)

    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)
        devArgs = self.getDeviceArgs(entry.device)
        args = [ "mke2fs", devicePath ]

        fsProfileArgs = self.getFsProfileArgs()
        if fsProfileArgs:
            args.extend(fsProfileArgs)
        args.extend(devArgs)
        args.extend(self.extraFormatArgs)

        log.info("Format command:  %s\n" % str(args))

        rc = ext2FormatFilesystem(args, "/dev/tty5",
                                  progress,
                                  entry.mountpoint)
        if rc:
            raise SystemError

    def clobberDevice(self, entry, chroot):
        device = entry.device.setupDevice(chroot)
        isys.ext2Clobber(device)

    # this is only for ext3 filesystems, but migration is a method
    # of the ext2 fstype, so it needs to be here.  FIXME should be moved
    def setExt3Options(self, entry, message, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)

        # if no journal, don't turn off the fsck
        if not isys.ext2HasJournal(devicePath):
            return

        rc = iutil.execWithRedirect("tune2fs",
                                    ["-c0", "-i0",
                                     "-ouser_xattr,acl", devicePath],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5", searchPath = 1)

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
        if isys.ext2HasJournal(devicePath):
            log.info("Skipping migration of %s, has a journal already.\n" % devicePath)
            return

        rc = iutil.execWithRedirect("tune2fs",
                                    ["-j", devicePath ],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5", searchPath = 1)

        if rc:
            raise SystemError

        # XXX this should never happen, but appears to have done
        # so several times based on reports in bugzilla.
        # At least we can avoid leaving them with a system which won't boot
        if not isys.ext2HasJournal(devicePath):
            log.warning("Migration of %s attempted but no journal exists after "
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
        self.extraFormatArgs = [ "-t", "ext3" ]
        self.partedFileSystemType = parted.file_system_type_get("ext3")
        if flags.cmdline.has_key("ext4"):
            self.migratetofs = ['ext4']

    def formatDevice(self, entry, progress, chroot='/'):
        extFileSystem.formatDevice(self, entry, progress, chroot)
        extFileSystem.setExt3Options(self, entry, progress, chroot)

    def migrateFileSystem(self, entry, message, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)

        if not entry.fsystem or not entry.origfsystem:
            raise RuntimeError, ("Trying to migrate fs w/o fsystem or "
                                 "origfsystem set")
        if entry.fsystem.getName() != "ext4":
            raise RuntimeError, ("Trying to migrate ext3 to something other "
                                 "than ext4")

fileSystemTypeRegister(ext3FileSystem())

class ext4FileSystem(extFileSystem):
    def __init__(self):
        extFileSystem.__init__(self)
        self.name = "ext4"
        self.partedFileSystemType = parted.file_system_type_get("ext3")
        self.extraFormatArgs = [ "-t", "ext4" ]
        self.bootable = False

        # this is way way experimental at present...
        if flags.cmdline.has_key("ext4"):
            self.supported = -1
        else:
            self.supported = 0


    def formatDevice(self, entry, progress, chroot='/'):
        extFileSystem.formatDevice(self, entry, progress, chroot)
        extFileSystem.setExt3Options(self, entry, progress, chroot)

fileSystemTypeRegister(ext4FileSystem())

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

        if len(raid.availRaidLevels) == 0:
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
        self.maxLabelChars = 15

    def mount(self, device, mountpoint, readOnly=0, bindMount=0,
              instroot = None):
        pagesize = resource.getpagesize()
        buf = None
        if pagesize > 2048:
            num = pagesize
        else:
            num = 2048
        try:
            fd = os.open(device, os.O_RDONLY)
            buf = os.read(fd, num)
        except:
            pass
        finally:
            try:
                os.close(fd)
            except:
                pass

        if buf is not None and len(buf) == pagesize:
            sig = buf[pagesize - 10:]
            if sig == 'SWAP-SPACE':
                raise OldSwapError
            if sig == 'S1SUSPEND\x00' or sig == 'S2SUSPEND\x00':
                raise SuspendError

        isys.swapon (device)

    def umount(self, device, path):
        if os.path.exists("/dev/" + device.device):
            swapFile = os.path.realpath("/dev/" + device.device)
        else:
            # path is something like /mnt/sysimage/swap, which is not very
            # useful.  But since we don't have instPath anywhere else, so
            # we have to pull it out of path and add the real swap file to
            # the end of it.
            swapFile = os.path.realpath(os.path.dirname(path) + "/" + device.device)

        try:
            iutil.execWithRedirect("swapoff", [swapFile], stdout="/dev/tty5",
                                   stderr="/dev/tty5", searchPath=1)
        except:
            raise RuntimeError, "unable to turn off swap"

    def formatDevice(self, entry, progress, chroot='/'):
        file = entry.device.setupDevice(chroot)
        rc = iutil.execWithRedirect ("mkswap",
                                     ['-v1', file],
                                     stdout = "/dev/tty5",
                                     stderr = "/dev/tty5",
                                     searchPath = 1)
        if rc:
            raise SystemError

    def labelDevice(self, entry, chroot):
        file = entry.device.setupDevice(chroot)
        devName = entry.device.getDevice()
        # we'll keep the SWAP-* naming for all devs but Compaq SMART2
        # nodes (#176074)
        if devName[0:6] == "cciss/":
            swapLabel = "SW-%s" % (devName)
        elif devName.startswith("mapper/"):
            swapLabel = "SWAP-%s" % (devName[7:],)
        else:
            swapLabel = "SWAP-%s" % (devName)
        label = self.createLabel(swapLabel, self.maxLabelChars)
        rc = iutil.execWithRedirect ("mkswap",
                                     ['-v1', "-L", label, file],
                                     stdout = "/dev/tty5",
                                     stderr = "/dev/tty5",
                                     searchPath = 1)
        if rc:
            raise SystemError
        entry.setLabel(label)

    def clobberDevice(self, entry, chroot):
        pagesize = resource.getpagesize()
        dev = entry.device.setupDevice(chroot)
        try:
            fd = os.open(dev, os.O_RDWR)
            buf = "\0x00" * pagesize
            os.write(fd, buf)
        except:
            pass
        finally:
            try:
                os.close(fd)
            except:
                pass

fileSystemTypeRegister(swapFileSystem())

class FATFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("fat32")
        self.formattable = 1
        self.checked = 0
        self.maxSizeMB = 1024 * 1024
        self.name = "vfat"
        self.packages = [ "dosfstools" ]
        self.defaultOptions = "umask=0077,shortname=winnt"

    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)
        devArgs = self.getDeviceArgs(entry.device)
        args = [ devicePath ]
        args.extend(devArgs)

        rc = iutil.execWithRedirect("mkdosfs", args,
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5", searchPath = 1)
        if rc:
            raise SystemError

    def labelDevice(self, entry, chroot):
        devicePath = entry.device.setupDevice(chroot)
        label = self.createLabel(entry.mountpoint, self.maxLabelChars,
                                 kslabel = entry.label)

        rc = iutil.execWithRedirect("dosfslabel",
                                    [devicePath, label],
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5",
                                    searchPath = 1)
        if rc:
            msg = iutil.execWithCapture("dosfslabel", [devicePath],
                                        stderr="/dev/tty5")
            raise SystemError, "dosfslabel failed on device %s: %s" % (devicePath, msg)

        newLabel = iutil.execWithCapture("dosfslabel", [devicePath],
                                         stderr = "/dev/tty5")
        newLabel = newLabel.strip()
        if label != newLabel:
            raise SystemError, "dosfslabel failed on device %s" % (devicePath,)
        entry.setLabel(label)

fileSystemTypeRegister(FATFileSystem())

class EFIFileSystem(FATFileSystem):
    def __init__(self):
        FATFileSystem.__init__(self)
        self.name = "efi"
        self.partedPartitionFlags = [ parted.PARTITION_BOOT ]
        self.maxSizeMB = 256
        self.defaultOptions = "umask=0077,shortname=winnt"
        self.bootable = True
        if not iutil.isEfi():
            self.supported = 0

    def getMountName(self, quoted = 0):
        return "vfat"

    def formatDevice(self, entry, progress, chroot='/'):
        FATFileSystem.formatDevice(self, entry, progress, chroot)

        # XXX need to set the name in GPT
        # entry.device.something.part.set_name("EFI System Partition")
        devicePath = entry.device.setupDevice(chroot)

fileSystemTypeRegister(EFIFileSystem())

class NTFSFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("ntfs")
        self.formattable = 0
        self.checked = 0
        self.name = "ntfs"
        if len(filter(lambda d: os.path.exists("%s/ntfsresize" %(d,)),
                      os.environ["PATH"].split(":"))) > 0:
            self.resizable = True

    def resize(self, entry, size, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)
        log.info("resizing %s to %sM" %(devicePath, size))
        w = None
        if progress:
            w = progress(_("Resizing"),
                         _("Resizing filesystem on %s...") %(devicePath),
                         100, pulse = True)

        p = os.pipe()
        os.write(p[1], "y\n")
        os.close(p[1])

        # FIXME: we should call ntfsresize -c to ensure that we can resize
        # before starting the operation

        rc = iutil.execWithPulseProgress("ntfsresize", ["-v",
                                                        "-s", "%sM" %(size,),
                                                        devicePath],
                                         stdin = p[0],
                                         stdout = "/tmp/resize.out",
                                         stderr = "/tmp/resize.out",
                                         progress = w)
        if progress:
            w.pop()
        if rc:
            raise ResizeError, ("Resize of %s failed" %(devicePath,), devicePath)

    def getMinimumSize(self, device):
        """Return the minimum filesystem size in megabytes"""
        devicePath = "/dev/%s" % (device,)

        buf = iutil.execWithCapture("ntfsresize", ["-m", devicePath],
                                    stderr = "/dev/tty5")
        for l in buf.split("\n"):
            if not l.startswith("Minsize"):
                continue
            try:
                min = l.split(":")[1].strip()
                return int(min) + 250
            except Exception, e:
                log.warning("Unable to parse output for minimum size on %s: %s" %(device, e))

        log.warning("Unable to discover minimum size of filesystem on %s" %(device,))        
        return 1


fileSystemTypeRegister(NTFSFileSystem())

class hfsFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("hfs")
        self.formattable = 1
        self.checked = 0
        self.name = "hfs"
        self.supported = 0
        self.needProgram = [ "hformat" ]

    def isMountable(self):
        return 0

    def formatDevice(self, entry, progress, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)
        devArgs = self.getDeviceArgs(entry.device)
        args = [ devicePath ]
        args.extend(devArgs)

        rc = iutil.execWithRedirect("hformat", args,
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5", searchPath = 1)
        if rc:
            raise SystemError

fileSystemTypeRegister(hfsFileSystem())

class HfsPlusFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("hfs+")
        self.formattable = 0
        self.checked = 0
        self.name = "hfs+"

fileSystemTypeRegister(HfsPlusFileSystem())

class applebootstrapFileSystem(hfsFileSystem):
    def __init__(self):
        hfsFileSystem.__init__(self)
        self.partedPartitionFlags = [ parted.PARTITION_BOOT ]
        self.maxSizeMB = 1
        self.name = "Apple Bootstrap"
        self.bootable = True
        if iutil.getPPCMacGen() == "NewWorld":
            self.linuxnativefs = 1
            self.supported = 1
        else:
            self.linuxnativefs = 0
            self.supported = 0

fileSystemTypeRegister(applebootstrapFileSystem())

class prepbootFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = None
        self.partedPartitionFlags = [ parted.PARTITION_BOOT, parted.PARTITION_PREP ]
        self.checked = 0
        self.name = "PPC PReP Boot"
        self.maxSizeMB = 10
        self.bootable = True

        if iutil.getPPCMachine() == "iSeries":
            self.maxSizeMB = 64

        # supported for use on the pseries
        if (iutil.getPPCMachine() == "pSeries" or
            iutil.getPPCMachine() == "iSeries"):
            self.linuxnativefs = 1
            self.supported = 1
            self.formattable = 1
        else:
            self.linuxnativefs = 0
            self.supported = 0
            self.formattable = 0

    def formatDevice(self, entry, progress, chroot='/'):
        return

fileSystemTypeRegister(prepbootFileSystem())

class networkFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.formattable = 0
        self.checked = 0
        self.name = "nfs"

    def isMountable(self):
        return 0

fileSystemTypeRegister(networkFileSystem())

class nfsv4FileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.formattable = 0
        self.checked = 0
        self.name = "nfs4"

    def isMountable(self):
        return 0

fileSystemTypeRegister(nfsv4FileSystem())

class ForeignFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.formattable = 0
        self.checked = 0
        self.name = "foreign"

    def formatDevice(self, entry, progress, chroot='/'):
        return

fileSystemTypeRegister(ForeignFileSystem())

class PseudoFileSystem(FileSystemType):
    def __init__(self, name):
        FileSystemType.__init__(self)
        self.formattable = 0
        self.checked = 0
        self.name = name
        self.supported = 0

    def isKernelFS(self):
        return True

class SpuFileSystem(PseudoFileSystem):
    def __init__(self):
        PseudoFileSystem.__init__(self, "spufs")

fileSystemTypeRegister(SpuFileSystem())

class ProcFileSystem(PseudoFileSystem):
    def __init__(self):
        PseudoFileSystem.__init__(self, "proc")

fileSystemTypeRegister(ProcFileSystem())

class SysfsFileSystem(PseudoFileSystem):
    def __init__(self):
        PseudoFileSystem.__init__(self, "sysfs")

fileSystemTypeRegister(SysfsFileSystem())

class SelinuxfsFileSystem(PseudoFileSystem):
    def __init__(self):
        PseudoFileSystem.__init__(self, "selinuxfs")

fileSystemTypeRegister(SelinuxfsFileSystem())

class DevptsFileSystem(PseudoFileSystem):
    def __init__(self):
        PseudoFileSystem.__init__(self, "devpts")
        self.defaultOptions = "gid=5,mode=620"

    def isMountable(self):
        return 0

fileSystemTypeRegister(DevptsFileSystem())

class DevshmFileSystem(PseudoFileSystem):
    def __init__(self):
        PseudoFileSystem.__init__(self, "tmpfs")

    def isMountable(self):
        return 0

fileSystemTypeRegister(DevshmFileSystem())

class AutoFileSystem(PseudoFileSystem):
    def __init__(self):
        PseudoFileSystem.__init__(self, "auto")

    def mount(self, device, mountpoint, readOnly=0, bindMount=0,
              instroot = None):
        errNum = 0
        errMsg = "cannot mount auto filesystem on %s of this type" % device

        if not self.isMountable():
            return
        iutil.mkdirChain("%s/%s" %(instroot, mountpoint))
        if flags.selinux:
            ret = isys.resetFileContext(mountpoint, instroot)
            log.info("set SELinux context for mountpoint %s to %s" %(mountpoint, ret))

        fs = isys.readFSType(device)
        if fs is not None:
            try:
                isys.mount (device, mountpoint, fstype = fs, readOnly =
                            readOnly, bindMount = bindMount)
                return
            except SystemError, (num, msg):
                errNum = num
                errMsg = msg

        raise SystemError (errNum, errMsg)

    def umount(self, device, path):
        isys.umount(path, removeDir = 0)

fileSystemTypeRegister(AutoFileSystem())

class BindFileSystem(PseudoFileSystem):
    def __init__(self):
        PseudoFileSystem.__init__(self, "bind")

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
        proc = FileSystemSetEntry(Device(device="proc"), '/proc',
                                  fileSystemTypeGet("proc"))
        self.add(proc)
        sys = FileSystemSetEntry(Device(device="sys"), '/sys',
                                 fileSystemTypeGet("sysfs"))
        self.add(sys)
        pts = FileSystemSetEntry(Device(device="devpts"), '/dev/pts',
                                 fileSystemTypeGet("devpts"), "gid=5,mode=620")
        self.add(pts)
        shm = FileSystemSetEntry(Device(device="shm"), '/dev/shm',
                                 fileSystemTypeGet("tmpfs"))
        self.add(shm)

        if iutil.isCell():
            spu = FileSystemSetEntry(Device(device="spufs"), '/spu',
                                 fileSystemTypeGet("spufs"))
            self.add(spu)

    def verify (self):
        for entry in self.entries:
            if type(entry.__dict__) != type({}):
                raise RuntimeError, "fsset internals inconsistent"

    def add (self, newEntry):
        # Should object A be sorted after object B?  Take mountpoints and
        # device names into account so bind mounts are sorted correctly.
        def comesAfter (a, b):
            mntA = a.mountpoint
            mntB = b.mountpoint
            devA = a.device.getDevice()
            devB = b.device.getDevice()

            if not mntB:
                return False
            if mntA and mntA != mntB and mntA.startswith(mntB):
                return True
            if devA and devA != mntB and devA.startswith(mntB):
                return True
            return False

        def samePseudo (a, b):
            return isinstance(a.fsystem, PseudoFileSystem) and isinstance (b.fsystem, PseudoFileSystem) and \
                   not isinstance (a.fsystem, BindFileSystem) and not isinstance (b.fsystem, BindFileSystem) and \
                   a.fsystem.getName() == b.fsystem.getName()

        def sameEntry (a, b):
            return a.device.getDevice() == b.device.getDevice() and a.mountpoint == b.mountpoint

        # Remove preexisting duplicate entries - pseudo filesystems are
        # duplicate if they have the same filesystem type as an existing one.
        # Otherwise, they have to have the same device and mount point
        # (required to check for bind mounts).
        for existing in self.entries:
            if samePseudo (newEntry, existing) or sameEntry (newEntry, existing):
                self.remove(existing)

        # XXX debuggin'
##         log.info ("fsset at %s\n"
##                   "adding entry for %s\n"
##                   "entry object %s, class __dict__ is %s",
##                   self, entry.mountpoint, entry,
##                   isys.printObject(entry.__dict__))

        insertAt = 0

        # Special case for /.
        if newEntry.mountpoint == "/":
            self.entries.insert(insertAt, newEntry)
            return

        # doesn't matter where these get added, so just put them at the end
        if not newEntry.mountpoint or not newEntry.mountpoint.startswith("/") or self.entries == []:
            self.entries.append(newEntry)
            return

        for entry in self.entries:
            if comesAfter(newEntry, entry):
                insertAt = self.entries.index(entry)+1

        self.entries.insert(insertAt, newEntry)

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

            # getDevice() will return the mapped device if using LUKS
            if entry.device.device == dev:
                return entry

        return None

    def copy (self):
        new = FileSystemSet()
        for entry in self.entries:
            new.add (entry)
        return new

    def fstab (self):
        format = "%-23s %-23s %-7s %-15s %d %d\n"
        fstab = """
#
# /etc/fstab
# Created by anaconda on %s
#
# Accessible filesystems, by reference, are maintained under '/dev/disk'
# See man pages fstab(5), findfs(8), mount(8) and/or vol_id(8) for more info
#
""" % time.asctime()

        for entry in self.entries:
            if entry.mountpoint:
                if entry.getUuid() and entry.device.doLabel is not None:
                    device = "UUID=%s" %(entry.getUuid(),)
                elif entry.getLabel() and entry.device.doLabel is not None:
                    device = "LABEL=%s" % (entry.getLabel(),)
                else:
                    device = devify(entry.device.getDevice())
                fstab = fstab + entry.device.getComment()
                fstab = fstab + format % (device, entry.mountpoint,
                                          entry.fsystem.getMountName(),
                                          entry.getOptions(), entry.fsck,
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
                options = entry.getOptions()
                if options:
                    options = "rw," + options
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
        activeArrays = iutil.execWithCapture("mdadm", ["--detail", "--scan"])
        if len(activeArrays) == 0:
            return

        cf = """
# mdadm.conf written out by anaconda
DEVICE partitions
MAILADDR root

%s
""" % activeArrays
        return cf

    def crypttab(self):
        """set up /etc/crypttab"""
        crypttab = ""
        for entry in self.entries:
            if entry.device.crypto:
                crypttab += entry.device.crypto.crypttab()

        return crypttab

    def write (self, prefix):
        f = open (prefix + "/etc/fstab", "w")
        f.write (self.fstab())
        f.close ()

        cf = self.mdadmConf()

        if cf:
            f = open (prefix + "/etc/mdadm.conf", "w")
            f.write (cf)
            f.close ()

        crypttab = self.crypttab()
        if crypttab:
            f = open(prefix + "/etc/crypttab", "w")
            f.write(crypttab)
            f.close()

        # touch mtab
        open (prefix + "/etc/mtab", "w+")
        f.close ()

    def mkDevRoot(self, instPath):
        root = self.getEntryByMountPoint("/")
        dev = "%s/dev/%s" % (instPath, root.device.getDevice())
        if not os.path.exists("%s/dev/root" %(instPath,)) and os.path.exists(dev):
            rdev = os.stat(dev).st_rdev
            os.mknod("%s/dev/root" % (instPath,), stat.S_IFBLK | 0600, rdev)

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
        elif iutil.isEfi():
            if mntDict.has_key("/boot/efi"):
                bootDev = mntDict['/boot/efi']
        elif mntDict.has_key("/boot"):
            bootDev = mntDict['/boot']
        elif mntDict.has_key("/"):
            bootDev = mntDict['/']

        return bootDev

    def bootloaderChoices(self, diskSet, bl):
        ret = {}
        bootDev = self.getBootDev()

        if bootDev is None:
            log.warning("no boot device set")
            return ret

        if iutil.isEfi():
            ret['boot'] = (bootDev.device, N_("EFI System Partition"))
            return ret

        if bootDev.getName() == "RAIDDevice":
            ret['boot'] = (bootDev.device, N_("RAID Device"))
            ret['mbr'] = (bl.drivelist[0], N_("Master Boot Record (MBR)"))
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
        ret['mbr'] = (bl.drivelist[0], N_("Master Boot Record (MBR)"))
        return ret

    # set active partition on disks
    # if an active partition is set, leave it alone; if none set
    # set either our boot partition or the first partition on the drive active
    def setActive(self, diskset):
        dev = self.getBootDev()

        if dev is None:
            return

        bootDev = dev.device

        if dev.getName() != "RAIDDevice":
            part = partedUtils.get_partition_by_name(diskset.disks, bootDev)
            drive = partedUtils.get_partition_drive(part)

            # on EFI systems, *only* /boot/efi should be marked bootable
            # similarly, on pseries, we really only want the PReP partition
            # active
            if iutil.isEfi() \
                    or iutil.getPPCMachine() in ("pSeries", "iSeries", "PMac") \
                    or (iutil.isX86() \
                             and partedUtils.hasGptLabel(diskset, drive)):
                if part and part.is_flag_available(parted.PARTITION_BOOT):
                    part.set_flag(parted.PARTITION_BOOT, 1)
                return

        for drive in diskset.disks.keys():
            foundActive = 0
            bootPart = None
            if partedUtils.hasGptLabel(diskset, drive):
                continue
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

    def resizeFilesystems (self, diskset, chroot = '/', shrink = False, grow = False):
        todo = []
        for entry in self.entries:
            if not entry.fsystem or not entry.fsystem.isResizable():
                continue
            if entry.fsystem.isFormattable() and entry.getFormat():
                continue
            if entry.resizeTargetSize is None:
                continue
            if shrink and not (entry.resizeTargetSize < entry.resizeOrigSize):
                continue
            if grow and not (entry.resizeTargetSize > entry.resizeOrigSize):
                continue
            todo.append(entry)
        if len(todo) == 0:
            return

        # we have to have lvm activated to be able to do resizes of LVs
        lvmActive = lvm.vgcheckactive()
        devicesActive = diskset.devicesOpen

        if not devicesActive:
            # should this not be diskset.openDevices() ?
            diskset.startMPath()
            diskset.startDmRaid()
            diskset.startMdRaid()

        if not lvmActive:
            lvm.vgscan()
            lvm.vgactivate()

        for entry in todo:
            entry.fsystem.resize(entry, entry.resizeTargetSize,
                                 self.progressWindow, chroot)
        if not lvmActive:
            lvm.vgdeactivate()
        
        if not devicesActive:
            # should this not be diskset.closeDevices() ?
            diskset.stopMPath()
            diskset.stopDmRaid()
            diskset.stopMdRaid()

    def shrinkFilesystems (self, diskset, chroot):
        self.resizeFilesystems(diskset, chroot, shrink = True)
    def growFilesystems (self, diskset, chroot):
        self.resizeFilesystems(diskset, chroot, grow = True)

    def formatSwap (self, chroot, forceFormat=False):
        formatted = []
        notformatted = []

        for entry in self.entries:
            if (not entry.fsystem or not entry.fsystem.getName() == "swap" or
                entry.isMounted()):
                continue
            if not entry.getFormat():
                if not forceFormat:
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
                                         "Press <Enter> to exit the installer.")
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

    def turnOnSwap (self, chroot, upgrading=False):
        def swapErrorDialog (msg, format_button_text, entry):
            buttons = [_("Skip"), format_button_text, _("_Exit installer")]
            ret = self.messageWindow(_("Error"), msg, type="custom",
                                     custom_buttons=buttons,
                                     custom_icon="warning")
            if ret == 0:
                self.entries.remove(entry)
            elif ret == 1:
                self.formatEntry(entry, chroot)
                entry.mount(chroot)
                self.mountcount = self.mountcount + 1
            else:
                sys.exit(0)

        for entry in self.entries:
            if (entry.fsystem and entry.fsystem.getName() == "swap"
                and not entry.isMounted()):
                try:
                    entry.mount(chroot)
                    self.mountcount = self.mountcount + 1
                except OldSwapError:
                    if self.messageWindow:
                        msg = _("The swap device:\n\n     /dev/%s\n\n"
                                "is a version 0 Linux swap partition. If you "
                                "want to use this device, you must reformat as "
                                "a version 1 Linux swap partition. If you skip "
                                "it, the installer will ignore it during the "
                                "installation.") % (entry.device.getDevice())

                        swapErrorDialog(msg, _("Reformat"), entry)
                except SuspendError:
                    if self.messageWindow:
                        if upgrading:
                            msg = _("The swap device:\n\n     /dev/%s\n\n"
                                    "in your /etc/fstab file is currently in "
                                    "use as a software suspend partition, "
                                    "which means your system is hibernating. "
                                    "To perform an upgrade, please shut down "
                                    "your system rather than hibernating it.") \
                                  % (entry.device.getDevice())
                        else:
                            msg = _("The swap device:\n\n     /dev/%s\n\n"
                                    "in your /etc/fstab file is currently in "
                                    "use as a software suspend partition, "
                                    "which means your system is hibernating. "
                                    "If you are performing a new install, "
                                    "make sure the installer is set "
                                    "to format all swap partitions.") \
                                  % (entry.device.getDevice())

                        # choose your own adventure swap partitions...
                        msg = msg + _("\n\nChoose Skip if you want the "
                              "installer to ignore this partition during "
                              "the upgrade.  Choose Format to reformat "
                              "the partition as swap space.")

                        swapErrorDialog(msg, _("Format"), entry)
                    else:
                        sys.exit(0)
                except SystemError, (num, msg):
                    if self.messageWindow:
                        if upgrading and not entry.getLabel():
                            err = _("Error enabling swap device %s: %s\n\n"
                                    "Devices in /etc/fstab should be specified "
                                    "by label, not by device name.\n\nPress "
                                    "OK to exit the installer.") % (entry.device.getDevice(), msg)
                        elif upgrading:
                            err = _("Error enabling swap device %s: %s\n\n"
                                    "The /etc/fstab on your upgrade partition "
                                    "does not reference a valid swap "
                                    "partition.\n\nPress OK to exit the "
                                    "installer") % (entry.device.getDevice(), msg)
                        else:
                            err = _("Error enabling swap device %s: %s\n\n"
                                    "This most likely means this swap "
                                    "partition has not been initialized.\n\n"
                                    "Press OK to exit the installer.") % (entry.device.getDevice(), msg)

                    self.messageWindow(_("Error"), err)
                    sys.exit(0)

    def labelEntry(self, entry, chroot, ignoreExisting = False):
        label = entry.device.getLabel()
        if label and not ignoreExisting:
            entry.setLabel(label)
            entry.device.doLabel = 1

        if entry.device.doLabel is not None:
            entry.fsystem.labelDevice(entry, chroot)

    def formatEntry(self, entry, chroot):
        if entry.mountpoint:
            log.info("formatting %s as %s" %(entry.mountpoint, entry.fsystem.name))
        entry.fsystem.clobberDevice(entry, chroot)
        entry.fsystem.formatDevice(entry, self.progressWindow, chroot)

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

    def createLogicalVolumes (self, chroot='/'):
        vgs = {}
        # first set up the volume groups
        for entry in self.entries:
            if entry.fsystem.name == "volume group (LVM)":
                entry.device.setupDevice(chroot)
                vgs[entry.device.name] = entry.device

        # then set up the logical volumes
        for entry in self.entries:
            if isinstance(entry.device, LogicalVolumeDevice):
                vg = None
                if vgs.has_key(entry.device.vgname):
                    vg = vgs[entry.device.vgname]
                entry.device.setupDevice(chroot, vgdevice = vg)
        self.volumesCreated = 1


    def makeFilesystems (self, chroot='/', skiprootfs=False):
        formatted = []
        notformatted = []
        for entry in self.entries:
            if (not entry.fsystem.isFormattable() or not entry.getFormat()
                or entry.isMounted()):
                notformatted.append(entry)
                continue
            # FIXME: this is a bit of a hack, but works
            if (skiprootfs and entry.mountpoint == '/'):
                formatted.append(entry)
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
                                         "Press <Enter> to exit the installer.")
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
            elif entry.fsystem.isSupported():
                self.labelEntry(entry, chroot)

    def haveMigratedFilesystems(self):
        return self.migratedfs

    def migrateFilesystems (self, anaconda):
        if self.migratedfs:
            return

        for entry in self.entries:
            if not entry.origfsystem:
                continue

            if not entry.origfsystem.isMigratable() or not entry.getMigrate():
                continue
            try: 
                entry.origfsystem.migrateFileSystem(entry, self.messageWindow,
                                                    anaconda.rootPath)
            except SystemError:
                if self.messageWindow:
                    self.messageWindow(_("Error"),
                                       _("An error occurred trying to "
                                         "migrate %s.  This problem is "
                                         "serious, and the install cannot "
                                         "continue.\n\n"
                                         "Press <Enter> to exit the installer.")
                                       % (entry.device.getDevice(),))
                sys.exit(0)

        # we need to unmount and remount so that we're mounted as the
        # new fstype as we want to use the new filesystem type during
        # the upgrade for ext3->ext4 migrations
        if self.isActive():
            self.umountFilesystems(anaconda.rootPath)
            self.mountFilesystems(anaconda)
            self.turnOnSwap(anaconda.rootPath)

        self.migratedfs = 1

    def mountFilesystems(self, anaconda, raiseErrors = 0, readOnly = 0, skiprootfs = 0):
        protected = anaconda.id.partitions.protectedPartitions()

        for entry in self.entries:
            # Don't try to mount a protected partition, since it will already
            # have been mounted as the installation source.
            if protected and entry.device.getDevice() in protected and os.path.ismount("/mnt/isodir"):
                continue

            if not entry.fsystem.isMountable() or (skiprootfs and entry.mountpoint == '/'):
                continue

            try:
                log.info("trying to mount %s on %s" %(entry.device.setupDevice(), entry.mountpoint,))
                entry.mount(anaconda.rootPath, readOnly = readOnly)
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
                                             "Press <Enter> to exit the "
                                             "installer.") % (entry.mountpoint,))
                    else:
                        self.messageWindow(_("Invalid mount point"),
                                           _("An error occurred when trying "
                                             "to create %s: %s.  This is "
                                             "a fatal error and the install "
                                             "cannot continue.\n\n"
                                             "Press <Enter> to exit the "
                                             "installer.") % (entry.mountpoint,
                                                           msg))
                log.error("OSError: (%d) %s" % (num, msg) )
                sys.exit(0)
            except SystemError, (num, msg):
                if raiseErrors:
                    raise SystemError, (num, msg)
                if self.messageWindow:
                    if not entry.fsystem.isLinuxNativeFS():
                        ret = self.messageWindow(_("Unable to mount filesystem"),
                                                 _("An error occurred mounting "
                                                 "device %s as %s.  You may "
                                                 "continue installation, but "
                                                 "there may be problems.") %
                                                 (entry.device.getDevice(),
                                                  entry.mountpoint),
                                                 type="custom", custom_icon="warning",
                                                 custom_buttons=[_("_Exit installer"),
                                                                _("_Continue")])

                        if ret == 0:
                            sys.exit(0)
                        else:
                            continue
                    else:
                        if anaconda.id.getUpgrade() and not (entry.getLabel() or entry.getUuid()) and entry.device.getDevice().startswith("/dev"):
                            errStr = _("Error mounting device %s as %s: "
                                       "%s\n\n"
                                       "Devices in /etc/fstab should be specified "
                                       "by label or UUID, not by device name."
                                       "\n\n"
                                       "Press OK to exit the installer.") % (entry.device.getDevice(), entry.mountpoint, msg)
                        else:
                            errStr = _("Error mounting device %s as %s: "
                                       "%s\n\n"
                                       "Press OK to exit the installer.") % (entry.device.getDevice(), entry.mountpoint, msg)

                        self.messageWindow(_("Error"), errStr)

                log.error("SystemError: (%d) %s" % (num, msg) )
                sys.exit(0)

        self.makeLVMNodes(anaconda.rootPath)

    def makeLVMNodes(self, instPath, trylvm1 = 0):
        # XXX hack to make the device node exist for the root fs if
        # it's a logical volume so that mkinitrd can create the initrd.
        root = self.getEntryByMountPoint("/")
        if not root:
            if self.messageWindow:
                self.messageWindow(_("Error"),
                                   _("Error finding / entry.\n\n"
                                   "This is most likely means that "
                                   "your fstab is incorrect."
                                   "\n\n"
                                   "Press OK to exit the installer."))
            sys.exit(0)

        rootlvm1 = 0
        if trylvm1:
            dev = root.device.getDevice()
            # lvm1 major is 58
            if os.access("%s/dev/%s" %(instPath, dev), os.R_OK) and posix.major(os.stat("%s/dev/%s" %(instPath, dev)).st_rdev) == 58:
                rootlvm1 = 1

        if isinstance(root.device, LogicalVolumeDevice) or rootlvm1:
            # now make sure all of the device nodes exist.  *sigh*
            rc = lvm.vgmknodes()

            rootDev = "/dev/%s" % (root.device.getDevice(),)
            rootdir = instPath + os.path.dirname(rootDev)
            if not os.path.isdir(rootdir):
                os.makedirs(rootdir)

            if root.device.crypto is None:
                dmdev = "/dev/mapper/" + root.device.getDevice().replace("-","--").replace("/", "-")
            else:
                dmdev = "/dev/" + root.device.getDevice()

            if os.path.exists(instPath + dmdev):
                os.unlink(instPath + dmdev)
            if not os.path.isdir(os.path.dirname(instPath + dmdev)):
                os.makedirs(os.path.dirname(instPath + dmdev))
            iutil.copyDeviceNode(dmdev, instPath + dmdev)

            # unlink existing so that we dtrt on upgrades
            if os.path.exists(instPath + rootDev) and not root.device.crypto:
                os.unlink(instPath + rootDev)
            if not os.path.isdir(rootdir):
                os.makedirs(rootdir)

            if root.device.crypto is None:
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
                space.append((entry.mountpoint, isys.pathSpaceAvailable(path)))
            except SystemError:
                log.error("failed to get space available in filesystemSpace() for %s" %(entry.mountpoint,))

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
                    log.info("%s is a dirty ext2 partition" % entry.device.getDevice())
                    ret.append(entry.device.getDevice())
            except Exception, e:
                log.error("got an exception checking %s for being dirty, hoping it's not" %(entry.device.getDevice(),))

        return ret

    def umountFilesystems(self, instPath, ignoreErrors = 0, swapoff = True):
        # Unmount things bind mounted into the instPath here because they're
        # not tracked by self.entries.
        if os.path.ismount("%s/dev" % instPath):
            isys.umount("%s/dev" % instPath, removeDir=0)

        # take a slice so we don't modify self.entries
        reverse = self.entries[:]
        reverse.reverse()

        for entry in reverse:
            if entry.mountpoint == "swap" and not swapoff:
                continue
            entry.umount(instPath)
            entry.device.cleanupDevice(instPath)

class FileSystemSetEntry:
    def __init__ (self, device, mountpoint,
                  fsystem=None, options=None,
                  origfsystem=None, migrate=0,
                  order=-1, fsck=-1, format=0,
                  fsprofile=None):
        if not fsystem:
            fsystem = fileSystemTypeGet("ext2")
        self.device = device
        self.mountpoint = mountpoint
        self.fsystem = fsystem
        self.origfsystem = origfsystem
        self.migrate = migrate
        self.resizeTargetSize = None
        self.resizeOrigSize = None
        self.options = options
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
        self.fsprofile = fsprofile

    def mount(self, chroot='/', devPrefix='/dev', readOnly = 0):
        device = self.device.setupDevice(chroot, devPrefix=devPrefix)

        self.fsystem.mount(device, "%s" % (self.mountpoint,),
                           readOnly = readOnly,
                           bindMount = isinstance(self.device,
                                                  BindMountDevice),
                           instroot = chroot)

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

    def getMountPoint(self):
        return self.mountpoint

    def getOptions(self):
        options = self.options
        if not options:
            options = self.fsystem.getDefaultOptions(self.mountpoint)
        return options + self.device.getDeviceOptions()

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

    def setResizeTarget (self, targetsize, size):
        if not self.fsystem.isResizable() and targetsize is not None:
            raise ValueError, "Can't set a resize target for a non-resizable filesystem"
        self.resizeTargetSize = targetsize
        self.resizeOrigSize = size

    def getResizeTarget (self):
        return self.resizeTargetSize

    def isMounted (self):
        return self.mountcount > 0

    def getLabel (self):
        return self.label

    def getUuid (self):
        return isys.readFSUuid(self.device.getDevice())

    def setLabel (self, label):
        self.label = label

    def __str__(self):
        if not self.mountpoint:
            mntpt = "None"
        else:
            mntpt = self.mountpoint

        str = ("fsentry -- device: %(device)s   mountpoint: %(mountpoint)s\n"
               "  fsystem: %(fsystem)s format: %(format)s\n"
               "  ismounted: %(mounted)s  options: '%(options)s'\n"
               "  label: %(label)s fsprofile: %(fsprofile)s\n"%
               {"device": self.device.getDevice(), "mountpoint": mntpt,
                "fsystem": self.fsystem.getName(), "format": self.format,
                "mounted": self.mountcount, "options": self.getOptions(),
                "label": self.label, "fsprofile": self.fsprofile})
        return str


class Device:
    def __init__(self, device = "none", encryption=None):
        self.device = device
        self.label = None
        self.isSetup = 0
        self.doLabel = 1
        self.deviceOptions = ""
        if encryption:
            self.crypto = encryption
            # mount by device since the name is based only on UUID
            self.doLabel = None
            if device not in ("none", None):
                self.crypto.setDevice(device)
        else:
            self.crypto = None

    def getComment (self):
        return ""

    def getDevice (self, asBoot = 0):
        if self.crypto:
            return self.crypto.getDevice()
        else:
            return self.device

    def setupDevice (self, chroot='/', devPrefix='/dev/'):
        return self.device

    def cleanupDevice (self, chroot, devPrefix='/dev/'):
        if self.crypto:
            self.crypto.closeDevice()

    def solidify (self):
        pass

    def getName(self):
        return self.__class__.__name__

    def getLabel(self):
        try:
            return isys.readFSLabel(self.setupDevice())
        except:
            return ""

    def setAsNetdev(self):
        """Ensure we're set up so that _netdev is in our device options."""
        if "_netdev" not in self.deviceOptions:
            self.deviceOptions += ",_netdev"

    def isNetdev(self):
        """Check to see if we're set as a netdev"""
        if "_netdev" in self.deviceOptions:
            return True
        return False

    def getDeviceOptions(self):
        return self.deviceOptions

class DevDevice(Device):
    """Device with a device node rooted in /dev that we just always use
       the pre-created device node for."""
    def __init__(self, dev):
        Device.__init__(self, device=dev)

    def getDevice(self, asBoot = 0):
        return self.device

    def setupDevice(self, chroot='/', devPrefix='/dev'):
        #We use precreated device but we have to make sure that the device exists
        path = '/dev/%s' % (self.getDevice(),)
        return path

class RAIDDevice(Device):
    # XXX usedMajors does not take in account any EXISTING md device
    #     on the system for installs.  We need to examine all partitions
    #     to investigate which minors are really available.
    usedMajors = {}

    # members is a list of Device based instances that will be
    # a part of this raid device
    def __init__(self, level, members, minor=-1, spares=0, existing=0,
                 chunksize = 64, encryption=None):
        Device.__init__(self, encryption=encryption)
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
            raise RuntimeError, ("you requested more spare devices "
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

        if self.crypto:
            self.crypto.setDevice(self.device)

        # make sure the list of raid members is sorted
        self.members.sort(cmp=lambda x,y: cmp(x.getDevice(),y.getDevice()))

    def __del__ (self):
        del RAIDDevice.usedMajors[self.minor]

    def ext2Args (self):
        if self.level == 5:
            return [ '-R', 'stride=%d' % ((self.numDisks - 1) * 16) ]
        elif self.level == 0:
            return [ '-R', 'stride=%d' % (self.numDisks * 16) ]
        return []

    def mdadmLine (self, devPrefix="/dev"):
        levels = { 0: "raid0",
                   1: "raid1",
                   4: "raid5",
                   5: "raid5",
                   6: "raid6",
                  10: "raid10" }

        # If we can't find the device for some reason, revert to old behavior.
        try:
            (dev, devices, level, numActive) = raid.lookup_raid_device (self.device)
        except KeyError:
            devices = []

        # First loop over all the devices that make up the RAID trying to read
        # the superblock off each.  If we read a superblock, return a line that
        # can go into the mdadm.conf.  If we fail, fall back to the old method
        # of using the super-minor.
        for d in devices:
            try:
                (major, minor, uuid, level, nrDisks, totalDisks, mdMinor) = \
                    isys.raidsb(d)
                return "ARRAY %s/%s level=%s num-devices=%d uuid=%s\n" \
                    %(devPrefix, self.device, levels[level], nrDisks, uuid)
            except ValueError:
               pass

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
        for device in [m.getDevice() for m in self.members[:self.numDisks]]:
            entry = entry + "    device	    %s/%s\n" % (devPrefix,
                                                        device)
            entry = entry + "    raid-disk     %d\n" % (i,)
            i = i + 1
        i = 0
        for device in [m.getDevice() for m in self.members[self.numDisks:]]:
            entry = entry + "    device	    %s/%s\n" % (devPrefix,
                                                        device)
            entry = entry + "    spare-disk     %d\n" % (i,)
            i = i + 1
        return entry

    def setupDevice (self, chroot="/", devPrefix='/dev'):
        if not self.isSetup:
            memberDevs = []
            for pd in self.members:
                memberDevs.append(pd.setupDevice(chroot, devPrefix=devPrefix))
                if pd.isNetdev(): self.setAsNetdev()

            args = ["--create", "/dev/%s" %(self.device,),
                    "--run", "--chunk=%s" %(self.chunksize,),
                    "--level=%s" %(self.level,),
                    "--raid-devices=%s" %(self.numDisks,)]

            if self.spares > 0:
                args.append("--spare-devices=%s" %(self.spares,),)

            args.extend(memberDevs)
            log.info("going to run: %s" %(["mdadm"] + args,))
            iutil.execWithRedirect ("mdadm", args,
                                    stderr="/dev/tty5", stdout="/dev/tty5",
                                    searchPath = 1)
            raid.register_raid_device(self.device,
                                      [m.getDevice() for m in self.members],
                                      self.level, self.numDisks)
            self.isSetup = 1
        else:
            isys.raidstart(self.device, self.members[0].getDevice())

        if self.crypto:
            self.crypto.formatDevice()
            self.crypto.openDevice()
            node = "%s/%s" % (devPrefix, self.crypto.getDevice())
        else:
            node = "%s/%s" % (devPrefix, self.device)

        return node

    def getDevice (self, asBoot = 0):
        if not asBoot and self.crypto:
            return self.crypto.getDevice()
        elif not asBoot:
            return self.device
        else:
            return self.members[0].getDevice(asBoot=asBoot)

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

    def setupDevice (self, chroot="/", devPrefix='/dev/'):
        nodes = []
        for volume in self.physicalVolumes:
            # XXX the lvm tools are broken and will only work for /dev
            node = volume.setupDevice(chroot, devPrefix="/dev")
            if volume.isNetdev(): self.setAsNetdev()

            # XXX I should check if the pv is set up somehow so that we
            # can have preexisting vgs and add new pvs to them.
            if not self.isSetup:
                lvm.pvcreate(node)
                nodes.append(node)

        if not self.isSetup:
            lvm.vgcreate(self.name, self.physicalextentsize, nodes)
            self.isSetup = 1
        else:
            lvm.vgscan()
            lvm.vgactivate()

        return "/dev/%s" % (self.name,)

    def solidify(self):
        return

class LogicalVolumeDevice(Device):
    # note that size is in megabytes!
    def __init__(self, vgname, size, lvname, vg, existing = 0, encryption=None):
        Device.__init__(self, encryption=encryption)
        self.vgname = vgname
        self.size = size
        self.name = lvname
        self.isSetup = 0
        self.isSetup = existing
        self.doLabel = None
        self.vg = vg

        # these are attributes we might want to expose.  or maybe not.
        # self.chunksize
        # self.stripes
        # self.stripesize
        # self.extents
        # self.readaheadsectors

    def setupDevice(self, chroot="/", devPrefix='/dev', vgdevice = None):
        if self.crypto:
            self.crypto.setDevice("mapper/%s-%s" % (self.vgname, self.name))

        if not self.isSetup:
            lvm.lvcreate(self.name, self.vgname, self.size)
            self.isSetup = 1

            if vgdevice and vgdevice.isNetdev():
                self.setAsNetdev()

        if self.crypto:
            self.crypto.formatDevice()
            self.crypto.openDevice()

        return "/dev/%s" % (self.getDevice(),)

    def getDevice(self, asBoot = 0):
        if self.crypto and not asBoot:
            device = self.crypto.getDevice()
        else:
            device = "%s/%s" % (self.vgname, self.name)

        return device

    def solidify(self):
        return


class PartitionDevice(Device):
    def __init__(self, partition, encryption=None):
        if type(partition) != types.StringType:
            raise ValueError, "partition must be a string"
        Device.__init__(self, device=partition, encryption=encryption)

        (disk, pnum) = getDiskPart(partition)
        if isys.driveIsIscsi(disk):
            self.setAsNetdev()

    def getDevice(self, asBoot = 0):
        if self.crypto and not asBoot:
            return self.crypto.getDevice()
        else:
            return self.device

    def setupDevice(self, chroot="/", devPrefix='/dev'):
        path = '%s/%s' % (devPrefix, self.device)
        if self.crypto:
            self.crypto.formatDevice()
            self.crypto.openDevice()
            path = "%s/%s" % (devPrefix, self.crypto.getDevice())
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

    def setupDevice (self, chroot="/", devPrefix='/dev'):
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

    def setupDevice(self, chroot="/", devPrefix='/dev'):
        return SwapFileDevice.setupDevice(self, self.piggypath, devPrefix)

class LoopbackDevice(Device):
    def __init__(self, hostPartition, hostFs):
        Device.__init__(self)
        self.host = "/dev/" + hostPartition
        self.hostfs = hostFs
        self.device = "loop1"

    def setupDevice(self, chroot="/", devPrefix='/dev/'):
        if not self.isSetup:
            isys.mount(self.host[5:], "/mnt/loophost", fstype = "vfat")
            self.device = allocateLoopback("/mnt/loophost/redhat.img")
            if not self.device:
                raise SystemError, "Unable to allocate loopback device"
            self.isSetup = 1
            path = '%s/%s' % (devPrefix, self.getDevice())
        else:
            path = '%s/%s' % (devPrefix, self.getDevice())
        path = os.path.normpath(path)
        return path

    def getComment (self):
        return "# LOOP1: %s %s /redhat.img\n" % (self.host, self.hostfs)

def makeDevice(dev):
    cryptoDev = partitions.lookup_cryptodev(dev)
    if cryptoDev and cryptoDev.getDevice() == dev:
        dev = cryptoDev.getDevice(encrypted=True)

    if dev.startswith('md'):
        try:
            (mdname, devices, level, numActive) = raid.lookup_raid_device(dev)
            # convert devices to Device instances and sort out encryption
            devList = []
            for dev in devices:
                cryptoMem = partitions.lookup_cryptodev(dev)
                if cryptoMem and cryptoMem.getDevice() == dev:
                    dev = cryptoMem.getDevice(encrypted=True)

                devList.append(PartitionDevice(dev, encryption=cryptoMem))

            device = RAIDDevice(level, devList,
                                minor=int(mdname[2:]),
                                spares=len(devices) - numActive,
                                existing=1, encryption=cryptoDev)
        except KeyError:
            device = PartitionDevice(dev, encryption=cryptoDev)
    else:
        device = PartitionDevice(dev, encryption=cryptoDev)
    return device

def findBackingDevInCrypttab(mappingName):
    backingDev = None
    try:
        lines = open("/mnt/sysimage/etc/crypttab").readlines()
    except IOError, e:
        pass
    else:
        for line in lines:
            fields = line.split()
            if len(fields) < 2:
                continue
            if fields[0] == mappingName:
                backingDev = fields[1]
                break

    return backingDev

# XXX fix RAID
def readFstab (anaconda):
    def createMapping(dict):
        mapping = {}
        dupes = []

        for device, info in dict.items():
            if not mapping.has_key(info):
                mapping[info] = device
            elif not info in dupes:
                dupes.append(info)

        return (mapping, dupes)

    def showError(label, intf):
        if intf:
            intf.messageWindow(_("Duplicate Labels"),
                               _("Multiple devices on your system are "
                                 "labelled %s.  Labels across devices must be "
                                 "unique for your system to function "
                                 "properly.\n\n"
                                 "Please fix this problem and restart the "
                                 "installation process.") %(label,),
                               type="custom", custom_icon="error",
                               custom_buttons=[_("_Exit installer")])
            sys.exit(0)
        else:
            log.warning("Duplicate labels for %s, but no intf so trying "
                        "to continue" %(label,))

    path = anaconda.rootPath + '/etc/fstab'
    intf = anaconda.intf
    fsset = FileSystemSet()

    # first, we look at all the disks on the systems and get any ext2/3
    # labels off of the filesystem.
    # temporary, to get the labels
    diskset = partedUtils.DiskSet(anaconda)
    diskset.openDevices()
    labels = diskset.getInfo()
    uuids = diskset.getInfo(readFn=lambda d: isys.readFSUuid(d))

    (labelToDevice, labelDupes) = createMapping(labels)
    (uuidToDevice, uuidDupes) = createMapping(uuids)

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
        # "none" is valid as an fs type for bind mounts (#151458)
        if fsystem is None and (string.find(fields[3], "bind") == -1):
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
            if label in labelDupes:
                showError(label, intf)

            if labelToDevice.has_key(label):
                device = makeDevice(labelToDevice[label])
            else:
                log.warning ("fstab file has LABEL=%s, but this label "
                             "could not be found on any file system", label)
                # bad luck, skip this entry.
                continue
        elif len(fields) >= 6 and fields[0].startswith('UUID='):
            uuid = fields[0][5:]
            if uuid in uuidDupes:
                showError(uuid, intf)

            if uuidToDevice.has_key(uuid):
                device = makeDevice(uuidToDevice[uuid])
            else:
                log.warning ("fstab file has UUID=%s, but this UUID"
                             "could not be found on any file system", uuid)
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
        elif fields[0].startswith("/dev/mapper/luks-"):
            backingDev = findBackingDevInCrypttab(fields[0][12:])
            log.debug("device %s has backing device %s" % (fields[0],
                                                           backingDev))
            if backingDev is None:
                log.error("unable to resolve backing device for %s" % fields[0])
                continue
            elif backingDev.startswith('LABEL='):
                label = backingDev[6:]
                if label in labelDupes:
                    showError(label, intf)

                if labelToDevice.has_key(label):
                    device = makeDevice(labelToDevice[label])
                else:
                    log.warning ("crypttab file has LABEL=%s, but this label "
                                 "could not be found on any file system", label)
                    # bad luck, skip this entry.
                    continue
            elif backingDev.startswith('UUID='):
                uuid = backingDev[5:]
                if uuid in uuidDupes:
                    showError(uuid, intf)

                if uuidToDevice.has_key(uuid):
                    device = makeDevice(uuidToDevice[uuid])
                else:
                    log.warning ("crypttab file has UUID=%s, but this UUID"
                                 "could not be found on any file system", uuid)
                    # bad luck, skip this entry.
                    continue
            else:
                device = makeDevice(backingDev[5:])
        elif fields[0].startswith('/dev/'):
            # Older installs may have lines starting with things like /dev/proc
            # so watch out for that on upgrade.
            if fsystem is not None and isinstance(fsystem, PseudoFileSystem):
                device = Device(device = fields[0][5:])
            else:
                device = makeDevice(fields[0][5:])
        else:
            device = Device(device = fields[0])

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

def allocateLoopback(file):
    found = 1
    for i in range(8):
        path = "/dev/loop%d" % (i,)
        try:
            isys.losetup(path, file)
            found = 1
        except SystemError:
            continue
        break
    if found:
        return path
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

        env = os.environ
        configs = [ "/tmp/updates/mke2fs.conf",
                    "/etc/mke2fs.conf",
                  ]
        for config in configs:
            if os.access(config, os.R_OK):
                env['MKE2FS_CONFIG'] = config
                break

        os.execvpe(argList[0], argList, env)
        log.critical("failed to exec %s", argList)
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
                num = ''
        except OSError, args:
            (errno, str) = args
            if (errno != 4):
                raise IOError, args

    try:
        (pid, status) = os.waitpid(childpid, 0)
    except OSError, (num, msg):
        log.critical("exception from waitpid while formatting: %s %s" %(num, msg))
        status = None
    os.close(fd)

    w and w.pop()

    # *shrug*  no clue why this would happen, but hope that things are fine
    if status is None:
        return 0

    if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
        return 0

    return 1

# copy and paste job from booty/bootloaderInfo.py...
def getDiskPart(dev):
    cut = len(dev)
    if (dev.startswith('rd/') or dev.startswith('ida/') or
            dev.startswith('cciss/') or dev.startswith('sx8/') or
            dev.startswith('mapper/') or dev.startswith('mmcblk')):
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
        partNum = int(dev[cut:]) - 1
    else:
        partNum = None

    return (name, partNum)
