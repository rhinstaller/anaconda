#
# partition_dialog_gui.py: dialog for editting a partition request
#
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

import copy

import gobject
import gtk

from rhpl.translate import _, N_

import gui
from fsset import *
from cryptodev import LUKSDevice
from partRequests import *
from partition_ui_helpers_gui import *
from constants import *


class PartitionEditor:
    def sizespinchangedCB(self, widget, fillmaxszsb):
	size = widget.get_value_as_int()
	maxsize = fillmaxszsb.get_value_as_int()
        if size < 1:
            widget.set_value(1)
            size = 1
	if size > maxsize:
	    fillmaxszsb.set_value(size)

	# ugly got to be better way
	adj = fillmaxszsb.get_adjustment()
	adj.clamp_page(size, adj.upper)
	fillmaxszsb.set_adjustment(adj)

    def cylspinchangedCB(self, widget, data):
	(dev, startcylspin, endcylspin, bycyl_sizelabel) = data
	startsec = start_cyl_to_sector(dev,
				       startcylspin.get_value_as_int())
	endsec = end_cyl_to_sector(dev, endcylspin.get_value_as_int())
	cursize = (endsec - startsec)/2048
	bycyl_sizelabel.set_text("%s" % (int(cursize))) 

    def fillmaxszCB(self, widget, spin):
	spin.set_sensitive(widget.get_active())

    # pass in CB defined above because of two scope limitation of python!
    def createSizeOptionsFrame(self, request, fillmaxszCB):
	frame = gtk.Frame(_("Additional Size Options"))
	sizeoptiontable = gtk.Table()
	sizeoptiontable.set_row_spacings(5)
	sizeoptiontable.set_border_width(4)

	fixedrb     = gtk.RadioButton(label=_("_Fixed size"))
	fillmaxszrb = gtk.RadioButton(group=fixedrb,
				      label=_("Fill all space _up "
					      "to (MB):"))
	maxsizeAdj = gtk.Adjustment(value = 1, lower = 1,
				    upper = MAX_PART_SIZE, step_incr = 1)
	fillmaxszsb = gtk.SpinButton(maxsizeAdj, digits = 0)
	fillmaxszsb.set_property('numeric', True)
	fillmaxszhbox = gtk.HBox()
	fillmaxszhbox.pack_start(fillmaxszrb)
	fillmaxszhbox.pack_start(fillmaxszsb)
	fillunlimrb = gtk.RadioButton(group=fixedrb,
				     label=_("Fill to maximum _allowable "
					     "size"))

	fillmaxszrb.connect("toggled", fillmaxszCB, fillmaxszsb)

	# default to fixed, turn off max size spinbutton
	fillmaxszsb.set_sensitive(0)
	if request.grow:
	    if request.maxSizeMB != None:
		fillmaxszrb.set_active(1)
		fillmaxszsb.set_sensitive(1)
		fillmaxszsb.set_value(request.maxSizeMB)
	    else:
		fillunlimrb.set_active(1)
	else:
	    fixedrb.set_active(1)

	sizeoptiontable.attach(fixedrb, 0, 1, 0, 1)
	sizeoptiontable.attach(fillmaxszhbox, 0, 1, 1, 2)
	sizeoptiontable.attach(fillunlimrb, 0, 1, 2, 3)

	frame.add(sizeoptiontable)

	return (frame, fixedrb, fillmaxszrb, fillmaxszsb)


    def run(self):
	if self.dialog is None:
	    return None

        while 1:
            rc = self.dialog.run()
	    
            # user hit cancel, do nothing
            if rc == 2:
                self.destroy()
                return None

            if self.origrequest.type == REQUEST_NEW:
                # read out UI into a partition specification
                filesystem = self.newfstypeCombo.get_active_value()

                request = copy.copy(self.origrequest)
                request.fstype = filesystem
                request.format = True
                
                if request.fstype.isMountable():
                    request.mountpoint = self.mountCombo.get_children()[0].get_text()
                else:
                    request.mountpoint = None
                    
                if self.primonlycheckbutton.get_active():
                    primonly = True
                else:
                    primonly = None

                if self.lukscb and self.lukscb.get_active():
                    if not request.encryption:
                        request.encryption = LUKSDevice(passphrase=self.partitions.encryptionPassphrase, format=1)
                else:
                    request.encryption = None

                if self.badblocks and self.badblocks.get_active():
                    request.badblocks = True
                else:
                    request.badblocks = None

                if not self.newbycyl:
                    if self.fixedrb.get_active():
                        grow = None
                    else:
                        grow = True

                    self.sizespin.update()

                    if self.fillmaxszrb.get_active():
                        self.fillmaxszsb.update()
                        maxsize = self.fillmaxszsb.get_value_as_int()
                    else:
                        maxsize = None

		    allowdrives = []
		    model = self.driveview.get_model()
		    iter = model.get_iter_first()
		    while iter:
			val   = model.get_value(iter, 0)
			drive = model.get_value(iter, 1)

			if val:
			    allowdrives.append(drive)

                        iter = model.iter_next(iter)

                    if len(allowdrives) == len(self.diskset.disks.keys()):
                        allowdrives = None
			
                    request.size = self.sizespin.get_value_as_int()
                    request.drive = allowdrives
                    request.grow = grow
                    request.primary = primonly
                    request.maxSizeMB = maxsize
                else:
                    self.startcylspin.update()
                    self.endcylspin.update()
                    
                    request.start = self.startcylspin.get_value_as_int()
                    request.end = self.endcylspin.get_value_as_int()
                    request.primary = primonly

                    if request.end <= request.start:
                        self.intf.messageWindow(_("Error With Request"),
                                                _("The end cylinder must be "
                                                "greater than the start "
                                                "cylinder."), custom_icon="error")

                        continue

		err = request.sanityCheckRequest(self.partitions)
		if not err:
		    err = doUIRAIDLVMChecks(request, self.diskset)
		    
                if err:
                    self.intf.messageWindow(_("Error With Request"),
                                            "%s" % (err), custom_icon="error")
                    continue
            else:
                # preexisting partition, just set mount point and format flag
                request = copy.copy(self.origrequest)
                request.encryption = copy.deepcopy(self.origrequest.encryption)
		
		if self.fsoptionsDict.has_key("formatrb"):
		    formatrb = self.fsoptionsDict["formatrb"]
		else:
		    formatrb = None

		if formatrb:
                    request.format = formatrb.get_active()
                    if request.format:
                        request.fstype = self.fsoptionsDict["fstypeCombo"].get_active_value()
                    if self.fsoptionsDict.has_key("badblocks") and self.fsoptionsDict["badblocks"].get_active():
                        request.badblocks = True
                    else:
                        request.badblocks = None
                else:
                    request.format = 0
                    request.badblocks = None

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
		    
	    # everything ok, fall out of loop
	    break
            
	return request

    def destroy(self):
	if self.dialog:
	    self.dialog.destroy()
	self.dialog = None


    def __init__(self, anaconda, parent, origrequest, isNew = 0,
                 restrictfs = None):
        self.anaconda = anaconda
	self.partitions = self.anaconda.id.partitions
	self.diskset = self.anaconda.id.diskset
	self.intf = self.anaconda.intf
	self.origrequest = origrequest
	self.isNew = isNew
	self.parent = parent

	if isNew:
	    tstr = _("Add Partition")
	else:
	    try:
		tstr = _("Edit Partition: /dev/%s") % (origrequest.device,)
	    except:
		tstr = _("Edit Partition")
	    
        self.dialog = gtk.Dialog(tstr, self.parent)
        gui.addFrame(self.dialog)
        self.dialog.add_button('gtk-cancel', 2)
        self.dialog.add_button('gtk-ok', 1)
        self.dialog.set_position(gtk.WIN_POS_CENTER)
        
        maintable = gtk.Table()
        maintable.set_row_spacings(5)
        maintable.set_col_spacings(5)
        row = 0

        # see if we are creating a floating request or by cylinder
        if self.origrequest.type == REQUEST_NEW:
            self.newbycyl = self.origrequest.start != None

        # Mount Point entry
	lbl = createAlignedLabel(_("_Mount Point:"))
        maintable.attach(lbl, 0, 1, row, row + 1)
        self.mountCombo = createMountPointCombo(origrequest)
	lbl.set_mnemonic_widget(self.mountCombo)
        maintable.attach(self.mountCombo, 1, 2, row, row + 1)
        row = row + 1

        # Partition Type
        if self.origrequest.type == REQUEST_NEW:
	    lbl = createAlignedLabel(_("File System _Type:"))
            maintable.attach(lbl, 0, 1, row, row + 1)
            self.lukscb = gtk.CheckButton(_("_Encrypt"))
            self.newfstypeCombo = createFSTypeMenu(self.origrequest.fstype,
                                                   fstypechangeCB,
                                                   self.mountCombo,
                                                   availablefstypes = restrictfs,
                                                   lukscb = self.lukscb)
	    lbl.set_mnemonic_widget(self.newfstypeCombo)
            maintable.attach(self.newfstypeCombo, 1, 2, row, row + 1)
        else:
            maintable.attach(createAlignedLabel(_("Original File System "
                                                  "Type:")),
                             0, 1, row, row + 1)

            if self.origrequest.origfstype:
                typestr = self.origrequest.origfstype.getName()
                if self.origrequest.origfstype.getName() == "foreign":
                    part = get_partition_by_name(self.diskset.disks,
                                                 self.origrequest.device)
                    typestr = map_foreign_to_fsname(part.native_type)
            else:
                typestr = _("Unknown")

            fstypelabel = gtk.Label(typestr)
            maintable.attach(fstypelabel, 1, 2, row, row + 1)
            self.newfstypeCombo = None
            
        row = row + 1

        # allowable drives
        if self.origrequest.type == REQUEST_NEW:
            if not self.newbycyl:
		lbl = createAlignedLabel(_("Allowable _Drives:"))
                maintable.attach(lbl, 0, 1, row, row + 1)

                self.driveview = createAllowedDrivesList(self.diskset.disks,
                                                         self.origrequest.drive,
                                                         self.anaconda.updateSrc)
		lbl.set_mnemonic_widget(self.driveview)
                sw = gtk.ScrolledWindow()
                sw.add(self.driveview)
                sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		sw.set_shadow_type(gtk.SHADOW_IN)
                maintable.attach(sw, 1, 2, row, row + 1)
		self.driveview.set_size_request(375, 80)
            else:
                maintable.attach(createAlignedLabel(_("Drive:")),
                                 0, 1, row, row + 1)
                maintable.attach(createAlignedLabel(origrequest.drive[0]),
                                 1, 2, row, row + 1)

            row = row + 1

        # original fs label
        if self.origrequest.type != REQUEST_NEW and self.origrequest.fslabel:
            maintable.attach(createAlignedLabel(_("Original File System "
                                                  "Label:")),
                             0, 1, row, row + 1)
            fslabel = gtk.Label(self.origrequest.fslabel)
            maintable.attach(fslabel, 1, 2, row, row + 1)

            row = row + 1

        # size
        if self.origrequest.type == REQUEST_NEW:
            if not self.newbycyl:
                # Size specification
		lbl = createAlignedLabel(_("_Size (MB):"))
                maintable.attach(lbl, 0, 1, row, row + 1)
                sizeAdj = gtk.Adjustment(value = 1, lower = 1,
                                         upper = MAX_PART_SIZE, step_incr = 1)
                self.sizespin = gtk.SpinButton(sizeAdj, digits = 0)
                self.sizespin.set_property('numeric', True)

                if self.origrequest.size:
                    self.sizespin.set_value(self.origrequest.size)

		lbl.set_mnemonic_widget(self.sizespin)
                maintable.attach(self.sizespin, 1, 2, row, row + 1)
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

		lbl = createAlignedLabel(_("_Start Cylinder:"))
                maintable.attach(lbl, 0, 1, row, row + 1)

                maxcyl = self.diskset.disks[origrequest.drive[0]].dev.cylinders
                cylAdj = gtk.Adjustment(value=origrequest.start,
                                        lower=origrequest.start,
                                        upper=maxcyl,
                                        step_incr=1)
                self.startcylspin = gtk.SpinButton(cylAdj, digits=0)
                self.startcylspin.set_property('numeric', True)
		lbl.set_mnemonic_widget(self.startcylspin)
                maintable.attach(self.startcylspin, 1, 2, row, row + 1)
                row = row + 1
                
                endcylAdj = gtk.Adjustment(value=origrequest.end,
                                           lower=origrequest.start,
                                           upper=maxcyl,
                                           step_incr=1)
		lbl = createAlignedLabel(_("_End Cylinder:"))		
                maintable.attach(lbl, 0, 1, row, row + 1)
                self.endcylspin = gtk.SpinButton(endcylAdj, digits = 0)
                self.endcylspin.set_property('numeric', True)
		lbl.set_mnemonic_widget(self.endcylspin)
                maintable.attach(self.endcylspin, 1, 2, row, row + 1)

                self.startcylspin.connect("value-changed", self.cylspinchangedCB,
					  (dev, self.startcylspin,
					   self.endcylspin, bycyl_sizelabel))
                self.endcylspin.connect("value-changed", self.cylspinchangedCB,
					(dev, self.startcylspin,
					 self.endcylspin, bycyl_sizelabel))
                
                startsec = start_cyl_to_sector(dev, origrequest.start)
                endsec = end_cyl_to_sector(dev, origrequest.end)
                cursize = (endsec - startsec)/2048
                bycyl_sizelabel.set_text("%s" % (int(cursize)))
        else:
            maintable.attach(createAlignedLabel(_("Size (MB):")),
                             0, 1, row, row + 1)
            sizelabel = gtk.Label("%d" % (origrequest.size))
            maintable.attach(sizelabel, 1, 2, row, row + 1)
            self.sizespin = None
            
        row = row + 1

        # format/migrate options for pre-existing partitions, as long as they
        # aren't protected (we'd still like to be able to mount them, though)
	self.fsoptionsDict = {}
        if self.origrequest.type == REQUEST_PREEXIST and self.origrequest.fstype and not self.origrequest.getProtected():
	    (row, self.fsoptionsDict) = createPreExistFSOptionSection(self.origrequest, maintable, row, self.mountCombo)

        # size options
        if self.origrequest.type == REQUEST_NEW:
            if not self.newbycyl:
                (sizeframe, self.fixedrb, self.fillmaxszrb,
                 self.fillmaxszsb) = self.createSizeOptionsFrame(self.origrequest,
							    self.fillmaxszCB)
                self.sizespin.connect("value-changed", self.sizespinchangedCB,
				      self.fillmaxszsb)

                maintable.attach(sizeframe, 0, 2, row, row + 1)
            else:
                # XXX need new by cyl options (if any)
                pass
            row = row + 1
        else:
            self.sizeoptiontable = None

        # create only as primary
        if self.origrequest.type == REQUEST_NEW:
            self.primonlycheckbutton = gtk.CheckButton(_("Force to be a _primary "
                                                    "partition"))
            self.primonlycheckbutton.set_active(0)
            if self.origrequest.primary:
                self.primonlycheckbutton.set_active(1)

            # only show if we have something other than primary
            if not self.diskset.onlyPrimaryParts():
                maintable.attach(self.primonlycheckbutton, 0, 2, row, row+1)
                row = row + 1

            self.lukscb.set_data("formatstate", 1)

            if self.origrequest.encryption:
                self.lukscb.set_active(1)
            else:
                self.lukscb.set_active(0)
            maintable.attach(self.lukscb, 0, 2, row, row + 1)
            row = row + 1

	    # disable option for badblocks checking
	    self.badblocks = None

	    # uncomment to reenable
            #self.badblocks = gtk.CheckButton(_("Check for _bad blocks"))
            #self.badblocks.set_active(0)
            #maintable.attach(self.badblocks, 0, 1, row, row + 1)
            #row = row + 1
            #if self.origrequest.badblocks:
            #    self.badblocks.set_active(1)
            
        # put main table into dialog
        self.dialog.vbox.pack_start(maintable)
        self.dialog.show_all()

