#
# raid_dialog_gui.py: dialog for editting a raid request
#
# Michael Fulbright <msf@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2004 Red Hat, Inc.
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
import datacombo

from rhpl.translate import _, N_

import gui
from fsset import *
from raid import availRaidLevels
from cryptodev import LUKSDevice
from partRequests import *
from partition_ui_helpers_gui import *
from constants import *

class RaidEditor:

    def createAllowedRaidPartitionsList(self, allraidparts, reqraidpart,
                                        preexist):

	store = gtk.TreeStore(gobject.TYPE_BOOLEAN,
			      gobject.TYPE_STRING,
			      gobject.TYPE_STRING)
	partlist = WideCheckList(2, store)

	sw = gtk.ScrolledWindow()
	sw.add(partlist)
	sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
	sw.set_shadow_type(gtk.SHADOW_IN)

	partrow = 0
	for part, size, used in allraidparts:
	    partname = "%s" % part
	    partsize = "%8.0f MB" % size
	    if used or not reqraidpart:
		selected = 1
	    else:
		selected = 0

            if preexist == 0 or selected == 1:
                partlist.append_row((partname, partsize), selected)

	return (partlist, sw)

    def createRaidLevelMenu(self, levels, reqlevel):
        levelcombo = gtk.combo_box_new_text()
	defindex = 0
	i = 0
	for lev in levels:
            levelcombo.append_text(lev)

	    if reqlevel and lev == reqlevel:
		defindex = i
	    i = i + 1

        levelcombo.set_active(defindex)

	if reqlevel and reqlevel == "RAID0":
	    self.sparesb.set_sensitive(0)

        if self.sparesb:
            levelcombo.connect("changed", self.raidlevelchangeCB, self.sparesb)
            
	return levelcombo

    def createRaidMinorMenu(self, minors, reqminor):
        minorcombo = datacombo.DataComboBox()
	defindex = 0
	i = 0
	for minor in minors:
            minorcombo.append("md%d" %(minor,), minor)
	    if reqminor and minor == reqminor:
		defindex = i
	    i = i + 1

        minorcombo.set_active(defindex)

	return minorcombo


    def raidlevelchangeCB(self, widget, sparesb):
	raidlevel = widget.get_model()[widget.get_active()][0]
	numparts = sparesb.get_data("numparts")
	maxspares = raid.get_raid_max_spares(raidlevel, numparts)

	if maxspares > 0 and raidlevel != "RAID0":
	    adj = sparesb.get_adjustment() 
	    value = adj.value 
	    if adj.value > maxspares: 
		value = maxspares 

	    sparesb.set_sensitive(1)
	    spareAdj = gtk.Adjustment(value = value, lower = 0,
				      upper = maxspares, step_incr = 1)
	    spareAdj.clamp_page(0, maxspares)
	    sparesb.set_adjustment(spareAdj)
	    sparesb.set_value(value)
	else:
	    sparesb.set_value(0)
	    sparesb.set_sensitive(0)

    def run(self):
	if self.dialog is None:
	    return None
	
	while 1:
	    rc = self.dialog.run()

	    # user hit cancel, do nothing
	    if rc == 2:
		self.destroy()
		return None

	    # read out UI into a partition specification
	    request = copy.copy(self.origrequest)
            request.encryption = copy.deepcopy(self.origrequest.encryption)

	    # doesn't make sense for RAID device
	    request.badblocks = None
            if not self.origrequest.getPreExisting():
                filesystem = self.fstypeCombo.get_active_value()
                request.fstype = filesystem

		if request.fstype.isMountable():
		    request.mountpoint = self.mountCombo.get_children()[0].get_text()
		else:
		    request.mountpoint = None

	    raidmembers = []
	    model = self.raidlist.get_model()
	    iter = model.get_iter_first()
	    while iter:
		val   = model.get_value(iter, 0)
		part = model.get_value(iter, 1)

		if val:
		    req = self.partitions.getRequestByDeviceName(part)
		    raidmembers.append(req.uniqueID)

                iter = model.iter_next(iter)

            if not self.origrequest.getPreExisting():
                request.raidminor = int(self.minorCombo.get_active_value())

                request.raidmembers = raidmembers
                model = self.levelcombo.get_model()
                request.raidlevel = model[self.levelcombo.get_active()][0]

                if request.raidlevel != "RAID0":
                    self.sparesb.update()
                    request.raidspares = self.sparesb.get_value_as_int()
                else:
                    request.raidspares = 0

		if self.formatButton:
		    request.format = self.formatButton.get_active()
		else:
		    request.format = 0

                if self.lukscb and self.lukscb.get_active():
                    if not request.encryption:
                        request.encryption = LUKSDevice(passphrase=self.partitions.encryptionPassphrase, format=1)
                else:
                    request.encryption = None
	    else:
		if self.fsoptionsDict.has_key("formatrb"):
		    formatrb = self.fsoptionsDict["formatrb"]
		else:
		    formatrb = None

		if formatrb:
                    request.format = formatrb.get_active()
                    if request.format:
                        request.fstype = self.fsoptionsDict["fstypeCombo"].get_active_value()
                else:
                    request.format = 0

		if self.fsoptionsDict.has_key("migraterb"):
		    migraterb = self.fsoptionsDict["migraterb"]
		else:
		    migraterb = None
		    
		if migraterb:
                    request.migrate = migraterb.get_active()
                    if request.migrate:
                        request.fstype =self.fsoptionsDict["migfstypeCombo"].get_active_value()
                else:
                    request.migrate = 0

                # set back if we are not formatting or migrating
		origfstype = self.origrequest.origfstype
                if not request.format and not request.migrate:
                    request.fstype = origfstype

                if request.fstype.isMountable():
                    request.mountpoint =  self.mountCombo.get_children()[0].get_text()
                else:
                    request.mountpoint = None

                lukscb = self.fsoptionsDict.get("lukscb")
                if lukscb and lukscb.get_active():
                    if not request.encryption:
                        request.encryption = LUKSDevice(passphrase=self.partitions.encryptionPassphrase, format=1)
                else:
                    request.encryption = None

	    err = request.sanityCheckRequest(self.partitions)
	    if err:
		self.intf.messageWindow(_("Error With Request"),
					"%s" % (err), custom_icon="error")
		continue

	    if (not request.format and
		request.mountpoint and request.formatByDefault()):
		if not queryNoFormatPreExisting(self.intf):
		    continue

	    # everything ok, break out
	    break


	return request

    def destroy(self):
	if self.dialog:
	    self.dialog.destroy()

	self.dialog = None
	
    def __init__(self, partitions, diskset, intf, parent, origrequest, isNew = 0):
	self.partitions = partitions
	self.diskset = diskset
	self.origrequest = origrequest
	self.isNew = isNew
	self.intf = intf
	self.parent = parent

	self.dialog = None

	#
	# start of editRaidRequest
	#
	availraidparts = self.partitions.getAvailRaidPartitions(origrequest,
								self.diskset)
	# if no raid partitions exist, raise an error message and return
	if len(availraidparts) < 2:
	    dlg = gtk.MessageDialog(self.parent, 0, gtk.MESSAGE_ERROR,
				    gtk.BUTTONS_OK,
				    _("At least two unused software RAID "
				      "partitions are needed to create "
				      "a RAID device.\n\n"
				      "First create at least two partitions "
				      "of type \"software RAID\", and then "
				      "select the \"RAID\" option again."))
	    gui.addFrame(dlg)
	    dlg.show_all()
	    dlg.set_position(gtk.WIN_POS_CENTER)
	    dlg.run()
	    dlg.destroy()
	    return

	if isNew:
	    tstr = _("Make RAID Device")
	else:
	    try:
		tstr = _("Edit RAID Device: /dev/md%s") % (origrequest.raidminor,)
	    except:
		tstr = _("Edit RAID Device")
		
	dialog = gtk.Dialog(tstr, self.parent)
	gui.addFrame(dialog)
	dialog.add_button('gtk-cancel', 2)
	dialog.add_button('gtk-ok', 1)
	dialog.set_position(gtk.WIN_POS_CENTER)

	maintable = gtk.Table()
	maintable.set_row_spacings(5)
	maintable.set_col_spacings(5)
	row = 0

	# Mount Point entry
	lbl = createAlignedLabel(_("_Mount Point:"))
	maintable.attach(lbl, 0, 1, row, row + 1)
	self.mountCombo = createMountPointCombo(origrequest)
	lbl.set_mnemonic_widget(self.mountCombo)
	maintable.attach(self.mountCombo, 1, 2, row, row + 1)
	row = row + 1

        # we'll maybe add this further down
        self.lukscb = gtk.CheckButton(_("_Encrypt"))
        self.lukscb.set_data("formatstate", 1)

	# Filesystem Type
        if not origrequest.getPreExisting():
            lbl = createAlignedLabel(_("_File System Type:"))
            maintable.attach(lbl, 0, 1, row, row + 1)
            self.fstypeCombo = createFSTypeMenu(origrequest.fstype,
                                                fstypechangeCB,
                                                self.mountCombo,
                                                ignorefs = ["software RAID", "PPC PReP Boot", "Apple Bootstrap"])
	    lbl.set_mnemonic_widget(self.fstypeCombo)
            maintable.attach(self.fstypeCombo, 1, 2, row, row + 1)
            row += 1
        else:
            maintable.attach(createAlignedLabel(_("Original File System Type:")),
                             0, 1, row, row + 1)
            if origrequest.fstype.getName():
                self.fstypeCombo = gtk.Label(origrequest.fstype.getName())
            else:
                self.fstypeCombo = gtk.Label(_("Unknown"))

            maintable.attach(self.fstypeCombo, 1, 2, row, row + 1)
            row += 1

            if origrequest.fslabel:
                maintable.attach(createAlignedLabel(_("Original File System "
                                                      "Label:")),
                                 0, 1, row, row + 1)
                maintable.attach(gtk.Label(origrequest.fslabel), 1, 2, row,
                                 row + 1)
                row += 1

	# raid minors
	lbl = createAlignedLabel(_("RAID _Device:"))	
	maintable.attach(lbl, 0, 1, row, row + 1)

        if not origrequest.getPreExisting():
            availminors = self.partitions.getAvailableRaidMinors()[:16]
            reqminor = origrequest.raidminor
            if reqminor is not None:
                availminors.append(reqminor)

            availminors.sort()
            self.minorCombo = self.createRaidMinorMenu(availminors, reqminor)
	    lbl.set_mnemonic_widget(self.minorCombo)
        else:
            self.minorCombo = gtk.Label("md%s" %(origrequest.raidminor,))
	maintable.attach(self.minorCombo, 1, 2, row, row + 1)
	row = row + 1

	# raid level
	lbl = createAlignedLabel(_("RAID _Level:"))
	maintable.attach(lbl, 0, 1, row, row + 1)

        if not origrequest.getPreExisting():
            # Create here, pack below
            numparts =  len(availraidparts)
            if origrequest.raidspares:
                nspares = origrequest.raidspares
            else:
                nspares = 0

            if origrequest.raidlevel:
                maxspares = raid.get_raid_max_spares(origrequest.raidlevel, numparts)
            else:
                maxspares = 0

            spareAdj = gtk.Adjustment(value = nspares, lower = 0,
                                      upper = maxspares, step_incr = 1)
            self.sparesb = gtk.SpinButton(spareAdj, digits = 0)
            self.sparesb.set_data("numparts", numparts)

            if maxspares > 0:
                self.sparesb.set_sensitive(1)
            else:
                self.sparesb.set_value(0)
                self.sparesb.set_sensitive(0)
        else:
            self.sparesb = gtk.Label(str(origrequest.raidspares))


        if not origrequest.getPreExisting():
            self.levelcombo = self.createRaidLevelMenu(availRaidLevels,
                                                       origrequest.raidlevel)
	    lbl.set_mnemonic_widget(self.levelcombo)
        else:
            self.levelcombo = gtk.Label(origrequest.raidlevel)

	maintable.attach(self.levelcombo, 1, 2, row, row + 1)
	row = row + 1

	# raid members
	lbl=createAlignedLabel(_("_RAID Members:"))
	maintable.attach(lbl, 0, 1, row, row + 1)

	# XXX need to pass in currently used partitions for this device
	(self.raidlist, sw) = self.createAllowedRaidPartitionsList(availraidparts,
                                                                   origrequest.raidmembers,
                                                                   origrequest.getPreExisting())

	lbl.set_mnemonic_widget(self.raidlist)
	self.raidlist.set_size_request(275, 80)
	maintable.attach(sw, 1, 2, row, row + 1)
	row = row + 1

        if origrequest.getPreExisting():
            self.raidlist.set_sensitive(False)

	# number of spares - created widget above
	lbl = createAlignedLabel(_("Number of _spares:"))
	maintable.attach(lbl, 0, 1, row, row + 1)
	maintable.attach(self.sparesb, 1, 2, row, row + 1)
	lbl.set_mnemonic_widget(self.sparesb)
	row = row + 1

	# format or not?
	self.formatButton = None
	self.fsoptionsDict = {}
	if (origrequest.fstype and origrequest.fstype.isFormattable()) and not origrequest.getPreExisting():
	    self.formatButton = gtk.CheckButton(_("_Format partition?"))
	    if origrequest.format == None or origrequest.format != 0:
		self.formatButton.set_active(1)
	    else:
		self.formatButton.set_active(0)
            # it only makes sense to show this for preexisting RAID
            if origrequest.getPreExisting():
                maintable.attach(self.formatButton, 0, 2, row, row + 1)
                row = row + 1

            # checkbutton for encryption using dm-crypt/LUKS
            if self.origrequest.encryption:
                self.lukscb.set_active(1)
            else:
                self.lukscb.set_active(0)
            maintable.attach(self.lukscb, 0, 2, row, row + 1)
            row = row + 1
	else:
	    (row, self.fsoptionsDict) = createPreExistFSOptionSection(self.origrequest, maintable, row, self.mountCombo, showbadblocks=0)

	# put main table into dialog
	dialog.vbox.pack_start(maintable)

	dialog.show_all()
	self.dialog = dialog
	return



class RaidCloneDialog:
    def createDriveList(self, diskset):

	store = gtk.ListStore(gobject.TYPE_STRING)
        view = gtk.TreeView(store)

	sw = gtk.ScrolledWindow()
	sw.add(view)
	sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
	sw.set_shadow_type(gtk.SHADOW_IN)

        drives = diskset.disks.keys()
        drives.sort()

        for drive in drives:
            iter = store.append()
            store.set_value(iter, 0, drive)
            
        view.set_property("headers-visible", False)

        col = gtk.TreeViewColumn("", gtk.CellRendererText(), text=0)
        view.append_column(col)
        
        return (sw, view)

    def getInterestingRequestsForDrive(self, drive):
        allrequests = self.partitions.getRequestsByDevice(self.diskset, drive)

	if allrequests is None or len(allrequests) == 0:
	    return allrequests

        # remove extended partitions
        requests = []
        for req in allrequests:
            try:
                part = partedUtils.get_partition_by_name(self.diskset.disks,
                                                         req.device)
            except:
                part = None

	    if part:
		if part.type & parted.PARTITION_EXTENDED:
		    continue
		elif part.type & parted.PARTITION_FREESPACE:
		    continue
		elif part.type & parted.PARTITION_METADATA:
		    continue
	    else:
		continue

            requests.append(req)

        return requests

    def sanityCheckSourceDrive(self):
        # first see if it has any non-software RAID partitions
        requests = self.getInterestingRequestsForDrive(self.sourceDrive)
        
        errmsg1 = _("The source drive has no partitions to be cloned.  "
                    "You must first define partitions of type "
                    "'software RAID' on this drive before it can be cloned.")
        if requests is None or len(requests) == 0:
            self.intf.messageWindow(_("Source Drive Error"), errmsg1,
				    custom_icon="error")
            return 1

        for req in requests:
            if not req.fstype or req.fstype.getName() != "software RAID":
                self.intf.messageWindow(_("Source Drive Error"),
                                        _("The source drive selected has "
                                          "partitions on it which are not of "
                                          "type 'software RAID'.\n\n"
                                          "These "
                                          "partitions will have to be removed "
                                          "before this drive can be cloned. "),
					custom_icon="error")
                return 1

        for req in requests:
            if not req.drive or req.drive[0] != self.sourceDrive or len(req.drive) > 1:
                self.intf.messageWindow(_("Source Drive Error"),
                                        _("The source drive selected has "
                                          "partitions which are not "
                                          "constrained to the drive /dev/%s.\n\n"
                                          "These partitions will have to be "
                                          "removed or restricted to this "
                                          "drive "
                                          "before this drive can be cloned. ")
                                        %(self.sourceDrive,), custom_icon="error")
                return 1

        for req in requests:
            if self.partitions.isRaidMember(req):
                self.intf.messageWindow(_("Source Drive Error"),
                                        _("The source drive selected has "
                                          "software RAID partition(s) which "
                                          "are members of an active "
                                          "software RAID device.\n\n"
                                          "These partitions will have to be "
                                          "removed before this drive "
                                          "can be cloned."), custom_icon="error")
                return 1

        return 0

    def sanityCheckTargetDrives(self):
        if self.targetDrives is None or len(self.targetDrives) < 1:
                self.intf.messageWindow(_("Target Drive Error"),
                                        _("Please select the target drives "
                                          "for the clone operation."), custom_icon="error")
                return 1

        if self.sourceDrive in self.targetDrives:
                self.intf.messageWindow(_("Target Drive Error"),
                                        _("The source drive /dev/%s cannot be "
                                          "selected as a target drive as well.") % (self.sourceDrive,), custom_icon="error")
                return 1

        for drive in self.targetDrives:
            requests = self.getInterestingRequestsForDrive(drive)
	    if requests is None:
		continue
	    
            for req in requests:
                rc = partIntfHelpers.isNotChangable(req, self.partitions)

                # If the partition is protected, we also can't delete it so
                # specify a reason why.
                if rc is None and req.getProtected():
                    rc = _("This partition is holding the data for the hard "
                           "drive install.")
                if rc:
                    self.intf.messageWindow(_("Target Drive Error"),
                                            _("The target drive /dev/%s "
                                              "has a partition which cannot "
                                              "be removed for the following "
                                              "reason:\n\n\"%s\"\n\n"
                                              "This partition must be removed "
                                              "before "
                                              "this drive can be a target.") %
                                            (drive, rc), custom_icon="error")
                    return 1

        return 0


    def cloneDrive(self):
	# first create list of interesting partitions on the source drive
        requests = self.getInterestingRequestsForDrive(self.sourceDrive)

	# no requests to clone, bail out
	if requests is None or len(requests) == 0:
	    return 0

	# now try to clear the target drives
	for device in self.targetDrives:
	    rc = doDeletePartitionsByDevice(self.intf, self.partitions,
					    self.diskset, device,
					    confirm=0, quiet=1)

	# now clone!
	for req in requests:
	    for drive in self.targetDrives:
		newreq = copy.copy(req)
		newreq.drive = [drive]
		newreq.uniqueID = None
		newreq.device = None
		newreq.preexist = 0
		newreq.dev = None
		self.partitions.addRequest(newreq)
		
	return 0
	

    def targetSelectFunc(self, model, path, iter):
        self.targetDrives.append(model.get_value(iter,0))
        
    def run(self):
	if self.dialog is None:
	    return None
	
	while 1:
	    rc = self.dialog.run()

	    # user hit cancel, do nothing
	    if rc == 2:
		self.destroy()
		return None

            # see what drive they selected as the source
            selection = self.sourceView.get_selection()
            (model, iter) = selection.get_selected()
            if iter is None:
                self.intf.messageWindow(_("Error"),
                                        _("Please select a source drive."),
					custom_icon="error")
                continue

            self.sourceDrive = model.get_value(iter, 0)

            # sanity check it
            if self.sanityCheckSourceDrive():
                continue
            
            # now get target drive(s)
            self.targetDrives = []
            selection = self.targetView.get_selection()
            selection.selected_foreach(self.targetSelectFunc)

            # sanity check it
            if self.sanityCheckTargetDrives():
                continue

	    # now give them last chance to bail
	    msgtxt = _("The drive /dev/%s will now be cloned to the "
		       "following drives:\n\n" % (self.sourceDrive,))
	    for drive in self.targetDrives:
		msgtxt = msgtxt + "\t" + "/dev/%s" % (drive,)

	    msgtxt = msgtxt + _("\n\nWARNING! ALL DATA ON THE TARGET DRIVES "
				"WILL BE DESTROYED.")
	    
	    rc = self.intf.messageWindow(_("Final Warning"),
					 msgtxt, type="custom",
					 custom_buttons = ["gtk-cancel", _("Clone Drives")], custom_icon="warning")
	    if not rc:
		return 0

	    # try to clone now
	    ret = self.cloneDrive()

	    if ret:
		self.intf.messageWindow(_("Error"),
					_("There was an error clearing the "
					  "target drives.  Cloning failed."),
					custom_icon="error")
		return 0

	    # if everything ok, break out
	    if not ret:
		break

	return 1

    def destroy(self):
	if self.dialog:
	    self.dialog.destroy()

	self.dialog = None
	
    def __init__(self, partitions, diskset, intf, parent):
	self.partitions = partitions
	self.diskset = diskset
	self.intf = intf
	self.parent = parent

	self.dialog = None
	self.dialog = gtk.Dialog(_("Make RAID Device"), self.parent)
        self.dialog.set_size_request(500, 400)
	gui.addFrame(self.dialog)
	self.dialog.add_button('gtk-cancel', 2)
	self.dialog.add_button('gtk-ok', 1)
	self.dialog.set_position(gtk.WIN_POS_CENTER)

        # present list of drives as source
        vbox = gtk.VBox()

        lbl = gui.WrappingLabel(_("Clone Drive Tool\n\n"
                                  "This tool allows you to significantly "
                                  "reduce the amount of effort required "
                                  "to setup RAID arrays.  The idea is to "
                                  "take a source drive which has been "
                                  "prepared with the desired partitioning "
                                  "layout, and clone this layout onto other "
                                  "similar sized drives.  Then a RAID device "
                                  "can be created.\n\n"
                                  "NOTE: The source drive must have "
                                  "partitions which are restricted to be on "
                                  "that drive only, and can only contain "
                                  "unused software RAID partitions.  Other "
                                  "partition types are not allowed.\n\n"
                                  "EVERYTHING on the target drive(s) will be "
                                  "destroyed by this process."))
        vbox.pack_start(lbl)
                                  
        box = gtk.HBox()

        lbl = gtk.Label(_("Source Drive:"))
        lbl.set_alignment(0.0, 0.0)
        box.pack_start(lbl, padding=5)
        (sw, self.sourceView) = self.createDriveList(diskset)
        selection = self.sourceView.get_selection()
        selection.set_mode(gtk.SELECTION_SINGLE)
        box.pack_start(sw)

        lbl = gtk.Label(_("Target Drive(s):"))
        lbl.set_alignment(0.0, 0.0)
        box.pack_start(lbl, padding=5)
        (sw, self.targetView) = self.createDriveList(diskset)
        selection = self.targetView.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        box.pack_start(sw)

        frame = gtk.Frame(_("Drives"))
        frame.add(box)
        vbox.pack_start(frame)

	# put contents into dialog
	self.dialog.vbox.pack_start(vbox)

	self.dialog.show_all()

	return



