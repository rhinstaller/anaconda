# Storage filtering classes
#
# Copyright (C) 2013  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

from gi.repository import Gtk

from collections import namedtuple

from blivet import arch
from blivet.devices import DASDDevice, FcoeDiskDevice, iScsiDiskDevice, MultipathDevice, ZFCPDiskDevice
from blivet.fcoe import has_fcoe

from pyanaconda.flags import flags
from pyanaconda.i18n import CN_, CP_

from pyanaconda.ui.lib.disks import getDisks
from pyanaconda.ui.gui.utils import timed_action
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.advstorage.fcoe import FCoEDialog
from pyanaconda.ui.gui.spokes.advstorage.iscsi import ISCSIDialog
from pyanaconda.ui.gui.spokes.advstorage.zfcp import ZFCPDialog
from pyanaconda.ui.gui.spokes.advstorage.dasd import DASDDialog
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.categories.system import SystemCategory

__all__ = ["FilterSpoke"]

DiskStoreRow = namedtuple("DiskStoreRow", ["visible", "selected", "mutable",
                                           "name", "type", "model", "capacity",
                                           "vendor", "interconnect", "serial",
                                           "wwid", "paths", "port", "target",
                                           "lun", "ccw", "wwpn"])

class FilterPage(object):
    """A FilterPage is the logic behind one of the notebook tabs on the filter
       UI spoke.  Each page has its own specific filtered model overlaid on top
       of a common model that holds all non-advanced disks.

       A Page is created once, when the filter spoke is initialized.  It is
       setup multiple times - each time the spoke is revisited.  When the Page
       is setup, it is given a complete view of all disks that belong on this
       Page.  This is because certain pages may require populating a combo with
       all vendor names, or other similar tasks.

       This class is just a base class.  One subclass should be created for each
       more specialized type of page.  Only one instance of each subclass should
       ever be created.
    """
    def __init__(self, storage, builder):
        """Create a new FilterPage instance.

           Instance attributes:

           builder      -- A reference to the Gtk.Builder instance containing
                           this page's UI elements.
           filterActive -- Whether the user has chosen to filter results down
                           on this page.  If set, visible_func should take the
                           filter UI elements into account.
           storage      -- An instance of a blivet object.
        """
        self.builder = builder
        self.storage = storage
        self.model = None

        self.filterActive = False

    def ismember(self, device):
        """Does device belong on this page?  This function should taken into
           account what kind of thing device is.  It should not be concerned
           with any sort of filtering settings.  It only determines whether
           device belongs.
        """
        return True

    def setup(self, store, selectedNames, disks):
        """Do whatever setup of the UI is necessary before this page can be
           displayed.  This function is called every time the filter spoke
           is revisited, and thus must first do any cleanup that is necessary.

           The setup function is passed a reference to the master store, a list
           of names of disks the user has selected (either from a previous visit
           or via kickstart), and a list of all disk objects that belong on this
           page as determined from the ismember method.

           At the least, this method should add all the disks to the store.  It
           may also need to populate combos and other lists as appropriate.
        """
        pass

    def clear(self):
        """Blank out any filtering-related fields on this page and return them
           to their defaults.  This is called when the Clear button is clicked.
        """
        pass

    def visible_func(self, model, itr, *args):
        """This method is called for every row (disk) in the store, in order to
           determine if it should be displayed on this page or not.  This method
           should take into account whether filterActive is set, perhaps whether
           something in pyanaconda.flags is setup, and other settings to make
           a final decision.  Because filtering can be complicated, many pages
           will want to farm this decision out to another method.

           The return value is a boolean indicating whether the row is visible
           or not.
        """
        return True

    def setupCombo(self, combo, items):
        """Populate a given GtkComboBoxText instance with a list of items.  The
           combo will first be cleared, so this method is suitable for calling
           repeatedly.  The first item in the list will be selected by default.
        """
        combo.remove_all()
        for i in sorted(items):
            combo.append_text(i)

        if items:
            combo.set_active(0)

    def _long_identifier(self, disk):
        # For iSCSI devices, we want the long ip-address:port-iscsi-tgtname-lun-XX
        # identifier, but blivet doesn't expose that in any useful way and I don't
        # want to go asking udev.  Instead, we dig around in the deviceLinks and
        # default to the name if we can't figure anything else out.
        for link in disk.deviceLinks:
            if "by-path" in link:
                lastSlash = link.rindex("/")+1
                return link[lastSlash:]

        return disk.name

class SearchPage(FilterPage):
    def __init__(self, storage, builder):
        FilterPage.__init__(self, storage, builder)
        self.model = self.builder.get_object("searchModel")
        self.model.set_visible_func(self.visible_func)

        self._lunEntry = self.builder.get_object("searchLUNEntry")
        self._wwidEntry = self.builder.get_object("searchWWIDEntry")

        self._combo = self.builder.get_object("searchTypeCombo")
        self._portCombo = self.builder.get_object("searchPortCombo")
        self._targetEntry = self.builder.get_object("searchTargetEntry")

    def setup(self, store, selectedNames, disks):
        self._combo.set_active(0)
        self._combo.emit("changed")

        ports = []
        for disk in disks:
            if hasattr(disk, "node"):
                ports.append(str(disk.node.port))

        self.setupCombo(self.builder.get_object("searchPortCombo"), ports)

    def clear(self):
        self._lunEntry.set_text("")
        self._portCombo.set_active(0)
        self._targetEntry.set_text("")
        self._wwidEntry.set_text("")

    def _port_equal(self, device):
        active = self._portCombo.get_active_text()
        if active and hasattr(device, "node"):
            return device.node.port == active
        else:
            return True

    def _target_equal(self, device):
        active = self._targetEntry.get_text().strip()
        if active:
            return active in getattr(device, "initiator", "")
        else:
            return True

    def _lun_equal(self, device):
        active = self._lunEntry.get_text().strip()
        if active and hasattr(device, "node"):
            try:
                return int(active) == device.node.tpgt
            except ValueError:
                return True
        elif active and hasattr(device, "fcp_lun"):
            return active in device.fcp_lun
        else:
            return True

    def _filter_func(self, device):
        if not self.filterActive:
            return True

        filterBy = self._combo.get_active()

        if filterBy == 0:
            return True
        elif filterBy == 1:
            return self._port_equal(device) and self._target_equal(device) and self._lun_equal(device)
        elif filterBy == 2:
            return self._wwidEntry.get_text() in getattr(device, "wwid", self._long_identifier(device))

    def visible_func(self, model, itr, *args):
        obj = DiskStoreRow(*model[itr])
        device = self.storage.devicetree.getDeviceByName(obj.name, hidden=True)
        return self._filter_func(device)

class MultipathPage(FilterPage):
    def __init__(self, storage, builder):
        FilterPage.__init__(self, storage, builder)
        self.model = self.builder.get_object("multipathModel")
        self.model.set_visible_func(self.visible_func)

        self._combo = self.builder.get_object("multipathTypeCombo")
        self._icCombo = self.builder.get_object("multipathInterconnectCombo")
        self._vendorCombo = self.builder.get_object("multipathVendorCombo")
        self._wwidEntry = self.builder.get_object("multipathWWIDEntry")

    def ismember(self, device):
        return isinstance(device, MultipathDevice)

    def setup(self, store, selectedNames, disks):
        vendors = []
        interconnects = []

        for disk in disks:
            paths = [d.name for d in disk.parents]
            selected = disk.name in selectedNames

            store.append([True, selected, not disk.protected,
                          disk.name, "", disk.model, str(disk.size),
                          disk.vendor, disk.bus, disk.serial,
                          disk.wwid, "\n".join(paths), "", "",
                          "", "", ""])
            if not disk.vendor in vendors:
                vendors.append(disk.vendor)

            if not disk.bus in interconnects:
                interconnects.append(disk.bus)

        self._combo.set_active(0)
        self._combo.emit("changed")

        self.setupCombo(self._vendorCombo, vendors)
        self.setupCombo(self._icCombo, interconnects)

    def clear(self):
        self._icCombo.set_active(0)
        self._vendorCombo.set_active(0)
        self._wwidEntry.set_text("")

    def _filter_func(self, device):
        if not self.filterActive:
            return True

        filterBy = self._combo.get_active()

        if filterBy == 0:
            return True
        elif filterBy == 1:
            return device.vendor == self._vendorCombo.get_active_text()
        elif filterBy == 2:
            return device.bus == self._icCombo.get_active_text()
        elif filterBy == 3:
            return self._wwidEntry.get_text() in device.wwid

    def visible_func(self, model, itr, *args):
        if not flags.mpath:
            return False

        obj = DiskStoreRow(*model[itr])
        device = self.storage.devicetree.getDeviceByName(obj.name, hidden=True)
        return self.ismember(device) and self._filter_func(device)

class OtherPage(FilterPage):
    def __init__(self, storage, builder):
        FilterPage.__init__(self, storage, builder)
        self.model = self.builder.get_object("otherModel")
        self.model.set_visible_func(self.visible_func)

        self._combo = self.builder.get_object("otherTypeCombo")
        self._icCombo = self.builder.get_object("otherInterconnectCombo")
        self._idEntry = self.builder.get_object("otherIDEntry")
        self._vendorCombo = self.builder.get_object("otherVendorCombo")

    def ismember(self, device):
        return isinstance(device, iScsiDiskDevice) or isinstance(device, FcoeDiskDevice)

    def setup(self, store, selectedNames, disks):
        vendors = []
        interconnects = []

        for disk in disks:
            paths = [d.name for d in disk.parents]
            selected = disk.name in selectedNames

            if hasattr(disk, "node"):
                port = str(disk.node.port)
                lun = str(disk.node.tpgt)
            else:
                port = ""
                lun = ""

            store.append([True, selected, not disk.protected,
                          disk.name, "", disk.model, str(disk.size),
                          disk.vendor, disk.bus, disk.serial,
                          self._long_identifier(disk), "\n".join(paths), port, getattr(disk, "initiator", ""),
                          lun, "", ""])

            if not disk.vendor in vendors:
                vendors.append(disk.vendor)

            if not disk.bus in interconnects:
                interconnects.append(disk.bus)

        self._combo.set_active(0)
        self._combo.emit("changed")

        self.setupCombo(self._vendorCombo, vendors)
        self.setupCombo(self._icCombo, interconnects)

    def clear(self):
        self._icCombo.set_active(0)
        self._idEntry.set_text("")
        self._vendorCombo.set_active(0)

    def _filter_func(self, device):
        if not self.filterActive:
            return True

        filterBy = self._combo.get_active()

        if filterBy == 0:
            return True
        elif filterBy == 1:
            return device.vendor == self._vendorCombo.get_active_text()
        elif filterBy == 2:
            return device.bus == self._icCombo.get_active_text()
        elif filterBy == 3:
            for link in device.deviceLinks:
                if "by-path" in link:
                    return self._idEntry.get_text().strip() in link

            return False

    def visible_func(self, model, itr, *args):
        obj = DiskStoreRow(*model[itr])
        device = self.storage.devicetree.getDeviceByName(obj.name, hidden=True)
        return self.ismember(device) and self._filter_func(device)

class ZPage(FilterPage):
    def __init__(self, storage, builder):
        FilterPage.__init__(self, storage, builder)
        self.model = self.builder.get_object("zModel")
        self.model.set_visible_func(self.visible_func)

        self._ccwEntry = self.builder.get_object("zCCWEntry")
        self._wwpnEntry = self.builder.get_object("zWWPNEntry")
        self._lunEntry = self.builder.get_object("zLUNEntry")
        self._combo = self.builder.get_object("zTypeCombo")

        self._isS390 = arch.isS390()

    def clear(self):
        self._lunEntry.set_text("")
        self._ccwEntry.set_text("")
        self._wwpnEntry.set_text("")

    def ismember(self, device):
        return isinstance(device, ZFCPDiskDevice) or isinstance(device, DASDDevice)

    def setup(self, store, selectedNames, disks):
        """ Set up our Z-page, but only if we're running on s390x. """
        if not self._isS390:
            return
        else:
            ccws = []
            wwpns = []
            luns = []

            self._combo.set_active(0)
            self._combo.emit("changed")

            for disk in disks:
                paths = [d.name for d in disk.parents]
                selected = disk.name in selectedNames

                if getattr(disk, "type") == "zfcp":
                    # remember to store all of the zfcp-related junk so we can
                    # see it in the UI
                    if not disk.fcp_lun in luns:
                        luns.append(disk.fcp_lun)
                    if not disk.wwpn in wwpns:
                        wwpns.append(disk.wwpn)
                    if not disk.hba_id in ccws:
                        ccws.append(disk.hba_id)

                    # now add it to our store
                    store.append([True, selected, not disk.protected,
                                  disk.name, "", disk.model, str(disk.size),
                                  disk.vendor, disk.bus, disk.serial, "", "\n".join(paths),
                                  "", "", disk.fcp_lun, disk.hba_id, disk.wwpn])

    def _filter_func(self, device):
        if not self.filterActive:
            return True

        filterBy = self._combo.get_active()

        if filterBy == 0:
            return True
        elif filterBy == 1:
            return self._ccwEntry.get_text() in device.hba_id
        elif filterBy == 2:
            return self._wwpnEntry.get_text() in device.wwpn
        elif filterBy == 3:
            return self._lunEntry.get_text() in device.fcp_lun

        return False

    def visible_func(self, model, itr, *args):
        obj = DiskStoreRow(*model[itr])
        device = self.storage.devicetree.getDeviceByName(obj.name, hidden=True)
        return self.ismember(device) and self._filter_func(device)

class FilterSpoke(NormalSpoke):
    builderObjects = ["diskStore", "filterWindow",
                      "searchModel", "multipathModel", "otherModel", "zModel"]
    mainWidgetName = "filterWindow"
    uiFile = "spokes/filter.glade"
    helpFile = "FilterSpoke.xml"

    category = SystemCategory

    title = CN_("GUI|Spoke", "_INSTALLATION DESTINATION")

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        self.applyOnSkip = True

        self.ancestors = []
        self.disks = []
        self.selected_disks = []

    @property
    def indirect(self):
        return True

    # This spoke has no status since it's not in a hub
    @property
    def status(self):
        return None

    def apply(self):
        onlyuse = self.selected_disks[:]
        for disk in [d for d in self.storage.disks if d.name in onlyuse]:
            onlyuse.extend([d.name for d in disk.ancestors
                                        if d.name not in onlyuse])

        self.data.ignoredisk.onlyuse = onlyuse
        self.data.clearpart.drives = self.selected_disks[:]

    def initialize(self):
        NormalSpoke.initialize(self)

        self.pages = [SearchPage(self.storage, self.builder),
                      MultipathPage(self.storage, self.builder),
                      OtherPage(self.storage, self.builder),
                      ZPage(self.storage, self.builder)]

        self._notebook = self.builder.get_object("advancedNotebook")

        if not arch.isS390():
            self._notebook.remove_page(-1)
            self.builder.get_object("addZFCPButton").destroy()
            self.builder.get_object("addDASDButton").destroy()

        if not has_fcoe():
            self.builder.get_object("addFCOEButton").destroy()

        self._store = self.builder.get_object("diskStore")
        self._addDisksButton = self.builder.get_object("addDisksButton")

        # Connect focus events in scrolled viewport children to scrolling on the viewport
        searchScrolledViewport = self.builder.get_object("searchScrolledViewport")
        searchGrid = self.builder.get_object("searchGrid")
        searchGrid.set_focus_hadjustment(searchScrolledViewport.get_hadjustment())
        searchGrid.set_focus_vadjustment(searchScrolledViewport.get_vadjustment())

        multipathViewport = self.builder.get_object("multipathViewport")
        multipathGrid = self.builder.get_object("multipathGrid")
        multipathGrid.set_focus_hadjustment(multipathViewport.get_hadjustment())
        multipathGrid.set_focus_vadjustment(multipathViewport.get_vadjustment())

        otherViewport = self.builder.get_object("otherViewport")
        otherGrid = self.builder.get_object("otherGrid")
        otherGrid.set_focus_hadjustment(otherViewport.get_hadjustment())
        otherGrid.set_focus_vadjustment(otherViewport.get_vadjustment())

        zViewport = self.builder.get_object("zViewport")
        zGrid = self.builder.get_object("zGrid")
        zGrid.set_focus_hadjustment(zViewport.get_hadjustment())
        zGrid.set_focus_vadjustment(zViewport.get_vadjustment())

    def _real_ancestors(self, disk):
        # Return a list of all the ancestors of a disk, but remove the disk
        # itself from this list.
        return [d for d in disk.ancestors if d.name != disk.name]

    def refresh(self):
        NormalSpoke.refresh(self)

        self.disks = getDisks(self.storage.devicetree)
        self.selected_disks = self.data.ignoredisk.onlyuse[:]

        self.ancestors = [d.name for disk in self.disks for d in self._real_ancestors(disk)]

        self._store.clear()

        allDisks = []
        multipathDisks = []
        otherDisks = []
        zDisks = []

        # Now all all the non-local disks to the store.  Everything has been set up
        # ahead of time, so there's no need to configure anything.  We first make
        # these lists of disks, then call setup on each individual page.  This is
        # because there could be page-specific setup to do that requires a complete
        # view of all the disks on that page.
        for disk in self.disks:
            if self.pages[1].ismember(disk):
                multipathDisks.append(disk)
            elif self.pages[2].ismember(disk):
                otherDisks.append(disk)
            elif self.pages[3].ismember(disk):
                zDisks.append(disk)

            allDisks.append(disk)

        self.pages[0].setup(self._store, self.selected_disks, allDisks)
        self.pages[1].setup(self._store, self.selected_disks, multipathDisks)
        self.pages[2].setup(self._store, self.selected_disks, otherDisks)
        self.pages[3].setup(self._store, self.selected_disks, zDisks)

        self._update_summary()

    def _update_summary(self):
        summaryButton = self.builder.get_object("summary_button")
        label = self.builder.get_object("summary_button_label")

        # We need to remove ancestor devices from the count.  Otherwise, we'll
        # end up in a situation where selecting one multipath device could
        # potentially show three devices selected (mpatha, sda, sdb for instance).
        count = len([disk for disk in self.selected_disks if disk not in self.ancestors])

        summary = CP_("GUI|Installation Destination|Filter",
                     "%d _storage device selected",
                     "%d _storage devices selected",
                     count) % count

        label.set_text(summary)
        label.set_use_underline(True)

        summaryButton.set_visible(count > 0)
        label.set_sensitive(count > 0)

    def on_back_clicked(self, button):
        self.skipTo = "StorageSpoke"
        NormalSpoke.on_back_clicked(self, button)

    def on_summary_clicked(self, button):
        dialog = SelectedDisksDialog(self.data)

        # Include any disks selected in the initial storage spoke, plus any
        # selected in this filter UI.
        disks = [disk for disk in self.disks if disk.name in self.selected_disks]
        free_space = self.storage.getFreeSpace(disks=disks)

        with self.main_window.enlightbox(dialog.window):
            dialog.refresh(disks, free_space, showRemove=False, setBoot=False)
            dialog.run()

    def on_find_clicked(self, button):
        n = self._notebook.get_current_page()
        self.pages[n].filterActive = True
        self.pages[n].model.refilter()

    def on_clear_icon_clicked(self, entry, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            entry.set_text("")

    def on_page_switched(self, notebook, newPage, newPageNum, *args):
        self.pages[newPageNum].model.refilter()
        notebook.get_nth_page(newPageNum).show_all()

    def on_row_toggled(self, button, path):
        if not path:
            return

        page_index = self._notebook.get_current_page()
        filter_model = self.pages[page_index].model
        model_itr = filter_model.get_iter(path)
        itr = filter_model.convert_iter_to_child_iter(model_itr)
        self._store[itr][1] = not self._store[itr][1]

        if self._store[itr][1] and self._store[itr][3] not in self.selected_disks:
            self.selected_disks.append(self._store[itr][3])
        elif not self._store[itr][1] and self._store[itr][3] in self.selected_disks:
            self.selected_disks.remove(self._store[itr][3])

        self._update_summary()

    @timed_action(delay=50, threshold=100)
    def on_refresh_clicked(self, widget, *args):
        self.storage.devicetree.populate()
        self.refresh()

    def on_add_iscsi_clicked(self, widget, *args):
        dialog = ISCSIDialog(self.data, self.storage)

        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

        # We now need to refresh so any new disks picked up by adding advanced
        # storage are displayed in the UI.
        self.refresh()

    def on_add_fcoe_clicked(self, widget, *args):
        dialog = FCoEDialog(self.data, self.storage)

        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

        # We now need to refresh so any new disks picked up by adding advanced
        # storage are displayed in the UI.
        self.refresh()

    def on_add_zfcp_clicked(self, widget, *args):
        dialog = ZFCPDialog(self.data, self.storage)

        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

        # We now need to refresh so any new disks picked up by adding advanced
        # storage are displayed in the UI.
        self.refresh()

    def on_add_dasd_clicked(self, widget, *args):
        dialog = DASDDialog(self.data, self.storage)

        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

        # We now need to refresh so any new disks picked up by adding advanced
        # storage are displayed in the UI.
        self.refresh()

    ##
    ## SEARCH TAB SIGNAL HANDLERS
    ##
    def on_search_type_changed(self, combo):
        ndx = combo.get_active()

        notebook = self.builder.get_object("searchTypeNotebook")
        findButton = self.builder.get_object("searchFindButton")

        findButton.set_sensitive(ndx != 0)
        notebook.set_current_page(ndx)

    ##
    ## MULTIPATH TAB SIGNAL HANDLERS
    ##
    def on_multipath_type_changed(self, combo):
        ndx = combo.get_active()

        notebook = self.builder.get_object("multipathTypeNotebook")
        findButton = self.builder.get_object("multipathFindButton")

        findButton.set_sensitive(ndx != 0)
        notebook.set_current_page(ndx)

    ##
    ## OTHER TAB SIGNAL HANDLERS
    ##
    def on_other_type_combo_changed(self, combo):
        ndx = combo.get_active()

        notebook = self.builder.get_object("otherTypeNotebook")
        findButton = self.builder.get_object("otherFindButton")

        findButton.set_sensitive(ndx != 0)
        notebook.set_current_page(ndx)

    ##
    ## Z TAB SIGNAL HANDLERS
    ##
    def on_z_type_combo_changed(self, combo):
        ndx = combo.get_active()

        notebook = self.builder.get_object("zTypeNotebook")
        findButton = self.builder.get_object("zFindButton")

        findButton.set_sensitive(ndx != 0)
        notebook.set_current_page(ndx)
