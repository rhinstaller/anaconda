#
# upgrade.py - Existing install probe and upgrade procedure
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 2001-2006 Red Hat, Inc.
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
import sys
import os.path
import partedUtils
import string
import shutil
import lvm
from flags import flags
from fsset import *
from partitioning import *
from constants import *
from installmethod import FileCopyException
from product import productName

import rhpl
from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

# blacklist made up of (name, arch) or 
# (name, ) to erase all matches
upgrade_remove_blacklist = [("system-config-mouse",), ("dev",)] 

if rhpl.getArch() == "x86_64":
    upgrade_remove_blacklist.extend( [("perl","i386"), ("e2fsprogs", "i386")] )

def queryUpgradeContinue(anaconda):
    if anaconda.dir == DISPATCH_FORWARD:
        return

    rc = anaconda.intf.messageWindow(_("Proceed with upgrade?"),
                       _("The file systems of the Linux installation "
                         "you have chosen to upgrade have already been "
                         "mounted. You cannot go back past this point. "
                         "\n\n") + 
                       _("Would you like to continue with the upgrade?"),
                         type="custom", custom_icon=["error","error"],
                         custom_buttons=[_("Reboot"), _("Yes")])
    if rc == 0:
        sys.exit(0)
    return DISPATCH_FORWARD

def findRootParts(anaconda):
    if anaconda.dir == DISPATCH_BACK:
        return
    if anaconda.id.rootParts is None:
        anaconda.id.rootParts = findExistingRoots(anaconda.intf, anaconda.id, anaconda.rootPath)

    anaconda.id.upgradeRoot = []
    for (dev, fs, meta) in anaconda.id.rootParts:
        anaconda.id.upgradeRoot.append( (dev, fs) )

    if anaconda.id.rootParts is not None and len(anaconda.id.rootParts) > 0:
        anaconda.dispatch.skipStep("findinstall", skip = 0)
        if productName.find("Red Hat Enterprise Linux") == -1:
            anaconda.dispatch.skipStep("installtype", skip = 1)
    else:
        anaconda.dispatch.skipStep("findinstall", skip = 1)
        anaconda.dispatch.skipStep("installtype", skip = 0)

def findExistingRoots(intf, id, chroot, upgradeany = 0):
    if not flags.setupFilesystems:
        relstr = partedUtils.getReleaseString (chroot)
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

    log.info("going to mount %s on %s as %s" %(root, instPath, rootFs))
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

    if (not oldfsset.getEntryByMountPoint("/") or
        not oldfsset.getEntryByMountPoint("/").fsystem or
        not oldfsset.getEntryByMountPoint("/").fsystem.isMountable()):
        raise RuntimeError, "/etc/fstab did not list a fstype for the root partition which we support"

def bindMountDevDirectory(instPath):
    fs = fsset.fileSystemTypeGet("bind")
    fs.mount("/dev", "%s/dev" % (instPath,), bindMount=1)

# returns None if no filesystem exist to migrate
def upgradeMigrateFind(dispatch, thefsset):
    migents = thefsset.getMigratableEntries()
    if not migents or len(migents) < 1:
        dispatch.skipStep("upgrademigratefs")
    else:
        dispatch.skipStep("upgrademigratefs", skip = 0)
    

# returns None if no more swap is needed
def upgradeSwapSuggestion(anaconda):
    # mem is in kb -- round it up to the nearest 4Mb
    mem = iutil.memInstalled()
    rem = mem % 16384
    if rem:
	mem = mem + (16384 - rem)
    mem = mem / 1024

    anaconda.dispatch.skipStep("addswap", 0)
    
    # don't do this if we have more then 250 MB
    if mem > 250:
        dispatch.skipStep("addswap", 1)
        return
    
    swap = iutil.swapAmount() / 1024

    # if we have twice as much swap as ram and at least 192 megs
    # total, we're safe 
    if (swap >= (mem * 1.5)) and (swap + mem >= 192):
        anaconda.dispatch.skipStep("addswap", 1)
	return

    # if our total is 512 megs or more, we should be safe
    if (swap + mem >= 512):
        anaconda.dispatch.skipStep("addswap", 1)
	return

    fsList = []

    for entry in anaconda.id.fsset.entries:
        if entry.fsystem.getName() in fsset.getUsableLinuxFs():
            if flags.setupFilesystems and not entry.isMounted():
                continue
            space = isys.pathSpaceAvailable(anaconda.rootPath + entry.mountpoint)
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

    anaconda.id.upgradeSwapInfo = (fsList, suggestion, suggMnt)

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
    theFsset.turnOnSwap(instPath, upgrading=True)

    # XXX generalize fstab modification
    f = open(fstabPath, "a")
    format = "%-23s %-23s %-7s %-15s %d %d\n";
    f.write(format % (prefix + file, "swap", "swap", "defaults", 0, 0))
    f.close()

# XXX handle going backwards
def upgradeMountFilesystems(anaconda):
    # mount everything and turn on swap

    if flags.setupFilesystems:
	try:
	    mountRootPartition(anaconda.intf, anaconda.id.upgradeRoot[0], anaconda.id.fsset,
                               anaconda.rootPath, allowDirty = 0)
	except SystemError, msg:
	    anaconda.intf.messageWindow(_("Mount failed"),
		_("One or more of the file systems listed in the "
		  "/etc/fstab on your Linux system cannot be mounted. "
		  "Please fix this problem and try to upgrade again."))
	    sys.exit(0)
        except RuntimeError, msg:
            anaconda.intf.messageWindow(_("Mount failed"),
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
	    if not os.path.islink(anaconda.rootPath + n): continue
	    l = os.readlink(anaconda.rootPath + n)
	    if l[0] == '/':
		badLinks.append(n)

	if badLinks:
	    message = _("The following files are absolute symbolic " 
			"links, which we do not support during an " 
			"upgrade. Please change them to relative "
			"symbolic links and restart the upgrade.\n\n")
	    for n in badLinks:
		message = message + '\t' + n + '\n'
	    anaconda.intf.messageWindow(_("Absolute Symlinks"), message)
	    sys.exit(0)

        # fix for 80446
        badLinks = []
        mustBeLinks = ( '/usr/tmp', )
        for n in mustBeLinks:
            if not os.path.islink(anaconda.rootPath + n):
                badLinks.append(n)

        if badLinks: 
	    message = _("The following are directories which should instead "
                        "be symbolic links, which will cause problems with the "
                        "upgrade.  Please return them to their original state "
                        "as symbolic links and restart the upgrade.\n\n")
            for n in badLinks:
                message = message + '\t' + n + '\n'
	    anaconda.intf.messageWindow(_("Invalid Directories"), message)
	    sys.exit(0)
           
        bindMountDevDirectory(anaconda.rootPath)
    else:
        if not os.access (anaconda.rootPath + "/etc/fstab", os.R_OK):
            rc = anaconda.intf.messageWindow(_("Warning"),
                                    _("%s not found")
                                    % (anaconda.rootPath + "/etc/fstab",),
                                  type="ok")
            return DISPATCH_BACK
            
	newfsset = fsset.readFstab(anaconda.rootPath + '/etc/fstab', anaconda.intf)
        for entry in newfsset.entries:
            anaconda.id.fsset.add(entry)
        
    if flags.setupFilesystems:
        anaconda.id.fsset.turnOnSwap(anaconda.rootPath, upgrading=True)
        anaconda.id.fsset.mkDevRoot(anaconda.rootPath)
