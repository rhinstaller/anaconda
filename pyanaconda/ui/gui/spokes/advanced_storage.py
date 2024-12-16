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

from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import CN_, CP_
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.ui.lib.storage import apply_disk_selection, try_populate_devicetree, \
    filter_disks_by_names
from pyanaconda.modules.common.constants.objects import DISK_SELECTION, FCOE, ISCSI, DASD, \
    DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE

from pyanaconda.ui.gui.utils import timed_action, really_show, really_hide
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.advstorage.fcoe import FCoEDialog
from pyanaconda.ui.gui.spokes.advstorage.iscsi import ISCSIDialog
from pyanaconda.ui.gui.spokes.advstorage.zfcp import ZFCPDialog
from pyanaconda.ui.gui.spokes.advstorage.dasd import DASDDialog
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.categories.system import SystemCategory

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

log = get_module_logger(__name__)

__all__ = ["FilterSpoke"]

PAGE_SEARCH = 0
PAGE_MULTIPATH = 1
PAGE_OTHER = 2
PAGE_NVMEFABRICS = 3
PAGE_Z = 4
# The Z page must be last = highest number, because it is dynamically removed, which would reorder
# the items and invalidate the indices hardcoded here.

DiskStoreRow = namedtuple("DiskStoreRow", [
    "visible", "selected", "mutable",
    "name", "device_id", "type", "model", "capacity",
    "vendor", "interconnect", "serial",
    "wwid", "paths", "port", "target",
    "lun", "ccw", "wwpn", "namespace", "mode",
    "controllers", "transport", "transport_address",
    "subsystem_nqn", "namespace_id"
])


def create_row(device_data, selected, mutable):
    """Create a disk store row for the given data.

    :param device_data: an instance of DeviceData
    :param selected: True if the device is selected, otherwise False
    :param mutable: False if the device is protected, otherwise True
    :return: an instance of DiskStoreRow
    """
    device = device_data
    attrs = device_data.attrs

    controller_ids = attrs.get("controllers-id", "").split(", ")
    transports_type = attrs.get("transports-type", "").split(", ")
    transports_address = attrs.get("transports-address", "").split(", ")
    subsystems_nqn = attrs.get("subsystems-nqn", "").split(", ")
    namespace_ids = list(filter(None, map(attrs.get, ["eui64", "nguid", "uuid"])))

    return DiskStoreRow(
        visible=True,
        selected=selected,
        mutable=mutable and not device.protected,
        name=device.name,
        device_id=device.device_id,
        type=device.type,
        model=attrs.get("model", ""),
        capacity=str(Size(device.size)),
        vendor=attrs.get("vendor", ""),
        interconnect=attrs.get("bus", ""),
        serial=attrs.get("serial", ""),
        wwid=attrs.get("path-id", ""),
        paths="\n".join(device.parents),
        port=attrs.get("port", ""),
        target=attrs.get("target", ""),
        lun=attrs.get("lun", "") or attrs.get("fcp-lun", ""),
        ccw=attrs.get("hba-id", ""),
        wwpn=attrs.get("wwpn", ""),
        namespace=attrs.get("namespace", "") or attrs.get("nsid", ""),
        mode=attrs.get("mode", ""),
        controllers="\n".join(controller_ids),
        transport="\n".join(transports_type),
        transport_address="\n".join(transports_address),
        subsystem_nqn="\n".join(subsystems_nqn),
        namespace_id="\n".join(namespace_ids),
    )


class FilterPage:
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

    def __init__(self, builder, model_name, combo_name):
        """Create a new FilterPage instance.

        :param builder: a instance of the Gtk.Builder
        :param model_name: a name of the filter model
        :param combo_name: a name of the type combo
        """
        self._builder = builder
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

    def is_member(self, device_type):
        """Does device belong on this page?  This function should taken into
           account what kind of thing device is.  It should not be concerned
           with any sort of filtering settings.  It only determines whether
           device belongs.
        """
        return True

    def setup(self, store, disks, selected_names, protected_names):
        """Do whatever setup of the UI is necessary before this page can be
           displayed.  This function is called every time the filter spoke
           is revisited, and thus must first do any cleanup that is necessary.

           The setup function is passed a reference to the primary store, a list
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

        # Remove duplicate and empty items and sort them.
        items = sorted(set(filter(None, items)))

        for i in items:
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
        if not self.is_member(row.type):
            return False

        log.debug("Filter %s with %s.", row.name, str(self))

        filter_by = self._combo.get_active_id()
        if filter_by == self.SEARCH_TYPE_NONE:
            return True

        return self._filter_func(filter_by, row)

    def _filter_func(self, filter_by, row):
        """Filter a row by the specified filter."""
        return True

    def __str__(self):
        """Get the name of the filter."""
        return self.__class__.__name__


class SearchPage(FilterPage):
    # Match these to searchTypeCombo ids in glade
    SEARCH_TYPE_PORT_TARGET_LUN = 'PTL'
    SEARCH_TYPE_WWID = 'WWID'

    def __init__(self, builder):
        super().__init__(builder, "searchModel", "searchTypeCombo")
        self._lun_entry = self._builder.get_object("searchLUNEntry")
        self._wwid_entry = self._builder.get_object("searchWWIDEntry")
        self._port_combo = self._builder.get_object("searchPortCombo")
        self._target_entry = self._builder.get_object("searchTargetEntry")

    def setup(self, store, disks, selected_names, protected_names):
        ports = set()

        for device_data in disks:
            ports.add(device_data.attrs.get("port"))

        self._setup_combo(self._port_combo, ports)
        self._setup_search_type()

    def clear(self):
        self._lun_entry.set_text("")
        self._port_combo.set_active(0)
        self._target_entry.set_text("")
        self._wwid_entry.set_text("")

    def _filter_func(self, filter_by, row):
        if filter_by == self.SEARCH_TYPE_PORT_TARGET_LUN:
            port = self._port_combo.get_active_text()
            if port and port != row.port:
                return False

            target = self._target_entry.get_text().strip()
            if target and target not in row.target:
                return False

            lun = self._lun_entry.get_text().strip()
            if lun and lun not in row.lun:
                return False

            return True

        if filter_by == self.SEARCH_TYPE_WWID:
            return self._wwid_entry.get_text() in row.wwid

        return False


class MultipathPage(FilterPage):
    # Match these to multipathTypeCombo ids in glade
    SEARCH_TYPE_VENDOR = 'Vendor'
    SEARCH_TYPE_INTERCONNECT = 'Interconnect'
    SEARCH_TYPE_WWID = 'WWID'

    def __init__(self, builder):
        super().__init__(builder, "multipathModel", "multipathTypeCombo")
        self._ic_combo = self._builder.get_object("multipathInterconnectCombo")
        self._vendor_combo = self._builder.get_object("multipathVendorCombo")
        self._wwid_entry = self._builder.get_object("multipathWWIDEntry")

    def is_member(self, device_type):
        return device_type == "dm-multipath"

    def setup(self, store, disks, selected_names, protected_names):
        vendors = set()
        interconnects = set()

        for device_data in disks:
            row = create_row(
                device_data,
                device_data.name in selected_names,
                device_data.name not in protected_names
            )

            store.append(list(row))
            vendors.add(device_data.attrs.get("vendor"))
            interconnects.add(device_data.attrs.get("bus"))

        self._setup_combo(self._vendor_combo, vendors)
        self._setup_combo(self._ic_combo, interconnects)
        self._setup_search_type()

    def clear(self):
        self._ic_combo.set_active(0)
        self._vendor_combo.set_active(0)
        self._wwid_entry.set_text("")

    def _filter_func(self, filter_by, row):
        if filter_by == self.SEARCH_TYPE_VENDOR:
            return row.vendor == self._vendor_combo.get_active_text()

        if filter_by == self.SEARCH_TYPE_INTERCONNECT:
            return row.interconnect == self._ic_combo.get_active_text()

        if filter_by == self.SEARCH_TYPE_WWID:
            return self._wwid_entry.get_text() in row.wwid

        return False


class OtherPage(FilterPage):
    # Match these to otherTypeCombo ids in glade
    SEARCH_TYPE_VENDOR = 'Vendor'
    SEARCH_TYPE_INTERCONNECT = 'Interconnect'
    SEARCH_TYPE_ID = 'ID'

    def __init__(self, builder):
        super().__init__(builder, "otherModel", "otherTypeCombo")
        self._ic_combo = self._builder.get_object("otherInterconnectCombo")
        self._id_entry = self._builder.get_object("otherIDEntry")
        self._vendor_combo = self._builder.get_object("otherVendorCombo")

    def is_member(self, device_type):
        return device_type in ("iscsi", "fcoe")

    def setup(self, store, disks, selected_names, protected_names):
        vendors = set()
        interconnects = set()

        for device_data in disks:
            row = create_row(
                device_data,
                device_data.name in selected_names,
                device_data.name not in protected_names
            )

            store.append([*row])
            vendors.add(device_data.attrs.get("vendor"))
            interconnects.add(device_data.attrs.get("bus"))

        self._setup_combo(self._vendor_combo, vendors)
        self._setup_combo(self._ic_combo, interconnects)
        self._setup_search_type()

    def clear(self):
        self._ic_combo.set_active(0)
        self._id_entry.set_text("")
        self._vendor_combo.set_active(0)

    def _filter_func(self, filter_by, row):
        if filter_by == self.SEARCH_TYPE_VENDOR:
            return self._vendor_combo.get_active_text() == row.vendor

        if filter_by == self.SEARCH_TYPE_INTERCONNECT:
            return self._ic_combo.get_active_text() == row.interconnect

        if filter_by == self.SEARCH_TYPE_ID:
            return self._id_entry.get_text().strip() in row.wwid

        return False


class ZPage(FilterPage):
    # Match these to zTypeCombo ids in glade
    SEARCH_TYPE_CCW = 'CCW'
    SEARCH_TYPE_WWPN = 'WWPN'
    SEARCH_TYPE_LUN = 'LUN'

    def __init__(self, builder):
        super().__init__(builder, "zModel", "zTypeCombo")
        self._ccw_entry = self._builder.get_object("zCCWEntry")
        self._wwpn_entry = self._builder.get_object("zWWPNEntry")
        self._lun_entry = self._builder.get_object("zLUNEntry")

    def clear(self):
        self._lun_entry.set_text("")
        self._ccw_entry.set_text("")
        self._wwpn_entry.set_text("")

    def is_member(self, device_type):
        return device_type in ("zfcp", "dasd")

    def setup(self, store, disks, selected_names, protected_names):
        """ Set up our Z-page, but only if we're running on s390x. """
        for device_data in disks:
            if device_data.type != "zfcp":
                continue

            row = create_row(
                device_data,
                device_data.name in selected_names,
                device_data.name not in protected_names
            )

            store.append([*row])

        self._setup_search_type()

    def _filter_func(self, filter_by, row):
        if filter_by == self.SEARCH_TYPE_CCW:
            return self._ccw_entry.get_text() in row.ccw

        if filter_by == self.SEARCH_TYPE_WWPN:
            return self._wwpn_entry.get_text() in row.wwpn

        if filter_by == self.SEARCH_TYPE_LUN:
            return self._lun_entry.get_text() in row.lun

        return False


class NVMeFabricsPage(FilterPage):
    # Match these to nvmefTypeCombo ids in glade
    SEARCH_TYPE_CONTROLLER = 'Controller'
    SEARCH_TYPE_TRANSPORT = 'Transport'
    SEARCH_TYPE_SUBSYSTEM_NQN = 'Subsystem NQN'
    SEARCH_TYPE_NAMESPACE_ID = 'Namespace ID'

    def __init__(self, builder):
        super().__init__(builder, "nvmefModel", "nvmefTypeCombo")
        self._controller_entry = self._builder.get_object("nvmefControllerEntry")
        self._transport_combo = self._builder.get_object("nvmefTransportCombo")
        self._address_entry = self._builder.get_object("nvmefTransportAddressEntry")
        self._subsystem_nqn_entry = self._builder.get_object("nvmefSubsystemNqnEntry")
        self._namespace_id_entry = self._builder.get_object("nvmefNamespaceIdEntry")

    def is_member(self, device_type):
        return device_type == "nvme-fabrics"

    def setup(self, store, disks, selected_names, protected_names):
        transports = set()

        for device_data in disks:
            row = create_row(
                device_data,
                device_data.name in selected_names,
                device_data.name not in protected_names,
            )
            store.append([*row])
            transports.update(row.transport.split("\n"))

        self._setup_combo(self._transport_combo, transports)
        self._transport_combo.set_active(0)
        self._setup_search_type()

    def clear(self):
        self._controller_entry.set_text("")
        self._transport_combo.set_active(0)
        self._address_entry.set_text("")
        self._subsystem_nqn_entry.set_text("")
        self._namespace_id_entry.set_text("")

    def _filter_func(self, filter_by, row):
        if filter_by == self.SEARCH_TYPE_CONTROLLER:
            return self._controller_entry.get_text().strip() in row.controllers

        if filter_by == self.SEARCH_TYPE_TRANSPORT:
            transports = [""] + row.transport.split("\n")

            return self._transport_combo.get_active_text() in transports \
                and self._address_entry.get_text().strip() in row.transport_address

        if filter_by == self.SEARCH_TYPE_SUBSYSTEM_NQN:
            return self._subsystem_nqn_entry.get_text().strip() in row.subsystem_nqn

        if filter_by == self.SEARCH_TYPE_NAMESPACE_ID:
            return self._namespace_id_entry.get_text().strip() in row.namespace_id

        return False


class FilterSpoke(NormalSpoke):
    """
       .. inheritance-diagram:: FilterSpoke
          :parts: 3
    """
    builderObjects = ["diskStore", "filterWindow",
                      "searchModel", "multipathModel", "otherModel", "zModel", "nvmefModel"]
    mainWidgetName = "filterWindow"
    uiFile = "spokes/advanced_storage.glade"
    category = SystemCategory
    title = CN_("GUI|Spoke", "_Installation Destination")

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "storage-advanced-configuration"

    def __init__(self, *args):
        super().__init__(*args)
        self.applyOnSkip = True

        self._pages = {}
        self._ancestors = []
        self._disks = []
        self._selected_disks = []
        self._protected_disks = []

        self._storage_module = STORAGE.get_proxy()
        self._device_tree = STORAGE.get_proxy(DEVICE_TREE)
        self._disk_selection = STORAGE.get_proxy(DISK_SELECTION)

        self._notebook = self.builder.get_object("advancedNotebook")
        self._store = self.builder.get_object("diskStore")

    @property
    def indirect(self):
        return True

    # This spoke has no status since it's not in a hub
    @property
    def status(self):
        return None

    def apply(self):
        apply_disk_selection(self._selected_disks)

    def initialize(self):
        super().initialize()
        self.initialize_start()

        self._pages = {
            PAGE_SEARCH: SearchPage(self.builder),
            PAGE_MULTIPATH: MultipathPage(self.builder),
            PAGE_OTHER: OtherPage(self.builder),
            PAGE_NVMEFABRICS: NVMeFabricsPage(self.builder),
            PAGE_Z: ZPage(self.builder),
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

        # report that we are done
        self.initialize_done()

    def refresh(self):
        super().refresh()

        # Reset the scheduled partitioning if any to make sure that we
        # are working with the current system's storage configuration.
        # FIXME: Change modules and UI to work with the right device tree.
        self._storage_module.ResetPartitioning()

        self._disks = self._disk_selection.GetUsableDisks()
        self._selected_disks = self._disk_selection.SelectedDisks
        self._protected_disks = self._disk_selection.ProtectedDevices
        self._ancestors = self._device_tree.GetAncestors(self._disks)

        # Now all all the non-local disks to the store.  Everything has been set up
        # ahead of time, so there's no need to configure anything.  We first make
        # these lists of disks, then call setup on each individual page.  This is
        # because there could be page-specific setup to do that requires a complete
        # view of all the disks on that page.
        self._store.clear()

        disks_data = DeviceData.from_structure_list([
            self._device_tree.GetDeviceData(device_id)
            for device_id in self._disks
        ])

        for page in self._pages.values():
            disks = [
                d for d in disks_data
                if page.is_member(d.type)
            ]

            page.setup(
                self._store,
                disks,
                self._selected_disks,
                self._protected_disks
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

        if count > 0:
            really_show(summary_button)
            label.set_text(summary)
            label.set_use_underline(True)
        else:
            really_hide(summary_button)

    def on_back_clicked(self, button):
        self.skipTo = "StorageSpoke"
        super().on_back_clicked(button)

    def on_summary_clicked(self, button):
        disks = filter_disks_by_names(
            self._disks, self._selected_disks
        )
        dialog = SelectedDisksDialog(
            self.data, disks, show_remove=False, set_boot=False
        )

        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

    def on_clear_icon_clicked(self, entry, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            entry.set_text("")

    def on_page_switched(self, notebook, _new_page, new_page_num, *args):
        # Disable all filters.
        for page in self._pages.values():
            page.is_active = False

        # Set up the new page.
        page = self._pages[new_page_num]
        page.is_active = True
        page.model.refilter()

        log.debug("Show the page %s.", str(page))

        # Set up the UI.
        notebook.get_nth_page(new_page_num).show_all()

    def on_row_toggled(self, button, path):
        if not path:
            return

        page_index = self._notebook.get_current_page()
        filter_model = self._pages[page_index].model
        model_itr = filter_model.get_iter(path)
        itr = filter_model.convert_iter_to_child_iter(model_itr)
        self._store[itr][1] = not self._store[itr][1]

        if self._store[itr][1] and self._store[itr][4] not in self._selected_disks:
            self._selected_disks.append(self._store[itr][4])
        elif not self._store[itr][1] and self._store[itr][4] in self._selected_disks:
            self._selected_disks.remove(self._store[itr][4])

        self._update_summary()

    @timed_action(delay=50, threshold=100)
    def on_refresh_clicked(self, widget, *args):
        log.debug("Refreshing...")
        try_populate_devicetree()
        self.refresh()

    def on_add_iscsi_clicked(self, widget, *args):
        log.debug("Add a new iSCSI device.")
        dialog = ISCSIDialog(self.data)
        self._run_dialog_and_refresh(dialog)

    def on_add_fcoe_clicked(self, widget, *args):
        log.debug("Add a new FCoE device.")
        dialog = FCoEDialog(self.data)
        self._run_dialog_and_refresh(dialog)

    def on_add_zfcp_clicked(self, widget, *args):
        log.debug("Add a new zFCP device.")
        dialog = ZFCPDialog(self.data)
        self._run_dialog_and_refresh(dialog)

    def on_add_dasd_clicked(self, widget, *args):
        log.debug("Add a new DASD device.")
        dialog = DASDDialog(self.data)
        self._run_dialog_and_refresh(dialog)

    def _run_dialog_and_refresh(self, dialog):
        # Run the dialog.
        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

        # We now need to refresh so any new disks picked up by adding advanced
        # storage are displayed in the UI.
        self.refresh()

    @timed_action(delay=1200, busy_cursor=False)
    def on_filter_changed(self, *args):
        self._refilter_current_page()

    def on_search_type_changed(self, combo):
        self._set_notebook_page("searchTypeNotebook", combo.get_active())
        self._refilter_current_page()

    def on_multipath_type_changed(self, combo):
        self._set_notebook_page("multipathTypeNotebook", combo.get_active())
        self._refilter_current_page()

    def on_other_type_combo_changed(self, combo):
        self._set_notebook_page("otherTypeNotebook", combo.get_active())
        self._refilter_current_page()

    def on_z_type_combo_changed(self, combo):
        self._set_notebook_page("zTypeNotebook", combo.get_active())
        self._refilter_current_page()

    def on_nvmef_type_combo_changed(self, combo):
        self._set_notebook_page("nvmefTypeNotebook", combo.get_active())
        self._refilter_current_page()

    def _set_notebook_page(self, notebook_name, page_index):
        notebook = self.builder.get_object(notebook_name)
        notebook.set_current_page(page_index)
        self._refilter_current_page()

    def _refilter_current_page(self):
        index = self._notebook.get_current_page()
        page = self._pages[index]
        page.model.refilter()
