from snack import *
from translate import _
import string
import isys
import iutil
from log import log
from constants_text import *
import upgrade

class UpgradeSwapWindow:
    def __call__ (self, dir, screen, todo):
	if dir == -1:
	    raise ValueError, "this can't happen"

	rc = upgrade.swapSuggestion(todo.instPath, todo.fstab)
	if not rc:
	    todo.upgradeFindPackages ()
	    return INSTALL_OK

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

	buttons = ButtonBar(screen, [(_("OK"), "ok"), (_("Skip"), "skip"),  
			     (_("Back"), "back") ] )

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

	    if result == "back":
		screen.popWindow()
		return INSTALL_BACK
	    elif result == "skip":
		todo.upgradeFindPackages ()
		screen.popWindow()
		return INSTALL_OK

	    val = amount.value()
            
	    try:
		val = int(val)
	    except ValueError:
		todo.intf.messageWindow(_("Error"),
		    _("The value you entered is not a valid number."))

	    if type(val) == type(1):
		(mnt, part, size) = fsList[listbox.current()]
		if size < (val + 16):
		    todo.intf.messageWindow(_("Error"),
			_("There is not enough space on the device you "
			  "selected for the swap partition."))
                elif val > 2000 or val < 1:
                    todo.intf.messageWindow(_("Warning"), 
                    _("The swap file must be between 1 and 2000 MB in size."))
		else:
		    screen.popWindow()
                    if todo.setupFilesystems:
                        upgrade.createSwapFile(todo.instPath, todo.fstab, mnt, val,
                                               todo.intf.progressWindow)
		    todo.upgradeFindPackages ()
		    return INSTALL_OK

	raise ValueError
	
class UpgradeExamineWindow:
    def __call__ (self, dir, screen, todo):
	if dir == -1:
            # msf dont go back!
            rc = ButtonChoiceWindow(screen, _("Proceed with upgrade?"),
                            _("The filesystems of the Linux installation "
                              "you have chosen to upgrade have already been "
                              "mounted. You cannot go back past this point. "
                              "\n\n") +
                              _("If you would like to exit the upgrade select "
                              "Exit, or choose Ok to continue with the "
                              "upgrade."),
                               [ _("Ok"), _("Exit") ], width = 50)

            if rc == 'ok':
                return INSTALL_OK
            else:
                import sys
                sys.exit(0)
           
	    # Hack to let backing out of upgrades work properly
	    from fstab import NewtFstab
	    if todo.fstab:
		todo.fstab.turnOffSwap()
	    todo.fstab = NewtFstab(todo.setupFilesystems, 
                                   todo.serial, 0, 0,
                                   todo.intf.waitWindow,
                                   todo.intf.messageWindow,
                                   todo.intf.progressWindow,
                                   not todo.expert,
                                   todo.method.protectedPartitions(),
                                   todo.expert, 1)

	    return INSTALL_NOOP

        parts = todo.upgradeFindRoot ()

        if not parts:
            ButtonChoiceWindow(screen, _("Error"),
                               _("You don't have any Linux partitions. You "
                                 "can't upgrade this system!"),
                               [ _("Back") ], width = 50)
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
                                    [ _("OK"), _("Back") ], width = 30,
                                    scroll = scroll, height = height,
				    help = "multipleroot")
            if button == string.lower (_("Back")):
                return INSTALL_BACK
            else:
                root = parts[choice]
        else:
            root = parts[0]
            (drive, fs) = root

            # terrible hack - need to fix in future
            # if we're skipping confirm upgrade window, we must be in
            # upgradeonly mode, so don't display this window either
            if not todo.instClass.skipStep('confirm-upgrade'):
                rc = ButtonChoiceWindow (screen, _("Upgrade Partition"),
                                         _("Upgrading the Red Hat Linux installation on partition /dev/") + drive,
                                         buttons = [ _("Ok"), _("Back") ])
                if rc  == string.lower (_("Back")):
                    return INSTALL_BACK

        todo.upgradeMountFilesystems (root)

class CustomizeUpgradeWindow:
    def __call__ (self, screen, todo, indiv):
        rc = ButtonChoiceWindow (screen, _("Customize Packages to Upgrade"),
                                 _("The packages you have installed, "
                                   "and any other packages which are "
                                   "needed to satisfy their "
                                   "dependencies, have been selected "
                                   "for installation. Would you like "
                                   "to customize the set of packages "
                                   "that will be upgraded?"),
                                 buttons = [ _("Yes"), _("No"), _("Back") ],
				help = "custupgrade")

        if rc == string.lower (_("Back")):
            return INSTALL_BACK

        if rc == string.lower (_("No")):
            indiv.set (0)
        else:
            indiv.set (1)

        return INSTALL_OK

