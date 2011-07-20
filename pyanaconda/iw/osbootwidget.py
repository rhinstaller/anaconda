#
# osbootwidget.py: gui bootloader list of operating systems to boot
#
# Copyright (C) 2001, 2002  Red Hat, Inc.  All rights reserved.
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

import gtk
import gobject
from pyanaconda import iutil
import parted
from pyanaconda import gui
from pyanaconda.bootloader import BootLoaderImage
import datacombo
from pyanaconda.constants import *
from pyanaconda.storage.devices import devicePathToName
import copy

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class OSBootWidget:
    """Widget to display OSes to boot and allow adding new ones."""
    
    def __init__(self, anaconda, parent):
        self.bl = anaconda.bootloader
        self.storage = anaconda.storage
        self.parent = parent
        self.intf = anaconda.intf
        self.blname = self.bl.name

        self.setIllegalChars()
        
        self.vbox = gtk.VBox(False, 5)
        label = gtk.Label("<b>" + _("Boot loader operating system list") + "</b>")
	label.set_alignment(0.0, 0.0)
        label.set_property("use-markup", True)
        self.vbox.pack_start(label, False)

        box = gtk.HBox (False, 5)
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.set_size_request(300, 100)
        box.pack_start(sw, True)

        self.osStore = gtk.ListStore(gobject.TYPE_BOOLEAN, gobject.TYPE_STRING,
                                     gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
        self.osTreeView = gtk.TreeView(self.osStore)
        theColumns = [ _("Default"), _("Label"), _("Device") ]

        self.checkboxrenderer = gtk.CellRendererToggle()
        column = gtk.TreeViewColumn(theColumns[0], self.checkboxrenderer,
                                    active = 0)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        self.checkboxrenderer.connect("toggled", self.toggledDefault)
        self.checkboxrenderer.set_radio(True)
        self.osTreeView.append_column(column)

        for columnTitle in theColumns[1:]:
            renderer = gtk.CellRendererText()
            column = gtk.TreeViewColumn(columnTitle, renderer,
                                        text = theColumns.index(columnTitle))
            column.set_clickable(False)
            self.osTreeView.append_column(column)

        self.osTreeView.set_headers_visible(True)
        self.osTreeView.columns_autosize()
        self.osTreeView.set_size_request(100, 100)
        sw.add(self.osTreeView)
        self.osTreeView.connect('row-activated', self.osTreeActivateCb)

        self.images = {}
        for image in self.bl.images:
            self.images[image.device.name] = copy.copy(image)

        self.defaultDev = self.bl.default.device
        self.fillOSList()

        buttonbar = gtk.VButtonBox()
        buttonbar.set_layout(gtk.BUTTONBOX_START)
        buttonbar.set_border_width(5)
        add = gtk.Button(_("_Add"))
        buttonbar.pack_start(add, False)
        add.connect("clicked", self.addEntry)

        edit = gtk.Button(_("_Edit"))
        buttonbar.pack_start(edit, False)
        edit.connect("clicked", self.editEntry)

        delete = gtk.Button(_("_Delete"))
        buttonbar.pack_start(delete, False)
        delete.connect("clicked", self.deleteEntry)
        box.pack_start(buttonbar, False)

        self.vbox.pack_start(box, False)

        self.widget = self.vbox

    def setIllegalChars(self):
        # illegal characters for boot loader labels
        if self.blname == "GRUB":
            self.illegalChars = [ "$", "=" ]
        else:
            self.illegalChars = [ "$", "=", " " ]

    def changeBootLoader(self, blname):
        if blname is not None:
            self.blname = blname
        else:
            self.blname = "GRUB"
        self.setIllegalChars()
        self.fillOSList()

    # adds/edits a new "other" os to the boot loader config
    def editOther(self, image):
        dialog = gtk.Dialog(_("Image"), self.parent)
        dialog.add_button('gtk-cancel', gtk.RESPONSE_CANCEL)
        dialog.add_button('gtk-ok', 1)
        dialog.set_position(gtk.WIN_POS_CENTER)
        gui.addFrame(dialog)

        dialog.vbox.pack_start(gui.WrappingLabel(
            _("Enter a label for the boot loader menu to display. The "
	      "device (or hard drive and partition number) is the device "
	      "from which it boots.")))

        table = gtk.Table(2, 5)
        table.set_row_spacings(5)
        table.set_col_spacings(5)

        label = gui.MnemonicLabel(_("_Label"))
        table.attach(label, 0, 1, 1, 2, gtk.FILL, 0, 10)
        labelEntry = gtk.Entry(32)
        label.set_mnemonic_widget(labelEntry)
        table.attach(labelEntry, 1, 2, 1, 2, gtk.FILL, 0, 10)
        if image.label:
            labelEntry.set_text(image.label)

        label = gui.MnemonicLabel(_("_Device"))
        table.attach(label, 0, 1, 2, 3, gtk.FILL, 0, 10)
        if image.device != self.storage.rootDevice:
            parts = []

            for part in self.storage.partitions:
                if part.partedPartition.getFlag(parted.PARTITION_LVM) or \
                   part.partedPartition.getFlag(parted.PARTITION_RAID) or \
                   not part.partedPartition.active:
                    continue

                parts.append(part)

            store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
            deviceCombo = datacombo.DataComboBox(store)
            defindex = 0
            i = 0
            for part in parts:
                deviceCombo.append(part.path, part)
                if image.device and image.device == part:
                    defindex = i
                i = i + 1


            deviceCombo.set_active(defindex)

            table.attach(deviceCombo, 1, 2, 2, 3, gtk.FILL, 0, 10)
            label.set_mnemonic_widget(deviceCombo)
        else:
            table.attach(gtk.Label(image.device.name), 1, 2, 2, 3, gtk.FILL, 0, 10)

        default = gtk.CheckButton(_("Default Boot _Target"))
        table.attach(default, 0, 2, 3, 4, gtk.FILL, 0, 10)
        default.set_active(image.device == self.defaultDev)
        if len(self.images.keys()) == 1 and image.device:
            default.set_sensitive(False)

        dialog.vbox.pack_start(table)
        dialog.show_all()

        while True:
            rc = dialog.run()

            # cancel
            if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
                break

            label = labelEntry.get_text()

            if not image.device == self.storage.rootDevice:
                dev = deviceCombo.get_active_value()
            else:
                dev = image.device

            if not dev:
                self.intf.messageWindow(_("Error"),
                                        _("You must select a device."),
                                        type="warning")
                continue

            if not label:
                self.intf.messageWindow(_("Error"),
                                        _("You must specify a label for the "
                                          "entry"),
                                        type="warning")
                continue

            foundBad = 0
            for char in self.illegalChars:
                if char in label:
                    self.intf.messageWindow(_("Error"),
                                            _("Boot label contains illegal "
                                              "characters"),
                                            type="warning")
                    foundBad = 1
                    break
            if foundBad:
                continue

            # verify that the label hasn't been used
            foundBad = 0
            for key in self.images.keys():
                if dev.name == key:
                    continue

                thisLabel = self.bl.image_label(self.images[key])

                # if the label is the same as it used to be, they must
                # have changed the device which is fine
                if thisLabel == image.label:
                    continue

                if thisLabel == label:
                    self.intf.messageWindow(_("Duplicate Label"),
                                            _("This label is already in "
                                              "use for another boot entry."),
                                            type="warning")
                    foundBad = 1
                    break
            if foundBad:
                continue

            # they could be duplicating a device, which we don't handle
            if dev.name in self.images.keys() and (not image.device or
                                                 dev != image.device):
                self.intf.messageWindow(_("Duplicate Device"),
                                        _("This device is already being "
                                          "used for another boot entry."),
                                        type="warning")
                continue

            # if we're editing and the device has changed, delete the old
            if image.device and dev != image.device:
                del self.images[image.device.name]
                image.device = dev

            image.label = label
                
            # go ahead and add it
            self.images[dev.name] = image
            if default.get_active():
                self.defaultDev = dev

            # refill the os list store
            self.fillOSList()
            break
        
        dialog.destroy()

    def getSelected(self):
        selection = self.osTreeView.get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return None

        return model.get_value(iter, 3)

    def addEntry(self, widget, *args):
        image = BootLoaderImage(device=None, label=None)
        self.editOther(image)

    def deleteEntry(self, widget, *args):
        image = self.getSelected()
        if not image:
            return
        if image.device != self.storage.rootDevice:
            del self.images[image.device.name]
            if image.device == self.defaultDev:
                devs = [i.device for i in self.images]
                devs.sort(key=lambda d: d.name)
                self.defaultDev = devs[0]
                
            self.fillOSList()
        else:
            self.intf.messageWindow(_("Cannot Delete"),
                                    _("This boot target cannot be deleted "
				      "because it is for the %s "
				      "system you are about to install.")
                                    %(productName,),
                                      type="warning")

    def editEntry(self, widget, *args):
        rc = self.getSelected()
        if not rc:
            return
        self.editOther(rc)

    # the default os was changed in the treeview
    def toggledDefault(self, data, row):
        iter = self.osStore.get_iter((int(row),))
        self.defaultDev = self.osStore.get_value(iter, 3).device
        self.fillOSList()

    # fill in the os list tree view
    def fillOSList(self):
        self.osStore.clear()
        
        devs = sorted(self.images.keys())
        for dev in devs:
            image = self.images[dev]

            # if the label is empty, remove from the image list and don't
            # worry about it
            if not image.label:
                del self.images[dev]
                continue

            iter = self.osStore.append()
            self.osStore.set_value(iter, 0, self.defaultDev == image.device)
            self.osStore.set_value(iter, 1, self.bl.image_label(image))
            self.osStore.set_value(iter, 2, dev)
            self.osStore.set_value(iter, 3, image)

    def osTreeActivateCb(self, view, path, col):
        self.editEntry(view)

    def getWidget(self):
        return self.widget

    def setBootloaderImages(self):
        """Apply the changes from our list into the self.bl object."""
        self.bl.clear_images()
        for image in self.images.values():
            self.bl.add_image(image)
            if image.device == self.defaultDev:
                self.bl.default = image
        
