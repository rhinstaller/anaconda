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
from translate import _

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
    def attemptPartitioning(self, partitions, prefstab, clearParts):
	attempt = []
	swapCount = 0

#	fstab = []
#	for (mntpoint, dev, fstype, reformat, size) in self.extraFilesystems:
#            fstab.append ((dev, mntpoint))

	fstab = []
        if prefstab != None:
            for (mntpoint, (dev, fstype, reformat)) in prefstab:
                fstab.append ((dev, mntpoint))

	ddruid = self.createDruid(fstab = fstab, ignoreBadDrives = 1)

        # skip out here if not partitions defined, just onpart def's
        if partitions == None:
            return ddruid

	for (mntpoint, sizespec, locspec, typespec, fsopts) in partitions:
            device = locspec
            (size, maxsize, grow) = sizespec

	    type = 0x83
	    if (mntpoint == "swap"):
		mntpoint = "Swap%04d-auto" % swapCount
		swapCount = swapCount + 1
		type = 0x82
	    elif (mntpoint[0:5] == "raid."):
		type = 0xfd

	    attempt.append((mntpoint, size, maxsize, type, grow, -1, device))

        success = 0

	try:
	    ddruid.attempt (attempt, "Junk Argument", clearParts)
            success = 1
	except:
	    pass

        if success == 1:
            # configure kickstart requested ext2 filesystem options
            for (mntpoint, sizespce, locspec, typespec, fsopts) in partitions:
                if fsopts != None:
                    self.setfsOptions (mntpoint, fsopts)
            
            return ddruid
        else:
            return None

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
        if not self.setupFilesystems: return 0
	for (mntpoint, partition, fsystem, doFormat, size) in self.mountList():
	    if mntpoint == '/':
		if fsystem == "vfat": 
		    return 1
		else:
		    return 0

	raise ValueError, "no root device has been set"

    def getLoopbackSize(self):
	return (self.loopbackSize, self.loopbackSwapSize)

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
				  self.readOnly)
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
	self.ddruid.save()

    def runDruid(self):
	rc = self.ddruid.edit()
	# yikes! this needs to be smarter
	self.beenSaved = 0
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
	for (device, doFormat) in self.swapList():
	    file = '/tmp/swap/' + device
	    isys.swapoff(file)

    def turnOnSwap(self, formatSwap = 1):
	# we could be smarter about this
	if self.swapOn or self.rootOnLoop(): return
	self.swapOn = 1

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
	for (device, name, type, start, size) in devices:
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

	isys.umount(instPath + '/proc')

	mounts = self.mountList()
	mounts.reverse()
	for (n, device, fsystem, doFormat, size) in mounts:
            if fsystem != "swap":
		try:
		    mntPoint = instPath + n
                    isys.umount(mntPoint)
		except SystemError, (errno, msg):
		    if not ignoreErrors:
			self.messageWindow(_("Error"), 
			    _("Error unmounting %s: %s") % (device, msg))

	if self.rootOnLoop():
	    isys.makeDevInode("loop0", '/tmp/' + "loop0")
	    isys.unlosetup("/tmp/loop0")

	for (raidDevice, mntPoint, fileSystem, deviceList) in self.existingRaid:
	    isys.raidstop(raidDevice)

    def readLabels(self, skipList = []):
	labels = {}
        for drive in self.driveList():
            isys.makeDevInode(drive, '/tmp/' + drive)
            
            try:
                table = _balkan.readTable ('/tmp/' + drive)
            except SystemError:
		next

	    for i in range (len (table)):
		dev = drive + str (i + 1)
		try:
		    skipList.index(dev)
		except ValueError, msg:
		    (type, sector, size) = table[i]
		    # 2 is ext2 in balkan speek
		    if type == 2:
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

	for (raidDevice, mntPoint, fileSystem, deviceList) in self.existingRaid:
	    isys.raidstart(raidDevice, deviceList[0])

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
	    if not doFormat: continue
	    isys.makeDevInode(device, '/tmp/' + device)
            if fsystem == "ext2":
		label = createLabel(labels, mntpoint)
                args = [ "mke2fs", '/tmp/' + device, '-L', label ]
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

		w = self.waitWindow(_("Formatting"),
			      _("Formatting %s filesystem...") % (mntpoint,))

                iutil.execWithRedirect ("/usr/sbin/mke2fs",
                                        args, stdout = messageFile, 
					stderr = messageFile, searchPath = 1)
		w.pop()
            else:
                pass

            os.remove('/tmp/' + device)

    def mountFilesystems(self, instPath):
	if (not self.setupFilesystems): return 

	for (mntpoint, device, fsystem, doFormat, size) in self.mountList():
            if fsystem == "swap":
		continue
	    elif fsystem == "vfat" and mntpoint == "/":
		# do a magical loopback mount -- whee!
		w = self.waitWindow(_("Loopback"),
			      _("Creating loopback filesystem on device /dev/%s...") % (device,))

		iutil.mkdirChain("/mnt/loophost")
		isys.makeDevInode(device, '/tmp/' + device)
		isys.mount('/tmp/' + device, "/mnt/loophost", fstype = "vfat")
		os.remove( '/tmp/' + device);
		
		isys.makeDevInode("loop0", '/tmp/' + "loop0")
		isys.ddfile("/mnt/loophost/redhat.img", self.loopbackSize)
		isys.losetup("/tmp/loop0", "/mnt/loophost/redhat.img")

		if self.serial:
		    messageFile = "/tmp/mke2fs.log"
		else:
		    messageFile = "/dev/tty5"

                iutil.execWithRedirect ("/usr/sbin/mke2fs", 
					[ "mke2fs", "/tmp/loop0" ],
                                        stdout = messageFile, 
					stderr = messageFile, searchPath = 1)

		isys.mount('/tmp/loop0', instPath)
		os.remove('/tmp/loop0')

		if self.loopbackSwapSize:
		    isys.ddfile("/mnt/loophost/rh-swap.img", 
				self.loopbackSwapSize)
		    iutil.execWithRedirect ("/usr/sbin/mkswap",
				     [ "mkswap", '-v1', 
				       '/mnt/loophost/rh-swap.img' ],
				     stdout = None, stderr = None)
		    isys.swapon("/mnt/loophost/rh-swap.img")

		w.pop()
	    elif fsystem == "ext2":
		try:
		    iutil.mkdirChain(instPath + mntpoint)
		    isys.makeDevInode(device, '/tmp/' + device)
		    isys.mount('/tmp/' + device, 
				instPath + mntpoint)
		    os.remove( '/tmp/' + device);
		except SystemError, (errno, msg):
		    self.messageWindow(_("Error"), 
			_("Error mounting %s: %s") % (device, msg))
		    raise SystemError, (errno, msg)

        try:
            os.mkdir (instPath + '/proc')
        except:
            pass
            
	isys.mount('/proc', instPath + '/proc', 'proc')

    def write(self, prefix, fdDevice = "/dev/fd0"):
	format = "%-23s %-23s %-7s %-15s %d %d\n";

	f = open (prefix + "/etc/fstab", "w")
	labels = self.readLabels()
	for (mntpoint, dev, fs, reformat, size) in self.mountList():
	    if fs == "vfat" and mntpoint == "/":
		f.write("# LOOP0: /dev/%s %s /redhat.img\n" % (dev, fs))
		dev = "loop0"
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
		elif fs == "auto" and (dev == "zip" or dev == "jaz"):
		    f.write (format % ( devName, mntpoint, fs, 'noauto,owner', 0, 0))
                else:
                    f.write (format % ( devName, mntpoint, fs, 'defaults', 0, 0))
	f.write (format % (fdDevice, "/mnt/floppy", 'auto', 'noauto,owner', 0, 0))
	f.write (format % ("none", "/proc", 'proc', 'defaults', 0, 0))
	f.write (format % ("none", "/dev/pts", 'devpts', 'gid=5,mode=620', 0, 0))

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
	    if fsystem == "swap": continue

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

    def saveDruidPartitions(self):
	if self.beenSaved: return
	self.ddruid.save()
	self.beenSaved = 1

    def setBadBlockCheck(self, state):
	self.badBlockCheck = state

    def getBadBlockCheck(self):
	return self.badBlockCheck

    def createDruid(self, fstab = [], ignoreBadDrives = 0):
	return self.fsedit(0, self.driveList(), fstab, self.zeroMbr, 
			   self.readOnly, ignoreBadDrives)

    def getRunDruid(self):
	return self.shouldRunDruid

    def setRunDruid(self, state):
	self.shouldRunDruid = state

    def __init__(self, fsedit, setupFilesystems, serial, zeroMbr, 
		 readOnly, waitWindow, messageWindow):
	self.fsedit = fsedit
	self.fsCache = {}
        self.clearfsOptions()
	self.swapOn = 0
	self.supplementalRaid = []
	self.beenSaved = 1
	self.setupFilesystems = setupFilesystems
	self.serial = serial
	self.zeroMbr = zeroMbr
	self.readOnly = readOnly
	self.waitWindow = waitWindow
	self.messageWindow = messageWindow
	self.badBlockCheck = 0

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
	self.beenSaved = 0

    def __init__(self, setupFilesystems, serial, zeroMbr, readOnly, waitWindow,
		 messageWindow):
	from gnomepyfsedit import fsedit        
	from gtk import *

	Fstab.__init__(self, fsedit, setupFilesystems, serial, zeroMbr, 
		       readOnly, waitWindow, messageWindow)

	self.GtkFrame = GtkFrame
        self.GtkAccelGroup = GtkAccelGroup
	self.SHADOW_NONE = SHADOW_NONE
        self.accelgroup = None

class NewtFstab(Fstab):

    def __init__(self, setupFilesystems, serial, zeroMbr, readOnly, waitWindow,
		 messageWindow):
	from newtpyfsedit import fsedit        

	Fstab.__init__(self, fsedit, setupFilesystems, serial, zeroMbr, 
		       readOnly, waitWindow, messageWindow)

def readFstab (path, fstab):
    f = open (path, "r")
    lines = f.readlines ()
    f.close

    fstab.clearExistingRaid()
    fstab.clearMounts()

    drives = fstab.driveList()
    raidList = raid.scanForRaid(drives)
    raidByDev = {}
    for (mdDev, devList) in raidList:
	raidByDev[mdDev] = devList

    for line in lines:
	fields = string.split (line)
	# skip comments
	if fields and fields[0][0] == '#':
	    continue
	if not fields: continue
	# all valid fstab entries have 6 fields
	if len (fields) < 4 or len (fields) > 6: continue

	if fields[2] != "ext2" and fields[2] != "swap": continue
	if string.find(fields[3], "noauto") != -1: continue
	if (fields[0][0:7] != "/dev/hd" and 
	    fields[0][0:7] != "/dev/sd" and
	    fields[0][0:7] != "/dev/md" and
	    fields[0][0:8] != "/dev/rd/" and
	    fields[0][0:9] != "/dev/ida/"): continue

        if fields[0][0:7] == "/dev/md":
	    fstab.addExistingRaidDevice(fields[0][5:], fields[1], 
				    fields[2], raidByDev[int(fields[0][7:])])
	else:
	    fstab.addMount(fields[0][5:], fields[1], fields[2])

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
