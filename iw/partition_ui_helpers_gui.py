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

from constants import *
from fsset import *
from partitioning import *
from partIntfHelpers import *
from partRequests import *
from partedUtils import *

from rhpl.translate import _, N_

class WideCheckList(checklist.CheckList):
    def toggled_item(self, data, row):

	rc = gtk.TRUE
	if self.clickCB:
	    rc = self.clickCB(data, row)

	if rc == gtk.TRUE:
	    checklist.CheckList.toggled_item(self, data, row)

    
    def __init__(self, columns, store, clickCB=None):
	checklist.CheckList.__init__(self, columns=columns,
				     custom_store = store)

	selection = self.get_selection()
	selection.set_mode(gtk.SELECTION_NONE)

	# make checkbox column wider
	column = self.get_column(0)
	column.set_fixed_width(75)
	column.set_alignment(0.0)

	self.clickCB = clickCB

def createAlignedLabel(text):
    label = gtk.Label(text)
    label.set_alignment(0.0, 0.0)

    return label

def createMountPointCombo(request, excludeMountPoints=[]):
    mountCombo = gtk.Combo()

    mntptlist = []
    if request.type != REQUEST_NEW and request.fslabel:
	mntptlist.append(request.fslabel)
    
    for p in defaultMountPoints:
	if p in excludeMountPoints:
	    continue
	
	if not p in mntptlist and (p[0] == "/"):
	    mntptlist.append(p)
	
    mountCombo.set_popdown_strings (mntptlist)

    mountpoint = request.mountpoint

    if request.fstype and request.fstype.isMountable():
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

def setMntPtComboStateFromType(fstype, mountCombo):
    prevmountable = mountCombo.get_data("prevmountable")
    mountpoint = mountCombo.get_data("saved_mntpt")

    if prevmountable and fstype.isMountable():
        return

    if fstype.isMountable():
        mountCombo.set_sensitive(1)
        if mountpoint != None:
            mountCombo.entry.set_text(mountpoint)
        else:
            mountCombo.entry.set_text("")
    else:
        if mountCombo.entry.get_text() != _("<Not Applicable>"):
            mountCombo.set_data("saved_mntpt", mountCombo.entry.get_text())
        mountCombo.entry.set_text(_("<Not Applicable>"))
        mountCombo.set_sensitive(0)

    mountCombo.set_data("prevmountable", fstype.isMountable())
    
def fstypechangeCB(widget, mountCombo):
    fstype = widget.get_data("type")
    setMntPtComboStateFromType(fstype, mountCombo)

def createAllowedDrivesList(disks, reqdrives):
    store = gtk.TreeStore(gobject.TYPE_BOOLEAN,
			  gobject.TYPE_STRING,
			  gobject.TYPE_STRING,
			  gobject.TYPE_STRING)
    drivelist = WideCheckList(3, store)

    driverow = 0
    drives = disks.keys()
    drives.sort()
    for drive in drives:
        size = getDeviceSizeMB(disks[drive].dev)
	selected = 0
        if reqdrives:
            if drive in reqdrives:
		selected = 1
        else:
	    selected = 1

	sizestr = "%8.0f MB" % size
	drivelist.append_row((drive, sizestr, disks[drive].dev.model),selected)

    return drivelist

# pass in callback for when fs changes because of python scope issues
def createFSTypeMenu(fstype, fstypechangeCB, mountCombo,
                     availablefstypes = None, ignorefs = None):
    fstypeoption = gtk.OptionMenu()
    fstypeoptionMenu = gtk.Menu()
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
    defindex = None
    i = 0
    for name in names:
        if not fileSystemTypeGet(name).isSupported():
            continue

        if ignorefs and name in ignorefs:
            continue
        
        if fileSystemTypeGet(name).isFormattable():
            item = gtk.MenuItem(name)
            item.set_data("type", types[name])
            # XXX gtk bug, if you don't show then the menu will be larger
            # than the largest menu item
            item.show()
            fstypeoptionMenu.add(item)
            if default and default.getName() == name:
                defindex = i
                defismountable = types[name].isMountable()
            if fstypechangeCB and mountCombo:
                item.connect("activate", fstypechangeCB, mountCombo)
            i = i + 1

    fstypeoption.set_menu(fstypeoptionMenu)

    if defindex:
        fstypeoption.set_history(defindex)

    if mountCombo:
        mountCombo.set_data("prevmountable",
                            fstypeoptionMenu.get_active().get_data("type").isMountable())

    return (fstypeoption, fstypeoptionMenu)
