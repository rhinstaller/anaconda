# this owns partitioning, fstab generation, disk scanning, raid, etc
#
# a fstab is returned as a list of:
#	( mntpoint, device, fsystem, doFormat, size, (file) )
# tuples, sorted by mntpoint; note that device may be a raid device; the file 
# value is optional, and if it exists it names a file which will be created 
# on the (already existant!) device and loopback mounted
#
# the swap information is stored as ( device, format ) tuples
#
# raid lists are stored as ( mntpoint, raiddevice, fssystem, doFormat,
#			     raidlevel, [ device list ] )
#
# we always store as much of the fstab within the disk druid structure
# as we can -- Don't Duplicate Data.

import isys
import iutil
import os
import string
import raid
import struct
import _balkan
import sys
from translate import _
from log import log

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

class Fstab:

    # return 1 if we should stay on the same screen
    def checkFormatting(self, messageWindow):
	alreadyExists = {}

	(drives, raid) = self.partitionList()
        for (drive, part, type, start, cyl, size, preexisting) in drives:
	    if preexisting:
		alreadyExists[part] = 1

	badList = []
	for (part, drive, fsystem, format, size) in \
		self.formattablePartitions():
	    if not alreadyExists.has_key(part) and not format:
		badList.append((part, drive))

	if badList:
	    message = _("The following partitions are newly created, but "
		        "you have chosen not to format them. This will "
			"probably cause an error later in the install.\n"
			"\n")

	    for (part, drive) in badList:
		message = message + ("\t%-20s /dev/%s\n" % (part, drive))

            message = message + _("\n\nPress OK to continue, or Cancel to go back and select these partitions to be formatted (RECOMMENDED).")
	    rc = messageWindow(_("Warning"), message, type = "okcancel").getrc()

	    return rc
	
	return 0

    def attemptPartitioning(self, partitions, prefstab, clearParts):
        
	attempt = []
	swapCount = 0

#
# this is probably not required
# 
#	fstab = []
#	for (mntpoint, dev, fstype, reformat, size) in self.extraFilesystems:
#            fstab.append ((dev, mntpoint))

	fstab = []
        if prefstab != None:
            for (mntpoint, (dev, fstype, reformat)) in prefstab:
                fstab.append ((dev, mntpoint))

        # if doing a harddrive install mark source partition so it isnt erased
        if self.protectList:
            for i in self.protectList:
                fstab.append ((i, "DONT ERASE "+i))

	ddruid = self.createDruid(fstab = fstab, ignoreBadDrives = 1)

        # skip out here if not partitions defined, just onpart def's
        # cant do this now, have to let attempt fixup partition types
        #if partitions == None:
        #    return ddruid
       
	for (mntpoint, sizespec, locspec, typespec, fsopts) in partitions:
            (device, part, primOnly) = locspec
            (size, maxsize, grow) = sizespec
            (type, active) = typespec

            if (part == 0):
                part = -1

            if (type == 0):
                type = 0x83
                
	    if (mntpoint == "swap"):
		mntpoint = "Swap%04d-auto" % swapCount
		swapCount = swapCount + 1
		type = 0x82
	    elif (mntpoint[0:5] == "raid."):
		type = 0xfd

	    attempt.append((mntpoint, size, maxsize, type, grow, -1, device, part, primOnly, active))

        success = 0

	try:
	    rc = ddruid.attempt (attempt, "Junk Argument", clearParts)
            success = 1

        except self.fserror, msg:
            log("Autopartitioning failed because following errors:")
            for i in string.split(msg, '\n'):
                if len(i) > 0:
                    log (i)
	    pass

        if success == 1:
            # configure kickstart requested ext2 filesystem options
            for (mntpoint, sizespce, locspec, typespec, fsopts) in partitions:
                if fsopts != None:
                    self.setfsOptions (mntpoint, fsopts)

            # sanity check
            for (partition, mount, fsystem, size) in ddruid.getFstab():
                if mount == '/' and fsystem != 'ext2':
                    raise ValueError, "--onpart specified for mount point / on non-ext2 partition"

                # if mount point other than '/' is on non-ext2, better have
                # specified --noformat 
                for (mntpoint, (dev, fstype, reformat)) in prefstab:
                    if mntpoint == mount and reformat != 0 and fsystem != fstype:
                        raise ValueError, "--onpart specified for mount point %s on non-ext2 partition without --noformat option" % mntpoint

            return ddruid
        else:
            return None

    # returns max cylinder, starting counting from 1
    # reads DIRECTLY from drive partition table, not the desired
    # partition table we construct at the start of the install
    # in disk druid/autopartitioning!!!
    def getBootPartitionMaxCylFromDrive(self):

        # avoid if partitionless install
        if rootOnLoop(self):
            return 0
        
	bootpart = self.getBootDevice()
	boothd = self.getMbrDevice()

        # for now just assume this will work on RAID systems, not simple to
        # test at all
	if bootpart[0:2] == "md":
            return 0

        maxcyl = 0
        
        try:
            bootgeom = isys.getGeometry(boothd)
        except:
            bootgeom = None

        log("Boot drive is %s, geometry is %s" % (boothd, bootgeom))
        if bootgeom != None:
            isys.makeDevInode(boothd, '/tmp/' + boothd)
                    
            try:
                table = _balkan.readTable ('/tmp/' + boothd)
            except SystemError:
                pass
            else:
                for i in range (len (table)):
                    part = "%s%d" % (boothd, i+1)
                    if part == bootpart:
                        (type, sector, size) = table[i]
                        maxcyl = (sector+size) / string.atoi(bootgeom[2])
                        maxcyl = maxcyl /  string.atoi(bootgeom[1])

                        log("Boot part %s ends on cyl %s" % (bootpart, maxcyl))
                                    
            os.remove ('/tmp/' + boothd)

            return maxcyl

    # returns max cylinder, starting counting from 1
    # this is read from the ddruid object of the partitioning scheme we
    # are currently building up from disk druid/autopartitioning
    # NOT guaranteed to be same as getBootPartitionMaxCylFromDrive() result
    def getBootPartitionMaxCylFromDesired(self):
	bootpart = self.getBootDevice()
	boothd = self.getMbrDevice()

        # for now just assume this will work on RAID systems, not simple to
        # test at all
	if bootpart[0:2] == "md":
            return 0


        (drives, raid) = self.partitionList()

        for (dev, devName, type, start, size, maxcyl, preexist) in drives:
            # only test if putting on ext2 partition, skip for
            # dos since its a partitionless install
            if type == 1:
                continue
            if dev == bootpart:
                log ("maxcyl of %s is %s" % (dev, maxcyl))
                return maxcyl

        return 0

    def getMbrDevice(self):
	return self.driveList()[0]

    def getBootDevice(self):
	bootDevice = None
	rootDevice = None
	for (mntpoint, partition, fsystem, doFormat, size) in self.mountList():
	    if mntpoint == '/':
		rootDevice = partition
	    elif mntpoint == '/boot':
		bootDevice = partition

	if not bootDevice:
	    bootDevice = rootDevice

	return bootDevice

    def getRootDevice(self):
	for (mntpoint, partition, fsystem, doFormat, size) in self.mountList():
	    if mntpoint == '/':
		return (partition, fsystem)

    def rootOnLoop(self):
	for (mntpoint, partition, fsystem, doFormat, size) in self.mountList():
	    if mntpoint == '/':
		if fsystem == "vfat": 
		    return 1
		else:
		    return 0

	raise ValueError, "no root device has been set"

    def getLoopbackSize(self):
	return (self.loopbackSize, self.loopbackSwapSize)

    def setLoopbackSwapSize(self, swapSize):
	self.loopbackSwapSize = swapSize

    def setLoopbackSize(self, size, swapSize):
	self.loopbackSize = size
	self.loopbackSwapSize = swapSize

    def setDruid(self, druid, raid):
	self.ddruid = druid
	self.fsCache = {}
	for (mntPoint, raidDev, level, devices) in raid:
	    if mntPoint == "swap":
		fsystem = "swap"
	    else:
		fsystem = "ext2"
	    self.addNewRaidDevice(mntPoint, raidDev, fsystem, level, devices)
	    
    def rescanPartitions(self, clearFstabCache = 0):
	if self.ddruid:
	    self.closeDrives(clearFstabCache)

        fstab = []
	for (mntpoint, dev, fstype, reformat, size) in self.cachedFstab:
            fstab.append ((dev, mntpoint))

	self.ddruid = self.fsedit(0, self.driveList(), fstab, self.zeroMbr,
				  self.readOnly, self.upgrade,
                                  self.expert, self.edd)
	del self.cachedFstab

    def closeDrives(self, clearFstabCache = 0):
	# we expect a rescanPartitions() after this!!!
        if clearFstabCache:
            self.cachedFstab = []
        else:
	    self.cachedFstab = self.mountList(skipExtra = 1)
	self.ddruid = None

    def setReadonly(self, readOnly):
	self.readOnly = readOnly
        self.ddruid.setReadOnly(readOnly)

    def savePartitions(self):
        import sys
	try:
	    self.ddruid.save()
	except SystemError:
	    # We can't reread the partition table for some reason. Display
	    # an error message and reboot
	    self.messageWindow(_("Error"), 
                    _("The kernel is unable to read your new partitioning "
                    "information, probably because you modified extended "
                    "partitions. While this is not critical, you must "
                    "reboot your machine before proceeding. Insert the "
                    "Red Hat boot disk now and press \"Ok\" to reboot "
                    "your system.\n"))
	    sys.exit(0)

    def runDruid(self):
	rc = self.ddruid.edit()
	return rc

    def updateFsCache(self):
	realFs = {}
	for (partition, mount, fsystem, size) in self.ddruid.getFstab():
	    realFs[(partition, mount)] = 1
	for ((partition, mount)) in self.fsCache.keys():
	    if not realFs.has_key((partition, mount)):
		del self.fsCache[(partition, mount)]

    def setFormatFilesystem(self, device, format):
	for (mntpoint, partition, fsystem, doFormat, size) in self.mountList():
	    if partition == device:
		self.fsCache[(partition, mntpoint)] = (format,)
		return

	raise TypeError, "unknown partition to format %s" % (device,)

    # sorted largest to smallest
    def spaceSort(self, a, b):
    	(m1, s1) = a
        (m2, s2) = b
	
        if (s1 > s2):
            return -1
        elif s1 < s2:
            return 1

        return 0


    def filesystemSpace(self, topMount):
	space = []
	for (mntpoint, partition, fsystem, doFormat, size) in self.mountList():
	    if fsystem == 'ext2':
		space.append((mntpoint, isys.fsSpaceAvailable(topMount + '/' + mntpoint)))
	    elif mntpoint == '/' and fsystem == 'vfat':
		space.append((mntpoint, isys.fsSpaceAvailable(topMount + '/' + mntpoint)))

	space.sort(self.spaceSort)
	return space

    def formatAllFilesystems(self):
	for (partition, mount, fsystem, size) in self.ddruid.getFstab():
	    if mount[0] == '/' and fsystem == "ext2":
		self.fsCache[(partition, mount)] = (1,)
        (devices, raid) = self.ddruid.partitionList()
	for (mount, partition, fsystem, level, i, j, deviceList) in \
	    self.raidList()[1]:
	    if mount[0] == '/' and fsystem == "ext2":
		self.fsCache[(partition, mount)] = (1,)

#   FSOptions is a list of options to be passed when creating fs for mount
    def setfsOptions (self, mount, fsopts):
        self.fsOptions[mount] = fsopts;
        return

    def getfsOptions (self, mount):
        if self.fsOptions.has_key(mount):
            return self.fsOptions[mount]
        else:
            return None

    def clearfsOptions (self):
        self.fsOptions = {}
        return

    def partitionList(self):
	return self.ddruid.partitionList()

    def writeCleanupPath(self, f):
	if self.rootOnLoop():
	    # swap gets turned off by init, then turn off loop1, and filesystem
	    # unmounts will just happen
	    f.write("umount /mnt/sysimage/proc\n")
	    f.write("umount /mnt/sysimage\n")
	    isys.makeDevInode("loop1", "/tmp/loop1")
	    f.write("lounsetup /tmp/loop1\n")

    def getprotectedList(self):
        if self.protectList:
            return self.protectList
        else:
            return []

    def formattablePartitions(self):
	l = []
	for item in self.mountList():
	    (mount, dev, fstype, format, size) = item

            # dont format protected partitions
            for n in self.getprotectedList():
                if n == dev:
                    continue
                
            if fstype == "ext2" or (fstype == "vfat" and mount == "/boot/efi"):
		l.append(item)

	return l

    def driveList(self):
	drives = isys.hardDriveDict().keys()
	drives.sort (isys.compareDrives)
	return drives

    def drivesByName(self):
	return isys.hardDriveDict()

    def swapList(self):
	fstab = []
	for (partition, mount, fsystem, size) in self.ddruid.getFstab():
	    if fsystem != "swap": continue

	    fstab.append((partition, 1))

	# Add raid mounts to mount list
        (devices, raid) = self.raidList()
	for (mntpoint, device, fsType, raidType, start, size, makeup) in raid:
	    if fsType != "swap": continue
	    fstab.append((device, 1))

	for n in self.extraFilesystems:
	    (mntpoint, device, fsType, doFormat, size) = n
	    if fsType != "swap": continue
	    fstab.append((device, 1))

	return fstab

    def turnOffSwap(self):
	if not self.swapOn: return
	self.swapOn = 0

	if self.rootOnLoop() and self.loopbackSwapSize:
	    isys.swapoff("/mnt/loophost/rh-swap.img")

	for (device, doFormat) in self.swapList():
	    file = '/tmp/swap/' + device
	    isys.swapoff(file)

    def turnOnSwap(self, formatSwap = 1):
	# we could be smarter about this
	if self.swapOn: return
	self.swapOn = 1

	if self.rootOnLoop() and self.loopbackSwapSize:
	    (rootDev, rootFs) = self.getRootDevice()

	    isys.mount(rootDev, "/mnt/loophost", fstype = "vfat")

	    # loopbackSwapSize = -1 turns on existing swap space rather
	    # then creating a new one
	    if self.loopbackSwapSize > 0:
		isys.ddfile("/mnt/loophost/rh-swap.img", 
			    self.loopbackSwapSize)

	    iutil.execWithRedirect ("/usr/sbin/mkswap",
			     [ "mkswap", '-v1', 
			       '/mnt/loophost/rh-swap.img' ],
			     stdout = None, stderr = None)

	    isys.swapon("/mnt/loophost/rh-swap.img")

	    return


	iutil.mkdirChain('/tmp/swap')

	for (device, doFormat) in self.swapList():
	    file = '/tmp/swap/' + device
	    isys.makeDevInode(device, file)

	    if formatSwap:
		w = self.waitWindow(_("Formatting"),
			      _("Formatting swap space on /dev/%s...") % 
				    (device,))

		rc = iutil.execWithRedirect ("/usr/sbin/mkswap",
					 [ "mkswap", '-v1', file ],
					 stdout = None, stderr = None,
					 searchPath = 1)
		w.pop()

		if rc:
		    self.messageWindow(_("Error"), _("Error creating swap on device ") + device)
		else:
		    isys.swapon (file)
	    else:
		try:
		    isys.swapon (file)
		except:
		    # XXX should we complain?
		    pass

    def addNewRaidDevice(self, mountPoint, raidDevice, fileSystem, 
		      raidLevel, deviceList):
	self.supplementalRaid.append((mountPoint, raidDevice, fileSystem,
				  raidLevel, deviceList))

    def clearExistingRaid(self):
	self.existingRaid = []

    def startExistingRaid(self):
	for (raidDevice, mntPoint, fileSystem, deviceList) in self.existingRaid:
	    isys.raidstart(raidDevice, deviceList[0])

    def stopExistingRaid(self):
	for (raidDevice, mntPoint, fileSystem, deviceList) in self.existingRaid:
	    isys.raidstop(raidDevice)

    def addExistingRaidDevice(self, raidDevice, mntPoint, fsystem, deviceList):
        self.existingRaid.append(raidDevice, mntPoint, fsystem, deviceList)

    def existingRaidList(self):
	return self.existingRaid
	
    def raidList(self):
        (devices, raid) = self.ddruid.partitionList()

	if raid == None:
	    raid = []

	for (mountPoint, raidDevice, fileSystem, raidLevel, deviceList) in \
		self.supplementalRaid:
	    raid.append(mountPoint, raidDevice, fileSystem, raidLevel,
			0, 0, deviceList)

	return (devices, raid)

    def createRaidTab(self, file, devPrefix, createDevices = 0):
	(devices, raid) = self.raidList()

	if not raid: return

	deviceDict = {}
	for (device, name, type, start, size, maxcyl, preexist) in devices:
	    deviceDict[name] = device

	rt = open(file, "w")
	for (mntpoint, device, fstype, raidType, start, size, makeup) in raid:

	    if createDevices:
		isys.makeDevInode(device, devPrefix + '/' + device)

	    rt.write("raiddev		    %s/%s\n" % (devPrefix, device,))
	    rt.write("raid-level		    %d\n" % (raidType,))
	    rt.write("nr-raid-disks		    %d\n" % (len(makeup),))
	    rt.write("chunk-size		    64k\n")
	    rt.write("persistent-superblock	    1\n");
	    rt.write("#nr-spare-disks	    0\n")
	    i = 0
	    for subDevName in makeup:
                if createDevices:
                    isys.makeDevInode(deviceDict[subDevName], '%s/%s' % 
                                      (devPrefix, deviceDict[subDevName]))
		rt.write("    device	    %s/%s\n" % 
		    (devPrefix, deviceDict[subDevName],))
		rt.write("    raid-disk     %d\n" % (i,))
		i = i + 1

	rt.write("\n")
	rt.close()

    def umountFilesystems(self, instPath, ignoreErrors = 0):
	if (not self.setupFilesystems): return 

	isys.umount(instPath + '/proc', removeDir = 0)

        try:
            isys.umount(instPath + '/proc/bus/usb', removeDir = 0)
            log("Umount USB OK")
        except:
            log("Umount USB Fail")
            pass

	mounts = self.mountList()
	mounts.reverse()
	for (n, device, fsystem, doFormat, size) in mounts:
            if fsystem != "swap":
		try:
		    mntPoint = instPath + n
                    isys.umount(mntPoint, removeDir = 0)
		except SystemError, (errno, msg):
		    if not ignoreErrors:
			self.messageWindow(_("Error"), 
			    _("Error unmounting %s: %s") % (device, msg))

	if self.rootOnLoop():
	    isys.makeDevInode("loop1", '/tmp/' + "loop1")
	    isys.unlosetup("/tmp/loop1")

	self.stopExistingRaid()

    def readLabels(self, skipList = []):
	labels = {}
        for drive in self.driveList():
            isys.makeDevInode(drive, '/tmp/' + drive)
            
            try:
                table = _balkan.readTable ('/tmp/' + drive)
            except SystemError:
		continue

	    for i in range (len (table)):
		dev = drive + str (i + 1)
		try:
		    skipList.index(dev)
		except ValueError, msg:
		    (type, sector, size) = table[i]

		    # we check the label on all filesystems because mount
		    # does to!
		    label = isys.readExt2Label(dev)
		    if label:
			labels[dev] = label
		    #print "label for", dev
	return labels

    def makeFilesystems(self):
	# let's make the RAID devices first -- the fstab will then proceed
	# naturally
	(devices, raid) = self.raidList()

	if self.serial:
	    messageFile = "/tmp/mke2fs.log"
	else:
	    messageFile = "/dev/tty5"

	if raid:
	    self.createRaidTab("/tmp/raidtab", "/tmp", createDevices = 1)

	    w = self.waitWindow(_("Creating"), _("Creating RAID devices..."))

	    for (mntpoint, device, fsType, raidType, start, size, makeup) in raid:
                iutil.execWithRedirect ("/usr/sbin/mkraid", 
			[ 'mkraid', '--really-force', '--configfile', 
			  '/tmp/raidtab', '/tmp/' + device ],
			stderr = messageFile, stdout = messageFile)

	    w.pop()
        
	    # XXX remove extraneous inodes here
#	    print "created raid"

	self.startExistingRaid()

        if not self.setupFilesystems: return

        arch = iutil.getArch ()

        if arch == "alpha":
            bootPart = self.getBootDevice()

	labelSkipList = []
	labels = {}
	for (mntpoint, device, fsystem, doFormat, size) in self.mountList():
	    if doFormat: labelSkipList.append(device)
	for label in self.readLabels(labelSkipList).values():
	    labels[label] = 1

	for (mntpoint, device, fsystem, doFormat, size) in self.mountList():
	    if not doFormat:
                continue

	    # Handle these before we handle the protect list, as the vfat
	    # partition itself could be in the protect list. 
	    if fsystem == "vfat" and mntpoint == "/":
		# do a magical loopback mount -- whee!
		isys.mount(device, "/mnt/loophost", fstype = "vfat")
		
		isys.makeDevInode("loop1", '/tmp/' + "loop1")
		isys.ddfile("/mnt/loophost/redhat.img", self.loopbackSize,
		    (self.progressWindow, _("Loopback"),
		      _("Creating loopback filesystem on device /dev/%s...")
			    % device))

		isys.losetup("/tmp/loop1", "/mnt/loophost/redhat.img")

		if self.serial:
		    messageFile = "/tmp/mke2fs.log"
		else:
		    messageFile = "/dev/tty5"

		ext2FormatFilesystem([ "/usr/sbin/mke2fs", "/tmp/loop1" ], 
				     messageFile, self.progressWindow, 
				     mntpoint)

		# don't leave this setup, or we'll get confused later
		isys.unlosetup("/tmp/loop1")
		isys.umount("/mnt/loophost")

		# Next
		continue

            if self.protectList:
                founddev = 0
                for i in self.protectList:
                    if i == device:
                        founddev = 1
                        break;
                if founddev != 0:
		    # Next
                    continue

	    isys.makeDevInode(device, '/tmp/' + device)
            if fsystem == "ext2":
		label = createLabel(labels, mntpoint)
                args = [ "/usr/sbin/mke2fs", '/tmp/' + device, '-L', label ]
                # FORCE the partition that MILO has to read
                # to have 1024 block size.  It's the only
                # thing that our milo seems to read.
                if arch == "alpha" and device == bootPart:
                    args = args + ["-b", "1024", '-r', '0', '-O', 'none']
                # set up raid options for md devices.
                if device[:2] == 'md':
                    for (rmnt, rdevice, fsType, raidType, start, size, makeup) in raid:
                        if rdevice == device:
                            rtype = raidType
                            rdisks = len (makeup)
                    if rtype == 5:
                        rdisks = rdisks - 1
                        args = args + [ '-R', 'stride=%d' % (rdisks * 16) ]
                    elif rtype == 0:
                        args = args + [ '-R', 'stride=%d' % (rdisks * 16) ]
                        
                if self.badBlockCheck:
                    args.append ("-c")

                fsopts = self.getfsOptions(mntpoint)
                if fsopts:
                    args.extend(fsopts)

		ext2FormatFilesystem(args, messageFile, self.progressWindow, 
				     mntpoint)
	    elif fsystem == "vfat" and mntpoint == "/boot/efi":
                args = [ "mkdosfs", '/tmp/' + device ]

		w = self.waitWindow(_("Formatting"),
			      _("Formatting %s filesystem...") % (mntpoint,))

                iutil.execWithRedirect ("/usr/sbin/mkdosfs",
                                        args, stdout = messageFile, 
					stderr = messageFile, searchPath = 1)
		w.pop()
            else:
                pass

	self.stopExistingRaid()

    def hasDirtyFilesystems(self):
	if (not self.setupFilesystems): return 

	if self.rootOnLoop():
	    (rootDev, rootFs) = self.getRootDevice()
	    mountLoopbackRoot(rootDev, skipMount = 1)
	    dirty = isys.ext2IsDirty("loop1")
	    unmountLoopbackRoot(skipMount = 1)
	    if dirty: return 1

	for (mntpoint, device, fsystem, doFormat, size) in self.mountList():
	    if fsystem != "ext2": continue
	    if doFormat: continue

	    if isys.ext2IsDirty(device): return 1

	return 0

    def mountFilesystems(self, instPath):
	if (not self.setupFilesystems): return 

	self.startExistingRaid()

	for (mntpoint, device, fsystem, doFormat, size) in self.mountList():
            if fsystem == "swap":
		continue
	    elif fsystem == "vfat" and mntpoint == "/":
		isys.mount(device, "/mnt/loophost", fstype = "vfat")

		isys.makeDevInode("loop1", '/tmp/' + "loop1")

		isys.losetup("/tmp/loop1", "/mnt/loophost/redhat.img")
		isys.mount("loop1", instPath)
	    elif fsystem == "ext2" or fsystem == "ext3" or \
			(fsystem == "vfat" and mntpoint == "/boot/efi"):
		try:
		    iutil.mkdirChain(instPath + mntpoint)
		    isys.mount(device, instPath + mntpoint, fstype = fsystem)
		except SystemError, (errno, msg):
		    self.messageWindow(_("Error"), 
			_("Error mounting device %s as %s: %s\n\n"
                          "This most likely means this partition has "
                          "not been formatted.\n\nPress OK to reboot your "
                          "system.") % (device, mntpoint, msg))
		    raise SystemError, (errno, msg)

        try:
            os.mkdir (instPath + '/proc')
        except:
            pass
            
	isys.mount('/proc', instPath + '/proc', 'proc')

    def write(self, prefix):
	format = "%-23s %-23s %-7s %-15s %d %d\n";

	f = open (prefix + "/etc/fstab", "w")
	labels = self.readLabels()
	for (mntpoint, dev, fs, reformat, size) in self.mountList():
            if mntpoint[:10] == 'DONT ERASE':
                continue
	    if fs == "vfat" and mntpoint == "/":
		f.write("# LOOP1: /dev/%s %s /redhat.img\n" % (dev, fs))
		dev = "loop1"
		fs = "ext2"

	    if labels.has_key(dev):
		devName = "LABEL=" + labels[dev]
	    else:
		devName = '/dev/' + dev

	    iutil.mkdirChain(prefix + mntpoint)
	    if mntpoint == '/':
		f.write (format % ( devName, mntpoint, fs, 'defaults', 1, 1))
	    else:
                if fs == "ext2":
                    f.write (format % ( devName, mntpoint, fs, 'defaults', 1, 2))
                elif fs == "iso9660":
                    f.write (format % ( devName, mntpoint, fs, 'noauto,owner,ro', 0, 0))
		elif fs == "auto":
		    f.write (format % ( devName, mntpoint, fs, 'noauto,owner', 0, 0))
                else:
                    f.write (format % ( devName, mntpoint, fs, 'defaults', 0, 0))
	f.write (format % ("none", "/proc", 'proc', 'defaults', 0, 0))
	f.write (format % ("none", "/dev/pts", 'devpts', 'gid=5,mode=620', 
			    0, 0))

	if self.loopbackSwapSize:
	    f.write(format % ("/initrd/loopfs/rh-swap.img", 'swap',
				'swap', 'defaults', 0, 0))

	for (partition, doFormat) in self.swapList():
	    f.write (format % ("/dev/" + partition, 'swap', 'swap', 
			       'defaults', 0, 0))

	f.close ()
        # touch mtab
        open (prefix + "/etc/mtab", "w+")
        f.close ()

	self.createRaidTab(prefix + "/etc/raidtab", "/dev")

    def clearMounts(self):
	self.extraFilesystems = []

    def addMount(self, partition, mount, fsystem, doFormat = 0, size = 0):
	self.extraFilesystems.append(mount, partition, fsystem, doFormat,
				     size)
# XXX code from sparc merge
#          if fsystem == "swap":
#              ufs = 0
#              try:
#                  isys.makeDevInode(device, '/tmp/' + device)
#              except:
#                  pass
#              try:
#                  ufs = isys.checkUFS ('/tmp/' + device)
#              except:
#                  pass
#              if not ufs:
#                  location = "swap"
#                  reformat = 1
#          self.mounts[location] = (device, fsystem, reformat)


    def mountList(self, skipExtra = 0):
	def sortMounts(one, two):
	    mountOne = one[0]
	    mountTwo = two[0]
	    if (mountOne < mountTwo):
		return -1
	    elif (mountOne == mountTwo):
		return 0
	    return 1

	fstab = []
	for (partition, mount, fsystem, size) in self.ddruid.getFstab():

	    if fsystem == "swap":
                continue

	    if not self.fsCache.has_key((partition, mount)):
		if mount == '/home' and isValidExt2(partition):
		    self.fsCache[(partition, mount)] = (0, )
		else:
		    self.fsCache[(partition, mount)] = (1, )
	    (doFormat,) = self.fsCache[(partition, mount)]
	    fstab.append((mount, partition, fsystem, doFormat, size ))

	for (raidDevice, mntPoint, fsType, deviceList) in self.existingRaid:
	    if fsType == "swap": continue

	    fstab.append((mntPoint, raidDevice, fsType, 0, 0 ))

	# Add raid mounts to mount list
        (devices, raid) = self.raidList()
	for (mntpoint, device, fsType, raidType, start, size, makeup) in raid:
	    if fsType == "swap": continue

	    if not self.fsCache.has_key((device, mntpoint)):
		self.fsCache[(device, mntpoint)] = (1, )
	    (doFormat,) = self.fsCache[(device, mntpoint)]
	    fstab.append((mntpoint, device, fsType, doFormat, size ))

	if not skipExtra:
	    for n in self.extraFilesystems:
		(mntpoint, sevice, fsType, doFormat, size) = n

                # skip swap
		if fsType == "swap":
                    continue

                # skip duplicate entries (happens when ks used with --onpart)
                foundit = 0
                for p in fstab:
                    (mntpoint2, device2, fsType2, doFormat2, size2) = p
                    if mntpoint2 == mntpoint:
                        foundit = 1
                        break

                if not foundit:
                    fstab.append(n)

	fstab.sort(sortMounts)

	return fstab

    def setBadBlockCheck(self, state):
	self.badBlockCheck = state

    def getBadBlockCheck(self):
	return self.badBlockCheck

    def createDruid(self, fstab = [], ignoreBadDrives = 0):
        tlist = self.driveList()
        list = []
        if self.ignoreRemovable:
            for dev in tlist:
                if isys.driveIsRemovable(dev):
                    log("Not in expert mode, ignoring removable device %s", dev)
                    continue
                list.append(dev)
        else:
            list = tlist

	return self.fsedit(0, list, fstab, self.zeroMbr, 
			   self.readOnly,
                           (self.upgrade or ignoreBadDrives),
                           self.expert, self.edd)

    def getRunDruid(self):
	return self.shouldRunDruid

    def setRunDruid(self, state):
	self.shouldRunDruid = state

    def __init__(self, fsedit, fserror, setupFilesystems, serial, zeroMbr, 
		 readOnly, waitWindow, messageWindow, progressWindow,
		 ignoreRemovable, protected, expert, upgrade):

	self.fsedit = fsedit
        self.fserror = fserror
	self.fsCache = {}
        self.clearfsOptions()
        self.protectList = protected
	self.swapOn = 0
	self.supplementalRaid = []
	self.setupFilesystems = setupFilesystems
	self.serial = serial
	self.zeroMbr = zeroMbr
	self.readOnly = readOnly
	self.waitWindow = waitWindow
	self.messageWindow = messageWindow
	self.progressWindow = progressWindow
	self.badBlockCheck = 0
        self.ignoreRemovable = ignoreRemovable
        self.expert = expert
        self.upgrade = upgrade
        if iutil.getArch() == "i386":
            import edd
            self.edd = edd.detect()
        else:
            self.edd = 0

        #
        # extraFilesystems used for upgrades when /etc/fstab is read as
        # well as for adding fstab entries for removable media
        # Should NOT be used by kickstart any more
        #
	self.extraFilesystems = []
	self.existingRaid = []
	self.ddruid = self.createDruid()
	self.loopbackSize = 0
	self.loopbackSwapSize = 0
	# I intentionally don't initialize this, as all install paths should
	# initialize this automatically
	#self.shouldRunDruid = 0

class GuiFstab(Fstab):
    def accel (self, widget, area):
        self.accelgroup = self.GtkAccelGroup (_obj = widget.get_data ("accelgroup"))
        self.toplevel = widget.get_toplevel()
        self.toplevel.add_accel_group (self.accelgroup)

    def runDruid(self, callback):
        self.ddruid.setCallback (callback)
        bin = self.GtkFrame (None, _obj = self.ddruid.getWindow ())
        bin.connect ("draw", self.accel)
        bin.set_shadow_type (self.SHADOW_NONE)
        self.ddruid.edit ()
	return bin

    def runDruidFinished(self):
        if self.accelgroup:
            self.toplevel.remove_accel_group (self.accelgroup)        
	self.ddruid.next ()
	self.updateFsCache()
	# yikes! this needs to be smarter

    def __init__(self, setupFilesystems, serial, zeroMbr, readOnly, waitWindow,
		 messageWindow, progressWindow, ignoreRemovable,
                 protected, expert, upgrade, requireBlockDevices = 1):
	from gnomepyfsedit import fsedit
        from gnomepyfsedit import fserror
	from gtk import *

	try:
	    Fstab.__init__(self, fsedit, fserror, setupFilesystems, serial, 
			   zeroMbr, readOnly, waitWindow, messageWindow, 
			   progressWindow, ignoreRemovable, protected,
			   expert, upgrade)
	except SystemError:
	    if requireBlockDevices:
		print "no valid block devices found"
		sys.exit(0)
	    raise SystemError, text

	self.GtkFrame = GtkFrame
        self.GtkAccelGroup = GtkAccelGroup
	self.SHADOW_NONE = SHADOW_NONE
        self.accelgroup = None

class NewtFstab(Fstab):

    def __init__(self, setupFilesystems, serial, zeroMbr, readOnly,
                 waitWindow, messageWindow, progressWindow,
                 ignoreRemovable, protected, expert, upgrade,
		 requireBlockDevices = 1):
	from newtpyfsedit import fsedit
        from newtpyfsedit import fserror
        
	try:
	    Fstab.__init__(self, fsedit, fserror, setupFilesystems, serial, 
			   zeroMbr, readOnly, waitWindow, messageWindow, 
			   progressWindow, ignoreRemovable, protected, expert, 
			   upgrade)
	except SystemError, text:
	    if requireBlockDevices:
		print "no valid block devices found"
		sys.exit(0)
	    raise SystemError, text

def readFstab (path, fstab):
    loopIndex = {}

    f = open (path, "r")
    lines = f.readlines ()
    f.close

    fstab.clearExistingRaid()
    fstab.clearMounts()

    labelsByMount = {}
    labels = fstab.readLabels()
    for device in labels.keys():
	labelsByMount[labels[device]] = device

    drives = fstab.driveList()
    raidList = raid.scanForRaid(drives)
    raidByDev = {}
    for (mdDev, devList) in raidList:
	raidByDev[mdDev] = devList

    for line in lines:
	fields = string.split (line)

	if not fields: continue

	if fields[0] == "#" and len(fields)>4 and fields[1][0:4] == "LOOP":
	    device = string.lower(fields[1])
	    if device[len(device) - 1] == ":":
		device = device[0:len(device) - 1]
	    realDevice = fields[2]
	    if realDevice[0:5] == "/dev/":
		realDevice = realDevice[5:]
	    loopIndex[device] = (realDevice, fields[3])

	elif line[0] == "#":
	    # skip comments
	    continue

	# all valid fstab entries have 6 fields
	if len (fields) < 4 or len (fields) > 6: continue

	if fields[2] != "ext2" and fields[2] != "ext3" and fields[2] != "swap":
	    continue
	if string.find(fields[3], "noauto") != -1: continue

	if len(fields) >= 6 and fields[0][0:6] == "LABEL=":
	    label = fields[0][6:]
	    device = labelsByMount[label]

	    fsystem = fields[2]

	    fstab.addMount(device, fields[1], fsystem)
	elif fields[0][0:7] == "/dev/md":
	    fstab.addExistingRaidDevice(fields[0][5:], fields[1], 
				    fields[2], raidByDev[int(fields[0][7:])])
	elif (fields[0][0:7] == "/dev/hd" or 
              fields[0][0:7] == "/dev/sd" or
              fields[0][0:9] == "/dev/loop" or
              fields[0][0:8] == "/dev/rd/" or
              fields[0][0:9] == "/dev/ida/" or
              fields[0][0:11] == "/dev/cciss/"): 
	    # this skips swap files! todo has to put them back for upgrades

	    device = fields[0][5:]
	    fsystem = fields[2]
	    if loopIndex.has_key(device):
		(device, fsystem) = loopIndex[device]

	    fstab.addMount(device, fields[1], fsystem)

def createLabel(labels, newLabel):
    if len(newLabel) > 16:
	newLabel = newLabel[0:16]
    count = 0
    while labels.has_key(newLabel):
	count = count + 1
	s = "%s" % count
	if (len(newLabel) + len(s)) <= 16:
	    newLabel = newLabel + s
	else:
	    strip = len(newLabel) + len(s) - 16
	    newLabel = newLabel[0:len(newLabel) - strip] + s
    labels[newLabel] = 1

    return newLabel

def mountLoopbackRoot(device, skipMount = 0):
    isys.mount(device, '/mnt/loophost', fstype = "vfat")
    isys.makeDevInode("loop1", '/tmp/' + "loop1")
    isys.losetup("/tmp/loop1", "/mnt/loophost/redhat.img")

    if not skipMount:
	isys.mount("loop1", '/mnt/sysimage')

def unmountLoopbackRoot(skipMount = 0):
    if not skipMount:
	isys.umount('/mnt/sysimage')        
    isys.makeDevInode("loop1", '/tmp/' + "loop1")
    isys.unlosetup("/tmp/loop1")
    isys.umount('/mnt/loophost')        

def ext2FormatFilesystem(argList, messageFile, windowCreator, mntpoint):
    w = windowCreator(_("Formatting"),
		  _("Formatting %s filesystem...") % (mntpoint,), 100)

    fd = os.open(messageFile, os.O_RDWR)
    p = os.pipe()
    childpid = os.fork()
    if (not childpid):
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
				w.set((int(l[0]) * 100) / int(l[1]))
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

    w.pop()
