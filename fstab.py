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

def _(str):
    return str

class Fstab:
    def attemptPartitioning(self, partitions, clearParts):
	attempt = []
	swapCount = 0

	fstab = []
	for (mntpoint, dev, fstype, reformat, size) in self.extraFilesystems:
            fstab.append ((dev, mntpoint))

	ddruid = self.createDruid(fstab = fstab)

	for (mntpoint, size, maxsize, grow, device) in partitions:
	    type = 0x83
	    if (mntpoint == "swap"):
		mntpoint = "Swap%04d-auto" % swapCount
		swapCount = swapCount + 1
		type = 0x82

	    attempt.append((mntpoint, size, type, grow, -1, device))

	try:
	    ddruid.attempt (attempt, "Junk Argument", clearParts)
	    return ddruid
	except:
	    pass

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

    def setDruid(self, druid, raid):
	self.ddruid = druid
	self.fsCache = {}
	for (mntPoint, raidDev, level, devices) in raid:
	    if mntPoint == "swap":
		fsystem = "swap"
	    else:
		fsystem = "ext2"
	    self.addRaidDevice(mntPoint, raidDev, fsystem, level, devices)
	    
    def rescanPartitions(self):
	if self.ddruid:
	    self.closeDrives()

        fstab = []
	for (mntpoint, dev, fstype, reformat, size) in self.cachedFstab:
            fstab.append ((dev, mntpoint))

	self.ddruid = self.fsedit(0, self.driveList(), fstab, self.zeroMbr,
				  self.readOnly)
	del self.cachedFstab

    def closeDrives(self):
	# we expect a rescanPartitions() after this!!!
	self.cachedFstab = self.mountList(skipExtra = 1)
	self.ddruid = None

    def setReadonly(self, readOnly):
	self.readOnly = readOnly

    def savePartitions(self):
	self.ddruid.save()

    def runDruid(self):
	self.ddruid.edit()
	# yikes! this needs to be smarter
	self.beenSaved = 0

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
	    if mount[0] == '/':
		self.fsCache[(partition, mount)] = (1,)
        (devices, raid) = self.ddruid.partitionList()
	for (mount, partition, fsystem, level, i, j, deviceList) in \
	    self.raidList()[1]:
	    if mount[0] == '/':
		self.fsCache[(partition, mount)] = (1,)

    def partitionList(self):
	return self.ddruid.partitionList()

    def driveList(self):
	drives = isys.hardDriveList().keys()
	drives.sort (isys.compareDrives)
	return drives

    def drivesByName(self):
	return isys.hardDriveList()

    def swapList(self):
	fstab = []
	for (partition, mount, fsystem, size) in self.ddruid.getFstab():
	    if fsystem != "swap": continue

	    fstab.append((partition, 1))
	return fstab

    def turnOnSwap(self):
	# we could be smarter about this
	if self.swapOn: return
	self.swapOn = 1

	for (device, doFormat) in self.swapList():
	    w = self.waitWindow(_("Formatting"),
			  _("Formatting swap space on /dev/%s...") % (device,))

	    file = '/tmp/' + device
	    isys.makeDevInode(device, file)

	    rc = iutil.execWithRedirect ("/usr/sbin/mkswap",
					 [ "mkswap", '-v1', '/tmp/' + device ],
					 stdout = None, stderr = None,
					 searchPath = 1)
	    w.pop()

	    if rc:
		self.messageWindow(_("Error"), _("Error creating swap on device ") + device)
	    else:
		isys.swapon (file)

	    os.unlink(file)

    def addRaidDevice(self, mountPoint, raidDevice, fileSystem, 
		      raidLevel, deviceList):
	self.supplementalRaid.append((mountPoint, raidDevice, fileSystem,
				  raidLevel, deviceList))
	
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
		isys.makeDevInode(deviceDict[subDevName], '%s/%s' % 
			    (devPrefix, deviceDict[subDevName]))
		rt.write("    device	    %s/%s\n" % 
		    (devPrefix, deviceDict[subDevName],))
		rt.write("    raid-disk     %d\n" % (i,))
		i = i + 1

	rt.write("\n")
	rt.close()

    def umountFilesystems(self):
	if (not self.setupFilesystems): return 

	isys.umount(self.instPath + '/proc')

	for (mntpoint, device, fsystem, doFormat, size) in self.mountList():
            if fsystem != "swap":
		try:
		    mntPoint = self.instPath + n
		    self.log("unmounting " + mntPoint)
                    isys.umount(mntPoint)
		except SystemError, (errno, msg):
		    self.messageWindow(_("Error"), 
			_("Error unmounting %s: %s") % (device, msg))


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

        if not self.setupFilesystems: return

        arch = iutil.getArch ()

        if arch == "alpha":
            if '/boot' in keys:
                kernelPart = '/boot'
            else:
                kernelPart = '/'

	for (mntpoint, device, fsystem, doFormat, size) in self.mountList():
	    if not doFormat: continue
	    isys.makeDevInode(device, '/tmp/' + device)
            if fsystem == "ext2":
                args = [ "mke2fs", '/tmp/' + device ]
                # FORCE the partition that MILO has to read
                # to have 1024 block size.  It's the only
                # thing that our milo seems to read.
                if arch == "alpha" and mntpoint == kernelPart:
                    args = args + ["-b", "1024"]
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
	for (mntpoint, dev, fs, reformat, size) in self.mountList():
	    iutil.mkdirChain(prefix + mntpoint)
	    if (mntpoint == '/'):
		f.write (format % ( '/dev/' + dev, mntpoint, fs, 'defaults', 1, 1))
	    else:
                if (fs == "ext2"):
                    f.write (format % ( '/dev/' + dev, mntpoint, fs, 'defaults', 1, 2))
                elif fs == "iso9660":
                    f.write (format % ( '/dev/' + dev, mntpoint, fs, 'noauto,owner,ro', 0, 0))
                else:
                    f.write (format % ( '/dev/' + dev, mntpoint, fs, 'defaults', 0, 0))
	f.write (format % (fdDevice, "/mnt/floppy", 'ext2', 'noauto,owner', 0, 0))
	f.write (format % ("none", "/proc", 'proc', 'defaults', 0, 0))
	f.write (format % ("none", "/dev/pts", 'devpts', 'gid=5,mode=620', 0, 0))

	for (partition, doFormat) in self.swapList():
	    f.write (format % ("/dev/" + partition, 'swap', 'swap', 
			       'defaults', 0, 0))

	f.close ()
        # touch mtab
        open (prefix + "/etc/mtab", "w+")
        f.close ()

	self.createRaidTab(prefix + "/etc/raidtab", "/dev")

    def addMount(self, partition, mount, fsystem, doFormat = 0, size = 0):
	self.extraFilesystems.append(mount, partition, fsystem, doFormat,
				     size)

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
		self.fsCache[(partition, mount)] = (0, )
	    (doFormat,) = self.fsCache[(partition, mount)]
	    fstab.append((mount, partition, fsystem, doFormat, size ))

	# Add raid mounts to mount list
        (devices, raid) = self.raidList()
	for (mntpoint, device, fsType, raidType, start, size, makeup) in raid:
	    if fsType == "swap": continue

	    if not self.fsCache.has_key((device, mntpoint)):
		self.fsCache[(device, mntpoint)] = (0, )
	    (doFormat,) = self.fsCache[(device, mntpoint)]
	    fstab.append((mntpoint, device, fsType, doFormat, size ))

	if not skipExtra:
	    for n in self.extraFilesystems:
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

    def createDruid(self, fstab = []):
	return self.fsedit(0, self.driveList(), fstab, self.zeroMbr, 
			   self.readOnly)

    def getRunDruid(self):
	return self.shouldRunDruid

    def setRunDruid(self, state):
	self.shouldRunDruid = state

    def __init__(self, fsedit, setupFilesystems, serial, zeroMbr, 
		 readOnly, waitWindow, messageWindow):
	self.fsedit = fsedit
	self.fsCache = {}
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
	self.extraFilesystems = []
	self.ddruid = self.createDruid()
	# I intentionally don't initialize this, as all install paths should
	# initialize this automatically
	#self.shouldRunDruid = 0

class GuiFstab(Fstab):

    def runDruid(self, callback):
        self.ddruid.setCallback (callback)

        bin = self.GtkFrame (None, _obj = self.ddruid.getWindow ())
        bin.set_shadow_type (self.SHADOW_NONE)
        self.ddruid.edit ()
	return bin

    def runDruidFinished(self):
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
	self.SHADOW_NONE = SHADOW_NONE

class NewtFstab(Fstab):

    def __init__(self, setupFilesystems, serial, zeroMbr, readOnly, waitWindow,
		 messageWindow):
	from newtpyfsedit import fsedit        

	Fstab.__init__(self, fsedit, setupFilesystems, serial, zeroMbr, 
		       readOnly, waitWindow, messageWindow)
