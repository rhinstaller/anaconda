#
# lvm_dialog_gui.py: dialog for editing a volume group request
#
# Copyright (C) 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
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
import datacombo

import gui
from partition_ui_helpers_gui import *
from constants import *
from storage.devices import *
from storage.deviceaction import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

import logging
log = logging.getLogger("anaconda")

class VolumeGroupEditor:

    def getTempVG(self):
        pvs = [copy.deepcopy(pv) for pv in self.pvs]
        vg = LVMVolumeGroupDevice('tmp-%s' % self.vg.name,
                                  parents=pvs, peSize=self.peSize)
        for lv in self.lvs.values():
            _l = LVMLogicalVolumeDevice(lv['name'], vg, format=lv['format'],
                                   size=lv['size'], exists=lv['exists'],
                                   stripes=lv['stripes'],
                                   logSize=lv['logSize'],
                                   snapshotSpace=lv['snapshotSpace'])
            _l.originalFormat = lv['originalFormat']

        return vg

    def numAvailableLVSlots(self):
	return max(0, lvm.MAX_LV_SLOTS - len(self.lvs))

    def computeSpaceValues(self):
        vg = self.getTempVG()
        vgsize = vg.size
        vgfree = vg.freeSpace
        vgused = vgsize - vgfree
	return (vgsize, vgused, vgfree)

    def getPVWastedRatio(self, newpe):
        """ given a new pe value, return percentage of smallest PV wasted

        newpe - (int) new value of PE, in KB
        """
        pvlist = self.getSelectedPhysicalVolumes()

	waste = 0.0
	for pv in pvlist:
	    waste = max(waste, (long(pv.size*1024) % newpe)/(pv.size*1024.0))

	return waste

    def getSmallestPVSize(self):
        """ finds the smallest PV and returns its size in MB
        """
	first = 1
        pvlist = self.getSelectedPhysicalVolumes()
	for pv in pvlist:
            try:
                pesize = int(self.peCombo.get_active_value()) / 1024.0
            except:
                pesize = self.vg.peSize

            # FIXME: move this logic into a property of LVMVolumeGroupDevice
            pvsize = max(0, lvm.clampSize(pv.size, pesize) - pesize)
	    if first:
		minpvsize = pvsize
		first = 0
	    else:
		minpvsize = min(pvsize, minpvsize)

	return minpvsize


    def reclampLV(self, newpe):
        """ given a new pe value, set logical volume sizes accordingly

        newpe - (int) new value of PE, in MB
        """

        pvlist = self.getSelectedPhysicalVolumes()
        availSpaceMB = self.computeVGSize(pvlist, newpe)

        # see if total space is enough
        used = 0
        resize = False
        for lv in self.lvs.values():
            # total space required by an lv may be greater than lv size.
            vg_space = lv['size'] * lv['stripes'] + lv['logSize'] \
                        + lv['snapshotSpace']
            clamped_vg_space = lvm.clampSize(vg_space, newpe, roundup=1)
            used += clamped_vg_space
            if lv['size'] != lvm.clampSize(lv['size'], newpe, roundup=1):
                resize = True

        if used > availSpaceMB:
            self.intf.messageWindow(_("Not enough space"),
                                    _("The physical extent size cannot be "
                                      "changed because otherwise the space "
                                      "required by the currently defined "
                                      "logical volumes will be increased "
                                      "to more than the available space."),
				    custom_icon="error")
            return 0

	if resize:
	    rc = self.intf.messageWindow(_("Confirm Physical Extent Change"),
					 _("This change in the value of the "
					   "physical extent will require the "
					   "sizes of the current logical "
					   "volume requests to be rounded "
					   "up in size to an integer multiple "
					   "of the "
					   "physical extent.\n\nThis change "
					   "will take effect immediately."),
					 type="custom", custom_icon="question",
					 custom_buttons=["gtk-cancel", _("C_ontinue")])
	    if not rc:
		return 0

        for lv in self.lvs.values():
            lv['size'] = lvm.clampSize(lv['size'], newpe, roundup=1)

        return 1
            
    def peChangeCB(self, widget, *args):
        """ handle changes in the Physical Extent option menu

        widget - menu item which was activated
        peOption - the Option menu containing the items. The data value for
                   "lastval" is the previous PE value.
        """

        curval = int(widget.get_active_value())
        # this one's in MB so we can stop with all this dividing by 1024
        curpe = curval / 1024.0
        lastval = widget.get_data("lastpe")
	lastidx = widget.get_data("lastidx")

	# see if PE is too large compared to smallest PV
	maxpvsize = self.getSmallestPVSize()
	if curpe > maxpvsize:
            self.intf.messageWindow(_("Not enough space"),
                                    _("The physical extent size cannot be "
                                      "changed because the value selected "
				      "(%(curpe)10.2f MB) is larger than the "
				      "smallest physical volume "
				      "(%(maxpvsize)10.2f MB) in the volume "
				      "group.") % {'curpe': curpe,
				                   'maxpvsize': maxpvsize},
                                      custom_icon="error")
	    widget.set_active(lastidx)
            return 0

	# see if new PE will make any PV useless due to overhead
	if lvm.clampSize(maxpvsize, curpe) < curpe:
            self.intf.messageWindow(_("Not enough space"),
                                    _("The physical extent size cannot be "
                                      "changed because the value selected "
				      "(%(curpe)10.2f MB) is too large "
				      "compared to the size of the "
				      "smallest physical volume "
				      "(%(maxpvsize)10.2f MB) in the "
				      "volume group.")
				    % {'curpe': curpe, 'maxpvsize': maxpvsize},
                                    custom_icon="error")
	    widget.set_active(lastidx)
            return 0
	    

	if self.getPVWastedRatio(curpe) > 0.10:
	    rc = self.intf.messageWindow(_("Too small"),
					 _("This change in the value of the "
					   "physical extent will waste "
					   "substantial space on one or more "
					   "of the physical volumes in the "
					   "volume group."),
					 type="custom", custom_icon="error",
					   custom_buttons=["gtk-cancel", _("C_ontinue")])
	    if not rc:
		widget.set_active(lastidx)
		return 0

	# now see if we need to fixup effect PV and LV sizes based on PE
        if curval > lastval:
            rc = self.reclampLV(curpe)
            if not rc:
		widget.set_active(lastidx)
		return 0
            else:
                self.updateLogVolStore()
	else:
	    maxlv = lvm.getMaxLVSize()
	    for lv in self.lvs.values():
		if lv['size'] > maxlv:
		    self.intf.messageWindow(_("Not enough space"),
					    _("The physical extent size "
					      "cannot be changed because the "
					      "resulting maximum logical "
					      "volume size (%10.2f MB) is "
					      "smaller "
					      "than one or more of the "
					      "currently defined logical "
					      "volumes.") % (maxlv,),
					    custom_icon="error")
		    widget.set_active(lastidx)
		    return 0
            
        widget.set_data("lastpe", curval)
	widget.set_data("lastidx", widget.get_active())

        # now actually set the VG's extent size
        self.peSize = curpe
        self.updateAllowedLvmPartitionsList()
	self.updateVGSpaceLabels()

    def prettyFormatPESize(self, val):
        """ Pretty print for PE size in KB """
        if val < 1024:
            return "%s KB" % (val,)
        elif val < 1024*1024:
            return "%s MB" % (val/1024,)
        else:
            return "%s GB" % (val/1024/1024,)

    def createPEOptionMenu(self, default=4096):
        peCombo = datacombo.DataComboBox()

        actualPE = []
        for curpe in lvm.getPossiblePhysicalExtents(floor=1024):
            # don't show PE over 128M, unless it's the default
            if curpe > 131072 and curpe != default:
                continue

            actualPE.append(curpe)
            val = self.prettyFormatPESize(curpe)

            peCombo.append(val, curpe)

        # First try to set the combo's active value to the default we're
        # passed.  If that doesn't work, just set it to the first one to
        # prevent TypeErrors everywhere.
        try:
            peCombo.set_active(actualPE.index(default))
        except ValueError:
            peCombo.set_active(0)

        peCombo.set_data("lastidx", peCombo.get_active())
        peCombo.connect("changed", self.peChangeCB)
        peCombo.set_data("lastpe", default)

	return peCombo

    def clickCB(self, row, data):
	model = self.lvmlist.get_model()
	pvlist = self.getSelectedPhysicalVolumes()

	# get the selected row
	iter = model.get_iter((string.atoi(data),))

	# we invert val because we get called before checklist
	# changes the toggle state
	val      = not model.get_value(iter, 0)
	partname = model.get_value(iter, 1)
        pv = self.storage.devicetree.getDeviceByName(partname)
        if val:
            self.pvs.append(pv)
        else:
            self.pvs.remove(pv)
            try:
                vg = self.getTempVG()
            except DeviceError as e:
                self.intf.messageWindow(_("Not enough space"),
                                    _("You cannot remove this physical "
                                      "volume because otherwise the "
                                      "volume group will be too small to "
                                      "hold the currently defined logical "
                                      "volumes."), custom_icon="error")
                self.pvs.append(pv)
                return False

	self.updateVGSpaceLabels()
	return True

    def createAllowedLvmPartitionsList(self):
	store = gtk.TreeStore(gobject.TYPE_BOOLEAN,
			      gobject.TYPE_STRING,
			      gobject.TYPE_STRING)
	partlist = WideCheckList(2, store, self.clickCB)

	sw = gtk.ScrolledWindow()
	sw.add(partlist)
	sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
	sw.set_shadow_type(gtk.SHADOW_IN)

        origpvs = self.pvs[:]
	for device in self.availlvmparts:
	    # clip size to current PE
	    pesize = int(self.peCombo.get_active_value()) / 1024.0
	    size = lvm.clampSize(device.size, pesize)
	    size_string = "%10.2f MB" % size
            include = True
            selected = False

            # now see if the pv is in use either by a vg in the tree or by
            # the vg we are editing now
            if device in origpvs:
                selected = True
                include = True
            else:
                for vg in self.storage.vgs:
                    if vg.name == self.vg.name:
                        continue

                    if device in vg.pvs:
                        include = False
                        break

                if include and not origpvs:
                    selected = True

            if include:
                partlist.append_row((device.name, size_string), selected)
                if selected and device not in self.pvs:
                    self.pvs.append(device)

	return (partlist, sw)

    def updateAllowedLvmPartitionsList(self):
	""" update sizes in pv list """
	row = 0
	for part in self.availlvmparts:
	    size = part.size

	    # clip size to current PE
	    pesize = int(self.peCombo.get_active_value()) / 1024.0
	    size = lvm.clampSize(size, pesize)
	    partsize = "%10.2f MB" % size

	    iter = self.lvmlist.store.get_iter((int(row),))
	    self.lvmlist.store.set_value(iter, 2, partsize)
	    row = row + 1
	
    def getCurrentLogicalVolume(self):
	selection = self.logvollist.get_selection()
	(model, iter) = selection.get_selected()
	return iter

    def editLogicalVolume(self, lv, isNew = 0):
        # Mixing logical code and gtk code is confusing to me.  So I am going
        # to do the logic first and then create all the gtk crap!
        #
        # lv -- whatever self.logvolstore.get_value returns

        #newfstypelabel = None # File system type label & combo
        #newfstypeCombo = None
        newfslabellabel = None # File system Label label & combo
        newfslableCombo = None
        #lvnamelabel = None # Logical Volume name label & entry
        #lvnameentry = None
        #lvsizelabel = None # Logical Volume size label & entry
        #lvsizeentry = None
        maxsizelabel = None # Maximum size label
        #mountCombo = None # Mount Point Combo Box
        #tstr = None # String that appears on top of the window
        tempvg = self.getTempVG()  # copy of self.vg
        templv = None
        cpefsos = None # lambda function that represents
                       # createPreExistFSOptionSection

        # Define the string
        if isNew:
            tstr = _("Make Logical Volume")
        else:
            tstr = _("Edit Logical Volume: %s") % lv['name']

        # Create the mountCombo.  This is the box where the mountpoint will
        # appear.  Note that if the format is swap or Raiddevice, the mount
        # point is none-sense.
        templuks = None
        templv = self.getLVByName(lv['name'], vg=tempvg)
        usedev = templv
        if templv.format.type == "luks":
            templuks = LUKSDevice("luks-%s" % lv['name'],
                                  parents=[templv],
                                  format=self.luks[lv['name']],
                                  exists=templv.format.exists)
            usedev = templuks

        if lv['format'].type == "luks":
            format = self.luks[lv['name']]
        else:
            format = lv['format']

        if lv['exists']:
            _origlv = self.getLVByName(lv['name'])
            originalFormat = _origlv.originalFormat
            if originalFormat.type == "luks":
                try:
                    _origluks = self.storage.devicetree.getChildren(_origlv)[0]
                except IndexError:
                    pass
                else:
                    originalFormat = _origluks.originalFormat

        mountCombo = createMountPointCombo(usedev, excludeMountPoints=["/boot"])


        # Stuff appears differently when the lv exists and when the lv is new.
        # here we make that difference.  Except for newfslabelCombo,  and
        # maxsizelabel all vars will have a value != None.
        if not lv['exists']:
            # File system type lables & combo
            newfstypelabel = createAlignedLabel(_("_File System Type:"))
            newfstypeCombo = createFSTypeMenu(format, fstypechangeCB,mountCombo,
                    ignorefs = ["mdmember", "lvmpv", "efi", "prepboot", "appleboot"])
            newfstypelabel.set_mnemonic_widget(newfstypeCombo)

            # Logical Volume name label & entry
            lvnamelabel = createAlignedLabel(_("_Logical Volume Name:"))
            lvnameentry = gtk.Entry(32)
            lvnamelabel.set_mnemonic_widget(lvnameentry)
            if lv['name']:
                lvnameentry.set_text(lv['name'])
            else:
                lvnameentry.set_text(self.storage.createSuggestedLVName(self.getTempVG()))

            # Logical Volume size label & entry
            lvsizelabel = createAlignedLabel(_("_Size (MB):"))
            lvsizeentry = gtk.Entry(16)
            lvsizelabel.set_mnemonic_widget(lvsizeentry)
            lvsizeentry.set_text("%Ld" % lv['size'])

            # Maximum size label
            max_grow = tempvg.freeSpace / lv['stripes']
            maxsizelabel = createAlignedLabel(_("(Max size is %s MB)") %
                                              min(lvm.getMaxLVSize(),
                                                  lv['size'] + max_grow))

            # Encrypt Check Box button.
            self.lukscb = gtk.CheckButton(_("_Encrypt"))
            self.lukscb.set_data("formatstate", 1)
            if lv['format'].type == "luks":
                self.lukscb.set_active(1)
            else:
                self.lukscb.set_active(0)

        else:
            # File system type lable & combo
            newfstypelabel = createAlignedLabel(_("Original File System Type:"))
            newfstypeCombo = gtk.Label(originalFormat.name)

            # File system label label & combo
            if getattr(originalFormat, "label", None):
                newfslabellabel = createAlignedLabel(_("Original File System "
                                                      "Label:"))
                newfslableCombo = gtk.Label(originalFormat.label)

            # Logical Volume name label & entry
            lvnamelabel = createAlignedLabel(_("Logical Volume Name:"))
            lvnameentry = gtk.Label(lv['name'])

            # Logical Volume size label & entry
            lvsizelabel = createAlignedLabel(_("Size (MB):"))
            lvsizeentry = gtk.Label(str(lv['size']))

            # Create the File System Format Section
            self.fsoptionsDict = {}
            # We are going to lambda the createPreExistFSOptionSection so we can call
            # it latter with two arguments, row and mainttable.
            cpefsos = lambda table, row: createPreExistFSOptionSection(templv,
                    maintable, row, mountCombo, self.storage,
                    ignorefs = ["software RAID", "physical volume (LVM)", "vfat"],
                    luksdev=templuks)


        # Here is where the gtk crap begins.
        dialog = gtk.Dialog(tstr, self.parent)
        gui.addFrame(dialog)
        dialog.add_button('gtk-cancel', 2)
        dialog.add_button('gtk-ok', 1)
        dialog.set_position(gtk.WIN_POS_CENTER)

        # Initialize main table
        maintable = gtk.Table()
        maintable.set_row_spacings(5)
        maintable.set_col_spacings(5)
        row = 0

        # Add the mountCombo that we previously created
        lbl = createAlignedLabel(_("_Mount Point:"))
        maintable.attach(lbl, 0, 1, row,row+1)
        lbl.set_mnemonic_widget(mountCombo)
        maintable.attach(mountCombo, 1, 2, row, row + 1)
        row += 1

        # Add the filesystem combo labels.
        maintable.attach(newfstypelabel, 0, 1, row, row + 1)
        maintable.attach(newfstypeCombo, 1, 2, row, row + 1)
        row += 1

        # If there is a File system lable, add it.
        if newfslabellabel is not None and newfslableCombo is not None:
            maintable.attach(newfslabellabel, 0, 1, row, row + 1)
            maintable.attach(newfslableCombo, 1, 2, row, row + 1)
            row += 1

        # Add the logical volume name
        maintable.attach(lvnamelabel, 0, 1, row, row + 1)
        maintable.attach(lvnameentry, 1, 2, row, row + 1)
        row += 1

        # Add the logical volume size
        maintable.attach(lvsizelabel, 0, 1, row, row + 1)
        maintable.attach(lvsizeentry, 1, 2, row, row + 1)
        row += 1

        # If there is a maxsize, add it.
        if maxsizelabel is not None:
            maintable.attach(maxsizelabel, 1, 2, row, row + 1)

        # If we have the createPreExistFSOptionSection lamda function it means
        # that we have a preexisting lv and we must call the lambda function
        # to create the Pre exsisting FS option section.
        if cpefsos is not None:
            (row, self.fsoptionsDict) = cpefsos(maintable, row)

        # checkbutton for encryption using dm-crypt/LUKS
        # FIXME: Here we could not decouple the gtk stuff from the logic because
        #        of the createPreExistFSOptionSection function call.  We must
        #        decouple that function.
        if not lv['exists']:
            maintable.attach(self.lukscb, 0, 2, row, row + 1)
            row = row + 1
        else:
            self.lukscb = self.fsoptionsDict.get("lukscb")

        dialog.vbox.pack_start(maintable)
        dialog.show_all()
        # Here ends the gtk crap

        while 1:
            rc = dialog.run()
            if rc in [2, gtk.RESPONSE_DELETE_EVENT]:
                if isNew:
                    del self.lvs[lv['name']]
                dialog.destroy()
                return

            actions = []
            targetSize = None
            migrate = None
            format = None
            newluks = None

            if templv.format.type == "luks":
                format = self.luks[lv['name']]
            else:
                format = templv.format

            if not templv.exists:
                fmt_class = newfstypeCombo.get_active_value()
            else:
                # existing lv
                fmt_class = self.fsoptionsDict["fstypeCombo"].get_active_value()

            mountpoint = mountCombo.get_children()[0].get_text().strip()
            if mountpoint == _("<Not Applicable>"):
                mountpoint = ""

            # validate logical volume name
            lvname = lvnameentry.get_text().strip()
            if not templv.exists:
                err = sanityCheckLogicalVolumeName(lvname)
                if err:
                    self.intf.messageWindow(_("Illegal Logical Volume Name"),
                                            err, custom_icon="error")
                    continue

            # check that the name is not already in use
            used = 0
            for _lv in self.lvs.values():
                if _lv == lv:
                    continue

                if _lv['name'] == lvname:
                    used = 1
                    break

            if used:
                self.intf.messageWindow(_("Illegal logical volume name"),
                                        _("The logical volume name \"%s\" is "
                                          "already in use. Please pick "
                                          "another.") % (lvname,), custom_icon="error")
                continue

            # test mount point
            # check in pending logical volume requests
            # these may not have been put in master list of requests
            # yet if we have not hit 'OK' for the volume group creation
            if fmt_class().mountable and mountpoint:
                used = False
                curmntpt = getattr(format, "mountpoint", None)

                for _lv in self.lvs.values():
                    if _lv['format'].type == "luks":
                        _format = self.luks[_lv['name']]
                    else:
                        _format = _lv['format']

                    if not _format.mountable or curmntpt and \
                       _format.mountpoint == curmntpt:
                        continue

                    if _format.mountpoint == mountpoint:
                        used = True
                        break

                if not used:
                    # we checked this VG's LVs above; now check the rest of
                    # the devices in the tree
                    mountdevs = self.lvs.values()
                    full_name = "%s-%s" % (self.vg.name, lv['name'])
                    for (mp,d) in self.storage.mountpoints.iteritems():
                        if (d.type != "lvmlv" or d.vg.id != self.vg.id) and \
                           mp == mountpoint and \
                           not (isinstance(d, LUKSDevice) and
                                full_name in [dev.name for dev in d.parents]):
                            used = True
                            break

                if used:
                    self.intf.messageWindow(_("Mount point in use"),
                                            _("The mount point \"%s\" is in "
                                              "use. Please pick another.") %
                                            (mountpoint,),
                                            custom_icon="error")
                    continue

            # check that size specification is numeric and positive
            if not templv.exists:
                badsize = 0
                try:
                    size = long(lvsizeentry.get_text())
                except:
                    badsize = 1

                if badsize or size <= 0:
                    self.intf.messageWindow(_("Illegal size"),
                                            _("The requested size as entered is "
                                              "not a valid number greater "
                                              "than 0."), custom_icon="error")
                    continue
            else:
                size = templv.size

            # check that size specification is within limits
            pesize = int(self.peCombo.get_active_value()) / 1024.0
            size = lvm.clampSize(size, pesize, roundup=True)
            maxlv = lvm.getMaxLVSize()
            if size > maxlv:
                self.intf.messageWindow(_("Not enough space"),
                                        _("The current requested size "
                                          "(%(size)10.2f MB) is larger than "
                                          "the maximum logical volume size "
                                          "(%(maxlv)10.2f MB). "
                                          "To increase this limit you can "
                                          "create more Physical Volumes from "
                                          "unpartitioned disk space and "
                                          "add them to this Volume Group.")
                                          % {'size': size, 'maxlv': maxlv},
                                        custom_icon="error")
                continue

            # Ok -- now we've done all the checks to validate the
            # user-specified parameters. Time to set up the device...
            origname = templv.lvname
            if not templv.exists:
                templv._name = lvname
                try:
                    templv.size = size
                except ValueError:
                    self.intf.messageWindow(_("Not enough space"),
                                            _("The logical volumes you have "
                                              "configured require %(size)d MB,"
                                              " but the volume group only has "
                                              "%(tempvgsize)d MB.  Please "
                                              "either make the volume group "
                                              "larger or make the logical "
                                              "volume(s) smaller.")
                                              % {'size': size,
                                                 'tempvgsize': tempvg.size},
                                            custom_icon="error")
                    continue

                format = fmt_class(mountpoint=mountpoint)
                if self.lukscb and self.lukscb.get_active():
                    if templv.format.type != "luks":
                        newluks = format
                        format = getFormat("luks",
                                       passphrase=self.storage.encryptionPassphrase)
                    else:
                        newluks = format
                        format = templv.format

                templv.format = format
            else:
                # existing lv
                if self.fsoptionsDict.has_key("formatcb") and \
                   self.fsoptionsDict["formatcb"].get_active():
                    format = fmt_class(mountpoint=mountpoint)
                    if self.lukscb and self.lukscb.get_active() and \
                       templv.format.type != "luks":
                        newluks = format
                        format = getFormat("luks",
                                           device=templv.path,
                                           passphrase=self.storage.encryptionPassphrase)
                    elif self.lukscb and self.lukscb.get_active():
                        newluks = format
                        format = templv.format

                    templv.format = format
                elif self.fsoptionsDict.has_key("formatcb") and \
                     not self.fsoptionsDict["formatcb"].get_active():
                    templv.format = templv.originalFormat
                    format = templv.format

                if format.mountable:
                    format.mountpoint = mountpoint

                if self.fsoptionsDict.has_key("migratecb") and \
                   self.fsoptionsDict["migratecb"].get_active():
                    format.migrate = True

                if self.fsoptionsDict.has_key("resizecb") and self.fsoptionsDict["resizecb"].get_active():
                    targetSize = self.fsoptionsDict["resizesb"].get_value_as_int()
                    templv.targetSize = targetSize

            if format.exists and format.mountable and format.mountpoint:
                tempdev = StorageDevice('tmp', format=format)
                if self.storage.formatByDefault(tempdev) and \
                   not queryNoFormatPreExisting(self.intf):
                    continue

            # everything ok
            break

        if templv.format.type == "luks":
            if newluks:
                self.luks[templv.lvname] = newluks

            if self.luks.has_key(origname) and origname != templv.lvname:
                self.luks[templv.lvname] = self.luks[origname]
                del self.luks[templv.lvname]
        elif templv.format.type != "luks" and self.luks.has_key(origname):
            del self.luks[origname]

        self.lvs[templv.lvname] = {'name': templv.lvname,
                                   'size': templv.size,
                                   'format': templv.format,
                                   'originalFormat': templv.originalFormat,
                                   'stripes': templv.stripes,
                                   'logSize': templv.logSize,
                                   'snapshotSpace': templv.snapshotSpace,
                                   'exists': templv.exists}
        if self.lvs.has_key(origname) and origname != templv.lvname:
            del self.lvs[origname]

        self.updateLogVolStore()
        self.updateVGSpaceLabels()
        dialog.destroy()
        return

    def editCurrentLogicalVolume(self):
	iter = self.getCurrentLogicalVolume()

	if iter is None:
	    return
	
	logvolname = self.logvolstore.get_value(iter, 0)
	lv = self.lvs[logvolname]
	self.editLogicalVolume(lv)

    def addLogicalVolumeCB(self, widget):
        if self.numAvailableLVSlots() < 1:
            self.intf.messageWindow(_("No free slots"),
                P_("You cannot create more than %d logical volume "
                   "per volume group.",
                   "You cannot create more than %d logical volumes "
                   "per volume group.", lvm.MAX_LV_SLOTS)
                % (lvm.MAX_LV_SLOTS,),
                custom_icon="error")
            return

        (total, used, free) = self.computeSpaceValues()
	if free <= 0:
	    self.intf.messageWindow(_("No free space"),
				    _("There is no room left in the "
				      "volume group to create new logical "
				      "volumes. "
				      "To add a logical volume you must "
				      "reduce the size of one or more of "
				      "the currently existing "
				      "logical volumes"), custom_icon="error")
	    return

        tempvg = self.getTempVG()
        name = self.storage.createSuggestedLVName(tempvg)
        format = getFormat(self.storage.defaultFSType)
        self.lvs[name] = {'name': name,
                          'size': free,
                          'format': format,
                          'originalFormat': format,
                          'stripes': 1,
                          'logSize': 0,
                          'snapshotSpace': 0,
                          'exists': False}
        self.editLogicalVolume(self.lvs[name], isNew = 1)
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
				_("Are you sure you want to delete the "
				"logical volume \"%s\"?") % (logvolname,),
				type = "custom", custom_buttons=["gtk-cancel", _("_Delete")], custom_icon="warning")
	if not rc:
	    return

        del self.lvs[logvolname]
        self.logvolstore.remove(iter)
        self.updateVGSpaceLabels()
        return
    
    def logvolActivateCb(self, view, path, col):
	self.editCurrentLogicalVolume()

    def getSelectedPhysicalVolumes(self):
        model = self.lvmlist.get_model()
        pv = []
        next = model.get_iter_first()
        currow = 0
        while next is not None:
	    iter = next
	    val      = model.get_value(iter, 0)
	    partname = model.get_value(iter, 1)
	    
	    if val:
		dev = self.storage.devicetree.getDeviceByName(partname)
                pv.append(dev)

	    next = model.iter_next(iter)
	    currow = currow + 1

	return pv

    def computeVGSize(self, pvlist, curpe):
	availSpaceMB = 0L
	for pv in pvlist:
            # have to clamp pvsize to multiple of PE
            # XXX why the subtraction? fudging metadata?
	    pvsize = lvm.clampSize(pv.size, curpe) - (curpe/1024)

	    availSpaceMB = availSpaceMB + pvsize

        log.info("computeVGSize: vgsize is %s" % (availSpaceMB,))
	return availSpaceMB

    def updateLogVolStore(self):
        self.logvolstore.clear()
        for lv in self.lvs.values():
            iter = self.logvolstore.append()
            if lv['format'].type == "luks":
                format = self.luks[lv['name']]
            else:
                format = lv['format']

            mntpt = getattr(format, "mountpoint", "")
            if lv['name']:
                self.logvolstore.set_value(iter, 0, lv['name'])
                
            if format.type and format.mountable:
                self.logvolstore.set_value(iter, 1, mntpt)
	    else:
		self.logvolstore.set_value(iter, 1, "N/A")

            self.logvolstore.set_value(iter, 2, "%Ld" % lv['size'])

    def updateVGSpaceLabels(self):
        (total, used, free) = self.computeSpaceValues()

	self.totalSpaceLabel.set_text("%10.2f MB" % (total,))
	self.usedSpaceLabel.set_text("%10.2f MB" % (used,))

	if total > 0:
	    usedpercent = (100.0*used)/total
	else:
	    usedpercent = 0.0
	    
	self.usedPercentLabel.set_text("(%4.1f %%)" % (usedpercent,))

	self.freeSpaceLabel.set_text("%10.2f MB" % (free,))
	if total > 0:
	    freepercent = (100.0*free)/total
	else:
	    freepercent = 0.0

	self.freePercentLabel.set_text("(%4.1f %%)" % (freepercent,))

#
# run the VG editor we created
#
    def run(self):
	if self.dialog is None:
	    return []
	
	while 1:
	    rc = self.dialog.run()

	    if rc in [2, gtk.RESPONSE_DELETE_EVENT]:
		self.destroy()
		return []

	    pvlist = self.getSelectedPhysicalVolumes()

	    # check volume name
	    volname = self.volnameEntry.get_text().strip()
	    err = sanityCheckVolumeGroupName(volname)
	    if err:
		self.intf.messageWindow(_("Invalid Volume Group Name"), err,
					custom_icon="error")
		continue

	    origvname = self.vg.name

	    if origvname != volname:
                # maybe we should see if _any_ device has this name
		if volname in [vg.name for vg in self.storage.vgs]:
		    self.intf.messageWindow(_("Name in use"),
					    _("The volume group name \"%s\" is "
					      "already in use. Please pick "
					      "another." % (volname,)),
					    custom_icon="error")
		    continue

	    # get physical extent
	    pesize = int(self.peCombo.get_active_value()) / 1024.0

	    # everything ok
	    break
        return self.convertToActions()

    def convertToActions(self):
        # here we have to figure out what all was done and convert it to
        # devices and actions
        #
        # set up the vg with the right pvs
        # set up the lvs
        #  set up the lvs' formats
        #
        log.debug("finished editing vg")
        log.debug("pvs: %s" % [p.name for p in self.pvs])
        log.debug("luks: %s" % self.luks.keys())
        volname = self.volnameEntry.get_text().strip()
        pesize = int(self.peCombo.get_active_value()) / 1024.0
        for lv in self.lvs.itervalues():
            log.debug("lv %s" % lv)
            _luks = self.luks.get(lv['name'])
            if _luks:
                log.debug("  luks: %s" % _luks)

        actions = []
        origlvs = self.vg.lvs
        if not self.vg.exists:
            log.debug("non-existing vg -- setting up lvs, pvs, name, pesize")
            # remove all of the lvs
            for lv in self.vg.lvs:
                self.vg._removeLogVol(lv)

            # set up the pvs
            for pv in self.vg.pvs:
                if pv not in self.pvs:
                    self.vg._removePV(pv)
            for pv in self.pvs:
                if pv not in self.vg.pvs:
                    self.vg._addPV(pv)

            self.vg.name = volname
            self.vg.peSize = pesize

            if self.isNew:
                actions = [ActionCreateDevice(self.vg)]

        # Schedule destruction of all non-existing lvs, their formats,
        # luks devices, &c. Also destroy devices that have been removed.
        for lv in origlvs:
            log.debug("old lv %s..." % lv.lvname)
            if not lv.exists or lv.lvname not in self.lvs or \
               (not self.lvs[lv.lvname]['exists'] and lv.exists):
                log.debug("removing lv %s" % lv.lvname)
                if lv.format.type == "luks":
                    try:
                        _luksdev = self.storage.devicetree.getChildren(lv)[0]
                    except IndexError:
                        pass
                    else:
                        if _luksdev.format.type:
                            actions.append(ActionDestroyFormat(_luksdev))

                        actions.append(ActionDestroyDevice(_luksdev))

                if lv.format.type:
                    actions.append(ActionDestroyFormat(lv))

                if lv in self.vg.lvs:
                    self.vg._removeLogVol(lv)

                actions.append(ActionDestroyDevice(lv))

        # schedule creation of all new lvs, their formats, luks devices, &c
        tempvg = self.getTempVG()
        for lv in tempvg.lvs:
            log.debug("new lv %s" % lv)
            if not lv.exists:
                log.debug("creating lv %s" % lv.lvname)
                # create the device
                newlv = LVMLogicalVolumeDevice(lv.lvname,
                                               self.vg,
                                               size=lv.size)
                actions.append(ActionCreateDevice(newlv))

                # create the format
                mountpoint = getattr(lv.format, "mountpoint", None)
                format = getFormat(lv.format.type,
                                   mountpoint=mountpoint,
                                   device=newlv.path)
                actions.append(ActionCreateFormat(newlv, format))

                if lv.format.type == "luks":
                    # create the luks device
                    newluks = LUKSDevice("luks-%s" % newlv.name,
                                         parents=[newlv])
                    actions.append(ActionCreateDevice(newluks))

                    # create the luks format
                    oldfmt = self.luks[lv.lvname]
                    mountpoint = getattr(oldfmt, "mountpoint", None)
                    format = getFormat(oldfmt.type,
                                       mountpoint=mountpoint,
                                       device=newluks.path)
                    actions.append(ActionCreateFormat(newluks, format))
            else:
                log.debug("lv %s already exists" % lv.lvname)
                # this lv is preexisting. check for resize and reformat.
                # first, get the real/original lv
                origlv = self.getLVByName(lv.lvname)
                if lv.resizable and lv.targetSize != origlv.size:
                    actions.append(ActionResizeDevice(origlv, lv.targetSize))

                if lv.format.exists:
                    log.debug("format already exists")
                    if lv.format.type == "luks":
                        # see if the luks device already exists
                        try:
                            usedev = self.storage.devicetree.getChildren(origlv)[0]
                        except IndexError:
                            # the luks device does not exist, meaning we
                            # do not have a key for it
                            continue

                        format = self.luks[lv.lvname]
                        if not format.exists:
                            actions.append(ActionCreateFormat(usedev, format))
                    else:
                        usedev = origlv
                        format = lv.format

                    # no formatting action requested, meaning we should
                    # cancel all format create/destroy actions
                    if format == usedev.originalFormat:
                        devicetree = self.storage.devicetree
                        cancel = []
                        if origlv.originalFormat.type == "luks":
                            path = "/dev/mapper/luks-%s" % origlv.originalFormat.uuid
                            cancel.extend(devicetree.findActions(path=path))

                        cancel.extend(devicetree.findActions(type="create",
                                                             object="format",
                                                             devid=origlv.id))
                        cancel.extend(devicetree.findActions(type="destroy",
                                                             object="format",
                                                             devid=origlv.id))
                        for action in cancel:
                            devicetree.cancelAction(action)

                        # even though we cancelled a bunch of actions, it's
                        # pretty much impossible to be sure we cancelled them
                        # in the correct order. make sure things are back to
                        # their original state.
                        if origlv.format.type == "luks":
                            try:
                                usedev = devicetree.getChildren(origlv)[0]
                            except IndexError:
                                usedev = origlv
                            else:
                                usedev.format = usedev.originalFormat
                        else:
                            usedev = origlv

                    if hasattr(format, "mountpoint"):
                        usedev.format.mountpoint = format.mountpoint

                    if format.migratable and format.migrate and \
                       not usedev.format.migrate:
                        usedev.format.migrate = format.migrate
                        actions.append(ActionMigrateFormat(usedev))

                    # check the lv's format also, explicitly, in case it is
                    # encrypted. in this case we must check them both.
                    if format.resizable and lv.format.resizable and \
                       lv.targetSize != format.currentSize and \
                       usedev.format.exists:
                        new_size = lv.targetSize
                        actions.append(ActionResizeFormat(usedev, new_size))
                elif lv.format.type:
                    log.debug("new format: %s" % lv.format.type)
                    # destroy old format and any associated luks devices
                    if origlv.format.type:
                        if origlv.format.type == "luks":
                            # destroy the luks device and its format
                            try:
                                _luksdev = self.storage.devicetree.getChildren(origlv)[0]
                            except IndexError:
                                pass
                            else:
                                if _luksdev.format.type:
                                    # this is probably unnecessary
                                    actions.append(ActionDestroyFormat(_luksdev))

                                actions.append(ActionDestroyDevice(_luksdev))

                        actions.append(ActionDestroyFormat(origlv))

                    # create the format
                    mountpoint = getattr(lv.format, "mountpoint", None)
                    format = getFormat(lv.format.type,
                                       mountpoint=mountpoint,
                                       device=origlv.path)
                    actions.append(ActionCreateFormat(origlv, format))

                    if lv.format.type == "luks":
                        # create the luks device
                        newluks = LUKSDevice("luks-%s" % origlv.name,
                                             parents=[origlv])
                        actions.append(ActionCreateDevice(newluks))

                        # create the luks format
                        tmpfmt = self.luks[lv.lvname]
                        mountpoint = getattr(tmpfmt, "mountpoint", None)
                        format = getFormat(tmpfmt.type,
                                           mountpoint=mountpoint,
                                           device=newluks.path)
                        actions.append(ActionCreateFormat(newluks, format))
                else:
                    log.debug("no format!?")

	return actions

    def destroy(self):
	if self.dialog:
	    self.dialog.destroy()
	self.dialog = None

    def getLVByName(self, name, vg=None):
        if vg is None:
            vg = self.vg

        for lv in vg.lvs:
            if lv.lvname == name or lv.name == name:
                return lv

    def __init__(self, anaconda, intf, parent, vg, isNew = 0):
        self.storage = anaconda.storage

        # the vg instance we were passed
        self.vg = vg
        self.peSize = vg.peSize
        self.pvs = self.vg.pvs[:]

        # a dict of dicts
        #  keys are lv names
        #  values are dicts representing the lvs
        #   name, size, format instance, exists
        self.lvs = {}

        # a dict of luks devices
        #  keys are lv names
        #  values are formats of the mapped devices
        self.luks = {}

        self.isNew = isNew
        self.intf = intf
        self.parent = parent
        self.actions = []

        for lv in self.vg.lvs:
            self.lvs[lv.lvname] = {"name": lv.lvname,
                                   "size": lv.size,
                                   "format": copy.copy(lv.format),
                                   "originalFormat": lv.originalFormat,
                                   "stripes": lv.stripes,
                                   "logSize": lv.logSize,
                                   "snapshotSpace": lv.snapshotSpace,
                                   "exists": lv.exists}

            if lv.format.type == "luks":
                try:
                    self.luks[lv.lvname] = self.storage.devicetree.getChildren(lv)[0].format
                except IndexError:
                    self.luks[lv.lvname] = lv.format

        self.availlvmparts = self.storage.unusedPVs(vg=vg)

        # if no PV exist, raise an error message and return
        if len(self.availlvmparts) < 1:
	    self.intf.messageWindow(_("Not enough physical volumes"),
			       _("At least one unused physical "
				 "volume partition is "
				 "needed to create an LVM Volume Group.\n\n"
				 "Create a partition or RAID array "
				 "of type \"physical volume (LVM)\" and then "
				 "select the \"LVM\" option again."),
				    custom_icon="error")
	    self.dialog = None
            return

	if isNew:
	    tstr = _("Make LVM Volume Group")
	else:
	    try:
		tstr = _("Edit LVM Volume Group: %s") % (vg.name,)
	    except AttributeError:
		tstr = _("Edit LVM Volume Group")
	    
        dialog = gtk.Dialog(tstr, self.parent)
        gui.addFrame(dialog)
        dialog.add_button('gtk-cancel', 2)
        dialog.add_button('gtk-ok', 1)

        dialog.set_position(gtk.WIN_POS_CENTER)

        maintable = gtk.Table()
        maintable.set_row_spacings(5)
        maintable.set_col_spacings(5)
        row = 0

        # volume group name
        if not vg.exists:
            lbl = createAlignedLabel(_("_Volume Group Name:"))
            self.volnameEntry = gtk.Entry(16)
            lbl.set_mnemonic_widget(self.volnameEntry)
            if not self.isNew:
                self.volnameEntry.set_text(self.vg.name)
            else:
                self.volnameEntry.set_text(self.storage.createSuggestedVGName(anaconda.network))
        else:
            lbl = createAlignedLabel(_("Volume Group Name:"))
            self.volnameEntry = gtk.Label(self.vg.name)
	    
	maintable.attach(lbl, 0, 1, row, row + 1,
                         gtk.EXPAND|gtk.FILL, gtk.SHRINK)
        maintable.attach(self.volnameEntry, 1, 2, row, row + 1, gtk.EXPAND|gtk.FILL, gtk.SHRINK)
	row = row + 1

        lbl = createAlignedLabel(_("_Physical Extent:"))
        self.peCombo = self.createPEOptionMenu(self.vg.peSize * 1024)
        lbl.set_mnemonic_widget(self.peCombo)
        if vg.exists:
            self.peCombo.set_sensitive(False)

        maintable.attach(lbl, 0, 1, row, row + 1,
                         gtk.EXPAND|gtk.FILL, gtk.SHRINK)
        maintable.attach(self.peCombo, 1, 2, row, row + 1, gtk.EXPAND|gtk.FILL, gtk.SHRINK)
        row = row + 1

        (self.lvmlist, sw) = self.createAllowedLvmPartitionsList()
        if vg.exists:
            self.lvmlist.set_sensitive(False)
        self.lvmlist.set_size_request(275, 80)
        lbl = createAlignedLabel(_("Physical Volumes to _Use:"))
        lbl.set_mnemonic_widget(self.lvmlist)
        maintable.attach(lbl, 0, 1, row, row + 1)
        maintable.attach(sw, 1, 2, row, row + 1)
        row = row + 1

        maintable.attach(createAlignedLabel(_("Used Space:")), 0, 1, row,
			 row + 1, gtk.EXPAND|gtk.FILL, gtk.SHRINK)
	lbox = gtk.HBox()
	self.usedSpaceLabel = gtk.Label("")
	labelalign = gtk.Alignment()
	labelalign.set(1.0, 0.5, 0.0, 0.0)
	labelalign.add(self.usedSpaceLabel)
	lbox.pack_start(labelalign, False, False)
	self.usedPercentLabel = gtk.Label("")
	labelalign = gtk.Alignment()
	labelalign.set(1.0, 0.5, 0.0, 0.0)
	labelalign.add(self.usedPercentLabel)
	lbox.pack_start(labelalign, False, False, padding=10)
        maintable.attach(lbox, 1, 2, row, row + 1, gtk.EXPAND|gtk.FILL, gtk.SHRINK)
	maintable.set_row_spacing(row, 0)
        row = row + 1

        maintable.attach(createAlignedLabel(_("Free Space:")), 0, 1, row,
			 row + 1, gtk.EXPAND|gtk.FILL, gtk.SHRINK)
	lbox = gtk.HBox()
	self.freeSpaceLabel = gtk.Label("")
	labelalign = gtk.Alignment()
	labelalign.set(1.0, 0.5, 0.0, 0.0)
	labelalign.add(self.freeSpaceLabel)
	lbox.pack_start(labelalign, False, False)
	self.freePercentLabel = gtk.Label("")
	labelalign = gtk.Alignment()
	labelalign.set(1.0, 0.5, 0.0, 0.0)
	labelalign.add(self.freePercentLabel)
	lbox.pack_start(labelalign, False, False, padding=10)

        maintable.attach(lbox, 1, 2, row, row + 1, gtk.EXPAND|gtk.FILL, gtk.SHRINK)
	maintable.set_row_spacing(row, 0)
        row = row + 1

        maintable.attach(createAlignedLabel(_("Total Space:")), 0, 1, row,
			 row + 1, gtk.EXPAND|gtk.FILL, gtk.SHRINK)
	self.totalSpaceLabel = gtk.Label("")
	labelalign = gtk.Alignment()
	labelalign.set(0.0, 0.5, 0.0, 0.0)
	labelalign.add(self.totalSpaceLabel)
        maintable.attach(labelalign, 1, 2, row, row + 1, gtk.EXPAND|gtk.FILL, gtk.SHRINK)
	maintable.set_row_spacing(row, 5)
        row = row + 1

	# populate list of logical volumes
        lvtable = gtk.Table()
        lvtable.set_row_spacings(5)
        lvtable.set_col_spacings(5)
	self.logvolstore = gtk.ListStore(gobject.TYPE_STRING,
				      gobject.TYPE_STRING,
				      gobject.TYPE_STRING)
	
	if self.vg.lvs:
	    for lv in self.vg.lvs:
		iter = self.logvolstore.append()
		self.logvolstore.set_value(iter, 0, lv.lvname)
                if lv.format.type == "luks":
                    try:
                        format = self.storage.devicetree.getChildren(lv)[0].format
                    except IndexError:
                        format = lv.format
                else:
                    format = lv.format

                if getattr(format, "mountpoint", None):
		    self.logvolstore.set_value(iter, 1,
                                               format.mountpoint)
		else:
		    self.logvolstore.set_value(iter, 1, "")
		self.logvolstore.set_value(iter, 2, "%Ld" % lv.size)

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
	lvtable.set_border_width(12)
        l = gtk.Label()
        l.set_markup_with_mnemonic("<b>%s</b>" %(_("_Logical Volumes"),))
        l.set_mnemonic_widget(self.logvollist)
	frame = gtk.Frame()
        frame.set_label_widget(l)
	frame.add(lvtable)
        frame.set_shadow_type(gtk.SHADOW_NONE)

#	dialog.vbox.pack_start(frame)
	maintable.attach(frame, 0, 2, row, row+1)
	row = row + 1
	
        dialog.vbox.pack_start(maintable)
	dialog.set_size_request(550, 450)
        dialog.show_all()

	# set space labels to correct values
	self.updateVGSpaceLabels()

	self.dialog = dialog
