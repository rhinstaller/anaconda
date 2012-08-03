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
import pyanaconda.partIntfHelpers as pih 
from pyanaconda import isys

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

# iSCSI Wizard classes and helpers

class GridEntry(object):
    def __init__(self, text, disabled=False, password=False, width=20):
        self.text = text
        self.disabled = disabled
        self.password = password
        self.width = width

class iSCSITextWizard(pih.iSCSIWizard):
    def __init__(self, screen):
        self.screen = screen
        self.entry_target_ip = None
        self.entry_initiator = None
        self.entry_disc_username = None
        self.entry_disc_password = None
        self.entry_disc_r_username = None
        self.entry_disc_r_password = None
        self.entry_login_username = None
        self.entry_login_password = None
        self.entry_login_r_username = None
        self.entry_login_r_password = None
        self.listbox_disc = None
        self.listbox_login = None
        self.listbox_nodes = None

    @staticmethod
    def _auth_entries(cred_type):
        all_entries = [
                GridEntry(_("CHAP Username:")),
                GridEntry(_("CHAP Password:"), password=True),
                GridEntry(_("Reverse CHAP Username:")),
                GridEntry(_("Reverse CHAP Password:"), password=True)
                ]

        entries = [None for i in range(4)]
        if cred_type == pih.CRED_ONE[0]:
            entries = all_entries[0:2] + [None for i in range(2)]
        elif cred_type == pih.CRED_BOTH[0]:
            entries = all_entries
        return entries

    @staticmethod
    def _build_grid(grid_entries):
        entries = []
        grid = Grid(2, len(grid_entries))
        for (i, ge) in enumerate(grid_entries):
            if ge:
                grid.setField(Label(ge.text), 0, i)
                entry = Entry(ge.width, password=ge.password)
                if ge.disabled:
                    entry.setFlags(FLAG_DISABLED, FLAGS_SET)
                grid.setField(entry, 1, i)
            else:
                entry = None
            # we want Nones in grid_entries result in Nones in return value
            entries.append(entry)
        return (grid, entries)

    @staticmethod
    def _value_when(entry):
        return entry.value() if entry else None
    
    def _discovery_auth_dialog(self):
        if self.listbox_disc.current() == pih.CRED_NONE[0]:
            # we need not collect anything
            return True

        grid = GridForm(self.screen, _("iSCSI Discovery Credentials"), 1, 3)
        grid.add(TextboxReflowed(50,
                                 _("Please enter the iSCSI "
                                   "discovery credentials.")),
                 0, 0)
        auth_entries = self._auth_entries(self.listbox_disc.current())
        (basic_grid, entries) = self._build_grid(auth_entries)
        (self.entry_disc_username,
         self.entry_disc_password,
         self.entry_disc_r_username,
         self.entry_disc_r_password) = entries
         
        grid.add(basic_grid, 0, 1, padding=(0, 1, 0, 1))

        grid.buttons = ButtonBar(self.screen, 
                                 [TEXT_OK_BUTTON,TEXT_CANCEL_BUTTON])
        grid.add(grid.buttons, 0, 2, padding=(0, 1, 0, -1))

        return self._run_grid(grid)

    def _discovery_setup_dialog(self, initiator, initiator_set):
        grid = GridForm(self.screen, _("iSCSI Discovery"), 1, 7)
        header_text = TextboxReflowed(60,
                                      _("To use iSCSI disks, you must provide "
                                        "the address of your iSCSI target and "
                                        "the iSCSI initiator name you've "
                                        "configured for your host."))
        grid.add(header_text, 0, 0)
        
        entry_list = [
            GridEntry(_("Target IP Address:"), width=40),
            GridEntry(_("iSCSI Initiator Name:"), 
                      disabled=initiator_set, 
                      width=40)
            ]
        (basic_grid, (self.entry_target_ip, self.entry_initiator)) = \
            self._build_grid(entry_list)
        self.entry_initiator.set(initiator)
        grid.add(basic_grid, 0, 1)

        grid.add(TextboxReflowed(60,
                                 _("What kind of iSCSI discovery "
                                   "authentication do you wish to perform:")), 
                 0, 2, padding=(0, 1, 0, 0))
        
        self.listbox_disc = Listbox(3, scroll=1)
        self.listbox_disc.append(*reversed(pih.CRED_NONE))
        self.listbox_disc.append(*reversed(pih.CRED_ONE))
        self.listbox_disc.append(*reversed(pih.CRED_BOTH))
        grid.add(self.listbox_disc, 0, 3)

        grid.add(TextboxReflowed(60,
                                 _("What kind of iSCSI login authentication "
                                   "do you wish to perform:")), 
                 0, 4, padding=(0, 1, 0, 0))

        self.listbox_login = Listbox(3, scroll=1)
        self.listbox_login.append(*reversed(pih.CRED_NONE))
        self.listbox_login.append(*reversed(pih.CRED_ONE))
        self.listbox_login.append(*reversed(pih.CRED_BOTH))
        self.listbox_login.append(*reversed(pih.CRED_REUSE))
        grid.add(self.listbox_login, 0, 5)

        grid.buttons = ButtonBar(self.screen,
                                 [TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON])
        grid.add(grid.buttons, 0, 6, padding=(0, 1, 0, -1))
        
        return self._run_grid(grid)

    def _run_grid(self, grid):
        result = grid.run()
        button = grid.buttons.buttonPressed(result)
        self.screen.popWindow()
        return bool(button == TEXT_OK_CHECK or result == "F12")

    def destroy_dialogs(self):
        pass

    def display_discovery_dialog(self, initiator, initiator_set):
        # this is in fact two dialogs here due to limited screen space in TUI
        return self._discovery_setup_dialog(initiator, initiator_set) and \
            self._discovery_auth_dialog()

    def display_login_dialog(self):
        # in TUI, the login credentials are asked for with nodes list, so this
        # should never stop us:
        return True

    def display_nodes_dialog(self, found_nodes, ifaces):
        grid_height = 4
        basic_grid = None
        if self.listbox_login.current() not in \
                (pih.CRED_NONE[0], pih.CRED_REUSE[0]):
            auth_entries = self._auth_entries(self.listbox_login.current())
            (basic_grid, entries) = self._build_grid(auth_entries)
            (self.entry_login_username,
             self.entry_login_password,
             self.entry_login_r_username,
             self.entry_login_r_password) = entries

            grid_height += 1

        grid = GridForm(self.screen, _("iSCSI Discovered Nodes"), 1, 5)
        grid.add(TextboxReflowed(50,
                                 _("Check the nodes you wish to log into:")),
                 0, 0)

        listbox = CheckboxTree(5, scroll=1)
        # unfortunately, Listbox.add won't accept node directly as the second
        # argument, we have to remember the list and use an index
        for i, node in enumerate(found_nodes):
            node_description = "%s via %s" % (node.name,
                                              ifaces.get(node.iface,
                                                         node.iface))
            listbox.append(node_description, i, selected=True)
        grid.add(listbox, 0, 1, padding=(0, 1, 0, 1))

        if basic_grid:
            grid.add(TextboxReflowed(60,
                                     _("Please enter iSCSI login credentials "
                                       "for the selected nodes:")),
                     0, 2)
            grid.add(basic_grid, 0, 3, padding=(0, 1, 0, 1))

        grid.buttons = ButtonBar(self.screen, 
                                 [TEXT_OK_BUTTON, TEXT_CANCEL_BUTTON])
        grid.add(grid.buttons, 0, 4, padding=(0, 0, 0, -1))

        rc = self._run_grid(grid)
        selected_nodes = [node for (i, node) in enumerate(found_nodes)
                          if i in listbox.getSelection()]
        return (rc, selected_nodes)

    def display_success_dialog(self, success_nodes, fail_nodes, fail_reason,
                               ifaces):
        buttons = [TEXT_OK_BUTTON]
        msg = _("Successfully logged into all the selected nodes.")
        msg_reason = _("Reason:")
        if fail_nodes:
            buttons.append(TEXT_RETRY_BUTTON)
            msg = _("Could not log into the following nodes:\n")
            msg = reduce(lambda s1, s2: "%s\n%s" % (s1, s2), fail_nodes, msg)
        if fail_reason:
            msg = "%s\n\n%s\n%s" % (msg, msg_reason, fail_reason)

        rc = ButtonChoiceWindow(self.screen,
                                _("iSCSI Login Results"),
                                msg,
                                buttons)
        return True if rc == TEXT_OK_CHECK else False

    def get_discovery_dict(self):

        dct = {
            'username' : self._value_when(self.entry_disc_username),
            'password' : self._value_when(self.entry_disc_password),
            'r_username' : self._value_when(self.entry_disc_r_username),
            'r_password' : self._value_when(self.entry_disc_r_password)
            }
        entered_ip = self.entry_target_ip.value()
        (ip, port) = pih.parse_ip(entered_ip)
        dct["ipaddr"] = ip
        dct["port"]   = port
        return dct

    def get_initiator(self):
        return self.entry_initiator.value()

    def get_login_dict(self):
        auth_kind = self.listbox_login.current()
        if auth_kind == pih.CRED_REUSE[0]:
            discovery_dict = self.get_discovery_dict()
            dct = dict((k,discovery_dict[k]) for k in discovery_dict if k in 
                       ['username', 
                        'password', 
                        'r_username', 
                        'r_password'])
        else:
            dct = {
                'username' : self._value_when(self.entry_login_username),
                'password' : self._value_when(self.entry_login_password),
                'r_username' : self._value_when(self.entry_login_r_username),
                'r_password' : self._value_when(self.entry_login_r_password)
                }

        return dct

    def set_initiator(self, initiator, initiator_set):
        pass

# general add drive stuff

class addDriveDialog(object):
    def __init__(self, anaconda):
        self.anaconda = anaconda

    def addDriveDialog(self, screen):
        newdrv = []
        if iscsi.has_iscsi():
            if iscsi.iscsi().mode == "none":
                newdrv.append("Add iSCSI target")
                newdrv.append("Add iSCSI target - use interface binding")
            elif iscsi.iscsi().mode == "bind":
                newdrv.append("Add iSCSI target - use interface binding")
            elif iscsi.iscsi().mode == "default":
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
            except ValueError as e:
                ButtonChoiceWindow(screen, _("Error"), str(e))
                return INSTALL_BACK
        elif newdrv[choice] == "Add FCoE SAN":
            try:
                return self.addFcoeDriveDialog(screen)
            except ValueError as e:
                ButtonChoiceWindow(screen, _("Error"), str(e))
                return INSTALL_BACK
        elif newdrv[choice].startswith("Add iSCSI target"):
            bind = newdrv[choice] == "Add iSCSI target - use interface binding"
            try:
                return self.addIscsiDriveDialog(screen, bind)
            except (ValueError, IOError) as e:
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
        devs = network.getDevices()
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
            hwaddr = isys.getMacAddress(dev)
            if hwaddr:
                desc = "%s - %.50s" % (dev, hwaddr)
            else:
                desc = dev

            interfaceList.append(desc, dev)

        interfaceList.setCurrent(devs[0])
        grid.add(interfaceList, 0, 1, padding = (0, 1, 0, 0))

        dcbCheckbox = Checkbox(_("Use DCB"), 1)
        grid.add(dcbCheckbox, 0, 2, anchorLeft = 1)
        autovlanCheckbox = Checkbox(_("Use auto vlan"), 1)
        grid.add(autovlanCheckbox, 0, 3, anchorLeft = 1)

        buttons = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON] )
        grid.add(buttons, 0, 4, anchorLeft = 1, growx = 1)

        result = grid.run()
        if buttons.buttonPressed(result) == TEXT_BACK_CHECK:
            screen.popWindow()
            return INSTALL_BACK

        nic = interfaceList.current()
        dcb = dcbCheckbox.selected()
        auto_vlan = autovlanCheckbox.selected()

        fcoe.fcoe().addSan(nic=nic, dcb=dcb, auto_vlan=auto_vlan,
                                   intf=self.anaconda.intf)

        screen.popWindow()
        return INSTALL_OK

    def addIscsiDriveDialog(self, screen, bind=False):
        if not network.hasActiveNetDev():
            ButtonChoiceWindow(screen, _("Error"),
                               "Must have a network configuration set up "
                               "for iSCSI config.  Please boot with "
                               "'linux asknetwork'")
            log.info("addIscsiDriveDialog(): early exit, network disabled.")
            return INSTALL_BACK

        # This will modify behaviour of iscsi.discovery() function
        if iscsi.iscsi().mode == "none" and not bind:
            iscsi.iscsi().delete_interfaces()
        elif (iscsi.iscsi().mode == "none" and bind) \
              or iscsi.iscsi().mode == "bind":
            active = set(network.getActiveNetDevs())
            created = set(iscsi.iscsi().ifaces.values())
            iscsi.iscsi().create_interfaces(active - created)

        wizard = iSCSITextWizard(screen)
        login_ok_nodes = pih.drive_iscsi_addition(self.anaconda, wizard)
        if len(login_ok_nodes):
            return INSTALL_OK
        log.info("addIscsiDriveDialog(): no new nodes added")
        return INSTALL_BACK
