#
# Storage filtering UI
#
# Copyright (C) 2009  Red Hat, Inc.
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

import block
import collections
import gtk, gobject
import gtk.glade
import gui
import parted
import _ped
from DeviceSelector import *
from baseudev import *
from constants import *
from iw_gui import *
from storage.devices import devicePathToName
from storage.udev import *
from storage.devicelibs.mpath import *
from flags import flags
import storage.iscsi
import storage.fcoe
import storage.zfcp

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

DEVICE_COL = 4
MODEL_COL = 5
CAPACITY_COL = 6
VENDOR_COL = 7
INTERCONNECT_COL = 8
SERIAL_COL = 9
ID_COL = 10
PATHS_COL = 11
PORT_COL = 12
TARGET_COL = 13
LUN_COL = 14

# This is kind of a magic class that is used for populating the device store.
# It mostly acts like a list except for some funny behavior on adding/getting.
# You must add udev dicts to this list, but when you go to examine the list
# (by pulling items out, checking membership, etc.) you are comparing based
# on names.
#
# The only reason to have this is to prevent needing two lists in a variety
# of places throughout FilterWindow.
class NameCache(collections.MutableSequence):
    def __init__(self, iterable):
        self._lst = list(iterable)

    def __contains__(self, item):
        return item["name"] in iter(self)

    def __delitem__(self, index):
        return self._lst.__delitem__(index)

    def __getitem__(self, index):
        return self._lst.__getitem__(index)["name"]

    def __iter__(self):
        for d in self._lst:
            yield d["name"]

    def __len__(self):
        return len(self._lst)

    def __setitem__(self, index, value):
        return self._lst.__setitem__(index, value)

    def insert(self, index, value):
        return self._lst.insert(index, value)

# These are global because they need to be accessible across all Callback
# objects as the same values, and from the AdvancedFilterWindow object to add
# and remove devices when populating scrolled windows.
totalDevices = 0
selectedDevices = 0
totalSize = 0
selectedSize = 0

# These are global so they can be accessed from all Callback objects.  The
# basic callback defines its membership as anything that doesn't pass the
# is* methods.
def isCCISS(info):
    return udev_device_is_cciss(info)

def isRAID(info):
    if flags.dmraid:
        return udev_device_is_biosraid(info)

    return False

def isMultipath(info):
    return udev_device_is_multipath_member(info)

def isOther(info):
    return udev_device_is_iscsi(info) or udev_device_is_fcoe(info)

class Callbacks(object):
    def __init__(self, xml):
        self.model = None
        self.xml = xml

        self.sizeLabel = self.xml.get_widget("sizeLabel")
        self.sizeLabel.connect("realize", self.update)

    def addToUI(self, tuple):
        pass

    def deviceToggled(self, set, device):
        global selectedDevices, totalDevices
        global selectedSize, totalSize

        if set:
            selectedDevices += 1
            selectedSize += device["XXX_SIZE"]
        else:
            selectedDevices -= 1
            selectedSize -= device["XXX_SIZE"]

        self.update()

    def isMember(self, info):
        return info and not isRAID(info) and not isCCISS(info) and \
               not isMultipath(info) and not isOther(info)

    def update(self, *args, **kwargs):
        global selectedDevices, totalDevices
        global selectedSize, totalSize

        self.sizeLabel.set_markup(_("<b>%s device(s) (%s MB) selected</b> out of %s device(s) (%s MB) total.") % (selectedDevices, selectedSize, totalDevices, totalSize))

    def visible(self, model, iter, view):
        # Most basic visibility function - does the model say this row
        # should be visible?  Subclasses can define their own more specific
        # visibility function, though they should also take a look at this
        # one to see what the model says.
        return self.isMember(model.get_value(iter, OBJECT_COL)) and \
               model.get_value(iter, VISIBLE_COL)

class RAIDCallbacks(Callbacks):
    def isMember(self, info):
        return info and (isRAID(info) or isCCISS(info))

class FilteredCallbacks(Callbacks):
    def __init__(self, *args, **kwargs):
        Callbacks.__init__(self, *args, **kwargs)

        # Are we even applying the filtering UI?  This is False when
        # whateverFilterBy is empty, True the rest of the time.
        self.filtering = False

    def reset(self):
        self.notebook.set_current_page(0)
        self.filtering = False

    def set(self, num):
        self.notebook.set_current_page(num)
        self.filtering = True

class MPathCallbacks(FilteredCallbacks):
    def __init__(self, *args, **kwargs):
        FilteredCallbacks.__init__(self, *args, **kwargs)

        self._vendors = []
        self._interconnects = []

        self.filterBy = self.xml.get_widget("mpathFilterBy")
        self.notebook = self.xml.get_widget("mpathNotebook")

        self.vendorEntry = self.xml.get_widget("mpathVendorEntry")
        self.interconnectEntry = self.xml.get_widget("mpathInterconnectEntry")
        self.IDEntry = self.xml.get_widget("mpathIDEntry")

        self.mpathFilterHBox = self.xml.get_widget("mpathFilterHBox")
        self.mpathFilterHBox.connect("realize", self._populateUI)

        self.vendorEntry.connect("changed", lambda entry: self.model.get_model().refilter())
        self.interconnectEntry.connect("changed", lambda entry: self.model.get_model().refilter())
        self.IDEntry.connect("changed", lambda entry: self.model.get_model().refilter())

    def addToUI(self, tuple):
        if not tuple[VENDOR_COL] in self._vendors:
            self._vendors.append(tuple[VENDOR_COL])

        if not tuple[INTERCONNECT_COL] in self._interconnects:
            self._interconnects.append(tuple[INTERCONNECT_COL])

    def isMember(self, info):
        return info and isMultipath(info)

    def visible(self, model, iter, view):
        if not FilteredCallbacks.visible(self, model, iter, view):
            return False

        if self.filtering:
            if self.notebook.get_current_page() == 0:
                return self._visible_by_interconnect(model, iter, view)
            elif self.notebook.get_current_page() == 1:
                return self._visible_by_vendor(model, iter, view)
            elif self.notebook.get_current_page() == 2:
                return self._visible_by_wwid(model, iter, view)

        return True

    def _populateUI(self, widget):
        cell = gtk.CellRendererText()

        self._vendors.sort()
        self.vendorEntry.set_model(gtk.ListStore(gobject.TYPE_STRING))
        self.vendorEntry.pack_start(cell)
        self.vendorEntry.add_attribute(cell, 'text', 0)

        for v in self._vendors:
            self.vendorEntry.append_text(v)

        self.vendorEntry.show_all()

        self._interconnects.sort()
        self.interconnectEntry.set_model(gtk.ListStore(gobject.TYPE_STRING))
        self.interconnectEntry.pack_start(cell)
        self.interconnectEntry.add_attribute(cell, 'text', 0)

        for i in self._interconnects:
            self.interconnectEntry.append_text(i)

        self.interconnectEntry.show_all()

    def _visible_by_vendor(self, model, iter, view):
        entered = self.vendorEntry.get_child().get_text()
        return model.get_value(iter, VENDOR_COL).find(entered) != -1

    def _visible_by_interconnect(self, model, iter, view):
        entered = self.interconnectEntry.get_child().get_text()
        return model.get_value(iter, INTERCONNECT_COL).find(entered) != -1

    def _visible_by_wwid(self, model, iter, view):
        # FIXME:  make this support globs, etc.
        entered = self.IDEntry.get_text()

        return entered != "" and model.get_value(iter, ID_COL).find(entered) != -1

class OtherCallbacks(MPathCallbacks):
    def __init__(self, *args, **kwargs):
        FilteredCallbacks.__init__(self, *args, **kwargs)

        self._vendors = []
        self._interconnects = []

        self.filterBy = self.xml.get_widget("otherFilterBy")
        self.notebook = self.xml.get_widget("otherNotebook")

        self.vendorEntry = self.xml.get_widget("otherVendorEntry")
        self.interconnectEntry = self.xml.get_widget("otherInterconnectEntry")
        self.IDEntry = self.xml.get_widget("otherIDEntry")

        self.otherFilterHBox = self.xml.get_widget("otherFilterHBox")
        self.otherFilterHBox.connect("realize", self._populateUI)

        self.vendorEntry.connect("changed", lambda entry: self.model.get_model().refilter())
        self.interconnectEntry.connect("changed", lambda entry: self.model.get_model().refilter())
        self.IDEntry.connect("changed", lambda entry: self.model.get_model().refilter())

    def isMember(self, info):
        return info and isOther(info)

class SearchCallbacks(FilteredCallbacks):
    def __init__(self, *args, **kwargs):
        FilteredCallbacks.__init__(self, *args, **kwargs)

        self._ports = []
        self._targets = []
        self._luns = []

        self.filterBy = self.xml.get_widget("searchFilterBy")
        self.notebook = self.xml.get_widget("searchNotebook")

        self.portEntry = self.xml.get_widget("searchPortEntry")
        self.targetEntry = self.xml.get_widget("searchTargetEntry")
        self.LUNEntry = self.xml.get_widget("searchLUNEntry")
        self.IDEntry = self.xml.get_widget("searchIDEntry")

        # When these entries are changed, we need to redo the filtering.
        # If we don't do filter-as-you-type, we'd need a Search/Clear button.
        self.portEntry.connect("changed", lambda entry: self.model.get_model().refilter())
        self.targetEntry.connect("changed", lambda entry: self.model.get_model().refilter())
        self.LUNEntry.connect("changed", lambda entry: self.model.get_model().refilter())
        self.IDEntry.connect("changed", lambda entry: self.model.get_model().refilter())

    def isMember(self, info):
        return True

    def visible(self, model, iter, view):
        if not model.get_value(iter, VISIBLE_COL):
            return False

        if self.filtering:
            if self.notebook.get_current_page() == 0:
                return self._visible_by_ptl(model, iter, view)
            else:
                return self._visible_by_wwid(model, iter, view)

        return True

    def _visible_by_ptl(self, model, iter, view):
        rowPort = model.get_value(iter, PORT_COL)
        rowTarget = model.get_value(iter, TARGET_COL)
        rowLUN = model.get_value(iter, LUN_COL)

        enteredPort = self.portEntry.get_text()
        enteredTarget = self.targetEntry.get_text()
        enteredLUN = self.LUNEntry.get_text()

        return (not enteredPort or enteredPort and enteredPort == rowPort) and \
               (not enteredTarget or enteredTarget and enteredTarget == rowTarget) and \
               (not enteredLUN or enteredLUN and enteredLUN == rowLUN)

    def _visible_by_wwid(self, model, iter, view):
        # FIXME:  make this support globs, etc.
        entered = self.IDEntry.get_text()

        return entered != "" and model.get_value(iter, ID_COL).find(entered) != -1

class NotebookPage(object):
    def __init__(self, store, name, xml, cb):
        # Every page needs a ScrolledWindow to display the results in.
        self.scroll = xml.get_widget("%sScroll" % name)

        self.filteredModel = store.filter_new()
        self.sortedModel = gtk.TreeModelSort(self.filteredModel)
        self.treeView = gtk.TreeView(self.sortedModel)

        self.scroll.add(self.treeView)

        self.cb = cb
        self.cb.model = self.sortedModel

        self.ds = DeviceSelector(store, self.sortedModel, self.treeView,
                                 visible=VISIBLE_COL, active=ACTIVE_COL)
        self.ds.createMenu()
        self.ds.createSelectionCol(toggledCB=self.cb.deviceToggled,
                                   membershipCB=self.cb.isMember)

        self.filteredModel.set_visible_func(self.cb.visible, self.treeView)

        # Not every NotebookPage will have a filter box - just those that do
        # some sort of filtering (obviously).
        self.filterBox = xml.get_widget("%sFilterHBox" % name)

        if self.filterBox:
            self.filterBy = xml.get_widget("%sFilterBy" % name)
            self.filterBy.connect("changed", self._filter_by_changed)

            # However if the page has a filter box, then it must also have a
            # notebook with an easily discoverable name.
            self.notebook = xml.get_widget("%sNotebook" % name)

    def _filter_by_changed(self, combo):
        active = combo.get_active()

        if active == -1:
            self.cb.reset()
        else:
            self.cb.set(active)

        self.filteredModel.refilter()

    def getNVisible(self):
        retval = 0
        iter = self.filteredModel.get_iter_first()

        while iter:
            if self.cb.visible(self.filteredModel, iter, self.treeView):
                retval += 1

            iter = self.filteredModel.iter_next(iter)

        return retval

class FilterWindow(InstallWindow):
    windowTitle = N_("Device Filter")

    def getNext(self):
        # All pages use the same store, so we only need to use the first one.
        # However, we do need to make sure all paths from multipath devices
        # are in the list.
        selected = set()
        for dev in self.pages[0].ds.getSelected():
            selected.add(udev_device_get_name(dev[OBJECT_COL]))

        if len(selected) == 0:
            self.anaconda.intf.messageWindow(_("Error"),
                                             _("You must select at least one "
                                               "drive to be used for installation."),
                                             custom_icon="error")
            raise gui.StayOnScreen

        self.anaconda.storage.exclusiveDisks = list(selected)

    def _add_advanced_clicked(self, button):
        from advanced_storage import addDrive

        if not addDrive(self.anaconda):
            return

        udev_trigger(subsystem="block", action="change")
        new_disks = filter(udev_device_is_disk, udev_get_block_devices())
        (new_singlepaths, new_mpaths, new_partitions) = identifyMultipaths(new_disks)
        (new_raids, new_nonraids) = self.split_list(lambda d: isRAID(d) and not isCCISS(d),
                                                    new_singlepaths)

        nonraids = filter(lambda d: d not in self._cachedDevices, new_nonraids)
        mpaths = filter(lambda d: d not in self._cachedMPaths, new_mpaths)
        raids = filter(lambda d: d not in self._cachedRaidDevices, new_raids)

        self.populate(nonraids, mpaths, raids)

        # Make sure to update the size label at the bottom.
        self.pages[0].cb.update()

        self._cachedDevices.extend(nonraids)
        self._cachedMPaths.extend(mpaths)
        self._cachedRaidDevices.extend(raids)

    def _makeBasic(self):
        np = NotebookPage(self.store, "basic", self.xml, Callbacks(self.xml))

        np.ds.addColumn(_("Model"), MODEL_COL)
        np.ds.addColumn(_("Capacity"), CAPACITY_COL)
        np.ds.addColumn(_("Vendor"), VENDOR_COL)
        np.ds.addColumn(_("Interconnect"), INTERCONNECT_COL)
        np.ds.addColumn(_("Serial Number"), SERIAL_COL)
        np.ds.addColumn(_("Device"), DEVICE_COL, displayed=False)
        return np

    def _makeRAID(self):
        np = NotebookPage(self.store, "raid", self.xml, RAIDCallbacks(self.xml))

        np.ds.addColumn(_("Model"), MODEL_COL)
        np.ds.addColumn(_("Capacity"), CAPACITY_COL)
        np.ds.addColumn(_("Device"), DEVICE_COL, displayed=False)
        return np

    def _makeMPath(self):
        np = NotebookPage(self.store, "mpath", self.xml, MPathCallbacks(self.xml))

        np.ds.addColumn(_("Identifier"), ID_COL)
        np.ds.addColumn(_("Capacity"), CAPACITY_COL)
        np.ds.addColumn(_("Vendor"), VENDOR_COL)
        np.ds.addColumn(_("Interconnect"), INTERCONNECT_COL)
        np.ds.addColumn(_("Paths"), PATHS_COL)
        np.ds.addColumn(_("Device"), DEVICE_COL, displayed=False)
        return np

    def _makeOther(self):
        np = NotebookPage(self.store, "other", self.xml, OtherCallbacks(self.xml))

        np.ds.addColumn(_("Identifier"), ID_COL)
        np.ds.addColumn(_("Capacity"), CAPACITY_COL)
        np.ds.addColumn(_("Vendor"), VENDOR_COL)
        np.ds.addColumn(_("Interconnect"), INTERCONNECT_COL)
        np.ds.addColumn(_("Serial Number"), SERIAL_COL, displayed=False)
        np.ds.addColumn(_("Device"), DEVICE_COL, displayed=False)
        return np

    def _makeSearch(self):
        np = NotebookPage(self.store, "search", self.xml, SearchCallbacks(self.xml))

        np.ds.addColumn(_("Model"), MODEL_COL)
        np.ds.addColumn(_("Capacity"), CAPACITY_COL, displayed=False)
        np.ds.addColumn(_("Vendor"), VENDOR_COL)
        np.ds.addColumn(_("Interconnect"), INTERCONNECT_COL, displayed=False)
        np.ds.addColumn(_("Serial Number"), SERIAL_COL, displayed=False)
        np.ds.addColumn(_("Identifier"), ID_COL)
        np.ds.addColumn(_("Port"), PORT_COL)
        np.ds.addColumn(_("Target"), TARGET_COL)
        np.ds.addColumn(_("LUN"), LUN_COL)
        np.ds.addColumn(_("Device"), DEVICE_COL, displayed=False)
        return np

    def _page_switched(self, notebook, useless, page_num):
        # When the page is switched, we need to change what is visible so the
        # Select All button only selects/deselected things on the current page.
        # Unfortunately, the only way to do this is iterate over all rows and
        # check for membership.
        for line in self.store:
            line[VISIBLE_COL] = self.pages[page_num].cb.isMember(line[OBJECT_COL])

    def _show_buttons(self, *args, **kwargs):
        if self.anaconda.simpleFilter:
            self.buttonBox.hide()
            self.buttonBox.set_no_show_all(True)
        else:
            self.buttonBox.show_all()

    def getScreen(self, anaconda):
        (self.xml, self.vbox) = gui.getGladeWidget("filter.glade", "vbox")
        self.buttonBox = self.xml.get_widget("buttonBox")
        self.notebook = self.xml.get_widget("notebook")
        self.addAdvanced = self.xml.get_widget("addAdvancedButton")

        self.buttonBox.connect("realize", self._show_buttons)
        self.notebook.connect("switch-page", self._page_switched)
        self.addAdvanced.connect("clicked", self._add_advanced_clicked)

        self.pages = []

        self.anaconda = anaconda

        # One common store that all the views on all the notebook tabs share.
        # Yes, this means a whole lot of columns that are going to be empty or
        # unused much of the time.  Oh well.

        # Object,
        # visible, active (checked), immutable,
        # device, model, capacity, vendor, interconnect, serial number, wwid
        # paths, port, target, lun
        self.store = gtk.TreeStore(gobject.TYPE_PYOBJECT,
                                   gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN,
                                   gobject.TYPE_BOOLEAN,
                                   gobject.TYPE_STRING, gobject.TYPE_STRING,
                                   gobject.TYPE_STRING, gobject.TYPE_STRING,
                                   gobject.TYPE_STRING, gobject.TYPE_STRING,
                                   gobject.TYPE_STRING, gobject.TYPE_STRING,
                                   gobject.TYPE_STRING, gobject.TYPE_STRING,
                                   gobject.TYPE_STRING)
        self.store.set_sort_column_id(MODEL_COL, gtk.SORT_ASCENDING)

        udev_trigger(subsystem="block", action="change")
        # So that drives onlined by these show up in the filter UI
        storage.iscsi.iscsi().startup(anaconda.intf)
        storage.fcoe.fcoe().startup(anaconda.intf)
        storage.zfcp.ZFCP().startup()
        # Note we do NOT call dasd.startup() here, that does not online drives,
        # but only checks if they need formatting.
        disks = filter(udev_device_is_disk, udev_get_block_devices())
        (singlepaths, mpaths, partitions) = identifyMultipaths(disks)

        # The device list could be really long, so we really only want to
        # iterate over it the bare minimum of times.  Dividing this list up
        # now means fewer elements to iterate over later.
        (raids, nonraids) = self.split_list(lambda d: isRAID(d) and not isCCISS(d),
                                            singlepaths)

        if anaconda.simpleFilter:
            # In the typical use case, the user likely only has one drive and
            # there's no point showing either the filtering UI or the
            # cleardisks UI.  Unfortunately, that means we need to duplicate
            # some of the getNext method.
            if len(singlepaths) == 1:
                anaconda.storage.exclusiveDisks = [udev_device_get_name(singlepaths[0])]
                return None

            self.pages = [self._makeBasic()]
            self.notebook.set_show_border(False)
            self.notebook.set_show_tabs(False)
        else:
            self.pages = [self._makeBasic(), self._makeRAID(),
                          self._makeMPath(), self._makeOther(),
                          self._makeSearch()]

        self.populate(nonraids, mpaths, raids)

        # If the "Add Advanced" button is ever clicked, we need to have a list
        # of what devices previously existed so we know what's new.  Then we
        # can just add the new devices to the UI.  This is going to be slow,
        # but the user has to click a button to get to the slow part.
        self._cachedDevices = NameCache(singlepaths)
        self._cachedMPaths = NameCache(mpaths)
        self._cachedRaidDevices = NameCache(raids)

        # Switch to the first notebook page that displays any devices.
        i = 0
        for pg in self.pages:
            if pg.getNVisible():
                self.notebook.set_current_page(i)
                break

            i += 1

        return self.vbox

    def populate(self, nonraids, mpaths, raids):
        def _addTuple(tuple):
            global totalDevices, totalSize
            global selectedDevices, selectedSize
            added = False

            self.store.append(None, tuple)

            for pg in self.pages:
                if pg.cb.isMember(tuple[0]):
                    added = True
                    pg.cb.addToUI(tuple)

            # Only update the size label if this device was added to any pages.
            # This prevents situations where we're only displaying the basic
            # filter that has one disk, but there are several advanced disks
            # in the store that cannot be seen.
            if added:
                totalDevices += 1
                totalSize += tuple[0]["XXX_SIZE"]

                if tuple[ACTIVE_COL]:
                    selectedDevices += 1
                    selectedSize += tuple[0]["XXX_SIZE"]

        def _isProtected(info):
            protectedNames = map(udev_resolve_devspec, self.anaconda.protected)

            sysfs_path = udev_device_get_sysfs_path(info)
            for protected in protectedNames:
                _p = "/sys/%s/%s" % (sysfs_path, protected)
                if os.path.exists(os.path.normpath(_p)):
                    return True

            return False

        def _active(info):
            if _isProtected(info):
                return True

            name = udev_device_get_name(info)

            if self.anaconda.storage.exclusiveDisks and \
               name in self.anaconda.storage.exclusiveDisks:
                return True
            elif self.anaconda.storage.ignoredDisks and \
                name not in self.anaconda.storage.ignoredDisks:
                return True
            else:
                return False

        for d in nonraids:
            name = udev_device_get_name(d)

            # We aren't guaranteed to be able to get a device.  In
            # particular, built-in USB flash readers show up as devices but
            # do not always have any media present, so parted won't be able
            # to find a device.
            try:
                partedDevice = parted.Device(path="/dev/" + name)
            except (_ped.IOException, _ped.DeviceException):
                continue
            d["XXX_SIZE"] = int(partedDevice.getSize())
            # cciss controllers, without any sets defined, show up as a 0 size
            # blockdev, ignore these
            if d["XXX_SIZE"] == 0:
                continue

            # This isn't so great, but iSCSI and s390 devices have an ID_PATH
            # that contains a lot of useful identifying info, so that should be
            # displayed instead of a blank WWID.
            if udev_device_is_iscsi(d) or udev_device_is_dasd(d) or udev_device_is_zfcp(d):
                ident = udev_device_get_path(d)
            else:
                ident = udev_device_get_wwid(d)

            tuple = (d, True, _active(d), _isProtected(d), name,
                     partedDevice.model, str(d["XXX_SIZE"]) + " MB",
                     udev_device_get_vendor(d), udev_device_get_bus(d),
                     udev_device_get_serial(d), ident, "", "", "", "")
            _addTuple(tuple)

        if raids and flags.dmraid:
            used_raidmembers = []
            for rs in block.getRaidSets():
                # dmraid does everything in sectors
                size = (rs.rs.sectors * 512) / (1024.0 * 1024.0)
                fstype = ""

                # get_members also returns subsets with layered raids, we only
                # want the devices
                members = filter(lambda m: isinstance(m, block.device.RaidDev),
                                 list(rs.get_members()))
                members = map(lambda m: m.get_devpath(), members)
                for d in raids:
                    if udev_device_get_name(d) in members:
                        fstype = udev_device_get_format(d)
                        sysfs_path = udev_device_get_sysfs_path(d)
                        break

                # Skip this set if none of its members are in the raids list
                if not fstype:
                    continue

                used_raidmembers.extend(members)

                # biosraid devices don't really get udev data, at least not in a
                # a way that's useful to the filtering UI.  So we need to fake
                # that data now so we have something to put into the store.
                data = {"XXX_SIZE": size, "ID_FS_TYPE": fstype,
                        "DM_NAME": rs.name, "name": rs.name,
                        "sysfs_path": sysfs_path}

                model = "BIOS RAID set (%s)" % rs.rs.set_type
                tuple = (data, True, _active(data), _isProtected(data), rs.name,
                         model, str(size) + " MB", "", "", "", "", "", "", "", "")
                _addTuple(tuple)

            unused_raidmembers = []
            for d in raids:
                if udev_device_get_name(d) not in used_raidmembers:
                    unused_raidmembers.append(udev_device_get_name(d))

            self.anaconda.intf.unusedRaidMembersWarning(unused_raidmembers)

        for mpath in mpaths:
            # We only need to grab information from the first device in the set.
            name = udev_device_get_name(mpath[0])

            try:
                partedDevice = parted.Device(path="/dev/" + name)
            except (_ped.IOException, _ped.DeviceException):
                continue
            mpath[0]["XXX_SIZE"] = int(partedDevice.getSize())
            model = partedDevice.model

            # However, we do need all the paths making up this multipath set.
            paths = "\n".join(map(udev_device_get_name, mpath))

            # We use a copy here, so as to not modify the original udev info
            # dict as that would break NameCache matching
            data = mpath[0].copy()
            data["name"] = udev_device_get_multipath_name(mpath[0])
            tuple = (data, True, _active(data), _isProtected(data),
                     udev_device_get_multipath_name(mpath[0]), model,
                     str(mpath[0]["XXX_SIZE"]) + " MB",
                     udev_device_get_vendor(mpath[0]),
                     udev_device_get_bus(mpath[0]),
                     udev_device_get_serial(mpath[0]),
                     udev_device_get_wwid(mpath[0]),
                     paths, "", "", "")
            _addTuple(tuple)

    def split_list(self, pred, lst):
        pos = []
        neg = []

        for ele in lst:
            if pred(ele):
                pos.append(ele)
            else:
                neg.append(ele)

        return (pos, neg)
