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
from collections import namedtuple

from blivet.devices import DASDDevice, FcoeDiskDevice, iScsiDiskDevice, MultipathDevice, \
    ZFCPDiskDevice, NVDIMMNamespaceDevice

from pyanaconda.flags import flags
from pyanaconda.core.i18n import CN_, CP_
from pyanaconda.storage.utils import filter_disks_by_names
from pyanaconda.ui.lib.storage import apply_disk_selection, try_populate_devicetree
from pyanaconda.storage.snapshot import on_disk_storage
from pyanaconda.modules.common.constants.objects import DISK_SELECTION, FCOE, ISCSI, DASD
from pyanaconda.modules.common.constants.services import STORAGE

from pyanaconda.ui.gui.utils import timed_action
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.advstorage.fcoe import FCoEDialog
from pyanaconda.ui.gui.spokes.advstorage.iscsi import ISCSIDialog
from pyanaconda.ui.gui.spokes.advstorage.zfcp import ZFCPDialog
from pyanaconda.ui.gui.spokes.advstorage.dasd import DASDDialog
from pyanaconda.ui.gui.spokes.advstorage.nvdimm import NVDIMMDialog
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.categories.system import SystemCategory

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

__all__ = ["FilterSpoke"]

PAGE_SEARCH = 0
PAGE_MULTIPATH = 1
PAGE_OTHER = 2
PAGE_NVDIMM = 3
PAGE_Z = 4

DiskStoreRow = namedtuple("DiskStoreRow", [
    "visible", "selected", "mutable",
    "name", "type", "model", "capacity",
    "vendor", "interconnect", "serial",
    "wwid", "paths", "port", "target",
    "lun", "ccw", "wwpn", "namespace", "mode"
])


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
    # Default value of a type combo.
    SEARCH_TYPE_NONE = 'None'

    def __init__(self, storage, builder, model_name, combo_name):
        """Create a new FilterPage instance.

        :param storage: an instance of the storage object
        :param builder: a instance of the Gtk.Builder
        :param model_name: a name of the filter model
        :param combo_name: a name of the type combo
        """
        self._builder = builder
        self._storage = storage
        self._is_active = False

        self._model = self._builder.get_object(model_name)
        self._model.set_visible_func(self.visible_func)

        self._combo = self._builder.get_object(combo_name)

    @property
    def model(self):
        """The model."""
        return self._model

    @property
    def is_active(self):
        """Is the filter active?"""
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        self._is_active = value

    def is_member(self, device):
        """Does device belong on this page?  This function should taken into
           account what kind of thing device is.  It should not be concerned
           with any sort of filtering settings.  It only determines whether
           device belongs.
        """
        return True

    def setup(self, store, selected_names, disks):
        """Do whatever setup of the UI is necessary before this page can be
           displayed.  This function is called every time the filter spoke
           is revisited, and thus must first do any cleanup that is necessary.

           The setup function is passed a reference to the master store, a list
           of names of disks the user has selected (either from a previous visit
           or via kickstart), and a list of all disk objects that belong on this
           page as determined from the is_member method.

           At the least, this method should add all the disks to the store.  It
           may also need to populate combos and other lists as appropriate.
        """
        pass

    def _setup_combo(self, combo, items):
        """Populate a given GtkComboBoxText instance with a list of items.

        The combo will first be cleared, so this method is suitable for calling
        repeatedly. The first item in the list will be empty to allow the combo
        box criterion to be cleared. The first non-empty item in the list will
        be selected by default.
        """
        combo.remove_all()
        combo.append_text('')

        for i in sorted(set(items)):
            combo.append_text(i)

        if items:
            combo.set_active(1)

    def _setup_search_type(self):
        """Set up the default search type."""
        self._combo.set_active_id(self.SEARCH_TYPE_NONE)
        self._combo.emit("changed")

    def clear(self):
        """Blank out any filtering-related fields on this page and return them
           to their defaults.  This is called when the Clear button is clicked.
        """
        pass

    def visible_func(self, model, itr, *args):
        """This method is called for every row (disk) in the store, in order to
           determine if it should be displayed on this page or not.  This method
           should take into account whether is_active is set, perhaps whether
           something in pyanaconda.flags is setup, and other settings to make
           a final decision.  Because filtering can be complicated, many pages
           will want to farm this decision out to another method.

           The return value is a boolean indicating whether the row is visible
           or not.
        """
        if not self._is_active:
            return True

        row = DiskStoreRow(*model[itr])
        device = self._storage.devicetree.get_device_by_name(row.name, hidden=True)

        if not self.is_member(device):
            return False

        filter_by = self._combo.get_active_id()
        if filter_by == self.SEARCH_TYPE_NONE:
            return True

        return self._filter_func(filter_by, device)

    def _filter_func(self, filter_by, device):
        """Filter a row by the specified filter."""
        return True


class SearchPage(FilterPage):
    # Match these to searchTypeCombo ids in glade
    SEARCH_TYPE_PORT_TARGET_LUN = 'PTL'
    SEARCH_TYPE_WWID = 'WWID'

    def __init__(self, storage, builder):
        super().__init__(storage, builder, "searchModel", "searchTypeCombo")
        self._lun_entry = self._builder.get_object("searchLUNEntry")
        self._wwid_entry = self._builder.get_object("searchWWIDEntry")
        self._port_combo = self._builder.get_object("searchPortCombo")
        self._target_entry = self._builder.get_object("searchTargetEntry")

    def setup(self, store, selected_names, disks):
        ports = []

        for disk in disks:
            if hasattr(disk, "port") and disk.port is not None:
                ports.append(str(disk.port))

        self._setup_combo(self._port_combo, ports)
        self._setup_search_type()

    def clear(self):
        self._lun_entry.set_text("")
        self._port_combo.set_active(0)
        self._target_entry.set_text("")
        self._wwid_entry.set_text("")

    def _port_equal(self, device):
        active = self._port_combo.get_active_text()
        if active:
            if hasattr(device, "port"):
                return device.port == int(active)
            else:
                return False

        return True

    def _target_equal(self, device):
        active = self._target_entry.get_text().strip()
        if active:
            return active in getattr(device, "initiator", "")

        return True

    def _lun_equal(self, device):
        active = self._lun_entry.get_text().strip()
        if active:
            if hasattr(device, "lun"):
                try:
                    return int(active) == device.lun
                except ValueError:
                    return False
            elif hasattr(device, "fcp_lun"):
                return active in device.fcp_lun
        else:
            return True

    def _wwid_equal(self, device):
        active = self._wwid_entry.get_text().strip()
        if active:
            if hasattr(device, "wwn"):
                return active in device.wwn
            elif hasattr(device, "id_path"):
                return active in device.id_path
            else:
                return active in device.name
        else:
            return True

    def _filter_func(self, filter_by, device):
        if filter_by == self.SEARCH_TYPE_PORT_TARGET_LUN:
            return self._port_equal(device) \
                   and self._target_equal(device) \
                   and self._lun_equal(device)

        if filter_by == self.SEARCH_TYPE_WWID:
            return self._wwid_equal(device)

        return False


class MultipathPage(FilterPage):
    # Match these to multipathTypeCombo ids in glade
    SEARCH_TYPE_VENDOR = 'Vendor'
    SEARCH_TYPE_INTERCONNECT = 'Interconnect'
    SEARCH_TYPE_WWID = 'WWID'

    def __init__(self, storage, builder):
        super().__init__(storage, builder, "multipathModel", "multipathTypeCombo")
        self._ic_combo = self._builder.get_object("multipathInterconnectCombo")
        self._vendor_combo = self._builder.get_object("multipathVendorCombo")
        self._wwid_entry = self._builder.get_object("multipathWWIDEntry")

    def is_member(self, device):
        return isinstance(device, MultipathDevice)

    def setup(self, store, selected_names, disks):
        vendors = []
        interconnects = []

        for disk in disks:
            paths = [d.name for d in disk.parents]
            selected = disk.name in selected_names

            store.append([
                True, selected, not disk.protected,
                disk.name, "", disk.model, str(disk.size),
                disk.vendor, disk.bus, disk.serial,
                disk.wwn, "\n".join(paths), "", "",
                "", "", "", "", ""
            ])

            if disk.vendor not in vendors:
                vendors.append(disk.vendor)

            if disk.bus not in interconnects:
                interconnects.append(disk.bus)

        self._setup_combo(self._vendor_combo, vendors)
        self._setup_combo(self._ic_combo, interconnects)
        self._setup_search_type()

    def clear(self):
        self._ic_combo.set_active(0)
        self._vendor_combo.set_active(0)
        self._wwid_entry.set_text("")

    def _filter_func(self, filter_by, device):
        if filter_by == self.SEARCH_TYPE_VENDOR:
            return device.vendor == self._vendor_combo.get_active_text()

        if filter_by == self.SEARCH_TYPE_INTERCONNECT:
            return device.bus == self._ic_combo.get_active_text()

        if filter_by == self.SEARCH_TYPE_WWID:
            return self._wwid_entry.get_text() in device.wwn

        return False

    def visible_func(self, model, itr, *args):
        if not flags.mpath:
            return False

        return super().visible_func(model, itr, *args)


class OtherPage(FilterPage):
    # Match these to otherTypeCombo ids in glade
    SEARCH_TYPE_VENDOR = 'Vendor'
    SEARCH_TYPE_INTERCONNECT = 'Interconnect'
    SEARCH_TYPE_ID = 'ID'

    def __init__(self, storage, builder):
        super().__init__(storage, builder, "otherModel", "otherTypeCombo")
        self._ic_combo = self._builder.get_object("otherInterconnectCombo")
        self._id_entry = self._builder.get_object("otherIDEntry")
        self._vendor_combo = self._builder.get_object("otherVendorCombo")

    def is_member(self, device):
        return isinstance(device, iScsiDiskDevice) or isinstance(device, FcoeDiskDevice)

    def setup(self, store, selected_names, disks):
        vendors = []
        interconnects = []

        for disk in disks:
            paths = [d.name for d in disk.parents]
            selected = disk.name in selected_names

            port = getattr(disk, "port", "")
            lun = str(getattr(disk, "lun", ""))
            target = getattr(disk, "target", "")

            store.append([
                True, selected, not disk.protected,
                disk.name, "", disk.model, str(disk.size),
                disk.vendor, disk.bus, disk.serial,
                disk.id_path or disk.name, "\n".join(paths), port, target,
                lun, "", "", "", ""
            ])

            if disk.vendor not in vendors:
                vendors.append(disk.vendor)

            if disk.bus not in interconnects:
                interconnects.append(disk.bus)

        self._setup_combo(self._vendor_combo, vendors)
        self._setup_combo(self._ic_combo, interconnects)
        self._setup_search_type()

    def clear(self):
        self._ic_combo.set_active(0)
        self._id_entry.set_text("")
        self._vendor_combo.set_active(0)

    def _filter_func(self, filter_by, device):
        if filter_by == self.SEARCH_TYPE_VENDOR:
            return device.vendor == self._vendor_combo.get_active_text()

        if filter_by == self.SEARCH_TYPE_INTERCONNECT:
            return device.bus == self._ic_combo.get_active_text()

        if filter_by == self.SEARCH_TYPE_ID:
            for link in device.device_links:
                if "by-path" in link:
                    return self._id_entry.get_text().strip() in link

        return False


class ZPage(FilterPage):
    # Match these to zTypeCombo ids in glade
    SEARCH_TYPE_CCW = 'CCW'
    SEARCH_TYPE_WWPN = 'WWPN'
    SEARCH_TYPE_LUN = 'LUN'

    def __init__(self, storage, builder):
        super().__init__(storage, builder, "zModel", "zTypeCombo")
        self._ccw_entry = self._builder.get_object("zCCWEntry")
        self._wwpn_entry = self._builder.get_object("zWWPNEntry")
        self._lun_entry = self._builder.get_object("zLUNEntry")

    def clear(self):
        self._lun_entry.set_text("")
        self._ccw_entry.set_text("")
        self._wwpn_entry.set_text("")

    def is_member(self, device):
        return isinstance(device, ZFCPDiskDevice) or isinstance(device, DASDDevice)

    def setup(self, store, selected_names, disks):
        """ Set up our Z-page, but only if we're running on s390x. """
        ccws = []
        wwpns = []
        luns = []

        for disk in disks:
            paths = [d.name for d in disk.parents]
            selected = disk.name in selected_names

            if getattr(disk, "type") != "zfcp":
                continue

            # remember to store all of the zfcp-related junk so we can
            # see it in the UI
            if disk.fcp_lun not in luns:
                luns.append(disk.fcp_lun)
            if disk.wwpn not in wwpns:
                wwpns.append(disk.wwpn)
            if disk.hba_id not in ccws:
                ccws.append(disk.hba_id)

            store.append([
                True, selected, not disk.protected,
                disk.name, "", disk.model, str(disk.size),
                disk.vendor, disk.bus, disk.serial, "", "\n".join(paths),
                "", "", disk.fcp_lun, disk.hba_id, disk.wwpn, "", ""
            ])

        self._setup_search_type()

    def _filter_func(self, filter_by, device):
        if filter_by == self.SEARCH_TYPE_CCW:
            return self._ccw_entry.get_text() in device.hba_id

        if filter_by == self.SEARCH_TYPE_WWPN:
            return self._wwpn_entry.get_text() in device.wwpn

        if filter_by == self.SEARCH_TYPE_LUN:
            return self._lun_entry.get_text() in device.fcp_lun

        return False


class NvdimmPage(FilterPage):
    # Match these to nvdimmTypeCombo ids in glade
    SEARCH_TYPE_NAMESPACE = 'Namespace'
    SEARCH_TYPE_MODE = 'Mode'

    def __init__(self, storage, builder):
        super().__init__(storage, builder, "nvdimmModel", "nvdimmTypeCombo")
        self._tree_view = self._builder.get_object("nvdimmTreeView")
        self._mode_combo = self._builder.get_object("nvdimmModeCombo")
        self._namespace_entry = self._builder.get_object("nvdimmNamespaceEntry")

    def is_member(self, device):
        return isinstance(device, NVDIMMNamespaceDevice)

    def setup(self, store, selected_names, disks):
        modes = []

        for disk in disks:
            paths = [d.name for d in disk.parents]
            selected = disk.name in selected_names
            mutable = not disk.protected

            if disk.mode != "sector":
                mutable = False
                selected = False

            store.append([
                True, selected, mutable,
                disk.name, "", disk.model, str(disk.size),
                disk.vendor, disk.bus, disk.serial,
                disk.id_path or disk.name, "\n".join(paths), "", "",
                "", "", "", disk.devname, disk.mode
            ])

            if disk.mode not in modes:
                modes.append(disk.mode)

        self._setup_combo(self._mode_combo, modes)
        self._setup_search_type()

    def clear(self):
        self._mode_combo.set_active(0)
        self._namespace_entry.set_text("")

    def _filter_func(self, filter_by, device):
        if filter_by == self.SEARCH_TYPE_MODE:
            return device.mode == self._mode_combo.get_active_text()

        if filter_by == self.SEARCH_TYPE_NAMESPACE:
            ns = self._namespace_entry.get_text().strip()
            return device.devname == ns

        return False

    def get_selected_namespaces(self):
        namespaces = []
        selection = self._tree_view.get_selection()
        store, path_list = selection.get_selected_rows()

        for path in path_list:
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

    title = CN_("GUI|Spoke", "_Installation Destination")

    def __init__(self, *args):
        super().__init__(*args)
        self.applyOnSkip = True

        self._pages = {}
        self._ancestors = []
        self._disks = []
        self._selected_disks = []

        self._disk_selection = STORAGE.get_proxy(DISK_SELECTION)

        self._notebook = self.builder.get_object("advancedNotebook")
        self._store = self.builder.get_object("diskStore")
        self._reconfigure_nvdimm_button = self.builder.get_object("reconfigureNVDIMMButton")

    @property
    def indirect(self):
        return True

    # This spoke has no status since it's not in a hub
    @property
    def status(self):
        return None

    def apply(self):
        apply_disk_selection(self._selected_disks)

        # some disks may have been added in this spoke, we need to recreate the
        # snapshot of on-disk storage
        if on_disk_storage.created:
            on_disk_storage.dispose_snapshot()
        on_disk_storage.create_snapshot(self.storage)

    def initialize(self):
        super().initialize()
        self.initialize_start()

        self._pages = {
            PAGE_SEARCH: SearchPage(self.storage, self.builder),
            PAGE_MULTIPATH: MultipathPage(self.storage, self.builder),
            PAGE_OTHER: OtherPage(self.storage, self.builder),
            PAGE_NVDIMM: NvdimmPage(self.storage, self.builder),
            PAGE_Z: ZPage(self.storage, self.builder),
        }

        if not STORAGE.get_proxy(DASD).IsSupported():
            self._notebook.remove_page(PAGE_Z)
            self._pages.pop(PAGE_Z)
            self.builder.get_object("addZFCPButton").destroy()
            self.builder.get_object("addDASDButton").destroy()

        if not STORAGE.get_proxy(FCOE).IsSupported():
            self.builder.get_object("addFCOEButton").destroy()

        if not STORAGE.get_proxy(ISCSI).IsSupported():
            self.builder.get_object("addISCSIButton").destroy()

        # The button is sensitive only on NVDIMM page
        self._reconfigure_nvdimm_button.set_sensitive(False)

        # report that we are done
        self.initialize_done()

    def _real_ancestors(self, disk):
        # Return a list of all the ancestors of a disk, but remove the disk
        # itself from this list.
        return [d for d in disk.ancestors if d.name != disk.name]

    def refresh(self):
        super().refresh()
        self._disks = self.storage.usable_disks
        self._selected_disks = self._disk_selection.SelectedDisks

        self._ancestors = [
            d.name for disk in self._disks
            for d in self._real_ancestors(disk)
        ]

        # Now all all the non-local disks to the store.  Everything has been set up
        # ahead of time, so there's no need to configure anything.  We first make
        # these lists of disks, then call setup on each individual page.  This is
        # because there could be page-specific setup to do that requires a complete
        # view of all the disks on that page.
        self._store.clear()

        for page in self._pages.values():
            page.setup(
                self._store,
                self._selected_disks,
                list(filter(page.is_member, self._disks)),
            )

        self._update_summary()

    def _update_summary(self):
        summary_button = self.builder.get_object("summary_button")
        label = self.builder.get_object("summary_button_label")

        # We need to remove ancestor devices from the count.  Otherwise, we'll
        # end up in a situation where selecting one multipath device could
        # potentially show three devices selected (mpatha, sda, sdb for instance).
        count = len([
            disk for disk in self._selected_disks
            if disk not in self._ancestors
        ])

        summary = CP_(
            "GUI|Installation Destination|Filter",
            "{} _storage device selected",
            "{} _storage devices selected",
            count
        ).format(count)

        label.set_text(summary)
        label.set_use_underline(True)

        summary_button.set_visible(count > 0)
        label.set_sensitive(count > 0)

    def on_back_clicked(self, button):
        self.skipTo = "StorageSpoke"
        super().on_back_clicked(button)

    def on_summary_clicked(self, button):
        disks = filter_disks_by_names(
            self._disks, self._selected_disks
        )
        dialog = SelectedDisksDialog(
            self.data, self.storage, disks, show_remove=False, set_boot=False
        )

        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

    @timed_action(delay=1200, busy_cursor=False)
    def on_filter_changed(self, *args):
        n = self._notebook.get_current_page()
        self._pages[n].is_active = True
        self._pages[n].model.refilter()

    def on_clear_icon_clicked(self, entry, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            entry.set_text("")

    def on_page_switched(self, notebook, new_page, new_page_num, *args):
        self._pages[new_page_num].model.refilter()
        notebook.get_nth_page(new_page_num).show_all()
        self._reconfigure_nvdimm_button.set_sensitive(new_page_num == 3)

    def on_row_toggled(self, button, path):
        if not path:
            return

        page_index = self._notebook.get_current_page()
        filter_model = self._pages[page_index].model
        model_itr = filter_model.get_iter(path)
        itr = filter_model.convert_iter_to_child_iter(model_itr)
        self._store[itr][1] = not self._store[itr][1]

        if self._store[itr][1] and self._store[itr][3] not in self._selected_disks:
            self._selected_disks.append(self._store[itr][3])
        elif not self._store[itr][1] and self._store[itr][3] in self._selected_disks:
            self._selected_disks.remove(self._store[itr][3])

        self._update_summary()

    @timed_action(delay=50, threshold=100)
    def on_refresh_clicked(self, widget, *args):
        try_populate_devicetree()
        self.refresh()

    def on_add_iscsi_clicked(self, widget, *args):
        dialog = ISCSIDialog(self.data)
        self._run_dialog_and_refresh(dialog)

    def on_add_fcoe_clicked(self, widget, *args):
        dialog = FCoEDialog(self.data)
        self._run_dialog_and_refresh(dialog)

    def on_add_zfcp_clicked(self, widget, *args):
        dialog = ZFCPDialog(self.data)
        self._run_dialog_and_refresh(dialog)

    def on_add_dasd_clicked(self, widget, *args):
        dialog = DASDDialog(self.data)
        self._run_dialog_and_refresh(dialog)

    def on_reconfigure_nvdimm_clicked(self, widget, *args):
        namespaces = self._pages[PAGE_NVDIMM].get_selected_namespaces()
        dialog = NVDIMMDialog(self.data, namespaces)
        self._run_dialog_and_refresh(dialog)

    def _run_dialog_and_refresh(self, dialog):
        # Run the dialog.
        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

        # We now need to refresh so any new disks picked up by adding advanced
        # storage are displayed in the UI.
        self.refresh()

    def on_search_type_changed(self, combo):
        self._set_notebook_page("searchTypeNotebook", combo.get_active())

    def on_multipath_type_changed(self, combo):
        self._set_notebook_page("multipathTypeNotebook", combo.get_active())

    def on_other_type_combo_changed(self, combo):
        self._set_notebook_page("otherTypeNotebook", combo.get_active())

    def on_nvdimm_type_combo_changed(self, combo):
        self._set_notebook_page("nvdimmTypeNotebook", combo.get_active())

    def on_z_type_combo_changed(self, combo):
        self._set_notebook_page("zTypeNotebook", combo.get_active())

    def _set_notebook_page(self, notebook_name, page_index):
        notebook = self.builder.get_object(notebook_name)
        notebook.set_current_page(page_index)
        self.on_filter_changed()
