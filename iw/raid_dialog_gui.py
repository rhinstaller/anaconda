#
# raid_dialog_gui.py: dialog for editting a raid request
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
#            Jeremy Katz <katzj@redhat.com>
#

import copy

import gobject
import gtk
import datacombo

import gui
import storage.devicelibs.mdraid as mdraidlib
from storage.devices import *
from storage.deviceaction import *
from partition_ui_helpers_gui import *
from constants import *
from partIntfHelpers import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class RaidEditor:
    def _adjust_spares_button(self, raidlevel, selected_count):
        maxspares = 0
        if raidlevel is not None:
            maxspares = mdraidlib.get_raid_max_spares(raidlevel, selected_count)

        if maxspares > 0:
	    adj = self.sparesb.get_adjustment()
	    value = int(min(adj.value, maxspares))
	    self.sparesb.set_sensitive(1)
            adj.configure(value=value, lower=0, upper=maxspares, step_increment=1,
                          page_increment=0, page_size=0)
	else:
	    self.sparesb.set_value(0)
	    self.sparesb.set_sensitive(0)

    def createAllowedRaidPartitionsList(self, allraidparts, reqraidpart,
                                        preexist):

	store = gtk.TreeStore(gobject.TYPE_BOOLEAN,
			      gobject.TYPE_STRING,
			      gobject.TYPE_STRING)
	columns = ['Drive', 'Size']
	partlist = WideCheckList(columns, store, 
                                 clickCB=self.raidlist_toggle_callback)

	sw = gtk.ScrolledWindow()
	sw.add(partlist)
	sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
	sw.set_shadow_type(gtk.SHADOW_IN)

        tempDevList = []
        if not self.isNew:
            # We need this list if we are editing.
            for dev in reqraidpart:
                tempDevList.append(dev)

	partrow = 0
	for part in allraidparts:
	    partname = "%s" % part.name
	    partsize = "%8.0f MB" % part.size

            if part in tempDevList:
                #list the partition and put it as selected
                partlist.append_row((partname, partsize), True)
            else:
                if not self.origrequest.exists:
                    partlist.append_row((partname, partsize), False)


	return (partlist, sw)

    def createRaidLevelMenu(self, levels, reqlevel):
        levelcombo = gtk.combo_box_new_text()
	defindex = 0
        if mdraidlib.RAID1 in levels:
            defindex = levels.index(mdraidlib.RAID1)
	i = 0
	for lev in levels:
            levelcombo.append_text("RAID%d" % lev)

	    if reqlevel is not None and lev == reqlevel:
		defindex = i
	    i = i + 1

        levelcombo.set_active(defindex)
        levelcombo.connect("changed", self.raidlevelchangeCB)
	return levelcombo

    def createRaidMinorMenu(self, minors, reqminor):
        minorcombo = datacombo.DataComboBox()
        defindex = 0
        i = 0
        for minor in minors:
            name = "md%d" % minor
            if name in self.storage.devicetree._ignoredDisks:
                continue
            minorcombo.append(name, minor)
            if reqminor and minor == reqminor:
                defindex = i
            i = i + 1

        minorcombo.set_active(defindex)

        return minorcombo

    def raidlevelchangeCB(self, widget):
	raidlevel = widget.get_model()[widget.get_active()][0]
        selected_count = self._total_selected_members()
        self._adjust_spares_button(raidlevel, selected_count)

    def run(self):
	if self.dialog is None:
	    return []
	
	while 1:
	    self.allow_ok_button(self._total_selected_members())
	    rc = self.dialog.run()

	    # user hit cancel, do nothing
	    if rc in [2, gtk.RESPONSE_DELETE_EVENT]:
		self.destroy()
		return []

            actions = []
            luksdev = None
	    raidmembers = []
            migrate = None
	    model = self.raidlist.get_model()
	    iter = model.get_iter_first()
            format = None
	    while iter:
		val   = model.get_value(iter, 0)
		part = model.get_value(iter, 1)

		if val:
		    dev = self.storage.devicetree.getDeviceByName(part)
		    raidmembers.append(dev)

                iter = model.iter_next(iter)

            # The user has to select some devices to be part of the array.
            if not raidmembers:
                continue

            mountpoint = self.mountCombo.get_children()[0].get_text()
            (sensitive,) = self.mountCombo.get_properties('sensitive')
            if sensitive and mountpoint:
                msg = sanityCheckMountPoint(mountpoint)
                if msg:
                    self.intf.messageWindow(_("Mount Point Error"),
                                            msg,
                                            custom_icon="error")
                    self.dialog.present()
                    continue

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
                    self.dialog.present()
                    continue

            if not self.origrequest.exists:
                # new device
                fmt_class = self.fstypeCombo.get_active_value()
                raidminor = int(self.minorCombo.get_active_value())

                model = self.levelcombo.get_model()
                raidlevel = model[self.levelcombo.get_active()][0]

                if not mdraidlib.isRaid(mdraidlib.RAID0, raidlevel):
                    self.sparesb.update()
                    spares = self.sparesb.get_value_as_int()
                else:
                    spares = 0

                format = fmt_class(mountpoint=mountpoint)
                members = len(raidmembers) - spares

                try:
                    request = self.storage.newMDArray(minor=raidminor,
                                                  level=raidlevel,
                                                  format=format,
                                                  parents=raidmembers,
                                                  totalDevices=len(raidmembers),
                                                  memberDevices=members)
                except ValueError, e:
                    self.intf.messageWindow(_("Error"), str(e),
                                            custom_icon="error")
                    self.dialog.present()
                    continue

                # we must destroy luks leaf before original raid request
                if self.origrequest.format.type == "luks":
                    # => not self.isNew
                    # destroy luks format and mapped device
                    # XXX remove catching, it should always succeed
                    try:
                        luksdev = self.storage.devicetree.getChildren(self.origrequest)[0]
                    except IndexError:
                        pass
                    else:
                        actions.append(ActionDestroyFormat(luksdev))
                        actions.append(ActionDestroyDevice(luksdev))
                        luksdev = None

                if self.lukscb and self.lukscb.get_active():
                    luksdev = LUKSDevice("luks-%s" % request.name,
                                         format=format,
                                         parents=request)
                    format = getFormat("luks",
                                       passphrase=self.storage.encryptionPassphrase)
                    request.format = format
                elif self.lukscb and not self.lukscb.get_active() and \
                    self.origrequest.format.type == "luks":

                    # XXXRV not needed as we destroy origrequest ?
                    actions.append(ActionDestroyFormat(self.origrequest))

                if not self.isNew:
                    # This may be handled in devicetree.registerAction,
                    # but not in case when we change minor and thus
                    # device name/path (at least with current md)
                    actions.append(ActionDestroyDevice(self.origrequest))
                actions.append(ActionCreateDevice(request))
                actions.append(ActionCreateFormat(request))
            
	    else:
                # existing device
                fmt_class = self.fsoptionsDict["fstypeCombo"].get_active_value()
		if self.fsoptionsDict.has_key("formatcb") and \
                   self.fsoptionsDict["formatcb"].get_active():
                    format = fmt_class(mountpoint=mountpoint)
                    if self.fsoptionsDict.has_key("lukscb") and \
                       self.fsoptionsDict["lukscb"].get_active() and \
                       (self.origrequest.format.type != "luks" or
                        (self.origrequest.format.exists and
                         not self.origrequest.format.hasKey)):
                        luksdev = LUKSDevice("luks-%s" % self.origrequest.name,
                                             format=format,
                                             parents=self.origrequest)
                        format = getFormat("luks",
                                           device=self.origrequest.path,
                                           passphrase=self.storage.encryptionPassphrase)
                    elif self.fsoptionsDict.has_key("lukscb") and \
                         not self.fsoptionsDict["lukscb"].get_active() and \
                         self.origrequest.format.type == "luks":
                        # destroy luks format and mapped device
                        try:
                            luksdev = self.storage.devicetree.getChildren(self.origrequest)[0]
                        except IndexError:
                            pass
                        else:
                            actions.append(ActionDestroyFormat(luksdev))
                            actions.append(ActionDestroyDevice(luksdev))
                            luksdev = None

                        actions.append(ActionDestroyFormat(self.origrequest))
                elif self.fsoptionsDict.has_key("formatcb") and \
                     not self.fsoptionsDict["formatcb"].get_active():
                    # if the format checkbutton is inactive, cancel all
                    # actions on this device that create or destroy formats
                    devicetree = self.storage.devicetree
                    request = self.origrequest
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

                if self.origrequest.format.mountable:
                    self.origrequest.format.mountpoint = mountpoint

		if self.fsoptionsDict.has_key("migratecb") and \
		   self.fsoptionsDict["migratecb"].get_active():
                    if self.origrequest.format.type == "luks":
                        try:
                            usedev = self.storage.devicetree.getChildren(self.origrequest)[0]
                        except IndexError:
                            usedev = self.origrequest
                    else:
                        usedev = self.origrequest
                    migrate = True

                if self.origrequest.format.exists and not format and \
                   self.storage.formatByDefault(self.origrequest):
                    if not queryNoFormatPreExisting(self.intf):
		        continue

                if format:
                    actions.append(ActionCreateFormat(self.origrequest, format))

	    # everything ok, break out
	    break


        if luksdev:
            actions.append(ActionCreateDevice(luksdev))
            actions.append(ActionCreateFormat(luksdev))

        if migrate:
            actions.append(ActionMigrateFormat(usedev))

	return actions

    def destroy(self):
	if self.dialog:
	    self.dialog.destroy()

	self.dialog = None
	
    def __init__(self, storage, intf, parent, origrequest, isNew = 0):
	self.storage = storage
	self.origrequest = origrequest
	self.isNew = isNew
	self.intf = intf
	self.parent = parent

	self.dialog = None

	#
	# start of editRaidRequest
	#
        availraidparts = self.storage.unusedMDMembers(array=self.origrequest)

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
	    if origrequest.minor is not None:
		tstr = _("Edit RAID Device: %s") % (origrequest.path,)
	    else:
		tstr = _("Edit RAID Device")
		
	dialog = gtk.Dialog(tstr, self.parent)
	gui.addFrame(dialog)
	dialog.add_button('gtk-cancel', 2)
	self.ok_button = dialog.add_button('gtk-ok', 1)
	dialog.set_position(gtk.WIN_POS_CENTER)

	maintable = gtk.Table()
	maintable.set_row_spacings(5)
	maintable.set_col_spacings(5)
	row = 0

        # we'll maybe add this further down
        self.lukscb = gtk.CheckButton(_("_Encrypt"))
        self.lukscb.set_data("formatstate", 1)

        if origrequest.format.type == "luks":
            try:
                luksdev = self.storage.devicetree.getChildren(origrequest)[0]
            except IndexError:
                luksdev = None
                usedev = origrequest
                format = origrequest.format
            else:
                usedev = luksdev
                format = usedev.format
        else:
            luksdev = None
            usedev = origrequest
            format = origrequest.format

	# Mount Point entry
	lbl = createAlignedLabel(_("_Mount Point:"))
	maintable.attach(lbl, 0, 1, row, row + 1)
	self.mountCombo = createMountPointCombo(usedev)
	lbl.set_mnemonic_widget(self.mountCombo)
	maintable.attach(self.mountCombo, 1, 2, row, row + 1)
	row = row + 1

	# Filesystem Type
        if not origrequest.exists:
            lbl = createAlignedLabel(_("_File System Type:"))
            maintable.attach(lbl, 0, 1, row, row + 1)
            self.fstypeCombo = createFSTypeMenu(format,
                                                fstypechangeCB,
                                                self.mountCombo,
                                                ignorefs = ["mdmember", "efi", "prepboot", "appleboot"])
	    lbl.set_mnemonic_widget(self.fstypeCombo)
            maintable.attach(self.fstypeCombo, 1, 2, row, row + 1)
            row += 1
        else:
            maintable.attach(createAlignedLabel(_("Original File System Type:")),
                             0, 1, row, row + 1)
            self.fstypeCombo = gtk.Label(usedev.originalFormat.name)
            maintable.attach(self.fstypeCombo, 1, 2, row, row + 1)
            row += 1

            if getattr(usedev.originalFormat, "label", None):
                maintable.attach(createAlignedLabel(_("Original File System "
                                                      "Label:")),
                                 0, 1, row, row + 1)
                maintable.attach(gtk.Label(usedev.originalFormat.label),
                                 1, 2, row, row + 1)
                row += 1

	# raid minors
	lbl = createAlignedLabel(_("RAID _Device:"))	
	maintable.attach(lbl, 0, 1, row, row + 1)

        if not origrequest.exists:
            availminors = self.storage.unusedMDMinors[:16]
            reqminor = origrequest.minor
            if reqminor is not None and reqminor not in availminors:
                availminors.append(reqminor)

            availminors.sort()
            self.minorCombo = self.createRaidMinorMenu(availminors, reqminor)
	    lbl.set_mnemonic_widget(self.minorCombo)
        else:
            self.minorCombo = gtk.Label("%s" %(origrequest.name,))
	maintable.attach(self.minorCombo, 1, 2, row, row + 1)
	row = row + 1

	# raid level
	lbl = createAlignedLabel(_("RAID _Level:"))
	maintable.attach(lbl, 0, 1, row, row + 1)

        if not origrequest.exists:
            # Create here, pack below
            # create the raid level combobox:
            self.levelcombo = self.createRaidLevelMenu(mdraidlib.raid_levels,
                                                       origrequest.level)
            # now the number-of-spares spin button:
            spareAdj = gtk.Adjustment(value=0, upper=0, step_incr=1)
            self.sparesb = gtk.SpinButton(spareAdj)
            # adjust the max number of spares depending on the default raid level
            level_index = self.levelcombo.get_active()
            selected_level = self.levelcombo.get_model()[level_index][0]
            self._adjust_spares_button(selected_level, origrequest.totalDevices)
            # if there's a specific spares number request, set it
            self.sparesb.set_value(origrequest.spares)
	    lbl.set_mnemonic_widget(self.levelcombo)
        else:
            self.sparesb = gtk.Label(str(origrequest.spares))
            self.levelcombo = gtk.Label(origrequest.level)

	maintable.attach(self.levelcombo, 1, 2, row, row + 1)
	row = row + 1

	# raid members
	lbl=createAlignedLabel(_("_RAID Members:"))
	maintable.attach(lbl, 0, 1, row, row + 1)

	# XXX need to pass in currently used partitions for this device
	(self.raidlist, sw) = self.createAllowedRaidPartitionsList(availraidparts,
                                                                   origrequest.devices,
                                                                   origrequest.exists)

	lbl.set_mnemonic_widget(self.raidlist)
	self.raidlist.set_size_request(275, 80)
	maintable.attach(sw, 1, 2, row, row + 1)
	row = row + 1

        if origrequest.exists:
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
	if not format.exists and not origrequest.exists:
	    self.formatButton = gtk.CheckButton(_("_Format partition?"))
	    if not format.type:
		self.formatButton.set_active(1)
	    else:
		self.formatButton.set_active(0)
            # it only makes sense to show this for preexisting RAID
            if origrequest.exists:
                maintable.attach(self.formatButton, 0, 2, row, row + 1)
                row = row + 1

            # checkbutton for encryption using dm-crypt/LUKS
            if origrequest.format.type == "luks":
                self.lukscb.set_active(1)
            else:
                self.lukscb.set_active(0)
            maintable.attach(self.lukscb, 0, 2, row, row + 1)
            row = row + 1
	else:
	    (row, self.fsoptionsDict) = createPreExistFSOptionSection(origrequest, maintable, row, self.mountCombo, self.storage, luksdev=luksdev)

	# put main table into dialog
	dialog.vbox.pack_start(maintable)

	dialog.show_all()
	self.dialog = dialog
	return

    def allow_ok_button(self, selected_count):
        """
        Determine if the OK button should be enabled.

        The OK button is enabled whenever at least one row is selected.
        """
        self.ok_button.set_sensitive(selected_count > 0)

    def _total_selected_members(self, path=None):
        """
        Determine how many raid members are checked (selected) at the moment.

        If path is given it points to the row where the toggle state is about to
        change. Unfortunately its value is opposite of the value it is *going to
        have* after the callback thus the complication below.
        """
        ret = 0
        model = self.raidlist.get_model()
        iter = model.get_iter_first()
        toggled_iter = None
        if path:
            toggled_iter = model.get_iter(path)
        while iter:
            val = model.get_value(iter, 0)
            if toggled_iter and \
                    model.get_value(toggled_iter, 1) == \
                    model.get_value(iter, 1):
                # this is being toggled, negate the value:
                if not val:
                    ret += 1
            else:
                if val:
                    ret += 1
            iter = model.iter_next(iter)

        return ret

    def raidlist_toggle_callback(self, data, path):
        level_index = self.levelcombo.get_active()
        raidlevel = self.levelcombo.get_model()[level_index][0]
        selected_count = self._total_selected_members(path)

        self.allow_ok_button(selected_count)
        self._adjust_spares_button(raidlevel, selected_count)
        return 1
