import string
import os
from lilo import LiloConfigFile
import _silo
import iutil
import isys

class SiloInstall:
    def allowSiloLocationConfig(self, fstab):
	bootDevice = fstab.getBootDevice()
	if bootDevice[0:2] == "md":
	    self.setDevice(("raid", bootDevice))
	    return None
	return 1

    def checkUFS(self, dev):
	f = open("/proc/mounts","r")
	lines = f.readlines ()
	f.close ()
	mounted = None
	ufstype = None
	for line in lines:
	    fields = string.split (line)
	    if fields[0] == '/dev/' + dev and fields[2] == 'ufs':
		mounted = fields[1]
	if not mounted:
	    try:
		os.mkdir ("/tmp/ufsmntpoint")
		isys.makeDevInode (dev, "/tmp/" + dev)
		isys.mount ("/tmp/" + dev, "/tmp/ufsmntpoint", "ufs")
	    except:
		try:
		    os.remove ("/tmp/" + dev)
		except:
		    pass
		try:
		    os.rmdir ("/tmp/ufsmntpoint")
		except:
		    pass
		return None
	    root = "/tmp/ufsmntpoint"
	else:
	    root = mounted
	if os.access (root + "/etc/system", os.X_OK):
	    if os.access (root + "/kernel/unix", os.X_OK):
		ufstype = "Solaris"
	    elif os.access (root + "/kernel/genunix", os.X_OK):
		ufstype = "Solaris"
	if os.access (root + "/vmunix", os.X_OK) or os.access (root + "/stand", os.X_OK):
	    if os.access (root + "/bin/sh", os.X_OK):
		# Check if /bin/sh is a.out SPARC binary
		aout = None
		try:
		    f = open (root + "/bin/sh", "r")
		    aout = f.read(4)
		    f.close()
		except:
		    pass
		if aout and len(aout) == 4 and aout[1] == "\x03" and aout[2] == "\x01":
		    if aout[3] == "\x07" or aout[3] == "\x08" or aout[3] == "\x0b":
			ufstype = "SunOS"
	if not mounted:
	    try:
		isys.umount ("/tmp/ufsmntpoint")
	    except:
		pass
	    try:
		os.rmdir ("/tmp/ufsmntpoint")
	    except:
		pass
	    try:
		os.remove ("/tmp/" + dev)
	    except:
		pass
	return ufstype

    def setSiloImages(self, images):
	self.siloImages = images

    def getSiloImages(self, fstab):
	(drives, raid) = fstab.raidList()

	# rearrange the fstab so it's indexed by device
	mountsByDev = {}
	for (mntpoint, device, fsystem, doFormat, size) in \
		fstab.mountList():
	    mountsByDev[device] = mntpoint

	for (mntpoint, device, fstype, raidType, start, size, makeup) in raid:
	    mountsByDev[device] = mntpoint
	    drives.append(device, "", 2, 0, 0)

	for (device, mntpoint, fsystem, makeup) in fstab.existingRaidList():
	    mountsByDev[device] = mntpoint
	    drives.append(device, "", 2, 0, 0)

	oldImages = {}
	for dev in self.siloImages.keys():
	    oldImages[dev] = self.siloImages[dev]

	self.siloImages = {}
	nSolaris = 0
	nSunOS = 0
	for (dev, devName, type, start, size) in drives:
	    # ext2 and raid partitions get listed if 
	    #	    1) they're /
	    #	    2) they're not mounted
	    #	       and contain /boot of
	    #	       some Linux installation
	    # FIXME: For now only list / and UFS partitions,
	    # for 7.0 write code which will read and parse silo.conf from other
	    # Linux partitions and merge it in (after required device
	    # substitions etc.

	    # only list ext2 and ufs partitions
	    if type != 2 and type != 6:
		continue

	    if (mountsByDev.has_key(dev)):
		if mountsByDev[dev] == '/':
		    self.siloImages[dev] = ("linux", 2)
	    elif type == 6:
		if not oldImages.has_key(dev):
		    self.siloImages[dev] = ("", type)
		else:
		    self.siloImages[dev] = oldImages[dev]
		ostype = self.checkUFS(dev)
		if ostype == "Solaris":
		    if nSolaris == 0:
			self.siloImages[dev] = ("solaris", type)
		    else:
			self.siloImages[dev] = ("solaris%d" % nSolaris, type)
		    nSolaris = nSolaris + 1
		elif ostype == "SunOS":
		    if nSunOS == 0:
			self.siloImages[dev] = ("sunos", type)
		    else:
			self.siloImages[dev] = ("sunos%d" % nSunOS, type)
		    nSunOS = nSunOS + 1

	return (self.siloImages, self.default)

    def getSiloMbrDefault(self, fstab):
	# Check partition at cylinder 0 on the boot disk
	# is /, /boot or Linux swap
	bootpart = fstab.getBootDevice()
	if bootpart[:2] == "md":
	    return "mbr"
	i = len (bootpart) - 1
	while i > 0 and bootpart[i] in string.digits:
	    i = i - 1
	boothd = bootpart[:i+1]
	(drives, raid) = fstab.partitionList()
	for (dev, devName, type, start, size) in drives:
	    i = len (dev) - 1
	    while i > 0 and dev[i] in string.digits:
		i = i - 1
	    devhd = dev[:i+1]
	    if devhd == boothd and start == 0:
		if type == 5:
		    return "mbr"
		elif type == 2:
		    if dev == bootpart:
			return "mbr"
		    elif dev == fstab.getRootDevice()[0]:
			return "mbr"
		return "partition"
	return "partition"

    def hasUsableFloppy(self):
	try:
	    f = open("/proc/devices", "r")
	except:
	    return 0
	lines = f.readlines ()
	f.close ()
	for line in lines:
	    if string.strip (line) == "2 fd":
		name = _silo.promRootName()
		if name and name[0:10] == 'SUNW,Ultra' and string.find(name, "Engine") == -1:
		    # Seems like SMCC Ultra box. It is highly probable
		    # the floppies will be unbootable
		    return 1
		return 2
	return 0

    def setPROM(self, linuxAlias, bootDevice):
	self.linuxAlias = linuxAlias
	self.bootDevice = bootDevice

    def hasAliases(self):
	return _silo.hasAliases()

    def disk2PromPath(self,dev):
	return _silo.disk2PromPath(dev)

    def makeInitrd (self, kernelTag, instRoot):
	initrd = "/boot/initrd%s.img" % (kernelTag, )
	if not self.initrdsMade.has_key(initrd):
	    iutil.execWithRedirect("/sbin/mkinitrd",
				  [ "/sbin/mkinitrd",
				    "--ifneeded",
				    initrd,
				    kernelTag[1:] ],
				  stdout = None, stderr = None, searchPath = 1,
				  root = instRoot)
	    self.initrdsMade[kernelTag] = 1
	return initrd

    def getMbrDevices(self, fstab):
	bootpart = fstab.getBootDevice()
	mbrdevs = []
	if bootpart[:2] == "md":
	    (devices, raid) = fstab.raidList()
	    for (raidMntPoint, raidDevice, fsType, raidType, raidStart, raidSize, raidDevs) in raid:
		if raidDevice != bootpart: continue
		for raidDev in raidDevs:
		    for (device, name, type, start, size) in devices:
			if name == raidDev:
			    i = len(device) - 1
			    while i > 0 and device[i] in string.digits:
				i = i - 1
			    mbrdevs.append(device[:i+1])
	else:
	    # Do not use fstab.getMbrDevice() here
	    i = len (bootpart) - 1
	    while i > 0 and bootpart[i] in string.digits:
		i = i - 1
	    mbrdevs.append(bootpart[:i+1])
	return mbrdevs

    def getMbrDevice(self, fstab):
	return self.getMbrDevices(fstab)[0]

    def install(self, fstab, instRoot, hdList, upgrade):
	if not self.siloDevice: return

	silo = LiloConfigFile ()

	if not self.siloImages:
	    (images, default) = self.getSiloImages(fstab)
	    self.setSiloImages(images)

	bootpart = fstab.getBootDevice()
	boothd = self.getMbrDevice(fstab)
	smpInstalled = (hdList.has_key('kernel-smp') and 
			hdList['kernel-smp'].selected)

	rootDev = fstab.getRootDevice ()
	if rootDev:
	    # strip off the filesystem; we don't need it
	    rootDev = rootDev[0]
	else:
	    raise RuntimeError, "Installing silo, but there is no root device"

	args = [ "silo" ]

	if bootpart[:2] == "md":
	    self.siloDevice = "mbr"
	else:
	    if self.siloDevice != "mbr":
		args.append("-t")

	    i = len (bootpart) - 1
	    while i > 0 and bootpart[i] in string.digits:
		i = i - 1
            silo.addEntry("partition", bootpart[i+1:])

	silo.addEntry("timeout", "50")
	silo.addEntry("root", '/dev/' + rootDev)
	silo.addEntry("read-only")

	kernelList = []
	otherList = []

	main = "linux"

	for (drive, (label, siloType)) in self.siloImages.items ():
	    if (drive == rootDev) and label:
		main = label
	    elif label:
		i = len(drive) - 1
		while i > 0 and drive[i] in string.digits:
		    i = i - 1
		prompath = drive[:i+1]
		if bootpart[:2] != "md" and prompath == boothd:
		    prompath = drive[i+1:]
		else:
		    prompath = self.disk2PromPath(prompath)
		    if prompath:
			if prompath[:3] == 'sd(':
			    prompath = prompath + drive[i+1:]
			else:
			    prompath = prompath + ";" + drive[i+1:]
		if prompath:
		    otherList.append (label, prompath)

	silo.addEntry("default", main)

	label = main
	if (smpInstalled):
	    kernelList.append((main, hdList['kernel-smp'], "smp"))
	    label = main + "-up"

	kernelList.append((label, hdList['kernel'], ""))

	for (label, kernel, tag) in kernelList:
	    kernelTag = "-%s-%s%s" % (kernel[rpm.RPMTAG_VERSION],
                                      kernel[rpm.RPMTAG_RELEASE], tag)
	    initrd = self.makeInitrd (kernelTag, instRoot)
	    if rootDev == bootpart:
		kernelFile = "/boot/vmlinuz" + kernelTag
		initrdFile = initrd
	    else:
		kernelFile = "/vmlinuz" + kernelTag
		initrdFile = initrd[5:]

	    try:
		(fsType, sl) = silo.getImage(label)
		silo.delImage(label)
	    except IndexError, msg:
		sl = LiloConfigFile(imageType = "image", path = kernelFile)

	    sl.addEntry("label", label)
	    if os.access (instRoot + initrd, os.R_OK):
		sl.addEntry("initrd", initrdFile)

	    if self.siloAppend:
		sl.addEntry('append', '"%s"' % self.siloAppend)

	    silo.addImage (sl)

	for (label, device) in otherList:
	    try:
		(fsType, sl) = silo.getImage(label)
		silo.delImage(label)
	    except IndexError:
                sl = LiloConfigFile(imageType = "other", path = device)
	    sl.addEntry("label", label)
	    silo.addImage (sl)

	# for (siloType, name, config) in silo.images:
	#    # remove entries for missing kernels (upgrade)
	#    if siloType == "image":
	#	if not os.access (todo.instPath + name, os.R_OK):
	#	    silo.delImage (name)
	#    # remove entries for unbootable partitions
	#    elif siloType == "other":
	#	device = name[5:]
	#	isys.makeDevInode(device, '/tmp/' + device)
	#	if not isys.checkBoot ('/tmp/' + device):
	#	    lilo.delImage (name)
	#	os.remove ('/tmp/' + device)

	if fstab.getBootDevice() != fstab.getRootDevice()[0]:
	    silo.write(instRoot + "/boot/silo.conf")
	    try:
		os.remove(instRoot + "/etc/silo.conf")
	    except:
		pass
	    os.symlink("../boot/silo.conf", instRoot + "/etc/silo.conf")
	else:
	    silo.write(instRoot + "/etc/silo.conf")

	if self.serial:
	    messages = "/tmp/silo.log"
	else:
	    messages = "/dev/tty3"
	iutil.execWithRedirect('/sbin/silo',
			       args,
			       stdout = None,
			       root = instRoot)

	if bootpart[:2] == "md":
	    mbrdevs = self.getMbrDevices(fstab)
	    linuxAliases = []
	    for mbrdev in mbrdevs:
		device = mbrdev
		try:
		    num = _silo.zeroBasedPart(instRoot + "/dev/" + mbrdev)
		    if num:
			device = mbrdev + "%d" % num
		except:
		    pass
		linuxAliases.append(self.disk2PromPath(device))
	    bootDevice = linuxAliases[0]
	    linuxAlias = ""
	    for alias in linuxAliases:
		if alias and alias != "":
		    if linuxAlias != "":
			linuxAlias = linuxAlias + ";"
		    linuxAlias = linuxAlias + alias
	elif self.siloDevice == "mbr":
	    device = boothd
	    try:
		num = _silo.zeroBasedPart(instRoot + "/dev/" + boothd)
		if num:
		    device = boothd + "%d" % num
	    except:
		pass
	    linuxAlias = self.disk2PromPath(device)
	    bootDevice = linuxAlias
	else:
	    device = bootpart
	    linuxAlias = self.disk2PromPath(device)
	    bootDevice = linuxAlias

	if not (self.linuxAlias and self.hasAliases()):
	    linuxAlias = ""
	if not self.bootDevice:
	    bootDevice = ""
	if not linuxAlias:
	    linuxAlias = ""
	_silo.setPromVars(linuxAlias,bootDevice)

    def setDevice(self, device):
	if (type(device) == type((1,))):
	    self.siloDevice = device
	elif device != "mbr" and device != "partition" and device:
	    raise ValueError, "device must be raid, mbr, partition, or None"
	self.siloDevice = device

    def setAppend(self, append):
	self.siloAppend = append

    def setDefault(self, default):
	for (label, fsType) in self.siloImages.values():
	    if label == default:
		self.default = default
		return
	raise IndexError, "unknown silo label %s" % (default,)

    def getLinear(self):
	return self.siloLinear

    def getDevice(self):
	return self.siloDevice

    def getAppend(self):
	return self.siloAppend

    def __init__(self, serial = 0):
	self.siloImages = {}
	self.siloDevice = 'mbr'
	self.siloLinear = 1
	self.siloAppend = None
	self.default = None
	self.initrdsMade = {}
	self.serial = serial
	self.linuxAlias = 1
	self.bootDevice = 1
