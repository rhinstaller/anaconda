#
# driveorderwidget.py: widget for reordering drives into BIOS order
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
import gobject
import iutil
import partedUtils
import gui
from rhpl.translate import _, N_


class DriveOrderWidget:
    """Widget to reorder drives according to BIOS drive order."""


    def __init__(self, driveorder, diskset):
        self.driveOrder = driveorder
        self.diskset = diskset
        
        hbox = gtk.HBox(False, 5)

        # different widget for this maybe?
        self.driveOrderStore = gtk.ListStore(gobject.TYPE_STRING,
                                             gobject.TYPE_STRING,
                                             gobject.TYPE_STRING)
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        
        self.driveOrderView = gtk.TreeView(self.driveOrderStore)
        i = 0
        for columnName in [ N_("Drive"), N_("Size"), N_("Model") ]:
            renderer = gtk.CellRendererText()
            column = gtk.TreeViewColumn(columnName, renderer, text = i)
            i = i + 1
            column.set_clickable(False)
            self.driveOrderView.append_column(column)

            
        self.driveOrderView.set_rules_hint(False)
        self.driveOrderView.set_headers_visible(False)
        self.driveOrderView.set_enable_search(False)

        self.makeDriveOrderStore()

        sw.add(self.driveOrderView)
        self.driveOrderView.set_size_request(375, 80)
        hbox.pack_start(sw, False)

        arrowbox = gtk.VBox(False, 5)
        arrowButton = gtk.Button()
        arrow = gtk.Arrow(gtk.ARROW_UP, gtk.SHADOW_ETCHED_IN)
        arrowButton.add(arrow)
        arrowButton.connect("clicked", self.arrowClicked, gtk.ARROW_UP)
        arrowbox.pack_start(arrowButton, False)
        
        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        arrowbox.pack_start(spacer, False)

        arrowButton = gtk.Button()
        arrow = gtk.Arrow(gtk.ARROW_DOWN, gtk.SHADOW_ETCHED_IN)
        arrowButton.add(arrow)
        arrowButton.connect("clicked", self.arrowClicked, gtk.ARROW_DOWN)
        arrowbox.pack_start(arrowButton, False)

        alignment = gtk.Alignment()
        alignment.set(0, 0.5, 0, 0)
        alignment.add(arrowbox)
        hbox.pack_start(alignment, False)

        self.widget = hbox


    def getWidget(self):
        return self.widget


    def getOrder(self):
        return self.driveOrder


    def arrowClicked(self, widget, direction, *args):
        selection = self.driveOrderView.get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return

        # there has got to be a better way to do this =\
        drive = model.get_value(iter, 0)[5:]
        index = self.driveOrder.index(drive)
        if direction == gtk.ARROW_DOWN:
            self.driveOrder.remove(drive)
            self.driveOrder.insert(index + 1, drive)
        elif direction == gtk.ARROW_UP:
            self.driveOrder.remove(drive)
            self.driveOrder.insert(index - 1, drive)
        self.makeDriveOrderStore()

    # make the store for the drive order
    def makeDriveOrderStore(self):
        disks = self.diskset.disks
        
        self.driveOrderStore.clear()
        for drive in self.driveOrder:
            iter = self.driveOrderStore.append()
            self.driveOrderStore.set_value(iter, 0, "/dev/%s" % (drive,))
            # if we have it in the diskset, get the size and type of drive
            if disks.has_key(drive):
                size = partedUtils.getDeviceSizeMB(disks[drive].dev)
                sizestr = "%8.0f MB" %(size,)
                
                self.driveOrderStore.set_value(iter, 1, sizestr)
                self.driveOrderStore.set_value(iter, 2, disks[drive].dev.model)
