#
# partition_gui.py: allows the user to choose how to partition their disks
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
import gnome.canvas
import pango
from gui import WrappingLabel, widgetExpander
from iw_gui import *
from translate import _, N_
from partitioning import *
from fsset import *
from autopart import doPartitioning, queryAutoPartitionOK
from autopart import CLEARPART_TYPE_LINUX_DESCR_TEXT, CLEARPART_TYPE_ALL_DESCR_TEXT, CLEARPART_TYPE_NONE_DESCR_TEXT
from autopart import AUTOPART_DISK_CHOICE_DESCR_TEXT

import gui
import parted
import string
import copy

STRIPE_HEIGHT = 32.0
LOGICAL_INSET = 3.0
CANVAS_WIDTH_800 = 500
CANVAS_WIDTH_640 = 400
CANVAS_HEIGHT = 200
TREE_SPACING = 2

MODE_ADD = 1
MODE_EDIT = 2

# XXX this is made up and used by the size spinner; should just be set with
# a callback
MAX_PART_SIZE = 1024*1024*1024

class DiskStripeSlice:
    def eventHandler(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            if event.button == 1:
                self.parent.selectSlice(self.partition, 1)
        elif event.type == gtk.gdk._2BUTTON_PRESS:
            self.editCb(self.ctree)
                
        return gtk.TRUE

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
        # XXX disable until CanvasRect's bounds function gets implemetned
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
        rc = rc + "%d MB" % (getPartSizeMB(self.partition),)
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
                      anchor=gtk.ANCHOR_NW, clip=gtk.TRUE,
                      clip_width=xlength-1, clip_height=yheight-1)
        self.hideOrShowText()
       
    def __init__(self, parent, partition, ctree, editCb):
        self.text = None
        self.partition = partition
        self.parent = parent
        self.ctree = ctree
        self.editCb = editCb
        pgroup = parent.getGroup()

        self.group = pgroup.add(gnome.canvas.CanvasGroup)
        self.box = self.group.add(gnome.canvas.CanvasRect)
        self.group.connect("event", self.eventHandler)
        self.text = self.group.add (gnome.canvas.CanvasText,
                                    font="helvetica", size_points=8)
        self.update()

class DiskStripe:
    def __init__(self, drive, disk, group, ctree, canvas, editCb):
        self.disk = disk
        self.group = group
        self.tree = ctree
        self.drive = drive
        self.canvas = canvas
        self.slices = []
        self.hash = {}
        self.editCb = editCb
        self.selected = None

        # XXX hack but will work for now
        if gtk.gdk.screen_width() > 640:
            width = CANVAS_WIDTH_800
        else:
            width = CANVAS_WIDTH_640
        
        group.add(gnome.canvas.CanvasRect, x1=0.0, y1=10.0, x2=width,
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

    def getCanvas(self):
        return self.canvas

    def selectSlice(self, partition, updateTree=0):
        self.deselect()
        slice = self.hash[partition]
        slice.select()

        # update selection of the tree
        if updateTree:
            self.tree.unselect(self.tree.selection[0])
            nodes = self.tree.base_nodes()
            for node in nodes:
                row = self.tree.find_by_row_data(node, partition)
                self.tree.select(row)
                break
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
    def __init__(self, ctree, editCb):
        self.canvas = gnome.canvas.Canvas()
        self.diskStripes = []
        self.textlabels = []
        self.ctree = ctree
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
        text = self.canvas.root().add(gnome.canvas.CanvasText,
                                      x=0.0, y=yoff,
                                      font="sans",
                                      size_points=12)
        drivetext = ("Drive %s (Geom: %s/%s/%s) "
                     "(Model: %s)") % ('/dev/' + drive,
                                       disk.dev.cylinders,
                                       disk.dev.heads,
                                       disk.dev.sectors,
                                       disk.dev.model)
        text.set(text=drivetext, fill_color='black', anchor=gtk.ANCHOR_NW,
                 weight=pango.WEIGHT_BOLD)
        (xxx1, yyy1, xxx2, yyy2) =  text.get_bounds()
        textheight = yyy2 - yyy1
        self.textlabels.append(text)
        group = self.canvas.root().add(gnome.canvas.CanvasGroup,
                                       x=0, y=yoff+textheight)
        stripe = DiskStripe(drive, disk, group, self.ctree, self.canvas,
                             self.editCb)
        self.diskStripes.append(stripe)
        self.next_ypos = self.next_ypos + STRIPE_HEIGHT+textheight+10
        return stripe


# this should probably go into a class
# some helper functions for build UI components
def createAlignedLabel(text):
    label = gtk.Label(text)
    label.set_alignment(0.0, 0.0)

    return label

def createMountPointCombo(request):
    mountCombo = gtk.Combo()
    mountCombo.set_popdown_strings(defaultMountPoints)

    mountpoint = request.mountpoint

    if request.fstype and request.fstype.isMountable():
        mountCombo.set_sensitive(1)
        if mountpoint:
            mountCombo.entry.set_text(mountpoint)
        else:
            mountCombo.entry.set_text("")
    else:
        mountCombo.entry.set_text(_("<Not Applicable>"))
        mountCombo.set_sensitive(0)

    mountCombo.set_data("saved_mntpt", None)

    return mountCombo

def setMntPtComboStateFromType(fstype, mountCombo):
    prevmountable = mountCombo.get_data("prevmountable")
    mountpoint = mountCombo.get_data("saved_mntpt")

    if prevmountable and fstype.isMountable():
        return

    if fstype.isMountable():
        mountCombo.set_sensitive(1)
        if mountpoint != None:
            mountCombo.entry.set_text(mountpoint)
        else:
            mountCombo.entry.set_text("")
    else:
        if mountCombo.entry.get_text() != _("<Not Applicable>"):
            mountCombo.set_data("saved_mntpt", mountCombo.entry.get_text())
        mountCombo.entry.set_text(_("<Not Applicable>"))
        mountCombo.set_sensitive(0)

    mountCombo.set_data("prevmountable", fstype.isMountable())
    
def fstypechangeCB(widget, mountCombo):
    fstype = widget.get_data("type")
    setMntPtComboStateFromType(fstype, mountCombo)
    
def createAllowedDrivesClist(disks, reqdrives):
    driveclist = gtk.CList()
    driveclist.set_selection_mode(gtk.SELECTION_MULTIPLE)
    driveclist.set_usize(-1, 75)

    driverow = 0
    drives = disks.keys()
    drives.sort()
    for drive in drives:
        size = getDeviceSizeMB(disks[drive].dev)
        str = "%s: %s - %0.0f MB" % (drive, disks[drive].dev.model, size)
        row = driveclist.append((str,))
        driveclist.set_row_data(row, drive)

        if reqdrives:
            if drive in reqdrives:
                driveclist.select_row(driverow, 0)
        else:
            driveclist.select_row(driverow, 0)
        driverow = driverow + 1

    return driveclist

def createAllowedRaidPartitionsClist(allraidparts, reqraidpart):

    partclist = gtk.CList()
    partclist.set_selection_mode(gtk.SELECTION_MULTIPLE)
    partclist.set_usize(-1, 95)
    sw = gtk.ScrolledWindow()
    sw.add(partclist)
    sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)

    partrow = 0
    for part, size, used in allraidparts:
        partname = "%s: %8.0f MB" % (part, size)
        partclist.append((partname,))

        if used or not reqraidpart:
            partclist.select_row(partrow, 0)
        partrow = partrow + 1

    return (partclist, sw)

def createRaidLevelMenu(levels, reqlevel, raidlevelchangeCB, sparesb):
    leveloption = gtk.OptionMenu()
    leveloptionmenu = gtk.Menu()
    defindex = None
    i = 0
    for lev in levels:
        item = gtk.MenuItem(lev)
        item.set_data("level", lev)
        leveloptionmenu.add(item)
        if reqlevel and lev == reqlevel:
            defindex = i
        if raidlevelchangeCB and sparesb:
            item.connect("activate", raidlevelchangeCB, sparesb)
        i = i + 1

    leveloption.set_menu(leveloptionmenu)
    
    if defindex:
        leveloption.set_history(defindex)

    if reqlevel and reqlevel == "RAID0":
        sparesb.set_sensitive(0)
        
    return (leveloption, leveloptionmenu)

# pass in callback for when fs changes because of python scope issues
def createFSTypeMenu(fstype, fstypechangeCB, mountCombo,
                     availablefstypes = None, ignorefs = None):
    fstypeoption = gtk.OptionMenu()
    fstypeoptionMenu = gtk.Menu()
    types = fileSystemTypeGetTypes()
    if availablefstypes:
        names = availablefstypes
    else:
        names = types.keys()
    if fstype and fstype.isSupported() and fstype.isFormattable():
        default = fstype
    else:
        default = fileSystemTypeGetDefault()
        
    names.sort()
    defindex = None
    i = 0
    for name in names:
        if not fileSystemTypeGet(name).isSupported():
            continue

        if ignorefs and name in ignorefs:
            continue
        
        if fileSystemTypeGet(name).isFormattable():
            item = gtk.MenuItem(name)
            item.set_data("type", types[name])
            fstypeoptionMenu.add(item)
            if default and default.getName() == name:
                defindex = i
                defismountable = types[name].isMountable()
            if fstypechangeCB and mountCombo:
                item.connect("activate", fstypechangeCB, mountCombo)
            i = i + 1

    fstypeoption.set_menu(fstypeoptionMenu)

    if defindex:
        fstypeoption.set_history(defindex)

    if mountCombo:
        mountCombo.set_data("prevmountable",
                            fstypeoptionMenu.get_active().get_data("type").isMountable())

    return (fstypeoption, fstypeoptionMenu)

def raidlevelchangeCB(widget, sparesb):
    raidlevel = widget.get_data("level")
    numparts = sparesb.get_data("numparts")
    maxspares = get_raid_max_spares(raidlevel, numparts)
    if maxspares > 0 and raidlevel != "RAID0":
        sparesb.set_sensitive(1)
        adj = sparesb.get_adjustment()
        value = adj.value
        if adj.value > maxspares:
            value = maxspares
        adj.set_all(value, 0, maxspares,
                    adj.step_increment, adj.page_increment,
                    adj.page_size)
        sparesb.set_adjustment(adj)
        sparesb.set_value(value)
        
    else:
        sparesb.set_value(0)
        sparesb.set_sensitive(0)

class PartitionWindow(InstallWindow):
    def __init__(self, ics):
	InstallWindow.__init__(self, ics)
        ics.setTitle(_("Disk Setup"))
        ics.setNextEnabled(gtk.TRUE)
        ics.readHTML("partition")
        self.parent = ics.getICW().window

    def quit(self):
        pass

    def presentPartitioningComments(self, type,
                                    title, labelstr1, labelstr2, comments):
        win = gtk.Dialog(title)
        
        if type == "ok":
            win.add_button('gtk-ok', 1)
        elif type == "yesno":
            win.add_button('gtk-yes', 1)
            win.add_button('gtk-no', 2)

        image = gtk.Image()
        image.set_from_stock('gtk-dialog-warning', gtk.ICON_SIZE_DIALOG)
        hbox = gtk.HBox(gtk.FALSE)
        hbox.pack_start(image, gtk.FALSE)

        win.connect("clicked", self.quit)
        textbox = gtk.Text()
        textbox.insert_defaults(comments)
        textbox.set_word_wrap(1)
        textbox.set_editable(0)
        
        sw = gtk.ScrolledWindow()
        sw.add(textbox)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        info1 = gtk.Label(labelstr1)
        info1.set_line_wrap(gtk.TRUE)
#        info1.set_usize(300, -1)

        info2 = gtk.Label(labelstr2)
        info2.set_line_wrap(gtk.TRUE)
#        info2.set_usize(300, -1)
        
        vbox = gtk.VBox(gtk.FALSE)
        vbox.pack_start(info1, gtk.FALSE)
        vbox.pack_start(sw, gtk.TRUE)
        vbox.pack_start(info2, gtk.FALSE)
        hbox.pack_start(vbox, gtk.FALSE)

        win.vbox.pack_start(hbox)
#        win.set_usize(400,300)
        win.set_position(gtk.WIN_POS_CENTER)
        win.show_all()
        rc = win.run()
        win.close()
        return rc
        
    def getNext(self):
        (errors, warnings) = sanityCheckAllRequests(self.partitions,
                                                    self.diskset)

        if errors:
            labelstr1 =  _("The following critical errors exist "
                           "with your requested partitioning "
                           "scheme.")
            labelstr2 = _("These errors must be corrected prior "
                          "to continuing with your install of "
                          "Red Hat Linux.")

            commentstr = string.join(errors, "\n\n")
            
            self.presentPartitioningComments("ok",
                                             _("Partitioning Errors"),
                                             labelstr1, labelstr2,
                                             commentstr)
            raise gui.StayOnScreen
        
        if warnings:
            labelstr1 = _("The following warnings exist with "
                         "your requested partition scheme.")
            labelstr2 = _("Would you like to continue with "
                         "your requested partitioning "
                         "scheme?")
            
            commentstr = string.join(warnings, "\n\n")
            rc = self.presentPartitioningComments("yesno",
                                                  _("Partitioning Warnings"),
                                                  labelstr1, labelstr2,
                                                  commentstr)
            if rc != 1:
                raise gui.StayOnScreen

        formatWarnings = getPreExistFormatWarnings(self.partitions,
                                                   self.diskset)
        if formatWarnings:
            labelstr1 = _("The following pre-existing partitions have been "
                          "selected to be formatted, destroying all data.")

            labelstr2 = _("Select 'Yes' to continue and format these "
                          "partitions, or 'No' to go back and change these "
                          "settings.")

            commentstr = ""
            for (dev, type, mntpt) in formatWarnings:
                commentstr = commentstr + \
                        "/dev/%s         %s         %s\n" % (dev,type,mntpt)

            rc = self.presentPartitioningComments("yesno",
                                                  _("Format Warnings"),
                                                  labelstr1, labelstr2,
                                                  commentstr)
            if rc != 1:
                raise gui.StayOnScreen

        
        self.diskStripeGraph.shutDown()
        self.tree.freeze()
        self.clearTree()
        del self.parent
        return None

    def getPrev(self):
        self.diskStripeGraph.shutDown()
        self.tree.freeze()
        self.clearTree()
        del self.parent
        return None
    
    def populate(self, initial = 0):
        drives = self.diskset.disks.keys()
        drives.sort()

        for drive in drives:
            text = [""] * self.numCols
            text[self.titleSlot["Device"]] = '/dev/' + drive
            disk = self.diskset.disks[drive]
            sectorsPerCyl = disk.dev.heads * disk.dev.sectors

            # add a disk stripe to the graph
            stripe = self.diskStripeGraph.add(drive, disk)

            # add a parent node to the tree
            parent = self.tree.insert_node(None, None, text,
                                           is_leaf = gtk.FALSE,
                                           expanded = gtk.TRUE,
                                           spacing = TREE_SPACING)
            extendedParent = None
            part = disk.next_partition()
            while part:
                if part.type & parted.PARTITION_METADATA:
                    part = disk.next_partition(part)
                    continue
                stripe.add(part)

                text = [""] * self.numCols
                device = get_partition_name(part)

                request = self.partitions.getRequestByDeviceName(device)
                if request and request.mountpoint:
                    text[self.titleSlot["Mount Point"]] = request.mountpoint
                
                if part.type & parted.PARTITION_FREESPACE:
                    ptype = _("Free space")
                elif part.type == parted.PARTITION_EXTENDED:
                    ptype = _("Extended")
                elif part.get_flag(parted.PARTITION_RAID) == 1:
                    ptype = _("software RAID")
                elif part.fs_type:
                    if request and request.fstype != None:
                        ptype = request.fstype.getName()
                        if ptype == "foreign":
                            ptype = map_foreign_to_fsname(part.native_type)
                    else:
                        ptype = part.fs_type.name
                    if request.format:
                        text[self.titleSlot["Format"]] = _("Yes")
                    else:
                        text[self.titleSlot["Format"]] = _("No")
                else:
                    if request and request.fstype != None:
                        ptype = request.fstype.getName()
                        if ptype == "foreign":
                            ptype = map_foreign_to_fsname(part.native_type)
                    else:
                        ptype = _("None")
                if part.type & parted.PARTITION_FREESPACE:
                    text[self.titleSlot["Device"]] = _("Free")
                else:
                    text[self.titleSlot["Device"]] = '/dev/' + device
                text[self.titleSlot["Type"]] = ptype
                text[self.titleSlot["Start"]] = "%d" % \
                             (start_sector_to_cyl(disk.dev, part.geom.start),)
                text[self.titleSlot["End"]] = "%d" % \
                                (end_sector_to_cyl(disk.dev, part.geom.end),)
                size = getPartSizeMB(part)
                if size < 1.0:
                    sizestr = "< 1"
                else:
                    sizestr = "%8.0f" % (size)
                text[self.titleSlot["Size (MB)"]] = sizestr

                if part.type == parted.PARTITION_EXTENDED:
                    if extendedParent:
                        raise RuntimeError, ("can't handle more than "
                                             "one extended partition per disk")
                    extendedParent = \
                                   self.tree.insert_node(parent,
                                                         None, text,
                                                         is_leaf=gtk.FALSE,
                                                         expanded=gtk.TRUE,
                                                         spacing=TREE_SPACING)
                    node = extendedParent
                                        
                elif part.type & parted.PARTITION_LOGICAL:
                    if not extendedParent:
                        raise RuntimeError, ("crossed logical partition "
                                             "before extended")
                    node = self.tree.insert_node(extendedParent, None, text,
                                                 spacing = TREE_SPACING)
                else:
                    node = self.tree.insert_node(parent, None, text,
                                                 spacing = TREE_SPACING)
               
                self.tree.node_set_row_data(node, part)

                part = disk.next_partition(part)

        # handle RAID next
        raidcounter = 0
        raidrequests = self.partitions.getRaidRequests()
        if raidrequests:
            for request in raidrequests:
		text = [""] * self.numCols

                if request and request.mountpoint:
                    text[self.titleSlot["Mount Point"]] = request.mountpoint
                
                if request.fstype:
                    ptype = request.fstype.getName()
                    if request.format:
                        text[self.titleSlot["Format"]] = _("Yes")
                    else:
                        text[self.titleSlot["Format"]] = _("No")
                else:
                    ptype = _("None")

                device = _("RAID Device %s"  % (str(raidcounter)))
                text[self.titleSlot["Device"]] = device
                text[self.titleSlot["Type"]] = ptype
                text[self.titleSlot["Start"]] = ""
                text[self.titleSlot["End"]] = ""
                text[self.titleSlot["Size (MB)"]] = \
                                          "%g" % (request.size)

                # add a parent node to the tree
                parent = self.tree.insert_node(None, None, text,
                                               is_leaf = gtk.FALSE,
                                               expanded = gtk.TRUE,
                                               spacing = TREE_SPACING)
                self.tree.node_set_row_data(parent, request.device)
                raidcounter = raidcounter + 1
                
        canvas = self.diskStripeGraph.getCanvas()
        apply(canvas.set_scroll_region, canvas.root().get_bounds())
        self.tree.columns_autosize()

    def treeSelectClistRowCb(self, list, row, column, event, tree):
        if event:
            if event.type == gtk.gdk._2BUTTON_PRESS:
                self.editCb(tree)

    def treeSelectCb(self, tree, node, column):
        partition = tree.node_get_row_data(node)
        if partition:
            self.diskStripeGraph.selectSlice(partition)

    def newCB(self, widget):
        # create new request of size 1M
        request = PartitionSpec(fileSystemTypeGetDefault(), REQUEST_NEW, 1)

        self.editPartitionRequest(request, isNew = 1)

    # edit a partition request
    # isNew implies that this request has never been successfully used before
    def editPartitionRequest(self, origrequest, isNew = 0):

        def formatOptionCB(widget, data):
            (menuwidget, menu, mntptcombo, ofstype) = data
            menuwidget.set_sensitive(widget.get_active())

            # inject event for fstype menu
            if widget.get_active():
                fstype = menu.get_active().get_data("type")
                setMntPtComboStateFromType(fstype, mntptcombo)
            else:
                setMntPtComboStateFromType(ofstype, mntptcombo)

        def noformatCB(widget, badblocks):
            badblocks.set_sensitive(widget.get_active())

        def sizespinchangedCB(widget, fillmaxszsb):
            size = widget.get_value_as_int()
            maxsize = fillmaxszsb.get_value_as_int()
            if size > maxsize:
                fillmaxszsb.set_value(size)

            # ugly got to be better way
            adj = fillmaxszsb.get_adjustment()
            adj.set_all(adj.value, size, adj.upper,
                        adj.step_increment, adj.page_increment,
                        adj.page_size)
            fillmaxszsb.set_adjustment(adj)

        def cylspinchangedCB(widget, data):
            (dev, startcylspin, endcylspin, bycyl_sizelabel) = data
            startsec = start_cyl_to_sector(dev,
                                           startcylspin.get_value_as_int())
            endsec = end_cyl_to_sector(dev, endcylspin.get_value_as_int())
            cursize = (endsec - startsec)/2048
            bycyl_sizelabel.set_text("%s" % (int(cursize))) 

        def fillmaxszCB(widget, spin):
            spin.set_sensitive(widget.get_active())

        # pass in CB defined above because of two scope limitation of python!
        def createSizeOptionsFrame(request, fillmaxszCB):
            frame = gtk.Frame(_("Additional Size Options"))
            sizeoptiontable = gtk.Table()
            sizeoptiontable.set_row_spacings(5)
            sizeoptiontable.set_border_width(4)
            
            fixedrb     = gtk.RadioButton(label=_("Fixed size"))
            fillmaxszrb = gtk.RadioButton(group=fixedrb,
                                          label=_("Fill all space up "
                                                  "to (MB):"))
            maxsizeAdj = gtk.Adjustment(value = 1, lower = 1,
                                        upper = MAX_PART_SIZE, step_incr = 1)
            fillmaxszsb = gtk.SpinButton(maxsizeAdj, digits = 0)
            fillmaxszhbox = gtk.HBox()
            fillmaxszhbox.pack_start(fillmaxszrb)
            fillmaxszhbox.pack_start(fillmaxszsb)
            fillunlimrb = gtk.RadioButton(group=fixedrb,
                                         label=_("Fill to maximum allowable "
                                                 "size"))

            fillmaxszrb.connect("toggled", fillmaxszCB, fillmaxszsb)

            # default to fixed, turn off max size spinbutton
            fillmaxszsb.set_sensitive(0)
            if request.grow:
                if request.maxSize != None:
                    fillmaxszrb.set_active(1)
                    fillmaxszsb.set_sensitive(1)
                    fillmaxszsb.set_value(request.maxSize)
                else:
                    fillunlimrb.set_active(1)
            else:
                fixedrb.set_active(1)

            sizeoptiontable.attach(fixedrb, 0, 1, 0, 1)
            sizeoptiontable.attach(fillmaxszhbox, 0, 1, 1, 2)
            sizeoptiontable.attach(fillunlimrb, 0, 1, 2, 3)
            
            frame.add(sizeoptiontable)

            return (frame, fixedrb, fillmaxszrb, fillmaxszsb)

        #
        # start of editPartitionRequest
        #


        dialog = gtk.Dialog(_("Add Partition"), self.parent)
        dialog.add_button('gtk-ok', 1)
        dialog.add_button('gtk-cancel', 2)
        dialog.set_position(gtk.WIN_POS_CENTER)
        
        maintable = gtk.Table()
        maintable.set_row_spacings(5)
        maintable.set_col_spacings(5)
        row = 0

        # see if we are creating a floating request or by cylinder
        if origrequest.type == REQUEST_NEW:
            newbycyl = origrequest.start != None

        # Mount Point entry
        maintable.attach(createAlignedLabel(_("Mount Point:")),
                                            0, 1, row, row + 1)
        mountCombo = createMountPointCombo(origrequest)
        maintable.attach(mountCombo, 1, 2, row, row + 1)
        row = row + 1

        # Partition Type
        if origrequest.type == REQUEST_NEW:
            maintable.attach(createAlignedLabel(_("Filesystem Type:")),
                             0, 1, row, row + 1)

            (newfstype, newfstypeMenu) = createFSTypeMenu(origrequest.fstype,
                                                          fstypechangeCB,
                                                          mountCombo)
            maintable.attach(newfstype, 1, 2, row, row + 1)
        else:
            maintable.attach(createAlignedLabel(_("Original Filesystem "
                                                  "Type:")),
                             0, 1, row, row + 1)

            if origrequest.origfstype:
                typestr = origrequest.origfstype.getName()
                if origrequest.origfstype.getName() == "foreign":
                    part = get_partition_by_name(self.diskset.disks,
                                                 origrequest.device)
                    typestr = map_foreign_to_fsname(part.native_type)
            else:
                typestr = _("Unknown")

            fstypelabel = gtk.Label(typestr)
            maintable.attach(fstypelabel, 1, 2, row, row + 1)
            newfstype = None
            newfstypeMenu = None
            
        row = row + 1

        # allowable drives
        if origrequest.type == REQUEST_NEW:
            if not newbycyl:
                maintable.attach(createAlignedLabel(_("Allowable Drives:")),
                                 0, 1, row, row + 1)

                driveclist = createAllowedDrivesClist(self.diskset.disks,
                                                      origrequest.drive)

                sw = gtk.ScrolledWindow()
                sw.add(driveclist)
                sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
                maintable.attach(sw, 1, 2, row, row + 1)
            else:
                maintable.attach(createAlignedLabel(_("Drive:")),
                                 0, 1, row, row + 1)
                maintable.attach(createAlignedLabel(origrequest.drive[0]),
                                 1, 2, row, row + 1)

            row = row + 1

        # original fs label
        if origrequest.type != REQUEST_NEW and origrequest.fslabel:
            maintable.attach(createAlignedLabel(_("Original Filesystem "
                                                  "Label:")),
                             0, 1, row, row + 1)
            fslabel = gtk.Label(origrequest.fslabel)
            maintable.attach(fslabel, 1, 2, row, row + 1)

            row = row + 1

        # size
        if origrequest.type == REQUEST_NEW:
            if not newbycyl:
                # Size specification
                maintable.attach(createAlignedLabel(_("Size (MB):")),
                                 0, 1, row, row + 1)
                sizeAdj = gtk.Adjustment(value = 1, lower = 1,
                                         upper = MAX_PART_SIZE, step_incr = 1)
                sizespin = gtk.SpinButton(sizeAdj, digits = 0)

                if origrequest.size:
                    sizespin.set_value(origrequest.size)

                maintable.attach(sizespin, 1, 2, row, row + 1)
                bycyl_sizelabel = None
            else:
                # XXX need to add partition by size and
                #     wire in limits between start and end
                dev = self.diskset.disks[origrequest.drive[0]].dev
                maintable.attach(createAlignedLabel(_("Size (MB):")),
                                 0, 1, row, row + 1)
                bycyl_sizelabel = createAlignedLabel("")
                maintable.attach(bycyl_sizelabel, 1, 2, row, row + 1)
                row = row + 1
                maintable.attach(createAlignedLabel(_("Start Cylinder:")),
                                 0, 1, row, row + 1)

                maxcyl = self.diskset.disks[origrequest.drive[0]].dev.cylinders
                cylAdj = gtk.Adjustment(value=origrequest.start,
                                        lower=origrequest.start,
                                        upper=maxcyl,
                                        step_incr=1)
                startcylspin = gtk.SpinButton(cylAdj, digits=0)
                maintable.attach(startcylspin, 1, 2, row, row + 1)
                row = row + 1
                
                endcylAdj = gtk.Adjustment(value=origrequest.end,
                                           lower=origrequest.start,
                                           upper=maxcyl,
                                           step_incr=1)
                maintable.attach(createAlignedLabel(_("End Cylinder:")),
                                 0, 1, row, row + 1)
                endcylspin = gtk.SpinButton(endcylAdj, digits = 0)
                maintable.attach(endcylspin, 1, 2, row, row + 1)

                startcylspin.connect("changed", cylspinchangedCB,
                            (dev, startcylspin, endcylspin, bycyl_sizelabel))
                endcylspin.connect("changed", cylspinchangedCB,
                             (dev, startcylspin, endcylspin, bycyl_sizelabel))
                
                startsec = start_cyl_to_sector(dev, origrequest.start)
                endsec = end_cyl_to_sector(dev, origrequest.end)
                cursize = (endsec - startsec)/2048
                bycyl_sizelabel.set_text("%s" % (int(cursize)))
        else:
            maintable.attach(createAlignedLabel(_("Size (MB):")),
                             0, 1, row, row + 1)
            sizelabel = gtk.Label("%d" % (origrequest.size))
            maintable.attach(sizelabel, 1, 2, row, row + 1)
            sizespin = None
            
        row = row + 1

        # format/migrate options for pre-existing partitions
        if origrequest.type == REQUEST_PREEXIST and origrequest.fstype:

            ofstype = origrequest.fstype
            
            maintable.attach(gtk.HSeparator(), 0, 2, row, row + 1)
            row = row + 1

            label = gtk.Label(_("How would you like to prepare the filesystem "
                               "on this partition?"))
            label.set_line_wrap(1)
            label.set_alignment(0.0, 0.0)
#            label.set_usize(400, -1)

            maintable.attach(label, 0, 2, row, row + 1)
            row = row + 1
            
            noformatrb = gtk.RadioButton(label=_("Leave unchanged "
                                                 "(preserve data)"))
            noformatrb.set_active(1)
            maintable.attach(noformatrb, 0, 2, row, row + 1)
            row = row + 1

            formatrb = gtk.RadioButton(label=_("Format partition as:"),
                                       group = noformatrb)
            formatrb.set_active(0)
            if origrequest.format:
                formatrb.set_active(1)

            maintable.attach(formatrb, 0, 1, row, row + 1)
            (fstype, fstypeMenu) = createFSTypeMenu(ofstype,fstypechangeCB,
                                                    mountCombo)
            fstype.set_sensitive(formatrb.get_active())
            maintable.attach(fstype, 1, 2, row, row + 1)
            row = row + 1

            if not formatrb.get_active() and not origrequest.migrate:
                mountCombo.set_data("prevmountable", ofstype.isMountable())

            formatrb.connect("toggled", formatOptionCB, (fstype, fstypeMenu,
                                                         mountCombo, ofstype))

            if origrequest.origfstype.isMigratable():
                migraterb = gtk.RadioButton(label=_("Migrate partition to:"),
                                            group=noformatrb)
                migraterb.set_active(0)
                if origrequest.migrate:
                    migraterb.set_active(1)

                migtypes = origrequest.origfstype.getMigratableFSTargets()

                maintable.attach(migraterb, 0, 1, row, row + 1)
                (migfstype, migfstypeMenu)=createFSTypeMenu(ofstype,
                                                            None, None,
                                                   availablefstypes = migtypes)
                migfstype.set_sensitive(migraterb.get_active())
                maintable.attach(migfstype, 1, 2, row, row + 1)
                row = row + 1

                migraterb.connect("toggled", formatOptionCB, (migfstype,
                                                              migfstypeMenu,
                                                              mountCombo,
                                                              ofstype))
                
            else:
                migraterb = None

            badblocks = gtk.CheckButton(_("Check for bad blocks?"))
            badblocks.set_active(0)
            maintable.attach(badblocks, 0, 1, row, row + 1)
            formatrb.connect("toggled", noformatCB, badblocks)
            if not origrequest.format:
                badblocks.set_sensitive(0)

            if origrequest.badblocks:
                badblocks.set_active(1)
            
            row = row + 1
            
        else:
            noformatrb = None
            formatrb = None
            migraterb = None

        # size options
        if origrequest.type == REQUEST_NEW:
            if not newbycyl:
                (sizeframe, fixedrb, fillmaxszrb,
                 fillmaxszsb) = createSizeOptionsFrame(origrequest,
                                                       fillmaxszCB)
                sizespin.connect("changed", sizespinchangedCB, fillmaxszsb)

                maintable.attach(sizeframe, 0, 2, row, row + 1)
            else:
                # XXX need new by cyl options (if any)
                pass
            row = row + 1
        else:
            sizeoptiontable = None

        # create only as primary
        if origrequest.type == REQUEST_NEW:
            primonlycheckbutton = gtk.CheckButton(_("Force to be a primary "
                                                    "partition"))
            primonlycheckbutton.set_active(0)
            if origrequest.primary:
                primonlycheckbutton.set_active(1)
            maintable.attach(primonlycheckbutton, 0, 2, row, row+1)
            row = row + 1

            badblocks = gtk.CheckButton(_("Check for bad blocks"))
            badblocks.set_active(0)
            maintable.attach(badblocks, 0, 1, row, row + 1)
            row = row + 1
            if origrequest.badblocks:
                badblocks.set_active(1)
            
        # put main table into dialog
        dialog.vbox.pack_start(maintable)
        dialog.show_all()

        while 1:
            rc = dialog.run()

            # user hit cancel, do nothing
            if rc == 2:
                dialog.destroy()
                return

            if origrequest.type == REQUEST_NEW:
                # read out UI into a partition specification
                filesystem = newfstypeMenu.get_active().get_data("type")

                request = copy.copy(origrequest)
                request.fstype = filesystem
                request.format = gtk.TRUE
                
                if request.fstype.isMountable():
                    request.mountpoint = mountCombo.entry.get_text()
                else:
                    request.mountpoint = None
                    
                if primonlycheckbutton.get_active():
                    primonly = gtk.TRUE
                else:
                    primonly = None

                if badblocks and badblocks.get_active():
                    request.badblocks = gtk.TRUE
                else:
                    request.badblocks = None

                if not newbycyl:
                    if fixedrb.get_active():
                        grow = None
                    else:
                        grow = gtk.TRUE

                    if fillmaxszrb.get_active():
                        maxsize = fillmaxszsb.get_value_as_int()
                    else:
                        maxsize = None

                    if len(driveclist.selection) == len(self.diskset.disks.keys()):
                        allowdrives = None
                    else:
                        allowdrives = []
                        for i in driveclist.selection:
                            allowdrives.append(driveclist.get_row_data(i))

                    request.size = sizespin.get_value_as_int()
                    request.drive = allowdrives
                    request.grow = grow
                    request.primary = primonly
                    request.maxSize = maxsize
                else:
                    request.start = startcylspin.get_value_as_int()
                    request.end = endcylspin.get_value_as_int()

                    if request.end <= request.start:
                        self.intf.messageWindow(_("Error With Request"),
                                                "The end cylinder must be "
                                                "greater than the start "
                                                "cylinder.")

                        continue

                err = sanityCheckPartitionRequest(self.partitions, request)
                if err:
                    self.intf.messageWindow(_("Error With Request"),
                                            "%s" % (err))
                    continue

            else:
                # preexisting partition, just set mount point and format flag
                request = copy.copy(origrequest)
                if formatrb:
                    request.format = formatrb.get_active()
                    if request.format:
                        request.fstype = fstypeMenu.get_active().get_data("type")
                    if badblocks and badblocks.get_active():
                        request.badblocks = gtk.TRUE
                    else:
                        request.badblocks = None
                        
                else:
                    request.format = 0
                    request.badblocks = None

                if migraterb:
                    request.migrate = migraterb.get_active()
                    if request.migrate:
                        request.fstype =migfstypeMenu.get_active().get_data("type")
                else:
                    request.migrate = 0

                # set back if we are not formatting or migrating
                if not request.format and not request.migrate:
                    request.fstype = origrequest.origfstype

                if request.fstype.isMountable():
                    request.mountpoint =  mountCombo.entry.get_text()
                else:
                    request.mountpoint = None

                err = sanityCheckPartitionRequest(self.partitions, request)
                if err:
                    self.intf.messageWindow(_("Error With Request"),
                                            "%s" % (err))
                    continue

#                if not origrequest.format and request.format:
#                    if not queryFormatPreExisting(self.intf):
#                        continue

                if (not request.format and
                    request.mountpoint and isFormatOnByDefault(request)):
                    if not queryNoFormatPreExisting(self.intf):
                        continue
            
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

        dialog.destroy()

    def deleteCb(self, widget):
        node = self.tree.selection[0]
        partition = self.tree.node_get_row_data(node)

        if doDeletePartitionByRequest(self.intf, self.partitions, partition):
            self.refresh()
            
    def clearTree(self):
        node = self.tree.node_nth(0)
        while node:
            self.tree.remove_node(node)
            node = self.tree.node_nth(0)
        self.tree.set_selection_mode(gtk.SELECTION_SINGLE)
        self.tree.set_selection_mode(gtk.SELECTION_BROWSE)

    def resetCb(self, *args):
        if not confirmResetPartitionState(self.intf):
            return
        
        self.diskStripeGraph.shutDown()
        self.newFsset = self.fsset.copy()
        self.tree.freeze()
        self.clearTree()
        self.diskset.refreshDevices()
        self.partitions.setFromDisk(self.diskset)
        self.populate()
        self.tree.thaw()

    def refresh(self):
        self.diskStripeGraph.shutDown()
        self.tree.freeze()
        self.clearTree()
        try:
            doPartitioning(self.diskset, self.partitions)
            rc = 0
        except PartitioningError, msg:
            self.intf.messageWindow(_("Error Partitioning"),
                   _("Could not allocate requested partitions: %s.") % (msg))
            rc = -1
        except PartitioningWarning, msg:
            # XXX somebody other than me should make this look better
            # XXX this doesn't handle the 'delete /boot partition spec' case
            #     (it says 'add anyway')
            dialog = gtk.Dialog(_("Warning"))
            dialog.set_parent(self.parent)
            button = gtk.Button(_("_Modify Partition"))
            dialog.add_action_widget(button, 1)
            button = gtk.Button(_("_Continue"))
            dialog.add_action_widget(button, 2)
            dialog.set_position(gtk.WIN_POS_CENTER)

            label = gtk.Label(_("Warning: %s.") % (msg))
            label.set_line_wrap(gtk.TRUE)
            dialog.vbox.pack_start(label)
            dialog.show_all()
            rc = dialog.run()
            dialog.destroy()
            
            if rc == 1:
                rc = -1
            else:
                rc = 0
                req = self.partitions.getBootableRequest()
                if req:
                    req.ignoreBootConstraints = 1

        self.populate()
        self.tree.thaw()
        return rc

    def editCb(self, widget):
        node = self.tree.selection[0]
        part = self.tree.node_get_row_data(node)

        (type, request) = doEditPartitionByRequest(self.intf, self.partitions,
                                                   part)
        if request:
            if type == "RAID":
                self.editRaidRequest(request)
            elif type == "NEW":
                self.editPartitionRequest(request, isNew = 1)
            else:
                self.editPartitionRequest(request)

    # isNew implies that this request has never been successfully used before
    def editRaidRequest(self, raidrequest, isNew = 0):
        #
        # start of editRaidRuquest
        #
        availraidparts = get_available_raid_partitions(self.diskset,
                                                       self.partitions,
                                                       raidrequest)

        # if no raid partitions exist, raise an error message and return
        if len(availraidparts) < 2:
            dlg = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
                                    _("At least two software RAID "
                                      "partitions are needed."))
            dlg.set_position(gtk.WIN_POS_CENTER)
            dlg.run()
            dlg.destroy()
            return

        dialog = gtk.Dialog(_("Make RAID Device"), self.parent)
        dialog.add_button('gtk-ok', 1)
        dialog.add_button('gtk-cancel', 2)
        dialog.set_position(gtk.WIN_POS_CENTER)
        
        maintable = gtk.Table()
        maintable.set_row_spacings(5)
        maintable.set_col_spacings(5)
        row = 0

        # Mount Point entry
        maintable.attach(createAlignedLabel(_("Mount Point:")),
                                            0, 1, row, row + 1)
        mountCombo = createMountPointCombo(raidrequest)
        maintable.attach(mountCombo, 1, 2, row, row + 1)
        row = row + 1

        # Filesystem Type
        maintable.attach(createAlignedLabel(_("Filesystem type:")),
                                            0, 1, row, row + 1)

        (fstypeoption, fstypeoptionMenu) = createFSTypeMenu(raidrequest.fstype,
                                                            fstypechangeCB,
                                                            mountCombo,
                                                            ignorefs = ["software RAID"])
        maintable.attach(fstypeoption, 1, 2, row, row + 1)
            
        row = row + 1

        # raid level
        maintable.attach(createAlignedLabel(_("RAID Level:")),
                                            0, 1, row, row + 1)

        # Create here, pack below
        numparts =  len(availraidparts)
        if raidrequest.raidspares:
            nspares = raidrequest.raidspares
        else:
            nspares = 0
            
        if raidrequest.raidlevel:
            maxspares = get_raid_max_spares(raidrequest.raidlevel, numparts)
        else:
            maxspares = 0

        spareAdj = gtk.Adjustment(value = nspares, lower = 0,
                                  upper = maxspares, step_incr = 1)
        sparesb = gtk.SpinButton(spareAdj, digits = 0)
        sparesb.set_data("numparts", numparts)

        if maxspares > 0:
            sparesb.set_sensitive(1)
        else:
            sparesb.set_value(0)
            sparesb.set_sensitive(0)

        (leveloption, leveloptionmenu) = createRaidLevelMenu(availRaidLevels,
                                                       raidrequest.raidlevel,
                                                       raidlevelchangeCB,
                                                       sparesb)
        maintable.attach(leveloption, 1, 2, row, row + 1)
            
        row = row + 1

        # raid members
        maintable.attach(createAlignedLabel(_("RAID Members:")),
                         0, 1, row, row + 1)

        # XXX need to pass in currently used partitions for this device
        (raidclist, sw) = createAllowedRaidPartitionsClist(availraidparts,
                                                     raidrequest.raidmembers)

        maintable.attach(sw, 1, 2, row, row + 1)
        row = row + 1

        # number of spares - created widget above
        maintable.attach(createAlignedLabel(_("Number of spares:")),
                         0, 1, row, row + 1)
        maintable.attach(sparesb, 1, 2, row, row + 1)
        row = row + 1

        # format or not?
        if raidrequest.fstype and raidrequest.fstype.isFormattable():
            formatButton = gtk.CheckButton(_("Format partition?"))
            # XXX this probably needs more logic once we detect existing raid
            if raidrequest.format == None or raidrequest.format != 0:
                formatButton.set_active(1)
            else:
                formatButton.set_active(0)
            maintable.attach(formatButton, 0, 2, row, row + 1)
            row = row + 1

        else:
            formatButton = None
            
        # put main table into dialog
        dialog.vbox.pack_start(maintable)

        dialog.show_all()

        while 1:
            rc = dialog.run()

            # user hit cancel, do nothing
            if rc == 2:
                dialog.destroy()
                return

            # read out UI into a partition specification
            request = copy.copy(raidrequest)

            filesystem = fstypeoptionMenu.get_active().get_data("type")
            request.fstype = filesystem

            if request.fstype.isMountable():
                request.mountpoint = mountCombo.entry.get_text()
            else:
                request.mountpoint = None

            raidmembers = []
            for i in raidclist.selection:
                id = self.partitions.getRequestByDeviceName(availraidparts[i][0]).uniqueID
                raidmembers.append(id)

            request.raidmembers = raidmembers
            request.raidlevel = leveloptionmenu.get_active().get_data("level")
            if request.raidlevel != "RAID0":
                request.raidspares = sparesb.get_value_as_int()
            else:
                request.raidspares = 0
            
            if formatButton:
                request.format = formatButton.get_active()
            else:
                request.format = 0

            err = sanityCheckRaidRequest(self.partitions, request)
            if err:
                self.intf.messageWindow(_("Error With Request"),
                                        "%s" % (err))
                continue
            
            if not isNew:
                self.partitions.removeRequest(raidrequest)

            self.partitions.addRequest(request)
            
            if self.refresh():
                # how can this fail?  well, if it does, do the remove new,
                # add old back in dance
                self.partitions.removeRequest(request)
                if not isNew:
                    self.partitions.addRequest(raidrequest)
                if self.refresh():
                    raise RuntimeError, ("Returning partitions to state "
                                         "prior to RAID edit failed")
            else:
                break

        dialog.destroy()

    def makeraidCB(self, widget):
        request = PartitionSpec(fileSystemTypeGetDefault(), REQUEST_RAID, 1)
        self.editRaidRequest(request, isNew = 1)

    def getScreen(self, fsset, diskset, partitions, intf):
        self.fsset = fsset
        self.diskset = diskset
        self.intf = intf
        
        self.diskset.openDevices()
        self.partitions = partitions

        checkForSwapNoMatch(self.intf, self.diskset, self.partitions)

        # XXX PartitionRequests() should already exist and
        # if upgrade or going back, have info filled in
#        self.newFsset = self.fsset.copy()

        # operational buttons
        buttonBox = gtk.HButtonBox()
        buttonBox.set_layout(gtk.BUTTONBOX_SPREAD)

        ops = ((_("_New"), self.newCB),
               (_("_Edit"), self.editCb),
               (_("_Delete"), self.deleteCb),
               (_("_Reset"), self.resetCb),
               (_("Make _RAID"), self.makeraidCB))
        
        for label, cb in ops:
            button = gtk.Button(label)
            buttonBox.add (button)
            button.connect ("clicked", cb)

        # set up the tree
        titles = [N_("Device"), N_("Start"), N_("End"),
                  N_("Size (MB)"), N_("Type"), N_("Mount Point"), N_("Format")]
        
        # do two things: enumerate the location of each field and translate
        self.titleSlot = {}
        i = 0
        for title in titles:
            self.titleSlot[title] = i
            titles[i] = _(title)
            i = i + 1

        self.numCols = len(titles)
        self.tree = gtk.CTree(self.numCols, 0, titles)
        self.tree.set_selection_mode(gtk.SELECTION_BROWSE)
        self.tree.column_titles_passive()
        for i in range(self.numCols):
            self.tree.set_column_resizeable(i, 0)
            
        self.tree.set_column_justification(1, gtk.JUSTIFY_RIGHT)
        self.tree.set_column_justification(2, gtk.JUSTIFY_RIGHT)
        self.tree.set_column_justification(3, gtk.JUSTIFY_RIGHT)
        self.tree.connect("select_row", self.treeSelectClistRowCb, self.tree)
        self.tree.connect("tree_select_row", self.treeSelectCb)

        # set up the canvas
        self.diskStripeGraph = DiskStripeGraph(self.tree, self.editCb)
        
        # do the initial population of the tree and the graph
        self.populate(initial = 1)

        box = gtk.VBox(gtk.FALSE, 5)
        sw = gtk.ScrolledWindow()
        sw.add(self.diskStripeGraph.getCanvas())
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        frame = gtk.Frame()
        frame.add(sw)
        box.pack_start(frame, gtk.TRUE, gtk.TRUE)
        box.pack_start(buttonBox, gtk.FALSE)
        sw = gtk.ScrolledWindow()
        sw.add(self.tree)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        box.pack_start(sw, gtk.TRUE)

	return box

class AutoPartitionWindow(InstallWindow):
    def __init__(self, ics):
    	InstallWindow.__init__(self, ics)
        ics.setTitle(_("Automatic Partitioning"))
        ics.setNextEnabled(gtk.TRUE)
        ics.readHTML("autopart")
        self.parent = ics.getICW().window

    def getNext(self):
        if self.clearLinuxRB.get_active():
            self.partitions.autoClearPartType = CLEARPART_TYPE_LINUX
        elif self.clearAllRB.get_active():
            self.partitions.autoClearPartType = CLEARPART_TYPE_ALL
        else:
            self.partitions.autoClearPartType = CLEARPART_TYPE_NONE

        allowdrives = []
        for i in self.driveclist.selection:
            allowdrives.append(self.driveclist.get_row_data(i))

        if len(allowdrives) < 1:
            self.intf.messageWindow(_("Warning"), 
                                    _("You need to select at least one "
                                      "drive to have Red Hat Linux installed "
                                      "onto."), type = "ok")
            raise gui.StayOnScreen

        self.partitions.autoClearPartDrives = allowdrives

        if not queryAutoPartitionOK(self.intf, self.diskset, self.partitions):
            raise gui.StayOnScreen
        
        if self.inspect.get_active():
            self.dispatch.skipStep("partition", skip = 0)
        else:
            self.dispatch.skipStep("partition")

        return None


    def getScreen(self, diskset, partitions, intf, dispatch):
        
        self.diskset = diskset
        self.partitions = partitions
        self.intf = intf
        self.dispatch = dispatch
        
        type = partitions.autoClearPartType
        cleardrives = partitions.autoClearPartDrives
        
        box = gtk.VBox(gtk.FALSE)
        box.set_border_width(5)

        label = WrappingLabel(_(AUTOPART_DISK_CHOICE_DESCR_TEXT))
        label.set_alignment(0.0, 0.0)
        box.pack_start(label, gtk.FALSE, gtk.FALSE)

        # what partition types to remove
        clearbox = gtk.VBox(gtk.FALSE)
        label = WrappingLabel(_("I want to have automatic partitioning:"))
        label.set_alignment(0.0, 0.0)
        clearbox.pack_start(label, gtk.FALSE, gtk.FALSE, 10)
        
        radioBox = gtk.VBox(gtk.FALSE)
        self.clearLinuxRB = gtk.RadioButton(
            None, _(CLEARPART_TYPE_LINUX_DESCR_TEXT))
	radioBox.pack_start(self.clearLinuxRB, gtk.FALSE, gtk.FALSE)
        self.clearAllRB = gtk.RadioButton(
            self.clearLinuxRB, _(CLEARPART_TYPE_ALL_DESCR_TEXT))
	radioBox.pack_start(self.clearAllRB, gtk.FALSE, gtk.FALSE)
        self.clearNoneRB = gtk.RadioButton(
            self.clearLinuxRB, _(CLEARPART_TYPE_NONE_DESCR_TEXT))
	radioBox.pack_start(self.clearNoneRB, gtk.FALSE, gtk.FALSE)

        if type == CLEARPART_TYPE_LINUX:
            self.clearLinuxRB.set_active(1)
        elif type == CLEARPART_TYPE_ALL:
            self.clearAllRB.set_active(1)
        else:
            self.clearNoneRB.set_active(1)
           
	align = gtk.Alignment()
	align.add(radioBox)
	align.set(0.5, 0.5, 0.0, 0.0)
	clearbox.pack_start(align, gtk.FALSE, gtk.FALSE)

        box.pack_start(clearbox, gtk.FALSE, gtk.FALSE, 10)

        # which drives to use?
        drivesbox = gtk.VBox(gtk.FALSE)
        label = WrappingLabel(_("Which drive(s) do you want to use for this "
                                "installation?"))
        label.set_alignment(0.0, 0.0)
        drivesbox.pack_start(label, gtk.FALSE, gtk.FALSE, 10)
        self.driveclist = createAllowedDrivesClist(diskset.disks,
                                                   cleardrives)
        # XXX bad use of usize
        self.driveclist.set_usize(300, 80)

        sw = gtk.ScrolledWindow()
        sw.add(self.driveclist)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        
	align = gtk.Alignment()
	align.add(sw)
	align.set(0.5, 0.5, 0.0, 0.0)
        
        drivesbox.pack_start(align, gtk.FALSE, gtk.FALSE)

        box.pack_start(drivesbox, gtk.FALSE, gtk.FALSE)

        self.inspect = gtk.CheckButton()
        widgetExpander(self.inspect)
        label = gtk.Label(_("Review (allows you to see and change the "
                            "automatic partitioning results)"))
        label.set_line_wrap(gtk.TRUE)
        widgetExpander(label, self.inspect)
        label.set_alignment(0.0, 1.0)
        self.inspect.add(label)

        self.inspect.set_active(not dispatch.stepInSkipList("partition"))

	box.pack_start(self.inspect, gtk.TRUE, gtk.TRUE, 10)

        self.ics.setNextEnabled(gtk.TRUE)

	align = gtk.Alignment()
	align.add(box)
	align.set(0.5, 0.5, 0.0, 0.0)

	return align
        
