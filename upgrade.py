#
# upgrade.py - Existing install probe and upgrade procedure
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
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
import lvm
from flags import flags
from fsset import *
from partitioning import *
from constants import *

from rhpl.log import log
from rhpl.translate import _

def findRootParts(intf, id, dispatch, dir, chroot):
    if dir == DISPATCH_BACK:
        return
    if id.rootParts is None:
        id.rootParts = findExistingRoots(intf, id, chroot)

    id.upgradeRoot = []
    for (dev, fs, meta) in id.rootParts:
        id.upgradeRoot.append( (dev, fs) )

    if id.rootParts is not None and len(id.rootParts) > 0:
        dispatch.skipStep("findinstall", skip = 0)
        dispatch.skipStep("installtype", skip = 1)
    else:
        dispatch.skipStep("findinstall", skip = 1)
        dispatch.skipStep("installtype", skip = 0)

def findExistingRoots(intf, id, chroot):
    if not flags.setupFilesystems: return [(chroot, 'ext2', "")]

    diskset = partedUtils.DiskSet()
    diskset.openDevices()
    
    win = intf.progressWindow(_("Searching"),
                              _("Searching for %s installations...") %
                              (productName,), 5)

    rootparts = diskset.findExistingRootPartitions(intf, chroot)
    for i in range(1, 6):
        time.sleep(0.5)
        win.set(i)

    win.pop()

    # close the devices to make sure we don't leave things sitting open 
    diskset.closeDevices()

    # this is a hack... need to clear the skipped disk list after this
    partedUtils.DiskSet.skippedDisks = []

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
    lvm.vgscan()
    lvm.vgactivate()

    log("going to mount %s on %s as %s" %(root, instPath, rootFs))
    isys.mount(root, instPath, rootFs)

    oldfsset.reset()
    newfsset = fsset.readFstab(instPath + '/etc/fstab')
    for entry in newfsset.entries:
        oldfsset.add(entry)

    isys.umount(instPath)        

    dirtyDevs = oldfsset.hasDirtyFilesystems(instPath)
    if not allowDirty and dirtyDevs != []:
        import sys
        diskset.stopAllRaid()
        lvm.vgdeactivate()
	intf.messageWindow(_("Dirty File Systems"),
                           _("The following file systems for your Linux system "
                             "were not unmounted cleanly.  Please boot your "
                             "Linux installation, let the file systems be "
                             "checked and shut down cleanly to upgrade.\n"
                             "%s" %(getDirtyDevString(dirtyDevs),)))
	sys.exit(0)
    elif warnDirty and dirtyDevs != []:
        rc = intf.messageWindow(_("Dirty File Systems"),
                                _("The following file systems for your Linux "
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
    
    # don't do this if we have more then 250 MB
    if mem > 250:
        dispatch.skipStep("addswap", 1)
        return
    
    swap = iutil.swapAmount() / 1024

    # if we have twice as much swap as ram and at least 192 megs
    # total, we're safe 
    if (swap >= (mem * 1.75)) and (swap + mem >= 192):
        dispatch.skipStep("addswap", 1)
	return

    fsList = []

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
		_("One or more of the file systems listed in the "
		  "/etc/fstab on your Linux system cannot be mounted. "
		  "Please fix this problem and try to upgrade again."))
	    sys.exit(0)
        except RuntimeError, msg:
            intf.messageWindow(_("Mount failed"),
		_("One or more of the file systems listed in the "
                  "/etc/fstab of your Linux system are inconsistent and "
                  "cannot be mounted.  Please fix this problem and try to "
                  "upgrade again."))
            sys.exit(0)

	checkLinks = ( '/etc', '/var', '/var/lib', '/var/lib/rpm',
		       '/boot', '/tmp', '/var/tmp', '/root',
                       '/bin/sh')
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

    # if we've been through here once for this root, then short-circuit
    if ((id.upgradeInfoFound is not None) and 
        (id.upgradeInfoFound == id.upgradeRoot)):
        log("already found packages to upgrade for %s" %(id.upgradeRoot,))
        return
    else:
        id.upgradeInfoFound = id.upgradeRoot

    win = intf.waitWindow(_("Finding"),
                          _("Finding packages to upgrade..."))

    # now, set the system clock so the timestamps will be right:
    if flags.setupFilesystems:
        iutil.setClock(instPath)

    # we should only have to rebuild for upgrades of pre rpm 4.0.x systems
    # according to jbj
    if os.access(instPath + "/var/lib/rpm/packages.rpm", os.R_OK):
        id.dbpath = "/var/lib/anaconda-rebuilddb" + rebuildTime
        rpm.addMacro("_dbpath", "/var/lib/rpm")
        rpm.addMacro("_dbpath_rebuild", id.dbpath)
        rpm.addMacro("_dbapi", "-1")
        # have to make sure this isn't set, otherwise rpm won't even
        # *try* to use old-format dbs
        #rpm.addMacro("__dbi_cdb", "")

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
    else:
        id.dbpath = None
        rebuildpath = None
        
    try:
        import findpackageset

        # FIXME: make sure that the rpmdb doesn't have stale locks :/
        for file in ["__db.001", "__db.002", "__db.003"]:
            try:
                os.unlink("%s/var/lib/rpm/%s" %(instPath, file))
            except:
                log("failed to unlink /var/lib/rpm/%s" %(file,))

	packages = findpackageset.findpackageset(id.hdList.hdlist, instPath)
    except rpm.error:
        if rebuildpath is not None:
            iutil.rmrf(rebuildpath)
	win.pop()
	intf.messageWindow(_("Error"),
                           _("An error occurred when finding the packages to "
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
    ts = rpm.TransactionSet(instPath)
    ts.setVSFlags(~(rpm.RPMVSF_NORSA|rpm.RPMVSF_NODSA))

    mi = ts.dbMatch()
    found = 0
    hasX = 0
    hasFileManager = 0

    for h in mi:
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
	if h[rpm.RPMTAG_NAME] == "nautilus":
	    hasFileManager = 1
	if h[rpm.RPMTAG_NAME] == "kdebase":
	    hasFileManager = 1
	if h[rpm.RPMTAG_NAME] == "gmc":
	    hasFileManager = 1

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

    # Figure out current version for upgrade nag and for determining weird
    # upgrade cases
    currentVersion = 0.0
    supportedUpgradeVersion = -1
    mi = ts.dbMatch('name', 'redhat-release')
    for h in mi:
        try:
            vers = string.atof(h[rpm.RPMTAG_VERSION])
        except ValueError:
            vers = 0.0
        if vers > currentVersion:
            currentVersion = vers

        # if we haven't found a redhat-release that compares favorably
        # to 6.2, check this one
        if supportedUpgradeVersion <= 0:
            val = rpm.labelCompare((None, '6.2', '1'),
                                   (h[rpm.RPMTAG_EPOCH], h[rpm.RPMTAG_VERSION],
                                    h[rpm.RPMTAG_RELEASE]))
            if val > 0:
                supportedUpgradeVersion = 0
            else:
                supportedUpgradeVersion = 1

    if supportedUpgradeVersion == 0:
        unsupportedUpgrade = 0
        rc = intf.messageWindow(_("Warning"),
                                _("Upgrades for this version of %s "
                                  "are only supported from Red Hat Linux "
                                  "6.2 or higher.  This appears to be an "
                                  "older system.  Do you wish to continue "
                                  "the upgrade process?") %(productName,),
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
##     if langs:
##         rpm.addMacro("_install_langs", langs)
                
    # check the installed system to see if the packages just
    # are not newer in this release.
    if hasX and not hasFileManager:
        for name in ("nautilus", "kdebase", "gmc"):
            h = ts.dbMatch('name', name).next()
            if h is not None:
                hasFileManager = 1
                break

    # make sure the boot loader being used is being installed.
    # FIXME: generalize so that specific bits aren't needed
    if iutil.getArch() == "i386" and id.bootloader.useGrub():
        log("Upgrade: User selected to use GRUB for bootloader")
        if id.hdList.has_key("grub") and not id.hdList["grub"].isSelected():
            log("Upgrade: grub is not currently selected to be upgraded")
            h = ts.dbMatch('name', 'grub').next()
            if h is None:
                text = ("Upgrade: GRUB is not already installed on the "
                        "system, selecting GRUB")
                id.upgradeDeps ="%s%s\n" % (id.upgradeDeps, text)
                log(text)
                id.hdList["grub"].select()
    if iutil.getArch() == "i386" and not id.bootloader.useGrub():
        log("Upgrade: User selected to use LILO for bootloader")
        if id.hdList.has_key("lilo") and not id.hdList["lilo"].isSelected():
            log("Upgrade: lilo is not currently selected to be upgraded")
            h = ts.dbMatch('name', 'lilo').next()
            if h is None:
                text = ("Upgrade: LILO is not already installed on the "
                        "system, selecting LILO")
                id.upgradeDeps ="%s%s\n" % (id.upgradeDeps, text)
                log(text)
                id.hdList["lilo"].select()
                

    h = ts.dbMatch('name', 'gnome-core').next()
    if h is not None:
        log("Upgrade: gnome-core was on the system.  Upgrading to GNOME 2")
        upgraded = []
        for pkg in ("gnome-terminal", "gnome-desktop", "gnome-session",
                    "gnome-panel", "metacity", "file-roller", "yelp",
                    "nautilus"):
            if id.hdList.has_key(pkg) and not id.hdList[pkg].isSelected():
                id.hdList[pkg].select()
                upgraded.append(pkg)

        text = ("Upgrade: gnome-core is on the system.  Selecting packages "
                "to upgrade to GNOME2: %s" %(str(upgraded),))
        id.upgradeDeps = "%s%s\n" %(id.upgradeDeps, text)

    # if they have up2date-gnome, they probably want the applet now too
    # since it works in both gnome and kde
    if (id.hdList.has_key("rhn-applet")
        and not id.hdList["rhn-applet"].isSelected()):
        log("Upgrade: rhn-applet is not currently selected to be upgraded")
        h = ts.dbMatch('name', 'up2date-gnome').next()

        if h is not None:
            hdr = ts.dbMatch('name', 'rhn-applet').next()
            if hdr is None:
                text = ("Upgrade: up2date-gnome is on the "
                        "system, but rhn-applet isn't.  Selecting "
                        "rhn-applet to be installed")
                id.upgradeDeps = "%s%s\n" % (id.upgradeDeps, text)
                log(text)
                id.hdList["rhn-applet"].select()

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


