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
#from rhpl.log import log
from rhpl.translate import _, N_
import rhpl.executil

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
        rhpl.executil.execWithRedirect( "/usr/sbin/xfs_freeze",
                                        ["/usr/sbin/xfs_freeze", "-f", mntpt],
                                        stdout = "/dev/tty5",
                                        stderr = "/dev/tty5",
                                        root = instRoot)
        rhpl.executil.execWithRedirect( "/usr/sbin/xfs_freeze",
                                        ["/usr/sbin/xfs_freeze", "-u", mntpt],
                                        stdout = "/dev/tty5",
                                        stderr = "/dev/tty5",
                                        root = instRoot)    

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
                    #log("exception parsing %s: %s" % (cfgFilename, e))
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
                import isys
                import partedUtils
                
                part = partedUtils.get_partition_by_name(diskSet.disks, dev)
                if part.native_type not in partedUtils.dosPartitionTypes:
                    continue

                try:
                    bootable = checkForBootBlock('/dev/' + dev)
                    devs.append((dev, type))
                    foundDos = 1
                except Exception, e:
                    #log("exception checking %s: %s" %(dev, e))
                    pass
            elif ((type == 'ntfs' or type =='hpfs') and not foundDos
                  and doesDualBoot()):
                devs.append((dev, type))
                # maybe questionable, but the first ntfs or fat is likely to
                # be the correct one to boot with XP using ntfs
                foundDos = 1
            elif type in ('hfs', 'hfs+') and rhpl.getPPCMachine() == "PMac":
                import isys
                import partedUtils

                part = partedUtils.get_partition_by_name(diskSet.disks, dev)
                if partedUtils.get_flags(part) != "boot":
                    devs.append((dev, type))

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
    def getBootloaderConfig(self, instRoot, fsset, bl, langs, kernelList,
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

    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
            defaultDev, justConfig, intf = None):
        if len(kernelList) >= 1:
            config = self.getBootloaderConfig(instRoot, fsset, bl, langs,
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


class grubBootloaderInfo(bootloaderInfo):
    def setPassword(self, val, isCrypted = 1):
        if not val:
            self.password = val
            self.pure = val
            return
        
        if isCrypted and self.useGrubVal == 0:
            #log("requested crypted password with lilo; ignoring")
            self.pure = None
            return
        elif isCrypted:
            self.password = val
            self.pure = None
        else:
            salt = "$1$"
            saltLen = 8

            saltchars = string.letters + string.digits + './'
            for i in range(saltLen):
                salt += random.choice(saltchars)

            self.password = crypt.crypt(val, salt)
            self.pure = val
        
    def getPassword (self):
        return self.pure

    def setForceLBA(self, val):
        self.forceLBA32 = val
        
    def setUseGrub(self, val):
        self.useGrubVal = val

    def getPhysicalDevices(self, device):
        # This finds a list of devices on which the given device name resides.
        # Accepted values for "device" are raid1 md devices (i.e. "md0"),
        # physical disks ("hda"), and real partitions on physical disks
        # ("hda1").  Volume groups/logical volumes are not accepted.
        # 
        # XXX this has internal anaconda-ish knowledge.  ick.
        import isys
        import lvm

        if string.split(device, '/', 1)[0] in map (lambda vg: vg[0],
                                                   lvm.vglist()):
            return []
    
        if device.startswith("mapper/luks-"):
            return []

        if device.startswith('md'):
            bootable = 0
            parts = checkbootloader.getRaidDisks(device, 1, stripPart=0)
            parts.sort()
            return parts

        return [device]

    def runGrubInstall(self, instRoot, bootDev, cmds, cfPath):
        #log("GRUB commands:")
        #for cmd in cmds:
        #    log("\t%s\n", cmd)
        if cfPath == "/":
            syncDataToDisk(bootDev, "/boot", instRoot)
        else:
            syncDataToDisk(bootDev, "/", instRoot)

        # copy the stage files over into /boot
        rhpl.executil.execWithRedirect( "/sbin/grub-install",
                                    ["/sbin/grub-install", "--just-copy"],
                                    stdout = "/dev/tty5", stderr = "/dev/tty5",
                                    root = instRoot)

        # really install the bootloader
        for cmd in cmds:
            p = os.pipe()
            os.write(p[1], cmd + '\n')
            os.close(p[1])
            import time

            # FIXME: hack to try to make sure everything is written
            #        to the disk
            if cfPath == "/":
                syncDataToDisk(bootDev, "/boot", instRoot)
            else:
                syncDataToDisk(bootDev, "/", instRoot)

            rhpl.executil.execWithRedirect('/sbin/grub' ,
                                    [ "grub",  "--batch", "--no-floppy",
                                      "--device-map=/boot/grub/device.map" ],
                                    stdin = p[0],
                                    stdout = "/dev/tty5", stderr = "/dev/tty5",
                                    root = instRoot)
            os.close(p[0])

    def installGrub(self, instRoot, bootDevs, grubTarget, grubPath, fsset,
                    target, cfPath):
        args = "--stage2=/boot/grub/stage2 "
        if self.forceLBA32:
            args = "%s--force-lba " % (args,)

        cmds = []
        for bootDev in bootDevs:
            gtPart = self.getMatchingPart(bootDev, grubTarget)
            gtDisk = self.grubbyPartitionName(getDiskPart(gtPart)[0])
            bPart = self.grubbyPartitionName(bootDev)
            cmd = "root %s\n" % (bPart,)

            stage1Target = gtDisk
            if target == "partition":
                stage1Target = self.grubbyPartitionName(gtPart)

            cmd += "install %s%s/stage1 d %s %s/stage2 p %s%s/grub.conf" % \
                (args, grubPath, stage1Target, grubPath, bPart, grubPath)
            cmds.append(cmd)

            self.runGrubInstall(instRoot, bootDev, cmds, cfPath)

    def writeGrub(self, instRoot, fsset, bl, langs, kernelList, chainList,
            defaultDev, justConfigFile):
        
        images = bl.images.getImages()
        rootDev = fsset.getEntryByMountPoint("/").device.getDevice()

        # XXX old config file should be read here for upgrade

        cf = "%s%s" % (instRoot, self.configfile)
        self.perms = 0600
        if os.access (cf, os.R_OK):
            self.perms = os.stat(cf)[0] & 0777
            os.rename(cf, cf + '.rpmsave')

        grubTarget = bl.getDevice()
        target = "mbr"
        if (grubTarget.startswith('rd/') or grubTarget.startswith('ida/') or
                grubTarget.startswith('cciss/') or
                grubTarget.startswith('sx8/') or
                grubTarget.startswith('mapper/')):
            if grubTarget[-1].isdigit():
                if grubTarget[-2] == 'p' or \
                        (grubTarget[-2].isdigit() and grubTarget[-3] == 'p'):
                    target = "partition"
        elif grubTarget[-1].isdigit() and not grubTarget.startswith('md'):
            target = "partition"
            
        f = open(cf, "w+")

        f.write("# grub.conf generated by anaconda\n")
        f.write("#\n")
        f.write("# Note that you do not have to rerun grub "
                "after making changes to this file\n")

        bootDev = fsset.getEntryByMountPoint("/boot")
        grubPath = "/grub"
        cfPath = "/"
        if not bootDev:
            bootDev = fsset.getEntryByMountPoint("/")
            grubPath = "/boot/grub"
            cfPath = "/boot/"
            f.write("# NOTICE:  You do not have a /boot partition.  "
                    "This means that\n")
            f.write("#          all kernel and initrd paths are relative "
                    "to /, eg.\n")            
        else:
            f.write("# NOTICE:  You have a /boot partition.  This means "
                    "that\n")
            f.write("#          all kernel and initrd paths are relative "
                    "to /boot/, eg.\n")

        bootDevs = self.getPhysicalDevices(bootDev.device.getDevice())
        bootDev = bootDev.device.getDevice()
        
        f.write('#          root %s\n' % self.grubbyPartitionName(bootDevs[0]))
        f.write("#          kernel %svmlinuz-version ro "
                "root=/dev/%s\n" % (cfPath, rootDev))
        f.write("#          initrd %sinitrd-version.img\n" % (cfPath))
        f.write("#boot=/dev/%s\n" % (grubTarget))

        # get the default image to boot... we have to walk and find it
        # since grub indexes by where it is in the config file
        if defaultDev == rootDev:
            default = 0
        else:
            # if the default isn't linux, it's the first thing in the
            # chain list
            default = len(kernelList)

        # keep track of which devices are used for the device.map
        usedDevs = {}

        f.write('default=%s\n' % (default))
        f.write('timeout=%d\n' % (self.timeout or 0))

        if self.serial == 1:
            # grub the 0-based number of the serial console device
            unit = self.serialDevice[-1]
            
            # and we want to set the speed too
            speedend = 0
            for char in self.serialOptions:
                if char not in string.digits:
                    break
                speedend = speedend + 1
            if speedend != 0:
                speed = self.serialOptions[:speedend]
            else:
                # reasonable default
                speed = "9600"
                
            f.write("serial --unit=%s --speed=%s\n" %(unit, speed))
            f.write("terminal --timeout=%s serial console\n" % (self.timeout or 5))
        else:
            # we only want splashimage if they're not using a serial console
            if os.access("%s/boot/grub/splash.xpm.gz" %(instRoot,), os.R_OK):
                f.write('splashimage=%s%sgrub/splash.xpm.gz\n'
                        % (self.grubbyPartitionName(bootDevs[0]), cfPath))
                f.write("hiddenmenu\n")

        for dev in self.getPhysicalDevices(grubTarget):
            usedDevs[dev] = 1
            
        if self.password:
            f.write('password --md5 %s\n' %(self.password))
        
        for (label, longlabel, version) in kernelList:
            kernelTag = "-" + version
            kernelFile = "%svmlinuz%s" % (cfPath, kernelTag)

            initrd = self.makeInitrd(kernelTag)

            f.write('title %s (%s)\n' % (longlabel, version))
            f.write('\troot %s\n' % self.grubbyPartitionName(bootDevs[0]))

            realroot = getRootDevName(initrd, fsset, rootDev, instRoot)
            realroot = " root=%s" %(realroot,)

            if version.endswith("xen0") or (version.endswith("xen") and not os.path.exists("/proc/xen")):
                # hypervisor case
                sermap = { "ttyS0": "com1", "ttyS1": "com2",
                           "ttyS2": "com3", "ttyS3": "com4" }
                if self.serial and sermap.has_key(self.serialDevice) and \
                       self.serialOptions:
                    hvs = "%s=%s" %(sermap[self.serialDevice],
                                    self.serialOptions)
                else:
                    hvs = ""
                if version.endswith("xen0"):
                    hvFile = "%sxen.gz-%s %s" %(cfPath,
                                                version.replace("xen0", ""),
                                                hvs)
                else:
                    hvFile = "%sxen.gz-%s %s" %(cfPath,
                                                version.replace("xen", ""),
                                                hvs)
                f.write('\tkernel %s\n' %(hvFile,))
                f.write('\tmodule %s ro%s' %(kernelFile, realroot))
                if self.args.get():
                    f.write(' %s' % self.args.get())
                f.write('\n')

                if os.access (instRoot + initrd, os.R_OK):
                    f.write('\tmodule %sinitrd%s.img\n' % (cfPath, kernelTag))
            else: # normal kernel
                f.write('\tkernel %s ro%s' % (kernelFile, realroot))
                if self.args.get():
                    f.write(' %s' % self.args.get())
                f.write('\n')

                if os.access (instRoot + initrd, os.R_OK):
                    f.write('\tinitrd %sinitrd%s.img\n' % (cfPath, kernelTag))

        for (label, longlabel, device) in chainList:
            if ((not longlabel) or (longlabel == "")):
                continue
            f.write('title %s\n' % (longlabel))
            f.write('\trootnoverify %s\n' % self.grubbyPartitionName(device))
#            f.write('\tmakeactive\n')
            f.write('\tchainloader +1')
            f.write('\n')
            usedDevs[device] = 1

        f.close()

        if not "/efi/" in cf:
            os.chmod(cf, self.perms)

        try:
            # make symlink for menu.lst (default config file name)
            menulst = "%s%s/menu.lst" % (instRoot, self.configdir)
            if os.access (menulst, os.R_OK):
                os.rename(menulst, menulst + ".rpmsave")
            os.symlink("./grub.conf", menulst)
        except:
            pass

        try:
            # make symlink for /etc/grub.conf (config files belong in /etc)
            etcgrub = "%s%s" % (instRoot, "/etc/grub.conf")
            if os.access (etcgrub, os.R_OK):
                os.rename(etcgrub, etcgrub + ".rpmsave")
            os.symlink(".." + self.configfile, etcgrub)
        except:
            pass
       
        for dev in self.getPhysicalDevices(rootDev) + bootDevs:
            usedDevs[dev] = 1

        if os.access(instRoot + "/boot/grub/device.map", os.R_OK):
            os.rename(instRoot + "/boot/grub/device.map",
                      instRoot + "/boot/grub/device.map.rpmsave")
        if 1: # not os.access(instRoot + "/boot/grub/device.map", os.R_OK):
            f = open(instRoot + "/boot/grub/device.map", "w+")
            f.write("# this device map was generated by anaconda\n")
            devs = usedDevs.keys()
            usedDevs = {}
            for dev in devs:
                drive = getDiskPart(dev)[0]
                if usedDevs.has_key(drive):
                    continue
                usedDevs[drive] = 1
            devs = usedDevs.keys()
            devs.sort()
            for drive in devs:
                # XXX hack city.  If they're not the sort of thing that'll
                # be in the device map, they shouldn't still be in the list.
                if not drive.startswith('md'):
                    f.write("(%s)     /dev/%s\n" % (self.grubbyDiskName(drive),
                                                drive))
            f.close()
        
        sysconf = '/etc/sysconfig/grub'
        if os.access (instRoot + sysconf, os.R_OK):
            self.perms = os.stat(instRoot + sysconf)[0] & 0777
            os.rename(instRoot + sysconf,
                      instRoot + sysconf + '.rpmsave')
        # if it's an absolute symlink, just get it out of our way
        elif (os.path.islink(instRoot + sysconf) and
              os.readlink(instRoot + sysconf)[0] == '/'):
            os.rename(instRoot + sysconf,
                      instRoot + sysconf + '.rpmsave')
        f = open(instRoot + sysconf, 'w+')
        f.write("boot=/dev/%s\n" %(grubTarget,))
        # XXX forcelba never gets read back...
        if self.forceLBA32:
            f.write("forcelba=1\n")
        else:
            f.write("forcelba=0\n")
        f.close()
            
        if not justConfigFile:
            self.installGrub(instRoot, bootDevs, grubTarget, grubPath, fsset, \
                             target, cfPath)

        return ""

    def getMatchingPart(self, bootDev, target):
        bootName, bootPartNum = getDiskPart(bootDev)
        devices = self.getPhysicalDevices(target)
        for device in devices:
            name, partNum = getDiskPart(device)
            if name == bootName:
                return device
        return devices[0]

    def grubbyDiskName(self, name):
        return "hd%d" % self.drivelist.index(name)

    def grubbyPartitionName(self, dev):
        (name, partNum) = getDiskPart(dev)
        if partNum != None:
            return "(%s,%d)" % (self.grubbyDiskName(name), partNum)
        else:
            return "(%s)" %(self.grubbyDiskName(name))
    

    def getBootloaderConfig(self, instRoot, fsset, bl, langs, kernelList,
                            chainList, defaultDev):
        config = bootloaderInfo.getBootloaderConfig(self, instRoot, fsset,
                                                    bl, langs,
                                                    kernelList, chainList,
                                                    defaultDev)

        liloTarget = bl.getDevice()

        config.addEntry("boot", '/dev/' + liloTarget, replace = 0)
        config.addEntry("map", "/boot/map", replace = 0)
        config.addEntry("install", "/boot/boot.b", replace = 0)
        message = "/boot/message"

        if self.pure is not None and not self.useGrubVal:
            config.addEntry("restricted", replace = 0)
            config.addEntry("password", self.pure, replace = 0)
        

        import language
        for lang in language.expandLangs(langs.getDefault()):
            fn = "/boot/message." + lang
            if os.access(instRoot + fn, os.R_OK):
                message = fn
                break

        if self.serial == 1:
           # grab the 0-based number of the serial console device
            unit = self.serialDevice[-1]
            # FIXME: we should probably put some options, but lilo
            # only supports up to 9600 baud so just use the defaults
            # it's better than nothing :(
            config.addEntry("serial=%s" %(unit,))
        else:
            # message screws up serial console
            if os.access(instRoot + message, os.R_OK):
                config.addEntry("message", message, replace = 0)

        if not config.testEntry('lba32'):
            if self.forceLBA32 or (bl.above1024 and
                                   rhpl.getArch() != "x86_64"):
                config.addEntry("lba32", replace = 0)

        return config

    # this is a hackish function that depends on the way anaconda writes
    # out the grub.conf with a #boot= comment
    # XXX this falls into the category of self.doUpgradeOnly
    def upgradeGrub(self, instRoot, fsset, bl, langs, kernelList, chainList,
                    defaultDev, justConfigFile):
        if justConfigFile:
            return ""

        theDev = None
        for (fn, stanza) in [ ("/etc/sysconfig/grub", "boot="),
                              ("/boot/grub/grub.conf", "#boot=") ]:
            try:
                f = open(instRoot + fn, "r")
            except:
                continue
        
            # the following bits of code are straight from checkbootloader.py
            lines = f.readlines()
            f.close()
            for line in lines:
                if line.startswith(stanza):
                    theDev = checkbootloader.getBootDevString(line)
                    break
            if theDev is not None:
                break
            
        if theDev is None:
            # we could find the dev before, but can't now...  cry about it
            return ""

        # migrate info to /etc/sysconfig/grub
        self.writeSysconfig(instRoot, theDev)

        # more suckage.  grub-install can't work without a valid /etc/mtab
        # so we have to do shenanigans to get updated grub installed...
        # steal some more code above
        bootDev = fsset.getEntryByMountPoint("/boot")
        grubPath = "/grub"
        cfPath = "/"
        if not bootDev:
            bootDev = fsset.getEntryByMountPoint("/")
            grubPath = "/boot/grub"
            cfPath = "/boot/"

        masterBootDev = bootDev.device.getDevice(asBoot = 0)
        if masterBootDev[0:2] == 'md':
            rootDevs = checkbootloader.getRaidDisks(masterBootDev, raidLevel=1,
                            stripPart = 0)
        else:
            rootDevs = [masterBootDev]
            
        if theDev[5:7] == 'md':
            stage1Devs = checkbootloader.getRaidDisks(theDev[5:], raidLevel=1)
        else:
            stage1Devs = [theDev[5:]]

        for stage1Dev in stage1Devs:
            # cross fingers; if we can't find a root device on the same
            # hardware as this boot device, we just blindly hope the first
            # thing in the list works.

            grubbyStage1Dev = self.grubbyPartitionName(stage1Dev)

            grubbyRootPart = self.grubbyPartitionName(rootDevs[0])

            for rootDev in rootDevs:
                testGrubbyRootDev = getDiskPart(rootDev)[0]
                testGrubbyRootDev = self.grubbyPartitionName(testGrubbyRootDev)

                if grubbyStage1Dev == testGrubbyRootDev:
                    grubbyRootPart = self.grubbyPartitionName(rootDev)
                    break
                    
            args = "--stage2=/boot/grub/stage2 "
            cmd ="root %s" % (grubbyRootPart,)
            cmds = [ cmd ]
            cmd = "install %s%s/stage1 d %s %s/stage2 p %s%s/grub.conf" \
                % (args, grubPath, grubbyStage1Dev, grubPath, grubbyRootPart,
                   grubPath)
            cmds.append(cmd)
        
            if not justConfigFile:
                #log("GRUB command %s", cmd)
                self.runGrubInstall(instRoot, bootDev.device.setupDevice(),
                                    cmds, cfPath)
 
        return ""

    def writeSysconfig(self, instRoot, installDev):
        sysconf = '/etc/sysconfig/grub'
        if not os.access(instRoot + sysconf, os.R_OK):
            f = open(instRoot + sysconf, "w+")
            f.write("boot=%s\n" %(installDev,))
            # XXX forcelba never gets read back at all...
            if self.forceLBA32:
                f.write("forcelba=1\n")
            else:
                f.write("forcelba=0\n")
            f.close()
        
    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
            defaultDev, justConfig, intf):
        if self.timeout is None and chainList:
            self.timeout = 5

        # XXX HACK ALERT - see declaration above
        if self.doUpgradeOnly:
            if self.useGrubVal:
                self.upgradeGrub(instRoot, fsset, bl, langs, kernelList,
                                 chainList, defaultDev, justConfig)
            return        

        if len(kernelList) < 1:
            self.noKernelsWarn(intf)

        out = self.writeGrub(instRoot, fsset, bl, langs, kernelList, 
                             chainList, defaultDev,
                             justConfig | (not self.useGrubVal))


    def getArgList(self):
        args = bootloaderInfo.getArgList(self)
        
        if self.forceLBA32:
            args.append("--lba32")
        if self.password:
            args.append("--md5pass=%s" %(self.password))
        
        return args

    def __init__(self):
        bootloaderInfo.__init__(self)
        self._configdir = "/boot/grub"
        self._configname = "grub.conf"
        # XXX use checkbootloader to determine what to default to
        self.useGrubVal = 1
        self.kernelLocation = "/boot/"
        self.password = None
        self.pure = None


class efiBootloaderInfo(bootloaderInfo):
    def getBootloaderName(self):
        return self._bootloader
    bootloader = property(getBootloaderName, None, None, \
                          "name of the bootloader to install")

    # XXX wouldn't it be nice to have a real interface to use efibootmgr from?
    def removeOldEfiEntries(self, instRoot):
        p = os.pipe()
        rhpl.executil.execWithRedirect('/usr/sbin/efibootmgr', ["efibootmgr"],
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
                rhpl.executil.execWithRedirect('/usr/sbin/efibootmgr',
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
        rhpl.executil.execWithRedirect(argv[0], argv, root = instRoot,
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

class x86BootloaderInfo(grubBootloaderInfo, efiBootloaderInfo):
    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
            defaultDev, justConfig, intf):
        grubBootloaderInfo.write(self, instRoot, fsset, bl, langs, kernelList,
                                 chainList, defaultDev, justConfig, intf)

        # XXX move the lilo.conf out of the way if they're using GRUB
        # so that /sbin/installkernel does a more correct thing
        if self.useGrubVal and os.access(instRoot + '/etc/lilo.conf', os.R_OK):
            os.rename(instRoot + "/etc/lilo.conf",
                      instRoot + "/etc/lilo.conf.anaconda")

    def installGrub(self, *args):
        args = [self] + list(args)
        try:
            apply(efiBootloaderInfo.installGrub, args, {})
        except EnvironmentError:
            apply(grubBootloaderInfo.installGrub, args, {})

    def __init__(self):
        grubBootloaderInfo.__init__(self)
        efiBootloaderInfo.__init__(self, initialize=False)

class ia64BootloaderInfo(efiBootloaderInfo):
    def getBootloaderConfig(self, instRoot, fsset, bl, langs, kernelList,
                            chainList, defaultDev):
        config = bootloaderInfo.getBootloaderConfig(self, instRoot, fsset,
                                                    bl, langs,
                                                    kernelList, chainList,
                                                    defaultDev)
        # altix boxes need relocatable (#120851)
        config.addEntry("relocatable")

        return config
            
    def writeLilo(self, instRoot, fsset, bl, langs, kernelList, 
                  chainList, defaultDev, justConfig):
        config = self.getBootloaderConfig(instRoot, fsset, bl, langs,
                                          kernelList, chainList, defaultDev)
        config.write(instRoot + self.configfile, perms = 0755)

        return ""
        
    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
            defaultDev, justConfig, intf):
        if len(kernelList) >= 1:
            out = self.writeLilo(instRoot, fsset, bl, langs, kernelList, 
                                 chainList, defaultDev, justConfig)
        else:
            self.noKernelsWarn(intf)

        self.removeOldEfiEntries(instRoot)
        self.addNewEfiEntry(instRoot, fsset)

    def makeInitrd(self, kernelTag):
        return "/boot/efi/EFI/redhat/initrd%s.img" % kernelTag

    def __init__(self):
        efiBootloaderInfo.__init__(self)
        self._configname = "elilo.conf"
        self._bootloader = "elilo.efi"

class s390BootloaderInfo(bootloaderInfo):
    def getBootloaderConfig(self, instRoot, fsset, bl, langs, kernelList,
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

        # Remove any invalid entries that are in the file; we probably
        # just removed those kernels. 
        for label in lilo.listImages():
            (fsType, sl, path, other) = lilo.getImage(label)
            if fsType == "other": continue

            if not os.access(instRoot + sl.getPath(), os.R_OK):
                lilo.delImage(label)

        rootDev = fsset.getEntryByMountPoint("/").device.getDevice()
        if not rootDev:
            raise RuntimeError, "Installing zipl, but there is no root device"

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
                sl.addEntry("initrd",
                            "%sinitrd%s.img" %(self.kernelLocation, kernelTag))

            sl.addEntry("read-only")
            sl.addEntry("root", '/dev/' + rootDev)
            sl.addEntry("ipldevice", '/dev/' + rootDev[:-1])

            if self.args.get():
                sl.addEntry('append', '"%s"' % self.args.get())
                
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

    def writeChandevConf(self, bl, instroot):   # S/390 only 
        cf = "/etc/chandev.conf"
        self.perms = 0644
        if bl.args.chandevget():
            fd = os.open(instroot + "/etc/chandev.conf",
                         os.O_WRONLY | os.O_CREAT)
            os.write(fd, "noauto\n")
            for cdev in bl.args.chandevget():
                os.write(fd,'%s\n' % cdev)
            os.close(fd)
        return ""
        
    
    def writeZipl(self, instRoot, fsset, bl, langs, kernelList, chainList,
                  defaultDev, justConfigFile):
        images = bl.images.getImages()
        rootDev = fsset.getEntryByMountPoint("/").device.getDevice()
        
        cf = '/etc/zipl.conf'
        self.perms = 0600
        if os.access (instRoot + cf, os.R_OK):
            self.perms = os.stat(instRoot + cf)[0] & 0777
            os.rename(instRoot + cf,
                      instRoot + cf + '.rpmsave')

        f = open(instRoot + cf, "w+")        

        f.write('[defaultboot]\n')
        f.write('default=' + kernelList[0][0] + '\n')
        f.write('target=%s\n' % (self.kernelLocation))

        cfPath = "/boot/"
        for (label, longlabel, version) in kernelList:
            kernelTag = "-" + version
            kernelFile = "%svmlinuz%s" % (cfPath, kernelTag)

            initrd = self.makeInitrd(kernelTag)
            f.write('[%s]\n' % (label))
            f.write('\timage=%s\n' % (kernelFile))
            if os.access (instRoot + initrd, os.R_OK):
                f.write('\tramdisk=%sinitrd%s.img\n' %(self.kernelLocation,
                                                     kernelTag))
            realroot = getRootDevName(initrd, fsset, rootDev, instRoot)
            f.write('\tparameters="root=%s' %(realroot,))
            if bl.args.get():
                f.write(' %s' % (bl.args.get()))
            f.write('"\n')

        f.close()

        if not justConfigFile:
            argv = [ "/sbin/zipl" ]
            rhpl.executil.execWithRedirect(argv[0], argv, root = instRoot,
                                   stdout = "/dev/stdout",
                                   stderr = "/dev/stderr")
            
        return ""

    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
            defaultDev, justConfig, intf):
        out = self.writeZipl(instRoot, fsset, bl, langs, kernelList, 
                             chainList, defaultDev,
                             justConfig | (not self.useZiplVal))
        out = self.writeChandevConf(bl, instRoot)
    
    def __init__(self):
        bootloaderInfo.__init__(self)
        self.useZiplVal = 1      # only used on s390
        self.kernelLocation = "/boot/"
        self.configfile = "/etc/zipl.conf"


class alphaBootloaderInfo(bootloaderInfo):
    def wholeDevice (self, path):
        (device, foo) = getDiskPart(path)
        return device

    def partitionNum (self, path):
        # getDiskPart returns part numbers 0-based; we need it one based
        # *sigh*
        (foo, partitionNumber) = getDiskPart(path)
        return partitionNumber + 1

    def writeAboot(self, instRoot, fsset, bl, langs, kernelList,
                   chainList, defaultDev, justConfig):
        # Get bootDevice and rootDevice
        rootDevice = fsset.getEntryByMountPoint("/").device.getDevice()
        if fsset.getEntryByMountPoint("/boot"):
            bootDevice = fsset.getEntryByMountPoint("/boot").device.getDevice()
        else:
            bootDevice = rootDevice
        bootnotroot = bootDevice != rootDevice

        # If /etc/aboot.conf already exists we rename it
        # /etc/aboot.conf.rpmsave.
        if os.path.isfile(instRoot + self.configfile):
            os.rename (instRoot + self.configfile,
                       instRoot + self.configfile + ".rpmsave")
        
        # Then we create the necessary files. If the root device isn't
        # the boot device, we create /boot/etc/ where the aboot.conf
        # will live, and we create /etc/aboot.conf as a symlink to it.
        if bootnotroot:
            # Do we have /boot/etc ? If not, create one
            if not os.path.isdir (instRoot + '/boot/etc'):
                os.mkdir(instRoot + '/boot/etc', 0755)

            # We install the symlink (/etc/aboot.conf has already been
            # renamed in necessary.)
            os.symlink("../boot" + self.configfile, instRoot + self.configfile)

            cfPath = instRoot + "/boot" + self.configfile
            # Kernel path is set to / because a boot partition will
            # be a root on its own.
            kernelPath = '/'
        # Otherwise, we just need to create /etc/aboot.conf.
        else:
            cfPath = instRoot + self.configfile
            kernelPath = self.kernelLocation

        # If we already have an aboot.conf, rename it
        if os.access (cfPath, os.R_OK):
            self.perms = os.stat(cfPath)[0] & 0777
            os.rename(cfPath, cfPath + '.rpmsave')
                
        # Now we're going to create and populate cfPath.
        f = open (cfPath, 'w+')
        f.write ("# aboot default configurations\n")

        if bootnotroot:
            f.write ("# NOTICE: You have a /boot partition. This means that\n")
            f.write ("#         all kernel paths are relative to /boot/\n")

        # bpn is the boot partition number.
        bpn = self.partitionNum(bootDevice)
        lines = 0

        # We write entries line using the following format:
        # <line><bpn><kernel-name> root=<rootdev> [options]
        # We get all the kernels we need to know about in kernelList.

        for (kernel, tag, version) in kernelList:
            kernelTag = "-" + version
            kernelFile = "%svmlinuz%s" %(kernelPath, kernelTag)

            f.write("%d:%d%s" %(lines, bpn, kernelFile))

            # See if we can come up with an initrd argument that exists
            initrd = self.makeInitrd(kernelTag)
            if os.path.isfile(instRoot + initrd):
                f.write(" initrd=%sinitrd%s.img" %(kernelPath, kernelTag))

            realroot = getRootDevName(initrd, fsset, rootDevice, instRoot)
            f.write(" root=%s" %(realroot,))

            args = self.args.get()
            if args:
                f.write(" %s" %(args,))

            f.write("\n")
            lines = lines + 1

        # We're done writing the file
        f.close ()
        del f

        if not justConfig:
            # Now we're ready to write the relevant boot information. wbd
            # is the whole boot device, bdpn is the boot device partition
            # number.
            wbd = self.wholeDevice (bootDevice)
            bdpn = self.partitionNum (bootDevice)

            # Calling swriteboot. The first argument is the disk to write
            # to and the second argument is a path to the bootstrap loader
            # file.
            args = ("swriteboot", ("/dev/%s" % wbd), "/boot/bootlx")
            #log("swriteboot command: %s" %(args,))
            rhpl.executil.execWithRedirect ('/sbin/swriteboot', args,
                                    root = instRoot,
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")

            # Calling abootconf to configure the installed aboot. The
            # first argument is the disk to use, the second argument is
            # the number of the partition on which aboot.conf resides.
            # It's always the boot partition whether it's / or /boot (with
            # the mount point being omitted.)
            args = ("abootconf", ("/dev/%s" % wbd), str (bdpn))
            #log("abootconf command: %s" %(args,))            
            rhpl.executil.execWithRedirect ('/sbin/abootconf', args,
                                    root = instRoot,
                                    stdout = "/dev/tty5",
                                    stderr = "/dev/tty5")


    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
            defaultDev, justConfig, intf):
        if len(kernelList) < 1:
            self.noKernelsWarn(intf)

        self.writeAboot(instRoot, fsset, bl, langs, kernelList, 
                        chainList, defaultDev, justConfig)

    def __init__(self):
        bootloaderInfo.__init__(self)
        self.useGrubVal = 0
        self.configfile = "/etc/aboot.conf"
        # self.kernelLocation is already set to what we need.
        self.password = None
        self.pure = None
    

class ppcBootloaderInfo(bootloaderInfo):
    def getBootDevs(self, fs, bl):
        import fsset

        devs = []
        machine = rhpl.getPPCMachine()

        if machine == 'pSeries':
            for entry in fs.entries:
                if isinstance(entry.fsystem, fsset.prepbootFileSystem) \
                        and entry.format:
                    devs.append('/dev/%s' % (entry.device.getDevice(),))
        elif machine == 'PMac':
            for entry in fs.entries:
                if isinstance(entry.fsystem, fsset.applebootstrapFileSystem) \
                        and entry.format:
                    devs.append('/dev/%s' % (entry.device.getDevice(),))

        if len(devs) == 0:
            # Try to get a boot device; bplan OF understands ext3
            if machine == 'Pegasos' or machine == 'Efika':
                entry = fs.getEntryByMountPoint('/boot')
                # Try / if we don't have this we're not going to work
                if not entry:
                    entry = fs.getEntryByMountPoint('/')
                if entry:
                    dev = "/dev/%s" % (entry.device.getDevice(asBoot=1),)
                    devs.append(dev)
            else:
                if bl.getDevice():
                    devs.append("/dev/%s" % bl.getDevice())
        return devs


    def writeYaboot(self, instRoot, fsset, bl, langs, kernelList, 
                  chainList, defaultDev, justConfigFile):

        yabootTarget = string.join(self.getBootDevs(fsset, bl))

        bootDev = fsset.getEntryByMountPoint("/boot")
        if bootDev:
            cf = "/boot/etc/yaboot.conf"
            cfPath = ""
            if not os.path.isdir(instRoot + "/boot/etc"):
                os.mkdir(instRoot + "/boot/etc")
        else:
            bootDev = fsset.getEntryByMountPoint("/")
            cfPath = "/boot"
            cf = "/etc/yaboot.conf"
        bootDev = bootDev.device.getDevice(asBoot = 1)

        f = open(instRoot + cf, "w+")

        f.write("# yaboot.conf generated by anaconda\n\n")
        
        f.write("boot=%s\n" %(yabootTarget,))
        f.write("init-message=\"Welcome to %s!\\nHit <TAB> for boot options\"\n\n"
                % productName)

        (name, partNum) = getDiskPart(bootDev)
        partno = partNum + 1 # 1 based

        f.write("partition=%s\n" %(partno,))

        f.write("timeout=%s\n" % (self.timeout or 80))
        f.write("install=/usr/lib/yaboot/yaboot\n")
        f.write("delay=5\n")
        f.write("enablecdboot\n")
        f.write("enableofboot\n")
        f.write("enablenetboot\n")        

        yabootProg = "/sbin/mkofboot"
        if rhpl.getPPCMachine() == "PMac":
            # write out the first hfs/hfs+ partition as being macosx
            for (label, longlabel, device) in chainList:
                if ((not label) or (label == "")):
                    continue
                f.write("macosx=/dev/%s\n" %(device,))
                break
            
            f.write("magicboot=/usr/lib/yaboot/ofboot\n")

        elif rhpl.getPPCMachine() == "pSeries":
            f.write("nonvram\n")
            f.write("fstype=raw\n")

        else: #  Default non-destructive case for anything else.
            f.write("nonvram\n")
            f.write("mntpoint=/boot/yaboot\n")
            f.write("usemount\n")
            if not os.access(instRoot + "/boot/yaboot", os.R_OK):
                os.mkdir(instRoot + "/boot/yaboot")
            yabootProg = "/sbin/ybin"

        if self.password:
            f.write("password=%s\n" %(self.password,))
            f.write("restricted\n")

        f.write("\n")
        
        rootDev = fsset.getEntryByMountPoint("/").device.getDevice()

        for (label, longlabel, version) in kernelList:
            kernelTag = "-" + version
            kernelFile = "%s/vmlinuz%s" %(cfPath, kernelTag)

            f.write("image=%s\n" %(kernelFile,))
            f.write("\tlabel=%s\n" %(label,))
            f.write("\tread-only\n")

            initrd = self.makeInitrd(kernelTag)
            if os.access(instRoot + initrd, os.R_OK):
                f.write("\tinitrd=%s/initrd%s.img\n" %(cfPath,kernelTag))

            append = "%s" %(self.args.get(),)

            realroot = getRootDevName(initrd, fsset, rootDev, instRoot)
            if rootIsDevice(realroot):
                f.write("\troot=%s\n" %(realroot,))
            else:
                if len(append) > 0:
                    append = "%s root=%s" %(append,realroot)
                else:
                    append = "root=%s" %(realroot,)

            if len(append) > 0:
                f.write("\tappend=\"%s\"\n" %(append,))
            f.write("\n")

        f.close()
        os.chmod(instRoot + cf, 0600)

        # FIXME: hack to make sure things are written to disk
        import isys
        isys.sync()
        isys.sync()
        isys.sync()

        ybinargs = [ yabootProg, "-f", "-C", cf ]
        
        #log("running: %s" %(ybinargs,))
        if not flags.test:
            rhpl.executil.execWithRedirect(ybinargs[0],
                                           ybinargs,
                                           stdout = "/dev/tty5",
                                           stderr = "/dev/tty5",
                                           root = instRoot)

        if (not os.access(instRoot + "/etc/yaboot.conf", os.R_OK) and
            os.access(instRoot + "/boot/etc/yaboot.conf", os.R_OK)):
            os.symlink("../boot/etc/yaboot.conf",
                       instRoot + "/etc/yaboot.conf")
        
        return ""

    def setPassword(self, val, isCrypted = 1):
        # yaboot just handles the password and doesn't care if its crypted
        # or not
        self.password = val
        
    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
            defaultDev, justConfig, intf):
        if len(kernelList) >= 1:
            out = self.writeYaboot(instRoot, fsset, bl, langs, kernelList, 
                                 chainList, defaultDev, justConfig)
        else:
            self.noKernelsWarn(intf)

    def __init__(self):
        bootloaderInfo.__init__(self)
        self.useYabootVal = 1
        self.kernelLocation = "/boot"
        self.configfile = "/etc/yaboot.conf"


class iseriesBootloaderInfo(bootloaderInfo):
    def ddFile(self, inf, of, bs = 4096):
        src = os.open(inf, os.O_RDONLY)
        dest = os.open(of, os.O_WRONLY | os.O_CREAT)
        size = 0

        buf = os.read(src, bs)
        while len(buf) > 0:
            size = size + len(buf)
            os.write(dest, buf)
            buf = os.read(src, bs)

        os.close(src)
        os.close(dest)

        return size
        
    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
              defaultDev, justConfig, intf):
        if len(kernelList) < 1:
            self.noKernelsWarn(intf)
            return
        #if len(kernelList) > 1:
        #    # FIXME: how can this happen?
        #    log("more than one kernel on iSeries.  bailing and just using "
        #        "the first")

        # iseries is Weird (tm) -- here's the basic theory 
        # a) have /boot/vmlinitrd-$(version) 
        # b) copy default kernel to PReP partition
        # c) dd default kernel to /proc/iSeries/mf/C/vmlinux
        # d) set cmdline in /boot/cmdline-$(version)
        # e) copy cmdline to /proc/iSeries/mf/C/cmdline
        # f) set default side to 'C' i /proc/iSeries/mf/side
        # g) put default kernel and cmdline on side B too (#91038)
        
        rootDevice = fsset.getEntryByMountPoint("/").device.getDevice()

        # write our command line files
        for (kernel, tag, kernelTag) in kernelList:
            cmdFile = "%scmdline-%s" %(self.kernelLocation, kernelTag)
            initrd = "%sinitrd-%s.img" %(self.kernelLocation, kernelTag)
            realroot = getRootDevName(initrd, fsset, rootDevice, instRoot)
            f = open(instRoot + cmdFile, "w")
            f.write("ro root=%s" %(realroot,))
            if bl.args.get():
                f.write(" %s" %(bl.args.get(),))
            f.write("\n")
            f.close()
            os.chmod(instRoot + cmdFile, 0644)
            
        kernel, tag, kernelTag = kernelList[0]
        kernelFile = "%svmlinitrd-%s" %(self.kernelLocation, kernelTag)

        # write the kernel to the PReP partition since that's what
        # OS/400 will load as NWSSTG
        bootDev = bl.getDevice()
        if bootDev:
            #log("Writing kernel %s to PReP partition %s" %(kernelFile, bootDev))
            try:
                self.ddFile(instRoot + kernelFile, "%s/dev/%s" %(instRoot,
                                                                 bootDev))
            except Exception, e:
                # FIXME: should this be more fatal
                #log("Failed to write kernel: %s" %(e,))
                pass
        else:
            #log("No PReP boot partition, not writing kernel for NWSSTG")
            pass


        # now, it's a lot faster to boot if we don't make people go back
        # into OS/400, so set up side C (used by default for NWSSTG) with
        # our current bits
        for side in ("C", "B"):
            #log("Writing kernel and cmdline to side %s" %(side,))
            wrotekernel = 0
            try:
                self.ddFile(instRoot + kernelFile,
                            "%s/proc/iSeries/mf/%s/vmlinux" %(instRoot, side))
                wrotekernel = 1
            except Exception, e:
                # FIXME: should this be more fatal?
                #log("Failed to write kernel to side %s: %s" %(side, e))
                pass

            if wrotekernel == 1:
                try:
                    # blank it.  ugh.
                    f = open("%s/proc/iSeries/mf/%s/cmdline" %(instRoot, side),
                             "w+")
                    f.write(" " * 255)
                    f.close()
                    
                    self.ddFile("%s/%scmdline-%s" %(instRoot,
                                                    self.kernelLocation,
                                                    kernelTag),
                                "%s/proc/iSeries/mf/%s/cmdline" %(instRoot,
                                                                  side))
                except Exception, e:
                    #log("Failed to write kernel command line to side %s: %s"
                    #    %(side, e))
                    pass

        #log("Setting default side to C")
        f = open(instRoot + "/proc/iSeries/mf/side", "w")
        f.write("C")
        f.close()
        
    def __init__(self):
        bootloaderInfo.__init__(self)
        self.kernelLocation = "/boot/"

class isolinuxBootloaderInfo(bootloaderInfo):
    def __init__(self):
        bootloaderInfo.__init__(self)
        self.kernelLocation = "/boot"
        self.configfile = "/boot/isolinux/isolinux.cfg"

    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
              defaultDev, justConfig, intf = None):
        if not os.path.isdir(instRoot + "/boot/isolinux"):
            os.mkdir(instRoot + "/boot/isolinux")

        f = open(instRoot + "/boot/isolinux/isolinux.cfg", "w+")
        f.write("# isolinux.cfg generated by anaconda\n\n")

        f.write("prompt 1\n")
        f.write("timeout %s\n" % (self.timeout or 600))

        # FIXME: as this stands, we can really only handle one due to
        # filename length limitations with base iso9660.  fun, fun.
        for (label, longlabel, version) in kernelList:
            # XXX hackity, hack hack hack.  but we need them in a different
            # path for live cd only
            shutil.copy("%s/boot/vmlinuz-%s" %(instRoot, version),
                        "%s/boot/isolinux/vmlinuz" %(instRoot,))
            shutil.copy("%s/boot/initrd-%s.img" %(instRoot, version),
                        "%s/boot/isolinux/initrd.img" %(instRoot,))
            
            # FIXME: need to dtrt for xen kernels with multiboot com32 module
            f.write("label linux\n")
            f.write("\tkernel vmlinuz\n")
            f.write("\tappend initrd=initrd.img,initlive.gz\n")
            f.write("\n")

            break
            
        f.close()
        os.chmod(instRoot + "/boot/isolinux/isolinux.cfg", 0600)

        # copy the isolinux bin
        shutil.copy(instRoot + "/usr/lib/syslinux/isolinux-debug.bin",
                    instRoot + "/boot/isolinux/isolinux.bin")
    
        
class sparcBootloaderInfo(bootloaderInfo):
    def writeSilo(self, instRoot, fsset, bl, langs, kernelList,
                chainList, defaultDev, justConfigFile):

        bootDev = fsset.getEntryByMountPoint("/boot")
        mf = '/silo.message'
        if bootDev:
            cf = "/boot/silo.conf"
            mfdir = '/boot'
            cfPath = ""
            if not os.path.isdir(instRoot + "/boot"):
                os.mkdir(instRoot + "/boot")
        else:
            bootDev = fsset.getEntryByMountPoint("/")
            cf = "/etc/silo.conf"
            mfdir = '/etc'
            cfPath = "/boot"
        bootDev = bootDev.device.getDevice(asBoot = 1)

        f = open(instRoot + mfdir + mf, "w+")
        f.write("Welcome to %s!\nHit <TAB> for boot options\n\n" % productName)
        f.close()
        os.chmod(instRoot + mfdir + mf, 0600)

        f = open(instRoot + cf, "w+")
        f.write("# silo.conf generated by anaconda\n\n")

        f.write("#boot=%s\n" % (bootDev,))
        f.write("message=%s\n" % (mf,))
        f.write("timeout=%s\n" % (self.timeout or 50))

        (name, partNum) = getDiskPart(bootDev)
        partno = partNum + 1
        f.write("partition=%s\n" % (partno,))

        if self.password:
            f.write("password=%s\n" % (self.password,))
            f.write("restricted\n")

        f.write("default=%s\n" % (kernelList[0][0],))
        f.write("\n")

        rootDev = fsset.getEntryByMountPoint("/").device.getDevice()

        for (label, longlabel, version) in kernelList:
            kernelTag = "-" + version
            kernelFile = "%s/vmlinuz%s" % (cfPath, kernelTag)

            f.write("image=%s\n" % (kernelFile,))
            f.write("\tlabel=%s\n" % (label,))
            f.write("\tread-only\n")

            initrd = self.makeInitrd(kernelTag)
            if os.access(instRoot + initrd, os.R_OK):
                f.write("\tinitrd=%s/initrd%s.img\n" % (cfPath, kernelTag))

            append = "%s" % (self.args.get(),)

            realroot = getRootDevName(initrd, fsset, rootDev, instRoot)
            if rootIsDevice(realroot):
                f.write("\troot=%s\n" % (realroot,))
            else:
                if len(append) > 0:
                    append = "%s root=%s" % (append, realroot)
                else:
                    append = "root=%s" % (realroot,)

            if len(append) > 0:
                f.write("\tappend=\"%s\"\n" % (append,))
            f.write("\n")

        f.close()
        os.chmod(instRoot + cf, 0600)

        # FIXME: hack to make sure things are written to disk
        import isys
        isys.sync()
        isys.sync()
        isys.sync()

        backup = "%s/backup.b" % (cfPath,)
        sbinargs = ["/sbin/silo", "-f", "-C", cf, "-S", backup]
        # TODO!!!  FIXME!!!  XXX!!!
        # butil is not defined!!!  - assume this is in rhpl now?
        if butil.getSparcMachine() == "sun4u":
            sbinargs += ["-u"]
        else:
            sbinargs += ["-U"]

        #log("running: %s" % (sbinargs,))
        if not flags.test:
            rhpl.executil.execWithRedirect(sbinargs[0],
                                            sbinargs,
                                            stdout = "/dev/tty5",
                                            stderr = "/dev/tty5",
                                            root = instRoot)

        if (not os.access(instRoot + "/etc/silo.conf", os.R_OK) and
            os.access(instRoot + "/boot/etc/silo.conf", os.R_OK)):
            os.symlink("../boot/etc/silo.conf",
                       instRoot + "/etc/silo.conf")

        return ""

    def setPassword(self, val, isCrypted = 1):
        # silo just handles the password unencrypted
        self.password = val

    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
            defaultDev, justConfig, intf):
        if len(kernelList) >= 1:
            self.writeSilo(instRoot, fsset, bl, langs, kernelList, chainList,
                        defaultDev, justConfig)
        else:
            self.noKernelsWarn(intf)

    def __init__(self):
        bootloaderInfo.__init__(self)
        self.useSiloVal = 1
        self.kernelLocation = "/boot"
        self._configdir = "/etc"
        self._configname = "silo.conf"

###############
# end of boot loader objects... these are just some utility functions used

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
