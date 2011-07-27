#
# partition_text.py: allows the user to choose how to partition their disks
# in text mode
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
# All rights reserved.
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
# Author(s): Jeremy Katz <katzj@redhat.com>
#

import os, sys
from pyanaconda import isys
import copy
from pyanaconda import network
import parted
from pyanaconda.partIntfHelpers import *
from snack import *
from constants_text import *
from pyanaconda.constants import *
from add_drive_text import addDriveDialog

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class PartitionTypeWindow:
    def typeboxChange(self, (typebox, drivelist)):
        flag = FLAGS_RESET
        if typebox.current() == CLEARPART_TYPE_NONE:
            flag = FLAGS_SET
        # XXX need a way to disable the checkbox tree

    def clearDrivelist(self):
        # XXX remove parted object refs
        #     need to put in clear() method for checkboxtree in snack
        self.drivelist.key2item = {}
        self.drivelist.item2key = {}

    def __call__(self, screen, anaconda):
        self.anaconda = anaconda

        while True:
            g = GridFormHelp(screen, _("Partitioning Type"), "autopart", 1, 6)

            txt = TextboxReflowed(65, _("Installation requires partitioning of your hard drive.  The default layout is suitable for most users.  Select what space to use and which drives to use as the install target."))
            g.add(txt, 0, 0, (0, 0, 0, 0))

            opts = ((_("Use entire drive"), CLEARPART_TYPE_ALL),
                    (_("Replace existing Linux system"), CLEARPART_TYPE_LINUX),
                    (_("Use free space"), CLEARPART_TYPE_NONE))
            typebox = Listbox(height = len(opts), scroll = 0)
            for (txt, val) in opts:
                typebox.append(txt, val)

            if anaconda.storage.config.clearPartType is None:
                preselection = CLEARPART_TYPE_LINUX
            else:
                preselection = anaconda.storage.config.clearPartType
            typebox.setCurrent(preselection)

            g.add(typebox, 0, 1, (0, 1, 0, 0))

            # list of drives to select which to clear
            subgrid = Grid(1, 2)
            subgrid.setField(TextboxReflowed(55, _("Which drive(s) do you want to "
                                                   "use for this installation?")),
                             0, 0)
            drivelist = CheckboxTree(height=2, scroll=1)
            subgrid.setField(drivelist, 0, 1)
            g.add(subgrid, 0, 2, (0, 1, 0, 0))

            bb = ButtonBar(screen, [ TEXT_OK_BUTTON, TEXT_BACK_BUTTON ])
            g.add(bb, 0, 5, (0,1,0,0))


            typebox.setCallback(self.typeboxChange, (typebox, drivelist))
            self.drivelist = drivelist

            g.addHotKey("F2")
            screen.pushHelpLine (_("<Space>,<+>,<-> selection   |   <F2> Add drive   |   <F12> next screen"))

            # restore the drive list each time
            disks = filter(lambda d: not d.format.hidden, anaconda.storage.disks)
            cleardrives = anaconda.storage.config.clearPartDisks

            for disk in disks:
                model = disk.model

                if not cleardrives or len(cleardrives) < 1:
                    selected = 1
                else:
                    if disk.name in cleardrives:
                        selected = 1
                    else:
                        selected = 0

                sizestr = "%8.0f MB" % (disk.size,)
                diskdesc = "%6s %s (%s)" % (disk.name, sizestr, model[:23],)

                drivelist.append(diskdesc, selected = selected)

            rc = g.run()

            if len(self.drivelist.getSelection()) > 0:
                sel = map(lambda s: s.split()[0], self.drivelist.getSelection())
            else:
                sel = []
            partmethod_ans = typebox.current()
            res = bb.buttonPressed(rc)

            self.clearDrivelist()
            screen.popHelpLine()
            screen.popWindow()

            if rc == "F2":
                addDialog = addDriveDialog(anaconda)
                if addDialog.addDriveDialog(screen) != INSTALL_BACK:
                    anaconda.storage.reset()
                continue

            if res == TEXT_BACK_CHECK:
                return INSTALL_BACK

            if anaconda.storage.checkNoDisks():
                continue

            if len(sel) < 1:
                mustHaveSelectedDrive(anaconda.intf)
                continue

            anaconda.dispatch.request_steps("autopartitionexecute")
            anaconda.storage.doAutoPart = True
            anaconda.storage.config.clearPartType = partmethod_ans
            anaconda.storage.config.clearPartDisks = sel
            break

        anaconda.dispatch.skip_steps("bootloader")

        return INSTALL_OK


