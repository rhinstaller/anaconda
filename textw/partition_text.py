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
import isys
import string
import copy
import network
import parted
from partIntfHelpers import *
from snack import *
from constants_text import *
from constants import *

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

        while 1:
            g = GridFormHelp(screen, _("Partitioning Type"), "autopart", 1, 6)

            txt = TextboxReflowed(65, _("Installation requires partitioning of your hard drive.  The default layout is suitable for most users.  Select what space to use and which drives to use as the install target."))
            g.add(txt, 0, 0, (0, 0, 0, 0))

            opts = ((_("Use entire drive"), CLEARPART_TYPE_ALL),
                    (_("Replace existing Linux system"), CLEARPART_TYPE_LINUX),
                    (_("Use free space"), CLEARPART_TYPE_NONE))
            typebox = Listbox(height = len(opts), scroll = 0)
            for (txt, val) in opts:
                typebox.append(txt, val)

            if anaconda.storage.clearPartType is None:
                preselection = CLEARPART_TYPE_LINUX
            else:
                preselection = anaconda.storage.clearPartType
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
            disks = anaconda.storage.partitioned
            cleardrives = anaconda.storage.clearPartDisks

            for disk in disks:
                model = disk.model

                if not cleardrives or len(cleardrives) < 1:
                    selected = 1
                else:
                    if disk in cleardrives:
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
                if self.addDriveDialog(screen) != INSTALL_BACK:
                    anaconda.storage.reset()
                    anaconda.bootloader.updateDriveList()
                continue

            if res == TEXT_BACK_CHECK:
                return INSTALL_BACK

            if anaconda.storage.checkNoDisks():
                continue

            if len(sel) < 1:
                mustHaveSelectedDrive(anaconda.intf)
                continue

            anaconda.dispatch.skipStep("autopartitionexecute", skip = 0)
            anaconda.storage.doAutoPart = True
            anaconda.storage.clearPartType = partmethod_ans
            anaconda.storage.clearPartDisks = sel
            break

        # ask to review autopartition layout - but only if it's not custom partitioning
        anaconda.dispatch.skipStep("partition", skip = 1)
        anaconda.dispatch.skipStep("bootloader", skip = 1)

        return INSTALL_OK

    def addDriveDialog(self, screen):
        newdrv = []
        from storage import iscsi
        if iscsi.has_iscsi():
            newdrv.append("Add iSCSI target")
        if iutil.isS390():
            newdrv.append( "Add zFCP LUN" )
        from storage import fcoe
        if fcoe.has_fcoe():
            newdrv.append("Add FCoE SAN")

        if len(newdrv) == 0:
            return INSTALL_BACK

        (button, choice) = ListboxChoiceWindow(screen,
                                   _("Advanced Storage Options"),
                                   _("How would you like to modify "
                                     "your drive configuration?"),
                                   newdrv,
                                   [ TEXT_OK_BUTTON, TEXT_BACK_BUTTON],
                                               width=55, height=3)
        
        if button == TEXT_BACK_CHECK:
            return INSTALL_BACK
        if newdrv[choice] == "Add zFCP LUN":
            try:
                return self.addZFCPDriveDialog(screen)
            except ValueError, e:
                ButtonChoiceWindow(screen, _("Error"), str(e))
                return INSTALL_BACK
        elif newdrv[choice] == "Add FCoE SAN":
            try:
                return self.addFcoeDriveDialog(screen)
            except ValueError, e:
                ButtonChoiceWindow(screen, _("Error"), str(e))
                return INSTALL_BACK
        else:
            try:
                return self.addIscsiDriveDialog(screen)
            except (ValueError, IOError), e:
                ButtonChoiceWindow(screen, _("Error"), str(e))
                return INSTALL_BACK

    def addZFCPDriveDialog(self, screen):
        (button, entries) = EntryWindow(screen,
                                        _("Add FCP Device"),
                                        _("zSeries machines can access industry-standard SCSI devices via Fibre Channel (FCP). You need to provide a 16 bit device number, a 64 bit World Wide Port Name (WWPN), and a 64 bit FCP LUN for each device."),
                                        prompts = [ "Device number",
                                                    "WWPN",
                                                    "FCP LUN" ] )
        if button == TEXT_CANCEL_CHECK:
            return INSTALL_BACK

        devnum = entries[0].strip()
        wwpn = entries[1].strip()
        fcplun = entries[2].strip()
        try:
            self.anaconda.storage.zfcp.addFCP(devnum, wwpn, fcplun)
        except ValueError, e:
            log.warn(str(e)) # alternatively popup error dialog instead
                                        
        return INSTALL_OK

    def addFcoeDriveDialog(self, screen):
        netdevs = self.anaconda.network.available()
        devs = netdevs.keys()
        devs.sort()

        if not devs:
            ButtonChoiceWindow(screen, _("Error"),
                               _("No network cards present."))
            return INSTALL_BACK

        grid = GridFormHelp(screen, _("Add FCoE SAN"), "fcoeconfig",
                            1, 4)

        tb = TextboxReflowed(60,
                        _("Select which NIC is connected to the FCoE SAN."))
        grid.add(tb, 0, 0, anchorLeft = 1, padding = (0, 0, 0, 1))

        interfaceList = Listbox(height=len(devs), scroll=1)
        for dev in devs:
            hwaddr = netdevs[dev].get("HWADDR")
            if hwaddr:
                desc = "%s - %.50s" % (dev, hwaddr)
            else:
                desc = dev

            interfaceList.append(desc, dev)

        interfaceList.setCurrent(devs[0])
        grid.add(interfaceList, 0, 1, padding = (0, 1, 0, 0))

        dcbCheckbox = Checkbox(_("Use DCB"), 1)
        grid.add(dcbCheckbox, 0, 2, anchorLeft = 1)

        buttons = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON] )
        grid.add(buttons, 0, 3, anchorLeft = 1, growx = 1)

        result = grid.run()
        if buttons.buttonPressed(result) == TEXT_BACK_CHECK:
            screen.popWindow()
            return INSTALL_BACK

        nic = interfaceList.current()
        dcb = dcbCheckbox.selected()

        self.anaconda.storage.fcoe.addSan(nic=nic, dcb=dcb,
                                          intf=self.anaconda.intf)

        screen.popWindow()
        return INSTALL_OK

    def addIscsiDriveDialog(self, screen):
        if not network.hasActiveNetDev():
            ButtonChoiceWindow(screen, _("Error"),
                               "Must have a network configuration set up "
                               "for iSCSI config.  Please boot with "
                               "'linux asknetwork'")
            return INSTALL_BACK
        
        (button, entries) = EntryWindow(screen,
                                        _("Configure iSCSI Parameters"),
                                        _("To use iSCSI disks, you must provide the address of your iSCSI target and the iSCSI initiator name you've configured for your host."),
                                        prompts = [ _("Target IP Address"),
                                                    _("iSCSI Initiator Name"),
                                                    _("CHAP username"),
                                                    _("CHAP password"),
                                                    _("Reverse CHAP username"),
                                                    _("Reverse CHAP password") ])
        if button == TEXT_CANCEL_CHECK:
            return INSTALL_BACK

        (user, pw, user_in, pw_in) = entries[2:]

        target = entries[0].strip()
        try:
            count = len(target.split(":"))
            idx = target.rfind("]:")
            # Check for IPV6 [IPV6-ip]:port
            if idx != -1:
                ip = target[1:idx]
                port = target[idx+2:]
            # Check for IPV4 aaa.bbb.ccc.ddd:port
            elif count == 2:
                idx = target.rfind(":")
                ip = target[:idx]
                port = target[idx+1:]
            else:
                ip = target
                port = "3260"
            network.sanityCheckIPString(ip)
        except network.IPMissing, msg:
            raise ValueError, msg
        except network.IPError, msg:
            raise ValueError, msg

        iname = entries[1].strip()
        if not self.anaconda.storage.iscsi.initiatorSet:
            self.anaconda.storage.iscsi.initiator = iname
        self.anaconda.storage.iscsi.addTarget(ip, port, user, pw,
                                              user_in, pw_in)
                                        
        return INSTALL_OK
