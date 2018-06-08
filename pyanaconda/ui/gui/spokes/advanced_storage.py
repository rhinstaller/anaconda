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

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from collections import namedtuple

from blivet import arch
from blivet.devices import DASDDevice, FcoeDiskDevice, iScsiDiskDevice, MultipathDevice, \
    ZFCPDiskDevice, NVDIMMNamespaceDevice
from blivet.fcoe import has_fcoe
from blivet.iscsi import iscsi

from pyanaconda.flags import flags
from pyanaconda.core.i18n import CN_, CP_
from pyanaconda.storage_utils import try_populate_devicetree, on_disk_storage
from pyanaconda.modules.common.constants.objects import DISK_SELECTION
from pyanaconda.modules.common.constants.services import STORAGE

from pyanaconda.ui.lib.disks import getDisks, applyDiskSelection
from pyanaconda.ui.gui.utils import timed_action
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.advstorage.fcoe import FCoEDialog
from pyanaconda.ui.gui.spokes.advstorage.iscsi import ISCSIDialog
from pyanaconda.ui.gui.spokes.advstorage.zfcp import ZFCPDialog
from pyanaconda.ui.gui.spokes.advstorage.dasd import DASDDialog
from pyanaconda.ui.gui.spokes.advstorage.nvdimm import NVDIMMDialog
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.categories.system import SystemCategory

__all__ = ["FilterSpoke"]

PAGE_SEARCH = 0
PAGE_MULTIPATH = 1
PAGE_OTHER = 2
PAGE_NVDIMM = 3
PAGE_Z = 4

DiskStoreRow = namedtuple("DiskStoreRow", ["visible", "selected", "mutable",
                                           "name", "type", "model", "capacity",
                                           "vendor", "interconnect", "serial",
                                           "wwid", "paths", "port", "target",
                                           "lun", "ccw", "wwpn", "namespace", "mode"])

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
           repeatedly. The first item in the list will be empty to allow the
           combo box criterion to be cleared. The first non-empty item in the
           list will be selected by default.
        """
        combo.remove_all()
        combo.append_text('')

        for i in sorted(set(items)):
            combo.append_text(i)

        if items:
            combo.set_active(1)

    def _long_identifier(self, disk):
        # For iSCSI devices, we want the long ip-address:port-iscsi-tgtname-lun-XX
        # identifier, but blivet doesn't expose that in any useful way and I don't
        # want to go asking udev.  Instead, we dig around in the deviceLinks and
        # default to the name if we can't figure anything else out.
        for link in disk.device_links:
            if "by-path" in link:
                lastSlash = link.rindex("/")+1
                return link[lastSlash:]

        return disk.name

class SearchPage(FilterPage):
    # Match these to searchTypeCombo ids in glade
    SEARCH_TYPE_NONE = 'None'
    SEARCH_TYPE_PORT_TARGET_LUN = 'PTL'
    SEARCH_TYPE_WWID = 'WWID'

    def __init__(self, storage, builder):
        super().__init__(storage, builder)
        self.model = self.builder.get_object("searchModel")
        self.model.set_visible_func(self.visible_func)

        self._lunEntry = self.builder.get_object("searchLUNEntry")
        self._wwidEntry = self.builder.get_object("searchWWIDEntry")

        self._combo = self.builder.get_object("searchTypeCombo")
        self._portCombo = self.builder.get_object("searchPortCombo")
        self._targetEntry = self.builder.get_object("searchTargetEntry")

    def setup(self, store, selectedNames, disks):
        self._combo.set_active_id(self.SEARCH_TYPE_NONE)
        self._combo.emit("changed")

        ports = []
        for disk in disks:
            if hasattr(disk, "node") and disk.node is not None:
                ports.append(str(disk.node.port))

        self.setupCombo(self._portCombo, ports)

    def clear(self):
        self._lunEntry.set_text("")
        self._portCombo.set_active(0)
        self._targetEntry.set_text("")
        self._wwidEntry.set_text("")

    def _port_equal(self, device):
        active = self._portCombo.get_active_text()
        if active:
            if hasattr(device, "node"):
                return device.node.port == int(active)
            else:
                return False
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
        if active:
            if hasattr(device, "node"):
                try:
                    return int(active) == device.node.tpgt
                except ValueError:
                    return False
            elif hasattr(device, "fcp_lun"):
                return active in device.fcp_lun
        else:
            return True

    def _filter_func(self, device):
        if not self.filterActive:
            return True

        filterBy = self._combo.get_active_id()

        if filterBy == self.SEARCH_TYPE_NONE:
            return True
        elif filterBy == self.SEARCH_TYPE_PORT_TARGET_LUN:
            return self._port_equal(device) and self._target_equal(device) and self._lun_equal(device)
        elif filterBy == self.SEARCH_TYPE_WWID:
            return self._wwidEntry.get_text() in getattr(device, "wwn", self._long_identifier(device))

    def visible_func(self, model, itr, *args):
        obj = DiskStoreRow(*model[itr])
        device = self.storage.devicetree.get_device_by_name(obj.name, hidden=True)
        return self._filter_func(device)

class MultipathPage(FilterPage):
    # Match these to multipathTypeCombo ids in glade
    SEARCH_TYPE_NONE = 'None'
    SEARCH_TYPE_VENDOR = 'Vendor'
    SEARCH_TYPE_INTERCONNECT = 'Interconnect'
    SEARCH_TYPE_WWID = 'WWID'

    def __init__(self, storage, builder):
        super().__init__(storage, builder)
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
                          disk.wwn, "\n".join(paths), "", "",
                          "", "", "", "", ""])
            if not disk.vendor in vendors:
                vendors.append(disk.vendor)

            if not disk.bus in interconnects:
                interconnects.append(disk.bus)

        self._combo.set_active_id(self.SEARCH_TYPE_NONE)
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

        filterBy = self._combo.get_active_id()

        if filterBy == self.SEARCH_TYPE_NONE:
            return True
        elif filterBy == self.SEARCH_TYPE_VENDOR:
            return device.vendor == self._vendorCombo.get_active_text()
        elif filterBy == self.SEARCH_TYPE_INTERCONNECT:
            return device.bus == self._icCombo.get_active_text()
        elif filterBy == self.SEARCH_TYPE_WWID:
            return self._wwidEntry.get_text() in device.wwn

    def visible_func(self, model, itr, *args):
        if not flags.mpath:
            return False

        obj = DiskStoreRow(*model[itr])
        device = self.storage.devicetree.get_device_by_name(obj.name, hidden=True)
        return self.ismember(device) and self._filter_func(device)

class OtherPage(FilterPage):
    # Match these to otherTypeCombo ids in glade
    SEARCH_TYPE_NONE = 'None'
    SEARCH_TYPE_VENDOR = 'Vendor'
    SEARCH_TYPE_INTERCONNECT = 'Interconnect'
    SEARCH_TYPE_ID = 'ID'

    def __init__(self, storage, builder):
        super().__init__(storage, builder)
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

            if hasattr(disk, "node") and disk.node is not None:
                port = str(disk.node.port)
                lun = str(disk.node.tpgt)
            else:
                port = ""
                lun = ""

            store.append([True, selected, not disk.protected,
                          disk.name, "", disk.model, str(disk.size),
                          disk.vendor, disk.bus, disk.serial,
                          self._long_identifier(disk), "\n".join(paths), port, getattr(disk, "initiator", ""),
                          lun, "", "", "", ""])

            if not disk.vendor in vendors:
                vendors.append(disk.vendor)

            if not disk.bus in interconnects:
                interconnects.append(disk.bus)

        self._combo.set_active_id(self.SEARCH_TYPE_NONE)
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

        filterBy = self._combo.get_active_id()

        if filterBy == self.SEARCH_TYPE_NONE:
            return True
        elif filterBy == self.SEARCH_TYPE_VENDOR:
            return device.vendor == self._vendorCombo.get_active_text()
        elif filterBy == self.SEARCH_TYPE_INTERCONNECT:
            return device.bus == self._icCombo.get_active_text()
        elif filterBy == self.SEARCH_TYPE_ID:
            for link in device.device_links:
                if "by-path" in link:
                    return self._idEntry.get_text().strip() in link

            return False

    def visible_func(self, model, itr, *args):
        obj = DiskStoreRow(*model[itr])
        device = self.storage.devicetree.get_device_by_name(obj.name, hidden=True)
        return self.ismember(device) and self._filter_func(device)

class ZPage(FilterPage):
    # Match these to zTypeCombo ids in glade
    SEARCH_TYPE_NONE = 'None'
    SEARCH_TYPE_CCW = 'CCW'
    SEARCH_TYPE_WWPN = 'WWPN'
    SEARCH_TYPE_LUN = 'LUN'

    def __init__(self, storage, builder):
        super().__init__(storage, builder)
        self.model = self.builder.get_object("zModel")
        self.model.set_visible_func(self.visible_func)

        self._ccwEntry = self.builder.get_object("zCCWEntry")
        self._wwpnEntry = self.builder.get_object("zWWPNEntry")
        self._lunEntry = self.builder.get_object("zLUNEntry")
        self._combo = self.builder.get_object("zTypeCombo")

        self._isS390 = arch.is_s390()

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

            self._combo.set_active_id(self.SEARCH_TYPE_NONE)
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
                                  "", "", disk.fcp_lun, disk.hba_id, disk.wwpn, "", ""])

    def _filter_func(self, device):
        if not self.filterActive:
            return True

        filterBy = self._combo.get_active_id()

        if filterBy == self.SEARCH_TYPE_NONE:
            return True
        elif filterBy == self.SEARCH_TYPE_CCW:
            return self._ccwEntry.get_text() in device.hba_id
        elif filterBy == self.SEARCH_TYPE_WWPN:
            return self._wwpnEntry.get_text() in device.wwpn
        elif filterBy == self.SEARCH_TYPE_LUN:
            return self._lunEntry.get_text() in device.fcp_lun

        return False

    def visible_func(self, model, itr, *args):
        obj = DiskStoreRow(*model[itr])
        device = self.storage.devicetree.get_device_by_name(obj.name, hidden=True)
        return self.ismember(device) and self._filter_func(device)

class NvdimmPage(FilterPage):
    # Match these to nvdimmTypeCombo ids in glade
    SEARCH_TYPE_NONE = 'None'
    SEARCH_TYPE_NAMESPACE = 'Namespace'
    SEARCH_TYPE_MODE = 'Mode'

    def __init__(self, storage, builder):
        FilterPage.__init__(self, storage, builder)
        self.model = self.builder.get_object("nvdimmModel")
        self.treeview = self.builder.get_object("nvdimmTreeView")
        self.model.set_visible_func(self.visible_func)

        self._combo = self.builder.get_object("nvdimmTypeCombo")
        self._modeCombo = self.builder.get_object("nvdimmModeCombo")
        self._namespaceEntry = self.builder.get_object("nvdimmNamespaceEntry")

    def ismember(self, device):
        return isinstance(device, NVDIMMNamespaceDevice)

    def setup(self, store, selectedNames, disks):
        modes = []

        for disk in disks:
            paths = [d.name for d in disk.parents]
            selected = disk.name in selectedNames
            mutable = not disk.protected

            if disk.mode != "sector":
                mutable = False
                selected = False

            store.append([True, selected, mutable,
                          disk.name, "", disk.model, str(disk.size),
                          disk.vendor, disk.bus, disk.serial,
                          self._long_identifier(disk), "\n".join(paths), "", "",
                          "", "", "", disk.devname, disk.mode])

            if not disk.mode in modes:
                modes.append(disk.mode)

        self._combo.set_active_id(self.SEARCH_TYPE_NONE)
        self._combo.emit("changed")

        self.setupCombo(self._modeCombo, modes)

    def clear(self):
        self._modeCombo.set_active(0)
        self._namespaceEntry.set_text("")

    def _filter_func(self, device):
        if not self.filterActive:
            return True

        filterBy = self._combo.get_active_id()

        if filterBy == self.SEARCH_TYPE_NONE:
            return True
        elif filterBy == self.SEARCH_TYPE_MODE:
            return device.mode == self._modeCombo.get_active_text()
        elif filterBy == self.SEARCH_TYPE_NAMESPACE:
            ns = self._namespaceEntry.get_text().strip()
            return device.devname == ns

    def visible_func(self, model, itr, *args):
        obj = DiskStoreRow(*model[itr])
        device = self.storage.devicetree.get_device_by_name(obj.name, hidden=True)
        return self.ismember(device) and self._filter_func(device)

    def get_selected_namespaces(self):
        namespaces = []
        selection = self.treeview.get_selection()
        store, pathlist = selection.get_selected_rows()
        for path in pathlist:
            store_row = DiskStoreRow(*store[store.get_iter(path)])
            namespaces.append(store_row.namespace)

        return namespaces

class FilterSpoke(NormalSpoke):
    """
       .. inheritance-diagram:: FilterSpoke
          :parts: 3
    """
    builderObjects = ["diskStore", "filterWindow",
                      "searchModel", "multipathModel", "otherModel", "zModel", "nvdimmModel"]
    mainWidgetName = "filterWindow"
    uiFile = "spokes/advanced_storage.glade"
    helpFile = "FilterSpoke.xml"

    category = SystemCategory

    title = CN_("GUI|Spoke", "_INSTALLATION DESTINATION")

    def __init__(self, *args):
        super().__init__(*args)
        self.applyOnSkip = True

        self.ancestors = []
        self.disks = []
        self.selected_disks = []

        self._reconfigureNVDIMMButton = self.builder.get_object("reconfigureNVDIMMButton")

    @property
    def indirect(self):
        return True

    # This spoke has no status since it's not in a hub
    @property
    def status(self):
        return None

    def apply(self):
        applyDiskSelection(self.storage, self.data, self.selected_disks)

        # some disks may have been added in this spoke, we need to recreate the
        # snapshot of on-disk storage
        if on_disk_storage.created:
            on_disk_storage.dispose_snapshot()
        on_disk_storage.create_snapshot(self.storage)

    def initialize(self):
        super().initialize()
        self.initialize_start()

        self.pages = {
            PAGE_SEARCH: SearchPage(self.storage, self.builder),
            PAGE_MULTIPATH: MultipathPage(self.storage, self.builder),
            PAGE_OTHER: OtherPage(self.storage, self.builder),
            PAGE_NVDIMM: NvdimmPage(self.storage, self.builder),
            PAGE_Z: ZPage(self.storage, self.builder),
        }

        self._notebook = self.builder.get_object("advancedNotebook")

        if not arch.is_s390():
            self._notebook.remove_page(-1)
            self.builder.get_object("addZFCPButton").destroy()
            self.builder.get_object("addDASDButton").destroy()

        if not has_fcoe():
            self.builder.get_object("addFCOEButton").destroy()

        if not iscsi.available:
            self.builder.get_object("addISCSIButton").destroy()


        self._store = self.builder.get_object("diskStore")
        self._addDisksButton = self.builder.get_object("addDisksButton")

        # The button is sensitive only on NVDIMM page
        self._reconfigureNVDIMMButton.set_sensitive(False)

        # report that we are done
        self.initialize_done()

    def _real_ancestors(self, disk):
        # Return a list of all the ancestors of a disk, but remove the disk
        # itself from this list.
        return [d for d in disk.ancestors if d.name != disk.name]

    def refresh(self):
        super().refresh()

        self.disks = getDisks(self.storage.devicetree)

        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        self.selected_disks = disk_select_proxy.SelectedDisks

        self.ancestors = [d.name for disk in self.disks for d in self._real_ancestors(disk)]

        self._store.clear()

        allDisks = []
        multipathDisks = []
        otherDisks = []
        nvdimmDisks = []
        zDisks = []

        # Now all all the non-local disks to the store.  Everything has been set up
        # ahead of time, so there's no need to configure anything.  We first make
        # these lists of disks, then call setup on each individual page.  This is
        # because there could be page-specific setup to do that requires a complete
        # view of all the disks on that page.
        for disk in self.disks:
            if self.pages[PAGE_MULTIPATH].ismember(disk):
                multipathDisks.append(disk)
            elif self.pages[PAGE_OTHER].ismember(disk):
                otherDisks.append(disk)
            elif self.pages[PAGE_NVDIMM].ismember(disk):
                nvdimmDisks.append(disk)
            elif self.pages[PAGE_Z].ismember(disk):
                zDisks.append(disk)

            allDisks.append(disk)

        self.pages[PAGE_SEARCH].setup(self._store, self.selected_disks, allDisks)
        self.pages[PAGE_MULTIPATH].setup(self._store, self.selected_disks, multipathDisks)
        self.pages[PAGE_OTHER].setup(self._store, self.selected_disks, otherDisks)
        self.pages[PAGE_NVDIMM].setup(self._store, self.selected_disks, nvdimmDisks)
        self.pages[PAGE_Z].setup(self._store, self.selected_disks, zDisks)

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
        super().on_back_clicked(button)

    def on_summary_clicked(self, button):
        dialog = SelectedDisksDialog(self.data)

        # Include any disks selected in the initial storage spoke, plus any
        # selected in this filter UI.
        disks = [disk for disk in self.disks if disk.name in self.selected_disks]
        free_space = self.storage.get_free_space(disks=disks)

        with self.main_window.enlightbox(dialog.window):
            dialog.refresh(disks, free_space, showRemove=False, setBoot=False)
            dialog.run()

    @timed_action(delay=1200, busy_cursor=False)
    def on_filter_changed(self, *args):
        n = self._notebook.get_current_page()
        self.pages[n].filterActive = True
        self.pages[n].model.refilter()

    def on_clear_icon_clicked(self, entry, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            entry.set_text("")

    def on_page_switched(self, notebook, newPage, newPageNum, *args):
        self.pages[newPageNum].model.refilter()
        notebook.get_nth_page(newPageNum).show_all()
        self._reconfigureNVDIMMButton.set_sensitive(newPageNum == 3)

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
        try_populate_devicetree(self.storage.devicetree)
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

    def on_reconfigure_nvdimm_clicked(self, widget, *args):
        namespaces = self.pages[PAGE_NVDIMM].get_selected_namespaces()
        dialog = NVDIMMDialog(self.data, self.storage, namespaces)

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

        notebook.set_current_page(ndx)
        self.on_filter_changed()

    ##
    ## MULTIPATH TAB SIGNAL HANDLERS
    ##
    def on_multipath_type_changed(self, combo):
        ndx = combo.get_active()

        notebook = self.builder.get_object("multipathTypeNotebook")

        notebook.set_current_page(ndx)
        self.on_filter_changed()

    ##
    ## OTHER TAB SIGNAL HANDLERS
    ##
    def on_other_type_combo_changed(self, combo):
        ndx = combo.get_active()

        notebook = self.builder.get_object("otherTypeNotebook")

        notebook.set_current_page(ndx)
        self.on_filter_changed()

    ##
    ## NVDIMM TAB SIGNAL HANDLERS
    ##
    def on_nvdimm_type_combo_changed(self, combo):
        ndx = combo.get_active()

        notebook = self.builder.get_object("nvdimmTypeNotebook")

        notebook.set_current_page(ndx)
        self.on_filter_changed()

    ##
    ## Z TAB SIGNAL HANDLERS
    ##
    def on_z_type_combo_changed(self, combo):
        ndx = combo.get_active()

        notebook = self.builder.get_object("zTypeNotebook")

        notebook.set_current_page(ndx)
        self.on_filter_changed()
