import string
import os
from lilo import LiloConfiguration
import _silo
import iutil

class SiloInstall:
    def __init__ (self, todo):
	self.todo = todo
	self.linuxAlias = None
	self.bootBevice = None

    def getSiloImages(self):
	todo = self.todo
	if not todo.ddruid:
	    raise RuntimeError, "No disk druid object"

	(drives, raid) = todo.ddruid.partitionList()

	# rearrange the fstab so it's indexed by device
	mountsByDev = {}
	for loc in todo.mounts.keys():
	    (device, fsystem, reformat) = todo.mounts[loc]
	    mountsByDev[device] = loc

	oldImages = {}
	for dev in todo.liloImages.keys():
	    oldImages[dev] = todo.liloImages[dev]

	todo.liloImages = {}
	foundUfs = 0
	for (dev, devName, type) in drives:
	    # ext2 partitions get listed if 
	    #	    1) they're /
	    #	    2) they're not mounted
	    #	       and contain /boot of
	    #	       some Linux installation

	    # only list ext2 and ufs partitions
	    if type != 2 and type != 6:
		continue

	    if (mountsByDev.has_key(dev)):
		if mountsByDev[dev] == '/':
		    todo.liloImages[dev] = ("linux", 2)
	    else:
		if not oldImages.has_key(dev):
		    todo.liloImages[dev] = ("", type)
		else:
		    todo.liloImages[dev] = oldImages[dev]
	    # XXX
	    if type == 6:
		if foundUfs: continue
		foundUfs = 1
		todo.liloImages[dev] = ("solaris", type)

	return todo.liloImages

    def getSiloOptions(self):
	if self.todo.mounts.has_key ('/boot'):
	    bootpart = self.todo.mounts['/boot'][0]
	else:
	    bootpart = self.todo.mounts['/'][0]
	i = len (bootpart) - 1
	while i > 0 and bootpart[i] in string.digits:
	    i = i - 1
	boothd = bootpart[:i+1]

	return (bootpart, boothd)

    def hasUsableFloppy(self):
	try:
	    f = open("/proc/devices", "r")
	except:
	    return 0
	lines = f.readlines ()
	f.close ()
	for line in lines:
	    if string.strip (line) == "2 fd":
		return 1
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

	(bootpart, boothd) = self.getSiloOptions()
	smpInstalled = (self.todo.hdList.has_key('kernel-smp') and 
			self.todo.hdList['kernel-smp'].selected)

	if self.todo.mounts.has_key ('/'):
	    (dev, fstype, format) = self.todo.mounts['/']
	    rootDev = dev
	else:
	    raise RuntimeError, "Installing silo, but there is no root device"

	args = [ "silo", "-r", todo.instPath ]

	if (todo.liloDevice != "mbr"):
	    args.append("-t")

	i = len (bootpart) - 1
	while i > 0 and bootpart[i] in string.digits:
	    i = i - 1
	silo.addEntry("partition", bootpart[i+1:])
	silo.addEntry("timeout", "50")
	silo.addEntry("root", rootDev)
	silo.addEntry("read-only")

	kernelList = []
	otherList = []

	main = "linux"

	for (drive, (label, liloType)) in todo.liloImages.items ():
	    if (drive == rootDev) and label:
		main = label
	    elif label:
		# FIXME
		otherList.append (label, "/dev/" + drive)

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

	silo.write(todo.instPath + "/etc/silo.conf")

	# XXX make me "not test mode"
	if todo.setupFilesystems:
	    iutil.execWithRedirect('/sbin/silo',
				   args,
				   stdout = None,
                                   root = todo.instPath)
