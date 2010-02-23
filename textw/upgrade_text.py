#
# upgrade_text.py: text mode upgrade dialogs
#
# Copyright (C) 2001  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import isys
import iutil
import upgrade
from constants_text import *
from snack import *
from flags import flags
from constants import *
from storage.formats import getFormat

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

seenExamineScreen = False

class UpgradeMigrateFSWindow:
    def __call__ (self, screen, anaconda):
      
        migent = anaconda.storage.migratableDevices

	g = GridFormHelp(screen, _("Migrate File Systems"), "upmigfs", 1, 4)

	text = (_("This release of %(productName)s supports "
                 "an updated file system, which has several "
                 "benefits over the file system traditionally shipped "
                 "in %(productName)s.  This installation program can migrate "
                 "formatted partitions without data loss.\n\n"
                 "Which of these partitions would you like to migrate?") %
                  {'productName': productName})

	tb = TextboxReflowed(60, text)
	g.add(tb, 0, 0, anchorLeft = 1, padding = (0, 0, 0, 1))

        partlist = CheckboxTree(height=4, scroll=1)
        for device in migent:
            if not device.format.exists:
                migrating = True
            else:
                migrating = False

            # FIXME: the fstype at least will be wrong here
            partlist.append("%s - %s - %s" % (device.path,
                                              device.format.type,
                                              device.format.mountpoint),
                                              device, migrating)
            
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
            # XXX the way to do this is by scheduling and cancelling actions
            #for entry in migent:
            #    entry.setFormat(0)
            #    entry.setMigrate(0)
            #    entry.fsystem = entry.origfsystem

            for entry in partlist.getSelection():
                try:
                    newfs = getFormat(entry.format.migratetofs[0])
                except Exception, e:
                    log.info("failed to get new filesystem type, defaulting to ext3: %s" %(e,))
                    newfs = getFormat("ext3")
                    anaconda.storage.migrateFormat(entry, newfs)

            screen.popWindow()
            return INSTALL_OK

class UpgradeSwapWindow:
    def __call__ (self, screen, anaconda):
	(fsList, suggSize, suggDev) = anaconda.upgradeSwapInfo

        ramDetected = iutil.memInstalled()/1024

	text = _("Recent kernels (2.4 or newer) need significantly more swap than older "
		 "kernels, up to twice the amount of RAM on the "
		 "system.  You currently have %dMB of swap configured, but "
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
	for (device, size) in fsList:
	    listbox.append("%-25s %-15s %6dMB" % (device.format.mountpoint,
                                                  device.path,
                                                  size),
                                                  count)

	    if (device == suggDev):
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
		(dev, size) = fsList[listbox.current()]
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
                    anaconda.storage.createSwapFile(dev, val)
                    anaconda.dispatch.skipStep("addswap", 1)
		    return INSTALL_OK

	raise ValueError
	
class UpgradeExamineWindow:
    def __call__ (self, screen, anaconda):
        parts = anaconda.rootParts

        height = min(len(parts), 11) + 1
        if height == 12:
            scroll = 1
        else:
            scroll = 0
        partList = []
        partList.append(_("Reinstall System"))

        global seenExamineScreen

	if (not seenExamineScreen and anaconda.dispatch.stepInSkipList("installtype")) or anaconda.upgrade:
            default = 1
        else:
            default = 0

        for (device, desc) in parts:
            partList.append("%s (%s)" %(desc, device.path))

        (button, choice) =  ListboxChoiceWindow(screen, _("System to Upgrade"),
                            _("There seem to be one or more existing Linux installations "
                              "on your system.\n\nPlease choose one to upgrade, "
			      "or select 'Reinstall System' to freshly install "
			      "your system."), partList,
                                                [ TEXT_OK_BUTTON,
                                                  TEXT_BACK_BUTTON ],
                                                width = 55, scroll = scroll,
                                                height = height,
                                                default = default,
                                                help = "upgraderoot")

        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK
        else:
            if choice == 0:
                root = None
            else:
                root = parts[choice - 1]

        if root is not None:
            upgrade.setSteps(anaconda)
            anaconda.upgrade = True

            anaconda.upgradeRoot = [(root[0], root[1])]
            anaconda.rootParts = parts
            anaconda.dispatch.skipStep("installtype", skip = 1)
        else:
            anaconda.dispatch.skipStep("installtype", skip = 0)
            anaconda.upgradeRoot = None

        seenExamineScreen = True
        return INSTALL_OK
