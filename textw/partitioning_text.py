import iutil
import os
import isys
from snack import *
from constants_text import *
from translate import _
from log import log

class PartitionMethod:
    def __call__(self, screen, todo):
	if not todo.fstab.getRunDruid():
	    todo.skipFdisk = 1
	    return INSTALL_NOOP

	rc = ButtonChoiceWindow(screen, _("Disk Setup"),
	    _("Disk Druid is a tool for partitioning and setting up mount "
	      "points. It is designed to be easier to use than Linux's "
	      "traditional disk partitioning sofware, fdisk, as well "
	      "as more powerful. However, there are some cases where fdisk "
	      "may be preferred.\n"
	      "\n"
	      "Which tool would you like to use?"),
	    [ (_("Disk Druid"), "dd") , (_("fdisk"), "fd"), 
	      (_("Back"), "back") ], width = 50, help = "parttool")

	if rc == "back":
	    return INSTALL_BACK
	elif rc == "fd":
	    todo.skipFdisk = 0
	else:
	    todo.skipFdisk = 1

	return INSTALL_OK

class ManualPartitionWindow:
    def __call__(self, screen, todo):
	from newtpyfsedit import fsedit        

	if todo.skipFdisk:
            return INSTALL_NOOP
	
	driveNames = todo.fstab.driveList()
	drives = todo.fstab.drivesByName()

	choices = []
	haveEdited = 0

	for device in driveNames:
	    descrip = drives[device]
	    if descrip:
		choices.append("/dev/%s - %s" % (device, descrip))
	    else:
		choices.append("/dev/%s" % (device,))

        button = None
	while button != "done" and button != "back":
	    (button, choice) = \
		 ListboxChoiceWindow(screen, _("Disk Setup"),
		_("To install Red Hat Linux, you must have at least one "
		     "partition of 150 MB dedicated to Linux. We suggest "
		     "placing that partition on one of the first two hard "
		     "drives in your system so you can boot into Linux "
		     "with LILO."), choices,
		[ (_("Done"), "done") , (_("Edit"), "edit"), 
		  (_("Back"), "back") ], width = 50, help = "fdisk")

	    if button != "done" and button != "back":
		# free our fd's to the hard drive -- we have to 
		# fstab.rescanDrives() after this or bad things happen!
		if not haveEdited:
		    todo.fstab.setReadonly(1)
		    todo.fstab.closeDrives()
		haveEdited = 1
		device = driveNames[choice]
		screen.suspend ()
		if os.access("/sbin/fdisk", os.X_OK):
		    path = "/sbin/fdisk"
		else:
		    path = "/usr/sbin/fdisk"
                    
                try:
                    isys.makeDevInode(device, '/tmp/' + device)
                except:
                    # XXX FIXME
                    pass
		iutil.execWithRedirect (path, [ path, "/tmp/" + device ],
					ignoreTermSigs = 1)
                try:
                    os.remove ('/tmp/' + device)
                except:
                    # XXX fixme
                    pass
		screen.resume ()

	todo.fstab.rescanPartitions()

	if button == "back":
	    return INSTALL_BACK

	return INSTALL_OK

class AutoPartitionWindow:
    def __call__(self, screen, todo):
	druid = None


        # if harddrive install and installing from a logical partition,
        # do not offer autopartitioning
        if iutil.getArch() == 'i386' and todo.instClass.getClearParts() != 0:
            pp = todo.method.protectedPartitions()
            if pp:
                for p in pp:
                    if int(p[-1:]) > 4:
                        todo.fstab.setRunDruid(1)
                        return

        # if instClass has new or old partition info we are in ks
	if todo.instClass.partitions or todo.instClass.fstab:
	    druid = \
		todo.fstab.attemptPartitioning(todo.instClass.partitions,
                                               todo.instClass.fstab,
					       todo.instClass.clearParts)

	if not druid:
	    # auto partitioning failed
	    todo.fstab.setRunDruid(1)
	    return

	if not todo.getPartitionWarningText():
	    todo.fstab.setRunDruid(0)
	    todo.fstab.setDruid(druid, todo.instClass.raidList)

	    # sets up lilo for raid boot partitions during kickstart
	    todo.lilo.allowLiloLocationConfig(todo.fstab)

	    todo.fstab.formatAllFilesystems()

            # make sure we don't format partitions we were told not too in
            # kickstart mode
            if todo.instClass.fstab:
                for (mntpoint, (dev, fstype, reformat)) in todo.instClass.fstab:
                    if reformat == 0:
                        todo.fstab.setFormatFilesystem(dev, 0)
                        
	    todo.instClass.addToSkipList("format")

	    return

	(rc, choice) = ListboxChoiceWindow(screen, _("Automatic Partitioning"),
	    _("Automatic partitioning will erase %s\n\n"
              "If you don't want to do this, you can continue with "
	      "this install by partitioning manually, or you can go back "
	      "and perform a fully customized installation.") % 
		    (_(todo.getPartitionWarningText()), ),
	    [_("Continue"), _("Manually partition")],
	    buttons = ((_("Ok"), "ok"), (_("Back"), "back")),
            default = _("Continue"), 
	    help = "confirmautopart")

	if (rc == "back"): 
	    # This happens automatically when we go out of scope, but it's
	    # important so let's be explicit
	    druid = None
	    return INSTALL_BACK

        if (choice == 1):
            # if druid wasn't running, must have been in autopartition mode
            # clear fstab cache so we don't get junk from attempted
            # autopartitioning
            #
            # msf - this is not working becaue setRunDruid is not
            #       called before we get here, unlike in the GUI case
            #
            #       Set clearcache - may need to be 1 to
            #       avoid autopartitioning attempt above from
            #       polluting manual partitioning with invalid
            #       fstab entries
            #
#           clearcache = not todo.fstab.getRunDruid()
            clearcache = 1
	    todo.fstab.setRunDruid(1)
	    del druid
	    todo.fstab.rescanPartitions(clearcache)
	    todo.instClass.removeFromSkipList("format")
	else:
	    todo.fstab.setRunDruid(0)
	    todo.fstab.setDruid(druid, todo.instClass.raidList)
	    todo.lilo.allowLiloLocationConfig(todo.fstab)
	    todo.fstab.formatAllFilesystems()
	    todo.instClass.addToSkipList("format")

        return INSTALL_OK
        
class PartitionWindow:
    def __call__(self, screen, todo):
	dir = INSTALL_NOOP
	if todo.fstab.getRunDruid():
	    dir = todo.fstab.runDruid()

	# runDruid returns None when it means INSTALL_OK
        if not dir:
	    dir = INSTALL_OK

        return dir

class TurnOnSwapWindow:

    beenTurnedOn = 0

    def __call__(self, screen, todo):
	if self.beenTurnedOn or (iutil.memInstalled() > isys.EARLY_SWAP_RAM):
	    return INSTALL_NOOP

        if not todo.instClass.earlySwapOn:
	    rc = ButtonChoiceWindow(screen, _("Low Memory"),
		       _("As you don't have much memory in this machine, we "
			 "need to turn on swap space immediately. To do this "
			 "we'll have to write your new partition table to the "
			 "disk immediately. Is that okay?"),
		       [ (_("Yes"), "yes"), (_("Back"), "back") ], width = 50,
		       help = "earlyswapon")

	    if (rc == "back"):
		return INSTALL_BACK

        todo.fstab.savePartitions ()
	todo.fstab.turnOnSwap()
	todo.ddruidAlreadySaved = 1
	self.beenTurnedOn = 1

	return INSTALL_OK

class FormatWindow:
    def __call__(self, screen, todo):
        tb = TextboxReflowed (55,
                              _("What partitions would you like to "
                                "format? We strongly suggest formatting "
                                "all of the system partitions, including "
                                "/, /usr, and /var. There is no need to "
                                "format /home or /usr/local if they have "
                                "already been configured during a "
                                "previous install."))

	mounts = todo.fstab.formattablePartitions()
        height = min (screen.height - 12, len (mounts))
        
        ct = CheckboxTree(height = height, scroll = 1)

	gotOne = 0
	for (mount, dev, fstype, format, size) in mounts:
	    gotOne = 1
	    ct.append("/dev/%s   %s" % (dev, mount), dev, format)

	if not gotOne: return INSTALL_NOOP

        cb = Checkbox (_("Check for bad blocks during format"),
			todo.fstab.getBadBlockCheck())

        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        g = GridFormHelp (screen, _("Choose Partitions to Format"), 
			 "formatwhat", 1, 4)
        g.add (tb, 0, 0, (0, 0, 0, 1))
        g.add (ct, 0, 1)
        g.add (cb, 0, 2, (0, 1, 0, 1))
        g.add (bb, 0, 3, growx = 1)

	done = 0

	while not done:
	    result = g.run()
	    rc = bb.buttonPressed (result)
	    if rc == "back":
		screen.popWindow()
		return INSTALL_BACK

	    for (mount, dev, fstype, format, size) in mounts:
		todo.fstab.setFormatFilesystem(dev, 0)

	    for dev in ct.getSelection():
		todo.fstab.setFormatFilesystem(dev, 1)

	    todo.fstab.setBadBlockCheck(cb.selected ())

	    rc = todo.fstab.checkFormatting(todo.intf.messageWindow)

	    if not rc:
		done = 1

	screen.popWindow()

        return INSTALL_OK

class LoopSizeWindow:

    def __call__(self, screen, todo):
	if not todo.fstab.rootOnLoop():
	    return INSTALL_NOOP

        rootdev = todo.fstab.getRootDevice()
	avail = apply(isys.spaceAvailable, rootdev)

        # add in size of loopback files if they exist
        extra = 0
        try:
            import os, stat
            isys.mount(rootdev[0], "/mnt/space", fstype = rootdev[1])
            extra = extra + os.stat("/mnt/space/redhat.img")[stat.ST_SIZE]
            extra = extra + os.stat("/mnt/space/rh-swap.img")[stat.ST_SIZE]
            isys.umount("/mnt/space")
        except:
            pass

        # do this separate since we dont know when above failed
        try:
            isys.umount("/mnt/space")
        except:
            pass

        extra = extra / 1024 / 1024
        avail = avail + extra
        
	(size, swapSize) = todo.fstab.getLoopbackSize()
	if not size:
	    size = avail / 2
            if size > 2000:
                size = 2000
	    swapSize = 32

	sizeEntry = Entry(6, "%d" % (size,))
	swapSizeEntry = Entry(6, "%d" % (swapSize,))

	while 1:
	    (rc, ent) = EntryWindow(screen, _("Root Filesystem Size"),
		_("You've chosen to put your root filesystem in a file on "
		  "an already-existing DOS or Windows filesystem. How large, "
		  "in megabytes, should would you like the root filesystem "
		  "to be, and how much swap space would you like? They must "
		  "total less then %d megabytes in size." % (avail, )),
		    [ ( _("Root filesystem size"), sizeEntry ),
		      ( _("Swap space"), swapSizeEntry ) ],
		    buttons = [ (_("OK"), "ok"), (_("Back"), "back") ],
		    help = "loopbacksize")

	    if rc == "back": return INSTALL_BACK

	    try:
		size = int(sizeEntry.value())
		swapSize = int(swapSizeEntry.value())
	    except:
		ButtonChoiceWindow(screen, _("Bad Size"),
			_("The size you enter must be a number."),
			buttons = [ _("OK") ])
		continue

	    if size + swapSize >= avail:
		ButtonChoiceWindow(screen, _("Bad Size"),
			_("The total size must be smaller then the amount of "
			  "free space on the disk, which is %d megabytes."
				% (avail, )),
			buttons = [ _("OK") ])
		continue
	    if size > 2000 or swapSize > 2000:
		ButtonChoiceWindow(screen, _("Bad Size"),
			_("Neither the root file system size "
			  "nor the swap space size may be greater then "
			  "2000 megabytes."),
			buttons = [ _("OK") ])
		continue

	    break

	todo.fstab.setLoopbackSize(size, swapSize)

	return INSTALL_NOOP
	
class LBA32WarningWindow:
    def __call__(self, dir, screen, todo):

        if dir == -1:
            return INSTALL_NOOP
        
        # check if boot partition is above 1024 cyl limit
        if iutil.getArch() != "i386":
            return INSTALL_NOOP

        maxcyl = todo.fstab.getBootPartitionMaxCylFromDesired()
        log("Maximum cylinder is %s" % maxcyl)
        if maxcyl > 1024:
            if not todo.fstab.edd:
                rc = ButtonChoiceWindow(screen, _("Boot Partition Warning"),
                     _("You have put the partition containing the kernel (the "
                      "boot partition) above the 1024 cylinder limit, and "
                      "it appears that this systems BIOS does not support "
                      "booting from above this limit. Proceeding will "
                      "most likely make the system unable to reboot into "
                      "Linux.\n\n"
                      "If you choose to proceed, it is HIGHLY recommended "
                      "you make a boot floppy when asked. This will "
                      "guarantee you have a way to boot into the system "
                      "after installation.\n\n"
                      "Are you sure you want to proceed?"),
                     [ (_("Yes"), "yes") , (_("No"), "no") ], width = 50,
                     help = "lba32warning")

                if rc == "no":
                    return INSTALL_BACK
                else:
                    return INSTALL_OK
            else:
                rc = ButtonChoiceWindow(screen, _("Boot Partition Warning"),
                    _("You have put the partition containing the kernel (the "
                      "boot partition) above the 1024 cylinder limit. "
                      "It appears that this systems BIOS supports "
                      "booting from above this limit. \n\n"
                      "It is HIGHLY recommended you make a boot floppy when "
                      "asked by the installer, as this is a new feature in "
                      "recent motherboards and is not always reliable. "
                      "Making a boot disk will guarantee you can boot "
                      "your system once installed."),
                     [ (_("Ok"), "ok") ], width = 50,
                     help = "lba32warning")
        else:
            return INSTALL_NOOP
            
        


