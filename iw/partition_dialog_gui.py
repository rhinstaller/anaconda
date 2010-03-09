#
# partition_dialog_gui.py: dialog for editting a partition request
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
# All rights reserved.
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
# Author(s): Michael Fulbright <msf@redhat.com>
#

import copy

import gobject
import gtk

import gui
from storage.devices import PartitionDevice, LUKSDevice
from storage.deviceaction import *
from partition_ui_helpers_gui import *
from constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

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
	fillunlimrb = gtk.RadioButton(group=fixedrb,
				     label=_("Fill to maximum _allowable "
					     "size"))

	fillmaxszrb.connect("toggled", fillmaxszCB, fillmaxszsb)

	# default to fixed, turn off max size spinbutton
	fillmaxszsb.set_sensitive(0)
	if request.req_grow:
	    if request.req_max_size:
		fillmaxszrb.set_active(1)
		fillmaxszsb.set_sensitive(1)
		fillmaxszsb.set_value(request.req_max_size)
	    else:
		fillunlimrb.set_active(1)
	else:
	    fixedrb.set_active(1)

	sizeoptiontable.attach(fixedrb, 0, 1, 0, 1)
	sizeoptiontable.attach(fillmaxszrb, 0, 1, 1, 2)
	sizeoptiontable.attach(fillmaxszsb, 1, 2, 1, 2)
	sizeoptiontable.attach(fillunlimrb, 0, 1, 2, 3)

	frame.add(sizeoptiontable)

	return (frame, fixedrb, fillmaxszrb, fillmaxszsb)


    def run(self):
	if self.dialog is None:
	    return []

        while 1:
            rc = self.dialog.run()
            actions = []
            luksdev = None
	    
            # user hit cancel, do nothing
            if rc in [2, gtk.RESPONSE_DELETE_EVENT]:
                self.destroy()
                return []

            mountpoint = self.mountCombo.get_children()[0].get_text()
            if mountpoint == _("<Not Applicable>"):
                mountpoint = ""

            if mountpoint:
                used = False
                for (mp, dev) in self.storage.mountpoints.iteritems():
                    if mp == mountpoint and \
                       dev.id != self.origrequest.id and \
                       not (self.origrequest.format.type == "luks" and
                            self.origrequest in dev.parents):
                        used = True
                        break

                if used:
                    self.intf.messageWindow(_("Mount point in use"),
                                            _("The mount point \"%s\" is in "
                                              "use. Please pick another.") %
                                            (mountpoint,),
                                            custom_icon="error")
                    continue

            if not self.origrequest.exists:
                # read out UI into a partition specification
                fmt_class = self.newfstypeCombo.get_active_value()
                # there's nothing about origrequest we care about
                #request = copy.copy(self.origrequest)

                if self.primonlycheckbutton.get_active():
                    primary = True
                else:
                    primary = None

                if self.fixedrb.get_active():
                    grow = None
                else:
                    grow = True

                self.sizespin.update()

                if self.fillmaxszrb.get_active():
                    self.fillmaxszsb.update()
                    maxsize = self.fillmaxszsb.get_value_as_int()
                else:
                    maxsize = 0

                allowdrives = []
                model = self.driveview.get_model()
                iter = model.get_iter_first()
                while iter:
                    val   = model.get_value(iter, 0)
                    drive = model.get_value(iter, 1)

                    if val:
                        allowdrives.append(drive)

                    iter = model.iter_next(iter)

                if len(allowdrives) == len(self.storage.partitioned):
                    allowdrives = None

                size = self.sizespin.get_value_as_int()
                disks = []
                if allowdrives:
                    for drive in allowdrives:
                        for disk in self.storage.partitioned:
                            if disk.name == drive:
                                disks.append(disk)

                format = fmt_class(mountpoint=mountpoint)
                weight = self.anaconda.platform.weight(mountpoint=mountpoint,
                                                       fstype=format.type)
                if self.isNew:
                    request = self.storage.newPartition(size=size,
                                                        grow=grow,
                                                        maxsize=maxsize,
                                                        primary=primary,
                                                        format=format,
                                                        parents=disks,
                                                        weight=weight)
                else:
                    request = self.origrequest
                    request.weight = weight

                if self.lukscb and self.lukscb.get_active() and \
                   request.format.type != "luks":
                    luksformat = format
                    format = getFormat("luks",
                                       passphrase=self.storage.encryptionPassphrase)
                    luksdev = LUKSDevice("luks%d" % self.storage.nextID,
                                         format=luksformat,
                                         parents=request)
                elif self.lukscb and not self.lukscb.get_active() and \
                     self.origrequest.format.type == "luks":
                    # destroy the luks format and the mapped device
                    try:
                        luksdev = self.storage.devicetree.getChildren(self.origrequest)[0]
                    except IndexError:
                        pass
                    else:
                        actions.append(ActionDestroyFormat(luksdev))
                        actions.append(ActionDestroyDevice(luksdev))
                        luksdev = None

                    actions.append(ActionDestroyFormat(request))

                if self.isNew:
                    # we're all set, so create the actions
                    actions.append(ActionCreateDevice(request))
                else:
                    request.req_size = size
                    request.req_base_size = size
                    request.req_grow = grow
                    request.req_max_size = maxsize
                    request.req_primary = primary
                    request.req_disks = disks

                actions.append(ActionCreateFormat(request, format))
                if luksdev:
                    actions.append(ActionCreateDevice(luksdev))
                    actions.append(ActionCreateFormat(luksdev))
            else:
                # preexisting partition
                request = self.origrequest
                if request.format.type == "luks":
                    try:
                        usedev = self.storage.devicetree.getChildren(request)[0]
                    except IndexError:
                        usedev = request
                else:
                    usedev = request

                origformat = usedev.format
                devicetree = self.anaconda.storage.devicetree

                if self.fsoptionsDict.has_key("formatcb"):
                    if self.fsoptionsDict["formatcb"].get_active():
                        fmt_class = self.fsoptionsDict["fstypeCombo"].get_active_value()

                        # carry over exists, migrate, size, and device
                        # necessary for partition editor UI
                        format = fmt_class(mountpoint=mountpoint,
                                           device=usedev.path)

                        luksdev = None
                        if self.fsoptionsDict.has_key("lukscb") and \
                           self.fsoptionsDict["lukscb"].get_active() and \
                           (request.format.type != "luks" or
                            (request.format.exists and
                             not request.format.hasKey)):
                            luksdev = LUKSDevice("luks%d" % self.storage.nextID,
                                                 format=format,
                                                 parents=request)
                            format = getFormat("luks",
                                               device=self.origrequest.path,
                                               passphrase=self.storage.encryptionPassphrase)
                        elif self.fsoptionsDict.has_key("lukscb") and \
                             not self.fsoptionsDict["lukscb"].get_active() and \
                             request.format.type == "luks":
                            # user elected to format the device w/o encryption
                            try:
                                luksdev = self.storage.devicetree.getChildren(request)[0]
                            except IndexError:
                                pass
                            else:
                                actions.append(ActionDestroyFormat(luksdev))
                                actions.append(ActionDestroyDevice(luksdev))
                                luksdev = None

                            actions.append(ActionDestroyFormat(request))
                            # we set the new format's device while under the
                            # impression that the device was going to be
                            # encrypted, so we need to remedy that now
                            format.device = request.path
                            usedev = request

                        actions.append(ActionCreateFormat(usedev, format))
                        if luksdev:
                            actions.append(ActionCreateDevice(luksdev))
                            actions.append(ActionCreateFormat(luksdev))
                    elif not self.fsoptionsDict["formatcb"].get_active():
                        # if the format checkbutton is inactive, cancel all
                        # actions on this device that create or destroy
                        # formats
                        cancel = []
                        if request.originalFormat.type == "luks":
                            path = "/dev/mapper/luks-%s" % request.originalFormat.uuid
                            cancel.extend(devicetree.findActions(path=path))

                        cancel.extend(devicetree.findActions(type="destroy",
                                                             object="format",
                                                             devid=request.id))
                        cancel.extend(devicetree.findActions(type="create",
                                                             object="format",
                                                             devid=request.id))
                        cancel.reverse()
                        for action in cancel:
                            devicetree.cancelAction(action)

                        # even though we cancelled a bunch of actions, it's
                        # pretty much impossible to be sure we cancelled them
                        # in the correct order. make sure things are back to
                        # their original state.
                        request.format = request.originalFormat
                        if request.format.type == "luks":
                            try:
                                usedev = devicetree.getChildren(request)[0]
                            except IndexError:
                                usedev = request
                            else:
                                usedev.format = usedev.originalFormat
                        else:
                            usedev = request

                        if usedev.format.mountable:
                            usedev.format.mountpoint = mountpoint
                elif self.origrequest.protected and usedev.format.mountable:
                    # users can set a mountpoint for protected partitions
                    usedev.format.mountpoint = mountpoint

                request.weight = self.anaconda.platform.weight(mountpoint=mountpoint,
                                                               fstype=request.format.type)

                if self.fsoptionsDict.has_key("migratecb") and \
                   self.fsoptionsDict["migratecb"].get_active():
                    actions.append(ActionMigrateFormat(usedev))

                if self.fsoptionsDict.has_key("resizecb") and \
                   self.fsoptionsDict["resizecb"].get_active():
                    size = self.fsoptionsDict["resizesb"].get_value_as_int()

                    try:
                        actions.append(ActionResizeDevice(request, size))
                        if request.format.type and request.format.exists:
                            actions.append(ActionResizeFormat(request, size))
                    except ValueError:
                        pass

                if request.format.exists and \
                   getattr(request, "mountpoint", None) and \
                   self.storage.formatByDefault(request):
                    if not queryNoFormatPreExisting(self.intf):
                        continue

            # everything ok, fall out of loop
	    break

	return actions

    def destroy(self):
	if self.dialog:
	    self.dialog.destroy()
	self.dialog = None


    def __init__(self, anaconda, parent, origrequest, isNew = 0,
                 restrictfs = None):
        self.anaconda = anaconda
	self.storage = self.anaconda.storage
	self.intf = self.anaconda.intf
	self.origrequest = origrequest
	self.isNew = isNew
	self.parent = parent

	if isNew:
	    tstr = _("Add Partition")
	else:
	    tstr = _("Edit Partition: %s") % (origrequest.path,)
	    
        self.dialog = gtk.Dialog(tstr, self.parent)
        gui.addFrame(self.dialog)
        self.dialog.add_button('gtk-cancel', 2)
        self.dialog.add_button('gtk-ok', 1)
        self.dialog.set_position(gtk.WIN_POS_CENTER)
        
        maintable = gtk.Table()
        maintable.set_row_spacings(5)
        maintable.set_col_spacings(5)
        row = 0

        # if this is a luks device we need to grab info from two devices
        # to make it seem like one device. wee!
        if self.origrequest.format.type == "luks":
            try:
                luksdev = self.storage.devicetree.getChildren(self.origrequest)[0]
            except IndexError:
                usereq = self.origrequest
                luksdev = None
            else:
                usereq = luksdev
        else:
            luksdev = None
            usereq = self.origrequest

        # Mount Point entry
	lbl = createAlignedLabel(_("_Mount Point:"))
        maintable.attach(lbl, 0, 1, row, row + 1)
        self.mountCombo = createMountPointCombo(usereq)
	lbl.set_mnemonic_widget(self.mountCombo)
        maintable.attach(self.mountCombo, 1, 2, row, row + 1)
        row = row + 1

        # Partition Type
        if not self.origrequest.exists:
	    lbl = createAlignedLabel(_("File System _Type:"))
            maintable.attach(lbl, 0, 1, row, row + 1)

            self.newfstypeCombo = createFSTypeMenu(usereq.format,
                                                   fstypechangeCB,
                                                   self.mountCombo,
                                                   availablefstypes = restrictfs)
	    lbl.set_mnemonic_widget(self.newfstypeCombo)
            maintable.attach(self.newfstypeCombo, 1, 2, row, row + 1)
        else:
            self.newfstypeCombo = None
            
        row = row + 1

        # allowable drives
        if not self.origrequest.exists:
            lbl = createAlignedLabel(_("Allowable _Drives:"))
            maintable.attach(lbl, 0, 1, row, row + 1)

            req_disk_names = [d.name for d in self.origrequest.req_disks]
            self.driveview = createAllowedDrivesList(self.storage.partitioned,
                                                     req_disk_names,
                                                     disallowDrives=[self.anaconda.updateSrc])
            lbl.set_mnemonic_widget(self.driveview)
            sw = gtk.ScrolledWindow()
            sw.add(self.driveview)
            sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            sw.set_shadow_type(gtk.SHADOW_IN)
            maintable.attach(sw, 1, 2, row, row + 1)
            self.driveview.set_size_request(375, 80)

            row = row + 1

        # original fs type and label
        if self.origrequest.exists:
            maintable.attach(createAlignedLabel(_("Original File System Type:")),
                             0, 1, row, row + 1)
            self.fstypeCombo = gtk.Label(usereq.originalFormat.name)

            maintable.attach(self.fstypeCombo, 1, 2, row, row + 1)
            row += 1

            if getattr(usereq.originalFormat, "label", None):
                maintable.attach(createAlignedLabel(_("Original File System "
                                                      "Label:")),
                                 0, 1, row, row + 1)
                fslabel = gtk.Label(usereq.originalFormat.label)
                maintable.attach(fslabel, 1, 2, row, row + 1)
                row = row + 1

        # size
        if not self.origrequest.exists:
            # Size specification
            lbl = createAlignedLabel(_("_Size (MB):"))
            maintable.attach(lbl, 0, 1, row, row + 1)
            sizeAdj = gtk.Adjustment(value = 1, lower = 1,
                                     upper = MAX_PART_SIZE, step_incr = 1)
            self.sizespin = gtk.SpinButton(sizeAdj, digits = 0)
            self.sizespin.set_property('numeric', True)

            if self.origrequest.req_size:
                self.sizespin.set_value(self.origrequest.req_size)

            lbl.set_mnemonic_widget(self.sizespin)
            maintable.attach(self.sizespin, 1, 2, row, row + 1)
        else:
            self.sizespin = None
            
        row = row + 1

        # format/migrate options for pre-existing partitions, as long as they
        # aren't protected (we'd still like to be able to mount them, though)
	self.fsoptionsDict = {}
        if self.origrequest.exists and \
           not self.origrequest.protected:
	    (row, self.fsoptionsDict) = createPreExistFSOptionSection(self.origrequest, maintable, row, self.mountCombo, self.storage, luksdev=luksdev)

        # size options
        if not self.origrequest.exists:
            (sizeframe, self.fixedrb, self.fillmaxszrb,
             self.fillmaxszsb) = self.createSizeOptionsFrame(self.origrequest,
                                                        self.fillmaxszCB)
            self.sizespin.connect("value-changed", self.sizespinchangedCB,
                                  self.fillmaxszsb)

            maintable.attach(sizeframe, 0, 2, row, row + 1)
            row = row + 1
        else:
            self.sizeoptiontable = None

        # create only as primary
        if not self.origrequest.exists:
            self.primonlycheckbutton = gtk.CheckButton(_("Force to be a _primary "
                                                    "partition"))
            self.primonlycheckbutton.set_active(0)
            if self.origrequest.req_primary:
                self.primonlycheckbutton.set_active(1)

            # only show if we have something other than primary
            if self.storage.extendedPartitionsSupported():
                maintable.attach(self.primonlycheckbutton, 0, 2, row, row+1)
                row = row + 1

        # checkbutton for encryption using dm-crypt/LUKS
        if not self.origrequest.exists:
            self.lukscb = gtk.CheckButton(_("_Encrypt"))
            self.lukscb.set_data("formatstate", 1)

            if self.origrequest.format.type == "luks":
                self.lukscb.set_active(1)
            else:
                self.lukscb.set_active(0)
            maintable.attach(self.lukscb, 0, 2, row, row + 1)
            row = row + 1

        # put main table into dialog
        self.dialog.vbox.pack_start(maintable)
        self.dialog.show_all()

