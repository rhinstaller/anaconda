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

from iw_gui import *
from gtk import *
from GDK import *
from gnome.ui import *
from translate import _, N_
from partitioning import *
from fsset import *
from autopart import doPartitioning
from autopart import CLEARPART_TYPE_LINUX, CLEARPART_TYPE_ALL, CLEARPART_TYPE_NONE
import parted
import string
import copy

STRIPE_HEIGHT = 32.0
LOGICAL_INSET = 3.0
CANVAS_WIDTH = 500
CANVAS_HEIGHT = 200
TREE_SPACING = 2

MODE_ADD = 1
MODE_EDIT = 2

# XXX this is made up and used by the size spinner; should just be set with
# a callback
MAX_PART_SIZE = 1024*1024*1024

class DiskStripeSlice:
    def eventHandler(self, widget, event):
        if event.type == GDK.BUTTON_PRESS:
            if event.button == 1:
                self.parent.selectSlice(self.partition, 1)

        return TRUE

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
        rc = rc + "%d MB" % (self.partition.geom.length
                             * self.parent.getDisk().dev.sector_size
                             / 1024.0 / 1024.0,)
        return rc

    def getDeviceName(self):
        return get_partition_name(self.partition)

    def update(self):
        disk = self.parent.getDisk()
        totalSectors = float(disk.dev.heads
                             * disk.dev.sectors
                             * disk.dev.cylinders)
        xoffset = self.partition.geom.start / totalSectors * CANVAS_WIDTH
        xlength = self.partition.geom.length / totalSectors * CANVAS_WIDTH
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
                      anchor=ANCHOR_NW, clip=TRUE,
                      clip_width=xlength-1, clip_height=yheight-1)
        self.hideOrShowText()
        
    def __init__(self, parent, partition):
        self.text = None
        self.partition = partition
        self.parent = parent
        pgroup = parent.getGroup()

        self.group = pgroup.add("group")
        self.box = self.group.add ("rect")
        self.group.connect("event", self.eventHandler)
        self.text = self.group.add ("text",
                                    fontset="-*-helvetica-medium-r-*-*-8-*")
        self.update()

class DiskStripe:
    def __init__(self, drive, disk, group, ctree, canvas):
        self.disk = disk
        self.group = group
        self.tree = ctree
        self.drive = drive
        self.canvas = canvas
        self.slices = []
        self.hash = {}
        self.selected = None
        group.add ("rect", x1=0.0, y1=10.0, x2=CANVAS_WIDTH,
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
        return self.hash.has_key (partition)

    def getSlice(self, partition):
        return self.hash[partition]
   
    def getDisk(self):
        return self.disk

    def getDrive(self):
        return self.drive

    def getGroup (self):
        return self.group

    def getCanvas (self):
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
                row = self.tree.find_by_row_data (node, partition)
                self.tree.select(row)
                break
        self.selected = slice

    def deselect(self):
        if self.selected:
            self.selected.deselect ()
        self.selected = None
    
    def add (self, partition):
        stripe = DiskStripeSlice(self, partition)
        self.slices.append(stripe)
        self.hash[partition] = stripe

class DiskStripeGraph:
    def __init__(self, ctree):
        self.canvas = GnomeCanvas()
        self.diskStripes = []
        self.textlabels = []
        self.ctree = ctree
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

    def add (self, drive, disk):
#        yoff = len(self.diskStripes) * (STRIPE_HEIGHT + 5)
        yoff = self.next_ypos
        text = self.canvas.root().add ("text", x=0.0, y=yoff,
                          fontset="-*-helvetica-bold-r-normal-*-*-120-*-*-p-*-iso8859-1")
        drivetext = "Drive %s (Geom: %s/%s/%s) (Model: %s)" % ('/dev/' + drive,
                                       disk.dev.cylinders,
                                       disk.dev.heads,
                                       disk.dev.sectors,
                                       disk.dev.model)
        text.set(text=drivetext, fill_color='black', anchor=ANCHOR_NW)
        (xxx1, yyy1, xxx2, yyy2) =  text.get_bounds()
        textheight = yyy2 - yyy1
        self.textlabels.append(text)

        group = self.canvas.root().add("group", x=0, y=yoff+textheight)
        stripe = DiskStripe (drive, disk, group, self.ctree, self.canvas)
        self.diskStripes.append(stripe)
        self.next_ypos = self.next_ypos + STRIPE_HEIGHT+textheight+10
        return stripe


# this should probably go into a class
# some helper functions for build UI components
def createAlignedLabel(text):
    label = GtkLabel(text)
    label.set_alignment(0.0, 0.0)

    return label

def createMountPointCombo(request):
    mountCombo = GtkCombo()
    mountCombo.set_popdown_strings (defaultMountPoints)

    mountpoint = request.mountpoint

    if request.fstype.isMountable():
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

def fstypechangeCB(widget, mountCombo):
    fstype = widget.get_data("type")

    prevmountable = mountCombo.get_data("prevmountable")
    mountpoint = mountCombo.get_data("saved_mntpt")

    if prevmountable and fstype.isMountable():
        return
    
    if fstype.isMountable():
        mountCombo.set_sensitive(1)
        if mountpoint != None:
            mountCombo.entry.set_text(mountpoint)
    else:
        if mountCombo.entry.get_text() != _("<Not Applicable>"):
            mountCombo.set_data("saved_mntpt", mountCombo.entry.get_text())
        mountCombo.entry.set_text(_("<Not Applicable>"))
        mountCombo.set_sensitive(0)

    mountCombo.set_data("prevmountable", fstype.isMountable())
    
    # XXX hrmm... we need to get these passed into the callback somehow
##     # XXX ugly, there has to be a better way
##     adj = maxSizeSpinner.get_adjustment()
##     adj.set_all(adj.value, size, fstype.getMaxSize(),
##                 adj.step_increment, adj.page_increment,
##                 adj.page_size)
##     maxSizeSpinner.set_adjustment(adj)

##     adj = sizeSpinner.get_adjustment()
##     adj.set_all(adj.value, size, fstype.getMaxSize(),
##                 adj.step_increment, adj.page_increment,
##                 adj.page_size)
##     sizeSpinner.set_adjustment(adj)

def createAllowedDrivesClist(drives, reqdrives):
    driveclist = GtkCList()
    driveclist.set_selection_mode (SELECTION_MULTIPLE)

    driverow = 0
    for drive in drives:
        driveclist.append((drive,))

        if reqdrives:
            if drive in reqdrives:
                driveclist.select_row(driverow, 0)
        else:
            driveclist.select_row(driverow, 0)
        driverow = driverow + 1

    return driveclist

def createAllowedRaidPartitionsClist(allraidparts, reqraidpart):

    partclist = GtkCList()
    partclist.set_selection_mode (SELECTION_MULTIPLE)

    partrow = 0
    for (part, used) in allraidparts:
        partname = "%s: %8.0f MB" % (get_partition_name(part),
                                     (part.geom.length
                                      * part.geom.disk.dev.sector_size
                                      / 1024.0 / 1024.0))
        
        partclist.append((partname,))

        if used or not reqraidpart:
            partclist.select_row(partrow, 0)
        partrow = partrow + 1

    return partclist

def createRaidLevelMenu(levels, reqlevel, raidlevelchangeCB, sparesb):
    leveloption = GtkOptionMenu()
    leveloptionmenu = GtkMenu()
    defindex = None
    i = 0
    for lev in levels:
        item = GtkMenuItem(lev)
        item.set_data ("level", lev)
        leveloptionmenu.add(item)
        if reqlevel and lev == reqlevel:
            defindex = i
        if raidlevelchangeCB and sparesb:
            item.connect("activate", raidlevelchangeCB, sparesb)
        i = i + 1

    leveloption.set_menu (leveloptionmenu)
    
    if defindex:
        leveloption.set_history(defindex)
        
    return (leveloption, leveloptionmenu)

# pass in callback for when fs changes because of python scope issues
def createFSTypeMenu(fstype, fstypechangeCB, mountCombo):
    fstypeoption = GtkOptionMenu ()
    fstypeoptionMenu = GtkMenu ()
    types = fileSystemTypeGetTypes()
    names = types.keys()
    names.sort()
    defindex = None
    i = 0
    for name in names:
        if not fileSystemTypeGet(name).isSupported():
            continue
        
        if fileSystemTypeGet(name).isFormattable():
            item = GtkMenuItem(name)
            item.set_data ("type", types[name])
            fstypeoptionMenu.add(item)
            if fstype and fstype.getName() == name:
                defindex = i
                defismountable = types[name].isMountable()
            if fstypechangeCB and mountCombo:
                item.connect("activate", fstypechangeCB, mountCombo)
            i = i + 1

    fstypeoption.set_menu (fstypeoptionMenu)

    if defindex:
        fstypeoption.set_history(defindex)

    mountCombo.set_data("prevmountable", fstypeoptionMenu.get_active().get_data("type").isMountable())

    return (fstypeoption, fstypeoptionMenu)

def raidlevelchangeCB(widget, sparesb):
    raidlevel = widget.get_data("level")
    numparts = sparesb.get_data("numparts")
    maxspares = get_raid_max_spares(raidlevel, numparts)
    if maxspares > 0:
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
        ics.setTitle (_("Disk Setup"))
        ics.setNextEnabled (FALSE)
        self.parent = ics.getICW().window
        
    def getNext(self):
        self.diskStripeGraph.shutDown()    
        self.clearTree()
        self.fsset.reset()
        for request in self.partitions.requests:
            # XXX improve sanity checking
            if not request.fstype or (request.fstype.isMountable() and not request.mountpoint):
                continue
            entry = request.toEntry()
            self.fsset.add (entry)

        print self.fsset.fstab()
        print self.fsset.raidtab()
        del self.parent
        return None

    def checkNextConditions(self):
        request = self.partitions.getRequestByMountPoint("/")
        if request:
            self.ics.setNextEnabled(TRUE)
        else:
            self.ics.setNextEnabled(FALSE)
        
    def populate (self, initial = 0):
        drives = self.diskset.disks.keys()
        drives.sort()

        for drive in drives:
            text = [""] * self.numCols
            text[self.titleSlot["Device"]] = '/dev/' + drive
            disk = self.diskset.disks[drive]
            sectorsPerCyl = disk.dev.heads * disk.dev.sectors

            # add a disk stripe to the graph
            stripe = self.diskStripeGraph.add (drive, disk)

            # add a parent node to the tree
            parent = self.tree.insert_node (None, None, text,
                                            is_leaf = FALSE, expanded = TRUE,
                                            spacing = TREE_SPACING)
            extendedParent = None
            part = disk.next_partition ()
            while part:
                if part.type & parted.PARTITION_METADATA:
                    part = disk.next_partition (part)
                    continue
                stripe.add (part)

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
                    ptype = _("software RAID component")
                elif part.fs_type:
                    ptype = part.fs_type.name
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
                size = part.geom.length*disk.dev.sector_size / 1024.0 / 1024.0
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
                                   self.tree.insert_node (parent,
                                                          None, text,
                                                          is_leaf=FALSE,
                                                          expanded=TRUE,
                                                          spacing=TREE_SPACING)
                    node = extendedParent
                                        
                elif part.type & parted.PARTITION_LOGICAL:
                    if not extendedParent:
                        raise RuntimeError, ("crossed logical partition "
                                             "before extended")
                    node = self.tree.insert_node (extendedParent, None, text,
                                                  spacing = TREE_SPACING)
                else:
                    node = self.tree.insert_node (parent, None, text,
                                                  spacing = TREE_SPACING)
                
                self.tree.node_set_row_data (node, part)

                part = disk.next_partition (part)

        # handle RAID next
        raidcounter = 0
        raidrequests = self.partitions.getRaidRequests()
        if raidrequests:
            for request in raidrequests:
                if request and request.mountpoint:
                    text[self.titleSlot["Mount Point"]] = request.mountpoint
                
                if request.fstype:
                    ptype = request.fstype.getName()
                else:
                    ptype = _("None")

                device = _("RAID Device %s"  % (str(raidcounter)))
                text[self.titleSlot["Device"]] = device
                text[self.titleSlot["Type"]] = ptype
                text[self.titleSlot["Start"]] = ""
                text[self.titleSlot["End"]] = ""
                text[self.titleSlot["Size (MB)"]] = \
                                          "%g" % (get_raid_device_size(request)
                                                  / 1024.0 / 1024.0)
                
                # add a parent node to the tree
                parent = self.tree.insert_node (None, None, text,
                                                is_leaf = FALSE,
                                                expanded = TRUE,
                                                spacing = TREE_SPACING)
                self.tree.node_set_row_data (parent, request.device)
                
        canvas = self.diskStripeGraph.getCanvas()
        apply(canvas.set_scroll_region, canvas.root().get_bounds())
        self.tree.columns_autosize()

    def treeSelectCb(self, tree, node, column):
        partition = tree.node_get_row_data (node)
        if partition:
            self.diskStripeGraph.selectSlice(partition)


    def newCB(self, widget):
        # create new request of size 1M
        request = PartitionSpec(fileSystemTypeGetDefault(), REQUEST_NEW, 1)

        self.editPartitionRequest(request)

    # edit a partition request
    def editPartitionRequest(self, origrequest):

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

        def fillmaxszCB(widget, spin):
            spin.set_sensitive(widget.get_active())

        # pass in CB defined above because of two scope limitation of python!
        def createSizeOptionsFrame(request, fillmaxszCB):
            frame = GtkFrame (_("Additional Size Options"))
            sizeoptiontable = GtkTable()
            sizeoptiontable.set_row_spacings(5)
            sizeoptiontable.set_border_width(4)
            
            fixedrb     = GtkRadioButton(label=_("Fixed size"))
            fillmaxszrb = GtkRadioButton(group=fixedrb, label=_("Fill all space up to (MB):"))
            maxsizeAdj = GtkAdjustment (value = 1, lower = 1,
                                        upper = MAX_PART_SIZE, step_incr = 1)
            fillmaxszsb = GtkSpinButton(maxsizeAdj, digits = 0)
            fillmaxszhbox = GtkHBox()
            fillmaxszhbox.pack_start(fillmaxszrb)
            fillmaxszhbox.pack_start(fillmaxszsb)
            fillunlimrb = GtkRadioButton(group=fixedrb,
                                         label=_("Fill to maximum allowable size"))

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
        dialog = GnomeDialog(_("Add Partition"))
        dialog.set_parent(self.parent)
        dialog.append_button (_("OK"))
        dialog.append_button (_("Cancel"))
        dialog.set_position(WIN_POS_CENTER)
        dialog.close_hides(TRUE)
        
        maintable = GtkTable()
        maintable.set_row_spacings (5)
        maintable.set_col_spacings (5)
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
        maintable.attach(createAlignedLabel(_("Filesystem Type:")),
                                            0, 1, row, row + 1)

        if origrequest.type == REQUEST_NEW:
            (fstypeoption, fstypeoptionMenu) = createFSTypeMenu(origrequest.fstype, fstypechangeCB, mountCombo)
            maintable.attach(fstypeoption, 1, 2, row, row + 1)
        else:
            fstypelabel = GtkLabel(origrequest.fstype.getName())
            maintable.attach(fstypelabel, 1, 2, row, row + 1)
            fstypeoption = None
            fstypeoptionMenu = None
            
        row = row + 1

        # allowable drives
        if origrequest.type == REQUEST_NEW:
            if not newbycyl:
                maintable.attach(createAlignedLabel(_("Allowable Drives:")),
                                 0, 1, row, row + 1)

                driveclist = createAllowedDrivesClist(self.diskset.disks.keys(),                                                      origrequest.drive)

                maintable.attach(driveclist, 1, 2, row, row + 1)
            else:
                maintable.attach(createAlignedLabel(_("Drive:")),
                                 0, 1, row, row + 1)
                maintable.attach(createAlignedLabel(origrequest.drive[0]),
                                 1, 2, row, row + 1)

            row = row + 1

        if origrequest.type == REQUEST_NEW:
            if not newbycyl:
                # Size specification
                maintable.attach(createAlignedLabel(_("Size (MB):")),
                                 0, 1, row, row + 1)
                sizeAdj = GtkAdjustment (value = 1, lower = 1,
                                         upper = MAX_PART_SIZE, step_incr = 1)
                sizespin = GtkSpinButton(sizeAdj, digits = 0)

                if origrequest.size:
                    sizespin.set_value(origrequest.size)

                maintable.attach(sizespin, 1, 2, row, row + 1)
            else:
                # XXX need to add partition by size and
                #     wire in limits between start and end
                maintable.attach(createAlignedLabel(_("Start Cylinder:")),
                                 0, 1, row, row + 1)

                maxcyl = self.diskset.disks[origrequest.drive[0]].dev.cylinders
                cylAdj = GtkAdjustment (value = origrequest.start,
                                        lower = origrequest.start,
                                        upper = maxcyl,
                                        step_incr = 1)
                startcylspin = GtkSpinButton(cylAdj, digits = 0)
                maintable.attach(startcylspin, 1, 2, row, row + 1)
                row = row + 1
                
                endcylAdj = GtkAdjustment (value = origrequest.end,
                                        lower = origrequest.start,
                                        upper = maxcyl,
                                        step_incr = 1)
                maintable.attach(createAlignedLabel(_("End Cylinder:")),
                                 0, 1, row, row + 1)
                endcylspin = GtkSpinButton(endcylAdj, digits = 0)
                maintable.attach(endcylspin, 1, 2, row, row + 1)

        else:
            maintable.attach(createAlignedLabel(_("Size (MB):")),
                             0, 1, row, row + 1)
            sizelabel = GtkLabel("%d" % (origrequest.size))
            maintable.attach(sizelabel, 1, 2, row, row + 1)
            sizespin = None
            
        row = row + 1

        if origrequest.type == REQUEST_PREEXIST:
            if origrequest.fstype and origrequest.fstype.isFormattable():
                formatButton = GtkCheckButton (_("Format partition?"))
                formatButton.set_active(0)
                if origrequest.format:
                    formatButton.set_active(1)
                maintable.attach(formatButton, 0, 2, row, row + 1)
                row = row + 1
            else:
                formatButton = None

        # size options
        if origrequest.type == REQUEST_NEW:
            if not newbycyl:
                (sizeframe, fixedrb, fillmaxszrb, fillmaxszsb) = createSizeOptionsFrame(origrequest, fillmaxszCB)
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
            primonlycheckbutton = GtkCheckButton(_("Force to be a primary partition"))
            primonlycheckbutton.set_active(0)
            if origrequest.primary:
                primonlycheckbutton.set_active(1)
            maintable.attach(primonlycheckbutton, 0, 2, row, row+1)
            row = row + 1
            
        # put main table into dialog
        dialog.vbox.pack_start(maintable)

        dialog.show_all()

        while 1:
            rc = dialog.run()

            # user hit cancel, do nothing
            if rc == 1:
                dialog.close()
                return
            elif rc == -1:
                raise ValueError,"Error while running edit partition request dialog."

            if origrequest.type == REQUEST_NEW:
                # read out UI into a partition specification
                filesystem = fstypeoptionMenu.get_active().get_data("type")

                request = copy.copy(origrequest)
                request.fstype = filesystem
                request.format = TRUE
                
                if request.fstype.isMountable():
                    request.mountpoint = mountCombo.entry.get_text()
                else:
                    request.mountpoint = None
                    
                if primonlycheckbutton.get_active():
                    primonly = TRUE
                else:
                    primonly = None

                if not newbycyl:
                    if fixedrb.get_active():
                        grow = None
                    else:
                        grow = TRUE

                    if fillmaxszrb.get_active():
                        maxsize = fillmaxszsb.get_value_as_int()
                    else:
                        maxsize = None

                    if len(driveclist.selection) == len(self.diskset.disks.keys()):
                        allowdrives = None
                    else:
                        allowdrives = []
                        for i in driveclist.selection:
                            allowdrives.append(self.diskset.disks.keys()[i])

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
                if origrequest.fstype.isMountable():
                    request.mountpoint =  mountCombo.entry.get_text()

    #            filesystem = fstypeoptionMenu.get_active().get_data("type")
    #            origrequest.fstype = filesystem

                if formatButton:
                    request.format = formatButton.get_active()
                else:
                    request.format = 0

                err = sanityCheckPartitionRequest(self.partitions, request)
                if err:
                    self.intf.messageWindow(_("Error With Request"),
                                            "%s" % (err))
                    continue
            
            # backup current (known working) configuration
            backpart = self.partitions.copy()
            if origrequest.device or origrequest.type != REQUEST_NEW:
                self.partitions.removeRequest(origrequest)

            self.partitions.addRequest(request)
            if self.refresh():
                self.partitions = backpart
                self.refresh()
            else:
                break

        dialog.close()

    def deleteCb(self, widget):
        node = self.tree.selection[0]
        partition = self.tree.node_get_row_data (node)
        if partition == None:
            dialog = GnomeWarningDialog(_("You must first select a partition"),
                                        parent=self.parent)
            dialog.set_position(WIN_POS_CENTER)            
            dialog.run()
            return
        elif type(partition) == type("RAID"):
            # XXXX evil way to reference RAID device requests!!
            request = self.partitions.getRequestByDeviceName(partition)
            if request:
                self.partitions.removeRequest(request)
            else: # shouldn't happen
                raise ValueError, "Deleting a non-existenent partition"
        elif partition.type & parted.PARTITION_FREESPACE:
            dialog = GnomeWarningDialog(_("You cannot remove free space."),
                                        parent=self.parent)
            dialog.set_position(WIN_POS_CENTER)
            dialog.run()
            return
        else:
            # see if device is in our partition requests, remove
            request = self.partitions.getRequestByDeviceName(get_partition_name(partition))
            if request:
                if self.partitions.isRaidMember(request):
                    dialog = GnomeWarningDialog(_("You cannot remove this "
                           "partition, as it is part of a RAID device."))
                    dialog.set_position(WIN_POS_CENTER)
                    dialog.run()
                    return

                self.partitions.removeRequest(request)
                if request.type == REQUEST_PREEXIST:
                    # get the drive
                    drive = partition.geom.disk.dev.path[5:]
                    delete = DeleteSpec(drive, partition.geom.start, partition.geom.end)
                    self.partitions.addDelete(delete)
            else: # shouldn't happen
                raise ValueError, "Deleting a non-existenent partition"

        # cheating
        self.refresh()
            
    def clearTree(self):
        node = self.tree.node_nth(0)
        while node:
            self.tree.remove_node(node)
            node = self.tree.node_nth(0)
        self.tree.set_selection_mode (SELECTION_SINGLE)
        self.tree.set_selection_mode (SELECTION_BROWSE)

    def resetCb(self, *args):
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
                   _("Could not allocated requested partitions: %s.") % (msg))
            rc = -1
        self.populate()
        self.tree.thaw()
        self.checkNextConditions()

        return rc

    def editCb(self, widget):
        node = self.tree.selection[0]
        partition = self.tree.node_get_row_data (node)

        if partition == None:
            dialog = GnomeWarningDialog(_("You must first select an existing "
                                          "partition or free space to edit."),
                                        parent=self.parent)
            dialog.set_position(WIN_POS_CENTER)            
            dialog.run()
            return
        elif type(partition) == type("RAID"):
            # XXXX evil way to reference RAID device requests!!
            request = self.partitions.getRequestByDeviceName(partition)
            if request:
                self.editRaidDevice(request)
                return
            else:
                raise ValueError, "Editting a non-existenent partition"
        elif partition.type & parted.PARTITION_FREESPACE:

            # create new request of size 1M
            request = PartitionSpec(fileSystemTypeGetDefault(), REQUEST_NEW,
                           start = start_sector_to_cyl(partition.geom.disk.dev,
                                                       partition.geom.start),
                           end = end_sector_to_cyl(partition.geom.disk.dev,
                                                   partition.geom.end),
                           drive = [get_partition_drive(partition)])
            self.editPartitionRequest(request)
            return
        
        elif partition.type & parted.PARTITION_EXTENDED:
            return

        # otherwise this is a "normal" partition to edit
        request = self.partitions.getRequestByDeviceName(get_partition_name(partition))

        if request:
            if self.partitions.isRaidMember(request):
                dialog = GnomeWarningDialog(_("You cannot edit this "
                          "partition, as it is part of a RAID device."))
                dialog.set_position(WIN_POS_CENTER)
                dialog.run()
                return
            else:
                self.editPartitionRequest(request)
        else:
            raise ValueError, "Editting a non-existenent partition"

    def editRaidDevice(self, raidrequest):
        #
        # start of editRaidDevice
        #
        dialog = GnomeDialog(_("Make Raid Device"))
        dialog.set_parent(self.parent)
        dialog.append_button (_("OK"))
        dialog.append_button (_("Cancel"))
        dialog.set_position(WIN_POS_CENTER)
        dialog.close_hides(TRUE)
        
        maintable = GtkTable()
        maintable.set_row_spacings (5)
        maintable.set_col_spacings (5)
        row = 0

        availraidparts = get_available_raid_partitions(self.diskset,
                                                      self.partitions.requests,
                                                       raidrequest)

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
                                                            mountCombo)
        maintable.attach(fstypeoption, 1, 2, row, row + 1)
            
        row = row + 1

        # raid level
        maintable.attach(createAlignedLabel(_("RAID Level:")),
                                            0, 1, row, row + 1)

        # Create here, pack below
        numparts =  len(availraidparts)
        if raidrequest.raidlevel:
            maxspares = get_raid_max_spares(raidrequest.raidlevel, numparts)
        else:
            maxspares = 0

        spareAdj = GtkAdjustment (value = 0, lower = 0,
                               upper = maxspares, step_incr = 1)
        sparesb = GtkSpinButton(spareAdj, digits = 0)
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
        maintable.attach(createAlignedLabel(_("Raid Members:")),
                         0, 1, row, row + 1)

        # XXX need to pass in currently used partitions for this device
        raidclist = createAllowedRaidPartitionsClist(availraidparts,
                                                     raidrequest.raidmembers)

        maintable.attach(raidclist, 1, 2, row, row + 1)
        row = row + 1

        # number of spares - created widget above
        maintable.attach(createAlignedLabel(_("Number of spares?:")),
                         0, 1, row, row + 1)
        maintable.attach(sparesb, 1, 2, row, row + 1)
        row = row + 1

        # format or not?
        if raidrequest.fstype and raidrequest.fstype.isFormattable():
            formatButton = GtkCheckButton (_("Format partition?"))
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
            if rc == 1:
                dialog.close()
                return
            elif rc == -1:
                # something died in dialog
                raise ValueError, "Died inside of raid edit dialog!"

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
                raidmembers.append(PartedPartitionDevice(availraidparts[i][0]))

            request.raidmembers = raidmembers
            request.raidspares = sparesb.get_value_as_int()
            request.raidlevel = leveloptionmenu.get_active().get_data("level")
            
            if formatButton:
                request.format = formatButton.get_active()
            else:
                request.format = 0

            err = sanityCheckRaidRequest(self.partitions, request)
            if err:
                self.intf.messageWindow(_("Error With Request"),
                                        "%s" % (err))
                continue
            
            # backup current (known working) configuration
            backpart = self.partitions.copy()

            # XXX should only remove if we know we put it in before
            try:
                self.partitions.removeRequest(raidrequest)
            except:
                pass

            self.partitions.addRequest(request)
            
            if self.refresh():
                self.partitions = backpart
                self.refresh()
            else:
                break

        dialog.close()

    def makeraidCB(self, widget):
        request = PartitionSpec(fileSystemTypeGetDefault(), REQUEST_RAID, 1)
        self.editRaidDevice(request)

    def getScreen (self, fsset, diskset, partitions, intf):
        self.fsset = fsset
        self.diskset = diskset
        self.intf = intf
        
        self.diskset.openDevices()
        self.partitions = partitions

        for part in self.partitions.requests:
            print part
        
        # XXX PartitionRequests() should already exist and
        # if upgrade or going back, have info filled in
#        self.newFsset = self.fsset.copy()

        # operational buttons
        buttonBox = GtkHButtonBox()
        buttonBox.set_layout (BUTTONBOX_SPREAD)

        ops = ((_("New"), self.newCB),
               (_("Edit"), self.editCb),
               (_("Delete"), self.deleteCb),
               (_("Reset"), self.resetCb),
               (_("Make Raid"), self.makeraidCB))
        for label, cb in ops:
            button = GtkButton (label)
            buttonBox.add (button)
            button.connect ("clicked", cb)
        
        # set up the tree
        titles = [N_("Device"), N_("Start"), N_("End"),
                  N_("Size (MB)"), N_("Type"), N_("Mount Point")]
        
        # do two things: enumerate the location of each field and translate
        self.titleSlot = {}
        i = 0
        for title in titles:
            self.titleSlot[title] = i
            titles[i] = _(title)
            i = i + 1

        self.numCols = len(titles)
        self.tree = GtkCTree (self.numCols, 0, titles)
        self.tree.set_selection_mode (SELECTION_BROWSE)
        self.tree.set_column_justification(1, JUSTIFY_RIGHT)
        self.tree.set_column_justification(2, JUSTIFY_RIGHT)
        self.tree.set_column_justification(3, JUSTIFY_RIGHT)
        self.tree.connect ("tree_select_row", self.treeSelectCb)

        # set up the canvas
        self.diskStripeGraph = DiskStripeGraph(self.tree)
        
        # do the initial population of the tree and the graph
        self.populate (initial = 1)
        self.checkNextConditions()

        box = GtkVBox(FALSE, 5)
        sw = GtkScrolledWindow()
        sw.add (self.diskStripeGraph.getCanvas())
        sw.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)
        box.pack_start (sw, TRUE)
        box.pack_start (buttonBox, FALSE)
        sw = GtkScrolledWindow()
        sw.add (self.tree)
        sw.set_policy (POLICY_NEVER, POLICY_AUTOMATIC)
        box.pack_start (sw, TRUE)

	return box



class AutoPartitionWindow(InstallWindow):
    def __init__(self, ics):
    	InstallWindow.__init__(self, ics)
        ics.setTitle (_("Automatic Disk Setup"))
        ics.setNextEnabled (TRUE)
        self.parent = ics.getICW().window

    def getNext(self):
        pass

    def getScreen(self, type, cleardrives, diskset, intf):
        vbox = GtkVBox(FALSE, 5)
        if type == CLEARPART_TYPE_LINUX:
            clearstring = "all Linux partitions"
        elif type == CLEARPART_TYPE_ALL:
            clearstring = "all partitions"
        else:
            clearstring = "no partitions"

        if not cleardrives or len(cleardrives) < 1:
            cleardrivestring = "on all drives"
        else:
            cleardrivestring = "on these drives: "
            for drive in cleardrives:
                cleardrivestring = cleardrivestring + drive + " "
                
        vbox.pack_start(GtkLabel(_("Autopartitioning will clear %s %s.") %
                                 (clearstring, cleardrivestring)))

        return vbox
