#
# upgrade.py - Existing install probe and upgrade procedure
#
# Matt Wilson <msw@redhat.com>
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
import os
import iutil
import time
import rpm
import sys
import os.path
import partedUtils
import string
from flags import flags
from fsset import *
from partitioning import *
from log import log
from translate import _
from constants import *

def findRootParts(intf, id, dir, chroot):
    if dir == DISPATCH_BACK:
        return
    parts = findExistingRoots(intf, id, chroot)
    id.upgradeRoot = parts

def findExistingRoots(intf, id, chroot):
    if not flags.setupFilesystems: return [(chroot, 'ext2')]

    diskset = partedUtils.DiskSet()
    diskset.openDevices()
    
    win = intf.waitWindow(_("Searching"),
                          _("Searching for %s installations...") % (productName,))

    rootparts = diskset.findExistingRootPartitions(intf, chroot)
    win.pop()

    return rootparts

def getDirtyDevString(dirtyDevs):
    ret = ""
    for dev in dirtyDevs:
        if dev != "loop":
            ret = "/dev/%s\n" % (dev,)
        else:
            ret = "%s\n" % (dev,)
    return ret

def mountRootPartition(intf, rootInfo, oldfsset, instPath, allowDirty = 0,
		       raiseErrors = 0, warnDirty = 0, readOnly = 0):
    (root, rootFs) = rootInfo

    diskset = partedUtils.DiskSet()
    diskset.openDevices()
    diskset.startAllRaid()

    if rootFs == "vfat":
	mountLoopbackRoot(root, mountpoint = instPath)
    else:
	isys.mount(root, instPath, rootFs)

    oldfsset.reset()
    newfsset = fsset.readFstab(instPath + '/etc/fstab')
    for entry in newfsset.entries:
        oldfsset.add(entry)

    if rootFs == "vfat":
	unmountLoopbackRoot(mountpoint = instPath)
    else:
	isys.umount(instPath)        

    dirtyDevs = oldfsset.hasDirtyFilesystems(instPath)
    if not allowDirty and dirtyDevs != []:
        import sys
        diskset.stopAllRaid()
	intf.messageWindow(_("Dirty Filesystems"),
                           _("The following filesystems for your Linux system "
                             "were not unmounted cleanly.  Please boot your "
                             "Linux installation, let the filesystems be "
                             "checked and shut down cleanly to upgrade.\n"
                             "%s" %(getDirtyDevString(dirtyDevs),)))
	sys.exit(0)
    elif warnDirty and dirtyDevs != []:
        rc = intf.messageWindow(_("Dirty Filesystems"),
                                _("The following filesystems for your Linux "
                                  "system were not unmounted cleanly.  Would "
                                  "you like to mount them anyway?\n"
                                  "%s" % (getDirtyDevString(dirtyDevs,))),
                                type = "yesno")
        if rc == 0:
            return -1

    if flags.setupFilesystems:
        oldfsset.mountFilesystems(instPath, readOnly = readOnly)

    # XXX we should properly support 'auto' at some point
    if (not oldfsset.getEntryByMountPoint("/") or
        not oldfsset.getEntryByMountPoint("/").fsystem or
        not oldfsset.getEntryByMountPoint("/").fsystem.isMountable()):
        raise RuntimeError, "/etc/fstab did not list a fstype for the root partition which we support"

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
    if rem:
	mem = mem + (16384 - rem)
    mem = mem / 1024

    dispatch.skipStep("addswap", 0)
    
    # don't do this if we have more then 512 MB
    if mem > 510:
        dispatch.skipStep("addswap", 1)
        return
    
    swap = iutil.swapAmount() / 1024

    # if we have twice as much swap as ram and at least 192 megs
    # total, we're safe 
    if (swap >= (mem * 1.75)) and (swap + mem >= 192):
        dispatch.skipStep("addswap", 1)
	return

    fsList = []

    if id.fsset.rootOnLoop():
	space = isys.pathSpaceAvailable("/mnt/loophost")

        for entry in id.fsset.entries:
            if entry.mountpoint != '/' or space <= 16:
                continue
            
	    info = (entry.mountpoint, entry.device.getDevice(), space)
	    fsList.append(info)
    else:
        for entry in id.fsset.entries:
            if entry.fsystem.getName() in fsset.getUsableLinuxFs():
                if flags.setupFilesystems and not entry.isMounted():
                    continue
                space = isys.pathSpaceAvailable(instPath + entry.mountpoint)
                if space > 16:
                    info = (entry.mountpoint, entry.device.getDevice(), space)
                    fsList.append(info)

    suggestion = mem * 2 - swap
    if (swap + mem + suggestion) < 192:
        suggestion = 192 - (swap + mem)
    if suggestion < 32:
        suggestion = 32
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
	    mountRootPartition(intf, rootInfo[0], oldfsset, instPath,
                               allowDirty = 0)
	except SystemError, msg:
	    intf.messageWindow(_("Mount failed"),
		_("One or more of the filesystems listed in the "
		  "/etc/fstab on your Linux system cannot be mounted. "
		  "Please fix this problem and try to upgrade again."))
	    sys.exit(0)
        except RuntimeError, msg:
            intf.messageWindow(_("Mount failed"),
		_("One or more of the filesystems listed in the "
                  "/etc/fstab of your Linux system are inconsistent and "
                  "cannot be mounted.  Please fix this problem and try to "
                  "upgrade again."))
            sys.exit(0)

	checkLinks = [ '/etc', '/var', '/var/lib', '/var/lib/rpm',
		       '/boot', '/tmp', '/var/tmp', '/root' ]
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
        if not os.access (instPath + "/etc/fstab", os.R_OK):
            rc = intf.messageWindow(_("Warning"),
                                    _("%s not found")
                                    % (instPath + "/etc/fstab",),
                                  type="ok")
            return DISPATCH_BACK
            
	newfsset = fsset.readFstab(instPath + '/etc/fstab')
        for entry in newfsset.entries:
            oldfsset.add(entry)
        
    if flags.setupFilesystems:
        oldfsset.turnOnSwap(instPath)

rebuildTime = None

def upgradeFindPackages(intf, method, id, instPath, dir):
    if dir == DISPATCH_BACK:
        return
    global rebuildTime
    if not rebuildTime:
	rebuildTime = str(int(time.time()))
    method.mergeFullHeaders(id.hdList)

    win = intf.waitWindow(_("Finding"),
                          _("Finding packages to upgrade..."))

    id.dbpath = "/var/lib/anaconda-rebuilddb" + rebuildTime
    rpm.addMacro("_dbpath", "/var/lib/rpm")
    rpm.addMacro("_dbpath_rebuild", id.dbpath)
    rpm.addMacro("_dbapi", "-1")

    # now, set the system clock so the timestamps will be right:
    if flags.setupFilesystems:
        iutil.setClock(instPath)
    
    # and rebuild the database so we can run the dependency problem
    # sets against the on disk db

    rebuildpath = instPath + id.dbpath

    try:
        iutil.rmrf(rebuildpath)
    except:
        pass

    rc = rpm.rebuilddb(instPath)
    if rc:
        try:
            iutil.rmrf(rebuildpath)
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
	packages = rpm.findUpgradeSet(id.hdList.hdlist, instPath)
    except rpm.error:
	iutil.rmrf(rebuildpath)
	win.pop()
	intf.messageWindow(_("Error"),
                           _("An error occured when finding the packages to "
                             "upgrade."))
	sys.exit(0)
	    
    # Turn off all comps
    for comp in id.comps:
	comp.unselect()

    # unselect all packages
    for package in id.hdList.packages.values():
	package.selected = 0

    # turn on the packages in the upgrade set
    for package in packages:
	id.hdList[package[rpm.RPMTAG_NAME]].select()

    # open up the database to check dependencies and currently
    # installed packages
    db = rpm.opendb(0, instPath)

    i = db.match()
    h = i.next()
    found = 0
    hasX = 0
    hasFileManager = 0

    while h:
        release = h[rpm.RPMTAG_RELEASE]
        # I'm going to try to keep this message as politically correct
        # as possible.  I think the Ximian GNOME is a very pretty desktop
        # and the hackers there do an extraordinary amount of work on
        # them.  But it throws a huge wrench in our upgrade process.  We
        # just want to warn our users that there are packages on the system
        # that might get messed up during the upgrade process.  Nothing
        # personal, guys.  - msw
        if (string.find(release, "helix") > -1
            or string.find(release, "ximian") > -1
            or string.find(release, "eazel") > -1):
            log("Third party package %s-%s-%s could cause problems." %
                (h[rpm.RPMTAG_NAME],
                 h[rpm.RPMTAG_VERSION],
                 h[rpm.RPMTAG_RELEASE]))
            found = 1
        if h[rpm.RPMTAG_NAME] == "XFree86":
            hasX = 1
	if h[rpm.RPMTAG_NAME] == "gmc":
	    hasFileManager = 1
	if h[rpm.RPMTAG_NAME] == "kdebase":
	    hasFileManager = 1
	if h[rpm.RPMTAG_NAME] == "nautilus":
	    hasFileManager = 1
        h = i.next()

    if found:
        rc = intf.messageWindow(_("Warning"),
                                _("This system appears to have third "
                                  "party packages installed that "
                                  "overlap with packages included in "
                                  "Red Hat Linux. Because these packages "
                                  "overlap, continuing the upgrade "
                                  "process may cause them to stop "
                                  "functioning properly or may cause "
                                  "other system instability.  Do you "
                                  "wish to continue the upgrade process?"),
                                type="yesno")
        if rc == 0:
            try:
                iutil.rmrf(rebuildpath)
            except:
                pass
            sys.exit(0)

    if not os.access(instPath + "/etc/redhat-release", os.R_OK):
        rc = intf.messageWindow(_("Warning"),
                                _("This system does not have an "
                                  "/etc/redhat-release file.  It is possible "
                                  "that this is not a Red Hat Linux system. "
                                  "Continuing with the upgrade process may "
                                  "leave the system in an unusable state.  Do "
                                  "you wish to continue the upgrade process?"),
                                  type="yesno")
        if rc == 0:
            try:
                iutil.rmrf(rebuildpath)
            except:
                pass
            sys.exit(0)

    # during upgrade, make sure that we only install %lang colored files
    # for the languages selected to be supported.
    langs = ''
    if os.access(instPath + "/etc/sysconfig/i18n", os.R_OK):
        f = open(instPath + "/etc/sysconfig/i18n", 'r')
        for line in f.readlines():
            line = string.strip(line)
            parts = string.split(line, '=')
            if len(parts) < 2:
                continue
            if string.strip(parts[0]) == 'SUPPORTED':
                langs = parts[1]
                if len(langs) > 0:
                    if langs[0] == '"' and langs[-1:] == '"':
                        langs = langs[1:-1]
                break
        del f
    if langs:
        rpm.addMacro("_install_langs", langs)
                
    # check the installed system to see if the packages just
    # are not newer in this release.
    if hasX and not hasFileManager:
        for name in ("gmc", "nautilus", "kdebase"):
            try:
                recs = db.findbyname(name)
                if recs:
                    hasFileManager = 1
                    break
            except rpm.error:
                continue

    currentVersion = 0.0
    try:
        recs = db.findbyprovides('redhat-release')
    except rpm.error:
        recs = None
    for rec in recs:
        try:
            vers = string.atof(db[rec][rpm.RPMTAG_VERSION])
        except ValueError:
            vers = 0.0
        if vers > currentVersion:
            currentVersion = vers

    # if we have X but not gmc, we need to turn on GNOME.  We only
    # want to turn on packages we don't have installed already, though.
    # Only do this mess if user is upgrading from version older than 6.0.
    if hasX and not hasFileManager and currentVersion < 6.0:
        text = "Upgrade: System has X but no desktop -- Installing GNOME"
        id.upgradeDeps ="%s%s\n" % (id.upgradeDeps, text)
	log(text)
        pkgs = ""
	for package in id.comps['GNOME'].pkgs:
	    try:
		rec = db.findbyname(package.name)
	    except rpm.error:
		rec = None
	    if not rec:
                pkgs = "%s %s" % (pkgs, package)
		package.select()
            log("Upgrade: GNOME: Adding packages: %s", pkgs)

    if iutil.getArch() == "i386" and id.bootloader.useGrub():
        log("Upgrade: User selected to use GRUB for bootloader")
        if id.hdList.has_key("grub") and not id.hdList["grub"].isSelected():
            log("Upgrade: grub is not currently selected to be upgraded")
            recs = None
            try:
                recs = db.findbyname("grub")
            except rpm.error:
                pass
            if not recs:
                text = ("Upgrade: GRUB is not already installed on the "
                        "system, selecting GRUB")
                id.upgradeDeps ="%s%s\n" % (id.upgradeDeps, text)
                log(text)
                id.hdList["grub"].select()
	
    if (id.hdList.has_key("nautilus")
        and not id.hdList["nautilus"].isSelected()):
        log("Upgrade: nautilus is not currently selected to be upgraded")
        recs = None
        try:
            recs = db.findbyname("gnome-core")
        except rpm.error:
            pass
        if recs:
            recs = None
            try:
                recs = db.findbyname("nautilus")
            except rpm.error:
                pass
            if not recs:
                text = ("Upgrade: gnome-core is on the system, but "
                        "nautilus isn't.  Selecting nautilus to be installed")
                id.upgradeDeps = "%s%s\n" % (id.upgradeDeps, text)
                log(text)
                id.hdList["nautilus"].select()

    # more hacks!  we can't really have anything require rhn-applet without
    # causing lots of pain (think systems that don't want rhn crap installed)
    # and up2date-gnome is just in the X11 group, so KDE users without GNOME
    # get it and we really don't want to change that.  so, more ugprade
    # hacks it is
    if (id.hdList.has_key("rhn-applet")
        and not id.hdList["rhn-applet"].isSelected()):
        log("Upgrade: rhn-applet is not currently selected to be upgraded")
        recs = None
        recs2 = None
        try:
            recs = db.findbyname("gnome-core")
            recs2 = db.findbyname("up2date-gnome")
        except rpm.error:
            pass
        if recs and recs2:
            recs = None
            try:
                recs = db.findbyname("rhn-applet")
            except rpm.error:
                pass
            if not recs:
                text = ("Upgrade: gnome-core and up2date-gnome are on the "
                        "system, but rhn-applet isn't.  Selecting "
                        "rhn-applet to be installed")
                id.upgradeDeps = "%s%s\n" % (id.upgradeDeps, text)
                log(text)
                id.hdList["rhn-applet"].select()

    del db

    # new package dependency fixup
    deps = id.comps.verifyDeps(instPath, 1)
    for (name, suggest) in deps:
        if suggest != _("no suggestion"):
            text = ("Upgrade Dependency: %s needs %s, "
                    "automatically added." % (name, suggest))
            log(text)
            id.upgradeDeps = "%s%s\n" % (id.upgradeDeps, text)
    id.comps.selectDeps(deps)

    win.pop()


