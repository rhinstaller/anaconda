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

from pyanaconda import isys
from pyanaconda import iutil
from pyanaconda import upgrade
from constants_text import *
from snack import *
from pyanaconda.flags import flags
from pyanaconda.constants import *
from pyanaconda.storage.formats import getFormat
from pyanaconda.storage.deviceaction import ActionMigrateFormat

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

	while True:
	    result = g.run()

	    if (buttons.buttonPressed(result)):
		result = buttons.buttonPressed(result)

	    if result == TEXT_BACK_CHECK:
		screen.popWindow()
		return INSTALL_BACK

            # Cancel any previously scheduled migrate actions first.
            for entry in partlist.getSelection():
                actions = anaconda.storage.devicetree.findActions(device=entry[1],
                                                                  type="migrate")
                if not actions:
                    continue

                for action in actions:
                    anaconda.storage.devicetree.cancelAction(action)

            # Then schedule an action for whatever rows were selected.
            for entry in partlist.getSelection():
                newfs = getFormat(entry[1].format.migrationTarget)
                if not newfs:
                    log.warning("failed to get new filesystem type (%s)"
                                % entry[1].format.migrationTarget)
                    continue

                action = ActionMigrateFormat(entry[1])
                anaconda.storage.devicetree.registerAction(action)

            screen.popWindow()
            return INSTALL_OK

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

        default = 1

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
        else:
            anaconda.upgradeRoot = None

        seenExamineScreen = True
        return INSTALL_OK
