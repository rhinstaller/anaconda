import isys
import partitioning
from translate import _
from lilo import LiloConfigFile
import os
import language
from flags import flags
import iutil
import string
from log import log

initrdsMade = {}

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

    # returns dictionary of (label, devtype) pairs indexed by device
    def getImages(self):
	# return a copy so users can modify it w/o affecting us

	dict = {}
	for key in self.images.keys():
	    dict[key] = self.images[key]

	return dict

    def setImageLabel(self, dev, label):
	self.images[dev] = (label, self.images[dev][1])

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
	    if devices.has_key(dev): del self.images[dev]

	# These have appeared
	for (dev, type) in devs:
	    if not self.images.has_key(dev):
                if type == "FAT":
                    self.images[dev] = ("DOS", type)
                else:
                    self.images[dev] = (None, type)

	if not self.images.has_key(self.default):
	    entry = fsset.getEntryByMountPoint('/')
	    self.default = entry.device.getDevice()
	    (label, type) = self.images[self.default]
	    if not label:
		self.images[self.default] = ("Red Hat Linux 7.2", type)

    def __init__(self):
	self.default = None
	self.images = {}
	
class x86BootloaderInfo:

    def getDevice(self):
	return self.device

    def setDevice(self, device):
	self.device = device

    def setUseGrub(self, val):
	self.useGrubVal = val

    def useGrub(self):
	return self.useGrubVal

    def writeGrub(self, instRoot, fsset, bl, langs, kernelList, chainList,
		  defaultDev, justConfigFile):
	images = bl.images.getImages()
        rootDev = fsset.getEntryByMountPoint("/").device.getDevice()
	grubRootDev = grubbyPartitionName(rootDev)

	cf = '/boot/grub/grub.conf'
	perms = 0644
        if os.access (instRoot + cf, os.R_OK):
	    perms = os.stat(instRoot + cf)[0] & 0777
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

	for (label, version) in kernelList:
	    kernelTag = "-" + version
	    kernelFile = cfPath + "vmlinuz" + kernelTag

	    initrd = makeInitrd (kernelTag, instRoot)

	    f.write('title %s (%s)\n' % (label, version))
	    f.write('\troot %s\n' % grubbyPartitionName(bootDev))
	    f.write('\tkernel %s ro root=/dev/%s' % (kernelFile, rootDev))
	    if self.args.get():
		f.write(' %s' % self.args.get())
	    f.write('\n')

	    if os.access (instRoot + initrd, os.R_OK):
		f.write('\tinitrd %s\n' % (cfPath + initrd[len(cfPath):]))

	for (label, device) in chainList:
	    f.write('title %s (%s)\n' % (label, version))
	    f.write('\trootnoverify %s\n' % grubbyPartitionName(device))
            f.write('\tmakeactive\n')
            f.write('\tchainloader +1')
	    f.write('\n')

	f.close()

	part = grubbyPartitionName(bootDev)
	prefix = grubbyPartitionName(bootDev) + "/" + grubPath
	cmd = "root %s\ninstall %s/i386-pc/stage1 d (%s) %s/i386-pc/stage2 p %s%s/grub.conf" % \
	    (part, grubPath, grubbyDiskName(bl.getDevice()), grubPath,
	     part, grubPath)

	log("GRUB command %s", cmd)

	if not justConfigFile:
	    p = os.pipe()
	    os.write(p[1], cmd + '\n')
	    os.close(p[1])

	    iutil.execWithRedirect('/sbin/grub' ,
				    [ "grub", "--batch" ], stdin = p[0],
				    stdout = "/dev/tty5", stderr = "/dev/tty5",
				    root = instRoot)
	    os.close(p[0])

	return None

    def writeLilo(self, instRoot, fsset, bl, langs, kernelList, chainList,
		  defaultDev, justConfigFile):
	images = bl.images.getImages()

        # on upgrade read in the lilo config file
	lilo = LiloConfigFile ()
	perms = 0644
        if os.access (instRoot + '/etc/lilo.conf', os.R_OK):
	    perms = os.stat(instRoot + '/etc/lilo.conf')[0] & 0777
	    lilo.read (instRoot + '/etc/lilo.conf')
	    os.rename(instRoot + '/etc/lilo.conf',
		      instRoot + '/etc/lilo.conf.rpmsave')

	# Remove any invalid entries that are in the file; we probably
	# just removed those kernels. 
	for label in lilo.listImages():
	    (fsType, sl) = lilo.getImage(label)
	    if fsType == "other": continue

	    if not os.access(instRoot + sl.getPath(), os.R_OK):
		lilo.delImage(label)

	liloTarget = bl.getDevice()

	lilo.addEntry("boot", '/dev/' + liloTarget, replace = 0)
	lilo.addEntry("map", "/boot/map", replace = 0)
	lilo.addEntry("install", "/boot/boot.b", replace = 0)
	lilo.addEntry("prompt", replace = 0)
	lilo.addEntry("timeout", "50", replace = 0)
        message = "/boot/message"
        for lang in language.expandLangs(langs.getDefault()):
            fn = "/boot/message." + lang
            if os.access(instRoot + fn, os.R_OK):
                message = fn
                break

	lilo.addEntry("message", message, replace = 0)

        if not lilo.testEntry('lba32') and not lilo.testEntry('linear'):
	    lilo.addEntry("linear", replace = 0)

        rootDev = fsset.getEntryByMountPoint("/").device.getDevice()
	if not rootDev:
            raise RuntimeError, "Installing lilo, but there is no root device"

	if rootDev == defaultDev:
	    lilo.addEntry("default", kernelList[0][0])
	else:
	    lilo.addEntry("default", otherList[0][0])

	for (label, version) in kernelList:
	    kernelTag = "-" + version
	    kernelFile = "/boot/vmlinuz" + kernelTag

	    try:
		lilo.delImage(label)
	    except IndexError, msg:
		pass

	    sl = LiloConfigFile(imageType = "image", path = kernelFile)

	    initrd = makeInitrd (kernelTag, instRoot)

	    sl.addEntry("label", label)
	    if os.access (instRoot + initrd, os.R_OK):
		sl.addEntry("initrd", initrd)

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
		sl = LiloConfigFile(imageType = "other", path = device)
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

	lilo.write(instRoot + "/etc/lilo.conf", perms = perms)

	if not justConfigFile:
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


    def __init__(self):
	self.args = KernelArguments()
	self.images = BootImages()
	self.useGrubVal = 1		    # use lilo otherwise
	self.device = None

def availableBootDevices(diskSet, fsset):
    devs = []
    foundDos = 0
    for (dev, type) in diskSet.partitionTypes():
	if type == 'FAT' and not foundDos:
	    foundDos = 1
	    isys.makeDevInode(dev, '/tmp/' + dev)

	    try:
		bootable = isys.checkBoot('/tmp/' + dev)
		devs.append((dev, type))
	    except:
		pass
	elif type == 'ntfs' or type =='hpfs':
	    devs.append((dev, type))

    devs.append((fsset.getEntryByMountPoint('/').device.getDevice(), 'ext2'))

    devs.sort()

    return devs

def partitioningComplete(dispatch, bl, fsset, diskSet):
    choices = fsset.bootloaderChoices(diskSet)
    if not choices:
	dispatch.skipStep("instbootloader")
    else:
	dispatch.skipStep("instbootloader", skip = 0)

    bl.images.setup(diskSet, fsset)

def writeBootloader(intf, instRoot, fsset, bl, langs, comps):
    justConfigFile = not flags.setupFilesystems

    w = intf.waitWindow(_("Bootloader"), _("Installing bootloader..."))

    kernelList = []
    otherList = []
    rootDev = fsset.getEntryByMountPoint('/').device.getDevice()
    defaultDev = bl.images.getDefault()

    for (dev, (label, type)) in bl.images.getImages().items():
	if dev == rootDev:
	    kernelLabel = label
	elif dev == defaultDev:
	    otherList = [(label, dev)] + otherList
	else:
	    otherList.append(label, dev)

    plainLabelUsed = 0
    for (version, nick) in comps.kernelVersionList():
	if plainLabelUsed:
	    kernelList.append(kernelLabel + "-" + nick, version)
	else:
	    kernelList.append(kernelLabel, version)
	    plainLabelUsed = 1

    bl.write(instRoot, fsset, bl, langs, kernelList, otherList, defaultDev,
	     justConfigFile)

    w.pop()

def makeInitrd (kernelTag, instRoot):
    global initrdsMade

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
    cut = -1
    if dev[-2] in string.digits:
	cut = -2

    partNum = int(dev[cut:]) - 1
    name = dev[:cut]

    # hack off the trailing 'p' from /dev/cciss/*, for example
    if name[-1] == 'p':
	for letter in name:
	    if letter not in string.letters and letter != "/":
		name = name[:-1]
		break

    return "(%s,%d)" % (grubbyDiskName(name), partNum)
