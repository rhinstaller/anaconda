#
# bootloaderInfo.py - bootloader config object used in creation of new
#                     bootloader configs.  Originally from anaconda
#
# Jeremy Katz <katzj@redhat.com>
# Erik Troan <ewt@redhat.com>
# Peter Jones <pjones@redhat.com>
#
# Copyright 2005-2008 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os, sys
import crypt
import random
import shutil
import string
import struct
from copy import copy

from lilo import LiloConfigFile
import rhpl
from rhpl.translate import _, N_

from flags import flags
from fsset import getDiskPart
import iutil
from product import *

import booty
import checkbootloader

if rhpl.getArch() not in ("s390", "s390x"):
    import block

dosFilesystems = ('FAT', 'fat16', 'fat32', 'ntfs', 'hpfs')

def doesDualBoot():
    if rhpl.getArch() == "i386" or rhpl.getArch() == "x86_64":
        return 1
    return 0

def checkForBootBlock(device):
    fd = os.open(device, os.O_RDONLY)
    buf = os.read(fd, 512)
    os.close(fd)
    if len(buf) >= 512 and \
           struct.unpack("H", buf[0x1fe: 0x200]) == (0xaa55,):
        return True
    return False

# hack and a half
# there's no guarantee that data is written to the disk and grub
# reads both the filesystem and the disk.  suck.
def syncDataToDisk(dev, mntpt, instRoot = "/"):
    import isys
    isys.sync()
    isys.sync()
    isys.sync()

    # and xfs is even more "special" (#117968)
    if isys.readFSType(dev) == "xfs":
        iutil.execWithRedirect("/usr/sbin/xfs_freeze",
                               ["/usr/sbin/xfs_freeze", "-f", mntpt],
                               stdout = "/dev/tty5",
                               stderr = "/dev/tty5",
                               root = instRoot)
        iutil.execWithRedirect("/usr/sbin/xfs_freeze",
                               ["/usr/sbin/xfs_freeze", "-u", mntpt],
                               stdout = "/dev/tty5",
                               stderr = "/dev/tty5",
                               root = instRoot)    

def rootIsDevice(dev):
    if dev.startswith("LABEL=") or dev.startswith("UUID="):
        return False
    return True

# hackery to determine if we should do root=LABEL=/ or whatnot
# as usual, knows too much about anaconda
def getRootDevName(initrd, fsset, rootDev, instRoot):
    if not os.access(instRoot + initrd, os.R_OK):
        return "/dev/%s" % (rootDev,)

    try:
        rootEntry = fsset.getEntryByMountPoint("/")
        if rootEntry.getUuid() is not None:
            return "UUID=%s" %(rootEntry.getUuid(),)
        elif rootEntry.getLabel() is not None and rootEntry.device.doLabel is not None:
            return "LABEL=%s" %(rootEntry.getLabel(),)
        return "/dev/%s" %(rootDev,)
    except:
        return "/dev/%s" %(rootDev,)

class BootyNoKernelWarning:
    def __init__ (self, value=""):
        self.value = value
        
    def __str__ (self):
        return self.value

class KernelArguments:

    def get(self):
        return self.args

    def set(self, args):
        self.args = args

    def chandevget(self):
        return self.cargs

    def chandevset(self, args):
        self.cargs = args

    def append(self, args):
        if self.args:
            # don't duplicate the addition of an argument (#128492)
            if self.args.find(args) != -1:
                return
            self.args = self.args + " "
        self.args = self.args + "%s" % (args,)
        

    def __init__(self):
        newArgs = []
        cfgFilename = "/tmp/install.cfg"

        if rhpl.getArch() == "s390":
            self.cargs = []
            f = open(cfgFilename)
            for line in f:
                try:
                    (vname,vparm) = line.split('=', 1)
                    vname = vname.strip()
                    vparm = vparm.replace('"','')
                    vparm = vparm.strip()
                    if vname == "DASD":
                        newArgs.append("dasd=" + vparm)
                    if vname == "CHANDEV":
                        self.cargs.append(vparm)
                    if vname == "QETHPARM":
                        self.cargs.append(vparm)
                except Exception, e:
                    pass
            f.close()

        # look for kernel arguments we know should be preserved and add them
        ourargs = ["speakup_synth", "apic", "noapic", "apm", "ide", "noht",
                   "acpi", "video", "pci", "nodmraid", "nompath"]
        for arg in ourargs:
            if not flags.cmdline.has_key(arg):
                continue

            val = flags.cmdline.get(arg, "")
            if val:
                newArgs.append("%s=%s" % (arg, val))
            else:
                newArgs.append(arg)

        self.args = " ".join(newArgs)


class BootImages:
    """A collection to keep track of boot images available on the system.
    Examples would be:
    ('linux', 'Red Hat Linux', 'ext2'),
    ('Other', 'Other', 'fat32'), ...
    """
    def __init__(self):
        self.default = None
        self.images = {}

    def getImages(self):
        """returns dictionary of (label, longlabel, devtype) pairs 
        indexed by device"""
        # return a copy so users can modify it w/o affecting us
        return copy(self.images)


    def setImageLabel(self, dev, label, setLong = 0):
        orig = self.images[dev]
        if setLong:
            self.images[dev] = (orig[0], label, orig[2])
        else:
            self.images[dev] = (label, orig[1], orig[2])            
            
    def setDefault(self, default):
        # default is a device
        self.default = default

    def getDefault(self):
        return self.default

    # XXX this has internal anaconda-ish knowledge.  ick 
    def setup(self, diskSet, fsset):
        devices = {}
        devs = self.availableBootDevices(diskSet, fsset)
        for (dev, type) in devs:
            devices[dev] = 1

        # These partitions have disappeared
        for dev in self.images.keys():
            if not devices.has_key(dev): del self.images[dev]

        # These have appeared
        for (dev, type) in devs:
            if not self.images.has_key(dev):
                if type in dosFilesystems and doesDualBoot():
                    self.images[dev] = ("Other", "Other", type)
                elif type in ("hfs", "hfs+") and rhpl.getPPCMachine() == "PMac":
                    self.images[dev] = ("Other", "Other", type)
                else:
                    self.images[dev] = (None, None, type)


        if not self.images.has_key(self.default):
            entry = fsset.getEntryByMountPoint('/')
            self.default = entry.device.getDevice()
            (label, longlabel, type) = self.images[self.default]
            if not label:
                self.images[self.default] = ("linux", productName, type)

    # XXX more internal anaconda knowledge
    def availableBootDevices(self, diskSet, fsset):
        devs = []
        foundDos = 0
        for (dev, type) in diskSet.partitionTypes():
            if type in dosFilesystems and not foundDos and doesDualBoot():
                try:
                    bootable = checkForBootBlock('/dev/' + dev)
                    devs.append((dev, type))
                    foundDos = 1
                except Exception, e:
                    pass
            elif ((type == 'ntfs' or type =='hpfs') and not foundDos
                  and doesDualBoot()):
                devs.append((dev, type))
                # maybe questionable, but the first ntfs or fat is likely to
                # be the correct one to boot with XP using ntfs
                foundDos = 1
            elif type in ('hfs', 'hfs+') and rhpl.getPPCMachine() == "PMac":
                import _ped

                for disk in diskset.disks:
                    part = disk.getPartitionByPath('/dev/' + dev)
                    if part:
                        if not part.getFlag(_ped.PARTITION_BOOT):
                            devs.append((dev, type))
                        break

        slash = fsset.getEntryByMountPoint('/')
        if not slash or not slash.device or not slash.fsystem:
            raise ValueError, ("Trying to pick boot devices but do not have a "
                               "sane root partition.  Aborting install.")
        devs.append((slash.device.getDevice(), slash.fsystem.getName()))

        devs.sort()

        return devs



class bootloaderInfo:
    def getConfigFileName(self):
        if not self._configname:
            raise NotImplementedError
        return self._configname
    configname = property(getConfigFileName, None, None, \
                          "bootloader config file name")

    def getConfigFileDir(self):
        if not self._configdir:
            raise NotImplementedError
        return self._configdir
    configdir = property(getConfigFileDir, None, None, \
                         "bootloader config file directory")

    def getConfigFilePath(self):
        return "%s/%s" % (self.configdir, self.configname)
    configfile = property(getConfigFilePath, None, None, \
                          "full path and name of the real config file")

    def setUseGrub(self, val):
        pass

    def useGrub(self):
        return self.useGrubVal

    def setForceLBA(self, val):
        pass
    
    def setPassword(self, val, isCrypted = 1):
        pass

    def getPassword(self):
        pass

    def getDevice(self):
        return self.device

    def setDevice(self, device):
        self.device = device

        (dev, part) = getDiskPart(device)
        if part is None:
            self.defaultDevice = "mbr"
        else:
            self.defaultDevice = "partition"

    def makeInitrd(self, kernelTag):
        return "/boot/initrd%s.img" % kernelTag

    # XXX need to abstract out the requirement for a fsset to be able
    # to get it "on the fly" on a running system as well as being able
    # to get it how we do now from anaconda.  probably by having the
    # first thing in the chain create a "fsset" object that has the
    # dictionary of mounted filesystems since that's what we care about
    def getBootloaderConfig(self, instRoot, fsset, bl, kernelList,
                            chainList, defaultDev):
        images = bl.images.getImages()

        # on upgrade read in the lilo config file
        lilo = LiloConfigFile ()
        self.perms = 0600
        if os.access (instRoot + self.configfile, os.R_OK):
            self.perms = os.stat(instRoot + self.configfile)[0] & 0777
            lilo.read (instRoot + self.configfile)
            os.rename(instRoot + self.configfile,
                      instRoot + self.configfile + '.rpmsave')
        # if it's an absolute symlink, just get it out of our way
        elif (os.path.islink(instRoot + self.configfile) and
              os.readlink(instRoot + self.configfile)[0] == '/'):
            os.rename(instRoot + self.configfile,
                      instRoot + self.configfile + '.rpmsave')            

        # Remove any invalid entries that are in the file; we probably
        # just removed those kernels. 
        for label in lilo.listImages():
            (fsType, sl, path, other) = lilo.getImage(label)
            if fsType == "other": continue

            if not os.access(instRoot + sl.getPath(), os.R_OK):
                lilo.delImage(label)

        lilo.addEntry("prompt", replace = 0)
        lilo.addEntry("timeout", self.timeout or "20", replace = 0)

        rootDev = fsset.getEntryByMountPoint("/").device.getDevice()
        if not rootDev:
            raise RuntimeError, "Installing lilo, but there is no root device"

        if rootDev == defaultDev:
            lilo.addEntry("default", kernelList[0][0])
        else:
            lilo.addEntry("default", chainList[0][0])

        for (label, longlabel, version) in kernelList:
            kernelTag = "-" + version
            kernelFile = self.kernelLocation + "vmlinuz" + kernelTag

            try:
                lilo.delImage(label)
            except IndexError, msg:
                pass

            sl = LiloConfigFile(imageType = "image", path = kernelFile)

            initrd = self.makeInitrd(kernelTag)

            sl.addEntry("label", label)
            if os.access (instRoot + initrd, os.R_OK):
                sl.addEntry("initrd", "%sinitrd%s.img" %(self.kernelLocation,
                                                         kernelTag))
                
            sl.addEntry("read-only")

            append = "%s" %(self.args.get(),)
            realroot = getRootDevName(initrd, fsset, rootDev, instRoot)
            if rootIsDevice(realroot):
                sl.addEntry("root", '/dev/' + rootDev)
            else:
                if len(append) > 0:
                    append = "%s root=%s" %(append,realroot)
                else:
                    append = "root=%s" %(realroot,)
            
            if len(append) > 0:
                sl.addEntry('append', '"%s"' % (append,))
                
            lilo.addImage (sl)

        for (label, longlabel, device) in chainList:
            if ((not label) or (label == "")):
                continue
            try:
                (fsType, sl, path, other) = lilo.getImage(label)
                lilo.delImage(label)
            except IndexError:
                sl = LiloConfigFile(imageType = "other",
                                    path = "/dev/%s" %(device))
                sl.addEntry("optional")

            sl.addEntry("label", label)
            lilo.addImage (sl)

        # Sanity check #1. There could be aliases in sections which conflict
        # with the new images we just created. If so, erase those aliases
        imageNames = {}
        for label in lilo.listImages():
            imageNames[label] = 1

        for label in lilo.listImages():
            (fsType, sl, path, other) = lilo.getImage(label)
            if sl.testEntry('alias'):
                alias = sl.getEntry('alias')
                if imageNames.has_key(alias):
                    sl.delEntry('alias')
                imageNames[alias] = 1

        # Sanity check #2. If single-key is turned on, go through all of
        # the image names (including aliases) (we just built the list) and
        # see if single-key will still work.
        if lilo.testEntry('single-key'):
            singleKeys = {}
            turnOff = 0
            for label in imageNames.keys():
                l = label[0]
                if singleKeys.has_key(l):
                    turnOff = 1
                singleKeys[l] = 1
            if turnOff:
                lilo.delEntry('single-key')

        return lilo

    def write(self, instRoot, fsset, bl, kernelList, chainList,
            defaultDev, justConfig, intf = None):
        if len(kernelList) >= 1:
            config = self.getBootloaderConfig(instRoot, fsset, bl,
                                              kernelList, chainList,
                                              defaultDev)
            config.write(instRoot + self.configfile, perms = self.perms)
        else:
            self.noKernelsWarn(intf)

        return ""

    # XXX in the future we also should do some validation on the config
    # file that's already there
    # XXX concept of the intf isn't very well defined outside of anaconda...
    # probably should just pass back up an error
    def noKernelsWarn(self, intf):
        raise BootyNoKernelWarning

    def getArgList(self):
        args = []

        if self.defaultDevice is None:
            args.append("--location=none")
            return args

        args.append("--location=%s" % (self.defaultDevice,))
        args.append("--driveorder=%s" % (",".join(self.drivelist)))

        if self.args.get():
            args.append("--append=\"%s\"" %(self.args.get()))

        return args

    def writeKS(self, f):
        f.write("bootloader")
        for arg in self.getArgList():
            f.write(" " + arg)
        f.write("\n")

    def createDriveList(self):
        # create a drive list that we can use for drive mappings
        # XXX has anaconda internals knowledge
        import isys
        drives = isys.hardDriveDict().keys()
        drives.sort(isys.compareDrives)

        # now filter out all of the drives without media present
        drives = filter(lambda x: isys.mediaPresent(x), drives)

        return drives

    def updateDriveList(self, sortedList=[]):
        self._drivelist = self.createDriveList()

        # If we're given a sort order, make sure the drives listed in it
        # are put at the head of the drivelist in that order.  All other
        # drives follow behind in whatever order they're found.
        if sortedList != []:
            revSortedList = sortedList
            revSortedList.reverse()

            for i in revSortedList:
                try:
                    ele = self._drivelist.pop(self._drivelist.index(i))
                    self._drivelist.insert(0, ele)
                except:
                    pass

    def _getDriveList(self):
        if self._drivelist is not None:
            return self._drivelist
        self.updateDriveList()
        return self._drivelist
    def _setDriveList(self, val):
        self._drivelist = val
    drivelist = property(_getDriveList, _setDriveList)

    def __init__(self):
        self.args = KernelArguments()
        self.images = BootImages()
        self.device = None
        self.defaultDevice = None  # XXX hack, used by kickstart
        self.useGrubVal = 0      # only used on x86
        self._configdir = None
        self._configname = None
        self.kernelLocation = "/boot/"
        self.forceLBA32 = 0
        self.password = None
        self.pure = None
        self.above1024 = 0
        self.timeout = None

        # this has somewhat strange semantics.  if 0, act like a normal
        # "install" case.  if 1, update lilo.conf (since grubby won't do that)
        # and then run lilo or grub only.
        # XXX THIS IS A HACK.  implementation details are only there for x86
        self.doUpgradeOnly = 0
        self.kickstart = 0

        self._drivelist = None

        if flags.serial != 0:
            options = ""
            device = ""
            console = flags.get("console", "")

            # the options are everything after the comma
            comma = console.find(",")
            if comma != -1:
                options = console[comma:]
                device = console[:comma]
            else:
                device = console

            if not device and rhpl.getArch() != "ia64":
                self.serialDevice = "ttyS0"
                self.serialOptions = ""
            else:
                self.serialDevice = device
                # don't keep the comma in the options
                self.serialOptions = options[1:]

            if self.serialDevice:
                self.args.append("console=%s%s" %(self.serialDevice, options))
                self.serial = 1
                self.timeout = 5
        else:
            self.serial = 0
            self.serialDevice = None
            self.serialOptions = None

        if flags.virtpconsole is not None:
            if flags.virtpconsole.startswith("/dev/"):
                con = flags.virtpconsole[5:]
            else:
                con = flags.virtpconsole
            self.args.append("console=%s" %(con,))

class efiBootloaderInfo(bootloaderInfo):
    def getBootloaderName(self):
        return self._bootloader
    bootloader = property(getBootloaderName, None, None, \
                          "name of the bootloader to install")

    # XXX wouldn't it be nice to have a real interface to use efibootmgr from?
    def removeOldEfiEntries(self, instRoot):
        p = os.pipe()
        iutil.execWithRedirect('/usr/sbin/efibootmgr', ["efibootmgr"],
                               root = instRoot, stdout = p[1])
        os.close(p[1])

        c = os.read(p[0], 1)
        buf = c
        while (c):
            c = os.read(p[0], 1)
            buf = buf + c
        os.close(p[0])
        lines = string.split(buf, '\n')
        for line in lines:
            fields = string.split(line)
            if len(fields) < 2:
                continue
            if string.join(fields[1:], " ") == productName:
                entry = fields[0][4:8]
                iutil.execWithRedirect('/usr/sbin/efibootmgr',
                                       ["efibootmgr", "-b", entry, "-B"],
                                       root = instRoot,
                                       stdout="/dev/tty5", stderr="/dev/tty5")

    def addNewEfiEntry(self, instRoot, fsset):
        bootdev = fsset.getEntryByMountPoint("/boot/efi").device.getDevice()
        if not bootdev:
            bootdev = fsset.getEntryByDeviceName("sda1").device.getDevice()

        link = "%s%s/%s" % (instRoot, "/etc/", self.configname)
        if not os.access(link, os.R_OK):
            os.symlink("../%s" % (self.configfile), link)

        ind = len(bootdev)
        try:
            while (bootdev[ind-1] in string.digits):
                ind = ind - 1
        except IndexError:
            ind = len(bootdev) - 1
            
        bootdisk = bootdev[:ind]
        bootpart = bootdev[ind:]
        if (bootdisk.startswith('ida/') or bootdisk.startswith('cciss/') or
            bootdisk.startswith('rd/') or bootdisk.startswith('sx8/')):
            bootdisk = bootdisk[:-1]

        argv = [ "/usr/sbin/efibootmgr", "-c" , "-w", "-L",
                 productName, "-d", "/dev/%s" % bootdisk,
                 "-p", bootpart, "-l", "\\EFI\\redhat\\" + self.bootloader ]
        iutil.execWithRedirect(argv[0], argv, root = instRoot,
                               stdout = "/dev/tty5",
                               stderr = "/dev/tty5")

    def installGrub(self, instRoot, bootDevs, grubTarget, grubPath, fsset,
                    target, cfPath):
        if not iutil.isEfi():
            raise EnvironmentError
        self.removeOldEfiEntries(instRoot)
        self.addNewEfiEntry(instRoot, fsset)

    def __init__(self, initialize = True):
        if initialize:
            bootloaderInfo.__init__(self)
        if iutil.isEfi():
            self._configdir = "/boot/efi/EFI/redhat"
            self._configname = "grub.conf"
            self._bootloader = "grub.efi"
            self.useGrubVal = 1
            self.kernelLocation = ""
