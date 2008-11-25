#
# partition_gui.py: allows the user to choose how to partition their disks
#
# Matt Wilson <msw@redhat.com>
# Michael Fulbright <msf@redhat.com>
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

import gobject
import gtk
try:
    import gnomecanvas
except ImportError:
    import gnome.canvas as gnomecanvas
import pango
import autopart
import gui
import parted
import string
import copy
import types
import raid
from constants import *
import lvm
import isys

from iw_gui import *
from flags import flags

import lvm_dialog_gui
import raid_dialog_gui
import partition_dialog_gui

from rhpl.translate import _, N_
from partitioning import *
from partIntfHelpers import *
from partedUtils import *
from fsset import *
from partRequests import *
from constants import *
from partition_ui_helpers_gui import *

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
            self.editCb()
                
        return True

    def shutDown(self):
        self.parent = None
        if self.group:
            self.group.destroy()
            self.group = None
        del self.partition

    def select(self):
        if self.partition.type != parted.PARTITION_EXTENDED:
            self.group.raise_to_top()
        self.box.set(outline_color="red")
        self.box.set(fill_color=self.selectColor())

    def deselect(self):
        self.box.set(outline_color="black", fill_color=self.fillColor())

    def getPartition(self):
        return self.partition

    def fillColor(self):
        if self.partition.type & parted.PARTITION_FREESPACE:
            return "grey88"
        return "white"

    def selectColor(self):
        if self.partition.type & parted.PARTITION_FREESPACE:
            return "cornsilk2"
        return "cornsilk1"

    def hideOrShowText(self):
        return
        if self.box.get_bounds()[2] < self.text.get_bounds()[2]:
            self.text.hide()
        else:
            self.text.show()

    def sliceText(self):
        if self.partition.type & parted.PARTITION_EXTENDED:
            return ""
        if self.partition.type & parted.PARTITION_FREESPACE:
            rc = "Free\n"
        else:
            rc = "%s\n" % (get_partition_name(self.partition),)
        rc = rc + "%Ld MB" % (getPartSizeMB(self.partition),)
        return rc

    def getDeviceName(self):
        return get_partition_name(self.partition)

    def update(self):
        disk = self.parent.getDisk()
        totalSectors = float(disk.dev.heads
                             * disk.dev.sectors
                             * disk.dev.cylinders)

        # XXX hack but will work for now
        if gtk.gdk.screen_width() > 640:
            width = CANVAS_WIDTH_800
        else:
            width = CANVAS_WIDTH_640

        xoffset = self.partition.geom.start / totalSectors * width
        xlength = self.partition.geom.length / totalSectors * width
        if self.partition.type & parted.PARTITION_LOGICAL:
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
        self.hideOrShowText()
       
    def __init__(self, parent, partition, treeView, editCb):
        self.text = None
        self.partition = partition
        self.parent = parent
        self.treeView = treeView
        self.editCb = editCb
        pgroup = parent.getGroup()

        self.group = pgroup.add(gnomecanvas.CanvasGroup)
        self.box = self.group.add(gnomecanvas.CanvasRect)
        self.group.connect("event", self.eventHandler)
        self.text = self.group.add(gnomecanvas.CanvasText,
                                    font="sans", size_points=8)
        self.update()

class DiskStripe:
    def __init__(self, drive, disk, group, tree, editCb):
        self.disk = disk
        self.group = group
        self.tree = tree
        self.drive = drive
        self.slices = []
        self.hash = {}
        self.editCb = editCb
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
        stripe = DiskStripeSlice(self, partition, self.tree, self.editCb)
        self.slices.append(stripe)
        self.hash[partition] = stripe

class DiskStripeGraph:
    def __init__(self, tree, editCb):
        self.canvas = gnomecanvas.Canvas()
        self.diskStripes = []
        self.textlabels = []
        self.tree = tree
        self.editCb = editCb
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
#        yoff = len(self.diskStripes) * (STRIPE_HEIGHT + 5)
        yoff = self.next_ypos
        text = self.canvas.root().add(gnomecanvas.CanvasText,
                                      x=0.0, y=yoff,
                                      font="sans",
                                      size_points=9)
	show_geometry = 0
        if drive.find('mapper/mpath') != -1:
            modelInfo = isys.getMpathModel(drive)
        else:
            modelInfo = disk.dev.model
	if show_geometry:
	    drivetext = _("Drive %s (Geom: %s/%s/%s) "
			 "(Model: %s)") % ('/dev/' + drive,
					   disk.dev.cylinders,
					   disk.dev.heads,
					   disk.dev.sectors,
					   modelInfo)
	else:
	    drivetext = _("Drive %s (%-0.f MB) "
			 "(Model: %s)") % ('/dev/' + drive,
					   partedUtils.getDeviceSizeMB(disk.dev),
					   modelInfo)


        text.set(text=drivetext, fill_color='black', anchor=gtk.ANCHOR_NW,
                 weight=pango.WEIGHT_BOLD)
        (xxx1, yyy1, xxx2, yyy2) =  text.get_bounds()
        textheight = yyy2 - yyy1 + 2
        self.textlabels.append(text)
        group = self.canvas.root().add(gnomecanvas.CanvasGroup,
                                       x=0, y=yoff+textheight)
        stripe = DiskStripe(drive, disk, group, self.tree, self.editCb)
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
              (N_("Mount Point"), gobject.TYPE_STRING, 0.0, 0, isLeaf),
              (N_("Type"), gobject.TYPE_STRING, 0.0, 0, 0),
#              (N_("Format"), gobject.TYPE_BOOLEAN, 0.5, 0, isFormattable),
#              (N_("Size (MB)"), gobject.TYPE_STRING, 1.0, 0, isLeaf),
              (N_("Format"), gobject.TYPE_OBJECT, 0.5, 0, isFormattable),
              (N_("Size (MB)"), gobject.TYPE_STRING, 1.0, 0, 0),
              (N_("Start"), gobject.TYPE_STRING, 1.0, 0, 1),
              (N_("End"), gobject.TYPE_STRING, 1.0, 0, 1),
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

    """ returns partition 'id' of current selection in tree """
    def getCurrentPartition(self):
        selection = self.view.get_selection()
        model, iter = selection.get_selected()
        if not iter:
            return None

        pyobject = self.titleSlot['PyObject']
	try:
            val = self.get_value(iter, pyobject)
            if type(val) == type("/dev/"):
                if val[:5] == '/dev/':
                    return None

            return val
        except:
            return None

    """ Return name of current selected drive (if a drive is highlighted) """
    def getCurrentDevice(self):
        selection = self.view.get_selection()
        model, iter = selection.get_selected()
        if not iter:
            return None

        pyobject = self.titleSlot['PyObject']
	try:
            val = self.get_value(iter, pyobject)
            if type(val) == type("/dev/"):
                if val[:5] == '/dev/':
                    return val
            return None
        except:
            return None

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
        (errors, warnings) = self.partitions.sanityCheckAllRequests(self.diskset)

        if errors:
            labelstr1 =  _("The following critical errors exist "
                           "with your requested partitioning "
                           "scheme.")
            labelstr2 = _("These errors must be corrected prior "
                          "to continuing with your install of "
                          "%s.") % (productName,)

            commentstr = string.join(errors, "\n\n")
            
            self.presentPartitioningComments(_("Partitioning Errors"),
                                             labelstr1, labelstr2,
                                             commentstr, type="ok")
            raise gui.StayOnScreen
        
        if warnings:
            labelstr1 = _("The following warnings exist with "
                         "your requested partition scheme.")
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

        formatWarnings = getPreExistFormatWarnings(self.partitions,
                                                   self.diskset)
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
                        "/dev/%s         %s         %s\n" % (dev,type,mntpt)

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
        self.tree.clear()
        del self.parent
        return None

    def getShortFSTypeName(self, name):
	if name == "physical volume (LVM)":
	    return "LVM PV"

	return name
    
    def populate(self, initial = 0):

        drives = self.diskset.disks.keys()
        drives.sort()

        self.tree.resetSelection()

	self.tree.clearHiddenPartitionsList()

	# first do LVM
        lvmrequests = self.partitions.getLVMRequests()
        if lvmrequests:
	    lvmparent = self.tree.append(None)
	    self.tree[lvmparent]['Device'] = _("LVM Volume Groups")
            for vgname in lvmrequests.keys():
		vgrequest = self.partitions.getRequestByVolumeGroupName(vgname)
		rsize = vgrequest.getActualSize(self.partitions, self.diskset)

                vgparent = self.tree.append(lvmparent)
		self.tree[vgparent]['Device'] = "%s" % (vgname,)
		self.tree[vgparent]['Mount Point'] = ""
		self.tree[vgparent]['Start'] = ""
		self.tree[vgparent]['End'] = ""
		self.tree[vgparent]['Size (MB)'] = "%Ld" % (rsize,)
                self.tree[vgparent]['PyObject'] = str(vgrequest.uniqueID)
		for lvrequest in lvmrequests[vgname]:
		    iter = self.tree.append(vgparent)
		    self.tree[iter]['Device'] = lvrequest.logicalVolumeName
		    if lvrequest.fstype and lvrequest.mountpoint:
			self.tree[iter]['Mount Point'] = lvrequest.mountpoint
		    else:
			self.tree[iter]['Mount Point'] = ""
		    self.tree[iter]['Size (MB)'] = "%Ld" % (lvrequest.getActualSize(self.partitions, self.diskset),)
		    self.tree[iter]['PyObject'] = str(lvrequest.uniqueID)
		
                    ptype = lvrequest.fstype.getName()
                    if lvrequest.isEncrypted(self.partitions, True) and lvrequest.format:
			self.tree[iter]['Format'] = self.lock_pixbuf
                    elif lvrequest.format:
			self.tree[iter]['Format'] = self.checkmark_pixbuf
                    self.tree[iter]['IsFormattable'] = lvrequest.fstype.isFormattable()
		    self.tree[iter]['IsLeaf'] = True
		    self.tree[iter]['Type'] = ptype
		    self.tree[iter]['Start'] = ""
		    self.tree[iter]['End'] = ""

        # handle RAID next
        raidrequests = self.partitions.getRaidRequests()
        if raidrequests:
	    raidparent = self.tree.append(None)
	    self.tree[raidparent]['Device'] = _("RAID Devices")
            for request in raidrequests:
		mntpt = None
		if request and request.fstype and request.fstype.getName() == "physical volume (LVM)":
		    vgreq = self.partitions.getLVMVolumeGroupMemberParent(request)
		    if vgreq and vgreq.volumeGroupName:
			if self.show_uneditable:
			    mntpt = vgreq.volumeGroupName
			else:
			    self.tree.appendToHiddenPartitionsList(str(request.uniqueID))
			    continue
		    else:
			mntpt = ""

                iter = self.tree.append(raidparent)
		if mntpt:
                    self.tree[iter]["Mount Point"] = mntpt
		    
                if request and request.mountpoint:
                    self.tree[iter]["Mount Point"] = request.mountpoint
		    
                if request.fstype:
                    ptype = self.getShortFSTypeName(request.fstype.getName())

                    if request.isEncrypted(self.partitions, True) and request.format:
                        self.tree[iter]['Format'] = self.lock_pixbuf
                    elif request.format:
                        self.tree[iter]['Format'] = self.checkmark_pixbuf
                    self.tree[iter]['IsFormattable'] = request.fstype.isFormattable()
                else:
                    ptype = _("None")
                    self.tree[iter]['IsFormattable'] = False

		try:
		    device = "/dev/md%d" % (request.raidminor,)
		except:
		    device = "Auto"
		    
                self.tree[iter]['IsLeaf'] = True
                self.tree[iter]['Device'] = device
                self.tree[iter]['Type'] = ptype
                self.tree[iter]['Start'] = ""
                self.tree[iter]['End'] = ""
                self.tree[iter]['Size (MB)'] = "%Ld" % (request.getActualSize(self.partitions, self.diskset),)
                self.tree[iter]['PyObject'] = str(request.uniqueID)
                
	# now normal partitions
	drvparent = self.tree.append(None)
	self.tree[drvparent]['Device'] = _("Hard Drives")
        for drive in drives:
            disk = self.diskset.disks[drive]

            # add a disk stripe to the graph
            stripe = self.diskStripeGraph.add(drive, disk)

            # add a parent node to the tree
            parent = self.tree.append(drvparent)
            self.tree[parent]['Device'] = '/dev/%s' % (drive,)
            self.tree[parent]['PyObject'] = str('/dev/%s' % (drive,))
            sectorsPerCyl = disk.dev.heads * disk.dev.sectors

            extendedParent = None
            part = disk.next_partition()
            while part:
                if part.type & parted.PARTITION_METADATA:
                    part = disk.next_partition(part)
                    continue
                # ignore the tiny < 1 MB partitions (#119479)
                if getPartSizeMB(part) <= 1.0:
                    if not part.is_active() or not part.get_flag(parted.PARTITION_BOOT):
                        part = disk.next_partition(part)                    
                        continue

                stripe.add(part)
                device = get_partition_name(part)
                request = self.partitions.getRequestByDeviceName(device)

                if part.type == parted.PARTITION_EXTENDED:
                    if extendedParent:
                        raise RuntimeError, ("can't handle more than "
                                             "one extended partition per disk")
                    extendedParent = self.tree.append(parent)
                    iter = extendedParent
                elif part.type & parted.PARTITION_LOGICAL:
                    if not extendedParent:
                        raise RuntimeError, ("crossed logical partition "
                                             "before extended")
                    iter = self.tree.append(extendedParent)
                    self.tree[iter]['IsLeaf'] = True
                else:
                    iter = self.tree.append(parent)
                    self.tree[iter]['IsLeaf'] = True
                    
                if request and request.mountpoint:
                    self.tree[iter]['Mount Point'] = request.mountpoint
                else:
                    self.tree[iter]['Mount Point'] = ""

		if request and request.fstype and request.fstype.getName() == "physical volume (LVM)":
		    vgreq = self.partitions.getLVMVolumeGroupMemberParent(request)
		    if vgreq and vgreq.volumeGroupName:
			if self.show_uneditable:
			    self.tree[iter]['Mount Point'] = vgreq.volumeGroupName
			else:
			    self.tree.appendToHiddenPartitionsList(part)
			    part = disk.next_partition(part)
			    self.tree.remove(iter)
			    continue
		    else:
			self.tree[iter]['Mount Point'] = ""

                    if request and request.isEncrypted(self.partitions, True) and request.format:
                        self.tree[iter]['Format'] = self.lock_pixbuf
                    elif request and request.format:
                        self.tree[iter]['Format'] = self.checkmark_pixbuf

			
                if request and request.fstype:
                    self.tree[iter]['IsFormattable'] = request.fstype.isFormattable()
                
                if part.type & parted.PARTITION_FREESPACE:
                    ptype = _("Free space")
                elif part.type == parted.PARTITION_EXTENDED:
                    ptype = _("Extended")
                elif part.get_flag(parted.PARTITION_RAID) == 1:
                    ptype = _("software RAID")
		    parreq = self.partitions.getRaidMemberParent(request)
		    if parreq:
			if self.show_uneditable:
			    try:
				mddevice = "/dev/md%d" % (parreq.raidminor,)
			    except:
				mddevice = "Auto"
			    self.tree[iter]['Mount Point'] = mddevice
			else:
			    self.tree.appendToHiddenPartitionsList(part)
			    part = disk.next_partition(part)
			    self.tree.remove(iter)
			    continue
		    else:
			self.tree[iter]['Mount Point'] = ""
                elif part.fs_type:
                    if request and request.fstype != None:
                        ptype = self.getShortFSTypeName(request.fstype.getName())
                        if ptype == "foreign":
                            ptype = map_foreign_to_fsname(part.native_type)
                    else:
                        ptype = part.fs_type.name

                    if request and request.isEncrypted(self.partitions, True) and request.format:
			self.tree[iter]['Format'] = self.lock_pixbuf
                    elif request and request.format:
			self.tree[iter]['Format'] = self.checkmark_pixbuf
                else:
                    if request and request.fstype != None:
                        ptype = self.getShortFSTypeName(request.fstype.getName())
                        
                        if ptype == "foreign":
                            ptype = map_foreign_to_fsname(part.native_type)
                    else:
                        ptype = _("None")
                if part.type & parted.PARTITION_FREESPACE:
                    devname = _("Free")
                else:
                    devname = '/dev/%s' % (device,)
                self.tree[iter]['Device'] = devname
                self.tree[iter]['Type'] = ptype
                self.tree[iter]['Start'] = str(start_sector_to_cyl(disk.dev,
                                                                   part.geom.start))
                self.tree[iter]['End'] = str(end_sector_to_cyl(disk.dev,
                                                               part.geom.end))
                size = getPartSizeMB(part)
                if size < 1.0:
                    sizestr = "< 1"
                else:
                    sizestr = "%Ld" % (size)
                self.tree[iter]['Size (MB)'] = sizestr
                self.tree[iter]['PyObject'] = part
                
                part = disk.next_partition(part)

        canvas = self.diskStripeGraph.getCanvas()
        apply(canvas.set_scroll_region, canvas.root().get_bounds())
        self.treeView.expand_all()

    def treeActivateCb(self, view, path, col):
        if self.tree.getCurrentPartition():
            self.editCb()
        
    def treeSelectCb(self, selection, *args):
        model, iter = selection.get_selected()
        if not iter:
            return
        partition = model[iter]['PyObject']
        if partition:
            self.diskStripeGraph.selectSlice(partition)

    def newCB(self, widget):
        # create new request of size 1M
        request = NewPartitionSpec(fileSystemTypeGetDefault(), size = 100)

        self.editPartitionRequest(request, isNew = 1)

    def deleteCb(self, widget):
        curselection = self.tree.getCurrentPartition()

        if curselection:
            if doDeletePartitionByRequest(self.intf, self.partitions, curselection):
                self.refresh()
        else:
            curdevice = self.tree.getCurrentDevice()
            if curdevice and len(curdevice) > 5:
                if doDeletePartitionsByDevice(self.intf, self.partitions, self.diskset, curdevice[5:]):
                    self.refresh()
                else:
                    return
                
    def resetCb(self, *args):
        if not confirmResetPartitionState(self.intf):
            return
        
        self.diskStripeGraph.shutDown()
        self.newFsset = self.fsset.copy()
        self.diskset.refreshDevices()
        self.partitions.setFromDisk(self.diskset)
        self.tree.clear()
        self.populate()

    def refresh(self):
        self.diskStripeGraph.shutDown()
        self.tree.clear()

	# XXXX - Backup some info which doPartitioning munges if it fails
	origInfoDict = {}
	for request in self.partitions.requests:
	    try:
		origInfoDict[request.uniqueID] = (request.requestSize, request.currentDrive)
	    except:
		pass

        try:
            autopart.doPartitioning(self.diskset, self.partitions)
            rc = 0
        except PartitioningError, msg:
	    try:
		for request in self.partitions.requests:
		    if request.uniqueID in origInfoDict.keys():
			(request.requestSize, request.currentDrive) = origInfoDict[request.uniqueID]
	    except:
		log.error("Failed to restore original info")

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
                reqs = self.partitions.getBootableRequest()
                if reqs:
                    for req in reqs:
                        req.ignoreBootConstraints = 1

	if not rc == -1:
	    self.populate()

        return rc

    def editCb(self, *args):
        part = self.tree.getCurrentPartition()

        (type, request) = doEditPartitionByRequest(self.intf, self.partitions,
                                                   part)
        if request:
            if type == "RAID":
                self.editRaidRequest(request)
	    elif type == "LVMVG":
		self.editLVMVolumeGroup(request)
	    elif type == "LVMLV":
		vgrequest = self.partitions.getRequestByID(request.volumeGroup)
		self.editLVMVolumeGroup(vgrequest)
            elif type == "NEW":
		self.editPartitionRequest(request, isNew = 1)
            else:
                self.editPartitionRequest(request)

    # isNew implies that this request has never been successfully used before
    def editRaidRequest(self, raidrequest, isNew = 0):
	raideditor = raid_dialog_gui.RaidEditor(self.partitions,
						     self.diskset, self.intf,
						     self.parent, raidrequest,
						     isNew)
	origpartitions = self.partitions.copy()
	
	while 1:
	    request = raideditor.run()

	    if request is None:
		return

	    if not isNew:
		self.partitions.removeRequest(raidrequest)
                if raidrequest.getPreExisting():
                    delete = partRequests.DeleteRAIDSpec(raidrequest.raidminor)
                    self.partitions.addDelete(delete)

	    self.partitions.addRequest(request)

	    if self.refresh():
		if not isNew:
		    self.partitions = origpartitions.copy()
                    if self.refresh():
                        raise RuntimeError, ("Returning partitions to state "
                                             "prior to RAID edit failed")
                continue
	    else:
		break

	raideditor.destroy()		


    def editPartitionRequest(self, origrequest, isNew = 0, restrictfs = None):
	parteditor = partition_dialog_gui.PartitionEditor(self.anaconda,
							  self.parent,
							  origrequest,
							  isNew = isNew,
                                                          restrictfs = restrictfs)

	while 1:
	    request = parteditor.run()

	    if request is None:
		return 0

            if not isNew:
                self.partitions.removeRequest(origrequest)

            self.partitions.addRequest(request)
            if self.refresh():
                # the add failed; remove what we just added and put
                # back what was there if we removed it
                self.partitions.removeRequest(request)
                if not isNew:
                    self.partitions.addRequest(origrequest)
                if self.refresh():
                    # this worked before and doesn't now...
                    raise RuntimeError, ("Returning partitions to state "
                                         "prior to edit failed")
            else:
		break

	parteditor.destroy()
	return 1

    def editLVMVolumeGroup(self, origvgrequest, isNew = 0):
	vgeditor = lvm_dialog_gui.VolumeGroupEditor(self.partitions,
						    self.diskset,
						    self.intf, self.parent,
						    origvgrequest, isNew)
	
	origpartitions = self.partitions.copy()
	origvolreqs = origpartitions.getLVMLVForVG(origvgrequest)

	while (1):
	    rc = vgeditor.run()

	    #
	    # return code is either None or a tuple containing
	    # volume group request and logical volume requests
	    #
	    if rc is None:
		return

	    (vgrequest, logvolreqs) = rc

	    # first add the volume group
	    if not isNew:
                # if an lv was preexisting and isn't in the new lv requests,
                # we need to add a delete for it.  
                for lv in origvolreqs:
                    if not lv.getPreExisting():
                        continue
                    found = 0
                    for newlv in logvolreqs:
                        if (newlv.getPreExisting() and
                            newlv.logicalVolumeName == lv.logicalVolumeName):
                            found = 1
                            break
                    if found == 0:
                        delete = partRequests.DeleteLogicalVolumeSpec(lv.logicalVolumeName,
                                                                      origvgrequest.volumeGroupName)
                        self.partitions.addDelete(delete)
                        
		for lv in origvolreqs:
		    self.partitions.removeRequest(lv)

		self.partitions.removeRequest(origvgrequest)

	    vgID = self.partitions.addRequest(vgrequest)

	    # now add the logical volumes
	    for lv in logvolreqs:
		lv.volumeGroup = vgID
                if not lv.getPreExisting():
                    lv.format = 1
		self.partitions.addRequest(lv)

	    if self.refresh():
		if not isNew:
		    self.partitions = origpartitions.copy()
		    if self.refresh():
			raise RuntimeError, ("Returning partitions to state "
					     "prior to edit failed")
		continue
	    else:
		break

	vgeditor.destroy()



    def makeLvmCB(self, widget):
	if (not fileSystemTypeGet('physical volume (LVM)').isSupported() or
            not lvm.has_lvm()):
	    self.intf.messageWindow(_("Not supported"),
				    _("LVM is NOT supported on "
				      "this platform."), type="ok",
				    custom_icon="error")
	    return

        request = VolumeGroupRequestSpec(format = True)
        self.editLVMVolumeGroup(request, isNew = 1)

	return

    def makeraidCB(self, widget):

	if not fileSystemTypeGet('software RAID').isSupported():
	    self.intf.messageWindow(_("Not supported"),
				    _("Software RAID is NOT supported on "
				      "this platform."), type="ok",
				    custom_icon="error")
	    return

	availminors = self.partitions.getAvailableRaidMinors()
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
	request = RaidRequestSpec(fileSystemTypeGetDefault())
	availraidparts = self.partitions.getAvailRaidPartitions(request,
								self.diskset)

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
				"create a RAID device which can "
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
        if len(availraidparts) > 0 and len(self.diskset.disks.keys()) > 1:
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
	    rdrequest = NewPartitionSpec(fileSystemTypeGet("software RAID"), size = 100)
	    rc = self.editPartitionRequest(rdrequest, isNew = 1, restrictfs=["software RAID"])
	elif createRAIDdev.get_active():
	    self.editRaidRequest(request, isNew=1)
	else:
            cloneDialog = raid_dialog_gui.RaidCloneDialog(self.partitions,
                                                          self.diskset,
                                                          self.intf,
                                                          self.parent)
            if cloneDialog is None:
                self.intf.messageWindow(_("Couldn't Create Drive Clone Editor"),
                                        _("The drive clone editor could not "
                                          "be created for some reason."),
					custom_icon="error")
                return
            
            while 1:
                rc = cloneDialog.run()

		if rc:
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
        self.fsset = anaconda.id.fsset
        self.diskset = anaconda.id.diskset
        self.intf = anaconda.intf
        
        self.diskset.openDevices()
        self.partitions = anaconda.id.partitions

	self.show_uneditable = 1

        checkForSwapNoMatch(anaconda)

        # XXX PartitionRequests() should already exist and
        # if upgrade or going back, have info filled in
#        self.newFsset = self.fsset.copy()

	# load up checkmark
	self.checkmark_pixbuf = gtk.gdk.pixbuf_new_from_inline(len(new_checkmark), new_checkmark, False)
        self.lock_pixbuf = gui.getPixbuf("gnome-lock.png")

        # operational buttons
        buttonBox = gtk.HButtonBox()
        buttonBox.set_layout(gtk.BUTTONBOX_SPREAD)

        ops = ((_("Ne_w"), self.newCB),
               (_("_Edit"), self.editCb),
               (_("_Delete"), self.deleteCb),
               (_("Re_set"), self.resetCb),
               (_("R_AID"), self.makeraidCB),
               (_("_LVM"), self.makeLvmCB))
        
        for label, cb in ops:
            button = gtk.Button(label)
            buttonBox.add (button)
            button.connect ("clicked", cb)

        self.tree = DiskTreeModel()
        self.treeView = self.tree.getTreeView()
        self.treeView.connect('row-activated', self.treeActivateCb)
        self.treeViewSelection = self.treeView.get_selection()
        self.treeViewSelection.connect("changed", self.treeSelectCb)

        # set up the canvas
        self.diskStripeGraph = DiskStripeGraph(self.tree, self.editCb)
        
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
