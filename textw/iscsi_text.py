#
# iscs_text.py: iscsi text dialog
#
# Copyright 2006 IBM, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import isys
from network import sanityCheckIPString
from snack import *
from constants import *
from constants_text import *
from rhpl.translate import _

class iscsiWindow:
    def __call__(self, screen, anaconda):
        self.iscsi = anaconda.id.iscsi

        # We have 3 values of interest: target IP address, port and
        # initiator name.
        #
        # Create a Grid that is 2 columns (label and value) by 3 rows in
        # size.
        grid = Grid(2, 3)

        row = 0
        self.ip_entry = Entry (16)
        self.ip_entry.set(self.iscsi.ipaddr)
        grid.setField(Label(_("Target IP address:")), 0, row, anchorLeft = 1)
        grid.setField(self.ip_entry, 1, row, anchorLeft = 1,
                      padding = (1, 0, 0, 0))

        row += 1
        self.port_entry = Entry(16)
        self.port_entry.set(self.iscsi.port)
        grid.setField(Label(_("Port Number:")), 0, row, anchorLeft = 1)
        grid.setField(self.port_entry, 1, row, anchorLeft = 1,
                      padding = (1, 0, 0, 0))

        row +=1
        self.initiator_entry = Entry(32)
        self.initiator_entry.set(self.iscsi.initiator)
        grid.setField(Label(_("iSCSI Initiator Name:")), 0, row, anchorLeft = 1)
        grid.setField(self.initiator_entry, 1, row, anchorLeft = 1,
                      padding = (1, 0, 0, 0))

        bb = ButtonBar(screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))

        toplevel = GridFormHelp(screen, _("iSCSI Configuration"), "iSCSI", 1, 5)
        toplevel.add(grid, 0, 1, (0, 0, 0, 1), anchorLeft = 1)
        toplevel.add(bb, 0, 3, growx = 1)

        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed (result)
            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK
            self.iscsi.ipaddr = self.ip_entry.value()
            if not self.iscsi.ipaddr:
                # XXX warn no iscsi configuration ...
                break
            if sanityCheckIPString(self.iscsi.ipaddr) is None:
                ButtonChoiceWindow(screen, _("Invalid IP string"),
                                   _("The entered IP '%s' is not a valid IP.")
                                   %(self.iscsi.ipaddr), 
                                   buttons = [ _("OK") ])
                continue
            self.iscsi.port = self.port_entry.value()
            self.iscsi.initiator = self.initiator_entry.value()
            break

        screen.popWindow()
        self.iscsi.startup()
        return INSTALL_OK

# vim:tw=78:ts=4:et:sw=4
