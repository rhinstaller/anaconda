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
from partRequests import *
from partition_ui_helpers_gui import *
from constants import *


class PartitionEditor:
    def formatOptionCB(self, widget, data):
	(menuwidget, menu, mntptcombo, ofstype) = data
	menuwidget.set_sensitive(widget.get_active())

	# inject event for fstype menu
	if widget.get_active():
	    fstype = menu.get_active().get_data("type")
	    setMntPtComboStateFromType(fstype, mntptcombo)
	else:
	    setMntPtComboStateFromType(ofstype, mntptcombo)

    def noformatCB(self, widget, badblocks):
	badblocks.set_sensitive(widget.get_active())

    def sizespinchangedCB(self, widget, fillmaxszsb):
	size = widget.get_value_as_int()
	maxsize = fillmaxszsb.get_value_as_int()
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

	fixedrb     = gtk.RadioButton(label=_("Fixed size"))
	fillmaxszrb = gtk.RadioButton(group=fixedrb,
				      label=_("Fill all space up "
					      "to (MB):"))
	maxsizeAdj = gtk.Adjustment(value = 1, lower = 1,
				    upper = MAX_PART_SIZE, step_incr = 1)
	fillmaxszsb = gtk.SpinButton(maxsizeAdj, digits = 0)
	fillmaxszsb.set_property('numeric', gtk.TRUE)
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
                filesystem = self.newfstypeMenu.get_active().get_data("type")

                request = copy.copy(self.origrequest)
                request.fstype = filesystem
                request.format = gtk.TRUE
                
                if request.fstype.isMountable():
                    request.mountpoint = self.mountCombo.entry.get_text()
                else:
                    request.mountpoint = None
                    
                if self.primonlycheckbutton.get_active():
                    primonly = gtk.TRUE
                else:
                    primonly = None

                if self.badblocks and self.badblocks.get_active():
                    request.badblocks = gtk.TRUE
                else:
                    request.badblocks = None

                if not self.newbycyl:
                    if self.fixedrb.get_active():
                        grow = None
                    else:
                        grow = gtk.TRUE

                    if self.fillmaxszrb.get_active():
                        maxsize = self.fillmaxszsb.get_value_as_int()
                    else:
                        maxsize = None

		    allowdrives = []
		    model = self.driveview.get_model()
		    iter = model.get_iter_first()
		    next = 1
		    while next:
			val   = model.get_value(iter, 0)
			drive = model.get_value(iter, 1)

			if val:
			    allowdrives.append(drive)

			next = model.iter_next(iter)

                    if len(allowdrives) == len(self.diskset.disks.keys()):
                        allowdrives = None
			
                    request.size = self.sizespin.get_value_as_int()
                    request.drive = allowdrives
                    request.grow = grow
                    request.primary = primonly
                    request.maxSizeMB = maxsize
                else:
                    request.start = self.startcylspin.get_value_as_int()
                    request.end = self.endcylspin.get_value_as_int()

                    if request.end <= request.start:
                        self.intf.messageWindow(_("Error With Request"),
                                                _("The end cylinder must be "
                                                "greater than the start "
                                                "cylinder."))

                        continue

                err = request.sanityCheckRequest(self.partitions)
                if err:
                    self.intf.messageWindow(_("Error With Request"),
                                            "%s" % (err))
                    continue
            else:
                # preexisting partition, just set mount point and format flag
                request = copy.copy(self.origrequest)
                if self.formatrb:
                    request.format = self.formatrb.get_active()
                    if request.format:
                        request.fstype = self.fstypeMenu.get_active().get_data("type")
                    if self.badblocks and self.badblocks.get_active():
                        request.badblocks = gtk.TRUE
                    else:
                        request.badblocks = None
                        
                else:
                    request.format = 0
                    request.badblocks = None

                if self.migraterb:
                    request.migrate = self.migraterb.get_active()
                    if request.migrate:
                        request.fstype =self.migfstypeMenu.get_active().get_data("type")
                else:
                    request.migrate = 0

                # set back if we are not formatting or migrating
                if not request.format and not request.migrate:
                    request.fstype = self.origrequest.origfstype

                if request.fstype.isMountable():
                    request.mountpoint =  self.mountCombo.entry.get_text()
                else:
                    request.mountpoint = None

                err = request.sanityCheckRequest(self.partitions)
                if err:
                    self.intf.messageWindow(_("Error With Request"),
                                            "%s" % (err))
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


    def __init__(self, partitions, diskset, intf, parent, origrequest, isNew = 0):
	self.partitions = partitions
	self.diskset = diskset
	self.origrequest = origrequest
	self.isNew = isNew
	self.intf = intf
	self.parent = parent

        self.dialog = gtk.Dialog(_("Add Partition"), self.parent)
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
        maintable.attach(createAlignedLabel(_("Mount Point:")),
                                            0, 1, row, row + 1)
        self.mountCombo = createMountPointCombo(origrequest)
        maintable.attach(self.mountCombo, 1, 2, row, row + 1)
        row = row + 1

        # Partition Type
        if self.origrequest.type == REQUEST_NEW:
            maintable.attach(createAlignedLabel(_("Filesystem Type:")),
                             0, 1, row, row + 1)

            (self.newfstype, self.newfstypeMenu) = createFSTypeMenu(self.origrequest.fstype,
                                                          fstypechangeCB,
                                                          self.mountCombo)
            maintable.attach(self.newfstype, 1, 2, row, row + 1)
        else:
            maintable.attach(createAlignedLabel(_("Original Filesystem "
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
            self.newfstype = None
            self.newfstypeMenu = None
            
        row = row + 1

        # allowable drives
        if self.origrequest.type == REQUEST_NEW:
            if not self.newbycyl:
                maintable.attach(createAlignedLabel(_("Allowable Drives:")),
                                 0, 1, row, row + 1)

                self.driveview = createAllowedDrivesList(self.diskset.disks,
							 self.origrequest.drive)

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
            maintable.attach(createAlignedLabel(_("Original Filesystem "
                                                  "Label:")),
                             0, 1, row, row + 1)
            fslabel = gtk.Label(self.origrequest.fslabel)
            maintable.attach(fslabel, 1, 2, row, row + 1)

            row = row + 1

        # size
        if self.origrequest.type == REQUEST_NEW:
            if not self.newbycyl:
                # Size specification
                maintable.attach(createAlignedLabel(_("Size (MB):")),
                                 0, 1, row, row + 1)
                sizeAdj = gtk.Adjustment(value = 1, lower = 1,
                                         upper = MAX_PART_SIZE, step_incr = 1)
                self.sizespin = gtk.SpinButton(sizeAdj, digits = 0)
                self.sizespin.set_property('numeric', gtk.TRUE)

                if self.origrequest.size:
                    self.sizespin.set_value(self.origrequest.size)

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
                maintable.attach(createAlignedLabel(_("Start Cylinder:")),
                                 0, 1, row, row + 1)

                maxcyl = self.diskset.disks[origrequest.drive[0]].dev.cylinders
                cylAdj = gtk.Adjustment(value=origrequest.start,
                                        lower=origrequest.start,
                                        upper=maxcyl,
                                        step_incr=1)
                self.startcylspin = gtk.SpinButton(cylAdj, digits=0)
                self.startcylspin.set_property('numeric', gtk.TRUE)
                maintable.attach(self.startcylspin, 1, 2, row, row + 1)
                row = row + 1
                
                endcylAdj = gtk.Adjustment(value=origrequest.end,
                                           lower=origrequest.start,
                                           upper=maxcyl,
                                           step_incr=1)
                maintable.attach(createAlignedLabel(_("End Cylinder:")),
                                 0, 1, row, row + 1)
                self.endcylspin = gtk.SpinButton(endcylAdj, digits = 0)
                self.endcylspin.set_property('numeric', gtk.TRUE)
                maintable.attach(self.endcylspin, 1, 2, row, row + 1)

                self.startcylspin.connect("changed", self.cylspinchangedCB,
					  (dev, self.startcylspin,
					   self.endcylspin, bycyl_sizelabel))
                self.endcylspin.connect("changed", self.cylspinchangedCB,
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

        # format/migrate options for pre-existing partitions
        if self.origrequest.type == REQUEST_PREEXIST and self.origrequest.fstype:

            ofstype = self.origrequest.fstype
            
            maintable.attach(gtk.HSeparator(), 0, 2, row, row + 1)
            row = row + 1

            label = gtk.Label(_("How would you like to prepare the filesystem "
                               "on this partition?"))
            label.set_line_wrap(1)
            label.set_alignment(0.0, 0.0)
#            label.set_size_request(400, -1)

            maintable.attach(label, 0, 2, row, row + 1)
            row = row + 1
            
            self.noformatrb = gtk.RadioButton(label=_("Leave unchanged "
                                                 "(preserve data)"))
            self.noformatrb.set_active(1)
            maintable.attach(self.noformatrb, 0, 2, row, row + 1)
            row = row + 1

            self.formatrb = gtk.RadioButton(label=_("Format partition as:"),
					    group =self.noformatrb)
            self.formatrb.set_active(0)
            if self.origrequest.format:
                self.formatrb.set_active(1)

            maintable.attach(self.formatrb, 0, 1, row, row + 1)
            (self.fstype, self.fstypeMenu) = createFSTypeMenu(ofstype,
							      fstypechangeCB,
							      self.mountCombo)
            self.fstype.set_sensitive(self.formatrb.get_active())
            maintable.attach(self.fstype, 1, 2, row, row + 1)
            row = row + 1

            if not self.formatrb.get_active() and not self.origrequest.migrate:
                self.mountCombo.set_data("prevmountable", ofstype.isMountable())

            self.formatrb.connect("toggled", self.formatOptionCB,
				  (self.fstype, self.fstypeMenu,
				   self.mountCombo, ofstype))

            if self.origrequest.origfstype.isMigratable():
                self.migraterb = gtk.RadioButton(label=_("Migrate partition to:"),
                                            group=self.noformatrb)
                self.migraterb.set_active(0)
                if self.origrequest.migrate:
                    self.migraterb.set_active(1)

                self.migtypes = self.origrequest.origfstype.getMigratableFSTargets()

                maintable.attach(self.migraterb, 0, 1, row, row + 1)
                (self.migfstype, self.migfstypeMenu)=createFSTypeMenu(ofstype,
								      None, None,
								      availablefstypes = self.migtypes)
                self.migfstype.set_sensitive(self.migraterb.get_active())
                maintable.attach(self.migfstype, 1, 2, row, row + 1)
                row = row + 1

                self.migraterb.connect("toggled", self.formatOptionCB,
				       (self.migfstype, self.migfstypeMenu,
					self.mountCombo, ofstype))
            else:
                self.migraterb = None

            self.badblocks = gtk.CheckButton(_("Check for bad blocks?"))
            self.badblocks.set_active(0)
            maintable.attach(self.badblocks, 0, 1, row, row + 1)
            self.formatrb.connect("toggled", self.noformatCB, self.badblocks)
            if not self.origrequest.format:
                self.badblocks.set_sensitive(0)

            if self.origrequest.badblocks:
                self.badblocks.set_active(1)
            
            row = row + 1
            
        else:
            self.noformatrb = None
            self.formatrb = None
            self.migraterb = None

        # size options
        if self.origrequest.type == REQUEST_NEW:
            if not self.newbycyl:
                (sizeframe, self.fixedrb, self.fillmaxszrb,
                 self.fillmaxszsb) = self.createSizeOptionsFrame(self.origrequest,
							    self.fillmaxszCB)
                self.sizespin.connect("changed", self.sizespinchangedCB,
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
            self.primonlycheckbutton = gtk.CheckButton(_("Force to be a primary "
                                                    "partition"))
            self.primonlycheckbutton.set_active(0)
            if self.origrequest.primary:
                self.primonlycheckbutton.set_active(1)
            maintable.attach(self.primonlycheckbutton, 0, 2, row, row+1)
            row = row + 1

            self.badblocks = gtk.CheckButton(_("Check for bad blocks"))
            self.badblocks.set_active(0)
            maintable.attach(self.badblocks, 0, 1, row, row + 1)
            row = row + 1
            if self.origrequest.badblocks:
                self.badblocks.set_active(1)
            
        # put main table into dialog
        self.dialog.vbox.pack_start(maintable)
        self.dialog.show_all()

