#
# autopart_type.py: Allows the user to choose how they want to partition
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2005-2006 Red Hat, Inc.
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

import autopart
from rhpl.translate import _, N_
from constants import *
import gui
from partition_ui_helpers_gui import *

from iw_gui import *
from flags import flags

class PartitionTypeWindow(InstallWindow):
    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        ics.setTitle("Automatic Partitioning")
        ics.setNextEnabled(True)
        ics.readHTML("autopart")

    def getNext(self):
        active = self.combo.get_active_iter()
        val = self.combo.get_model().get_value(active, 1)

        if val == -1:
            self.dispatch.skipStep("autopartitionexecute", skip = 1)
            self.dispatch.skipStep("partition", skip = 0)
            self.dispatch.skipStep("bootloader", skip = 0)
        else:
            self.dispatch.skipStep("autopartitionexecute", skip = 0)
            
            self.partitions.useAutopartitioning = 1
            self.partitions.autoClearPartType = val

            allowdrives = []
            model = self.drivelist.get_model()
            for row in model:
                if row[0]:
                    allowdrives.append(row[1])

            if len(allowdrives) < 1:
                mustHaveSelectedDrive(self.intf)
                raise gui.StayOnScreen

            self.partitions.autoClearPartDrives = allowdrives

            if not autopart.queryAutoPartitionOK(self.anaconda):
                raise gui.StayOnScreen

            if self.xml.get_widget("reviewButton").get_active():
                self.dispatch.skipStep("partition", skip = 0)
                self.dispatch.skipStep("bootloader", skip = 0)
            else:
                self.dispatch.skipStep("partition")
                self.dispatch.skipStep("bootloader")
                self.dispatch.skipStep("bootloaderadvanced")

        return None

    def comboChanged(self, *args):
        active = self.combo.get_active_iter()
        val = self.combo.get_model().get_value(active, 1)
        self.review = self.xml.get_widget("reviewButton").get_active()

        # -1 is the combo box choice for 'create custom layout'
        if val == -1:
            if self.prevrev == None:
               self.prevrev = self.xml.get_widget("reviewButton").get_active()

            self.xml.get_widget("reviewButton").set_active(True)
            self.xml.get_widget("reviewButton").set_sensitive(False)
        else:
            if self.prevrev == None:
               self.xml.get_widget("reviewButton").set_active(self.review)
            else:
               self.xml.get_widget("reviewButton").set_active(self.prevrev)
               self.prevrev = None

            self.xml.get_widget("reviewButton").set_sensitive(True)

    def getScreen(self, anaconda):
        self.anaconda = anaconda
        self.diskset = anaconda.id.diskset
        self.partitions = anaconda.id.partitions
        self.intf = anaconda.intf
        self.dispatch = anaconda.dispatch

        (self.xml, vbox) = gui.getGladeWidget("autopart.glade", "parttypeBox")

        self.combo = self.xml.get_widget("partitionTypeCombo")
        cell = gtk.CellRendererText()
        self.combo.pack_start(cell, True)
        self.combo.set_attributes(cell, text = 0)
        cell.set_property("wrap-width", 525)        
        self.combo.set_size_request(480, -1)

        store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_INT)
        self.combo.set_model(store)
        opts = ((_("Remove all partitions on selected drives and create default layout."), CLEARPART_TYPE_ALL),
                (_("Remove linux partitions on selected drives and create default layout."), CLEARPART_TYPE_LINUX),
                (_("Use free space on selected drives and create default layout."), CLEARPART_TYPE_NONE),
                (_("Create custom layout."), -1))
        for (txt, val) in opts:
            iter = store.append(None)
            store[iter] = (txt, val)
            if val == self.partitions.autoClearPartType:
                self.combo.set_active_iter(iter)

        if ((self.combo.get_active() == -1) or
            self.dispatch.stepInSkipList("autopartitionexecute")):
            self.combo.set_active(len(opts) - 1) # yeah, it's a hack

        self.drivelist = createAllowedDrivesList(self.diskset.disks,
                                                 self.partitions.autoClearPartDrives)
        self.drivelist.set_size_request(375, 80)

        self.xml.get_widget("driveScroll").add(self.drivelist)

        self.prevrev = None
        self.review = not self.dispatch.stepInSkipList("partition")
        self.xml.get_widget("reviewButton").set_active(self.review)

        sigs = { "on_partitionTypeCombo_changed": self.comboChanged }
        self.xml.signal_autoconnect(sigs)

        return vbox
