from snack import *
from translate import _
import string
import isys
import iutil
from log import log
from flags import flags
from constants_text import *
import upgrade

class UpgradeSwapWindow:
    def __call__ (self, screen, intf, fsset, instPath, swapInfo):
	rc = swapInfo

	(fsList, suggSize, suggMntPoint) = rc

	text = _("The 2.4 kernel needs significantly more swap than older "
		 "kernels, as much as twice as much swap space as RAM on the "
		 "system. You currently have %dMB of swap configured, but "
		 "you may create additional swap space on one of your "
		 "file systems now.") % (iutil.swapAmount() / 1024)

	tb = TextboxReflowed(60, text)
	amount = Entry(10, scroll = 0)
	amount.set(str(suggSize))

	l = len(fsList)
	scroll = 0
	if l > 4:
	    l = 4
	    scroll = 1
	listbox = Listbox(l, scroll = scroll)

	liLabel = Label("%-25s %-15s %8s" % (_("Mount Point"), 
			_("Partition"), _("Free Space")))

	count = 0
	for (mnt, part, size) in fsList:
	    listbox.append("%-25s /dev/%-10s %6dMB" % (mnt, part, size), count)

	    if (mnt == suggMntPoint):
		listbox.setCurrent(count)

	    count = count + 1

	buttons = ButtonBar(screen, [TEXT_OK_BUTTON, (_("Skip"), "skip"),  
			    TEXT_BACK_BUTTON] )

	amGrid = Grid(2, 2)
	amGrid.setField(Label(_("Suggested size (MB):")), 0, 0, anchorLeft = 1,
			padding = (0, 0, 1, 0))
	amGrid.setField(Label(str(suggSize)), 1, 0, anchorLeft = 1)
	amGrid.setField(Label(_("Swap file size (MB):")), 0, 1, anchorLeft = 1,
			padding = (0, 0, 1, 0))
	amGrid.setField(amount, 1, 1)
	
	liGrid = Grid(1, 2)
	liGrid.setField(liLabel, 0, 0)
	liGrid.setField(listbox, 0, 1)

	g = GridFormHelp(screen, _("Add Swap"), "upgradeswap", 1, 4)
	g.add(tb, 0, 0, anchorLeft = 1, padding = (0, 0, 0, 1))
	g.add(amGrid, 0, 1, padding = (0, 0, 0, 1))
	g.add(liGrid, 0, 2, padding = (0, 0, 0, 1))
	g.add(buttons, 0, 3, anchorLeft = 1, growx = 1)

	while 1:
	    result = g.run()

	    if (buttons.buttonPressed(result)):
		result = buttons.buttonPressed(result)

	    if result == TEXT_BACK_CHECK:
		screen.popWindow()
		return INSTALL_BACK
	    elif result == "skip":
		screen.popWindow()
		return INSTALL_OK

	    val = amount.value()
            
	    try:
		val = int(val)
	    except ValueError:
		intf.messageWindow(_("Error"),
                                   _("The value you entered is not a "
                                     "valid number."))

	    if type(val) == type(1):
		(mnt, part, size) = fsList[listbox.current()]
		if size < (val + 16):
		    intf.messageWindow(_("Error"),
                                       _("There is not enough space on the "
                                         "device you selected for the swap "
                                         "partition."))
                elif val > 2000 or val < 1:
                    intf.messageWindow(_("Warning"), 
                                       _("The swap file must be between 1 "
                                         "and 2000 MB in size."))
		else:
		    screen.popWindow()
                    if flags.setupFilesystems:
                        # XXX fix me
                        # upgrade.createSwapFile(todo.instPath, todo.fstab,
                                               mnt, val)
		    return INSTALL_OK

	raise ValueError
	
class UpgradeExamineWindow:
    def __call__ (self, screen, dispatch, intf, id, chroot):
        self.parts = upgrade.findExistingRoots(intf, id, chroot)
        parts = upgrade.findExistingRoots (intf, id, chroot)

        if not parts:
            ButtonChoiceWindow(screen, _("Error"),
                               _("You don't have any Linux partitions. You "
                                 "can't upgrade this system!"),
                               [ TEXT_BACK_BUTTON ], width = 50)
            return INSTALL_BACK
        
        if len (parts) > 1:
            height = min (len (parts), 12)
            if height == 12:
                scroll = 1
            else:
                scroll = 0

	    partList = []
	    for (drive, fs) in parts:
		partList.append(drive)

            (button, choice) = \
                ListboxChoiceWindow(screen, _("System to Upgrade"),
                                    _("What partition holds the root partition "
                                      "of your installation?"), partList, 
                                    [ TEXT_OK_BUTTON, TEXT_BACK_BUTTON ], width = 30,
                                    scroll = scroll, height = height,
				    help = "multipleroot")
            if button == TEXT_BACK_CHECK:
                return INSTALL_BACK
            else:
                root = parts[choice]
        else:
            root = parts[0]
            (drive, fs) = root

            rc = ButtonChoiceWindow (screen, _("Upgrade Partition"),
                                     _("Upgrading the Red Hat Linux "
                                       "installation on partition "
                                       "/dev/%s") % (drive,),
                                     buttons = [ TEXT_OK_BUTTON,
                                                 TEXT_BACK_BUTTON ])
            if rc == TEXT_BACK_CHECK:
                return INSTALL_BACK
                
        id.upgradeRoot = root

        # if root is on vfat we want to always display boot floppy screen
        # otherwise they can't boot!
        # This check is required for upgradeonly installclass to work so
        # we only show boot floppy screen in partitonless install case
        # XXX WRONG PLACE TO DO THIS
        #if root[1] == "vfat":
        #    todo.instClass.removeFromSkipList("bootdisk")
        return INSTALL_OK

class CustomizeUpgradeWindow:
    def __call__ (self, screen, dispatch):
        rc = ButtonChoiceWindow (screen, _("Customize Packages to Upgrade"),
                                 _("The packages you have installed, "
                                   "and any other packages which are "
                                   "needed to satisfy their "
                                   "dependencies, have been selected "
                                   "for installation. Would you like "
                                   "to customize the set of packages "
                                   "that will be upgraded?"),
                                 buttons = [ _("Yes"), _("No"),
                                             TEXT_BACK_BUTTON],
                                 help = "custupgrade")

        if rc == TEXT_BACK_CHECK:
            return INSTALL_BACK

        if rc == string.lower (_("No")):
            dispatch.skipStep("indivpackage")
        else:
            dispatch.skipStep("indivpackage", skip = 0)            

        return INSTALL_OK

