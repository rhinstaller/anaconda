#
# partition_ui_helpers_gui.py: convenience functions for partition_gui.py
#                              and friends.
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

import gobject
import gtk
import checklist
import datacombo
import iutil

from constants import *
from partIntfHelpers import *
from storage.formats import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

FLAG_FORMAT = 1
FLAG_MIGRATE = 2

class WideCheckList(checklist.CheckList):
    def toggled_item(self, data, row):

	rc = True
	if self.clickCB:
	    rc = self.clickCB(data, row)

	if rc:
	    checklist.CheckList.toggled_item(self, data, row)

    
    def __init__(self, columns, store, clickCB=None, sensitivity=False):
        checklist.CheckList.__init__(self, columns=columns,
                                     custom_store=store,
                                     sensitivity=sensitivity)

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

defaultMountPoints = ['/', '/boot', '/home', '/tmp', '/usr',
                      '/var', '/usr/local', '/opt']

if iutil.isS390():
    # Many s390 have 2G DASDs, we recomment putting /usr/share on its own DASD
    defaultMountPoints.insert(5, '/usr/share')

if iutil.isEfi():
    defaultMountPoints.insert(2, '/boot/efi')

def createMountPointCombo(request, excludeMountPoints=[]):
    mountCombo = gtk.combo_box_entry_new_text()

    mntptlist = []
    label = getattr(request.format, "label", None)
    if request.exists and label and label.startswith("/"):
        mntptlist.append(label)
        idx = 0

    for p in defaultMountPoints:
        if p in excludeMountPoints:
            continue

        if not p in mntptlist and (p[0] == "/"):
            mntptlist.append(p)

    map(mountCombo.append_text, mntptlist)

    if (request.format.type or request.format.migrate) and \
       request.format.mountable:
        mountpoint = request.format.mountpoint
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

def setMntPtComboStateFromType(fmt_class, mountCombo):
    prevmountable = mountCombo.get_data("prevmountable")
    mountpoint = mountCombo.get_data("saved_mntpt")

    format = fmt_class()
    if prevmountable and format.mountable:
        return

    if format.mountable:
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

    mountCombo.set_data("prevmountable", format.mountable)

def fstypechangeCB(widget, mountCombo):
    fstype = widget.get_active_value()
    setMntPtComboStateFromType(fstype, mountCombo)

def createAllowedDrivesStore(disks, reqdrives, drivelist, selectDrives=True,
                             disallowDrives=[]):
    drivelist.clear()
    for disk in disks:
        selected = 0

        if selectDrives:
            if reqdrives:
                if disk.name in reqdrives:
                    selected = 1
            else:
                if disk.name not in disallowDrives:
                    selected = 1

        sizestr = "%8.0f MB" % disk.size
        drivelist.append_row((disk.name,
                              sizestr,
                              disk.description),
                             selected)

    if len(disks) < 2:
        drivelist.set_sensitive(False)
    else:
        drivelist.set_sensitive(True)

def createAllowedDrivesList(disks, reqdrives, selectDrives=True, disallowDrives=[]):
    store = gtk.TreeStore(gobject.TYPE_BOOLEAN,
                          gobject.TYPE_STRING,
                          gobject.TYPE_STRING,
                          gobject.TYPE_STRING,
                          gobject.TYPE_BOOLEAN)
    drivelist = WideCheckList(3, store, sensitivity=True)
    createAllowedDrivesStore(disks, reqdrives, drivelist, selectDrives=selectDrives,
                             disallowDrives=disallowDrives)

    return drivelist
    
    

# pass in callback for when fs changes because of python scope issues
def createFSTypeMenu(format, fstypechangeCB, mountCombo,
                     availablefstypes = None, ignorefs = None):
    store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
    fstypecombo = datacombo.DataComboBox(store)
    
    if availablefstypes:
        names = availablefstypes
    else:
        names = device_formats.keys()
    if format and format.supported and format.formattable:
        default = format.type
    else:
        default = get_default_filesystem_type()
        
    names.sort()
    defindex = 0
    i = 0
    for name in names:
        # we could avoid instantiating them all if we made a static class
        # method that does what the supported property does
        format = device_formats[name]()
        if not format.supported:
            continue

        if ignorefs and name in ignorefs:
            continue
        
        if format.formattable:
            fstypecombo.append(format.name, device_formats[name])
            if default == name:
                defindex = i
                defismountable = format.mountable
            i = i + 1

    fstypecombo.set_active(defindex)

    if fstypechangeCB and mountCombo:
        fstypecombo.connect("changed", fstypechangeCB, mountCombo)

    if mountCombo:
        mountCombo.set_data("prevmountable",
                            fstypecombo.get_active_value()().mountable)
        mountCombo.connect("changed", mountptchangeCB, fstypecombo)

    return fstypecombo

def mountptchangeCB(widget, fstypecombo):
    if iutil.isEfi() and widget.get_children()[0].get_text() == "/boot/efi":
        fstypecombo.set_active_text(getFormat("efi").name)
    if widget.get_children()[0].get_text() == "/boot":
        fstypecombo.set_active_text(get_default_filesystem_type(boot=True))

def resizeOptionCB(widget, resizesb):
    resizesb.set_sensitive(widget.get_active())

def formatOptionResizeCB(widget, data):
    (resizesb, fmt) = data

    if widget.get_active():
        lower = 1
    else:
        lower = resizesb.get_data("reqlower")

    adj = resizesb.get_adjustment()
    adj.lower = lower
    resizesb.set_adjustment(adj)

    if resizesb.get_value_as_int() < lower:
        resizesb.set_value(adj.lower)

def formatMigrateOptionCB(widget, data):
    (sensitive,) = widget.get_properties('sensitive')
    if not sensitive:
        return

    (combowidget, mntptcombo, fs, lukscb, othercombo, othercb, flag) = data
    combowidget.set_sensitive(widget.get_active())

    if othercb is not None:
        othercb.set_sensitive(not widget.get_active())
        othercb.set_active(False)

        if othercombo is not None:
            othercombo.set_sensitive(othercb.get_active())

    if lukscb is not None:
        lukscb.set_data("formatstate", widget.get_active())
        if not widget.get_active():
            # set "Encrypt" checkbutton to match partition's initial state
            lukscb.set_active(lukscb.get_data("encrypted"))
            lukscb.set_sensitive(False)
        else:
            lukscb.set_sensitive(True)

    # inject event for fstype menu
    if widget.get_active():
        fstype = combowidget.get_active_value()
        setMntPtComboStateFromType(fstype, mntptcombo)
        combowidget.grab_focus()
    else:
        if isinstance(fs, type(fs)):
            fs = type(fs)

        setMntPtComboStateFromType(fs, mntptcombo)


def createPreExistFSOptionSection(origrequest, maintable, row, mountCombo,
                                  partitions, ignorefs=[], luksdev=None):
    """ createPreExistFSOptionSection: given inputs for a preexisting partition,
        create a section that will provide format and migrate options

        Returns the value of row after packing into the maintable,
        and a dictionary consistenting of:
           formatcb      - checkbutton for 'format as new fs'
           fstype        - part of format fstype menu
           fstypeMenu    - part of format fstype menu
           migratecb     - checkbutton for migrate fs
           migfstypeMenu - menu for migrate fs types
           lukscb        - checkbutton for 'encrypt using LUKS/dm-crypt'
           resizecb      - checkbutton for 'resize fs'
           resizesb      - spinbutton with resize target
    """
    rc = {}

    if luksdev:
        origfs = luksdev.format
    else:
        origfs = origrequest.format

    if origfs.formattable or not origfs.type:
        formatcb = gtk.CheckButton(label=_("_Format as:"))
        maintable.attach(formatcb, 0, 1, row, row + 1)
        formatcb.set_active(origfs.formattable and not origfs.exists)
        rc["formatcb"] = formatcb

        fstypeCombo = createFSTypeMenu(origfs, fstypechangeCB,
                                       mountCombo, ignorefs=ignorefs)
        fstypeCombo.set_sensitive(formatcb.get_active())
        maintable.attach(fstypeCombo, 1, 2, row, row + 1)
        row += 1
        rc["fstypeCombo"] = fstypeCombo
    else:
        formatcb = None
        fstypeCombo = None

    if formatcb and not formatcb.get_active() and not origfs.migrate:
        mountCombo.set_data("prevmountable", origfs.mountable)

    # this gets added to the table a bit later on
    lukscb = gtk.CheckButton(_("_Encrypt"))

    if origfs.migratable and origfs.exists:
        migratecb = gtk.CheckButton(label=_("Mi_grate filesystem to:"))
        if formatcb is not None:
            migratecb.set_active(origfs.migrate and (not formatcb.get_active()))
        else:
            migratecb.set_active(origfs.migrate)

        migtypes = [origfs.migrationTarget]

        maintable.attach(migratecb, 0, 1, row, row + 1)
        migfstypeCombo = createFSTypeMenu(origfs,
                                          None, None,
                                          availablefstypes = migtypes)
        migfstypeCombo.set_sensitive(migratecb.get_active())
        maintable.attach(migfstypeCombo, 1, 2, row, row + 1)
        row = row + 1
        rc["migratecb"] = migratecb
        rc["migfstypeCombo"] = migfstypeCombo
        migratecb.connect("toggled", formatMigrateOptionCB,
                          (migfstypeCombo, mountCombo, origfs, None,
                           fstypeCombo, formatcb, FLAG_MIGRATE))
    else:
        migratecb = None
        migfstypeCombo = None

    if formatcb:
        formatcb.connect("toggled", formatMigrateOptionCB,
                         (fstypeCombo, mountCombo, origfs, lukscb,
                          migfstypeCombo, migratecb, FLAG_FORMAT))

    if origrequest.resizable and origfs.exists:
        resizecb = gtk.CheckButton(label=_("_Resize"))
        resizecb.set_active(origfs.resizable and \
                            (origfs.currentSize != origfs.targetSize) and \
                            (origfs.currentSize != 0))
        rc["resizecb"] = resizecb
        maintable.attach(resizecb, 0, 1, row, row + 1)

        if origrequest.targetSize is not None:
            value = origrequest.targetSize
        else:
            value = origrequest.size

        reqlower = 1
        requpper = origrequest.maxSize

        if origfs.exists:
            reqlower = origrequest.minSize

            if origrequest.type == "partition":
                geomsize = origrequest.partedPartition.geometry.getSize(unit="MB")
                if (geomsize != 0) and (requpper > geomsize):
                    requpper = geomsize

        adj = gtk.Adjustment(value = value, lower = reqlower,
                             upper = requpper, step_incr = 1)
        resizesb = gtk.SpinButton(adj, digits = 0)
        resizesb.set_property('numeric', True)
        resizesb.set_data("requpper", requpper)
        resizesb.set_data("reqlower", reqlower)
        rc["resizesb"] = resizesb
        maintable.attach(resizesb, 1, 2, row, row + 1)
        resizecb.connect('toggled', resizeOptionCB, resizesb)
        resizeOptionCB(resizecb, resizesb)
        row = row + 1

        if formatcb:
            formatcb.connect("toggled", formatOptionResizeCB, (resizesb, origfs))

    if luksdev:
        lukscb.set_active(1)

    if origrequest.originalFormat.type == "luks":
        lukscb.set_data("encrypted", 1)
    else:
        lukscb.set_data("encrypted", 0)

    if formatcb:
        lukscb.set_sensitive(formatcb.get_active())
        lukscb.set_data("formatstate", formatcb.get_active())
    else:
        lukscb.set_sensitive(0)
        lukscb.set_data("formatstate", 0)

    rc["lukscb"] = lukscb
    maintable.attach(lukscb, 0, 2, row, row + 1)
    row = row + 1

    return (row, rc)

# do tests we just want in UI for now, not kickstart
def doUIRAIDLVMChecks(request, storage):
    fstype = request.format.name
    numdrives = len(storage.partitioned)
    
##     if fstype and fstype.getName() == "physical volume (LVM)":
## 	if request.grow:
## 	    return (_("Partitions of type '%s' must be of fixed size, and "
## 		     "cannot be marked to fill to use available space.")) % (fstype.getName(),)

    if fstype in ["physical volume (LVM)", "software RAID"]:
	if numdrives > 1 and (not request.req_disks or len(request.req_disks) > 1):
	    return (_("Partitions of type '%s' must be constrained to "
		      "a single drive.  To do this, select the "
		      "drive in the 'Allowable Drives' checklist.")) % (fstype.getName(),)
    
    return None
