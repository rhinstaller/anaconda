#
# upgrade.py - Existing install probe and upgrade procedure
#
# Matt Wilsonm <msw@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import isys
import _balkan
import os
import iutil
import time
import rpm
import sys
import os.path
from flags import flags
from fsset import *
from partitioning import *
from log import log
from translate import _

def findExistingRoots (intf, id, chroot):
    if not flags.setupFilesystems: return [ (chroot, 'ext2') ]

    diskset = DiskSet()
    diskset.openDevices()
    
    win = intf.waitWindow (_("Searching"),
		    _("Searching for Red Hat Linux installations..."))

    rootparts = diskset.findExistingRootPartitions(intf)
    win.pop ()

    return rootparts

def mountRootPartition(intf, rootInfo, oldfsset, instPath, allowDirty = 0,
		       raiseErrors = 0):
    (root, rootFs) = rootInfo

    diskset = DiskSet()
    diskset.openDevices()
    diskset.startAllRaid()

    if rootFs == "vfat":
	mountLoopbackRoot(root)
    else:
	isys.mount(root, '/mnt/sysimage', rootFs)

    oldfsset.reset()
    newfsset = fsset.readFstab(instPath + '/etc/fstab')
    for entry in newfsset.entries:
        oldfsset.add(entry)

    if rootFs == "vfat":
	unmountLoopbackRoot()
    else:
	isys.umount('/mnt/sysimage')        

    if not allowDirty and oldfsset.hasDirtyFilesystems():
        import sys
        diskset.stopAllRaid()
	intf.messageWindow(_("Dirty Filesystems"),
	    _("One or more of the filesystems for your Linux system "
	      "was not unmounted cleanly. Please boot your Linux "
	      "installation, let the filesystems be checked, and "
	      "shut down cleanly to upgrade."))
	sys.exit(0)

    if flags.setupFilesystems:
        oldfsset.mountFilesystems (instPath)

# returns None if no filesystem exist to migrate
def upgradeMigrateFind(dispatch, thefsset):
    migents = thefsset.getMigratableEntries()
    if not migents or len(migents) < 1:
        dispatch.skipStep("upgrademigratefs")
    else:
        dispatch.skipStep("upgrademigratefs", skip = 0)
    

# returns None if no more swap is needed
def upgradeSwapSuggestion(dispatch, id, instPath):
    # mem is in kb -- round it up to the nearest 4Mb
    mem = iutil.memInstalled(corrected = 0)
    rem = mem % 16384
    if (rem):
	mem = mem + (16384 - rem)
    mem = mem / 1024

    dispatch.skipStep("addswap", 0)
    
    # don't do this if we have more then 512 MB
    if mem > 510:
        dispatch.skipStep("addswap", 1)
        return
    
    swap = iutil.swapAmount() / 1024

    # if we have twice as much swap as ram, we're safe
    if swap >= (mem * 2):
        dispatch.skipStep("addswap", 1)
	return

    fsList = []

    if id.fsset.rootOnLoop():
	space = isys.pathSpaceAvailable("/mnt/loophost")

        for entry in fsset.entries:
            if entry.mountpoint != '/' or space <= 16:
                continue
            
	    info = (entry.mountpoint, entry.device.getDevice(), space)
	    fsList.append(info)
    else:
        for entry in id.fsset.entries:
            # XXX multifsify
            if (entry.fsystem.getName() == "ext2"
                or entry.fsystem.getName() == "ext3"):
                if flags.setupFilesystems and not entry.isMounted():
                    continue
                space = isys.pathSpaceAvailable(instPath + entry.mountpoint)
                if space > 16:
                    info = (entry.mountpoint, entry.device.getDevice(), space)
                    fsList.append(info)

    suggestion = mem * 2 - swap
    suggSize = 0
    suggMnt = None
    for (mnt, part, size) in fsList:
	if (size > suggSize) and (size > (suggestion + 100)):
	    suggMnt = mnt

    id.upgradeSwapInfo = (fsList, suggestion, suggMnt)

def swapfileExists(swapname):
    try:
        os.lstat(swapname)
	return 1
    except:
	return 0

def createSwapFile(instPath, theFsset, mntPoint, size):
    fstabPath = instPath + "/etc/fstab"
    prefix = ""
    if theFsset.rootOnLoop():
	instPath = "/mnt/loophost"
	prefix = "/initrd/loopfs"

    if mntPoint != "/":
        file = mntPoint + "/SWAP"
    else:
        file = "/SWAP"

    swapFileDict = {}
    for entry in theFsset.entries:
        if entry.fsystem.getName() == "swap":
            swapFileDict[entry.device.getName()] = 1
        
    count = 0
    while (swapfileExists(instPath + file) or 
	   swapFileDict.has_key(file)):
	count = count + 1
	tmpFile = "/SWAP-%d" % (count)
        if mntPoint != "/":
            file = mntPoint + tmpFile
        else:
            file = tmpFile

    device = SwapFileDevice(file)
    device.setSize(size)
    fsystem = fileSystemTypeGet("swap")
    entry = FileSystemSetEntry(device, "swap", fsystem)
    entry.setFormat(1)
    theFsset.add(entry)
    theFsset.formatEntry(entry, instPath)
    theFsset.turnOnSwap(instPath)

    # XXX generalize fstab modification
    f = open(fstabPath, "a")
    format = "%-23s %-23s %-7s %-15s %d %d\n";
    f.write(format % (prefix + file, "swap", "swap", "defaults", 0, 0))
    f.close()

# XXX handle going backwards
def upgradeMountFilesystems(intf, rootInfo, oldfsset, instPath):
    # mount everything and turn on swap

    if flags.setupFilesystems:
	try:
	    mountRootPartition(intf, rootInfo, oldfsset, instPath,
                               allowDirty = 0)
	except SystemError, msg:
	    intf.messageWindow(_("Dirty Filesystems"),
		_("One or more of the filesystems listed in the "
		  "/etc/fstab on your Linux system cannot be mounted. "
		  "Please fix this problem and try to upgrade again."))
	    sys.exit(0)

	checkLinks = [ '/etc', '/var', '/var/lib', '/var/lib/rpm',
		       '/boot', '/tmp', '/var/tmp' ]
	badLinks = []
	for n in checkLinks:
	    if not os.path.islink(instPath + n): continue
	    l = os.readlink(instPath + n)
	    if l[0] == '/':
		badLinks.append(n)

	if badLinks:
	    message = _("The following files are absolute symbolic " 
			"links, which we do not support during an " 
			"upgrade. Please change them to relative "
			"symbolic links and restart the upgrade.\n\n")
	    for n in badLinks:
		message = message + '\t' + n + '\n'
	    intf.messageWindow(("Absolute Symlinks"), message)
	    sys.exit(0)
    else:
	newfsset = fsset.readFstab(instPath + '/etc/fstab')
        for entry in newfsset.entries:
            oldfsset.add(entry)
        
    if flags.setupFilesystems:
        oldfsset.turnOnSwap(instPath)

rebuildTime = None

def upgradeFindPackages (intf, method, id, instPath):
    global rebuildTime
    if not rebuildTime:
	rebuildTime = str(int(time.time()))
    method.mergeFullHeaders(id.hdList)

    win = intf.waitWindow (_("Finding"),
                           _("Finding packages to upgrade..."))

    id.dbpath = "/var/lib/anaconda-rebuilddb" + rebuildTime
    rpm.addMacro("_dbpath_rebuild", id.dbpath)
    rpm.addMacro("_dbapi", "-1")

    # now, set the system clock so the timestamps will be right:
    if flags.setupFilesystems:
        iutil.setClock (instPath)
    
    # and rebuild the database so we can run the dependency problem
    # sets against the on disk db

    rebuildpath = instPath + id.dbpath
    rc = rpm.rebuilddb (instPath)
    if rc:
        try:
            iutil.rmrf (rebuildpath)
        except:
            pass
        
	win.pop()
	intf.messageWindow(_("Error"),
                           _("Rebuild of RPM database failed. "
                             "You may be out of disk space?"))
	sys.exit(0)

    rpm.addMacro("_dbpath", id.dbpath)
    rpm.addMacro("_dbapi", "3")
    try:
	packages = rpm.findUpgradeSet (id.hdList.hdlist, instPath)
    except rpm.error:
	iutil.rmrf (rebuildpath)
	win.pop()
	intf.messageWindow(_("Error"),
                           _("An error occured when finding the packages to "
                             "upgrade."))
	sys.exit(0)
	    
    # Turn off all comps
    for comp in id.comps:
	comp.unselect()

    # unselect all packages
    for package in id.hdList.packages.values ():
	package.selected = 0

    hasX = 0
    hasFileManager = 0
    # turn on the packages in the upgrade set
    for package in packages:
	id.hdList[package[rpm.RPMTAG_NAME]].select()
	if package[rpm.RPMTAG_NAME] == "XFree86":
	    hasX = 1
	if package[rpm.RPMTAG_NAME] == "gmc":
	    hasFileManager = 1
	if package[rpm.RPMTAG_NAME] == "kdebase":
	    hasFileManager = 1

    # open up the database to check dependencies
    db = rpm.opendb (0, instPath)

    # check the installed system to see if the packages just
    # are not newer in this release.
    if hasX and not hasFileManager:
        for name in ("gmc", "kdebase"):
            try:
                recs = db.findbyname (name)
                if recs:
                    hasFileManager = 1
                    break
            except rpm.error:
                continue

    # if we have X but not gmc, we need to turn on GNOME.  We only
    # want to turn on packages we don't have installed already, though.
    if hasX and not hasFileManager:
	log ("Upgrade: System has X but no desktop -- Installing GNOME")
        pkgs = ""
	for package in id.comps['GNOME'].pkgs:
	    try:
		rec = db.findbyname (package.name)
	    except rpm.error:
		rec = None
	    if not rec:
                pkgs = "%s %s" % (pkgs, package)
		package.select()
            log ("Upgrade: GNOME: Adding packages: %s", pkgs)

    if iutil.getArch() == "i386" and id.bootloader.useGrub():
	log ("Upgrade: User selected to use GRUB for bootloader")
        if id.hdList.has_key("grub") and not id.hdList["grub"].isSelected():
            log ("Upgrade: grub is not currently selected to be upgraded")
            recs = None
            try:
                recs = db.findbyname ("grub")
            except rpm.error:
                pass
            if not recs:
                log("Upgrade: GRUB is not already installed on the system, "
                    "selecting GRUB")
                id.hdList["grub"].select()
	
    del db

    # new package dependency fixup
    deps = id.comps.verifyDeps(instPath, 1)
    for (name, suggest) in deps:
        if name != _("no suggestion"):
            log ("Upgrade Dependency: %s needs %s, "
                 "automatically added.", name, suggest)
    id.comps.selectDeps (deps)

    win.pop ()


