import isys
import _balkan
import os
from translate import _
import raid
import iutil
import fstab
from log import log
import os.path

def findExistingRoots (intf, diskset):
    rootparts = []
    win = intf.waitWindow (_("Searching"),
		    _("Searching for Red Hat Linux installations..."))

    drives = theFstab.driveList()
    mdList = raid.startAllRaid(drives)

    for dev in mdList:
	if fstab.isValidExt2 (dev):
	    try:
		isys.mount(dev, '/mnt/sysimage', readOnly = 1)
	    except SystemError, (errno, msg):
		intf.messageWindow(_("Error"),
					_("Error mounting ext2 filesystem on %s: %s") % (dev, msg))
		continue
	    if os.access ('/mnt/sysimage/etc/fstab', os.R_OK):
		rootparts.append ((dev, "ext2"))
	    isys.umount('/mnt/sysimage')

    raid.stopAllRaid(mdList)
    
    for drive in drives:
	isys.makeDevInode(drive, '/tmp/' + drive)
	
	try:
	    table = _balkan.readTable ('/tmp/' + drive)
	except SystemError:
	    pass
	else:
	    for i in range (len (table)):
		(type, sector, size) = table[i]
		if size and type == _balkan.EXT2:
		    # for RAID arrays of format c0d0p1
		    if drive [:3] == "rd/" or drive [:4] == "ida/" or drive [:6] == "cciss/":
			dev = drive + 'p' + str (i + 1)
		    else:
			dev = drive + str (i + 1)
		    try:
			isys.mount(dev, '/mnt/sysimage')
		    except SystemError, (errno, msg):
			intf.messageWindow(_("Error"),
						_("Error mounting ext2 filesystem on %s: %s") % (dev, msg))
			continue
		    if os.access ('/mnt/sysimage/etc/fstab', os.R_OK):
			rootparts.append ((dev, "ext2"))
		    isys.umount('/mnt/sysimage')
		elif size and type == _balkan.DOS:
		    dev = drive + str (i + 1)
		    try:
			isys.mount(dev, '/mnt/sysimage', fstype = "vfat",
				   readOnly = 1)
		    except SystemError, (errno, msg):
			log("failed to mount vfat filesystem on %s\n" 
				    % dev)
			continue

		    if os.access('/mnt/sysimage/redhat.img', os.R_OK):
                        rootparts.append((dev, "vfat"))

		    isys.umount('/mnt/sysimage')

	os.remove ('/tmp/' + drive)
    win.pop ()
    return rootparts

def mountRootPartition(intf, rootInfo, theFstab, instPath, allowDirty = 0,
		       raiseErrors = 0):
    (root, rootFs) = rootInfo

    mdList = raid.startAllRaid(theFstab.driveList())

    if rootFs == "vfat":
	fstab.mountLoopbackRoot(root)
    else:
	isys.mount(root, '/mnt/sysimage')

    fstab.readFstab(instPath + '/etc/fstab', theFstab)

    if rootFs == "vfat":
	fstab.unmountLoopbackRoot()
    else:
	isys.umount('/mnt/sysimage')        

    raid.stopAllRaid(mdList)

    if not allowDirty and theFstab.hasDirtyFilesystems():
        import sys
	intf.messageWindow(_("Dirty Filesystems"),
	    _("One or more of the filesystems for your Linux system "
	      "was not unmounted cleanly. Please boot your Linux "
	      "installation, let the filesystems be checked, and "
	      "shut down cleanly to upgrade."))
	sys.exit(0)

    theFstab.mountFilesystems (instPath, raiseErrors = raiseErrors)

# returns None if no more swap is needed
def swapSuggestion(instPath, fstab):
    # mem is in kb -- round it up to the nearest 4Mb
    mem = iutil.memInstalled(corrected = 0)
    rem = mem % 16384
    if (rem):
	mem = mem + (16384 - rem)
    mem = mem / 1024

    # don't do this if we have more then 512 MB
    if mem > 510: return None

    swap = iutil.swapAmount() / 1024

    # if we have twice as much swap as ram, we're safe
    if swap >= (mem * 2):
	return None

    fsList = []

    if fstab.rootOnLoop():
	space = isys.pathSpaceAvailable("/mnt/loophost")

	for info in fstab.mountList():
	    (mntpoint, partition) = info[0:2]
	    if mntpoint != '/': continue
	    info = (mntpoint, partition, space)
	    fsList.append(info)
    else:
	for info in fstab.mountList():
	    (mntpoint, partition, fsystem) = info[0:3]
	    if fsystem == "ext2":
		space = isys.pathSpaceAvailable(instPath + mntpoint)
		info = (mntpoint, partition, space)
		fsList.append(info)

    suggestion = mem * 2 - swap
    suggSize = 0
    suggMnt = None
    for (mnt, part, size) in fsList:
	if (size > suggSize) and (size > (suggestion + 100)):
	    suggMnt = mnt

    return (fsList, suggestion, suggMnt)


def swapfileExists(swapname):

    try:
        rc = os.lstat(swapname)
	return 1
    except:
	return 0

def createSwapFile(instPath, theFstab, mntPoint, size):
    fstabPath = instPath + "/etc/fstab"
    prefix = ""
    if theFstab.rootOnLoop():
	instPath = "/mnt/loophost"
	prefix = "/initrd/loopfs"

    if mntPoint != "/":
        file = mntPoint + "/SWAP"
    else:
        file = "/SWAP"

    existingSwaps = theFstab.swapList(files = 1)
    swapFileDict = {}
    for n in existingSwaps:
	dev = n[0]
	swapFileDict[dev] = 1
        
    count = 0
    while (swapfileExists(instPath + file) or 
	   swapFileDict.has_key(file)):
	count = count + 1
	tmpFile = "/SWAP-%d" % (count)
        if mntPoint != "/":
            file = mntPoint + tmpFile
        else:
            file = tmpFile

    theFstab.addMount(file, size, "swap")
    theFstab.turnOnSwap(instPath)

    f = open(fstabPath, "a")
    f.write(fstab.fstabFormatString % (prefix + file, "swap", "swap", "defaults",
	    0, 0))
    f.close()

def upgradeFindRoot(self):
    if not self.setupFilesystems: return [ (self.instPath, 'ext2') ]
    return upgrade.findExistingRoots(self.intf, self.fstab)

def upgradeMountFilesystems(self, rootInfo):
    # mount everything and turn on swap

    if self.setupFilesystems:
	try:
	    upgrade.mountRootPartition(self.intf,rootInfo,
				       self.fstab, self.instPath,
				       allowDirty = 0)
	except SystemError, msg:
	    self.intf.messageWindow(_("Dirty Filesystems"),
		_("One or more of the filesystems listed in the "
		  "/etc/fstab on your Linux system cannot be mounted. "
		  "Please fix this problem and try to upgrade again."))
	    sys.exit(0)

	checkLinks = [ '/etc', '/var', '/var/lib', '/var/lib/rpm',
		       '/boot', '/tmp', '/var/tmp' ]
	badLinks = []
	for n in checkLinks:
	    if not os.path.islink(self.instPath + n): continue
	    l = os.readlink(self.instPath + n)
	    if l[0] == '/':
		badLinks.append(n)

	if badLinks:
	    message = _("The following files are absolute symbolic " 
			"links, which we do not support during an " 
			"upgrade. Please change them to relative "
			"symbolic links and restart the upgrade.\n\n")
	    for n in badLinks:
		message = message + '\t' + n + '\n'
	    self.intf.messageWindow(("Absolute Symlinks"), message)
	    sys.exit(0)
    else:
	fstab.readFstab(self.instPath + '/etc/fstab', self.fstab)
	
    # XXX fssetify
    self.fstab.turnOnSwap(self.instPath, formatSwap = 0)
		
def upgradeFindPackages (self):
    if not self.rebuildTime:
	self.rebuildTime = str(int(time.time()))
    self.getCompsList ()
    self.getHeaderList ()
    self.method.mergeFullHeaders(self.hdList)

    win = self.intf.waitWindow (_("Finding"),
				_("Finding packages to upgrade..."))

    self.dbpath = "/var/lib/anaconda-rebuilddb" + self.rebuildTime
    rpm.addMacro("_dbpath_rebuild", self.dbpath)
    rpm.addMacro("_dbapi", "-1")

    # now, set the system clock so the timestamps will be right:
    iutil.setClock (self.instPath)
    
    # and rebuild the database so we can run the dependency problem
    # sets against the on disk db
    rc = rpm.rebuilddb (self.instPath)
    if rc:
        try:
            iutil.rmrf (self.instPath + "/var/lib/anaconda-rebuilddb"
                        + self.rebuildTime)
        except:
            pass
        
	win.pop()
	self.intf.messageWindow(_("Error"),
				_("Rebuild of RPM database failed. "
				  "You may be out of disk space?"))
	if self.setupFilesystems:
	    self.fstab.umountFilesystems (self.instPath)
	sys.exit(0)

    rpm.addMacro("_dbpath", self.dbpath)
    rpm.addMacro("_dbapi", "3")
    try:
	packages = rpm.findUpgradeSet (self.hdList.hdlist, self.instPath)
    except rpm.error:
	iutil.rmrf (self.instPath + "/var/lib/anaconda-rebuilddb"
		    + self.rebuildTime)
	win.pop()
	self.intf.messageWindow(_("Error"),
				_("An error occured when finding the packages to "
				  "upgrade."))
	if self.setupFilesystems:
	    self.fstab.umountFilesystems (self.instPath)
	sys.exit(0)
	    
    # Turn off all comps
    for comp in self.comps:
	comp.unselect()

    # unselect all packages
    for package in self.hdList.packages.values ():
	package.selected = 0

    hasX = 0
    hasFileManager = 0
    # turn on the packages in the upgrade set
    for package in packages:
	self.hdList[package[rpm.RPMTAG_NAME]].select()
	if package[rpm.RPMTAG_NAME] == "XFree86":
	    hasX = 1
	if package[rpm.RPMTAG_NAME] == "gmc":
	    hasFileManager = 1
	if package[rpm.RPMTAG_NAME] == "kdebase":
	    hasFileManager = 1

    # open up the database to check dependencies
    db = rpm.opendb (0, self.instPath)

    # if we have X but not gmc, we need to turn on GNOME.  We only
    # want to turn on packages we don't have installed already, though.
    if hasX and not hasFileManager:
	log ("Has X but no desktop -- Installing GNOME")
	for package in self.comps['GNOME'].pkgs:
	    try:
		rec = db.findbyname (package.name)
	    except rpm.error:
		rec = None
	    if not rec:
		log ("GNOME: Adding %s", package)
		package.select()
	
    del db

    # new package dependency fixup
    deps = self.verifyDeps ()
    loops = 0
    while deps and self.canResolveDeps (deps) and loops < 10:
	for (name, suggest) in deps:
	    if name != _("no suggestion"):
		log ("Upgrade Dependency: %s needs %s, "
		     "automatically added.", name, suggest)
	self.selectDeps (deps)
	deps = self.verifyDeps ()
	loops = loops + 1

    win.pop ()


