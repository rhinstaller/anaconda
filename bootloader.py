#
# bootloader.py: bootloader configuration data
#
# Erik Troan <ewt@redhat.com>
# Jeremy Katz <katzj@redhat.com>
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
if iutil.getArch() == "i386":
    import edd
from flags import flags
from log import log
from constants import *
from lilo import LiloConfigFile
from translate import _

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

    def chandevget(self):
        return self.cargs

    def chandevset(self, args):
        self.cargs = args

    def __init__(self):
	if iutil.getArch() == "s390" or iutil.getArch() == "s390x":
	    self.args = ""
	    self.cargs = []
	    if os.environ.has_key("DASD"):
                self.args = "dasd=" + os.environ["DASD"]
	    if os.environ.has_key("CHANDEV"):
	        self.cargs.append(os.environ["CHANDEV"])
	    if os.environ.has_key("QETHPARM"):
	        self.cargs.append(os.environ["QETHPARM"])
	else:
	    cdrw = isys.ideCdRwList()
	    str = ""
	    for device in cdrw:
                if str: str = str + " "
                str = str + ("%s=ide-scsi" % device)
                
            self.args = str

class BootImages:

    # returns dictionary of (label, longlabel, devtype) pairs indexed by device
    def getImages(self):
	# return a copy so users can modify it w/o affecting us

	dict = {}
	for key in self.images.keys():
	    dict[key] = self.images[key]

	return dict

    def setImageLabel(self, dev, label, setLong = 0):
        if setLong:
            self.images[dev] = (self.images[dev][0], label, self.images[dev][2])
        else:
            self.images[dev] = (label, self.images[dev][1], self.images[dev][2])            
            

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

	for (label, longlabel, version) in kernelList:
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

	for (label, longlabel, device) in chainList:
            if ((not label) or (label == "")):
                continue
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
		  defaultDev, justConfig, intf):
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
    def noKernelsWarn(self, intf):
        intf.messageWindow(_("Warning"),
                           _("No kernel packages were installed on your "
                             "system.  Your boot loader configuration "
                             "will not be changed."))

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
        self.defaultDevice = None  # XXX hack, used by kickstart
        self.useGrubVal = 0      # only used on x86
        self.configfile = None
        self.kernelLocation = "/boot/"
        self.forceLBA32 = 0
	self.password = None
        self.pure = None
        self.above1024 = 0

class ia64BootloaderInfo(bootloaderInfo):
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
            if len(fields) < 4:
                continue
            if fields[1:4] == ["Red","Hat","Linux"]:
                entry = fields[0][4:8]
                iutil.execWithRedirect('/usr/sbin/efibootmgr',
                                       ["efibootmgr", "-b", entry, "-B"],
                                       root = instRoot,
                                       stdout="/dev/tty5", stderr="/dev/tty5")
            

    def writeLilo(self, instRoot, fsset, bl, langs, kernelList, 
                  chainList, defaultDev, justConfig):
        config = self.getBootloaderConfig(instRoot, fsset, bl, langs,
                                          kernelList, chainList, defaultDev)
	config.write(instRoot + self.configfile, perms = self.perms)

	return ""
        
    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
		  defaultDev, justConfig, intf):
        if len(kernelList) >= 1:
            str = self.writeLilo(instRoot, fsset, bl, langs, kernelList, 
                                 chainList, defaultDev, justConfig)
        else:
            self.noKernelsWarn(intf)

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

        self.removeOldEfiEntries(instRoot)            
                    
        argv = [ "/usr/sbin/efibootmgr", "-c" , "-w", "-L",
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
        if len(kernelList) < 1:
            return ""
        
	images = bl.images.getImages()
        rootDev = fsset.getEntryByMountPoint("/").device.getDevice()

        if not os.path.isdir(instRoot + '/boot/grub/'):
            os.mkdir(instRoot + '/boot/grub', 0755)

	cf = '/boot/grub/grub.conf'
	self.perms = 0600
        if os.access (instRoot + cf, os.R_OK):
	    self.perms = os.stat(instRoot + cf)[0] & 0777
	    os.rename(instRoot + cf,
		      instRoot + cf + '.rpmsave')

        grubTarget = bl.getDevice()
        # XXX wouldn't it be nice if grub really understood raid? :)
        if grubTarget[:2] == "md":
            device = fsset.getEntryByDeviceName(grubTarget).device.members[0]
            (grubTarget, None) = getDiskPart(device)

	f = open(instRoot + cf, "w+")

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
            f.write ("# NOTICE:  You do not have a /boot partition.  This means that\n")
            f.write ("#          all kernel and initrd paths are relative to /, eg.\n")            
	else:
            f.write ("# NOTICE:  You have a /boot partition.  This means that\n")
            f.write ("#          all kernel and initrd paths are relative to /boot/, eg.\n")

        bootDev = bootDev.device.getDevice(asBoot = 1)
        
        f.write ('#          root %s\n' % grubbyPartitionName(bootDev))
        f.write ("#          kernel %svmlinuz-version ro root=/dev/%s\n" % (cfPath, rootDev))
        f.write ("#          initrd %sinitrd-version.img\n" % (cfPath))
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
        f.write('timeout=10\n')
        f.write('splashimage=%s%sgrub/splash.xpm.gz\n'
                % (grubbyPartitionName(bootDev), cfPath))

        usedDevs[bootDev] = 1
        usedDevs[grubTarget] = 1

        if self.password:
            f.write('password --md5 %s\n' %(self.password))
        
	for (label, longlabel, version) in kernelList:
	    kernelTag = "-" + version
	    kernelFile = "%svmlinuz%s" % (cfPath, kernelTag)

	    initrd = makeInitrd (kernelTag, instRoot)

	    f.write('title %s (%s)\n' % (longlabel, version))
	    f.write('\troot %s\n' % grubbyPartitionName(bootDev))
	    f.write('\tkernel %s ro root=/dev/%s' % (kernelFile, rootDev))
	    if self.args.get():
		f.write(' %s' % self.args.get())
	    f.write('\n')

	    if os.access (instRoot + initrd, os.R_OK):
		f.write('\tinitrd %sinitrd%s.img\n' % (cfPath, kernelTag))

	for (label, longlabel, device) in chainList:
            if ((not longlabel) or (longlabel == "")):
                continue
	    f.write('title %s\n' % (longlabel))
	    f.write('\trootnoverify %s\n' % grubbyPartitionName(device))
#            f.write('\tmakeactive\n')
            f.write('\tchainloader +1')
	    f.write('\n')
            usedDevs[device] = 1

	f.close()
        os.chmod(instRoot + "/boot/grub/grub.conf", self.perms)

        # make a symlink for menu.lst since it's the default config file name
        if os.access (instRoot + "/boot/grub/menu.lst", os.R_OK):
	    os.rename(instRoot + "/boot/grub/menu.lst",
		      instRoot + "/boot/grub/menu.lst.rpmsave")
        os.symlink("./grub.conf", instRoot + "/boot/grub/menu.lst")
 
        # make a symlink for /etc/grub.conf since config files belong in /etc
        if os.access (instRoot + "/etc/grub.conf", os.R_OK):
	    os.rename(instRoot + "/etc/grub.conf",
		      instRoot + "/etc/grub.conf.rpmsave")
        os.symlink("../boot/grub/grub.conf", instRoot + "/etc/grub.conf")
       

        if not os.access(instRoot + "/boot/grub/device.map", os.R_OK):
            f = open(instRoot + "/boot/grub/device.map", "w+")
            f.write("# this device map was generated by anaconda\n")
            f.write("(fd0)     /dev/fd0\n")
            devs = usedDevs.keys()
            devs.sort()
            usedDevs = {}
            for dev in devs:
                drive = getDiskPart(dev)[0]
                if usedDevs.has_key(drive):
                    continue
                f.write("(%s)     /dev/%s\n" % (grubbyDiskName(drive), drive))
                usedDevs[drive] = 1
            f.close()
        
        if self.forceLBA32:
            forcelba = "--force-lba "
        else:
            forcelba = ""

	part = grubbyPartitionName(bootDev)
 	prefix = "%s/%s" % (grubbyPartitionName(bootDev), grubPath)
	cmd = "root %s\ninstall %s%s/stage1 d %s %s/stage2 p %s%s/grub.conf" % \
	    (part, forcelba, grubPath, grubbyPartitionName(grubTarget),
             grubPath, part, grubPath)

	if not justConfigFile:
            log("GRUB command %s", cmd)

            # copy the stage files over into /boot
            iutil.execWithRedirect( "/sbin/grub-install",
                                    ["/sbin/grub-install", "--just-copy"],
                                    stdout = "/dev/tty5", stderr = "/dev/tty5",
                                    root = instRoot)


            # really install the bootloader
	    p = os.pipe()
	    os.write(p[1], cmd + '\n')
	    os.close(p[1])
	    iutil.execWithRedirect('/sbin/grub' ,
				    [ "grub",  "--batch", "--no-floppy",
                                      "--device-map=/boot/grub/device.map" ],
                                    stdin = p[0],
				    stdout = "/dev/tty5", stderr = "/dev/tty5",
				    root = instRoot)
	    os.close(p[0])

	return ""

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
            if self.forceLBA32 or (bl.above1024 and edd.detect()):
                config.addEntry("lba32", replace = 0)
            elif self.useLinear:
                config.addEntry("linear", replace = 0)
            else:
                config.addEntry("nolinear", replace = 0)

        return config

    def writeLilo(self, instRoot, fsset, bl, langs, kernelList, 
                  chainList, defaultDev, justConfig):
        if len(kernelList) >= 1:
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
		  defaultDev, justConfig, intf):
        if len(kernelList) < 1:
            self.noKernelsWarn(intf)

        str = self.writeLilo(instRoot, fsset, bl, langs, kernelList, 
                             chainList, defaultDev,
                             justConfig | (self.useGrubVal))
        str = self.writeGrub(instRoot, fsset, bl, langs, kernelList, 
                             chainList, defaultDev,
                             justConfig | (not self.useGrubVal))
        # XXX move the lilo.conf out of the way if they're using GRUB
        # so that /sbin/installkernel does a more correct thing
        if self.useGrubVal and os.access(instRoot + '/etc/lilo.conf', os.R_OK):
            os.rename(instRoot + "/etc/lilo.conf",
                      instRoot + "/etc/lilo.conf.anaconda")
        
        

    def getArgList(self):
        args = bootloaderInfo.getArgList(self)
        
        if not self.useGrubVal:
            args.append("--useLilo")
        if self.forceLBA32:
            args.append("--lba32")
        if not self.useLinear:
            args.append("--nolinear")
        if self.password:
            args.append("--md5pass=%s" %(self.password))
        
        
        # XXX add location of bootloader here too

        return args

    def __init__(self):
        bootloaderInfo.__init__(self)
	self.useGrubVal = 1
        self.kernelLocation = "/boot/"
        self.configfile = "/etc/lilo.conf"
        self.password = None
        self.pure = None

class s390BootloaderInfo(bootloaderInfo):
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

        #lilo.addEntry("prompt", replace = 0)
	#lilo.addEntry("timeout", "50", replace = 0)

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

	    initrd = makeInitrd (kernelTag, instRoot)

	    sl.addEntry("label", label)
	    if os.access (instRoot + initrd, os.R_OK):
		sl.addEntry("initrd", "%sinitrd%s.img" %(self.kernelLocation, kernelTag))

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

    def writeChandevConf(self, instroot, bl):   # S/390 only 
	cf = "/etc/chandev.conf"
	self.perms = 0644
        fd = open(instroot + cf, "w+")
        for cdev in bl.args.chandevget():
            fd.write('%s\n' % cdev)
	fd.close()
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

        cfPath = "/boot/"
	for (label, longlabel, version) in kernelList:
	    kernelTag = "-" + version
	    kernelFile = "%svmlinuz%s" % (cfPath, kernelTag)

	    initrd = makeInitrd (kernelTag, instRoot)
	    f.write('[%s]\n' % (label))
	    f.write('\ttarget=%s\n' % (self.kernelLocation))
	    f.write('\timage=%s\n' % (kernelFile))
	    if os.access (instRoot + initrd, os.R_OK):
		f.write("ramdisk=%sinitrd%s.img\n" %(self.kernelLocation, kernelTag))
	    if self.args.get():
		f.write('\tparameters="root=/dev/%s %s"\n' % (rootDev, self.args.get()))
	    f.write('\n')

	f.close()

	if not justConfigFile:
            argv = [ "/sbin/zipl" ]
            iutil.execWithRedirect(argv[0], argv, root = instRoot,
                                   stdout = "/dev/stdout",
                                   stderr = "/dev/stderr")
            
	return ""

    def write(self, instRoot, fsset, bl, langs, kernelList, chainList,
		  defaultDev, justConfig, intf):
        str = self.writeZipl(instRoot, fsset, bl, langs, kernelList, 
                             chainList, defaultDev,
                             justConfig | (not self.useZiplVal))
	str = self.writeChandevConf(instRoot, bl)
    
    def __init__(self):
        bootloaderInfo.__init__(self)
        self.useGrubVal = 0      # only used on x86
        self.useZiplVal = 1      # only used on s390
        self.kernelLocation = "/boot/"
        self.configfile = "/etc/zipl.conf"


def availableBootDevices(diskSet, fsset):
    devs = []
    foundDos = 0
    for (dev, type) in diskSet.partitionTypes():
        # XXX do we boot fat on anything other than i386?
	if type == 'FAT' and not foundDos and iutil.getArch() == "i386":
	    isys.makeDevInode(dev, '/tmp/' + dev)
            part = partitioning.get_partition_by_name(diskSet.disks, dev)
            if part.native_type not in partitioning.dosPartitionTypes:
                continue

	    try:
		bootable = isys.checkBoot('/tmp/' + dev)
		devs.append((dev, type))
                foundDos = 1
	    except:
		pass
	elif type == 'ntfs' or type =='hpfs':
	    devs.append((dev, type))

    slash = fsset.getEntryByMountPoint('/')
    if not slash or not slash.device or not slash.fsystem:
        raise ValueError, ("Trying to pick boot devices but do not have a "
                           "sane root partition.  Aborting install.")
    devs.append((slash.device.getDevice(), slash.fsystem.getName()))

    devs.sort()

    return devs

def bootloaderSetupChoices(dispatch, bl, fsset, diskSet, dir):
    if dir == DISPATCH_BACK:
        return

    # do not give option to change bootloader if partitionless case
    if fsset.rootOnLoop():
        bl.setUseGrub(0)
        dispatch.skipStep("bootloader")
        dispatch.skipStep("bootloaderpassword")
	dispatch.skipStep("instbootloader")
        return
    
    choices = fsset.bootloaderChoices(diskSet)
    if not choices:
	dispatch.skipStep("instbootloader")
    else:
	dispatch.skipStep("instbootloader", skip = 0)

    bl.images.setup(diskSet, fsset)

    if bl.defaultDevice != None and choices:
        if bl.defaultDevice > len(choices):
            bl.defaultDevice = len(choices)
        bl.setDevice(choices[bl.defaultDevice][0])

    bootDev = fsset.getEntryByMountPoint("/")
    if not bootDev:
        bootDev = fsset.getEntryByMountPoint("/boot")
    part = partitioning.get_partition_by_name(diskSet.disks, bootDev.device.getDevice())
    if part and partitioning.end_sector_to_cyl(part.geom.disk.dev,
                                               part.geom.end) >= 1024:
        bl.above1024 = 1
    

def writeBootloader(intf, instRoot, fsset, bl, langs, comps):
    justConfigFile = not flags.setupFilesystems

    if bl.defaultDevice == -1:
        return

    w = intf.waitWindow(_("Bootloader"), _("Installing bootloader..."))

    kernelList = []
    otherList = []
    rootDev = fsset.getEntryByMountPoint('/').device.getDevice()
    defaultDev = bl.images.getDefault()

    for (dev, (label, longlabel, type)) in bl.images.getImages().items():
	if dev == rootDev:
	    kernelLabel = label
            kernelLongLabel = longlabel
	elif dev == defaultDev:
	    otherList = [(label, longlabel, dev)] + otherList
	else:
	    otherList.append(label, longlabel, dev)

    plainLabelUsed = 0
    for (version, nick) in comps.kernelVersionList():
	if plainLabelUsed:
	    kernelList.append("%s-%s" % (kernelLabel, nick),
                              "%s-%s" % (kernelLongLabel, nick), version)
	else:
	    kernelList.append(kernelLabel, kernelLongLabel, version)
	    plainLabelUsed = 1


    bl.write(instRoot, fsset, bl, langs, kernelList, otherList, defaultDev,
                 justConfigFile, intf)

    w.pop()

# note that this function no longer actually creates an initrd.
# the kernel's %post does this now
def makeInitrd (kernelTag, instRoot):
    if iutil.getArch() == 'ia64':
	initrd = "/boot/efi/initrd%s.img" % (kernelTag, )
    else:
	initrd = "/boot/initrd%s.img" % (kernelTag, )

    return initrd

# return (disk, partition number) eg ('hda', 1)
def getDiskPart(dev):
    cut = len(dev)
    if dev[:3] == "rd/" or dev[:4] == "ida/" or dev[:6] == "cciss/":
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

def grubbyDiskName(name):
    drives = isys.hardDriveDict().keys()
    drives.sort (isys.compareDrives)

    return "hd%d" % drives.index(name)

def grubbyPartitionName(dev):
    (name, partNum) = getDiskPart(dev)
    if partNum != None:
        return "(%s,%d)" % (grubbyDiskName(name), partNum)
    else:
        return "(%s)" %(grubbyDiskName(name))

# return instance of the appropriate bootloader for our arch
def getBootloader():
    if iutil.getArch() == 'i386':
        return x86BootloaderInfo()
    elif iutil.getArch() == 'ia64':
        return ia64BootloaderInfo()
    elif iutil.getArch() == 's390' or iutil.getArch() == "s390x":
        return s390BootloaderInfo()
    else:
        return bootloaderInfo()
