import string
import os
import isys
import iutil

class LiloConfigFile:
    def __repr__ (self, tab = 0):
	s = ""
	for n in self.order:
	    if (tab):
		s = s + '\t'
	    if n[0] == '#':
		s = s + n[1:]
	    else:
		s = s + n
		if self.items[n]:
		    s = s + "=" + self.items[n]
	    s = s + '\n'
	for image in self.images:
	    (type, name, cl) = image
	    s = s + "\n%s=%s\n" % (type, name)
	    s = s + cl.__repr__(1)
	return s

    def addEntry(self, item, val = None, replace = 1):
	if not self.items.has_key(item):
	    self.order.append(item)
	elif not replace:
	    return

	if (val):
	    self.items[item] = str(val)
	else:
	    self.items[item] = None

    def getEntry(self, item):
	return self.items[item]

    def getImage(self, name):
        for (type, label, config) in self.images:
            if label == name:
		return (type, config)
	raise IndexError, "unknown image %s" % (name,)

    def addImage (self, type, name, config):
	self.images.append((type, name, config))

    def delImage (self, name):
        for entry in self.images:
            type, label, config = entry
            if label == name:
                self.images.remove (entry)

    def listImages (self):
	l = []
        for (type, label, config) in self.images:
	    l.append(label)
	return l

    def write(self, file):
	f = open(file, "w")
	f.write(self.__repr__())
	f.close()
	os.chmod(file, 0644)

    def read (self, file):
	f = open(file, "r")
	image = None
	for l in f.readlines():
	    l = l[:-1]
	    orig = l
	    while (l and (l[0] == ' ' or l[0] == '\t')):
		l = l[1:]
	    if (not l or l[0] == '#'):
		self.order.append('#' + orig)
		continue
	    fields = string.split(l, '=', 1)
	    if (len(fields) == 2):
		if (fields[0] == "image"):
		    image = LiloConfigFile()
		    self.addImage(fields[0], fields[1], image)
		    args = None
		elif (fields[0] == "other"):
		    image = LiloConfigFile()
		    self.addImage(fields[0], fields[1], image)
		    args = None
                else:
		    args = (fields[0], fields[1])
	    else:
		args = (l,)

	    if (args and image):
		apply(image.addEntry, args)
	    elif args:
		apply(self.addEntry, args)
	    
	f.close()

    def __init__(self):
	self.order = []
	self.images = []		# more (type, name, LiloConfigFile) pair
	self.items = {}

class LiloConfiguration:

    def allowLiloLocationConfig(self, fstab):
	bootDevice = fstab.getBootDevice()
	if bootDevice[0:2] == "md":
	    self.setDevice(("raid", bootDevice))
	    return None

	return 1

    def setLiloImages(self, images):
	self.liloImages = images

    def getLiloImages(self, fstab):
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
	for dev in self.liloImages.keys():
	    oldImages[dev] = self.liloImages[dev]

	self.liloImages = {}
        foundDos = 0
	for (dev, devName, type, start, size) in drives:
	    # ext2 and raid partitions get listed if they're / -- we do
	    # not allow non-mounted partitions to be booted anymore as
	    # modules are so unlikely to work out as to be not worth
	    # worrying about
	    #
	    # there is a good chance we should configure them as chain
	    # loadable, but we don't

            # only list dos and ext2 partitions
            if type != 1 and type != 2:
                continue

	    if (mountsByDev.has_key(dev)):
		if mountsByDev[dev] == '/':
		    if oldImages.has_key(dev):
			self.liloImages[dev] = oldImages[dev]
		    else:
			self.liloImages[dev] = ("linux", 2)

            if type == 1:
		if foundDos: continue

		foundDos = 1
                isys.makeDevInode(dev, '/tmp/' + dev)
		bootable = isys.checkBoot('/tmp/' + dev)
		os.unlink('/tmp/' + dev)

		if bootable:
		    if oldImages.has_key(dev):
			self.liloImages[dev] = oldImages[dev]
		    else:
			self.liloImages[dev] = ("dos", type)

	# if there is no default image (self.default is None, or invalid)
	# set the default image to the liunx partition
	if self.default:
	    for (label, type) in self.liloImages.values():
		if label == self.default: break
	    if label != self.default:
		self.default = None

	if not self.default:
	    for (label, type) in self.liloImages.values():
		if type == 2:
		    self.default = label
		    break

	return (self.liloImages, self.default)

    def install (self, fstab):
	# If self.liloDevice is None, skipping lilo doesn't work
	if not self.liloDevice: return

	# If the root partition is on a loopback device, lilo won't work!
	if fstab.rootOnLoop():
	    return 

	if not self.liloImages:
	    self.setLiloImages(self.getLiloImages())

        # on upgrade read in the lilo config file
        if os.access (self.instPath + '/etc/lilo.conf', os.R_OK):
	    lilo.read (self.instPath + '/etc/lilo.conf')
	lilo = LiloConfigFile ()

	# Remove any invalid entries that are in the file; we probably
	# just removed those kernels. While we're here, build an index
	# to the already-configured (and valid) lilo images by the lilo
	# label, as we can normally only get them by filename which isn't
	# easily done.
	imagesByLabel = {}
	for image in lilo.listImages():
	    (type, sl) = lilo.getImage(image)
	    if type == "other": continue
	    if not os.access(self.instPath + image):
		lilo.delImage(image)
	    else:
		imagesByLabel[sl.getEntry('label')] = image

	bootpart = fstab.getBootDevice()
	boothd = fstab.getMbrDevice()

	if (self.liloDevice == "mbr"):
	    liloTarget = boothd
	elif (type(self.liloDevice) == type((1,)) and 
	      self.liloDevice[0] == "raid"):
	    liloTarget = self.liloDevice[1]
	else:
	    liloTarget = bootpart

	lilo.addEntry("boot", '/dev/' + liloTarget, replace = 0)
	lilo.addEntry("map", "/boot/map", replace = 0)
	lilo.addEntry("install", "/boot/boot.b", replace = 0)
	lilo.addEntry("prompt", replace = 0)
	lilo.addEntry("timeout", "50", replace = 0)
	if self.liloLinear:
	    lilo.addEntry("linear", replace = 0)

	smpInstalled = (self.hdList.has_key('kernel-smp') and 
                        self.hdList['kernel-smp'].selected)

	# This is a bit odd, but old versions of Red Hat could install
	# SMP kernels on UP systems, but (properly) configure the UP version.
	# We don't want to undo that, but we do want folks using this install
	# to be able to override the kernel to use during installs. This rule
	# seems to nail this.
	if (self.upgrade and not isys.smpAvailable()):
	    smpInstalled = 0

        rootDev = fstab.getRootDevice ()
        if rootDev:
	    # strip off the filesystem; we don't need it
            rootDev = rootDev[0]
        else:
            raise RuntimeError, "Installing lilo, but there is no root device"

        kernelList = []
        otherList = []

        main = self.default

        for (drive, (label, liloType)) in self.liloImages.items ():
            if (drive == rootDev) and label:
                main = label
            elif label:
                otherList.append (label, "/dev/" + drive)

        lilo.addEntry("default", main)        

	label = main
	if (smpInstalled):
	    kernelList.append((main, self.hdList['kernel-smp'], "smp"))
	    label = main + "-up"

	kernelList.append((label, self.hdList['kernel'], ""))

	for (label, kernel, tag) in kernelList:
	    if imagesByLabel.has_key(label):
		(type, sl) = lilo.getImage(imagesByLabel[label])
		lilo.delImage(imagesByLabel[label])
	    else:
		sl = LiloConfigFile()

	    kernelTag = "-%s-%s%s" % (kernel['version'], kernel['release'], tag)
	    kernelFile = "/boot/vmlinuz" + kernelTag

	    initrd = self.makeInitrd (kernelTag)

	    sl.addEntry("label", label)
	    if os.access (self.instPath + initrd, os.R_OK):
		sl.addEntry("initrd", initrd)

	    sl.addEntry("read-only")
	    sl.addEntry("root", '/dev/' + rootDev)

	    if self.liloAppend:
		sl.addEntry('append', '"%s"' % (self.liloAppend,))
		
	    lilo.addImage ("image", kernelFile, sl)

	for (label, device) in otherList:
	    try:
		(type, sl) = lilo.getImage(device)
		lilo.delImage(device)
	    except IndexError:
		sl = LiloConfigFile()

	    sl.addEntry("label", label)
	    lilo.addImage ("other", device, sl)

	lilo.write(self.instPath + "/etc/lilo.conf")

        # XXX make me "not test mode"
        if self.setupFilesystems:
            iutil.execWithRedirect(self.instPath + '/sbin/lilo' ,
                                   [ "lilo", "-r", self.instPath ],
                                   stdout = None)

    def setDevice(self, device):
	if (type(device) == type((1,))):
	    self.liloDevice = device
	elif device != "mbr" and device != "partition" and device:
	    raise ValueError, "device must be raid, mbr, partition, or None"
	self.liloDevice = device

    def setLinear(self, linear):
	self.liloLinear = linear

    def setAppend(self, append):
	self.liloAppend = append

    def setDefault(self, default):
	for (label, type) in self.liloImages.values():
	    if label == default:
		self.default = default
		return
	raise IndexError, "unknown lilo label %s" % (default,)

    def getLinear(self):
	return self.liloLinear

    def getDevice(self):
	return self.liloDevice

    def getAppend(self):
	return self.liloAppend

    def __init__(self):
	self.liloImages = {}
	self.liloDevice = 'mbr'
	self.liloLinear = 1
	self.liloAppend = None
	self.default = None


if __name__ == "__main__":
    config = LiloConfigFile ()
    config.read ('/etc/lilo.conf')
    print config
    print "image list", config.listImages()
    config.delImage ('/boot/vmlinuz-2.2.5-15')
    print '----------------------------------'
    config = LiloConfigFile ()
    config.read ('/etc/lilo.conf')
    print config
    print '----------------------------------'    
    print config.getImage('/boot/vmlinuz-2.2.5-15')
    

