#
# iscsi_gui.py: gui interface for configuration of iscsi 
#
# Copyright 2005, 2006 IBM, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
import gobject
import gui
import iutil
import network
from rhpl.translate import _, N_
from iw_gui import *

class iscsiWindow(InstallWindow):
    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        ics.setTitle(_("iSCSI Configuration"))
        ics.setNextEnabled(True)

    def getNext(self):
        try:
            network.sanityCheckIPString(self.ip_widget.get_text())
            self.iscsi.ipaddr = self.ip_widget.get_text()
        except network.IPMissing, msg:
            self.intf.messageWindow(_("Error with Data"),
                                    _("No IP address entered, skipping iSCSI setup"))
        except network.IPError, msg:
            self.intf.messageWindow(_("Error with Data"), _("%s") % (msg,))
            raise gui.StayOnScreen

        self.iscsi.port = self.port.get_text()
        self.iscsi.initiator = self.initiator.get_text()

        w = self.intf.waitWindow(_("Initializing iSCSI initiator"), "")
        self.iscsi.startup()
        import time # XXX mmmm. hacktastic.
        time.sleep(5)
        w.pop()

        return None

    def getScreen(self, anaconda):
        self.intf = anaconda.intf
        self.iscsi = anaconda.id.iscsi

        (self.xml, widget) = gui.getGladeWidget("iscsi-config.glade", "iscsiRows")
        self.ip_table = self.xml.get_widget("iscsiTable")
        self.ip_widget = gtk.Entry()
        self.ip_widget.set_text(self.iscsi.ipaddr)

        self.port = self.xml.get_widget("iscsiPort")
        if self.iscsi.port:
            self.port.set_text(self.iscsi.port)

        self.initiator = self.xml.get_widget("iscsiInitiator")
        if self.iscsi.initiator:
            self.initiator.set_text(self.iscsi.initiator)

        # put the IP address widget in the right (1, 2) upper (0, 1)
        # corner of our 3 rows by 2 columns table.

        # XXX there is too much space around the IP address. Using this
        # variant had no affect:
        # self.ip_table.attach(self.ip_widget, 1, 2, 0, 1, gtk.FILL|gtk.EXPAND)
        self.ip_table.attach(self.ip_widget, 1, 2, 0, 1)
        return widget

# vim:tw=78:ts=4:et:sw=4
