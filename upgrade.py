import isys
import _balkan
import os
from translate import _
import raid
import iutil
import fstab
from log import log
import os.path

def findExistingRoots (intf, theFstab):
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

    fstab.readFstab('/mnt/sysimage/etc/fstab', theFstab)

    if rootFs == "vfat":
	fstab.unmountLoopbackRoot()
    else:
	isys.umount('/mnt/sysimage')        

    raid.stopAllRaid(mdList)

    if not allowDirty and theFstab.hasDirtyFilesystems():
        import sys
	intf.messageWindow(("Dirty Filesystems"),
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
	    (mntpoint, partition) = info[0:2]
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

    if os.access(swapname, os.R_OK):
        return 1

    exists = 0
    try:
        rc = os.lstat(swapname)
        exists = 1
    except:
        pass

    return exists
            

def createSwapFile(instPath, theFstab, mntPoint, size, progressWindow):
    fstabPath = instPath + "/etc/fstab"
    prefix = ""
    if theFstab.rootOnLoop():
	instPath = "/mnt/loophost"
	prefix = "/initrd/loopfs"

    file = mntPoint + "/SWAP"
    count = 0
    while (swapfileExists(instPath + file)):
	count = count + 1
	file = "%s/SWAP-%d" % mntPoint, count

    theFstab.addMount(file, size, "swap")
    theFstab.turnOnSwap(instPath, progressWindow)

    f = open(fstabPath, "a")
    f.write(fstab.fstabFormatString % (prefix + file, "swap", "swap", "defaults",
	    0, 0))
    f.close()








