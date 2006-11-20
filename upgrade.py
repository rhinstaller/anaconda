#
# upgrade.py - Existing install probe and upgrade procedure
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 2001-2003 Red Hat, Inc.
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
import shutil
import lvm
import hdrlist
from flags import flags
from fsset import *
from partitioning import *
from constants import *
from installmethod import FileCopyException
from product import productName

from rhpl.log import log
from rhpl.translate import _
import rhpl

# blacklist made up of (name, arch) or 
# (name, ) to erase all matches
upgrade_remove_blacklist = () 

if rhpl.getArch() == "x86_64":
        upgrade_remove_blacklist.extend( [("ImageMagick","i386"), 
                                          ("gdb", "i386"),
                                          ("libtabe", "i386"),
                                          ("mozilla", "i386"),
                                          ])

if iutil.getArch() == "ppc":
    upgrade_remove_blacklist = (("samba","ppc64"),)

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
        if productName.find("Red Hat Enterprise Linux") == -1:
            dispatch.skipStep("installtype", skip = 1)
    else:
        dispatch.skipStep("findinstall", skip = 1)
        dispatch.skipStep("installtype", skip = 0)

def findExistingRoots(intf, id, chroot, upgradeany = 0):
    if not flags.setupFilesystems:
        relstr = partedUtils.getRedHatReleaseString (chroot)
        if ((cmdline.find("upgradeany") != -1) or
            (upgradeany == 1) or
            (partedUtils.productMatches(relstr, productName))):
            return [(chroot, 'ext2', "")]
        return []

    diskset = partedUtils.DiskSet()
    diskset.openDevices()
    
    win = intf.progressWindow(_("Searching"),
                              _("Searching for %s installations...") %
                              (productName,), 5)

    rootparts = diskset.findExistingRootPartitions(intf, chroot,
                                                   upgradeany = upgradeany)
    for i in range(1, 6):
        time.sleep(0.25)
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
    newfsset = fsset.readFstab(instPath + '/etc/fstab', intf)
    for entry in newfsset.entries:
        oldfsset.add(entry)

    isys.umount(instPath)        

    dirtyDevs = oldfsset.hasDirtyFilesystems(instPath)
    if not allowDirty and dirtyDevs != []:
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
    mem = iutil.memInstalled()
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
    if (swap >= (mem * 1.5)) and (swap + mem >= 192):
        dispatch.skipStep("addswap", 1)
	return

    # if our total is 512 megs or more, we should be safe
    if (swap + mem >= 512):
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
                       '/bin/sh', '/usr/tmp')
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
	    intf.messageWindow(_("Absolute Symlinks"), message)
	    sys.exit(0)

        # fix for 80446
        badLinks = []
        mustBeLinks = ( '/usr/tmp', )
        for n in mustBeLinks:
            if not os.path.islink(instPath + n):
                badLinks.append(n)

        if badLinks: 
	    message = _("The following are directories which should instead "
                        "be symbolic links, which will cause problems with the "
                        "upgrade.  Please return them to their original state "
                        "as symbolic links and restart the upgrade.\n\n")
            for n in badLinks:
                message = message + '\t' + n + '\n'
	    intf.messageWindow(_("Invalid Directories"), message)
	    sys.exit(0)
           
    else:
        if not os.access (instPath + "/etc/fstab", os.R_OK):
            rc = intf.messageWindow(_("Warning"),
                                    _("%s not found")
                                    % (instPath + "/etc/fstab",),
                                  type="ok")
            return DISPATCH_BACK
            
	newfsset = fsset.readFstab(instPath + '/etc/fstab', intf)
        for entry in newfsset.entries:
            oldfsset.add(entry)
        
    if flags.setupFilesystems:
        oldfsset.turnOnSwap(instPath)

# move the old pre-convert db back in case of problems
def resetRpmdb(olddb, instPath):
    if olddb is not None:
        iutil.rmrf(instPath + "/var/lib/rpm")
        os.rename (olddb, instPath + "/var/lib/rpm")    

rebuildTime = None

def upgradeFindPackages(intf, method, id, instPath, dir):
    if dir == DISPATCH_BACK:
        return
    global rebuildTime
    if not rebuildTime:
	rebuildTime = str(int(time.time()))
    try:
        method.mergeFullHeaders(id.grpset.hdrlist)
    except FileCopyException:
        method.unmountCD()
        intf.messageWindow(_("Error"),
                           _("Unable to merge header list.  This may be "
                             "due to a missing file or bad media.  "
                             "Press <return> to try again."))

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
    if (os.access(instPath + "/var/lib/rpm/packages.rpm", os.R_OK) and
        not os.access(instPath + "/var/lib/rpm/Packages", os.R_OK)):
        win.pop()
        intf.messageWindow(_("Error"),
                           _("The installation program is unable to upgrade "
                             "systems with a pre-rpm 4.x database. "
                             "Please install the errata rpm packages "
                             "for your release as described in the release "
                             "notes and then run the upgrade procedure."))
        sys.exit(0)
        
    else:
        id.dbpath = None
        
    try:
        import findpackageset

        # FIXME: make sure that the rpmdb doesn't have stale locks :/
        for file in ["__db.001", "__db.002", "__db.003"]:
            try:
                os.unlink("%s/var/lib/rpm/%s" %(instPath, file))
            except:
                log("failed to unlink /var/lib/rpm/%s" %(file,))

	packages = findpackageset.findpackageset(id.grpset.hdrlist.hdlist,
                                                 instPath)
    except rpm.error:
        if id.dbpath is not None:
            resetRpmdb(id.dbpath, instPath)
	win.pop()
	intf.messageWindow(_("Error"),
                           _("An error occurred when finding the packages to "
                             "upgrade."))
	sys.exit(0)
	    
    # Turn off all comps
    id.grpset.unselectAll()

    # unselect all packages
    for package in id.grpset.hdrlist.pkgs.values():
	package.usecount = 0
        package.manual_state = 0

    # turn on the packages in the upgrade set
    for package in packages:
	id.grpset.hdrlist[hdrlist.nevra(package)].select()

    # open up the database to check dependencies and currently
    # installed packages
    ts = rpm.TransactionSet(instPath)
    ts.setVSFlags(~(rpm.RPMVSF_NORSA|rpm.RPMVSF_NODSA))

    # make sure we have an arch match. (#87655)
    # FIXME: bash wasn't good enough (#129677).  let's try initscripts
    mi = ts.dbMatch('name', 'initscripts')
    myarch = id.grpset.hdrlist["initscripts"][rpm.RPMTAG_ARCH]
    for h in mi:
        if h[rpm.RPMTAG_ARCH] != myarch:
            rc = intf.messageWindow(_("Warning"),
                                    _("The arch of the release of %s you "
                                      "are upgrading to appears to be %s "
                                      "which does not match your previously "
                                      "installed arch of %s.  This is likely "
                                      "to not succeed.  Are you sure you "
                                      "wish to continue the upgrade process?")
                                    %(productName, myarch, 
                                      h[rpm.RPMTAG_ARCH]),
                                    type="yesno")
            if rc == 0:
                try:
                    resetRpmdb(id.dbpath, instPath)
                except Exception, e:
                    log("error returning rpmdb to old state: %s" %(e,))
                    pass
                sys.exit(0)
            else:
                log("WARNING: upgrade between possibly incompatible "
                    "arches %s -> %s" %(h[rpm.RPMTAG_ARCH], myarch))
                
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
        if h[rpm.RPMTAG_NAME] == "XFree86" or h[rpm.RPMTAG_NAME] == "xorg-x11":
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
                                  "%s. Because these packages "
                                  "overlap, continuing the upgrade "
                                  "process may cause them to stop "
                                  "functioning properly or may cause "
                                  "other system instability.  Please see "
                                  "the release notes for more information."
                                  "\n\n"
                                  "Do you wish to continue the upgrade "
                                  "process?") % (productName,),
                                type="yesno")
        if rc == 0:
            try:
                resetRpmdb(id.dbpath, instPath)
            except Exception, e:
                log("error returning rpmdb to old state: %s" %(e,))
                pass
            sys.exit(0)

    if not os.access(instPath + "/etc/redhat-release", os.R_OK):
        rc = intf.messageWindow(_("Warning"),
                                _("This system does not have an "
                                  "/etc/redhat-release file.  It is possible "
                                  "that this is not a %s system. "
                                  "Continuing with the upgrade process may "
                                  "leave the system in an unusable state.  Do "
                                  "you wish to continue the upgrade process?") % (productName,),
                                  type="yesno")
        if rc == 0:
            try:
                resetRpmdb(id.dbpath, instPath)
            except Exception, e:
                log("error returning rpmdb to old state: %s" %(e,))
                pass
            sys.exit(0)

    # Figure out current version for upgrade nag and for determining weird
    # upgrade cases
    supportedUpgradeVersion = -1
    mi = ts.dbMatch('provides', 'redhat-release')
    for h in mi:
        if h[rpm.RPMTAG_EPOCH] is None:
            epoch = None
        else:
            epoch = str(h[rpm.RPMTAG_EPOCH])

        if supportedUpgradeVersion <= 0:
            val = rpm.labelCompare((None, '3', '1'),
                                   (epoch, h[rpm.RPMTAG_VERSION],
                                    h[rpm.RPMTAG_RELEASE]))
            if val > 0:
                supportedUpgradeVersion = 0
            else:
                supportedUpgradeVersion = 1
                break

    if productName.find("Red Hat Enterprise Linux") == -1:
        supportedUpgradeVersion = 1

    if supportedUpgradeVersion == 0:
        rc = intf.messageWindow(_("Warning"),
                                _("You appear to be upgrading from a system "
                                  "which is too old to upgrade to this "
                                  "version of %s.  Are you sure you wish to "
                                  "continue the upgrade "
                                  "process?") %(productName,),
                                type = "yesno")
        if rc == 0:
            try:
                resetRpmdb(id.dbpath, instPath)
            except Exception, e:
                log("error returning rpmdb to old state: %s" %(e,))
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
            try:
                h = ts.dbMatch('name', name).next()
            except StopIteration:
                continue
            if h is not None:
                hasFileManager = 1
                break

    # make sure the boot loader being used is being installed.
    # FIXME: generalize so that specific bits aren't needed
    if iutil.getArch() == "i386" and id.bootloader.useGrub():
        log("Upgrade: User selected to use GRUB for bootloader")
        if id.grpset.hdrlist.has_key("grub") and not id.grpset.hdrlist["grub"].isSelected():
            log("Upgrade: grub is not currently selected to be upgraded")
            h = None
            try:
                h = ts.dbMatch('name', 'grub').next()
            except StopIteration:
                pass
            if h is None:
                text = ("Upgrade: GRUB is not already installed on the "
                        "system, selecting GRUB")
                id.upgradeDeps ="%s%s\n" % (id.upgradeDeps, text)
                log(text)
                id.grpset.hdrlist["grub"].select()
    if iutil.getArch() == "i386" and not id.bootloader.useGrub():
        log("Upgrade: User selected to use LILO for bootloader")
        if id.grpset.hdrlist.has_key("lilo") and not id.grpset.hdrlist["lilo"].isSelected():
            log("Upgrade: lilo is not currently selected to be upgraded")
            h = None
            try:
                h = ts.dbMatch('name', 'lilo').next()
            except StopIteration:
                pass
            if h is None:
                text = ("Upgrade: LILO is not already installed on the "
                        "system, selecting LILO")
                id.upgradeDeps ="%s%s\n" % (id.upgradeDeps, text)
                log(text)
                id.grpset.hdrlist["lilo"].select()
                

    h = None
    try:
        h = ts.dbMatch('name', 'gnome-core').next()
    except StopIteration:
        pass
    if h is not None:
        log("Upgrade: gnome-core was on the system.  Upgrading to GNOME 2")
        upgraded = []
        for pkg in ("gnome-terminal", "gnome-desktop", "gnome-session",
                    "gnome-panel", "metacity", "file-roller", "yelp",
                    "nautilus"):
            if id.grpset.hdrlist.has_key(pkg) and not id.grpset.hdrlist[pkg].isSelected():
                id.grpset.hdrlist[pkg].select()
                upgraded.append(pkg)

        text = ("Upgrade: gnome-core is on the system.  Selecting packages "
                "to upgrade to GNOME2: %s" %(str(upgraded),))
        id.upgradeDeps = "%s%s\n" %(id.upgradeDeps, text)

    # if they have up2date-gnome, they probably want the applet now too
    # since it works in both gnome and kde
    if (id.grpset.hdrlist.has_key("rhn-applet")
        and not id.grpset.hdrlist["rhn-applet"].isSelected()):
        log("Upgrade: rhn-applet is not currently selected to be upgraded")
        h = None
        try:
            h = ts.dbMatch('name', 'up2date-gnome').next()
        except StopIteration:
            pass

        if h is not None:
            hdr = None
            try:
                hdr = ts.dbMatch('name', 'rhn-applet').next()
            except StopIteration:
                pass
            if hdr is None:
                text = ("Upgrade: up2date-gnome is on the "
                        "system, but rhn-applet isn't.  Selecting "
                        "rhn-applet to be installed")
                id.upgradeDeps = "%s%s\n" % (id.upgradeDeps, text)
                log(text)
                id.grpset.hdrlist["rhn-applet"].select()

    # and since xterm is now split out from XFree86 (#98254)
    if (id.grpset.hdrlist.has_key("xterm") and
        not id.grpset.hdrlist["xterm"].isSelected()):
        h = None
        try:
            h = ts.dbMatch('name', 'XFree86').next()
        except StopIteration:
            pass
        if h is not None:
            text = ("Upgrade: XFree86 was on the system.  Pulling in xterm "
                    "for upgrade.")
            id.upgradeDeps = "%s%s\n" %(id.upgradeDeps, text)
            log(text)
            id.grpset.hdrlist["xterm"].select()

    # input methods all changed.  hooray!
    imupg = ( ("ami", "iiimf-le-hangul"),
              ("kinput2-canna-wnn6", "iiimf-le-canna"),
              ("miniChinput", "iiimf-le-chinput"),
              ("xcin", "iiimf-le-xcin") )
    iiimf = 0
    for (old, new) in imupg:
        mi = ts.dbMatch("name", old)
        if (mi.count() > 0 and id.grpset.hdrlist.has_key(new) and
            not id.grpset.hdrlist[new].isSelected()):
            text = "Upgrade: %s was on the system.  Pulling in %s" %(old, new)
            id.upgradeDeps = "%s%s\n" %(id.upgradeDeps, text)
            log(text)
            id.grpset.hdrlist[new].select()
            iiimf = 1
    if iiimf:
        imupg = ( ("iiimf-gnome-im-switcher", "control-center"),
                  ("iiimf-gnome-im-switcher", "gnome-panel"),
                  ("iiimf-gtk", "gtk2"),
                  ("system-switch-im", "gtk2"),
                  ("iiimf-x", "xorg-x11"),
                  ("iiimf-x", "XFree86"))
        for (new, old) in imupg:
            mi = ts.dbMatch("name", old)
            if (not id.grpset.hdrlist.has_key(new) or
                id.grpset.hdrlist[new].isSelected()):
                continue
            if (mi.count() > 0 or
                id.grpset.hdrlist.has_key(old) and
                id.grpset.hdrlist[old].isSelected()):
                text = "Upgrade: Need iiimf base package %s" %(new,)
                id.upgradeDeps = "%s%s\n" %(id.upgradeDeps, text)
                log(text)
                id.grpset.hdrlist[new].select()

    # firefox replaces mozilla/netscape (#137244)
    if (id.grpset.hdrlist.has_key("firefox") and
        not id.grpset.hdrlist["firefox"].isSelected()):
        found = 0
        for p in ("mozilla", "netscape-navigator", "netscape-communicator"):
            mi = ts.dbMatch("name", p)
            found += mi.count()
        if found > 0:
            text = "Upgrade: Found a graphical browser.  Pulling in firefox"
            id.upgradeDeps = "%s%s\n" %(id.upgradeDeps, text)
            log(text)
            id.grpset.hdrlist["firefox"].select()

    # now some upgrade removal black list checking... there are things that
    # if they were installed in the past, we want to remove them because
    # they'll screw up the upgrade otherwise
    for pkg in upgrade_remove_blacklist:
        pkgarch = None
        pkgnames = None
        if len(pkg) == 1:
            pkgname = pkg[0]
        elif len(pkg) == 2:
            pkgname, pkgarch = pkg
        if pkgname is None:
            continue

        mi = ts.dbMatch('name', pkgname)
        for h in mi:
            if h is not None:
                if pkgarch is None:
                    text = ("Upgrade: %s is on the system but will cause "
                    "problems with the upgrade transaction.  Removing." %(pkg,))
                    log(text)
                    id.upgradeDeps = "%s%s\n" %(id.upgradeDeps, text)
                    id.upgradeRemove.append(pkgname)
                    break
                else:
                    if h['arch'] == pkgarch:
                        text = ("Upgrade: %s.%s is on the system but will "
                        "cause problems with the upgrade transaction.  "
                        "Removing." %(pkgname,pkgarch))
                        log(text)
                        id.upgradeDeps = "%s%s\n" %(id.upgradeDeps, text)
                        id.upgradeRemove.append(mi.instance())

    # new package dependency fixup
    depcheck = hdrlist.DependencyChecker(id.grpset, how = "u")
    for p in id.grpset.hdrlist.pkgs.values():
        if p.isSelected():
            ts.addInstall(p.hdr, p.hdr, "u")
    deps = ts.check(depcheck.callback)
    for pkgnevra in deps:
        text = ("Upgrade Dependency: Needs %s, "
                "automatically added." % (pkgnevra,))
        #            log(text)
        id.upgradeDeps = "%s%s\n" % (id.upgradeDeps, text)

    win.pop()


