#
# Copyright (C) 2010  Red Hat, Inc.  All rights reserved.
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

from pyanaconda import iutil
from pyanaconda import network
from pyanaconda.storage import iscsi
from pyanaconda.storage import fcoe
from pyanaconda.storage import zfcp
from snack import *
from constants_text import *
from pyanaconda.constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class addDriveDialog(object):
    def __init__(self, anaconda):
        self.anaconda = anaconda

    def addDriveDialog(self, screen):
        newdrv = []
        if iscsi.has_iscsi():
            newdrv.append("Add iSCSI target")
        if iutil.isS390():
            newdrv.append( "Add zFCP LUN" )
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

        # This may throw a value error, which gets handled by addDriveDialog()
        zfcp.ZFCP().addFCP(devnum, wwpn, fcplun)

        return INSTALL_OK

    def addFcoeDriveDialog(self, screen):
        netdevs = self.anaconda.network.netdevices
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

        fcoe.fcoe().addSan(nic=nic, dcb=dcb,
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
        
        iname = iscsi.iscsi().initiator
        (button, entries) = EntryWindow(screen,
                                        _("Configure iSCSI Parameters"),
                                        _("To use iSCSI disks, you must provide the address of your iSCSI target and the iSCSI initiator name you've configured for your host."),
                                        prompts = [ _("Target IP Address"),
                                                    (_("iSCSI Initiator Name"),
                                                     iname),
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
        iscsi.iscsi().initiator = iname
        iscsi.iscsi().addTarget(ip, port, user, pw, user_in, pw_in,
                                        intf=self.anaconda.intf)

        return INSTALL_OK
