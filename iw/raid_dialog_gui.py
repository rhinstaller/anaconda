#
# raid_dialog_gui.py: dialog for editting a raid request
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
	leveloption = gtk.OptionMenu()
	leveloptionmenu = gtk.Menu()
	defindex = None
	i = 0
	for lev in levels:
	    item = gtk.MenuItem(lev)
	    item.set_data("level", lev)
	    # XXX gtk bug, if you don't show then the menu will be larger
	    # than the largest menu item
	    item.show()        
	    leveloptionmenu.add(item)
	    if reqlevel and lev == reqlevel:
		defindex = i
	    if self.sparesb:
		item.connect("activate", self.raidlevelchangeCB, self.sparesb)
	    i = i + 1

	leveloption.set_menu(leveloptionmenu)

	if defindex:
	    leveloption.set_history(defindex)

	if reqlevel and reqlevel == "RAID0":
	    self.sparesb.set_sensitive(0)

	return (leveloption, leveloptionmenu)

    def createRaidMinorMenu(self, minors, reqminor):
	minoroption = gtk.OptionMenu()
	minoroptionmenu = gtk.Menu()
	defindex = None
	i = 0
	for minor in minors:
	    item = gtk.MenuItem("md%d" % (minor,))
	    item.set_data("minor", minor)
	    # XXX gtk bug, if you don't show then the menu will be larger
	    # than the largest menu item
	    item.show()
	    minoroptionmenu.add(item)
	    if reqminor and minor == reqminor:
		defindex = i
	    i = i + 1

	minoroption.set_menu(minoroptionmenu)

	if defindex:
	    minoroption.set_history(defindex)

	return (minoroption, minoroptionmenu)


    def raidlevelchangeCB(self, widget, sparesb):
	raidlevel = widget.get_data("level")
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

            if not self.origrequest.getPreExisting():
                filesystem = self.fstypeoptionMenu.get_active().get_data("type")
                request.fstype = filesystem

		if request.fstype.isMountable():
		    request.mountpoint = self.mountCombo.entry.get_text()
		else:
		    request.mountpoint = None

	    raidmembers = []
	    model = self.raidlist.get_model()
	    iter = model.get_iter_first()
	    next = 1
	    while next:
		val   = model.get_value(iter, 0)
		part = model.get_value(iter, 1)

		if val:
		    req = self.partitions.getRequestByDeviceName(part)
		    raidmembers.append(req.uniqueID)

		next = model.iter_next(iter)

            if not self.origrequest.getPreExisting():
                request.raidminor = self.minorOptionMenu.get_active().get_data("minor")

                request.raidmembers = raidmembers
                request.raidlevel = self.leveloptionmenu.get_active().get_data("level")
                if request.raidlevel != "RAID0":
                    request.raidspares = self.sparesb.get_value_as_int()
                else:
                    request.raidspares = 0

		if self.formatButton:
		    request.format = self.formatButton.get_active()
		else:
		    request.format = 0
	    else:
		if self.fsoptionsDict.has_key("formatrb"):
		    formatrb = self.fsoptionsDict["formatrb"]
		else:
		    formatrb = None

		if formatrb:
                    request.format = formatrb.get_active()
                    if request.format:
                        request.fstype = self.fsoptionsDict["fstypeMenu"].get_active().get_data("type")
                    if self.fsoptionsDict.has_key("badblocks") and self.fsoptionsDict["badblocks"].get_active():
                        request.badblocks = gtk.TRUE
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
                        request.fstype =self.fsoptionsDict["migfstypeMenu"].get_active().get_data("type")
                else:
                    request.migrate = 0

                # set back if we are not formatting or migrating
		origfstype = self.origrequest.origfstype
                if not request.format and not request.migrate:
                    request.fstype = origfstype

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

	dialog = gtk.Dialog(_("Make RAID Device"), self.parent)
	gui.addFrame(dialog)
	dialog.add_button('gtk-cancel', 2)
	dialog.add_button('gtk-ok', 1)
	dialog.set_position(gtk.WIN_POS_CENTER)

	maintable = gtk.Table()
	maintable.set_row_spacings(5)
	maintable.set_col_spacings(5)
	row = 0

	# Mount Point entry
	maintable.attach(createAlignedLabel(_("Mount Point:")),
					    0, 1, row, row + 1)
	self.mountCombo = createMountPointCombo(origrequest)
	maintable.attach(self.mountCombo, 1, 2, row, row + 1)
	row = row + 1

	# Filesystem Type
	maintable.attach(createAlignedLabel(_("Filesystem type:")),
					    0, 1, row, row + 1)

        if not origrequest.getPreExisting():
            (self.fstypeoption, self.fstypeoptionMenu) = createFSTypeMenu(origrequest.fstype,
                                                                          fstypechangeCB,
                                                                          self.mountCombo,
                                                                          ignorefs = ["software RAID"])
        else:
            if origrequest.fstype.getName():
                self.fstypeoption = gtk.Label(origrequest.fstype.getName())
            else:
                self.fstypeoption = gtk.Label(_("Unknown"))
            
	maintable.attach(self.fstypeoption, 1, 2, row, row + 1)
	row = row + 1

	# raid minors
	maintable.attach(createAlignedLabel(_("RAID Device:")),
                         0, 1, row, row + 1)

        if not origrequest.getPreExisting():
            availminors = self.partitions.getAvailableRaidMinors()[:16]
            reqminor = origrequest.raidminor
            if reqminor is not None:
                availminors.append(reqminor)

            availminors.sort()
            (self.minorOption, self.minorOptionMenu) = self.createRaidMinorMenu(availminors, reqminor)
        else:
            self.minorOption = gtk.Label("md%s" %(origrequest.raidminor,))
	maintable.attach(self.minorOption, 1, 2, row, row + 1)
	row = row + 1

	# raid level
	maintable.attach(createAlignedLabel(_("RAID Level:")),
					    0, 1, row, row + 1)

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
            (self.leveloption, self.leveloptionmenu) = \
                               self.createRaidLevelMenu(availRaidLevels,
                                                        origrequest.raidlevel)
        else:
            self.leveloption = gtk.Label(origrequest.raidlevel)

	maintable.attach(self.leveloption, 1, 2, row, row + 1)
	row = row + 1

	# raid members
	maintable.attach(createAlignedLabel(_("RAID Members:")),
			 0, 1, row, row + 1)

	# XXX need to pass in currently used partitions for this device
	(self.raidlist, sw) = self.createAllowedRaidPartitionsList(availraidparts,
                                                                   origrequest.raidmembers,
                                                                   origrequest.getPreExisting())

	self.raidlist.set_size_request(275, 80)
	maintable.attach(sw, 1, 2, row, row + 1)
	row = row + 1

        if origrequest.getPreExisting():
            self.raidlist.set_sensitive(gtk.FALSE)

	# number of spares - created widget above
	maintable.attach(createAlignedLabel(_("Number of spares:")),
			 0, 1, row, row + 1)
	maintable.attach(self.sparesb, 1, 2, row, row + 1)
	row = row + 1

	# format or not?
	self.formatButton = None
	self.fsoptionsDict = {}
	if (origrequest.fstype and origrequest.fstype.isFormattable()) and not origrequest.getPreExisting():
	    self.formatButton = gtk.CheckButton(_("Format partition?"))
	    if origrequest.format == None or origrequest.format != 0:
		self.formatButton.set_active(1)
	    else:
		self.formatButton.set_active(0)
            # it only makes sense to show this for preexisting RAID
            if origrequest.getPreExisting():
                maintable.attach(self.formatButton, 0, 2, row, row + 1)
                row = row + 1
	else:
	    (row, self.fsoptionsDict) = createPreExistFSOptionSection(self.origrequest, maintable, row, self.mountCombo, showbadblocks=0)

	# put main table into dialog
	dialog.vbox.pack_start(maintable)

	dialog.show_all()
	self.dialog = dialog
	return
