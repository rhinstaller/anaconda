#
# partition_ui_helpers_gui.py: convenience functions for partition_gui.py
#                              and friends.
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

import gobject
import gtk
import checklist
import datacombo
import isys
import iutil

from constants import *
from fsset import *
from partitioning import *
from partIntfHelpers import *
from partRequests import *
from partedUtils import *

import rhpl
from rhpl.translate import _, N_

class WideCheckList(checklist.CheckList):
    def toggled_item(self, data, row):

	rc = True
	if self.clickCB:
	    rc = self.clickCB(data, row)

	if rc == True:
	    checklist.CheckList.toggled_item(self, data, row)

    
    def __init__(self, columns, store, clickCB=None):
	checklist.CheckList.__init__(self, columns=columns,
				     custom_store=store)

        # make checkbox column wider
        column = self.get_column(columns)
        self.set_expander_column(column)
        column = self.get_column(0)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_fixed_width(25)

	self.clickCB = clickCB

def createAlignedLabel(text):
    label = gtk.Label(text)
    label.set_alignment(0.0, 0.5)
    label.set_property("use-underline", True)

    return label

def createMountPointCombo(request, excludeMountPoints=[]):
    mountCombo = gtk.combo_box_entry_new_text()

    mntptlist = []

    if request.type != REQUEST_NEW and request.fslabel:
	mntptlist.append(request.fslabel)
        idx = 0
    
    for p in defaultMountPoints:
	if p in excludeMountPoints:
	    continue
	
	if not p in mntptlist and (p[0] == "/"):
	    mntptlist.append(p)

    map(mountCombo.append_text, mntptlist)

    mountpoint = request.mountpoint

    if request.fstype and request.fstype.isMountable():
        mountCombo.set_sensitive(1)
        if mountpoint:
            mountCombo.get_children()[0].set_text(mountpoint)
        else:
            mountCombo.get_children()[0].set_text("")
    else:
        mountCombo.get_children()[0].set_text(_("<Not Applicable>"))
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
            mountCombo.get_children()[0].set_text(mountpoint)
        else:
            mountCombo.get_children()[0].set_text("")
    else:
        if mountCombo.get_children()[0].get_text() != _("<Not Applicable>"):
            mountCombo.set_data("saved_mntpt", mountCombo.get_children()[0].get_text())
        mountCombo.get_children()[0].set_text(_("<Not Applicable>"))
        mountCombo.set_sensitive(0)

    mountCombo.set_data("prevmountable", fstype.isMountable())
    
def fstypechangeCB(widget, data):
    (mountCombo, lukscb) = data
    fstype = widget.get_active_value()
    setMntPtComboStateFromType(fstype, mountCombo)
    if lukscb:
        if fstype == fileSystemTypeGet("software RAID"):
            lukscb.set_active(0)
            lukscb.set_sensitive(0)
        else:
            lukscb.set_sensitive(1)

def createAllowedDrivesStore(disks, reqdrives, drivelist, updateSrc):
    drivelist.clear()
    drives = disks.keys()
    drives.sort()
    for drive in drives:
        size = getDeviceSizeMB(disks[drive].dev)
        selected = 0
        if reqdrives:
            if drive in reqdrives:
                selected = 1
        else:
            if drive != updateSrc:
                selected = 1

        sizestr = "%8.0f MB" % size

        if drive.find('mapper/mpath') != -1:
            model = isys.getMpathModel(drive)
        else:
            model = disks[drive].dev.model

        drivelist.append_row((drive, sizestr, model), selected)

    if len(disks.keys()) < 2:
        drivelist.set_sensitive(False)
    else:
        drivelist.set_sensitive(True)

def createAllowedDrivesList(disks, reqdrives, updateSrc):
    store = gtk.TreeStore(gobject.TYPE_BOOLEAN,
			  gobject.TYPE_STRING,
			  gobject.TYPE_STRING,
			  gobject.TYPE_STRING)
    drivelist = WideCheckList(3, store)
    createAllowedDrivesStore(disks, reqdrives, drivelist, updateSrc)

    return drivelist
    
    

# pass in callback for when fs changes because of python scope issues
def createFSTypeMenu(fstype, fstypechangeCB, mountCombo,
                     availablefstypes = None, ignorefs = None, lukscb = None):
    store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
    fstypecombo = datacombo.DataComboBox(store)
    
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
    defindex = 0
    i = 0
    for name in names:
        if not fileSystemTypeGet(name).isSupported():
            continue

        if ignorefs and name in ignorefs:
            continue
        
        if fileSystemTypeGet(name).isFormattable():
            fstypecombo.append(name, types[name])
            if default and default.getName() == name:
                defindex = i
                defismountable = types[name].isMountable()
            i = i + 1

    fstypecombo.set_active(defindex)

    if fstypechangeCB and mountCombo:
        fstypecombo.connect("changed", fstypechangeCB, (mountCombo, lukscb))

    if mountCombo:
        mountCombo.set_data("prevmountable",
                            fstypecombo.get_active_value().isMountable())
        mountCombo.connect("changed", mountptchangeCB, fstypecombo)

    return fstypecombo

def mountptchangeCB(widget, fstypecombo):
    if rhpl.getArch() == "ia64" and widget.get_children()[0].get_text() == "/boot/efi":
        fstypecombo.set_active_text("vfat")

def formatOptionCB(widget, data):
    (combowidget, mntptcombo, ofstype, lukscb) = data
    combowidget.set_sensitive(widget.get_active())
    if lukscb is not None:
        lukscb.set_data("formatstate", widget.get_active())
        if not widget.get_active():
            # set "Encrypt" checkbutton to match partition's initial state
            lukscb.set_active(lukscb.get_data("encrypted"))
            lukscb.set_sensitive(0)
        elif combowidget.get_active_value() == fileSystemTypeGet("software RAID"):
            lukscb.set_sensitive(0)
            lukscb.set_active(0)
        else:
            lukscb.set_sensitive(1)

    # inject event for fstype menu
    if widget.get_active():
	fstype = combowidget.get_active_value()
	setMntPtComboStateFromType(fstype, mntptcombo)
        combowidget.grab_focus()
    else:
	setMntPtComboStateFromType(ofstype, mntptcombo)

def noformatCB(widget, badblocks):
    badblocks.set_sensitive(widget.get_active())

def noformatCB2(widget, data):
    (combowidget, mntptcombo, ofstype) = data
    combowidget.set_sensitive(not widget.get_active())

    # inject event for fstype menu
    if widget.get_active():
	setMntPtComboStateFromType(ofstype, mntptcombo)


""" createPreExistFSOptionSection: given inputs for a preexisting partition,
    create a section that will provide format and migrate options

    Returns the value of row after packing into the maintable,
    and a dictionary consistenting of:
       noformatrb    - radiobutton for 'leave fs unchanged'
       formatrb      - radiobutton for 'format as new fs'
       fstype        - part of format fstype menu
       fstypeMenu    - part of format fstype menu
       migraterb     - radiobutton for migrate fs
       migfstype     - menu for migrate fs types
       migfstypeMenu - menu for migrate fs types
       badblocks     - toggle button for badblock check
"""
def createPreExistFSOptionSection(origrequest, maintable, row, mountCombo,
                                  showbadblocks=0, ignorefs=[]):
    ofstype = origrequest.fstype

    maintable.attach(gtk.HSeparator(), 0, 2, row, row + 1)
    row = row + 1

    label = gtk.Label(_("How would you like to prepare the file system "
		       "on this partition?"))
    label.set_line_wrap(1)
    label.set_alignment(0.0, 0.0)

    maintable.attach(label, 0, 2, row, row + 1)
    row = row + 1

    noformatrb = gtk.RadioButton(label=_("Leave _unchanged "
					 "(preserve data)"))
    noformatrb.set_active(1)
    maintable.attach(noformatrb, 0, 2, row, row + 1)
    row = row + 1

    formatrb = gtk.RadioButton(label=_("_Format partition as:"),
				    group=noformatrb)
    formatrb.set_active(0)
    if origrequest.format:
	formatrb.set_active(1)

    maintable.attach(formatrb, 0, 1, row, row + 1)
    lukscb = gtk.CheckButton(_("_Encrypt"))
    fstypeCombo = createFSTypeMenu(ofstype, fstypechangeCB,
                                   mountCombo, ignorefs=ignorefs,
                                   lukscb=lukscb)
    fstypeCombo.set_sensitive(formatrb.get_active())
    maintable.attach(fstypeCombo, 1, 2, row, row + 1)
    row = row + 1

    if not formatrb.get_active() and not origrequest.migrate:
	mountCombo.set_data("prevmountable", ofstype.isMountable())

    formatrb.connect("toggled", formatOptionCB,
		     (fstypeCombo, mountCombo, ofstype, lukscb))

    noformatrb.connect("toggled", noformatCB2,
		     (fstypeCombo, mountCombo, origrequest.origfstype))

    if origrequest.origfstype.isMigratable():
	migraterb = gtk.RadioButton(label=_("Mi_grate partition to:"),
				    group=noformatrb)
	migraterb.set_active(0)
	if origrequest.migrate:
	    migraterb.set_active(1)

	migtypes = origrequest.origfstype.getMigratableFSTargets()

	maintable.attach(migraterb, 0, 1, row, row + 1)
        lukscb = gtk.CheckButton(_("_Encrypt"))
	migfstypeCombo = createFSTypeMenu(ofstype, None, None,
                                          lukscb = lukscb,
                                          availablefstypes = migtypes)
	migfstypeCombo.set_sensitive(migraterb.get_active())
	maintable.attach(migfstypeCombo, 1, 2, row, row + 1)
	row = row + 1

	migraterb.connect("toggled", formatOptionCB,
                          (migfstypeCombo, mountCombo, ofstype, lukscb))
    else:
	migraterb = None
	migfstypeCombo = None

    if showbadblocks:
        badblocks = gtk.CheckButton(_("Check for _bad blocks?"))
        badblocks.set_active(0)
        maintable.attach(badblocks, 0, 1, row, row + 1)
        formatrb.connect("toggled", noformatCB, badblocks)
        if not origrequest.format:
            badblocks.set_sensitive(0)

        if origrequest.badblocks:
            badblocks.set_active(1)

    else:
        badblocks = None
        
    row = row + 1

    if origrequest.encryption:
        lukscb.set_active(1)
        lukscb.set_data("encrypted", 1)
    else:
        lukscb.set_data("encrypted", 0)

    lukscb.set_sensitive(formatrb.get_active())
    lukscb.set_data("formatstate", formatrb.get_active())
    maintable.attach(lukscb, 0, 2, row, row + 1)
    row = row + 1

    rc = {}
    for var in ['noformatrb', 'formatrb', 'fstypeCombo',
                'migraterb', 'migfstypeCombo', 'badblocks', 'lukscb' ]:
        if eval("%s" % (var,)) is not None:
            rc[var] = eval("%s" % (var,))

    return (row, rc)

# do tests we just want in UI for now, not kickstart
def doUIRAIDLVMChecks(request, diskset):
    fstype = request.fstype
    numdrives = len(diskset.disks.keys())
    
##     if fstype and fstype.getName() == "physical volume (LVM)":
## 	if request.grow:
## 	    return (_("Partitions of type '%s' must be of fixed size, and "
## 		     "cannot be marked to fill to use available space.")) % (fstype.getName(),)

    if fstype and fstype.getName() in ["physical volume (LVM)", "software RAID"]:
	if numdrives > 1 and (request.drive is None or len(request.drive) > 1):
	    return (_("Partitions of type '%s' must be constrained to "
		      "a single drive.  This is done by selecting the "
		      "drive in the 'Allowable Drives' checklist.")) % (fstype.getName(),)
    
    return None
