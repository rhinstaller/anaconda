import isys
import _balkan
import os
from translate import _
import raid
import fstab
from log import log

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
# old code		rootparts.append((dev, "vfat"))
			intf.messageWindow(_("Error"),
			_("Partitionless upgrades are NOT supported in this beta"))
                        isys.umount('/mnt/sysimage')
                        win.pop ()
                        return []

		    isys.umount('/mnt/sysimage')

	os.remove ('/tmp/' + drive)
    win.pop ()
    return rootparts

def mountRootPartition(rootInfo, theFstab, instPath, allowDirty = 0):
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
	intf.messageWindow(("Dirty Filesystems"),
	    _("One or more of the filesystems for your Linux system "
	      "was not unmounted cleanly. Please boot your Linux "
	      "installation, let the filesystems be checked, and "
	      "shut down cleanly to upgrade."))
	sys.exit(0)

    theFstab.mountFilesystems (instPath)
