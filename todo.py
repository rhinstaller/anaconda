# For an install to proceed, the following todo fields must be filled in
#
#	mount list (unless todo.runLive)		addMount()
#	lilo boot.b installation (may be None)		liloLocation()

import rpm, os
import util, isys
from lilo import LiloConfiguration
from syslog import Syslog

def instCallback(what, amount, total, key, data):
    if (what == rpm.RPMCALLBACK_INST_OPEN_FILE):
	(h, method) = key
	data.setPackage(h)
	data.setPackageScale(0, 1)
	fn = method.getFilename(h)
	d = os.open(fn, os.O_RDONLY)
	return d
    elif (what == rpm.RPMCALLBACK_INST_PROGRESS):
	data.setPackageScale(amount, total)
    elif (what == rpm.RPMCALLBACK_INST_CLOSE_FILE):
	(h, method) = key
	data.completePackage(h)

class ToDo:

    def umountFilesystems(self):
	if (not self.setupFilesystems): return 

	self.mounts.sort(mountListCmp)
	self.mounts.reverse()
	for n in self.mounts:
	    isys.makeDevInode(n, '/tmp/' + n)
	    isys.umount(n)
            os.remove('/tmp/' + n)

    def makeFilesystems(self):
	if (not self.setupFilesystems): return 

	self.mounts.sort(mountListCmp)
	for n in self.mounts:
	    (device, mntpoint, format) = n
	    if not format: continue
	    w = self.intf.waitWindow("Formatting", 
			"Formatting %s filesystem..." % (mntpoint,))
	    isys.makeDevInode(device, '/tmp/' + device)
	    util.execWithRedirect("mke2fs", [ "mke2fs", '/tmp/' + device ],
				  stdout = None, stderr = None, searchPath = 1)
            os.remove('/tmp/' + device)
	    w.pop()

    def mountFilesystems(self):
	if (not self.setupFilesystems): return 

	for n in self.mounts:
	    (device, mntpoint, format) = n
            isys.makeDevInode(device, '/tmp/' + device)
	    isys.mount( '/tmp/' + device, self.instPath + mntpoint)
	    os.remove( '/tmp/' + device);

    def doInstall(self):
	# make sure we have the header list and comps file
	self.headerList()
	self.compsList()

	self.makeFilesystems()
	self.mountFilesystems()

	if not self.installSystem: 
	    return

	for i in [ '/var', '/var/lib', '/var/lib/rpm', '/tmp', '/dev' ]:
	    try:
	        os.mkdir(self.instPath + i)
	    except os.error, (errno, msg):
                print 'Error making directory %s: %s' % (i, msg)

	db = rpm.opendb(1, self.instPath)
	ts = rpm.TransactionSet(self.instPath, db)

        total = 0
	totalSize = 0
	for p in self.hdList.selected():
	    ts.add(p.h, (p.h, self.method))
	    total = total + 1
	    totalSize = totalSize + p.h[rpm.RPMTAG_SIZE]

	ts.order()

	instLog = open(self.instPath + '/tmp/install.log', "w+")
	syslog = Syslog(root = self.instPath, output = instLog)

	instLogFd = os.open(self.instPath + '/tmp/install.log', os.O_RDWR)
	ts.scriptFd = instLogFd
	# the transaction set dup()s the file descriptor and will close the
	# dup'd when we go out of scope
	os.close(instLogFd)	

	p = self.intf.packageProgressWindow(total, totalSize)
	ts.run(0, 0, instCallback, p)

	del syslog

	self.writeFstab()
	self.installLilo()

    def installLilo(self):
	if not self.liloDevice: return

	# FIXME: make an initrd here

	l = LiloConfiguration()
	l.addEntry("boot", '/dev/' + self.liloDevice)
	l.addEntry("map", "/boot/map")
	l.addEntry("install", "/boot/boot.b")
	l.addEntry("prompt")
	l.addEntry("timeout", "50")

	sl = LiloConfiguration()
	sl.addEntry("label", "linux")

	for n in self.mounts:
	    (dev, fs, reformat) = n
	    if fs == '/':
		sl.addEntry("root", '/dev/' + dev)
	sl.addEntry("read-only")

	kernelFile = '/boot/vmlinuz-' +  \
		str(self.kernelPackage[rpm.RPMTAG_VERSION]) + "-" + \
		str(self.kernelPackage[rpm.RPMTAG_RELEASE])
	    
	l.addImage(kernelFile, sl)
	l.write(self.instPath + "/etc/lilo.conf")

	util.execWithRedirect(self.instPath + '/sbin/lilo' , [ "lilo", 
				"-r", self.instPath ], stdout = None)

    def writeFstab(self):
	format = "%-23s %-23s %-7s %-15s %d %d\n";

	f = open(self.instPath + "/etc/fstab", "w")
	self.mounts.sort(mountListCmp)
	for n in self.mounts: 
	    (dev, fs, reformat) = n
	    if (fs == '/'):
		f.write(format % ( '/dev/' + dev, fs, 'ext2', 'defaults', 1, 1))
	    else:
		f.write(format % ( '/dev/' + dev, fs, 'ext2', 'defaults', 1, 2))
	f.write(format % ("/mnt/floppy", "/dev/fd0", 'ext', 'noauto', 0, 0))
	f.write(format % ("none", "/proc", 'proc', 'defaults', 0, 0))
	f.write(format % ("none", "/dev/pts", 'devpts', 'gid=5,mode=620', 0, 0))
	f.close()

    def addMount(self, device, location, reformat = 1):
	self.mounts.append((device, location, reformat))

    def freeHeaders(self):
	if (self.hdList):
	    self.hdList = None

    def headerList(self):
	if (not self.hdList):
	    w = self.intf.waitWindow("Reading",
                                     "Reading package information...")
	    self.hdList = self.method.readHeaders()
	    w.pop()
	return self.hdList

    def liloLocation(self, device):
	self.liloDevice = device

    def compsList(self):
	if (not self.comps):
	    self.headerList()
	    self.comps = self.method.readComps(self.hdList)
	self.comps['Base'].select(1)
	self.kernelPackage = self.hdList['kernel']

	if (self.hdList.has_key('kernel-smp') and isys.smpAvailable()):
	    self.hdList['kernel-smp'].selected = 1
	    self.kernelPackage = self.hdList['kernel-smp']

	return self.comps

    def __init__(self, intf, method, rootPath, setupFilesystems = 1,
		 installSystem = 1):
	self.intf = intf
	self.method = method
	self.mounts = []
	self.hdList = None
	self.comps = None
	self.instPath = rootPath
	self.setupFilesystems = setupFilesystems
	self.installSystem = installSystem

def mountListCmp(first, second):
    mnt1 = first[1]
    mnt2 = first[2]
    if (first < second):
	return -1
    elif (first == second):
	return 0
    return 1
