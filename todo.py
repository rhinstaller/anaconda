# For an install to proceed, the following todo fields must be filled in
#
#	mount list (unless todo.runLive)		addMount()
#	lilo boot.b installation (may be None)		liloLocation()

import rpm, os
import util, isys
from lilo import LiloConfiguration

def instCallback(what, amount, total, key, data):
    if (what == rpm.RPMCALLBACK_INST_OPEN_FILE):
	(h, method) = key
	data.setPackage(h[rpm.RPMTAG_NAME])
	data.setPackageScale(0, 1)
	fn = method.getFilename(h)
	d = os.open(fn, os.O_RDONLY)
	return d
    elif (what == rpm.RPMCALLBACK_INST_PROGRESS):
	data.setPackageScale(amount, total)

class ToDo:

    def umountFilesystems(self):
	if (not self.setupFilesystems): return 

	self.mounts.sort(mountListCmp)
	self.mounts.reverse()
	for n in self.mounts:
	    isys.umount(n)

    def makeFilesystems(self):
	if (not self.setupFilesystems): return 

	self.mounts.sort(mountListCmp)
	for n in self.mounts:
	    (device, mntpoint, format) = n
	    if not format: continue
	    w = self.intf.waitWindow("Formatting", 
			"Formatting %s filesystem..." % (mntpoint,))
	    util.execWithRedirect("mke2fs", [ "mke2fs", device ],
				  stdout = None, searchPath = 1)
	    w.pop()

    def mountFilesystems(self):
	if (not self.setupFilesystems): return 

	for n in self.mounts:
	    (device, mntpoint, format) = n
	    isys.mount(device, self.instPath + mntpoint)

    def doInstall(self):
	# make sure we have the header list and comps file
	self.headerList()
	self.compsList()

	self.makeFilesystems()
	self.mountFilesystems()

	if not self.installSystem: 
	    return

	os.mkdir(self.instPath + '/var')
	os.mkdir(self.instPath + '/var/lib')
	os.mkdir(self.instPath + '/var/lib/rpm')

	db = rpm.opendb(1, self.instPath)
	ts = rpm.TransactionSet(self.instPath, db)

	for p in self.hdList.selected():
	    ts.add(p.h, (p.h, self.method))

	ts.order()
	p = self.intf.packageProgessWindow()
	ts.run(0, 0, instCallback, p)

	self.installLilo()

    def installLilo(self):
	if not self.liloDevice: return

	# FIXME: make an initrd here

	l = LiloConfiguration()
	l.addEntry("boot", self.liloDevice)
	l.addEntry("map", "/boot/map")
	l.addEntry("install", "/boot/boot.b")
	l.addEntry("prompt")
	l.addEntry("timeout", "50")

	sl = LiloConfiguration()
	sl.addEntry("label", "linux")
	sl.addEntry("root", "/dev/hda8")
	sl.addEntry("read-only")

	kernelFile = '/boot/vmlinuz-' +  \
		str(self.kernelPackage[rpm.RPMTAG_VERSION]) + "-" + \
		str(self.kernelPackage[rpm.RPMTAG_RELEASE])
	    
	l.addImage(kernelFile, sl)
	l.write(self.instPath + "/etc/lilo.conf")

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
	    self.hdList['kernel'].selected = 0
	    self.hdList['kernel-smp'].selected = 1
	    self.kernelPackage = self.hdList['kernel-smp']

	return self.comps

    def __init__(self, intf, method, rootPath, setupFilesystems = 1,
		 installSystem = 1, create):
	self.intf = intf
	self.method = method
	self.mounts = []
	self.hdList = None
	self.comps = None
	self.instPath = rootPath
	self.setupFilesystems = setupFilesystems
	self.installSystem = installSystem
	pass

def mountListCmp(first, second):
    mnt1 = first[1]
    mnt2 = first[2]
    if (first < second):
	return -1
    elif (first == second):
	return 0
    return 1
