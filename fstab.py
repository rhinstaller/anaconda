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
import kudzu

fstabFormatString = "%-23s %-23s %-7s %-15s %d %d\n";

class Fstab:

    # return 1 if we should stay on the same screen
    def checkFormatting(self, messageWindow):
	return 0

    def getMbrDevice(self):
	return self.drive

    def getBootDevice(self):
	return self.boot

    def getRootDevice(self):
	return self.root

    def rootOnLoop(self):
	return 0

    def rescanPartitions(self, clearFstabCache = 0):
	pass

    def closeDrives(self, clearFstabCache = 0):
	pass

    def setReadonly(self, readOnly):
	pass

    def savePartitions(self):
	pass

    def runDruid(self):
	pass

    def updateFsCache(self):
	pass

    def setFormatFilesystem(self, device, format):
	pass

    def writeCleanupPath(self, f):
	pass

    def driveList(self):
	return self.drive

    def turnOffSwap(self, devices = 1, files = 0):
	isys.swapoff(self.swap)

    def turnOnSwap(self, instPath, waitWindow, formatSwap = 1):
	iutil.mkdirChain('/tmp/swap')

	device = self.swap

	file = '/tmp/swap/' + device
	isys.makeDevInode(device, file)

	w = waitWindow(_("Formatting"),
		      _("Formatting swap space..."))

	rc = iutil.execWithRedirect ("/usr/sbin/mkswap",
				 [ "mkswap", '-v1', file ],
				 stdout = None, stderr = None,
				 searchPath = 1)
	w.pop()

	if rc:
	    self.messageWindow(_("Error"), _("Error creating swap on device ") + file)
	else:
	    isys.swapon (file)

    def umountFilesystems(self, instPath, ignoreErrors = 0):
	isys.umount(instPath + '/proc', removeDir = 0)

        try:
            isys.umount(instPath + '/proc/bus/usb', removeDir = 0)
            log("Umount USB OK")
        except:
#           log("Umount USB Fail")
            pass

	mounts = self.mountList()
	mounts.reverse()
	for (n, device, fsystem, doFormat, size) in self.mountList():

	    isys.umount(mntPoint, removeDir = 0)

    def makeFilesystems(self, messageWindow, progressWindow):
	labelSkipList = []
	labels = {}
	for (mntpoint, device, fsystem, doFormat, size) in self.mountList():
	    if doFormat: labelSkipList.append(device)

	for (mntpoint, device, fsystem, doFormat, size) in self.mountList():
	    if not doFormat:
                continue

	    isys.makeDevInode(device, '/tmp/' + device)
            if fsystem == "ext2":
		label = createLabel(labels, mntpoint)
                args = [ "/usr/sbin/mke2fs", '/tmp/' + device, '-L', label ]

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

		rc = ext2FormatFilesystem(args, "/dev/tty5",
					  progressWindow, mntpoint)
		if rc:
		    messageWindow(_("Error"), 
			_("An error occured trying to format %s. This problem "
			  "is serious, and the install cannot continue.\n\n"
			  "Press Enter to reboot your system.") % mntpoint)
		    raise SystemError
				
            else:
                pass

    def mountList(self):
	return [("/", self.root, "ext2", 1, 0), 
		("/boot", self.boot, "ext2", 1, 0), 
	        ("swap", self.swap, "swap", 1, 0)]

    def mountFilesystems(self, instPath, raiseErrors = 0, readOnly = 0):
	for (mntpoint, device, fsystem, doFormat, size) in self.mountList():
            if fsystem == "swap":
		continue
	    elif fsystem == "ext2" or fsystem == "ext3" or \
			(fsystem == "vfat" and mntpoint == "/boot/efi"):
		try:
		    iutil.mkdirChain(instPath + mntpoint)
		    isys.mount(device, instPath + mntpoint, fstype = fsystem, 
			       readOnly = readOnly)
		except SystemError, (errno, msg):
		    if raiseErrors:
			raise SystemError, (errno, msg)
		    self.messageWindow(_("Error"), 
			_("Error mounting device %s as %s: %s\n\n"
                          "This most likely means this partition has "
                          "not been formatted.\n\nPress OK to reboot your "
                          "system.") % (device, mntpoint, msg))
                    sys.exit(0)

        try:
            os.mkdir (instPath + '/proc')
        except:
            pass
            
	isys.mount('/proc', instPath + '/proc', 'proc')

    def hasDirtyFilesystems(self):
	if self.rootOnLoop():
	    (rootDev, rootFs) = self.getRootDevice()
	    mountLoopbackRoot(rootDev, skipMount = 1)
	    dirty = isys.ext2IsDirty("loop1")
	    unmountLoopbackRoot(skipMount = 1)
	    if dirty: return 1

	for entry in self.entries:
            # XXX - multifsify, virtualize isdirty per fstype
	    if fsystem != "ext2": continue
	    if doFormat: continue

	    if isys.ext2IsDirty(entry.device.getDevice()): return 1

	return 0


    def write(self, prefix):
	format = fstabFormatString

	f = open (prefix + "/etc/fstab", "w")
	labels = {}
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

	f.close ()
        # touch mtab
        open (prefix + "/etc/mtab", "w+")
        f.close ()

    def __init__(self):

	self.fsCache = {}
	self.swapOn = 0
	self.supplementalRaid = []
	self.badBlockCheck = 0

        #
        # extraFilesystems used for upgrades when /etc/fstab is read as
        # well as for adding fstab entries for removable media
        # Should NOT be used by kickstart any more
        #
	self.extraFilesystems = []
	self.existingRaid = []
	self.loopbackSize = 0
	self.loopbackMountCount = 0
	# I intentionally don't initialize this, as all install paths should
	# initialize this automatically
	#self.shouldRunDruid = 0

	devices = kudzu.probe(kudzu.CLASS_HD, 0, 0)
	list = []
	for dev in devices:
	    if dev.device:
		list.append(dev.device)
	
	list.sort()
	drive = list[0]

	self.drive = drive
	self.root = drive + "1"
	self.boot = drive + "2"
	self.swap = drive + "3"


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
            if labelsByMount.has_key(label):
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
	    # this gets things on devices

	    device = fields[0][5:]
	    fsystem = fields[2]
	    if loopIndex.has_key(device):
		(device, fsystem) = loopIndex[device]

	    fstab.addMount(device, fields[1], fsystem)
	elif (fields[2] == "swap" and fields[0][0:5] != "/dev/"):
	    # swap files
	    file = fields[0]

	    # the loophost looks like /mnt/loophost to the install, not
	    # like /initrd/loopfs
	    if file[0:15] == "/initrd/loopfs/":
		file = "/mnt/loophost/" + file[14:]

	    fstab.addMount(file, "swap", "swap")

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

    fd = os.open(messageFile, os.O_RDWR | os.O_CREAT | os.O_APPEND)
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

    if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
	return 0

    return 1


def enabledSwapDict():
    # returns a dict of swap areas currently being used
    f = open("/proc/swaps", "r")
    lines = f.readlines()
    f.close()

    # the first line is header
    lines = lines[1:]

    swaps = {}
    for line in lines:
	l = string.split(line)
	swaps[l[0]] = 1

    return swaps

