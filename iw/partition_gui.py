#
# partition_gui.py: allows the user to choose how to partition their disks
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
# Author(s): Matt Wilson <msw@redhat.com>
#            Michael Fulbright <msf@redhat.com>
#

import gobject
import gtk
try:
    import gnomecanvas
except ImportError:
    import gnome.canvas as gnomecanvas
import pango
import gui
import parted
import string
import types
from constants import *

import storage
from iw_gui import *
from flags import flags

import lvm_dialog_gui
import raid_dialog_gui
import partition_dialog_gui

from partIntfHelpers import *
from constants import *
from partition_ui_helpers_gui import *
from storage.partitioning import doPartitioning
from storage.devicelibs import lvm
from storage.devices import devicePathToName, PartitionDevice

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

STRIPE_HEIGHT = 35.0
LOGICAL_INSET = 3.0
CANVAS_WIDTH_800 = 490
CANVAS_WIDTH_640 = 390
CANVAS_HEIGHT = 200
TREE_SPACING = 2

MODE_ADD = 1
MODE_EDIT = 2

# XXXX temporary image data
new_checkmark = "GdkP"
new_checkmark = new_checkmark + "\0\0\2X"
new_checkmark = new_checkmark + "\1\1\0\2"
new_checkmark = new_checkmark + "\0\0\0""0"
new_checkmark = new_checkmark + "\0\0\0\14"
new_checkmark = new_checkmark + "\0\0\0\14" 
new_checkmark = new_checkmark + "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
new_checkmark = new_checkmark + "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
new_checkmark = new_checkmark + "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0&\0\0\0\217\0\0\0""3\0\0\0\0\0"
new_checkmark = new_checkmark + "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0,\0\0\0\252"
new_checkmark = new_checkmark + "\0\0\0\254\0\0\0\1\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
new_checkmark = new_checkmark + "\0\0\0\0\0\0#\0\0\0\246\0\0\0\264\0\0\0\227\0\0\0\0\0\0\0\0\0\0\0\0\0"
new_checkmark = new_checkmark + "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\6\0\0\0\221\0\0\0\264\0\0\0\264"
new_checkmark = new_checkmark + "\0\0\0\214\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\21\0\0\0\0\0\0\0\0\0\0\0\0\0"
new_checkmark = new_checkmark + "\0\0U\0\0\0\264\0\0\0\264\0\0\0\202\0\0\0\21\0\0\0\0\0\0\0\0\0\0\0\40"
new_checkmark = new_checkmark + "\0\0\0\222\0\0\0\37\0\0\0\0\0\0\0\26\0\0\0\252\0\0\0\264\0\0\0\214\0"
new_checkmark = new_checkmark + "\0\0\16\0\0\0\0\0\0\0\0\0\0\0\6\0\0\0u\0\0\0\264\0\0\0\240\0\0\0'\0\0"
new_checkmark = new_checkmark + "\0l\0\0\0\264\0\0\0\254\0\0\0!\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\24\0\0\0"
new_checkmark = new_checkmark + "\207\0\0\0\256\0\0\0\264\0\0\0\240\0\0\0\256\0\0\0\264\0\0\0d\0\0\0\0"
new_checkmark = new_checkmark + "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\4\0\0\0;\0\0\0\233\0\0\0\263\0"
new_checkmark = new_checkmark + "\0\0\264\0\0\0\252\0\0\0\20\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
new_checkmark = new_checkmark + "\0\0\0\0\0\0\0\0\0\0\15\0\0\0r\0\0\0\263\0\0\0i\0\0\0\0\0\0\0\0\0\0\0"
new_checkmark = new_checkmark + "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0g\0\0"
new_checkmark = new_checkmark + "\0\"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"


class DiskStripeSlice:
    def eventHandler(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 1:
                self.parent.selectSlice(self.partition, 1)
        elif event.type == gtk.gdk._2BUTTON_PRESS:
            self.editCB()
                
        return True

    def shutDown(self):
        self.parent = None
        if self.group:
            self.group.destroy()
            self.group = None
        del self.partedPartition
        del self.partition

    def select(self):
        if self.partedPartition.type != parted.PARTITION_EXTENDED:
            self.group.raise_to_top()
        self.box.set(outline_color="red")
        self.box.set(fill_color=self.selectColor())

    def deselect(self):
        self.box.set(outline_color="black", fill_color=self.fillColor())

    def getPartition(self):
        return self.partition

    def fillColor(self):
        if self.partedPartition.type & parted.PARTITION_FREESPACE:
            return "grey88"
        return "white"

    def selectColor(self):
        if self.partedPartition.type & parted.PARTITION_FREESPACE:
            return "cornsilk2"
        return "cornsilk1"

    def sliceText(self):
        if self.partedPartition.type & parted.PARTITION_EXTENDED:
            return ""
        if self.partedPartition.type & parted.PARTITION_FREESPACE:
            rc = "Free\n"
        else:
            rc = "%s\n" % (self.partedPartition.getDeviceNodeName().split("/")[-1],)
        rc = rc + "%Ld MB" % (self.partedPartition.getSize(unit="MB"),)
        return rc

    def update(self):
        disk = self.parent.getDisk()
        (cylinders, heads, sectors) = disk.device.biosGeometry
        totalSectors = float(heads * sectors * cylinders)

        # XXX hack but will work for now
        if gtk.gdk.screen_width() > 640:
            width = CANVAS_WIDTH_800
        else:
            width = CANVAS_WIDTH_640

        # If it's a very, very small partition then there's no point in trying
        # cut off a piece of the parent disk's stripe for it.
        if totalSectors == 0:
            return

        xoffset = self.partedPartition.geometry.start / totalSectors * width
        xlength = self.partedPartition.geometry.length / totalSectors * width

        if self.partedPartition.type & parted.PARTITION_LOGICAL:
            yoffset = 0.0 + LOGICAL_INSET
            yheight = STRIPE_HEIGHT - (LOGICAL_INSET * 2)
            texty = 0.0
        else:
            yoffset = 0.0
            yheight = STRIPE_HEIGHT
            texty = LOGICAL_INSET
        self.group.set(x=xoffset, y=yoffset)
        self.box.set(x1=0.0, y1=0.0, x2=xlength,
                     y2=yheight, fill_color=self.fillColor(),
                     outline_color='black', width_units=1.0)
        self.text.set(x=2.0, y=texty + 2.0, text=self.sliceText(),
                      fill_color='black',
                      anchor=gtk.ANCHOR_NW, clip=True,
                      clip_width=xlength-1, clip_height=yheight-1)
       
    def __init__(self, parent, partition, treeView, editCB):
        self.text = None
        self.partition = partition
        self.partedPartition = partition.partedPartition
        self.parent = parent
        self.treeView = treeView
        self.editCB = editCB
        pgroup = parent.getGroup()

        self.group = pgroup.add(gnomecanvas.CanvasGroup)
        self.box = self.group.add(gnomecanvas.CanvasRect)
        self.group.connect("event", self.eventHandler)
        self.text = self.group.add(gnomecanvas.CanvasText,
                                    font="sans", size_points=8)
        self.update()

class DiskStripe:
    def __init__(self, drive, disk, group, tree, editCB):
        self.disk = disk
        self.group = group
        self.tree = tree
        self.drive = drive
        self.slices = []
        self.hash = {}
        self.editCB = editCB
        self.selected = None

        # XXX hack but will work for now
        if gtk.gdk.screen_width() > 640:
            width = CANVAS_WIDTH_800
        else:
            width = CANVAS_WIDTH_640
        
        group.add(gnomecanvas.CanvasRect, x1=0.0, y1=10.0, x2=width,
                  y2=STRIPE_HEIGHT, fill_color='green',
                  outline_color='grey71', width_units=1.0)
        group.lower_to_bottom()

    def shutDown(self):
        while self.slices:
            slice = self.slices.pop()
            slice.shutDown()
        if self.group:
            self.group.destroy()
            self.group = None
        del self.disk

    def holds(self, partition):
        return self.hash.has_key(partition)

    def getSlice(self, partition):
        return self.hash[partition]
   
    def getDisk(self):
        return self.disk

    def getDrive(self):
        return self.drive

    def getGroup(self):
        return self.group

    def selectSlice(self, partition, updateTree=0):
        self.deselect()
        slice = self.hash[partition]
        slice.select()

        # update selection of the tree
        if updateTree:
            self.tree.selectPartition(partition)
        self.selected = slice

    def deselect(self):
        if self.selected:
            self.selected.deselect()
        self.selected = None
    
    def add(self, partition):
        stripe = DiskStripeSlice(self, partition, self.tree, self.editCB)
        self.slices.append(stripe)
        self.hash[partition] = stripe

class DiskStripeGraph:
    def __init__(self, tree, editCB):
        self.canvas = gnomecanvas.Canvas()
        self.diskStripes = []
        self.textlabels = []
        self.tree = tree
        self.editCB = editCB
        self.next_ypos = 0.0

    def __del__(self):
        self.shutDown()
        
    def shutDown(self):
        # remove any circular references so we can clean up
        while self.diskStripes:
            stripe = self.diskStripes.pop()
            stripe.shutDown()

        while self.textlabels:
            lab = self.textlabels.pop()
            lab.destroy()

        self.next_ypos = 0.0

    def getCanvas(self):
        return self.canvas

    def selectSlice(self, partition):
        for stripe in self.diskStripes:
            stripe.deselect()
            if stripe.holds(partition):
                stripe.selectSlice(partition)

    def getSlice(self, partition):
        for stripe in self.diskStripes:
            if stripe.holds(partition):
                return stripe.getSlice(partition)

    def getDisk(self, partition):
        for stripe in self.diskStripes:
            if stripe.holds(partition):
                return stripe.getDisk()

    def add(self, drive, disk):
        yoff = self.next_ypos
        text = self.canvas.root().add(gnomecanvas.CanvasText,
                                      x=0.0, y=yoff,
                                      font="sans",
                                      size_points=9)
        drivetext = _("Drive %s (%-0.f MB) "
                     "(Model: %s)") % ('/dev/' + drive,
                                       disk.device.getSize(unit="MB"),
                                       disk.device.model)

        text.set(text=drivetext, fill_color='black', anchor=gtk.ANCHOR_NW,
                 weight=pango.WEIGHT_BOLD)
        (xxx1, yyy1, xxx2, yyy2) =  text.get_bounds()
        textheight = yyy2 - yyy1 + 2
        self.textlabels.append(text)
        group = self.canvas.root().add(gnomecanvas.CanvasGroup,
                                       x=0, y=yoff+textheight)
        stripe = DiskStripe(drive, disk, group, self.tree, self.editCB)
        self.diskStripes.append(stripe)
        self.next_ypos = self.next_ypos + STRIPE_HEIGHT+textheight+10
        return stripe

class DiskTreeModelHelper:
    def __init__(self, model, columns, iter):
        self.model = model
        self.iter = iter
        self.columns = columns

    def __getitem__(self, key):
        if type(key) == types.StringType:
            key = self.columns[key]
        try:
            return self.model.get_value(self.iter, key)
        except:
            return None

    def __setitem__(self, key, value):
        if type(key) == types.StringType:
            key = self.columns[key]
        self.model.set_value(self.iter, key, value)

class DiskTreeModel(gtk.TreeStore):
    isLeaf = -3
    isFormattable = -2
    
    # format: column header, type, x alignment, hide?, visibleKey
    titles = ((N_("Device"), gobject.TYPE_STRING, 0.0, 0, 0),
              (N_("Label"), gobject.TYPE_STRING, 0.0, 1, 0),
              (N_("Mount Point"), gobject.TYPE_STRING, 0.0, 0, isLeaf),
              (N_("Type"), gobject.TYPE_STRING, 0.0, 0, 0),
#              (N_("Format"), gobject.TYPE_BOOLEAN, 0.5, 0, isFormattable),
#              (N_("Size (MB)"), gobject.TYPE_STRING, 1.0, 0, isLeaf),
              (N_("Format"), gobject.TYPE_OBJECT, 0.5, 0, isFormattable),
              (N_("Size (MB)"), gobject.TYPE_STRING, 1.0, 0, 0),
	      ("", gobject.TYPE_STRING, 0.0, 0, 0),
              # the following must be the last two
              ("IsLeaf", gobject.TYPE_BOOLEAN, 0.0, 1, 0),
              ("IsFormattable", gobject.TYPE_BOOLEAN, 0.0, 1, 0),
              ("PyObject", gobject.TYPE_PYOBJECT, 0.0, 1, 0))
    
    def __init__(self):
	self.hiddenPartitions = []
        self.titleSlot = {}
        i = 0
        types = [self]
        self.columns = []
        for title, kind, alignment, hide, key in self.titles:
            self.titleSlot[title] = i
            types.append(kind)
            if hide:
                i += 1
                continue
            elif kind == gobject.TYPE_OBJECT:
                renderer = gtk.CellRendererPixbuf()
                propertyMapping = {'pixbuf': i}
            elif kind == gobject.TYPE_BOOLEAN:
                renderer = gtk.CellRendererToggle()
                propertyMapping = {'active': i}
            elif (kind == gobject.TYPE_STRING or
                  kind == gobject.TYPE_INT):
                renderer = gtk.CellRendererText()
		propertyMapping = {'text': i}

            # wire in the cells that we want only visible on leaf nodes to
            # the special leaf node column.
            if key < 0:
                propertyMapping['visible'] = len(self.titles) + key
                
            renderer.set_property('xalign', alignment)
	    if title == "Mount Point":
		title = _("Mount Point/\nRAID/Volume")
	    elif title == "Size (MB)":
		title = _("Size\n(MB)")
            elif title != "":
                title = _(title)
            col = apply(gtk.TreeViewColumn, (title, renderer),
                        propertyMapping)
	    col.set_alignment(0.5)
	    if kind == gobject.TYPE_STRING or kind == gobject.TYPE_INT:
		col.set_property('sizing', gtk.TREE_VIEW_COLUMN_AUTOSIZE)
            self.columns.append(col)
            i += 1

        apply(gtk.TreeStore.__init__, types)

        self.view = gtk.TreeView(self)
        # append all of the columns
        map(self.view.append_column, self.columns)

    def getTreeView(self):
        return self.view

    def clearHiddenPartitionsList(self):
	self.hiddenPartitions = []

    def appendToHiddenPartitionsList(self, member):
	self.hiddenPartitions.append(member)

    def selectPartition(self, partition):
	# if we've hidden this partition in the tree view just return
	if partition in self.hiddenPartitions:
	    return
	
        pyobject = self.titleSlot['PyObject']
        iter = self.get_iter_first()
	parentstack = [None,]
	parent = None
        # iterate over the list, looking for the current mouse selection
        while iter:
            try:
                rowpart = self.get_value(iter, pyobject)
            except SystemError:
                rowpart = None
            if rowpart == partition:
                path = self.get_path(parent)
                self.view.expand_row(path, True)
                selection = self.view.get_selection()
                if selection is not None:
                    selection.unselect_all()
                    selection.select_iter(iter)
                path = self.get_path(iter)
                col = self.view.get_column(0)
                self.view.set_cursor(path, col, False)
                self.view.scroll_to_cell(path, col, True, 0.5, 0.5)
                return
            # if this is a parent node, and it didn't point to the partition
            # we're looking for, get the first child and iter over them
            elif self.iter_has_child(iter):
                parent = iter
                parentstack.append(iter)
                iter = self.iter_children(iter)
                continue
            # get the next row.
            iter = self.iter_next(iter)
            # if there isn't a next row and we had a parent, go to the next
            # node after our parent
            while not iter and parent:
                # pop last parent off of parentstack and resume search at next
                # node after the last parent... and don't forget to update the
                # variable "parent" to its new value
                if len(parentstack) > 0:
                    iter = self.iter_next(parentstack.pop())
                    parent = parentstack[-1]
                else:
                    # we've fallen off the end of the model, and we have
                    # not found the partition
                    raise RuntimeError, "could not find partition"

    def getCurrentDevice(self):
        """ Return the device representing the current selection """
        selection = self.view.get_selection()
        model, iter = selection.get_selected()
        if not iter:
            return None

        pyobject = self.titleSlot['PyObject']
	try:
            val = self.get_value(iter, pyobject)
        except Exception:
            val = None

        return val

    def resetSelection(self):
        pass
##         selection = self.view.get_selection()
##         selection.set_mode(gtk.SELECTION_SINGLE)
##         selection.set_mode(gtk.SELECTION_BROWSE)

    def clear(self):
        selection = self.view.get_selection()
        if selection is not None:
            selection.unselect_all()
        gtk.TreeStore.clear(self)
        
    def __getitem__(self, iter):
        if type(iter) == gtk.TreeIter:
            return DiskTreeModelHelper(self, self.titleSlot, iter)
        raise KeyError, iter


class PartitionWindow(InstallWindow):
    def __init__(self, ics):
	InstallWindow.__init__(self, ics)
        ics.setTitle(_("Partitioning"))
        ics.setNextEnabled(True)
        self.parent = ics.getICW().window

    def quit(self):
        pass

    def presentPartitioningComments(self,title, labelstr1, labelstr2, comments,
				    type="ok", custom_buttons=None):

        if flags.autostep:
            return 1

        win = gtk.Dialog(title)
        gui.addFrame(win)
        
        if type == "ok":
            win.add_button('gtk-ok', 1)
	    defaultchoice = 0
        elif type == "yesno":
            win.add_button('gtk-no', 2)
            win.add_button('gtk-yes', 1)
	    defaultchoice = 1
	elif type == "continue":
            win.add_button('gtk-cancel', 0)
            win.add_button(_("Continue"), 1)
	    defaultchoice = 1
	elif type == "custom":
	    rid=0

	    for button in custom_buttons:
		widget = win.add_button(button, rid)
		rid = rid + 1

            defaultchoice = rid - 1
	    
        image = gtk.Image()
        image.set_from_stock('gtk-dialog-warning', gtk.ICON_SIZE_DIALOG)
        hbox = gtk.HBox(False, 9)
	al=gtk.Alignment(0.0, 0.0)
	al.add(image)
        hbox.pack_start(al, False)

        buffer = gtk.TextBuffer(None)
        buffer.set_text(comments)
        text = gtk.TextView()
        text.set_buffer(buffer)
        text.set_property("editable", False)
        text.set_property("cursor_visible", False)
        text.set_wrap_mode(gtk.WRAP_WORD)
        
        sw = gtk.ScrolledWindow()
        sw.add(text)
	sw.set_size_request(400, 200)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        
        info1 = gtk.Label(labelstr1)
        info1.set_line_wrap(True)
        info1.set_size_request(400, -1)

        info2 = gtk.Label(labelstr2)
        info2.set_line_wrap(True)
        info2.set_size_request(400, -1)
        
        vbox = gtk.VBox(False, 9)

	al=gtk.Alignment(0.0, 0.0)
	al.add(info1)
        vbox.pack_start(al, False)
	
        vbox.pack_start(sw, True, True)

	al=gtk.Alignment(0.0, 0.0)
	al.add(info2)
        vbox.pack_start(al, True)
	
        hbox.pack_start(vbox, True, True)

        win.vbox.pack_start(hbox)
        win.set_position(gtk.WIN_POS_CENTER)
        win.set_default_response(defaultchoice)
        win.show_all()
        rc = win.run()
        win.destroy()
        return rc
        
    def getNext(self):
        (errors, warnings) = self.storage.sanityCheck()
        if errors:
            labelstr1 =  _("The partitioning scheme you requested "
                           "caused the following critical errors.")
            labelstr2 = _("You must correct these errors before "
                          "you continue your installation of "
                          "%s.") % (productName,)

            commentstr = string.join(errors, "\n\n")
            
            self.presentPartitioningComments(_("Partitioning Errors"),
                                             labelstr1, labelstr2,
                                             commentstr, type="ok")
            raise gui.StayOnScreen
        
        if warnings:
            # "storage configuration"
            labelstr1 = _("The partitioning scheme you requested "
                          "generated the following warnings.")
            labelstr2 = _("Would you like to continue with "
                         "your requested partitioning "
                         "scheme?")
            
            commentstr = string.join(warnings, "\n\n")
            rc = self.presentPartitioningComments(_("Partitioning Warnings"),
                                                  labelstr1, labelstr2,
                                                  commentstr,
						  type="yesno")
            if rc != 1:
                raise gui.StayOnScreen

        formatWarnings = getPreExistFormatWarnings(self.storage)
        if formatWarnings:
            labelstr1 = _("The following pre-existing partitions have been "
                          "selected to be formatted, destroying all data.")

#            labelstr2 = _("Select 'Yes' to continue and format these "
#                          "partitions, or 'No' to go back and change these "
#                          "settings.")
            labelstr2 = ""
            commentstr = ""
            for (dev, type, mntpt) in formatWarnings:
                commentstr = commentstr + \
                        "%s         %s         %s\n" % (dev,type,mntpt)

            rc = self.presentPartitioningComments(_("Format Warnings"),
                                                  labelstr1, labelstr2,
                                                  commentstr,
						  type="custom",
						  custom_buttons=["gtk-cancel",
								  _("_Format")])
            if rc != 1:
                raise gui.StayOnScreen

        
        self.diskStripeGraph.shutDown()
        self.tree.clear()
        del self.parent
        return None

    def getPrev(self):
        self.diskStripeGraph.shutDown()
        self.storage.reset()
        self.tree.clear()
        del self.parent
        return None

    def populate(self, initial = 0):
        self.tree.resetSelection()

	self.tree.clearHiddenPartitionsList()

	# first do LVM
        vgs = self.storage.vgs
        if vgs:
	    lvmparent = self.tree.append(None)
	    self.tree[lvmparent]['Device'] = _("LVM Volume Groups")
            for vg in vgs:
		rsize = vg.size

                vgparent = self.tree.append(lvmparent)
		self.tree[vgparent]['Device'] = "%s" % vg.name
                self.tree[vgparent]['Label'] = ""
		self.tree[vgparent]['Mount Point'] = ""
		self.tree[vgparent]['Size (MB)'] = "%Ld" % (rsize,)
                self.tree[vgparent]['PyObject'] = vg
		for lv in vg.lvs:
                    if lv.format.type == "luks":
                        # we'll want to grab format info from the mapped
                        # device, not the encrypted one
                        try:
                            dm_dev = self.storage.devicetree.getChildren(lv)[0]
                        except IndexError:
                            format = lv.format
                        else:
                            format = dm_dev.format
                    else:
                        format = lv.format
		    iter = self.tree.append(vgparent)
		    self.tree[iter]['Device'] = lv.lvname
		    if format.mountable and format.mountpoint:
			self.tree[iter]['Mount Point'] = format.mountpoint
		    else:
			self.tree[iter]['Mount Point'] = ""
		    self.tree[iter]['Size (MB)'] = "%Ld" % lv.size
		    self.tree[iter]['PyObject'] = vg
		
                    if lv.format.type == "luks" and not lv.format.exists:
                        # we're creating the LUKS header
			self.tree[iter]['Format'] = self.lock_pixbuf
                    elif not format.exists:
                        # we're creating a format on the device
			self.tree[iter]['Format'] = self.checkmark_pixbuf
                    self.tree[iter]['IsFormattable'] = format.formattable
		    self.tree[iter]['IsLeaf'] = True
		    self.tree[iter]['Type'] = format.name
		    #self.tree[iter]['Start'] = ""
		    #self.tree[iter]['End'] = ""

        # handle RAID next
        mdarrays = self.storage.mdarrays
        if mdarrays:
	    raidparent = self.tree.append(None)
	    self.tree[raidparent]['Device'] = _("RAID Devices")
            for array in mdarrays:
		mntpt = None
                if array.format.type == "luks":
                    # look up the mapped/decrypted device since that's
                    # where we'll find the format we want to display
                    try:
                        dm_dev = self.storage.devicetree.getChildren(array)[0]
                    except IndexError:
                        format = array.format
                    else:
                        format = dm_dev.format
                else:
                    format = array.format

                if format.type == "lvmpv":
                    vg = None
		    for _vg in self.storage.vgs:
                        if _vg.dependsOn(array):
                            vg = _vg
                            break
                    if vg and self.show_uneditable:
                        mntpt = vg.name
                    elif vg:
                        self.tree.appendToHiddenPartitionsList(array.path)
                        continue
		    else:
			mntpt = ""
                elif format.mountable and format.mountpoint:
                    mntpt = format.mountpoint

                iter = self.tree.append(raidparent)
		if mntpt:
                    self.tree[iter]["Mount Point"] = mntpt
                else:
                    self.tree[iter]["Mount Point"] = ""
		    
                if format.type:
                    ptype = format.name
                    if array.format.type == "luks" and \
                       not array.format.exists:
			self.tree[iter]['Format'] = self.lock_pixbuf
                    elif not format.exists:
                        self.tree[iter]['Format'] = self.checkmark_pixbuf
                    self.tree[iter]['IsFormattable'] = format.formattable
                else:
                    ptype = _("None")
                    self.tree[iter]['IsFormattable'] = False

		if array.minor is not None:
		    device = "%s" % array.path
		else:
		    device = "Auto"
		    
                self.tree[iter]['IsLeaf'] = True
                self.tree[iter]['Device'] = device
                if array.format.exists and getattr(format, "label", None):
                    self.tree[iter]['Label'] = "%s" % format.label
                else:
                    self.tree[iter]['Label'] = ""
                self.tree[iter]['Type'] = ptype
                self.tree[iter]['Size (MB)'] = "%Ld" % array.size
                self.tree[iter]['PyObject'] = array

	# now normal partitions
        disks = self.storage.disks
	drvparent = self.tree.append(None)
	self.tree[drvparent]['Device'] = _("Hard Drives")
        for disk in disks:
            # add a disk stripe to the graph
            stripe = self.diskStripeGraph.add(disk.name, disk.partedDisk)

            # add a parent node to the tree
            parent = self.tree.append(drvparent)
            self.tree[parent]['Device'] = "%s" % disk.path
            self.tree[parent]['PyObject'] = disk
            (cylinders, heads, sectors) = disk.partedDisk.device.biosGeometry
            sectorsPerCyl = heads * sectors

            part = disk.partedDisk.getFirstPartition()
            extendedParent = None
            while part:
                if part.type & parted.PARTITION_METADATA:
                    part = part.nextPartition()
                    continue

                partName = devicePathToName(part.getDeviceNodeName())
                device = self.storage.devicetree.getDeviceByName(partName)
                if not device and not part.type & parted.PARTITION_FREESPACE:
                    log.debug("can't find partition %s in device"
                                       " tree" % partName)

                # ignore the tiny < 1 MB partitions (#119479)
                if part.getSize(unit="MB") <= 1.0:
                    if not part.active or not device.bootable:
                        part = part.nextPartition()
                        continue

                stripe.add(device)
                if device and device.isExtended:
                    if extendedParent:
                        raise RuntimeError, ("can't handle more than "
                                             "one extended partition per disk")
                    extendedParent = self.tree.append(parent)
                    iter = extendedParent
                elif device and device.isLogical:
                    if not extendedParent:
                        raise RuntimeError, ("crossed logical partition "
                                             "before extended")
                    iter = self.tree.append(extendedParent)
                    self.tree[iter]['IsLeaf'] = True
                else:
                    iter = self.tree.append(parent)
                    self.tree[iter]['IsLeaf'] = True

                if device and device.format.type == "luks":
                    # look up the mapped/decrypted device in the tree
                    # the format we care about will be on it
                    try:
                        dm_dev = self.storage.devicetree.getChildren(device)[0]
                    except IndexError:
                        format = device.format
                    else:
                        format = dm_dev.format
                elif device:
                    format = device.format
                else:
                    format = None

                if format and format.mountable and format.mountpoint:
                    self.tree[iter]['Mount Point'] = format.mountpoint
                else:
                    self.tree[iter]['Mount Point'] = ""

		if format and format.type == "lvmpv":
		    vg = None
                    for _vg in self.storage.vgs:
                        if _vg.dependsOn(part):
                            vg = _vg
                            break
		    if vg and vg.name:
			if self.show_uneditable:
			    self.tree[iter]['Mount Point'] = vg.name
			else:
			    self.tree.appendToHiddenPartitionsList(part)
			    self.tree.remove(iter)
                            part = part.nextPartition()
			    continue
		    else:
			self.tree[iter]['Mount Point'] = ""

                if device and device.format and \
                   device.format.type == "luks" and \
                   not device.format.exists:
                    self.tree[iter]['Format'] = self.lock_pixbuf
                elif format and not format.exists:
                    self.tree[iter]['Format'] = self.checkmark_pixbuf
		
                if format and format.type:
                    self.tree[iter]['IsFormattable'] = device.format.formattable

                if device and device.isExtended:
                    ptype = _("Extended")
                elif format and format.type == "mdmember":
                    ptype = _("software RAID")
                    mds = self.storage.mdarrays
                    array = None
                    for _array in mds:
                        if _array.dependsOn(device):
                            array = _array
                            break
		    if array:
			if self.show_uneditable:
                            if array.minor is not None:
                                mddevice = "%s" % array.path
                            else:
                                mddevice = "Auto"
				mddevice = "Auto"
			    self.tree[iter]['Mount Point'] = mddevice
			else:
			    self.tree.appendToHiddenPartitionsList(part)
			    self.tree.remove(iter)
			    part = part.nextPartition()
			    continue
		    else:
			self.tree[iter]['Mount Point'] = ""

                    if device.format.type == "luks" and \
                       not device.format.exists:
			self.tree[iter]['Format'] = self.lock_pixbuf
                else:
                    if format and format.type:
                        ptype = format.name
                    else:
                        ptype = _("None")
                if part.type & parted.PARTITION_FREESPACE:
                    devname = _("Free")
                else:
                    devname = "%s" % device.path
                self.tree[iter]['Device'] = devname
                if format and format.exists and \
                   getattr(format, "label", None):
                    self.tree[iter]['Label'] = "%s" % format.label
                else:
                    self.tree[iter]['Label'] = ""

                self.tree[iter]['Type'] = ptype
                size = part.getSize(unit="MB")
                if size < 1.0:
                    sizestr = "< 1"
                else:
                    sizestr = "%Ld" % (size)
                self.tree[iter]['Size (MB)'] = sizestr
                self.tree[iter]['PyObject'] = device

                part = part.nextPartition()

        canvas = self.diskStripeGraph.getCanvas()
        apply(canvas.set_scroll_region, canvas.root().get_bounds())
        self.treeView.expand_all()

    def treeActivateCB(self, view, path, col):
        if isinstance(self.tree.getCurrentDevice(),
                      storage.devices.PartitionDevice):
            self.editCB()

    def treeSelectCB(self, selection, *args):
        model, iter = selection.get_selected()
        if not iter:
            return
        device = model[iter]['PyObject']
        if device:
            if not isinstance(device, PartitionDevice):
                return

            self.diskStripeGraph.selectSlice(device)

    def newCB(self, widget):
        device = self.storage.newPartition(fmt_type=self.storage.defaultFSType,
                                           size=200)
        self.editPartition(device, isNew=1)

    def deleteCB(self, widget):
        """ Right now we can say that if the device is partitioned we
            want to delete all of the devices it contains. At some point
            we will want to support creation and removal of partitionable
            devices. This will need some work when that time comes.
        """
        device = self.tree.getCurrentDevice()
        if hasattr(device, "partedDisk"):
            if doDeleteDependentDevices(self.intf,
                                        self.storage,
                                        device):
                self.refresh()
        elif doDeleteDevice(self.intf,
                            self.storage,
                            device):
            if isinstance(device, storage.devices.DiskDevice) or \
               isinstance(device, storage.devices.PartitionDevice):
                justRedraw = False
            else:
                justRedraw = True

            self.refresh(justRedraw=justRedraw)
                
    def resetCB(self, *args):
        if not confirmResetPartitionState(self.intf):
            return
        
        self.diskStripeGraph.shutDown()
        self.storage.reset()
        self.tree.clear()
        self.populate()

    def refresh(self, justRedraw=None):
        log.debug("refresh: justRedraw=%s" % justRedraw)
        self.diskStripeGraph.shutDown()
        self.tree.clear()

        if justRedraw:
            rc = 0
        else:
            try:
                doPartitioning(self.storage)
                rc = 0
            except PartitioningError, msg:
                self.intf.messageWindow(_("Error Partitioning"),
                       _("Could not allocate requested partitions: %s.") % (msg),
                                        custom_icon="error")
                rc = -1
            except PartitioningWarning, msg:
                # XXX somebody other than me should make this look better
                # XXX this doesn't handle the 'delete /boot partition spec' case
                #     (it says 'add anyway')
                dialog = gtk.MessageDialog(self.parent, 0, gtk.MESSAGE_WARNING,
                                           gtk.BUTTONS_NONE,
                                           _("Warning: %s.") % (msg))
                gui.addFrame(dialog)
                button = gtk.Button(_("_Modify Partition"))
                dialog.add_action_widget(button, 1)
                button = gtk.Button(_("_Continue"))
                dialog.add_action_widget(button, 2)
                dialog.set_position(gtk.WIN_POS_CENTER)

                dialog.show_all()
                rc = dialog.run()
                dialog.destroy()
                
                if rc == 1:
                    rc = -1
                else:
                    rc = 0
                    all_devices = self.storage.devicetree.devices.values()
                    bootDevs = [d for d in all_devices if d.bootable]
                    #if reqs:
                    #    for req in reqs:
                    #        req.ignoreBootConstraints = 1

	if not rc == -1:
	    self.populate()

        return rc

    def editCB(self, *args):
        device = self.tree.getCurrentDevice()
        if not device:
            self.intf.messageWindow(_("Unable To Edit"),
                               _("You must select a device to edit"),
                               custom_icon="error")
            return

        reason = self.storage.deviceImmutable(device, ignoreProtected=True)
        if reason:
            self.intf.messageWindow(_("Unable To Edit"),
                                    _("You cannot edit this device:\n\n%s")
                                    % reason,
                                    custom_icon="error")
            return

        if device.type == "mdarray":
            self.editRaidArray(device)
        elif device.type == "lvmvg":
            self.editLVMVolumeGroup(device)
        elif device.type == "lvmlv":
            self.editLVMVolumeGroup(device)
        elif isinstance(device, storage.devices.PartitionDevice):
            self.editPartition(device)

    # isNew implies that this request has never been successfully used before
    def editRaidArray(self, raiddev, isNew = 0):
	raideditor = raid_dialog_gui.RaidEditor(self.storage,
						self.intf,
						self.parent,
                                                raiddev,
						isNew)
	
	while 1:
	    actions = raideditor.run()

            for action in actions:
                # FIXME: this needs to handle exceptions
                self.storage.devicetree.registerAction(action)

	    if self.refresh(justRedraw=True):
                actions.reverse()
                for action in actions:
                    self.storage.devicetree.cancelAction(action)
                    if self.refresh():
                        raise RuntimeError, ("Returning partitions to state "
                                             "prior to RAID edit failed")
                continue
	    else:
		break

	raideditor.destroy()		


    def editPartition(self, device, isNew = 0, restrictfs = None):
	parteditor = partition_dialog_gui.PartitionEditor(self.anaconda,
							  self.parent,
							  device,
							  isNew = isNew,
                                                          restrictfs = restrictfs)

	while 1:
	    actions = parteditor.run()

            for action in actions:
                # XXX we should handle exceptions here
                self.anaconda.id.storage.devicetree.registerAction(action)

            if self.refresh(justRedraw=not actions):
                # autopart failed -- cancel the actions and try to get
                # back to previous state
                actions.reverse()
                for action in actions:
                    self.anaconda.id.storage.devicetree.cancelAction(action)

                if self.refresh():
                    # this worked before and doesn't now...
                    raise RuntimeError, ("Returning partitions to state "
                                         "prior to edit failed")
            else:
		break

	parteditor.destroy()
	return 1

    def editLVMVolumeGroup(self, device, isNew = 0):
        # we don't really need to pass in self.storage if we're passing
        # self.anaconda already
        vgeditor = lvm_dialog_gui.VolumeGroupEditor(self.anaconda,
                                                    self.intf,
                                                    self.parent,
                                                    device,
                                                    isNew)
	
	while True:
	    actions = vgeditor.run()

            for action in actions:
                # FIXME: handle exceptions
                self.storage.devicetree.registerAction(action)

	    if self.refresh(justRedraw=True):
                actions.reverse()
                for action in actions:
                    self.storage.devicetree.cancelAction(action)

                if self.refresh():
                    raise RuntimeError, ("Returning partitions to state "
                                         "prior to edit failed")
		continue
	    else:
		break

	vgeditor.destroy()


    def makeLvmCB(self, widget):
        if not getFormat("lvmpv").supported or not lvm.has_lvm():
	    self.intf.messageWindow(_("Not supported"),
				    _("LVM is NOT supported on "
				      "this platform."), type="ok",
				    custom_icon="error")
	    return

        vg = self.storage.newVG()
        self.editLVMVolumeGroup(vg, isNew = 1)
	return

    def makeraidCB(self, widget):
        if not getFormat("software RAID").supported:
	    self.intf.messageWindow(_("Not supported"),
				    _("Software RAID is NOT supported on "
				      "this platform."), type="ok",
				    custom_icon="error")
	    return

	availminors = self.storage.unusedMDMinors
	if len(availminors) < 1:
	    self.intf.messageWindow(_("No RAID minor device numbers available"),
				    _("A software RAID device cannot "
				      "be created because all of the "
				      "available RAID minor device numbers "
				      "have been used."),
				    type="ok", custom_icon="error")
	    return
	    
	
	# see if we have enough free software RAID partitions first
	# if no raid partitions exist, raise an error message and return
	availraidparts = self.storage.unusedMDMembers()

	dialog = gtk.Dialog(_("RAID Options"), self.parent)
	gui.addFrame(dialog)
	dialog.add_button('gtk-cancel', 2)
	dialog.add_button('gtk-ok', 1)
        dialog.set_position(gtk.WIN_POS_CENTER)
	
        maintable = gtk.Table()
        maintable.set_row_spacings(5)
        maintable.set_col_spacings(5)
        row = 0

	lbltxt = _("Software RAID allows you to combine "
		   "several disks into a larger "
		   "RAID device.  A RAID device can be configured to "
		   "provide additional speed and "
		   "reliability compared to using an individual drive.  "
		   "For more information on using RAID devices "
		   "please consult the %s documentation.\n\n"
		   "You currently have %s software RAID "
		   "partition(s) free to use.\n\n") % (productName, len(availraidparts))

        if len(availraidparts) < 2:
	    lbltxt = lbltxt + _("To use RAID you must first "
				"create at least two partitions of type "
				"'software RAID'.  Then you can "
				"create a RAID device that can "
				"be formatted and mounted.\n\n")
	    
	lbltxt = lbltxt + _("What do you want to do now?")
	
	lbl = gui.WrappingLabel(lbltxt)
	maintable.attach(lbl, 0, 1, row, row + 1)
	row = row + 1
	
	newminor = availminors[0]
        radioBox = gtk.VBox (False)

        createRAIDpart = gtk.RadioButton(None, _("Create a software RAID _partition."))
	radioBox.pack_start(createRAIDpart, False, False, padding=10)
        createRAIDdev = gtk.RadioButton(createRAIDpart,
		    _("Create a RAID _device [default=/dev/md%s].") % newminor)
	radioBox.pack_start(createRAIDdev, False, False, padding=10)

        doRAIDclone = gtk.RadioButton(createRAIDpart,
				      _("Clone a _drive to create a "
					"RAID device [default=/dev/md%s].") % newminor)
	radioBox.pack_start(doRAIDclone, False, False, padding=10)

        createRAIDpart.set_active(1)
        doRAIDclone.set_sensitive(0)
        createRAIDdev.set_sensitive(0)
        if len(availraidparts) > 0 and len(self.storage.disks) > 1:
            doRAIDclone.set_sensitive(1)

        if len(availraidparts) > 1:
            createRAIDdev.set_active(1)
	    createRAIDdev.set_sensitive(1)

	align = gtk.Alignment(0.5, 0.0)
	align.add(radioBox)
	maintable.attach(align,0,1,row, row+1)
	row = row + 1

	maintable.show_all()
	dialog.vbox.pack_start(maintable)
	dialog.show_all()
	rc = dialog.run()
	dialog.destroy()
	if rc == 2:
	    return

	# see which option they choose
	if createRAIDpart.get_active():
            member = self.storage.newPartition(fmt_type="software RAID",
                                               size=200)
	    rc = self.editPartition(member,
                                    isNew = 1,
                                    restrictfs=["mdmember"])
	elif createRAIDdev.get_active():
	    array = self.storage.newMDArray(fmt_type=self.storage.defaultFSType)
	    self.editRaidArray(array, isNew=1)
	else:
            cloneDialog = raid_dialog_gui.RaidCloneDialog(self.storage,
                                                          self.intf,
                                                          self.parent)
            if cloneDialog is None:
                self.intf.messageWindow(_("Couldn't Create Drive Clone Editor"),
                                        _("The drive clone editor could not "
                                          "be created for some reason."),
					custom_icon="error")
                return
            
            if cloneDialog.run():
                self.refresh()

            cloneDialog.destroy()
	    return

    def viewButtonCB(self, widget):
	self.show_uneditable = not widget.get_active()
        self.diskStripeGraph.shutDown()
	self.tree.clear()
	self.populate()

    def getScreen(self, anaconda):
        self.anaconda = anaconda
        self.storage = anaconda.id.storage
        self.intf = anaconda.intf
        
	self.show_uneditable = 1

        checkForSwapNoMatch(anaconda)

	# load up checkmark
	self.checkmark_pixbuf = gtk.gdk.pixbuf_new_from_inline(len(new_checkmark), new_checkmark, False)
        self.lock_pixbuf = gui.getPixbuf("gnome-lock.png")

        # operational buttons
        buttonBox = gtk.HButtonBox()
        buttonBox.set_layout(gtk.BUTTONBOX_SPREAD)

        ops = ((_("Ne_w"), self.newCB),
               (_("_Edit"), self.editCB),
               (_("_Delete"), self.deleteCB),
               (_("Re_set"), self.resetCB),
               (_("R_AID"), self.makeraidCB),
               (_("_LVM"), self.makeLvmCB))
        
        for label, cb in ops:
            button = gtk.Button(label)
            buttonBox.add (button)
            button.connect ("clicked", cb)

        self.tree = DiskTreeModel()
        self.treeView = self.tree.getTreeView()
        self.treeView.connect('row-activated', self.treeActivateCB)
        self.treeViewSelection = self.treeView.get_selection()
        self.treeViewSelection.connect("changed", self.treeSelectCB)

        # set up the canvas
        self.diskStripeGraph = DiskStripeGraph(self.tree, self.editCB)
        
        # do the initial population of the tree and the graph
        self.populate(initial = 1)

	vpaned = gtk.VPaned()

        hadj = gtk.Adjustment(step_incr = 5.0)
        vadj = gtk.Adjustment(step_incr = 5.0)
        sw = gtk.ScrolledWindow(hadjustment = hadj, vadjustment = vadj)
        sw.add(self.diskStripeGraph.getCanvas())
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
            
        frame = gtk.Frame()
        frame.add(sw)
	vpaned.add1(frame)

        box = gtk.VBox(False, 5)
        box.pack_start(buttonBox, False)
        sw = gtk.ScrolledWindow()
        sw.add(self.treeView)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
	sw.set_shadow_type(gtk.SHADOW_IN)
	
        box.pack_start(sw, True)

	self.toggleViewButton = gtk.CheckButton(_("Hide RAID device/LVM Volume _Group members"))
	self.toggleViewButton.set_active(not self.show_uneditable)
	self.toggleViewButton.connect("toggled", self.viewButtonCB)
	box.pack_start(self.toggleViewButton, False, False)
	
	vpaned.add2(box)

	# XXX should probably be set according to height 
	vpaned.set_position(175)

	return vpaned
