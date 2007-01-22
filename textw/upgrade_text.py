#
# upgrade_text.py: text mode upgrade dialogs
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

import string
import isys
import iutil
import upgrade
from constants_text import *
from snack import *
from fsset import *
from flags import flags
from constants import *
import upgradeclass
UpgradeClass = upgradeclass.InstallClass

from rhpl.translate import _
import rhpl

class UpgradeMigrateFSWindow:
    def __call__ (self, screen, anaconda):
      
        migent = anaconda.id.fsset.getMigratableEntries()

	g = GridFormHelp(screen, _("Migrate File Systems"), "upmigfs", 1, 4)

	text = _("This release of %s supports "
                 "the ext3 journalling file system.  It has several "
                 "benefits over the ext2 file system traditionally shipped "
                 "in %s.  It is possible to migrate the ext2 "
                 "formatted partitions to ext3 without data loss.\n\n"
                 "Which of these partitions would you like to migrate?"
                 % (productName, productName))

	tb = TextboxReflowed(60, text)
	g.add(tb, 0, 0, anchorLeft = 1, padding = (0, 0, 0, 1))

        partlist = CheckboxTree(height=4, scroll=1)
        for entry in migent:
            if rhpl.getArch() == "ia64" \
                    and entry.getMountPoint() == "/boot/efi":
                continue
            if entry.fsystem.getName() != entry.origfsystem.getName():
                migrating = 1
            else:
                migrating = 0

            partlist.append("/dev/%s - %s - %s" % (entry.device.getDevice(),
                                              entry.origfsystem.getName(),
                                              entry.mountpoint), entry, migrating)
            
	g.add(partlist, 0, 1, padding = (0, 0, 0, 1))
        
	buttons = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON] )
	g.add(buttons, 0, 3, anchorLeft = 1, growx = 1)

	while 1:
	    result = g.run()
        
	    if (buttons.buttonPressed(result)):
		result = buttons.buttonPressed(result)

	    if result == TEXT_BACK_CHECK:
		screen.popWindow()
		return INSTALL_BACK

            # reset
            for entry in migent:
                if rhpl.getArch() == "ia64" \
                        and entry.getMountPoint() == "/boot/efi":
                    continue
                entry.setFormat(0)
                entry.setMigrate(0)
                entry.fsystem = entry.origfsystem

            for entry in partlist.getSelection():
                entry.setMigrate(1)
                entry.fsystem = fileSystemTypeGet("ext3")

            screen.popWindow()
            return INSTALL_OK

class UpgradeSwapWindow:
    def __call__ (self, screen, anaconda):
	(fsList, suggSize, suggMntPoint) = anaconda.id.upgradeSwapInfo

        ramDetected = iutil.memInstalled()/1024

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

	amGrid = Grid(2, 3)
	amGrid.setField(Label(_("RAM detected (MB):")), 0, 0, anchorLeft = 1,
			padding = (0, 0, 1, 0))
	amGrid.setField(Label(str(ramDetected)), 1, 0, anchorLeft = 1)
	amGrid.setField(Label(_("Suggested size (MB):")), 0, 1, anchorLeft = 1,
			padding = (0, 0, 1, 0))
	amGrid.setField(Label(str(suggSize)), 1, 1, anchorLeft = 1)
	amGrid.setField(Label(_("Swap file size (MB):")), 0, 2, anchorLeft = 1,
			padding = (0, 0, 1, 0))
	amGrid.setField(amount, 1, 2)
	
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
		anaconda.intf.messageWindow(_("Error"),
                                   _("The value you entered is not a "
                                     "valid number."))

	    if type(val) == type(1):
		(mnt, part, size) = fsList[listbox.current()]
		if size < (val + 16):
		    anaconda.intf.messageWindow(_("Error"),
                                       _("There is not enough space on the "
                                         "device you selected for the swap "
                                         "partition."))
                elif val > 2000 or val < 1:
                    anaconda.intf.messageWindow(_("Warning"), 
                                       _("The swap file must be between 1 "
                                         "and 2000 MB in size."))
		else:
		    screen.popWindow()
                    if flags.setupFilesystems:
                        upgrade.createSwapFile(anaconda.rootPath, anaconda.id.fsset, mnt, val)
                    anaconda.dispatch.skipStep("addswap", 1)
		    return INSTALL_OK

	raise ValueError
	
class UpgradeExamineWindow:
    def __call__ (self, screen, anaconda):
        parts = anaconda.id.rootParts

        height = min(len(parts), 11) + 1
        if height == 12:
            scroll = 1
        else:
            scroll = 0
        partList = []
        partList.append(_("Reinstall System"))

        for (drive, fs, desc, label) in parts:
	    if drive[:5] != "/dev/":
		devname = "/dev/" + drive
	    else:
		devname = drive
            partList.append("%s (%s)" %(desc, drive))

        (button, choice) =  ListboxChoiceWindow(screen, _("System to Upgrade"),
                            _("One or more existing Linux installations "
			      "have been found "
                              "on your system.\n\nPlease choose one to upgrade, "
			      "or select 'Reinstall System' to freshly install "
			      "your system."), partList,
                                                [ TEXT_OK_BUTTON,
                                                  TEXT_BACK_BUTTON ],
                                                width = 55, scroll = scroll,
                                                height = height,
                                                help = "upgraderoot")

        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK
        else:
            if choice == 0:
                root = None
            else:
                root = parts[choice - 1]

        if root is not None:
            c = UpgradeClass(flags.expert)
            # hack, hack, hack...
            c.installkey = anaconda.id.instClass.installkey
            c.repopaths = anaconda.id.instClass.repopaths
            c.setSteps(anaconda.dispatch)
            c.setInstallData(anaconda)

            anaconda.id.upgradeRoot = [(root[0], root[1])]
            anaconda.id.rootParts = parts
            anaconda.dispatch.skipStep("installtype", skip = 1)
        else:
            anaconda.dispatch.skipStep("installtype", skip = 0)
            anaconda.id.upgradeRoot = None

        return INSTALL_OK
