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
import parted
from log import log
from translate import _, N_
import partitioning
import sys

defaultMountPoints = ('/', '/boot', '/home', '/tmp', '/usr', '/var')

fileSystemTypes = {}

availRaidLevels = ['RAID0', 'RAID1', 'RAID5']

def fileSystemTypeGetDefault():
    return fileSystemTypeGet('ext2')

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
    if device != "none":
        return "/dev/" + device
    return device

class LabelFactory:
    def __init__(self):
        self.labels = {}

    def createLabel(self, mountpoint):
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
        
    def mount(self, device, mountpoint, readOnly=0):
        if not self.isMountable():
            return
        iutil.mkdirChain(mountpoint)
        isys.mount(device, mountpoint, fstype = self.getName(), 
                   readOnly = readOnly)

    def umount(self, path):
        isys.umount(path, removeDir = 0)

    def getName(self):
        return self.name

    def registerDeviceArgumentFunction(self, klass, function):
        self.deviceArguments[klass] = function

    def formatDevice(self, devicePath, device, progress, message, chroot='/'):
        if self.isFormattable():
            raise RuntimeError, "formatDevice method not defined"

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

class reiserfsFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("reiserfs")
        self.formattable = 0
        self.checked = 1
        self.linuxnativefs = 1
        self.name = "reiserfs"
        self.maxSize = 4 * 1024 * 1024
        self.supported = 0
    
fileSystemTypeRegister(reiserfsFileSystem())

class extFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("ext2")
        self.formattable = 1
        self.checked = 1
        self.linuxnativefs = 1
        self.maxSize = 4 * 1024 * 1024

    def formatDevice(self, entry, progress, message, chroot='/'):
        devicePath = entry.device.setupDevice(chroot)
        devArgs = self.getDeviceArgs(entry.device)
        label = labelFactory.createLabel(entry.mountpoint)
        entry.setLabel(label)
        args = [ "/usr/sbin/mke2fs", devicePath, '-L', label ]
        args.extend(devArgs)
        args.extend(self.extraFormatArgs)

        rc = ext2FormatFilesystem(args, "/dev/tty5",
                                  progress,
                                  entry.mountpoint)
        if rc:
            message and message(_("Error"), 
                                _("An error occured trying to format %s. "
                                  "This problem is serious, and the install "
                                  "cannot continue.\n\n"
                                  "Press Enter to reboot your "
                                  "system.") % (entry.device.getDevice(),))
            raise SystemError
    

class ext2FileSystem(extFileSystem):
    def __init__(self):
        extFileSystem.__init__(self)
        self.name = "ext2"
        self.extraFormatArgs = []

fileSystemTypeRegister(ext2FileSystem())

class ext3FileSystem(extFileSystem):
    def __init__(self):
        extFileSystem.__init__(self)
        self.name = "ext3"
        self.extraFormatArgs = [ "-j" ]

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

fileSystemTypeRegister(ext3FileSystem())

class raidMemberDummyFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("ext2")
        self.partedPartitionFlags = [ parted.PARTITION_RAID ]
        self.formattable = 1
        self.checked = 0
        self.linuxnativefs = 0
        self.name = "software raid component"
        self.maxSize = 4 * 1024 * 1024
        self.supported = 1

    def formatDevice(self, entry, progress, message, chroot='/'):
        # mkraid did all we need to format this partition...
        pass
    
fileSystemTypeRegister(raidMemberDummyFileSystem())

class swapFileSystem(FileSystemType):
    enabledSwaps = {}
    
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("linux-swap")
        self.formattable = 1
        self.name = "swap"
        self.maxSize = 2 * 1024
        self.supported = 1

    def mount(self, device, mountpoint):
        isys.swapon (device)

    def umount(self, device, path):
        # unfortunately, turning off swap is bad.
        pass
    
    def formatDevice(self, entry, progress, message, chroot='/'):
        file = entry.device.setupDevice(chroot)
        rc = iutil.execWithRedirect ("/usr/sbin/mkswap",
                                     [ "mkswap", '-v1', file ],
                                     stdout = None, stderr = None,
                                     searchPath = 1)

fileSystemTypeRegister(swapFileSystem())

class FATFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.partedFileSystemType = parted.file_system_type_get("FAT")
        self.formattable = 0
        self.checked = 0
        self.name = "vfat"

fileSystemTypeRegister(FATFileSystem())

class ForeignFileSystem(FileSystemType):
    def __init__(self):
        FileSystemType.__init__(self)
        self.formattable = 0
        self.checked = 0
        self.name = "foreign"

    def formatDevice(self, entry, progress, message, chroot='/'):
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

class FileSystemSet:
    def __init__(self):
        self.messageWindow = None
        self.progressWindow = None
        self.reset()
        
    def registerMessageWindow(self, method):
        self.messageWindow = method
        
    def registerProgressWindow(self, method):
        self.progressWindow = method

    def reset (self):
        self.entries = []
        proc = FileSystemSetEntry(Device(), '/proc', fileSystemTypeGet("proc"))
        self.add(proc)
        pts = FileSystemSetEntry(Device(), '/dev/pts',
                                 fileSystemTypeGet("devpts"), "gid=5,mode=620")
        self.add(pts)

    def add (self, entry):
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
	format = "%-23s %-23s %-7s %-15s %d %d\n";
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
            f = open (prefix + "/etc/fstab", "w")
            f.write (raidtab)
            f.close ()

        # touch mtab
        open (prefix + "/etc/mtab", "w+")
        f.close ()

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

	if mntDict.has_key("/boot"):
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

    def formatSwap (self, chroot):
        for entry in self.entries:
            if (entry.fsystem and entry.fsystem.getName() == "swap"
                and entry.getFormat()):
                entry.fsystem.formatDevice(entry, self.progressWindow,
                                           self.messageWindow, chroot)
                
    def turnOnSwap (self, chroot):
        for entry in self.entries:
            if entry.fsystem and entry.fsystem.getName() == "swap":
                entry.mount(chroot)

    def turnOffSwap(self, devices = 1, files = 0):
        for entry in self.entries:
            if entry.fsystem and entry.fsystem.getName() == "swap":
                entry.umount(chroot)

    def formattablePartitions(self):
        list = []
        for entry in self.entries:
            if entry.fsystem.isFormattable():
                list.append (entry)
        return list

    def makeFilesystems (self, chroot='/'):
        for entry in self.entries:
            if (not entry.fsystem.isFormattable() or not entry.getFormat()
                or entry.isMounted()):
                continue
            entry.fsystem.formatDevice(entry, self.progressWindow,
                                       self.messageWindow, chroot)

    def mountFilesystems(self, instPath = '/', raiseErrors = 0, readOnly = 0):
	for entry in self.entries:
            if not entry.fsystem.isMountable():
		continue
            try:
                entry.mount(instPath)
            except SystemError, (errno, msg):
                if raiseErrors:
                    raise SystemError, (errno, msg)
                self.messageWindow and self.messageWindow(_("Error"), 
                    _("Error mounting device %s as %s: %s\n\n"
                      "This most likely means this partition has "
                      "not been formatted.\n\nPress OK to reboot your "
                      "system.") % (entry.device.getDevice(),
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
                  order=-1, fsck=-1, format=0):
        if not fsystem:
            fsystem = fileSystemTypeGet("ext2")
        self.device = device
        self.mountpoint = mountpoint
        self.fsystem = fsystem
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

    def mount(self, chroot='/', devPrefix='/tmp'):
        device = self.device.setupDevice(chroot, devPrefix=devPrefix) 
        self.fsystem.mount(device, "%s/%s" % (chroot, self.mountpoint))
        self.mountcount = self.mountcount + 1

    def umount(self, chroot='/'):
        if self.mountcount > 0:
            self.fssytem.umount(self.device, "%s/%s" % (chroot,
                                                        self.mountpoint))
            self.mountcount = self.mountcount - 1
        
    def setFormat (self, state):
        self.format = state

    def getFormat (self):
        return self.format

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

    def __repr__(self):
        return self.device

    def getComment (self):
        return ""

    def getDevice (self):
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
                raise RuntimeError, ("Unable to allocate minor number for "
                                     "raid device")
            minor = I
        RAIDDevice.usedMajors[minor] = None
        self.device = "md" + str(minor)
        self.minor = minor

    def __del__ (self):
        RAIDDevice.usedMajors.remove(minor)

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
                                                        device.getDevice())
            entry = entry + "    raid-disk     %d\n" % (i,)
            i = i + 1
        i = 0
        for device in self.members[self.numDisks:]:
            entry = entry + "    device	    %s/%s\n" % (devPrefix,
                                                        device.getDevice())
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
                device.setupDevice(chroot, devPrefix=devPrefix)
            iutil.execWithRedirect ("/usr/sbin/mkraid", 
                                    ( 'mkraid', '--really-force',
                                      '--configfile', raidtab, node ),
                                    stderr = "/dev/tty5", stdout = "/dev/tty5")
            self.isSetup = 1
        return node

    def solidify(self):
        for device in self.members:
            device.solidify()
        
ext2 = fileSystemTypeGet("ext2")
ext2.registerDeviceArgumentFunction(RAIDDevice, RAIDDevice.ext2Args)

class LVMDevice(Device):
    def __init__(self):
        Device.__init__(self)
    
class PartitionDevice(Device):
    def __init__(self, partition):
        Device.__init__(self)
        self.device = partition

    def setupDevice(self, chroot, devPrefix='/tmp'):
        path = '%s/%s' % (devPrefix, self.getDevice(),)
        isys.makeDevInode(self.getDevice(), path)
        return path

class PartedPartitionDevice(PartitionDevice):
    def __init__(self, partition):
        PartitionDevice.__init__(self, None)
        self.partition = partition

    def getDevice(self):
        if not self.partition:
            return self.device
        
        if (self.partition.geom.disk.dev.type == parted.DEVICE_DAC960
            or self.partition.geom.disk.dev.type == parted.DEVICE_CPQARRAY):
            return "%sp%d" % (self.partition.geom.disk.dev.path[5:],
                              self.partition.num)
        return "%s%d" % (self.partition.geom.disk.dev.path[5:],
                         self.partition.num)

    def solidify(self):
        # drop reference on the parted partition object and note
        # the current minor number allocation
        self.device = self.getDevice()
        self.partition = None
        
class SwapFileDevice(Device):
    def __init__(self, file):
        Device.__init__(self)
        self.device = file
        self.device.size = 0

    def setSize (self, size):
        self.size = size

    def setupDevice (self, chroot, devPrefix='/tmp'):
        file = os.path.normpath(chroot + self.getDevice())
        if not os.access(file, os.R_OK):
            if self.size:
                isys.ddfile(file, self.size, None)
            else:
                raise SystemError, ("swap file creation necessary, but "
                                    "required size is unknown.")
        return file

class LoopbackDevice(Device):
    def __init__(self, hostPartition, hostFs):
        Device.__init__(self)
        self.host = "/dev/" + hostPartition
        self.hostfs = hostFs
        self.device = "loop1"

    def getComment (self):
        return "# LOOP1: %s %s /redhat.img\n" % (self.host, self.hostfs)

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

        if not fileSystemTypes.has_key(fields[2]):
	    continue
	if string.find(fields[3], "noauto") != -1: continue

        fsystem = fileSystemTypeGet(fields[2])
        label = None
	if len(fields) >= 6 and fields[0][:6] == "LABEL=":
            label = fields[0][6:]
            if labelToDevice.has_key(label):
                device = PartitionDevice(labelToDevice[label])
            else:
                log ("Warning: fstab file has LABEL=%s, but this label "
                     "could not be found on any filesystem", label)
                # bad luck, skip this entry.
                continue
	elif (fields[2] == "swap" and fields[0][:5] != "/dev/"):
	    # swap files
	    file = fields[0]

	    # the loophost looks like /mnt/loophost to the install, not
	    # like /initrd/loopfs
	    if file[:15] == "/initrd/loopfs/":
		file = "/mnt/loophost/" + file[14:]

	    device = SwapFileDevice(file)
        elif fields[0][:9] == "/dev/loop":
	    # look up this loop device in the index to find the
            # partition that houses the filesystem image
            # XXX currently we assume /dev/loop1
	    if loopIndex.has_key(device):
		(dev, fs) = loopIndex[device]
                device = LoopbackDevice(dev, fs)
	else:
            device = PartitionDevice(fields[0][5:])
            
        entry = FileSystemSetEntry(device, fields[1], fsystem, fields[3])
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
                if num:
                    l = string.split(num, '/')
                    w and w.set((int(l[0]) * 100) / int(l[1]))
                    isys.sync()
                num = ''
        except OSError, args:
            (num, str) = args
            if (num != 4):
                raise IOError, args

    try:
        (pid, status) = os.waitpid(childpid, 0)
    except OSError, (errno, msg):
        print __name__, "waitpid:", msg
    os.close(fd)

    w and w.pop()

    if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
	return 0

    return 1

def enabledSwapDict():
    # returns a dict of swap areas currently being used
    f = open("/proc/swaps", "r")
    lines = f.readlines()
    f.close()

    # the first line is header
    lines = lines[1:]

    swaps = {}
    for line in lines:
	l = string.split(line)
	swaps[l[0]] = 1

    return swaps

if __name__ == "__main__":
    import sys
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
