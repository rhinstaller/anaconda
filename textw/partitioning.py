import gettext
import iutil
import os
from snack import *
from textw.constants import *
from newtpyfsedit import fsedit        

cat = gettext.Catalog ("anaconda", "/usr/share/locale")
_ = cat.gettext

class PartitionMethod:
    def __call__(self, screen, todo):
	if not todo.expert or todo.instClass.partitions:
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
	      (_("Back"), "back") ], width = 50)

	if rc == "back":
	    return INSTALL_BACK
	elif rc == "dd":
	    todo.skipFdisk = 1
	else:
	    todo.skipFdisk = 0

	return INSTALL_OK

class ManualPartitionWindow:
    def __call__(self, screen, todo):
	if todo.skipFdisk: return INSTALL_NOOP
	
	drives = todo.drives.available ()
	driveNames = drives.keys()
	driveNames.sort ()

	choices = []
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
		  (_("Back"), "back") ], width = 50)

	    if button != "done" and button != "back":
		device = driveNames[choice]
		screen.suspend ()
		if os.access("/sbin/fdisk", os.X_OK):
		    path = "/sbin/fdisk"
		else:
		    path = "/usr/sbin/fdisk"
		iutil.execWithRedirect (path, [ path, "/tmp/" + device ])
		screen.resume ()

	if button == "back":
	    return INSTALL_BACK

	return INSTALL_OK


class AutoPartitionWindow:
    def __call__(self, screen, todo):
        fstab = []
        for mntpoint, (dev, fstype, reformat) in todo.mounts.items ():
            fstab.append ((dev, mntpoint))

        if not todo.ddruid:
            drives = todo.drives.available ().keys ()
            drives.sort ()
            todo.ddruid = fsedit(0, drives, fstab, todo.zeroMbr)

	todo.instClass.finishPartitioning(todo.ddruid)

	if not todo.getPartitionWarningText(): 
	    return INSTALL_NOOP

	(rc, choice) = ListboxChoiceWindow(screen, _("Automatic Partitioning"),
	    _("%s\n\nIf you don't want to do this, you can continue with "
	      "this install by partitioning manually, or you can go back "
	      "and perform a fully customized installation.") % 
		    (todo.getPartitionWarningText(), ),
	    [_("Continue"), _("Manually partition")], 
	    buttons = basicButtons, default = _("Continue"))

	if (rc == "back"): return INSTALL_BACK

        if (choice == 1):
            todo.ddruid = fsedit(0, drives, fstab)
	    todo.manuallyPartition()

class PartitionWindow:
    def __call__(self, screen, todo):
	dir = INSTALL_NOOP
	if not todo.getSkipPartitioning():
	    dir = todo.ddruid.edit ()

	for partition, mount, fstype, size in todo.ddruid.getFstab ():
	    todo.addMount(partition, mount, fstype)

        return dir

class TurnOnSwapWindow:

    beenTurnedOn = 0

    def __call__(self, screen, todo):
	if self.beenTurnedOn or (iutil.memInstalled() > 30000):
	    return INSTALL_NOOP

	rc = ButtonChoiceWindow(screen, _("Low Memory"),
		   _("As you don't have much memory in this machine, we "
		     "need to turn on swap space immediately. To do this "
		     "we'll have to write your new partition table to the "
		     "disk immediately. Is that okay?"),
		   [ (_("Yes"), "yes"), (_("No"), "back") ], width = 50)

	if (rc == "back"):
	    return INSTALL_BACK

	todo.ddruid.save ()
	todo.makeFilesystems (createFs = 0)
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

        height = min (screen.height - 12, len (todo.mounts.items()))
        
        ct = CheckboxTree(height = height)

        mounts = todo.mounts.keys ()
        mounts.sort ()

        for mount in mounts:
            (dev, fstype, format) = todo.mounts[mount]
            if fstype == "ext2":
                ct.append("/dev/%s   %s" % (dev, mount), mount, format)

        cb = Checkbox (_("Check for bad blocks during format"))

        bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))

        g = GridForm (screen, _("Choose Partitions to Format"), 1, 4)
        g.add (tb, 0, 0, (0, 0, 0, 1))
        g.add (ct, 0, 1)
        g.add (cb, 0, 2, (0, 0, 0, 1))
        g.add (bb, 0, 3, growx = 1)

        result = g.runOnce()

        for mount in todo.mounts.keys ():
            (dev, fstype, format) = todo.mounts[mount]
            if fstype == "ext2":
                todo.mounts[mount] = (dev, fstype, 0)

        for mount in ct.getSelection():
            (dev, fstype, format) = todo.mounts[mount]
            todo.mounts[mount] = (dev, fstype, 1)

        todo.badBlockCheck = cb.selected ()

        rc = bb.buttonPressed (result)

        if rc == "back":
            return INSTALL_BACK
        return INSTALL_OK

