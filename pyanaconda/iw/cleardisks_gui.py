#
# Select which disks to clear and which ones to just mount.
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

import gtk, gobject
from pyanaconda import gui
from DeviceSelector import *
from pyanaconda.constants import *
from pyanaconda import isys
from iw_gui import *
from pyanaconda.storage.devices import deviceNameToDiskByPath
from pyanaconda.storage.udev import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class ClearDisksWindow (InstallWindow):
    windowTitle = N_("Clear Disks Selector")

    def getNext (self):
        # All the rows that are visible in the right hand side should be cleared.
        cleardisks = []
        for row in self.store:
            if row[self.rightVisible]:
                cleardisks.append(row[OBJECT_COL].name)

        if len(cleardisks) == 0:
            self.anaconda.intf.messageWindow(_("Error"),
                                             _("You must select at least one "
                                               "drive to be used for installation."),
                                             custom_icon="error")
            raise gui.StayOnScreen

        # The selected row is the disk to boot from.
        selected = self.rightDS.getSelected()

        if len(selected) == 0:
            self.anaconda.intf.messageWindow(_("Error"),
                                             _("You must select one drive to "
                                               "boot from."),
                                             custom_icon="error")
            raise gui.StayOnScreen

        cleardisks.sort(self.anaconda.storage.compareDisks)
        self.resetStorage(clear=cleardisks, boot=selected[0][OBJECT_COL].name)

    def resetStorage(self, clear=None, boot=None):
        """ Save clearPartDisks and reset storage, preserving stage1_drive. """
        # Re-scan the devices. We only come here for autopart, so the clearpart
        # type should be set appropriately already.
        self.anaconda.storage.config.clearPartDisks = clear
        self.anaconda.storage.reset()
        boot_disk = self.anaconda.storage.devicetree.getDeviceByName(boot)
        self.anaconda.bootloader.stage1_drive = boot_disk

    def getScreen (self, anaconda):
        # We can't just use exclusiveDisks here because of kickstart.  First,
        # the kickstart file could have used ignoredisk --drives= in which case
        # exclusiveDisks would be empty.  Second, ignoredisk is entirely
        # optional in which case neither list would be populated.  Luckily,
        # storage.disks takes isIgnored into account and that handles both these
        # issues.
        disks = filter(lambda d: not d.format.hidden, anaconda.storage.disks)

        self.anaconda = anaconda

        # Skip this screen as well if there's only one disk to use.
        if len(disks) == 1:
            self.resetStorage(clear=[disks[0].name], boot=disks[0].name)
            return None

        (xml, self.vbox) = gui.getGladeWidget("cleardisks.glade", "vbox")
        self.leftScroll = xml.get_widget("leftScroll")
        self.rightScroll = xml.get_widget("rightScroll")
        self.addButton = xml.get_widget("addButton")
        self.removeButton = xml.get_widget("removeButton")
        self.installTargetImage = xml.get_widget("installTargetImage")
        self.installTargetTip = xml.get_widget("installTargetTip")

        self.leftVisible = 1
        self.leftActive = 2
        self.rightVisible = 4
        self.rightActive = 5

        # One store for both views.  First the obejct, then a visible/active for
        # the left hand side, then a visible/active for the right hand side, then
        # all the other stuff.
        #
        # NOTE: the third boolean is a placeholder.  DeviceSelector uses the third
        # slot in the store to determine whether the row is immutable or not.  We
        # just need to put False in there for everything.
        self.store = gtk.TreeStore(gobject.TYPE_PYOBJECT,
                                   gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN,
                                   gobject.TYPE_BOOLEAN,
                                   gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN,
                                   gobject.TYPE_STRING, gobject.TYPE_STRING,
                                   gobject.TYPE_STRING, gobject.TYPE_STRING,
                                   gobject.TYPE_STRING)
        self.store.set_sort_column_id(6, gtk.SORT_ASCENDING)

        # The left view shows all the drives that will just be mounted, but
        # can still be moved to the right hand side.
        self.leftFilteredModel = self.store.filter_new()
        self.leftSortedModel = gtk.TreeModelSort(self.leftFilteredModel)
        self.leftTreeView = gtk.TreeView(self.leftSortedModel)

        self.leftFilteredModel.set_visible_func(lambda model, iter, view: model.get_value(iter, self.leftVisible), self.leftTreeView)

        self.leftScroll.add(self.leftTreeView)

        self.leftDS = DeviceSelector(self.store, self.leftSortedModel,
                                     self.leftTreeView, visible=self.leftVisible,
                                     active=self.leftActive)
        self.leftDS.createMenu()
        self.leftDS.addColumn(_("Model"), 6)
        self.leftDS.addColumn(_("Capacity"), 7)
        self.leftDS.addColumn(_("Vendor"), 8)
        self.leftDS.addColumn(_("Identifier"), 9)
        self.leftDS.addColumn(_("Interconnect"), 10, displayed=False)

        # The right view show all the drives that will be wiped during install.
        self.rightFilteredModel = self.store.filter_new()
        self.rightSortedModel = gtk.TreeModelSort(self.rightFilteredModel)
        self.rightTreeView = gtk.TreeView(self.rightSortedModel)

        self.rightFilteredModel.set_visible_func(lambda model, iter, view: model.get_value(iter, self.rightVisible), self.rightTreeView)

        self.rightScroll.add(self.rightTreeView)

        self.rightDS = DeviceSelector(self.store, self.rightSortedModel,
                                      self.rightTreeView, visible=self.rightVisible,
                                      active=self.rightActive)
        self.rightDS.createSelectionCol(title=_("Boot\nLoader"), radioButton=True)
        self.rightDS.createMenu()
        self.rightDS.addColumn(_("Model"), 6)
        self.rightDS.addColumn(_("Capacity"), 7)
        self.rightDS.addColumn(_("Identifier"), 9)

        # Store the first disk (according to bootloader ordering) for
        # auto boot device selection
        self.bootDisk = getattr(self.anaconda.bootloader.stage1_drive,
                                "name",
                                self.anaconda.bootloader.drives[0].name)

        # The device filtering UI set up exclusiveDisks as a list of the names
        # of all the disks we should use later on.  Now we need to go get those,
        # look up some more information in the devicetree, and set up the
        # selector.
        for d in disks:
            rightVisible = d.name in self.anaconda.storage.config.clearPartDisks
            rightActive = rightVisible and d.name == self.bootDisk
            leftVisible = not rightVisible

            if hasattr(d, "wwid"):
                ident = d.wwid
            else:
                try:
                    ident = deviceNameToDiskByPath(d.name)
                    if ident.startswith("/dev/disk/by-path/"):
                        ident = ident.replace("/dev/disk/by-path/", "")
                except DeviceNotFoundError:
                    ident = d.name

            self.store.append(None, (d,
                                     leftVisible, True, False,
                                     rightVisible, rightActive,
                                     d.model,
                                     str(int(d.size)) + " MB",
                                     d.vendor, ident, d.bus))

        self.addButton.connect("clicked", self._add_clicked)
        self.removeButton.connect("clicked", self._remove_clicked)

        # Also allow moving devices back and forth with double click, enter, etc.
        self.leftTreeView.connect("row-activated", self._add_clicked)
        self.rightTreeView.disconnect(self.rightDS._activated_id)
        self.rightTreeView.connect("row-activated", self._remove_clicked)

        # And let the user select multiple devices at a time.
        self.leftTreeView.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.rightTreeView.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        if self.anaconda.storage.config.clearPartType == CLEARPART_TYPE_LINUX:
            self.installTargetTip.set_markup(_("<b>Tip:</b> All Linux filesystems on the install target devices will be reformatted and wiped of any data.  Make sure you have backups."))
        elif self.anaconda.storage.config.clearPartType == CLEARPART_TYPE_ALL:
            self.installTargetTip.set_markup(_("<b>Tip:</b> The install target devices will be reformatted and wiped of any data.  Make sure you have backups."))
        else:
            self.installTargetTip.set_markup(_("<b>Tip:</b> Your filesystems on the install target devices will not be reformatted unless you choose to do so during customization."))

        return self.vbox

    def _autoSelectBootDisk(self):
        if self.rightDS.getSelected():
            return

        for row in self.store:
            if row[OBJECT_COL].name == self.bootDisk and row[self.rightVisible]:
                row[self.rightActive] = True

    def _add_clicked(self, widget, *args, **kwargs):
        (sortedModel, pathlist) = self.leftTreeView.get_selection().get_selected_rows()

        if not pathlist:
            return

        for path in reversed(pathlist):
            sortedIter = sortedModel.get_iter(path)
            if not sortedIter:
                continue

            filteredIter = self.leftSortedModel.convert_iter_to_child_iter(None, sortedIter)
            iter = self.leftFilteredModel.convert_iter_to_child_iter(filteredIter)

            self.store.set_value(iter, self.leftVisible, False)
            self.store.set_value(iter, self.rightVisible, True)
            self.store.set_value(iter, self.rightActive, False)

        self._autoSelectBootDisk()
        self.leftFilteredModel.refilter()
        self.rightFilteredModel.refilter()

    def _remove_clicked(self, widget, *args, **kwargs):
        (sortedModel, pathlist) = self.rightTreeView.get_selection().get_selected_rows()

        if not pathlist:
            return

        for path in reversed(pathlist):
            sortedIter = sortedModel.get_iter(path)
            if not sortedIter:
                continue

            filteredIter = self.rightSortedModel.convert_iter_to_child_iter(None, sortedIter)
            iter = self.rightFilteredModel.convert_iter_to_child_iter(filteredIter)

            self.store.set_value(iter, self.leftVisible, True)
            self.store.set_value(iter, self.rightVisible, False)
            self.store.set_value(iter, self.rightActive, False)

        self._autoSelectBootDisk()
        self.leftFilteredModel.refilter()
        self.rightFilteredModel.refilter()
