#
# osbootwidget.py: gui bootloader list of operating systems to boot
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
import datacombo
from rhpl.translate import _, N_
from constants import *


class OSBootWidget:
    """Widget to display OSes to boot and allow adding new ones."""
    
    def __init__(self, anaconda, parent, blname):
        self.bl = anaconda.id.bootloader
        self.fsset = anaconda.id.fsset
        self.diskset = anaconda.id.diskset
        self.parent = parent
        self.intf = anaconda.intf
        if blname is not None:
            self.blname = blname
        else:
            self.blname = "GRUB"

        self.setIllegalChars()
        
        self.vbox = gtk.VBox(False, 5)
        label = gui.WrappingLabel(_("You can configure the boot loader to boot other operating systems. "
				    "It will allow you to select an operating system to boot from the list. "
				    "To add additional operating systems, which are not automatically "
				    "detected, click 'Add.' To change the operating system booted by default, "
				    "select 'Default' by the desired operating system."))
	label.set_alignment(0.0, 0.0)
	label.set_size_request(350, -1)
        self.vbox.pack_start(label, False)

        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        self.vbox.pack_start(spacer, False)

        box = gtk.HBox (False, 5)
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.set_size_request(300, 100)
        box.pack_start(sw, True)


        self.osStore = gtk.ListStore(gobject.TYPE_BOOLEAN, gobject.TYPE_STRING,
                                     gobject.TYPE_STRING, gobject.TYPE_BOOLEAN)
        self.osTreeView = gtk.TreeView(self.osStore)
        theColumns = [ _("Default"), _("Label"), _("Device") ]

        self.checkboxrenderer = gtk.CellRendererToggle()
        column = gtk.TreeViewColumn(theColumns[0], self.checkboxrenderer,
                                    active = 0)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
        self.checkboxrenderer.connect("toggled", self.toggledDefault)
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

        self.imagelist = self.bl.images.getImages()
        self.defaultDev = self.bl.images.getDefault()
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
    def editOther(self, oldDevice, oldLabel, isDefault, isRoot = 0):
        dialog = gtk.Dialog(_("Image"), self.parent)
        dialog.add_button('gtk-cancel', 2)
        dialog.add_button('gtk-ok', 1)
        dialog.set_position(gtk.WIN_POS_CENTER)
        gui.addFrame(dialog)

        dialog.vbox.pack_start(gui.WrappingLabel(
            _("Enter a label to be displayed in the boot loader menu. The "
	      "device (or hard drive and partition number) is the device "
	      "from which it boots.")))

        spacer = gtk.Label("")
        spacer.set_size_request(10, 1)
        dialog.vbox.pack_start(spacer, False)

        table = gtk.Table(2, 5)
        table.set_row_spacings(5)
        table.set_col_spacings(5)

        label = gui.MnemonicLabel(_("_Label"))
        table.attach(label, 0, 1, 1, 2, gtk.FILL, 0, 10)
        labelEntry = gtk.Entry(32)
        label.set_mnemonic_widget(labelEntry)
        table.attach(labelEntry, 1, 2, 1, 2, gtk.FILL, 0, 10)
        if oldLabel:
            labelEntry.set_text(oldLabel)

        label = gui.MnemonicLabel(_("_Device"))
        table.attach(label, 0, 1, 2, 3, gtk.FILL, 0, 10)
        if not isRoot:
            # XXX should potentially abstract this out into a function
            pedparts = []
            parts = []
            disks = self.diskset.disks
            for drive in disks.keys():
                pedparts.extend(partedUtils.get_all_partitions(disks[drive]))
            for part in pedparts:
                parts.append(partedUtils.get_partition_name(part))
            del pedparts
            parts.sort()

            deviceCombo = datacombo.DataComboBox()
            defindex = 0
            i = 0
            for part in  parts:
                deviceCombo.append("/dev/%s" %(part,), part)
                if oldDevice and oldDevice == part:
                    defindex = i
                i = i + 1


            deviceCombo.set_active(defindex)
            
            table.attach(deviceCombo, 1, 2, 2, 3, gtk.FILL, 0, 10)
            label.set_mnemonic_widget(deviceCombo)
        else:
            table.attach(gtk.Label(oldDevice), 1, 2, 2, 3, gtk.FILL, 0, 10)

        default = gtk.CheckButton(_("Default Boot _Target"))
        table.attach(default, 0, 2, 3, 4, gtk.FILL, 0, 10)
        if isDefault != 0:
            default.set_active(True)

        if self.numentries == 1 and oldDevice != None:
            default.set_sensitive(False)
        else:
            default.set_sensitive(True)
        
        dialog.vbox.pack_start(table)
        dialog.show_all()

        while 1:
            rc = dialog.run()

            # cancel
            if rc == 2:
                break

            label = labelEntry.get_text()

            if not isRoot:
                dev = deviceCombo.get_active_value()
            else:
                dev = oldDevice

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
            for key in self.imagelist.keys():
                if dev == key:
                    continue
                if self.blname == "GRUB":
                    thisLabel = self.imagelist[key][1]
                else:
                    thisLabel = self.imagelist[key][0]

                # if the label is the same as it used to be, they must
                # have changed the device which is fine
                if thisLabel == oldLabel:
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

            # XXX need to do some sort of validation of the device?

            # they could be duplicating a device, which we don't handle
            if dev in self.imagelist.keys() and (not oldDevice or
                                                 dev != oldDevice):
                self.intf.messageWindow(_("Duplicate Device"),
                                        _("This device is already being "
                                          "used for another boot entry."),
                                        type="warning")
                continue

            # if we're editing a previous, get what the old info was for
            # labels.  otherwise, make it something safe for grub and the
            # device name for lilo for lack of any better ideas
            if oldDevice:
                (oldshort, oldlong, oldisroot) = self.imagelist[oldDevice]
            else:
                (oldshort, oldlong, oldisroot) = (dev, label, None)
                
            # if we're editing and the device has changed, delete the old
            if oldDevice and dev != oldDevice:
                del self.imagelist[oldDevice]
                
            # go ahead and add it
            if self.blname == "GRUB":
                self.imagelist[dev] = (oldshort, label, isRoot)
            else:
                self.imagelist[dev] = (label, oldlong, isRoot)

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

        dev = model.get_value(iter, 2)
        theDev = dev[5:] # strip /dev/
        
        label = model.get_value(iter, 1)
        isRoot = model.get_value(iter, 3)
        isDefault = model.get_value(iter, 0)
        return (theDev, label, isDefault, isRoot)


    def addEntry(self, widget, *args):
        self.editOther(None, None, 0)

    def deleteEntry(self, widget, *args):
        rc = self.getSelected()
        if not rc:
            return
        (dev, label, isDefault, isRoot) = rc
        if not isRoot:
            del self.imagelist[dev]
            if isDefault:
                keys = self.imagelist.keys()
                keys.sort()
                self.defaultDev = keys[0]
                
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
        (dev, label, isDefault, isRoot) = rc
        self.editOther(dev, label, isDefault, isRoot)

    # the default os was changed in the treeview
    def toggledDefault(self, data, row):
        iter = self.osStore.get_iter((int(row),))
        dev = self.osStore.get_value(iter, 2)
        self.defaultDev = dev[5:]
        self.fillOSList()

    # fill in the os list tree view
    def fillOSList(self):
        self.osStore.clear()
        
        keys = self.imagelist.keys()
        keys.sort()

        for dev in keys:
            (label, longlabel, fstype) = self.imagelist[dev]
            if self.blname == "GRUB":
                theLabel = longlabel
            else:
                theLabel = label

            # if the label is empty, remove from the image list and don't
            # worry about it
            if not theLabel:
                del self.imagelist[dev]
                continue

	    isRoot = 0
	    fsentry = self.fsset.getEntryByDeviceName(dev)
	    if fsentry and fsentry.getMountPoint() == '/':
		isRoot = 1

            iter = self.osStore.append()
            self.osStore.set_value(iter, 1, theLabel)
            self.osStore.set_value(iter, 2, "/dev/%s" % (dev,))
            self.osStore.set_value(iter, 3, isRoot)
            if self.defaultDev == dev:
                self.osStore.set_value(iter, 0, True)
            else:
                self.osStore.set_value(iter, 0, False)

        self.numentries = len(keys)

    def osTreeActivateCb(self, view, path, col):
        self.editEntry(view)
        
        
    def getWidget(self):
        return self.widget

    # FIXME: I really shouldn't have such intimate knowledge of
    # the bootloader object
    def setBootloaderImages(self):
        "Apply the changes from our list into the self.bl object"
        # make a copy of our image list to shove into the bl struct
        self.bl.images.images = {}
        for key in self.imagelist.keys():
            self.bl.images.images[key] = self.imagelist[key]
        self.bl.images.setDefault(self.defaultDev)
        
