#
# bootloader.py: bootloader configuration data
#
# Erik Troan <ewt@redhat.com>
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

import isys
import partitioning
import os
import crypt
import whrandom
import language
import iutil
import string
from flags import flags
from log import log
from constants import *
from lilo import LiloConfigFile
from translate import _

initrdsMade = {}

## if 0:
##     if arch == "sparc":
##         errors = self.silo.install (self.fstab, instPath, 
##                             id.hdList, upgrade)
##     elif arch == "i386":
##         defaultlang = self.language.getLangNickByName(self.language.getDefault())
##         langlist = expandLangs(defaultlang)
##         errors = self.lilo.install (self.fstab, instPath, 
##                             id.hdList, upgrade, langlist)
##     elif arch == "ia64":
##         errors = self.eli.install (self.fstab, instPath, 
##                             id.hdList, upgrade)
##     elif arch == "alpha":
##         errors = self.milo.write ()
##     else:
##         raise RuntimeError, "What kind of machine is this, anyway?!"

## if errors:
##     w.pop()
##     mess = _("An error occured while installing "
##              "the bootloader.\n\n"
##              "We HIGHLY recommend you make a recovery "
##              "boot floppy when prompted, otherwise you "
##              "may not be able to reboot into Red Hat Linux."
##              "\n\nThe error reported was:\n\n") + errors
##     intf.messageWindow(_("Bootloader Errors"), mess)

##     # make sure bootdisk window appears
##     if iutil.getArch () == "i386":
##         self.instClass.removeFromSkipList('bootdisk')
##         self.bootdisk = 1

##     w = apply(apply, createWindow)


class KernelArguments:

    def get(self):
	return self.args

    def set(self, args):
	self.args = args

    def __init__(self):
	cdrw = isys.ideCdRwList()
	str = ""
	for device in cdrw:
	    if str: str = str + " "
	    str = str + ("%s=ide-scsi" % device)

	self.args = str

class BootImages:

    # returns dictionary of (label, longlabel, devtype) pairs indexed by device
    # XXX note that after we've gone through the bootloader screen once we
    # lose the distinction between the two and label == longlabel
    def getImages(self):
	# return a copy so users can modify it w/o affecting us

	dict = {}
	for key in self.images.keys():
	    dict[key] = self.images[key]

	return dict

    def setImageLabel(self, dev, label):
	self.images[dev] = (label, label, self.images[dev][2])

    # default is a device
    def setDefault(self, default):
	self.default = default

    def getDefault(self):
	return self.default

    def setup(self, diskSet, fsset):
	devices = {}
	devs = availableBootDevices(diskSet, fsset)
	for (dev, type) in devs:
	    devices[dev] = 1

	# These partitions have disappeared
	for dev in self.images.keys():
	    if not devices.has_key(dev): del self.images[dev]

	# These have appeared
	for (dev, type) in devs:
	    if not self.images.has_key(dev):
                if type == "FAT":
                    self.images[dev] = ("DOS", "DOS", type)
                else:
                    self.images[dev] = (None, None, type)

	if not self.images.has_key(self.default):
	    entry = fsset.getEntryByMountPoint('/')
	    self.default = entry.device.getDevice()
	    (label, longlabel, type) = self.images[self.default]
	    if not label:
		self.images[self.default] = ("linux", "Red Hat Linux", type)

    def __init__(self):
	self.default = None
	self.images = {}


class bootloaderInfo:
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

    def getBootloaderConfig(self, instRoot, fsset, bl, langs, kernelList,
                            chainList, defaultDev):
	images = bl.images.getImages()

        # on upgrade read in the lilo config file
	lilo = LiloConfigFile ()
	self.perms = 0644
        if os.access (instRoot + self.configfile, os.R_OK):
	    self.perms = os.stat(instRoot + self.configfile)[0] & 0777
	    lilo.read (instRoot + self.configfile)
	    os.rename(instRoot + self.configfile,
		      instRoot + self.configfile + '.rpmsave')

	# Remove any invalid entries that are in the file; we probably
	# just removed those kernels. 
	for label in lilo.listImages():
	    (fsType, sl) = lilo.getImage(label)
	    if fsType == "other": continue

	    if not os.access(instRoot + sl.getPath(), os.R_OK):
		lilo.delImage(label)

	lilo.addEntry("prompt", replace = 0)
	lilo.addEntry("timeout", "50", replace = 0)

        rootDev = fsset.getEntryByMountPoint("/").device.getDevice()
	if not rootDev:
            raise RuntimeError, "Installing lilo, but there is no root device"

	if rootDev == defaultDev:
	    lilo.addEntry("default", kernelList[0][0])
	else:
	    lilo.addEntry("default", chainList[0][0])

	for (label, version) in kernelList:
	    kernelTag = "-" + version
	    kernelFile = self.kernelLocation + "vmlinuz" + kernelTag

	    try:
		lilo.delImage(label)
	    except IndexError, msg:
		pass

	    sl = LiloConfigFile(imageType = "image", path = kernelFile)

	    initrd = makeInitrd (kernelTag, instRoot)

	    sl.addEntry("label", label)
	    if os.access (instRoot + initrd, os.R_OK):
		sl.addEntry("initrd", "%sinitrd%s.img" %(self.kernelLocation, kernelTag))

	    sl.addEntry("read-only")
	    sl.addEntry("root", '/dev/' + rootDev)

	    if self.args.get():
		sl.addEntry('append', '"%s"' % self.args.get())
		
	    lilo.addImage (sl)

	for (label, device) in chainList:
	    try:
		(fsType, sl) = lilo.getImage(label)
		lilo.delImage(label)
	    except IndexError:
		sl = LiloConfigFile(imageType = "other", path = "/dev/%s" %(device))
		sl.addEntry("optional")

	    sl.addEntry("label", label)
	    lilo.addImage (sl)

	# Sanity check #1. There could be aliases in sections which conflict
	# with the new images we just created. If so, erase those aliases
	imageNames = {}
	for label in lilo.listImages():
	    imageNames[label] = 1

	for label in lilo.listImages():
	    (fsType, sl) = lilo.getImage(label)
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
		  defaultDev, justConfig):

        config = self.getBootloaderConfig(instRoot, fsset, bl, langs,
                                          kernelList, chainList, defaultDev)
	config.write(instRoot + self.configfile, perms = self.perms)

        return ""

    def getArgList(self):
        args = []

        if self.args.get():
            args.append("--append")
            args.append(self.args.get())

        return args

    def writeKS(self, f):
        f.write("bootloader")
        for arg in self.getArgList():
            f.write(" " + arg)
        f.write("\n")

    def __init__(self):
	self.args = KernelArguments()
	self.images = BootImages()
	self.device = None
        self.useLinear = 1    # only used for kickstart compatibility
        self.useDefaultDevice = 0  # XXX hack, used by kickstart
        self.useGrubVal = 0      # only used on x86
        self.configfile = None
        self.kernelLocation = "/boot/"
        self.forceLBA32 = 0

class ia64BootloaderInfo(bootloaderInfo):
    def writeLilo(self, instRoot, fsset, bl, langs, kernelList, 
                  chainList, defaultDev, justConfig):
        config = self.getBootloaderConfig(instRoot, fsset, bl, langs,
                                          kernelList, chainList, defaultDev)
	config.write(instRoot + self.configfile, perms = self.perms)

	return ""
        
    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
		  defaultDev, justConfig):
        str = self.writeLilo(instRoot, fsset, bl, langs, kernelList, 
                             chainList, defaultDev, justConfig)

        bootdev = fsset.getEntryByMountPoint("/boot/efi").device.getDevice()
        if not bootdev:
            bootdev = fsset.getEntryByDeviceName("sda1").device.getDevice()

        ind = len(bootdev)
        try:
            while (bootdev[ind-1] in string.digits):
                ind = ind - 1
        except IndexError:
            ind = len(bootdev) - 1
            
        bootdisk = bootdev[:ind]
        bootpart = bootdev[ind:]
        if bootdisk[0:4] == "ida/" or bootdisk[0:6] == "cciss/" or bootdisk[0:3] == "rd/":
            bootdisk = bootdisk[:-1]
                    
        argv = [ "/usr/sbin/efibootmgr", "-c" , "-L",
                 "Red Hat Linux", "-d", "/dev/%s" % bootdisk, "-p", bootpart ]
        iutil.execWithRedirect(argv[0], argv, root = instRoot,
                               stdout = "/dev/tty5",
                               stderr = "/dev/tty5")

    def __init__(self):
        bootloaderInfo.__init__(self)
	self.useGrubVal = 1
        self.kernelLocation = ""
        self.configfile = "/boot/efi/elilo.conf"
    
	
class x86BootloaderInfo(bootloaderInfo):
    def setPassword(self, val, isCrypted = 1):
        if not val:
            self.password = val
            self.pure = val
            return
        
        if isCrypted:
            self.password = val
        else:
            salt = "$1$"
            saltLen = 8

	    for i in range(saltLen):
                salt = salt + whrandom.choice (string.letters +
                                               string.digits + './')

            self.password = crypt.crypt (val, salt)
            self.pure = val
        
    def getPassword (self):
        return self.pure

    def setForceLBA(self, val):
        self.forceLBA32 = val
        
    def setUseGrub(self, val):
	self.useGrubVal = val

    def writeGrub(self, instRoot, fsset, bl, langs, kernelList, chainList,
		  defaultDev, justConfigFile):
	images = bl.images.getImages()
        rootDev = fsset.getEntryByMountPoint("/").device.getDevice()

	cf = '/boot/grub/grub.conf'
	self.perms = 0600
        if os.access (instRoot + cf, os.R_OK):
	    self.perms = os.stat(instRoot + cf)[0] & 0777
	    os.rename(instRoot + cf,
		      instRoot + cf + '.rpmsave')

	f = open(instRoot + cf, "w+")

	bootDev = fsset.getEntryByMountPoint("/boot")
	grubPath = "/grub"
	cfPath = "/"
	if not bootDev:
	    bootDev = fsset.getEntryByMountPoint("/")
	    grubPath = "/boot/grub"
	    cfPath = "/boot/"
	else:
            f.write ("# NOTICE:  You have a /boot partition.  This means that\n")
            f.write ("#          all kernel paths are relative to /boot/\n")

	bootDev = bootDev.device.getDevice()

        f.write('default=0\n')
        f.write('timeout=30\n')
        f.write('splashimage=%s%sgrub/splash.xpm.gz\n'
                % (grubbyPartitionName(bootDev), cfPath))

        if self.password:
            f.write('password --md5 %s\n' %(self.password))
        
	for (label, version) in kernelList:
	    kernelTag = "-" + version
	    kernelFile = "%svmlinuz%s" % (cfPath, kernelTag)

	    initrd = makeInitrd (kernelTag, instRoot)

	    f.write('title %s (%s)\n' % (label, version))
	    f.write('\troot %s\n' % grubbyPartitionName(bootDev))
	    f.write('\tkernel %s ro root=/dev/%s' % (kernelFile, rootDev))
	    if self.args.get():
		f.write(' %s' % self.args.get())
	    f.write('\n')

	    if os.access (instRoot + initrd, os.R_OK):
		f.write('\tinitrd %sinitrd%s.img\n' % (cfPath, kernelTag))

	for (label, device) in chainList:
	    f.write('title %s\n' % (label))
	    f.write('\trootnoverify %s\n' % grubbyPartitionName(device))
            f.write('\tmakeactive\n')
            f.write('\tchainloader +1')
	    f.write('\n')

	f.close()

        if self.forceLBA32:
            forcelba = "--force-lba "
        else:
            forcelba = ""

	part = grubbyPartitionName(bootDev)
	prefix = "%s/%s" % (grubbyPartitionName(bootDev), grubPath)
	cmd = "root %s\ninstall %s%s/i386-redhat/stage1 d %s %s/i386-redhat/stage2 p %s%s/grub.conf" % \
	    (part, forcelba, grubPath, grubbyPartitionName(bl.getDevice()),
             grubPath, part, grubPath)

	log("GRUB command %s", cmd)

	if not justConfigFile:
	    p = os.pipe()
	    os.write(p[1], cmd + '\n')
	    os.close(p[1])

	    iutil.execWithRedirect('/sbin/grub' ,
				    [ "grub",  "--batch", "--no-floppy" ],
                                    stdin = p[0],
				    stdout = "/dev/tty5", stderr = "/dev/tty5",
				    root = instRoot)
	    os.close(p[0])

	return None

    def getBootloaderConfig(self, instRoot, fsset, bl, langs, kernelList,
                            chainList, defaultDev):
        config = bootloaderInfo.getBootloaderConfig(self, instRoot, fsset, bl, langs,
                                                    kernelList, chainList,
                                                    defaultDev)

	liloTarget = bl.getDevice()

	config.addEntry("boot", '/dev/' + liloTarget, replace = 0)
	config.addEntry("map", "/boot/map", replace = 0)
	config.addEntry("install", "/boot/boot.b", replace = 0)
        message = "/boot/message"
        for lang in language.expandLangs(langs.getDefault()):
            fn = "/boot/message." + lang
            if os.access(instRoot + fn, os.R_OK):
                message = fn
                break

	config.addEntry("message", message, replace = 0)

        if not config.testEntry('lba32') and not config.testEntry('linear'):
            if self.forceLBA32:
                config.addEntry("lba32", replace = 0)
            elif self.useLinear:
                config.addEntry("linear", replace = 0)
            else:
                config.addEntry("nolinear", replace = 0)

        return config

    def writeLilo(self, instRoot, fsset, bl, langs, kernelList, 
                  chainList, defaultDev, justConfig):
        config = self.getBootloaderConfig(instRoot, fsset, bl, langs,
                                          kernelList, chainList, defaultDev)
	config.write(instRoot + self.configfile, perms = self.perms)

        if not justConfig:
	    # throw away stdout, catch stderr
	    str = iutil.execWithCapture(instRoot + '/sbin/lilo' ,
					[ "lilo", "-r", instRoot ],
					catchfd = 2, closefd = 1)
	else:
	    str = ""

	return str
        
    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
		  defaultDev, justConfig):
	if self.useGrubVal:
	    str = self.writeGrub(instRoot, fsset, bl, langs, kernelList, 
				 chainList, defaultDev, justConfig)
	else:
	    str = self.writeLilo(instRoot, fsset, bl, langs, kernelList, 
				 chainList, defaultDev, justConfig)

    def getArgList(self):
        args = bootloaderInfo.getArgList(self)
        
        if not self.useGrubVal:
            args.append("--useLilo")
        # XXX add location of bootloader here too

        return args

    def __init__(self):
        bootloaderInfo.__init__(self)
	self.useGrubVal = 1
        self.kernelLocation = "/boot/"
        self.configfile = "/etc/lilo.conf"
        self.password = None
        self.pure = None

def availableBootDevices(diskSet, fsset):
    devs = []
    foundDos = 0
    for (dev, type) in diskSet.partitionTypes():
        # XXX do we boot fat on anything other than i386?
	if type == 'FAT' and not foundDos and iutil.getArch() == "i386":
	    foundDos = 1
	    isys.makeDevInode(dev, '/tmp/' + dev)

	    try:
		bootable = isys.checkBoot('/tmp/' + dev)
		devs.append((dev, type))
	    except:
		pass
	elif type == 'ntfs' or type =='hpfs':
	    devs.append((dev, type))

    slash = fsset.getEntryByMountPoint('/')
    devs.append((slash.device.getDevice(), slash.fsystem.getName()))

    devs.sort()

    return devs

def bootloaderSetupChoices(dispatch, bl, fsset, diskSet, dir):
    if dir == DISPATCH_BACK:
        return
    
    choices = fsset.bootloaderChoices(diskSet)
    if not choices:
	dispatch.skipStep("instbootloader")
    else:
	dispatch.skipStep("instbootloader", skip = 0)

    bl.images.setup(diskSet, fsset)

    if bl.useDefaultDevice and choices:
        bl.setDevice(choices[0][0])

def writeBootloader(intf, instRoot, fsset, bl, langs, comps):
    justConfigFile = not flags.setupFilesystems

    w = intf.waitWindow(_("Bootloader"), _("Installing bootloader..."))

    kernelList = []
    otherList = []
    rootDev = fsset.getEntryByMountPoint('/').device.getDevice()
    defaultDev = bl.images.getDefault()

    for (dev, (label, longlabel, type)) in bl.images.getImages().items():
	if dev == rootDev:
	    kernelLabel = label
	elif dev == defaultDev:
	    otherList = [(label, dev)] + otherList
	else:
	    otherList.append(label, dev)

    plainLabelUsed = 0
    for (version, nick) in comps.kernelVersionList():
	if plainLabelUsed:
	    kernelList.append("%s-%s" % (kernelLabel, nick), version)
	else:
	    kernelList.append(kernelLabel, version)
	    plainLabelUsed = 1

    if not flags.test:
        bl.write(instRoot, fsset, bl, langs, kernelList, otherList, defaultDev,
                 justConfigFile)

    w.pop()

def makeInitrd (kernelTag, instRoot):
    global initrdsMade

    if iutil.getArch() == 'ia64':
	initrd = "/boot/efi/initrd%s.img" % (kernelTag, )
    else:
	initrd = "/boot/initrd%s.img" % (kernelTag, )
    
    if not initrdsMade.has_key(initrd) and flags.setupFilesystems:
	iutil.execWithRedirect("/sbin/mkinitrd",
			      [ "/sbin/mkinitrd",
				"--ifneeded",
				"-f",
				initrd,
				kernelTag[1:] ],
			      stdout = None, stderr = None, searchPath = 1,
			      root = instRoot)
	initrdsMade[kernelTag] = 1

    return initrd

def grubbyDiskName(name):
    drives = isys.hardDriveDict().keys()
    drives.sort (isys.compareDrives)

    return "hd%d" % drives.index(name)

def grubbyPartitionName(dev):
    cut = len(dev)
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
        return "(%s,%d)" % (grubbyDiskName(name), partNum)
    else:
        return "(%s)" %(grubbyDiskName(name))

# return instance of the appropriate bootloader for our arch
def getBootloader():
    if iutil.getArch() == 'i386':
        return x86BootloaderInfo()
    elif iutil.getArch() == 'ia64':
        return ia64BootloaderInfo()
    else:
        return bootloaderInfo()
