#
# lvm_dialog_gui.py: dialog for editting a volume group request
#
# Michael Fulbright <msf@redhat.com>
#
# Copyright 2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import copy

import gobject
import gtk

from rhpl.translate import _, N_

import gui
from fsset import *
from partRequests import *
from partition_ui_helpers_gui import *
from constants import *

class VolumeGroupEditor:

    def createAllowedLvmPartitionsList(self, alllvmparts, reqlvmpart, partitions):

	store = gtk.TreeStore(gobject.TYPE_BOOLEAN,
			      gobject.TYPE_STRING,
			      gobject.TYPE_STRING)
	partlist = WideCheckList(2, store)

	sw = gtk.ScrolledWindow()
	sw.add(partlist)
	sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
	sw.set_shadow_type(gtk.SHADOW_IN)

	for uid, size, used in alllvmparts:
	    request = partitions.getRequestByID(uid)
	    if request.type != REQUEST_RAID:
		partname = "%s" % (request.device,)
	    else:
		partname = "md%d" % (request.raidminor,)
	    partsize = "%8.0f MB" % size
	    if used or not reqlvmpart:
		selected = 1
	    else:
		selected = 0

	    partlist.append_row((partname, partsize), selected)

	return (partlist, sw)



    def getCurrentLogicalVolume(self):
	selection = self.logvollist.get_selection()
	rc = selection.get_selected()
	if rc:
	    model, iter = rc
	else:
	    return None

	return iter


    def editLogicalVolume(self, logrequest, isNew = 0):
        dialog = gtk.Dialog(_("Make Logical Volume"), self.parent)
        gui.addFrame(dialog)
        dialog.add_button('gtk-cancel', 2)
        dialog.add_button('gtk-ok', 1)
        dialog.set_position(gtk.WIN_POS_CENTER)

        maintable = gtk.Table()
        maintable.set_row_spacings(5)
        maintable.set_col_spacings(5)
        row = 0

	maintable.attach(createAlignedLabel(_("Mount point:")), 0, 1, row,row+1)
        mountCombo = createMountPointCombo(logrequest)
        maintable.attach(mountCombo, 1, 2, row, row + 1)
        row = row + 1

	maintable.attach(createAlignedLabel(_("Filesystem Type:")),
			 0, 1, row, row + 1)

	(newfstype, newfstypeMenu) = createFSTypeMenu(logrequest.fstype,
						      fstypechangeCB,
						      mountCombo,
						      ignorefs = ["software RAID", "physical volume (LVM)", "vfat"])
	maintable.attach(newfstype, 1, 2, row, row + 1)
	row = row+1
			 
        maintable.attach(createAlignedLabel(_("Logical Volume Name:")), 0, 1, row, row + 1)
        lvnameEntry = gtk.Entry(16)
        maintable.attach(lvnameEntry, 1, 2, row, row + 1)
	if logrequest and logrequest.logicalVolumeName:
	    lvnameEntry.set_text(logrequest.logicalVolumeName)
        row = row + 1

        maintable.attach(createAlignedLabel(_("Size (MB):")), 0, 1, row, row+1)
        sizeEntry = gtk.Entry(16)
        maintable.attach(sizeEntry, 1, 2, row, row + 1)
	if logrequest:
	    sizeEntry.set_text("%g" % (logrequest.size,))
        row = row + 1

        dialog.vbox.pack_start(maintable)
        dialog.show_all()

	while 1:
	    rc = dialog.run()
	    if rc == 2:
		dialog.destroy()
		return

	    fsystem = newfstypeMenu.get_active().get_data("type")
            mntpt = string.strip(mountCombo.entry.get_text())

	    # check size specification
	    badsize = 0
	    try:
		size = int(sizeEntry.get_text())
	    except:
		badsize = 1

	    if badsize or size <= 0:
		self.intf.messageWindow(_("Illegal size"),
					_("The requested size as entered is "
					  "not a valid number greater than 0."))
		continue
	    
	    # test mount point
            if logrequest:
                preexist = logrequest.preexist
            else:
                preexist = 0

	    if fsystem.isMountable():
		err = sanityCheckMountPoint(mntpt, fsystem, preexist)
	    else:
		mntpt = None
		err = None
		
	    if err:
		self.intf.messageWindow(_("Bad mount point"), err)
		continue

	    # see if mount point is used already
	    used = 0
	    if fsystem.isMountable():
		if not logrequest or mntpt != logrequest.mountpoint:
		    # check in existing requests
		    curreq = self.partitions.getRequestByMountPoint(mntpt)
		    if curreq:
			used = 1

		    # check in pending logical volume requests
		    if not used:
			for lv in self.logvolreqs:
			    if logrequest and logrequest.mountpoint and lv.mountpoint == logrequest.mountpoint:
				continue

			    if lv.mountpoint == mntpt:
				used = 1
				break

	    if used:
		self.intf.messageWindow(_("Mount point in use"),
					_("The mount point %s is in use, "
					  "please pick another.") % (mntpt,))
		continue

	    # check out logical volumne name
	    lvname = string.strip(lvnameEntry.get_text())

	    err = sanityCheckLogicalVolumeName(lvname)
	    if err:
		self.intf.messageWindow(_("Illegal Logical Volume Name"),err)
		continue

	    # is it in use?
	    used = 0
	    if logrequest:
		origlvname = logrequest.logicalVolumeName
	    else:
		origlvname = None
		
	    if not used:
		for lv in self.logvolreqs:
		    if logrequest and lv.mountpoint == logrequest.mountpoint:
			continue

		    if lv.logicalVolumeName == lvname:
			used = 1
			break
	    else:
		self.intf.messageWindow(_("Illegal logical volume name"),
					_("The logical volume name %s is "
					  "already in use. Please pick "
					  "another.") % (lvname,))
		continue

	    # everything ok
	    break

	if not isNew:
	    self.logvolreqs.remove(logrequest)
	    iter = self.getCurrentLogicalVolume()
	    self.logvolstore.remove(iter)
	    
        request = LogicalVolumeRequestSpec(fsystem, mountpoint = mntpt,
                                           lvname = lvname, size = size)
        self.logvolreqs.append(request)

	iter = self.logvolstore.append()
	self.logvolstore.set_value(iter, 0, lvname)
	if request.fstype and request.fstype.isMountable():
	    self.logvolstore.set_value(iter, 1, mntpt)
	self.logvolstore.set_value(iter, 2, "%g" % (size,))

	self.updateVGSpaceLabels()
        dialog.destroy()
	
    def editCurrentLogicalVolume(self):
	iter = self.getCurrentLogicalVolume()

	if iter is None:
	    return
	
	logvolname = self.logvolstore.get_value(iter, 0)
	logrequest = None
	for lv in self.logvolreqs:
	    if lv.logicalVolumeName == logvolname:
		logrequest = lv
		
	if logrequest is None:
	    return

	self.editLogicalVolume(logrequest)

    def addLogicalVolumeCB(self, widget):
        request = LogicalVolumeRequestSpec(fileSystemTypeGetDefault(), size = 1)
	self.editLogicalVolume(request, isNew = 1)
	return

    def editLogicalVolumeCB(self, widget):
	self.editCurrentLogicalVolume()
	return

    def delLogicalVolumeCB(self, widget):
	iter = self.getCurrentLogicalVolume()
	if iter is None:
	    return
	
	logvolname = self.logvolstore.get_value(iter, 0)
	if logvolname is None:
	    return

	rc = self.intf.messageWindow(_("Confirm Delete"),
				_("Are you sure you want to Delete the "
				"logical volume %s?") % (logvolname,),
				type = "custom", custom_buttons=["gtk-cancel", _("Delete")])
	if not rc:
	    return

	for lv in self.logvolreqs:
	    if lv.logicalVolumeName == logvolname:
		self.logvolreqs.remove(lv)

	self.logvolstore.remove(iter)

	self.updateVGSpaceLabels()
	return
    
    def logvolActivateCb(self, view, path, col):
	self.editCurrentLogicalVolume()

    def getSelectedPhysicalVolumes(self, model):
	pv = []
	iter = model.get_iter_root()
	next = 1
	while next:
	    val      = model.get_value(iter, 0)
	    partname = model.get_value(iter, 1)

	    if val:
		pvreq = self.partitions.getRequestByDeviceName(partname)
		id = pvreq.uniqueID
		pv.append(id)

	    next = model.iter_next(iter)

	return pv

    def computeVGSize(self, pvlist):
	availSpaceMB = 0
	for id in pvlist:
	    pvreq = self.partitions.getRequestByID(id)
	    availSpaceMB = (availSpaceMB +
			    pvreq.getActualSize(self.partitions,
						self.diskset))
	return availSpaceMB

    def computeLVSpaceNeeded(self, logreqs):
	neededSpaceMB = 0
	print logreqs
	for lv in logreqs:
	    print lv.getActualSize(self.partitions, self.diskset)
	    neededSpaceMB = neededSpaceMB + lv.getActualSize(self.partitions, self.diskset)

	return neededSpaceMB

    def updateVGSpaceLabels(self):
	pvlist = self.getSelectedPhysicalVolumes(self.lvmlist.get_model())
	tspace = self.computeVGSize(pvlist)
	self.totalSpaceLabel.set_text(("%8.0f MB") % (tspace,))
	self.freeSpaceLabel.set_text(("%8.0f MB") % (tspace - self.computeLVSpaceNeeded(self.logvolreqs),))

#
# run the VG editor we created
#
    def run(self):
	if self.dialog is None:
	    return None
	
	while 1:
	    rc = self.dialog.run()

	    if rc == 2:
		self.destroy()
		return None

	    pvlist = self.getSelectedPhysicalVolumes(self.lvmlist.get_model())
	    availSpaceMB = self.computeVGSize(pvlist)
	    print "Total size of volume group is %g MB" % (availSpaceMB,)

	    neededSpaceMB = self.computeLVSpaceNeeded(self.logvolreqs)
	    print "Required size for logical volumes is %g MB" % (neededSpaceMB,)

	    if neededSpaceMB > availSpaceMB:
		self.intf.messageWindow(_("Not enough space"),
					_("The logical volumes you have "
					  "configured require %g MB, but the "
					  "volume group only has %g MB.  Please "
					  "either make the volume group larger "
					  "or make the logical volume(s) smaller.") % (neededSpaceMB, availSpaceMB))
		continue

	    # check volume name
	    volname = string.strip(self.volnameEntry.get_text())
	    err = sanityCheckVolumeGroupName(volname)
	    if err:
		self.intf.messageWindow(_("Invalid Volume Group Name"), err)
		continue

	    if self.origvgrequest:
		origvname = self.origvgrequest.volumeGroupName
	    else:
		origname = None

	    if origvname != volname:
		tmpreq = VolumeGroupRequestSpec(physvols = pvlist,
                                                vgname = volname)
		if self.partitions.isVolumeGroupNameInUse(volname):
		    self.intf.messageWindow(_("Name in use"),
					    _("The volume group name %s is "
					      "already in use. Please pick "
					      "another." % (volname,)))
		    del tmpreq
		    continue

		del tmpreq

	    # everything ok
	    break

	request = VolumeGroupRequestSpec(physvols = pvlist, vgname = volname)

	return (request, self.logvolreqs)

    def destroy(self):
	if self.dialog:
	    self.dialog.destroy()
	self.dialog = None

    def __init__(self, partitions, diskset, intf, parent, origvgrequest, isNew = 0):
	self.partitions = partitions
	self.diskset = diskset
	self.origvgrequest = origvgrequest
	self.isNew = isNew
	self.intf = intf
	self.parent = parent

        self.availlvmparts = self.partitions.getAvailLVMPartitions(self.origvgrequest,
                                                              self.diskset)

        # if no raid partitions exist, raise an error message and return
        if len(self.availlvmparts) < 1:
	    self.intf.messageWindow(_("Not enough physical volumes"),
			       _("At least one LVM partition is needed."))
	    self.dialog = None
            return

        dialog = gtk.Dialog(_("Make LVM Device"), self.parent)
        gui.addFrame(dialog)
        dialog.add_button('gtk-cancel', 2)
        dialog.add_button('gtk-ok', 1)

        dialog.set_position(gtk.WIN_POS_CENTER)

        maintable = gtk.Table()
        maintable.set_row_spacings(5)
        maintable.set_col_spacings(5)
        row = 0

        # volume group name
	labelalign = gtk.Alignment()
	labelalign.set(0.0, 0.5, 0.0, 0.0)
	labelalign.add(createAlignedLabel(_("Volume Group Name:")))
        maintable.attach(labelalign, 0, 1, row, row + 1)
        self.volnameEntry = gtk.Entry(16)
	if not self.isNew:
	    self.volnameEntry.set_text(self.origvgrequest.volumeGroupName)
	    
        maintable.attach(self.volnameEntry, 1, 2, row, row + 1)
	row = row + 1

	labelalign = gtk.Alignment()
	labelalign.set(0.0, 0.5, 0.0, 0.0)
	labelalign.add(createAlignedLabel(_("Physical Extent:")))
        maintable.attach(labelalign, 0, 1, row, row + 1)
        self.extentEntry = gtk.Entry(16)
        maintable.attach(self.extentEntry, 1, 2, row, row + 1)
        row = row + 1

        (self.lvmlist, sw) = self.createAllowedLvmPartitionsList(self.availlvmparts, [], self.partitions)
        self.lvmlist.set_size_request(275, 80)
        maintable.attach(createAlignedLabel(_("Physical Volumes to Use:")), 0, 1,
			 row, row + 1)
        maintable.attach(sw, 1, 2, row, row + 1)
        row = row + 1

	labelalign = gtk.Alignment()
	labelalign.set(0.0, 0.5, 0.0, 0.0)
	labelalign.add(createAlignedLabel(_("Total Space:")))
        maintable.attach(labelalign, 0, 1, row, row + 1)
	self.totalSpaceLabel = gtk.Label("")
	self.totalSpaceLabel.set_text("Test")
	labelalign = gtk.Alignment()
	labelalign.set(0.0, 0.5, 0.0, 0.0)
	labelalign.add(self.totalSpaceLabel)
        maintable.attach(labelalign, 1, 2, row, row + 1)
        row = row + 1

	labelalign = gtk.Alignment()
	labelalign.set(0.0, 0.5, 0.0, 0.0)
	labelalign.add(createAlignedLabel(_("Free Space:")))
        maintable.attach(labelalign, 0, 1, row, row + 1)
	self.freeSpaceLabel = gtk.Label("")
	self.freeSpaceLabel.set_text("Test")
	labelalign = gtk.Alignment()
	labelalign.set(0.0, 0.5, 0.0, 0.0)
	labelalign.add(self.freeSpaceLabel)
        maintable.attach(labelalign, 1, 2, row, row + 1)
        row = row + 1

	maintable.attach(gtk.HSeparator(), 0, 2, row, row + 1)
	row = row + 1

	# populate list of logical volumes
        lvtable = gtk.Table()
        lvtable.set_row_spacings(5)
        lvtable.set_col_spacings(5)
	self.logvolstore = gtk.ListStore(gobject.TYPE_STRING,
				      gobject.TYPE_STRING,
				      gobject.TYPE_STRING)
	
        self.logvolreqs = self.partitions.getLVMLVForVG(self.origvgrequest)
	self.origvolreqs = copy.copy(self.logvolreqs)

	if self.logvolreqs:
	    for lvrequest in self.logvolreqs:
		iter = self.logvolstore.append()
		self.logvolstore.set_value(iter, 0, lvrequest.logicalVolumeName)
		if lvrequest.fstype and lvrequest.fstype.isMountable():
		    self.logvolstore.set_value(iter, 1, lvrequest.mountpoint)
		else:
		    self.logvolstore.set_value(iter, 1, "")
		self.logvolstore.set_value(iter, 2, "%g" % (lvrequest.getActualSize(self.partitions, self.diskset)))

	self.logvollist = gtk.TreeView(self.logvolstore)
        col = gtk.TreeViewColumn(_("Logical Volume Name"),
				 gtk.CellRendererText(), text=0)
        self.logvollist.append_column(col)
        col = gtk.TreeViewColumn(_("Mount Point"),
				 gtk.CellRendererText(), text=1)
        self.logvollist.append_column(col)
        col = gtk.TreeViewColumn(_("Size (MB)"),
				 gtk.CellRendererText(), text=2)
        self.logvollist.append_column(col)
        self.logvollist.connect('row-activated', self.logvolActivateCb)

        sw = gtk.ScrolledWindow()
        sw.add(self.logvollist)
        sw.set_size_request(100, 100)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
	sw.set_shadow_type(gtk.SHADOW_IN)
        lvtable.attach(sw, 0, 1, 0, 1)

	# button box of options
	lvbbox = gtk.VBox()
        add = gtk.Button(_("_Add"))
        add.connect("clicked", self.addLogicalVolumeCB)
	lvbbox.pack_start(add)
        edit = gtk.Button(_("_Edit"))
        edit.connect("clicked", self.editLogicalVolumeCB)
	lvbbox.pack_start(edit)
        delete = gtk.Button(_("_Delete"))
        delete.connect("clicked", self.delLogicalVolumeCB)
	lvbbox.pack_start(delete)

	lvalign = gtk.Alignment()
	lvalign.set(0.5, 0.0, 0.0, 0.0)
	lvalign.add(lvbbox)
        lvtable.attach(lvalign, 1, 2, 0, 1, gtk.SHRINK, gtk.SHRINK)

	# pack all logical volumne stuff in a frame
	lvtable.set_border_width(5)
	frame = gtk.Frame(_("Logical Volumes"))
	frame.add(lvtable)
	maintable.attach(frame, 0, 2, row, row+1)
	row = row + 1
	
	dialog.set_size_request(500, 400)

        dialog.vbox.pack_start(maintable)
        dialog.show_all()

	# set space labels to correct values
	self.updateVGSpaceLabels()

	self.dialog = dialog
