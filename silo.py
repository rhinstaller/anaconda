import string
import os
from lilo import LiloConfiguration
import _silo
import iutil
import isys

class SiloInstall:
    def __init__ (self, todo):
	self.todo = todo
	self.linuxAlias = 1
	self.bootDevice = 1

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

    def getSiloImages(self):
	todo = self.todo

	if not todo.__dict__.has_key('fstab'):
	    raise RuntimeError, "No fstab object"

	(drives, raid) = todo.fstab.partitionList()

	# rearrange the fstab so it's indexed by device
	mountsByDev = {}
	for (mntpoint, device, fsystem, doFormat, size) in \
		self.todo.fstab.mountList():
	    mountsByDev[device] = mntpoint

	oldImages = {}
	for dev in todo.liloImages.keys():
	    oldImages[dev] = todo.liloImages[dev]

	todo.liloImages = {}
	nSolaris = 0
	nSunOS = 0
	for (dev, devName, type, start, size) in drives:
	    # ext2 partitions get listed if 
	    #	    1) they're /
	    #	    2) they're not mounted
	    #	       and contain /boot of
	    #	       some Linux installation
	    # FIXME: For now only list / and UFS partitions,
	    # for 6.2 write code which will read and parse silo.conf from other
	    # Linux partitions and merge it in (after required device
	    # substitions etc.

	    # only list ext2 and ufs partitions
	    if type != 2 and type != 6:
		continue

	    if (mountsByDev.has_key(dev)):
		if mountsByDev[dev] == '/':
		    todo.liloImages[dev] = ("linux", 2)
	    elif type == 6:
		if not oldImages.has_key(dev):
		    todo.liloImages[dev] = ("", type)
		else:
		    todo.liloImages[dev] = oldImages[dev]
		ostype = self.checkUFS(dev)
		if ostype == "Solaris":
		    if nSolaris == 0:
			todo.liloImages[dev] = ("solaris", type)
		    else:
			todo.liloImages[dev] = ("solaris%d" % nSolaris, type)
		    nSolaris = nSolaris + 1
		elif ostype == "SunOS":
		    if nSunOS == 0:
			todo.liloImages[dev] = ("sunos", type)
		    else:
			todo.liloImages[dev] = ("sunos%d" % nSunOS, type)
		    nSunOS = nSunOS + 1

	return todo.liloImages

    def getSiloOptions(self):
	bootpart = self.todo.fstab.getBootDevice()
	i = len (bootpart) - 1
	while i > 0 and bootpart[i] in string.digits:
	    i = i - 1
	boothd = bootpart[:i+1]

	mbrpart = None

	(drives, raid) = self.todo.fstab.partitionList()
	for (dev, devName, type, start, size) in drives:
	    i = len (dev) - 1
	    while i > 0 and dev[i] in string.digits:
		i = i - 1
	    devhd = dev[:i+1]
	    if devhd == boothd and start == 0:
		mbrpart = dev
		break

	if not mbrpart: mbrpart = boothd + "3"
	return (bootpart, boothd, mbrpart)

    def getSiloMbrDefault(self):
	# Check partition at cylinder 0 on the boot disk
	# is /, /boot or Linux swap
	bootpart = self.todo.fstab.getBootDevice()
	i = len (bootpart) - 1
	while i > 0 and bootpart[i] in string.digits:
	    i = i - 1
	boothd = bootpart[:i+1]
	(drives, raid) = self.todo.fstab.partitionList()
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
		    elif dev == self.todo.fstab.getRootDevice()[0]:
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

    def installSilo (self):
	todo = self.todo
	silo = LiloConfiguration ()

	if not todo.liloImages:
	    todo.setLiloImages(self.getSiloImages())

	# OK - for this release we need to just blow away the old silo.conf
	# just like we used to.
##	 # on upgrade read in the silo config file
##	 if os.access (todo.instPath + '/etc/silo.conf', os.R_OK):
##	     silo.read (todo.instPath + '/etc/silo.conf')
##	 elif not todo.liloDevice: return

	(bootpart, boothd, mbrpart) = self.getSiloOptions()
	smpInstalled = (self.todo.hdList.has_key('kernel-smp') and 
			self.todo.hdList['kernel-smp'].selected)

	rootDev = self.todo.fstab.getRootDevice()[0]

	args = [ "silo" ]

	if todo.liloDevice == "mbr":
	    device = mbrpart
	    try:
		num = _silo.zeroBasedPart(todo.instPath + "/dev/" + boothd)
		if num:
		    device = boothd + "%d" % num
	    except:
		pass
	else:
	    device = bootpart
	    args.append("-t")
	bootDevice = self.disk2PromPath(device)

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

	for (drive, (label, liloType)) in todo.liloImages.items ():
	    if (drive == rootDev) and label:
		main = label
	    elif label:
		i = len(drive) - 1
		while i > 0 and drive[i] in string.digits:
		    i = i - 1
		prompath = drive[:i+1]
		if prompath == boothd:
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
	    kernelList.append((main, self.todo.hdList['kernel-smp'], "smp"))
	    label = main + "-up"

	kernelList.append((label, self.todo.hdList['kernel'], ""))

	for (label, kernel, tag) in kernelList:
	    kernelTag = "-%s-%s%s" % (kernel['version'], kernel['release'], tag)
	    initrd = todo.makeInitrd (kernelTag)
	    if rootDev == bootpart:
		kernelFile = "/boot/vmlinuz" + kernelTag
		initrdFile = initrd
	    else:
		kernelFile = "/vmlinuz" + kernelTag
		initrdFile = initrd[5:]

	    sl = LiloConfiguration()

	    sl.addEntry("label", label)
	    if os.access (todo.instPath + initrd, os.R_OK):
		sl.addEntry("initrd", initrdFile)

            if self.todo.liloAppend:
		sl.addEntry('append', '"%s"' % self.todo.liloAppend)

	    silo.addImage ("image", kernelFile, sl)

	for (label, device) in otherList:
	    sl = LiloConfiguration()
	    sl.addEntry("label", label)
	    silo.addImage ("other", device, sl)

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

	# pass 2, remove duplicate entries
	labels = []

	for (siloType, name, config) in silo.images:
	    if not name in labels:
		labels.append (name)
	    else: # duplicate entry, first entry wins
		silo.delImage (name)

	if self.todo.fstab.getBootDevice() != self.todo.fstab.getRootDevice()[0]:
	    silo.write(todo.instPath + "/boot/silo.conf")
	    try:
		os.remove(todo.instPath + "/etc/silo.conf")
	    except:
		pass
	    os.symlink("../boot/silo.conf", todo.instPath + "/etc/silo.conf")
	else:
	    silo.write(todo.instPath + "/etc/silo.conf")

	# XXX make me "not test mode"
	if todo.setupFilesystems:
	    if todo.serial:
		messages = "/tmp/silo.log"
	    else:
		messages = "/dev/tty3"
	    iutil.execWithRedirect('/sbin/silo',
				   args,
				   stdout = None,
                                   root = todo.instPath)
	    linuxAlias = ""
	    if self.linuxAlias and self.hasAliases():
		linuxAlias = bootDevice
	    if not self.bootDevice:
		bootDevice = ""
	    if not linuxAlias:
		linuxAlias = ""
	    _silo.setPromVars(linuxAlias,bootDevice)
