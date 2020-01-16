#
# Custom partitioning classes.
#
# Copyright (C) 2012-2014  Red Hat, Inc.
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

# TODO:
# - Deleting an LV is not reflected in available space in the bottom left.
#   - this is only true for preexisting LVs
# - Device descriptions, suggested sizes, etc. should be moved out into a support file.
# - Tabbing behavior in the accordion is weird.
# - Implement striping and mirroring for LVM.
# - Activating reformat should always enable resize for existing devices.
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("AnacondaWidgets", "3.3")

from gi.repository import Gdk, Gtk
from gi.repository.AnacondaWidgets import MountpointSelector

from blivet import devicefactory
from blivet.devicefactory import DEVICE_TYPE_BTRFS, SIZE_POLICY_AUTO
from blivet.devicelibs import raid, crypto
from blivet.devices import MDRaidArrayDevice, LVMVolumeGroupDevice
from blivet.errors import StorageError
from blivet.formats import get_format
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from dasbus.structure import generate_dictionary_from_data, compare_data
from pyanaconda.core.constants import THREAD_EXECUTE_STORAGE, THREAD_STORAGE, \
    SIZE_UNITS_DEFAULT, DEFAULT_AUTOPART_TYPE
from pyanaconda.core.i18n import _, N_, CP_, C_
from pyanaconda.modules.common.constants.objects import BOOTLOADER, DISK_SELECTION
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.configuration import BootloaderConfigurationError, \
    StorageConfigurationError
from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.modules.common.structures.device_factory import DeviceFactoryRequest
from pyanaconda.modules.storage.partitioning.interactive.interactive_partitioning import \
    InteractiveAutoPartitioningTask
from pyanaconda.modules.storage.partitioning.interactive.utils import collect_unused_devices, \
    collect_new_devices, collect_selected_disks, collect_roots, create_new_root, \
    collect_file_system_types, collect_device_types, get_device_raid_level, destroy_device, \
    rename_container, get_container, collect_containers, suggest_device_name, get_new_root_name, \
    generate_device_factory_request, validate_device_factory_request, \
    get_device_factory_arguments, get_raid_level_by_name, get_container_size_policy_by_number, \
    generate_device_factory_permissions
from pyanaconda.modules.storage.partitioning.interactive.add_device import AddDeviceTask
from pyanaconda.modules.storage.partitioning.interactive.change_device import ChangeDeviceTask
from pyanaconda.platform import platform
from pyanaconda.product import productName, productVersion
from pyanaconda.storage.checker import verify_luks_devices_have_key, storage_checker
from pyanaconda.storage.execution import configure_storage
from pyanaconda.storage.initialization import reset_bootloader
from pyanaconda.storage.root import find_existing_installations
from pyanaconda.storage.utils import DEVICE_TEXT_MAP, MOUNTPOINT_DESCRIPTIONS, NAMED_DEVICE_TYPES, \
    CONTAINER_DEVICE_TYPES, device_type_from_autopart, filter_unsupported_disklabel_devices, \
    unlock_device, setup_passphrase, find_unconfigured_luks, DEVICE_TYPE_UNSUPPORTED
from pyanaconda.threading import threadMgr
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.accordion import update_selector_from_device, Accordion, Page, \
    CreateNewPage, UnknownPage
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.gui.spokes.lib.custom_storage_helpers import get_size_from_entry, \
    get_selected_raid_level, \
    get_raid_level_selection, get_default_raid_level, get_supported_container_raid_levels, \
    get_container_type, \
    get_default_container_raid_level, AddDialog, ConfirmDeleteDialog, \
    DisksDialog, ContainerDialog, NOTEBOOK_LABEL_PAGE, NOTEBOOK_DETAILS_PAGE, NOTEBOOK_LUKS_PAGE, \
    NOTEBOOK_UNEDITABLE_PAGE, NOTEBOOK_INCOMPLETE_PAGE, NEW_CONTAINER_TEXT, CONTAINER_TOOLTIP, \
    ui_storage_logger, ui_storage_logged, get_selected_raid_level_name, \
    get_supported_device_raid_levels
from pyanaconda.ui.gui.spokes.lib.passphrase import PassphraseDialog
from pyanaconda.ui.gui.spokes.lib.refresh import RefreshDialog
from pyanaconda.ui.gui.spokes.lib.summary import ActionSummaryDialog
from pyanaconda.ui.gui.utils import setViewportBackground, fancy_set_sensitive, ignoreEscape, \
    really_hide, really_show, timed_action, escape_markup
from pyanaconda.ui.helpers import StorageCheckHandler

log = get_module_logger(__name__)

__all__ = ["CustomPartitioningSpoke"]


class CustomPartitioningSpoke(NormalSpoke, StorageCheckHandler):
    """
       .. inheritance-diagram:: CustomPartitioningSpoke
          :parts: 3
    """
    builderObjects = ["customStorageWindow", "containerStore", "deviceTypeStore",
                      "partitionStore", "raidStoreFiltered", "raidLevelStore",
                      "addImage", "removeImage", "settingsImage",
                      "mountPointCompletion", "mountPointStore", "fileSystemStore",
                      "luksVersionStore"]
    mainWidgetName = "customStorageWindow"
    uiFile = "spokes/custom_storage.glade"
    helpFile = "CustomSpoke.xml"

    category = SystemCategory
    title = N_("MANUAL PARTITIONING")

    # The maximum number of places to show when displaying a size
    MAX_SIZE_PLACES = 2

    # If the user enters a smaller size, the GUI changes it to this value
    MIN_SIZE_ENTRY = Size("1 MiB")

    def __init__(self, data, storage, payload):
        StorageCheckHandler.__init__(self)
        NormalSpoke.__init__(self, data, storage, payload)

        self._back_already_clicked = False
        self._storage_playground = None

        self.passphrase = ""
        self._error = None
        self._partitioning_scheme = DEFAULT_AUTOPART_TYPE

        self._device_disks = []
        self._device_name = ""
        self._device_type = None
        self._device_suggested_name = ""
        self._device_container_name = None
        self._device_container_raid_level = None
        self._device_container_encrypted = False
        self._device_container_size = SIZE_POLICY_AUTO

        self._initialized = False
        self._accordion = None

        self._bootloader_module = STORAGE.get_proxy(BOOTLOADER)
        self._disk_select_module = STORAGE.get_proxy(DISK_SELECTION)

    def apply(self):
        self.clear_errors()

        # Make sure that the protected disks are visible again.
        self._storage_playground.show_protected_disks()

        # Make sure any device/passphrase pairs we've obtained are remembered.
        setup_passphrase(self.storage, self.passphrase)

        hubQ.send_ready("StorageSpoke", True)

    @property
    def indirect(self):
        return True

    # This spoke has no status since it's not in a hub
    @property
    def status(self):
        return None

    def _grab_objects(self):
        self._partitionsViewport = self.builder.get_object("partitionsViewport")
        self._partitionsNotebook = self.builder.get_object("partitionsNotebook")

        # Connect partitionsNotebook focus events to scrolling in the parent viewport
        partitions_notebook_viewport = self.builder.get_object("partitionsNotebookViewport")
        self._partitionsNotebook.set_focus_vadjustment(
            Gtk.Scrollable.get_vadjustment(partitions_notebook_viewport))

        self._pageLabel = self.builder.get_object("pageLabel")

        self._availableSpaceLabel = self.builder.get_object("availableSpaceLabel")
        self._totalSpaceLabel = self.builder.get_object("totalSpaceLabel")
        self._summaryLabel = self.builder.get_object("summary_label")

        # Buttons
        self._addButton = self.builder.get_object("addButton")
        self._applyButton = self.builder.get_object("applyButton")
        self._configButton = self.builder.get_object("configureButton")
        self._removeButton = self.builder.get_object("removeButton")
        self._resetButton = self.builder.get_object("resetButton")

        # Detailed configuration stuff
        self._encryptCheckbox = self.builder.get_object("encryptCheckbox")
        self._fsCombo = self.builder.get_object("fileSystemTypeCombo")
        self._fsStore = self.builder.get_object("fileSystemStore")
        self._luksCombo = self.builder.get_object("luksVersionCombo")
        self._luksStore = self.builder.get_object("luksVersionStore")
        self._luksLabel = self.builder.get_object("luksVersionLabel")
        self._labelEntry = self.builder.get_object("labelEntry")
        self._mountPointEntry = self.builder.get_object("mountPointEntry")
        self._nameEntry = self.builder.get_object("nameEntry")
        self._raidLevelCombo = self.builder.get_object("raidLevelCombo")
        self._raidLevelLabel = self.builder.get_object("raidLevelLabel")
        self._reformatCheckbox = self.builder.get_object("reformatCheckbox")
        self._sizeEntry = self.builder.get_object("sizeEntry")
        self._typeStore = self.builder.get_object("deviceTypeStore")
        self._typeCombo = self.builder.get_object("deviceTypeCombo")
        self._modifyContainerButton = self.builder.get_object("modifyContainerButton")
        self._containerCombo = self.builder.get_object("containerCombo")
        self._containerStore = self.builder.get_object("containerStore")
        self._deviceDescLabel = self.builder.get_object("deviceDescLabel")

        # Set the fixed-size properties on the volume group ComboBox renderers to
        # False so that the "Create a new..." row can overlap with the free space
        # on the other rows. These properties are not accessible from glade.
        cell_area = self._containerCombo.get_area()
        desc_renderer = self.builder.get_object("descRenderer")
        free_space_renderer = self.builder.get_object("freeSpaceRenderer")
        cell_area.cell_set_property(desc_renderer, "fixed-size", False)
        cell_area.cell_set_property(free_space_renderer, "fixed-size", False)

        self._passphraseEntry = self.builder.get_object("passphraseEntry")

        # Stores
        self._raidStoreFilter = self.builder.get_object("raidStoreFiltered")

        # Labels
        self._selectedDeviceLabel = self.builder.get_object("selectedDeviceLabel")
        self._selectedDeviceDescLabel = self.builder.get_object("selectedDeviceDescLabel")
        self._encryptedDeviceLabel = self.builder.get_object("encryptedDeviceLabel")
        self._encryptedDeviceDescLabel = self.builder.get_object("encryptedDeviceDescriptionLabel")
        self._incompleteDeviceLabel = self.builder.get_object("incompleteDeviceLabel")
        self._incompleteDeviceDescLabel = self.builder.get_object(
            "incompleteDeviceDescriptionLabel")
        self._incompleteDeviceOptionsLabel = self.builder.get_object(
            "incompleteDeviceOptionsLabel")
        self._uneditableDeviceLabel = self.builder.get_object("uneditableDeviceLabel")
        self._uneditableDeviceDescLabel = self.builder.get_object(
            "uneditableDeviceDescriptionLabel")
        self._containerLabel = self.builder.get_object("containerLabel")

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()
        self._grab_objects()

        setViewportBackground(self.builder.get_object("availableSpaceViewport"), "#db3279")
        setViewportBackground(self.builder.get_object("totalSpaceViewport"), "#60605b")

        self._raidStoreFilter.set_visible_func(self._raid_level_visible)

        self._accordion = Accordion()
        self._partitionsViewport.add(self._accordion)

        # Connect viewport scrolling with accordion focus events
        self._accordion.set_focus_hadjustment(
            Gtk.Scrollable.get_hadjustment(self._partitionsViewport))
        self._accordion.set_focus_vadjustment(
            Gtk.Scrollable.get_vadjustment(self._partitionsViewport))

        self.initialize_done()

    @property
    def _new_root_name(self):
        return get_new_root_name()

    def _get_selected_disks(self):
        return collect_selected_disks(
            storage=self._storage_playground,
            selection=self._disk_select_module.SelectedDisks
        )

    def _get_selected_disk_names(self):
        return [d.name for d in self._get_selected_disks()]

    def _get_unused_devices(self):
        return collect_unused_devices(self._storage_playground)

    @property
    def _bootloader_drive(self):
        return self._bootloader_module.Drive

    def _get_new_devices(self):
        return collect_new_devices(
            storage=self._storage_playground,
            boot_drive=self._bootloader_drive
        )

    def _update_space_display(self):
        # Set up the free space/available space displays in the bottom left.
        disks = self._get_selected_disks()
        free_space = self._storage_playground.get_disk_free_space()
        total_space = sum((d.size for d in disks), Size(0))

        self._availableSpaceLabel.set_text(str(free_space))
        self._totalSpaceLabel.set_text(str(total_space))

        count = len(disks)
        summary = CP_("GUI|Custom Partitioning",
                      "%d _storage device selected",
                      "%d _storage devices selected",
                      count) % count

        self._summaryLabel.set_text(summary)
        self._summaryLabel.set_use_underline(True)

    @ui_storage_logged
    def _reset_storage(self):
        self._storage_playground = self.storage.copy()
        self._storage_playground.hide_protected_disks()

    def refresh(self):
        self.clear_errors()
        NormalSpoke.refresh(self)

        # Make sure the storage spoke execute method has finished before we
        # copy the storage instance.
        for thread_name in [THREAD_EXECUTE_STORAGE, THREAD_STORAGE]:
            threadMgr.wait(thread_name)

        self._back_already_clicked = False

        self._reset_storage()
        self._do_refresh()

        self._update_space_display()
        self._applyButton.set_sensitive(False)

    def _get_container_names(self):
        for data in self._containerStore:
            yield data[0]

    def _get_file_system_type(self):
        itr = self._fsCombo.get_active_iter()
        if not itr:
            return None

        model = self._fsCombo.get_model()
        return model[itr][1]

    def _get_autopart_type(self, autopart_type_combo):
        itr = autopart_type_combo.get_active_iter()
        if not itr:
            return DEFAULT_AUTOPART_TYPE

        model = autopart_type_combo.get_model()
        return model[itr][1]

    def _change_autopart_type(self, autopart_type_combo):
        """
        This is called when the autopart type combo on the left hand side of
        custom partitioning is changed.  We already know how to handle the case
        where the user changes the type and then clicks the autopart link
        button.  This handles the case where the user changes the type and then
        clicks the '+' button.

        """
        self._partitioning_scheme = self._get_autopart_type(autopart_type_combo)

    def _set_page_label_text(self):
        if self._accordion.is_multiselection:
            select_tmpl = _("%(items_selected)s of %(items_total)s mount points in %(page_name)s")
            span_tmpl = "<span size='large' weight='bold' fgcolor='%s'>%s</span>"
            pages_count = ""
            for page in self._accordion.all_pages:
                if not page.members:
                    continue

                if page.selected_members:
                    highlight_color = "black"
                    page_text_tmpl = select_tmpl
                else:
                    highlight_color = "gray"
                    page_text_tmpl = "<span fgcolor='gray'>%s</span>" % escape_markup(select_tmpl)

                selected_str = span_tmpl % (escape_markup(highlight_color),
                                            escape_markup(str(len(page.selected_members))))
                total_str = span_tmpl % (escape_markup(highlight_color),
                                         escape_markup(str(len(page.members))))
                page_name = span_tmpl % (escape_markup(highlight_color),
                                         escape_markup(page.pageTitle))

                page_line = page_text_tmpl % {"items_selected": selected_str,
                                              "items_total": total_str,
                                              "page_name": page_name}
                pages_count += page_line + "\n"

            self._pageLabel.set_markup(
                _("Please select a single mount point to edit properties.\n\n"
                  "You have currently selected:\n"
                  "%s") % pages_count)
        else:
            self._pageLabel.set_text(
                _("When you create mount points for your %(name)s %(version)s "
                  "installation, you'll be able to view their details here.")
                % {"name": productName, "version": productVersion})

    def _populate_accordion(self):
        # Make sure we start with a clean state.
        self._accordion.remove_all_pages()

        new_devices = filter_unsupported_disklabel_devices(self._get_new_devices())
        all_devices = filter_unsupported_disklabel_devices(self._storage_playground.devices)
        unused_devices = filter_unsupported_disklabel_devices(self._get_unused_devices())

        # Collect the existing roots.
        ui_roots = collect_roots(self._storage_playground)

        # Now it's time to populate the accordion.
        log.debug(
            "Populating accordion for devices %s (unused %s, new %s).",
            [d.name for d in all_devices],
            [d.name for d in unused_devices],
            [d.name for d in new_devices]
        )

        # Add the initial page.
        if not new_devices:
            self._add_initial_page(reuse_existing=bool(ui_roots or unused_devices))
        else:
            new_root = create_new_root(self._storage_playground, self._bootloader_drive)
            ui_roots.insert(0, new_root)

        # Add root pages.
        for root in ui_roots:
            self._add_root_page(root)

        # Add the unknown page.
        if unused_devices:
            self._add_unknown_page(unused_devices)

    def _add_initial_page(self, reuse_existing=False):
        page = CreateNewPage(
            self._new_root_name,
            self.on_create_clicked,
            self._change_autopart_type,
            partitionsToReuse=reuse_existing
        )

        self._accordion.add_page(page, cb=self.on_page_clicked)
        self._partitionsNotebook.set_current_page(NOTEBOOK_LABEL_PAGE)
        self._set_page_label_text()

    def _add_root_page(self, root):
        page = Page(root.name)
        self._accordion.add_page(page, cb=self.on_page_clicked)

        for mountpoint, device in root.mounts.items():
            selector = page.add_selector(
                device,
                self.on_selector_clicked,
                mountpoint=mountpoint
            )

            selector.root = root

        for device in root.swaps:
            selector = page.add_selector(
                device,
                self.on_selector_clicked
            )

            selector.root = root

        page.show_all()

    def _add_unknown_page(self, devices):
        page = UnknownPage(_("Unknown"))
        self._accordion.add_page(page, cb=self.on_page_clicked)

        for u in sorted(devices, key=lambda d: d.name):
            page.add_selector(u, self.on_selector_clicked)

        page.show_all()

    def _do_refresh(self, mountpoint_to_show=None):
        # block mountpoint selector signal handler for now
        self._initialized = False
        self._accordion.clear_current_selector()

        # Start with buttons disabled, since nothing is selected.
        self._removeButton.set_sensitive(False)
        self._configButton.set_sensitive(False)

        # populate the accorion with roots and mount points
        self._populate_accordion()

        # And then open the first page by default.  Most of the time, this will
        # be fine since it'll be the new installation page.
        self._initialized = True
        first_page = self._accordion.all_pages[0]
        self._accordion.expand_page(first_page.pageTitle)
        self._show_mountpoint(page=first_page, mountpoint=mountpoint_to_show)

        self._applyButton.set_sensitive(False)
        self._resetButton.set_sensitive(
            len(self._storage_playground.devicetree.actions.find()) > 0)

    ###
    ### RIGHT HAND SIDE METHODS
    ###
    def _update_selectors(self):
        """ Update all btrfs selectors' size properties. """
        # we're only updating selectors in the new root. problem?
        page = self._accordion.find_page_by_title(self._new_root_name)
        for selector in page.members:
            update_selector_from_device(selector, selector.device)

    def _save_right_side(self, selector):
        """ Save settings from RHS and apply changes to the device.

            This method must never trigger a call to self._do_refresh.
        """
        self.clear_errors()

        # check if initialized and have something to operate on
        if not self._initialized or not selector:
            return

        # only call _save_right_side if on the right page and some changes need
        # to be saved (sensitivity of the Update Settings button reflects that)
        if self._partitionsNotebook.get_current_page() != NOTEBOOK_DETAILS_PAGE or \
                not self._applyButton.get_sensitive():
            return

        device = selector.device
        if device not in self._storage_playground.devices:
            # just-removed device
            return

        self._back_already_clicked = False

        log.debug("Saving the right side for device: %s", device.name)

        # Get the device factory request.
        old_request = generate_device_factory_request(self._storage_playground, device)
        new_request = self._get_new_device_factory_request(device, old_request)

        if compare_data(old_request, new_request):
            log.debug("Nothing to do.")
            return

        # Log the results.
        description = self._get_new_request_description(new_request, old_request)
        log.debug("Device request: %s", description)

        # Validate the device info.
        error = validate_device_factory_request(self._storage_playground, new_request)

        if error:
            log.debug("Validation has failed: %s", error)
            self.set_warning(error)
            self._populate_right_side(selector)
            return

        # Apply the changes.
        self.clear_errors()

        try:
            task = ChangeDeviceTask(self._storage_playground, device, new_request, old_request)
            task.run()
        except StorageError as e:
            log.error("Failed to reconfigure the device: %s", e)
            self.set_detailed_error(_("Device reconfiguration failed."), e)
            self._reset_storage()
            self._do_refresh()
            return

        # Update UI.
        log.debug("The device request changes are applied.")
        self._do_refresh(mountpoint_to_show=new_request.mount_point)

    def _get_new_device_factory_request(self, device, old_request):
        log.info("Getting a new device factory request for %s", device.name)

        new_request = DeviceFactoryRequest()
        new_request.device_spec = device.name

        self._get_new_device_name(new_request, old_request)
        self._get_new_device_size(new_request, old_request)
        self._get_new_device_type(new_request, old_request)
        self._get_new_device_reformat(new_request, old_request)
        self._get_new_device_fstype(new_request, old_request)
        self._get_new_device_enctyption(new_request, old_request)
        self._get_new_device_luks_version(new_request, old_request)
        self._get_new_device_label(new_request, old_request)
        self._get_new_device_mount_point(new_request, old_request)
        self._get_new_device_raid_level(new_request, old_request)
        self._get_new_device_for_btrfs(new_request, old_request)
        self._get_new_device_disks(new_request, old_request)
        self._get_new_device_container(new_request, old_request)

        return new_request

    def _get_new_device_name(self, new_request, old_request):
        if self._nameEntry.get_sensitive():
            new_request.device_name = self._nameEntry.get_text()
        else:
            # name entry insensitive means we don't control the name
            new_request.device_name = ""
            old_request.device_name = ""

    def _get_new_device_size(self, new_request, old_request):
        # If the size text hasn't changed at all from that displayed,
        # assume no change intended.
        device = self._storage_playground.devicetree.resolve_device(new_request.device_spec)
        use_dev = device.raw_device

        size = Size(old_request.device_size)
        displayed_size = size.human_readable(max_places=self.MAX_SIZE_PLACES)

        if (displayed_size != self._sizeEntry.get_text()) \
                and (use_dev.resizable or not use_dev.exists):
            size = get_size_from_entry(
                self._sizeEntry,
                lower_bound=self.MIN_SIZE_ENTRY,
                units=SIZE_UNITS_DEFAULT
            )

        if size:
            new_request.device_size = size.get_bytes()

    def _get_new_device_type(self, new_request, old_request):
        new_request.device_type = self._get_current_device_type()

    def _get_new_device_reformat(self, new_request, old_request):
        new_request.reformat = self._reformatCheckbox.get_active()

    def _get_new_device_fstype(self, new_request, old_request):
        new_request.format_type = self._get_file_system_type()

    def _get_new_device_enctyption(self, new_request, old_request):
        new_request.device_encrypted = (self._encryptCheckbox.get_active()
                                        and self._encryptCheckbox.is_sensitive())

    def _get_new_device_luks_version(self, new_request, old_request):
        luks_version_index = self._luksCombo.get_active()
        luks_version_str = self._luksCombo.get_model()[luks_version_index][0]

        if new_request.device_encrypted:
            new_request.luks_version = luks_version_str

    def _get_new_device_label(self, new_request, old_request):
        new_request.label = self._labelEntry.get_text()

    def _get_new_device_mount_point(self, new_request, old_request):
        if self._mountPointEntry.get_sensitive():
            new_request.mount_point = self._mountPointEntry.get_text()

    def _get_new_device_raid_level(self, new_request, old_request):
        new_request.device_raid_level = get_selected_raid_level_name(self._raidLevelCombo)

    def _get_new_device_for_btrfs(self,  new_request, old_request):
        # FIXME: Move this code to the new methods.
        device = self._storage_playground.devicetree.resolve_device(new_request.device_spec)
        use_dev = device.raw_device

        # If the device is a btrfs volume, the only things we can set/update
        # are mountpoint and container-wide settings.
        if new_request.device_type == DEVICE_TYPE_BTRFS and hasattr(use_dev, "subvolumes"):
            new_request.device_size = 0
            old_request.device_size = 0

            new_request.device_encrypted = False
            old_request.device_encrypted = False

            new_request.device_raid_level = ""
            old_request.device_raid_level = ""

    def _get_new_device_disks(self, new_request, old_request):
        new_request.disks = [d.name for d in self._device_disks]

    def _get_new_device_container(self, new_request, old_request):
        with ui_storage_logger():
            # create a new factory using the appropriate size and type
            names = ("device_type", "size", "disks", "encrypted", "luks_version", "raid_level")
            arguments = get_device_factory_arguments(self._storage_playground, new_request, names)

            factory = devicefactory.get_device_factory(
                self._storage_playground,
                **arguments
            )

        # Name
        if self._device_container_name:
            new_request.container_name = self._device_container_name

        # Encryption
        if self._device_container_encrypted:
            new_request.container_encrypted = True

        # Raid level
        raid_level = self._device_container_raid_level
        supported_raid_levels = get_supported_container_raid_levels(new_request.device_type)
        default_raid_level = get_default_container_raid_level(new_request.device_type)

        if raid_level not in supported_raid_levels:
            raid_level = default_raid_level

        if raid_level:
            new_request.container_raid_level = raid_level.name

        # Size
        if not self._device_container_size:
            new_request.container_size_policy = 0
        elif self._device_container_size < 0:
            new_request.container_size_policy = self._device_container_size
        elif self._device_container_size > 0:
            new_request.container_size_policy = self._device_container_size.get_bytes()

        # Disks
        container = factory.get_container()

        if container and old_request.device_type != new_request.device_type:
            log.debug("Overriding disk set with container's.")
            new_request.disks = [d.name for d in container.disks]

    def _get_new_request_description(self, new_request, old_request):
        new_device_info = generate_dictionary_from_data(new_request)
        old_device_info = generate_dictionary_from_data(old_request)
        attributes = []

        if new_device_info.keys() != old_device_info.keys():
            raise KeyError

        for key in new_device_info.keys():
            if new_device_info[key] == old_device_info[key]:
                attribute = "{} = {}".format(
                    key, repr(new_device_info[key])
                )
            else:
                attribute = "{} = {} -> {}".format(
                    key, repr(old_device_info[key]), repr(new_device_info[key])
                )

            attributes.append(attribute)

        return "\n".join(["{"] + attributes + ["}"])

    def _raid_level_visible(self, model, itr, user_data):
        device_type = self._get_current_device_type()
        raid_level = raid.get_raid_level(model[itr][1])
        return raid_level in get_supported_device_raid_levels(device_type)

    def _populate_raid(self, raid_level):
        """ Set up the raid-specific portion of the device details.

            :param raid_level: RAID level
            :type raid_level: instance of blivet.devicelibs.raid.RAIDLevel or None
        """
        device_type = self._get_current_device_type()

        if not get_supported_device_raid_levels(device_type):
            for widget in [self._raidLevelLabel, self._raidLevelCombo]:
                really_hide(widget)
            return

        raid_level = raid_level or get_default_raid_level(device_type)
        raid_level_name = get_raid_level_selection(raid_level)

        # Set a default RAID level in the combo.
        for (i, row) in enumerate(self._raidLevelCombo.get_model()):
            if row[1] == raid_level_name:
                self._raidLevelCombo.set_active(i)
                break
        for widget in [self._raidLevelLabel, self._raidLevelCombo]:
            really_show(widget)

    def _populate_luks(self, luks_version):
        """Set up the LUKS version combo box.

        :param luks_version: a LUKS version or None
        """
        # Add the values.
        self._luksStore.clear()
        for version in crypto.LUKS_VERSIONS:
            self._luksStore.append([version])

        # Get the selected value.
        luks_version = luks_version or self.storage.default_luks_version

        # Set the selected value.
        idx = next(
            i for i, data in enumerate(self._luksCombo.get_model())
            if data[0] == luks_version
        )
        self._luksCombo.set_active(idx)
        self.on_encrypt_toggled(self._encryptCheckbox)

    def _get_current_device_type(self):
        """ Return integer for type combo selection.

            :returns: the corresponding integer code, a constant in
            blivet.devicefactory.
            :rtype: int or NoneType
        """
        itr = self._typeCombo.get_active_iter()
        if not itr:
            return None

        device_type = self._typeStore[itr][1]
        if device_type == DEVICE_TYPE_UNSUPPORTED:
            return None

        return device_type

    def _setup_fstype_combo(self, device_type, device_format_type, format_types):
        """Setup the filesystem combo box."""
        default_type = device_format_type

        if default_type not in format_types:
            format_types.append(default_type)

        # Add all desired fileystem type names to the box, sorted alphabetically
        self._fsStore.clear()
        for fs_type in format_types:
            fmt = get_format(fs_type)
            self._fsStore.append([fmt.name, fmt.type or ""])

        # set the active filesystem type
        model = self._fsCombo.get_model()
        idx = next(i for i, data in enumerate(model) if data[1] == default_type)
        self._fsCombo.set_active(idx)

        # do additional updating handled by other method
        self._update_fstype_combo(device_type)

    def _setup_device_type_combo(self, device_type, device_types):
        """Set up device type combo."""
        # Include md only if there are two or more disks.
        if len(self._get_selected_disks()) <= 1:
            device_types.remove(devicefactory.DEVICE_TYPE_MD)

        # For existing unsupported device add the information in the UI.
        if device_type not in device_types:
            log.debug("Existing device with unsupported type %s found.", device_type)
            device_type = DEVICE_TYPE_UNSUPPORTED
            device_types.append(device_type)

        # Add values.
        self._typeStore.clear()
        for dt in device_types:
            self._typeStore.append([_(DEVICE_TEXT_MAP[dt]), dt])

        # Set the selected value.
        idx = next(
            i for i, data in enumerate(self._typeCombo.get_model())
            if data[1] == device_type
        )
        self._typeCombo.set_active(idx)

    def _get_device_name(self, device_type):
        """Update the dictionary of device names."""
        if device_type == self._device_type:
            return self._device_name
        elif device_type in NAMED_DEVICE_TYPES:
            return self._device_suggested_name
        else:
            return ""

    def _set_devices_label(self):
        device_disks = self._device_disks
        if not device_disks:
            devices_desc = _("No disks assigned")
        else:
            devices_desc = "%s (%s)" % (device_disks[0].description, device_disks[0].name)
            num_disks = len(device_disks)
            if num_disks > 1:
                devices_desc += CP_("GUI|Custom Partitioning|Devices",
                                    " and %d other", " and %d others",
                                    num_disks - 1) % (num_disks - 1)
        self._deviceDescLabel.set_text(devices_desc)

    def _populate_right_side(self, selector):
        device = selector.device

        request = generate_device_factory_request(self._storage_playground, device)
        permissions = generate_device_factory_permissions(self._storage_playground, request)
        description = self._get_new_request_description(request, request)
        log.debug("Populating the right side for device %s: %s", device.name, description)

        self._device_disks = [
            self._storage_playground.devicetree.resolve_device(d) for d in request.disks
        ]

        self._device_container_name = request.container_name or None
        self._device_container_raid_level = get_raid_level_by_name(request.container_raid_level)
        self._device_container_encrypted = request.container_encrypted
        self._device_container_size = get_container_size_policy_by_number(request.container_size_policy)

        self._device_container_raid_level = \
            self._device_container_raid_level or \
            get_default_container_raid_level(request.device_type)

        self._selectedDeviceLabel.set_text(selector.props.name)
        desc = _(MOUNTPOINT_DESCRIPTIONS.get(selector.props.name, ""))
        self._selectedDeviceDescLabel.set_text(desc)

        self._set_devices_label()

        self._device_name = request.device_name
        self._device_suggested_name = suggest_device_name(self._storage_playground, device)

        self._mountPointEntry.set_text(request.mount_point)
        fancy_set_sensitive(self._mountPointEntry, permissions.mount_point)

        self._labelEntry.set_text(request.label)
        fancy_set_sensitive(self._labelEntry, permissions.label)

        self._sizeEntry.set_text(
            Size(request.device_size).human_readable(max_places=self.MAX_SIZE_PLACES))

        self._reformatCheckbox.set_active(request.reformat)
        fancy_set_sensitive(self._reformatCheckbox, permissions.reformat)

        self._encryptCheckbox.set_active(request.device_encrypted)
        fancy_set_sensitive(self._encryptCheckbox, permissions.device_encrypted)

        if request.container_encrypted:
            # The encryption checkbutton should not be sensitive if there is
            # existing encryption below the leaf layer.
            fancy_set_sensitive(self._encryptCheckbox, False)
            self._encryptCheckbox.set_active(True)
            self._encryptCheckbox.set_tooltip_text(_("The container is encrypted."))
        else:
            self._encryptCheckbox.set_tooltip_text("")

        # Set up the filesystem type combo.
        format_types = collect_file_system_types(device)
        self._setup_fstype_combo(request.device_type, request.format_type, format_types)
        fancy_set_sensitive(self._fsCombo, permissions.format_type)

        # Set up the device type combo.
        device_types = collect_device_types(device)
        self._setup_device_type_combo(request.device_type, device_types)
        fancy_set_sensitive(self._typeCombo, permissions.device_type)

        # FIXME: device encryption should be mutually exclusive with container
        # encryption

        # FIXME: device raid should be mutually exclusive with container raid

        # The size entry is only sensitive for resizable existing devices and
        # new devices that are not btrfs subvolumes.
        # Do this after the device type combo is set since
        # on_device_type_changed doesn't account for device existence.
        fancy_set_sensitive(self._sizeEntry, permissions.device_size)

        if permissions.device_size:
            self._sizeEntry.props.has_tooltip = False
        elif request.format_type == "btrfs":
            self._sizeEntry.set_tooltip_text(_(
                "The space available to this mount point can "
                "be changed by modifying the volume below."
            ))
        else:
            self._sizeEntry.set_tooltip_text(_(
                "This file system may not be resized."
            ))

        self._populate_raid(get_raid_level_by_name(request.device_raid_level))
        fancy_set_sensitive(self._raidLevelCombo, permissions.device_raid_level)

        self._populate_container(device)
        self._populate_luks(request.luks_version)

        self._nameEntry.set_text(self._device_name)
        fancy_set_sensitive(self._nameEntry, permissions.device_name)

    ###
    ### SIGNAL HANDLERS
    ###

    def on_key_pressed(self, widget, event, *args):
        if not event or event and event.type != Gdk.EventType.KEY_RELEASE:
            return

        if event.keyval in [Gdk.KEY_Delete, Gdk.KEY_minus]:
            # But we only want delete to work if you have focused a MountpointSelector,
            # and not just any random widget.  For those, it's likely the user wants
            # to delete a character.
            if isinstance(self.main_window.get_focus(), MountpointSelector):
                self._removeButton.emit("clicked")
        elif event.keyval == Gdk.KEY_plus:
            # And we only want '+' to work if you don't have a text entry focused, since
            # the user might be entering some free-form text that can include a plus.
            if not isinstance(self.main_window.get_focus(), Gtk.Entry):
                self._addButton.emit("clicked")

    def _do_check(self):
        self.clear_errors()
        StorageCheckHandler.errors = []
        StorageCheckHandler.warnings = []

        # We can't overwrite the main Storage instance because all the other
        # spokes have references to it that would get invalidated, but we can
        # achieve the same effect by updating/replacing a few key attributes.
        self.storage.devicetree._devices = self._storage_playground.devicetree._devices
        self.storage.devicetree._actions = self._storage_playground.devicetree._actions
        self.storage.devicetree._hidden = self._storage_playground.devicetree._hidden
        self.storage.roots = self._storage_playground.roots

        # set up bootloader and check the configuration
        bootloader_errors = []
        try:
            configure_storage(self.storage, interactive=True)
        except BootloaderConfigurationError as e:
            bootloader_errors = str(e).split("\n")
            reset_bootloader(self.storage)

        StorageCheckHandler.check_storage(self)

        if self.errors or bootloader_errors:
            self.set_warning(_(
                "Error checking storage configuration. <a href=\"\">Click for details</a> "
                "or press Done again to continue."))
        elif self.warnings:
            self.set_warning(_(
                "Warning checking storage configuration. <a href=\"\">Click for details</a> "
                "or press Done again to continue."))

        # on_info_bar_clicked requires self._error to be set, so set it to the
        # list of all errors and warnings that storage checking found.
        self._error = "\n".join(bootloader_errors + self.errors + self.warnings)

        return self._error == ""

    def on_back_clicked(self, button):
        # Clear any existing errors
        self.clear_errors()

        # Save anything from the currently displayed mountpoint.
        self._save_right_side(self._accordion.current_selector)
        self._applyButton.set_sensitive(False)

        # And then display the summary screen.  From there, the user will either
        # head back to the hub, or stay on the custom screen.
        # If back has been clicked on once already and no other changes made on the screen,
        # run the storage check now.  This handles displaying any errors in the info bar.
        if not self._back_already_clicked:
            self._back_already_clicked = True

            # If we hit any errors while saving things above, stop and let the
            # user think about what they have done
            if self._error is not None:
                return

            if find_unconfigured_luks(self._storage_playground):
                dialog = PassphraseDialog(self.data, default_passphrase=self.passphrase)
                with self.main_window.enlightbox(dialog.window):
                    rc = dialog.run()

                if rc != 1:
                    # Cancel. Leave the old passphrase set if there was one.
                    return

                self.passphrase = dialog.passphrase

            setup_passphrase(self._storage_playground, self.passphrase)

            if not self._do_check():
                return

        self._storage_playground.devicetree.actions.prune()
        self._storage_playground.devicetree.actions.sort()
        actions = self._storage_playground.devicetree.actions.find()

        if actions:
            dialog = ActionSummaryDialog(self.data, actions)
            dialog.refresh()

            with self.main_window.enlightbox(dialog.window):
                rc = dialog.run()

            if rc != 1:
                # Cancel.  Stay on the custom screen.
                return

        NormalSpoke.on_back_clicked(self, button)

    def on_add_clicked(self, button):
        self._save_right_side(self._accordion.current_selector)

        # Initialize and run the AddDialog.
        dialog = AddDialog(self.data, self._storage_playground)
        dialog.refresh()

        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()

            if rc != 1:
                # user cancel
                dialog.window.destroy()
                return

        self._back_already_clicked = False

        # Gather data about the added mount point.
        request = DeviceFactoryRequest()
        request.mount_point = dialog.mount_point

        if dialog.size is None or dialog.size < Size("1 MB"):
            request.device_size = 0
        else:
            request.device_size = dialog.size.get_bytes()

        request.device_type = device_type_from_autopart(self._partitioning_scheme)
        request.disks = self._get_selected_disk_names()

        # Clear errors and try to add the mountpoint/device.
        self.clear_errors()

        try:
            task = AddDeviceTask(self._storage_playground, request)
            task.run()
        except StorageError as e:
            self.set_detailed_error(_("Failed to add new device."), e)
            self._do_refresh()
        else:
            self._do_refresh(mountpoint_to_show=dialog.mount_point)

        self._update_space_display()

    @ui_storage_logged
    def _destroy_device(self, device):
        self.clear_errors()

        try:
            destroy_device(self._storage_playground, device)
            return True
        except StorageError as e:
            log.error("The device removal has failed: %s", e)
            self.set_detailed_warning(_("Device removal request failed."), e)
            return False

    def _show_mountpoint(self, page, mountpoint=None):
        if not self._initialized:
            return

        # Make sure there's something displayed on the RHS.  If a page and
        # mountpoint within that page is given, display that.
        log.debug("Showing mount point: %s", page.pageTitle)

        if not page.members:
            self._accordion.clear_current_selector()
            return

        if not mountpoint and len(self._accordion.selected_items) == 0 \
                and not page.get_parent().get_expanded():
            self._accordion.select(page.members[0])
            self.on_selector_clicked(None, page.members[0])
            return

        if mountpoint:
            for member in page.members:
                if member.get_property("mountpoint").lower() == mountpoint.lower():
                    self._accordion.select(member)
                    self.on_selector_clicked(None, member)
                    break

    def _show_confirmation_dialog(self, root_name, device, protected_types):
        dialog = ConfirmDeleteDialog(self.data)
        bootpart = device.format.type in protected_types
        snapshots = (device.direct and not device.isleaf)
        checkbox_text = None
        if not self._accordion.is_multiselection:
            if root_name and "_" in root_name:
                root_name = root_name.replace("_", "__")

            if root_name:
                checkbox_text = (C_(
                    "GUI|Custom Partitioning|Confirm Delete Dialog",
                    "Delete _all file systems which are only used by %s."
                ) % root_name)
        else:
            checkbox_text = C_(
                "GUI|Custom Partitioning|Confirm Delete Dialog",
                "Do _not show this dialog for other selected file systems."
            )
        dialog.refresh(getattr(device.format, "mountpoint", ""),
                       device.name, checkbox_text=checkbox_text,
                       snapshots=snapshots, bootpart=bootpart)
        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()
            option_checked = dialog.option_checked
            dialog.window.destroy()
            return rc, option_checked

    def on_remove_clicked(self, button):
        # Nothing selected?  Nothing to remove.
        if not self._accordion.is_current_selected and not self._accordion.is_multiselection:
            return

        option_checked = False
        part_removed = False
        is_multiselection = self._accordion.is_multiselection
        protected_types = platform.boot_stage1_constraint_dict["format_types"]
        for selector in self._accordion.selected_items:
            page = self._accordion.page_for_selector(selector)
            device = selector.device
            root_name = None
            if selector.root:
                root_name = selector.root.name
            elif page:
                root_name = page.pageTitle

            log.debug("Removing device %s from page %s.", device.name, root_name)

            if root_name == self._new_root_name:
                if is_multiselection and not option_checked:
                    (rc, option_checked) = self._show_confirmation_dialog(
                        root_name, device, protected_types
                    )

                    if rc != 1:
                        if option_checked:
                            break  # skip evaluation of all other mountpoints
                        continue

                if device.exists:
                    # This is an existing device that was added to the new page.
                    # All we want to do is revert any changes to the device and
                    # it will end up back in whatever old pages it came from.
                    with ui_storage_logger():
                        self._storage_playground.reset_device(device)
                else:
                    # Destroying a non-existing device doesn't require any
                    # confirmation.
                    self._destroy_device(device)
            else:
                # This is a device that exists on disk and most likely has data
                # on it.  Thus, we first need to confirm with the user and then
                # schedule actions to delete the thing.
                # In multiselection user could confirm once for all next
                # selections.
                if not option_checked:
                    (rc, option_checked) = self._show_confirmation_dialog(
                        root_name, device, protected_types
                    )

                    if rc != 1:
                        if option_checked:
                            break  # skip evaluation of all other mountpoints
                        continue

                if option_checked and not is_multiselection:
                    otherpgs = (pg for pg in self._accordion.all_pages
                                if pg is not page)
                    otherdevs = []
                    for otherpg in otherpgs:
                        otherdevs.extend(mem._device.id for mem in otherpg.members)
                    # We never want to delete known-shared devs here.
                    # The same rule applies for selected device. If it's shared do not
                    # remove it in other pages when Delete all option is checked.
                    for dev in (s._device for s in page.members
                                if s._device.id not in otherdevs):
                        # we only want to delete boot partitions if they're not
                        # shared *and* we have no unknown partitions
                        if not self._get_unused_devices() or dev.format.type not in protected_types:
                            self._destroy_device(dev)
                        else:
                            log.debug("Device %s cannot be removed.", dev.name)
                else:
                    self._destroy_device(device)

            part_removed = True

        # Now that devices have been removed from the installation root,
        # refreshing the display will have the effect of making them disappear.
        # It's like they never existed.
        if part_removed:
            self._storage_playground.roots = find_existing_installations(
                self._storage_playground.devicetree)
            self._update_space_display()
            self._do_refresh()

    def on_summary_clicked(self, button):
        disks = self._get_selected_disks()
        dialog = SelectedDisksDialog(self.data, self.storage, disks, show_remove=False,
                                     set_boot=False)

        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

    def on_configure_clicked(self, button):
        selector = self._accordion.current_selector
        if not selector:
            return

        device = selector.device
        if device.exists:
            return

        if self._get_current_device_type() in CONTAINER_DEVICE_TYPES:
            # disk set management happens through container edit on RHS
            return

        self.clear_errors()

        dialog = DisksDialog(
            self.data,
            self._storage_playground,
            disks=self._get_selected_disks(),
            selected=self._device_disks
        )
        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()

        if rc != 1:
            return

        disks = dialog.selected

        if not disks:
            self._error = _("No disks selected. Keeping previous disk set.")
            self.set_info(self._error)
            return

        if set(disks) != self._device_disks:
            self._applyButton.set_sensitive(True)

        self._device_disks = disks
        self._set_devices_label()
        self._populate_raid(get_selected_raid_level(self._raidLevelCombo))

    def _container_encryption_change(self, old_encrypted, new_encrypted):
        if not old_encrypted and new_encrypted:
            # container set to be encrypted, we should make sure the leaf device
            # is not encrypted and make the encryption checkbox insensitive
            self._encryptCheckbox.set_active(False)
            fancy_set_sensitive(self._encryptCheckbox, False)
        elif old_encrypted and not new_encrypted:
            fancy_set_sensitive(self._encryptCheckbox, True)

        self.on_encrypt_toggled(self._encryptCheckbox)

    def run_container_editor(self, container=None, name=None, new_container=False):
        """ Run container edit dialog and return True if changes were made. """
        size = Size(0)
        size_policy = self._device_container_size
        if container:
            container_name = container.name
            size = container.size
            size_policy = container.size_policy
        elif name:
            container_name = name
            if name != self._device_container_name:
                # creating a new container -- switch to the default
                size_policy = SIZE_POLICY_AUTO

        dialog = ContainerDialog(
            self.data,
            self._storage_playground,
            device_type=self._get_current_device_type(),
            name=container_name,
            raid_level=self._device_container_raid_level,
            encrypted=self._device_container_encrypted,
            size_policy=size_policy,
            size=size,
            disks=self._get_selected_disks(),
            selected=self._device_disks,
            exists=getattr(container, "exists", False)
        )

        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()
            dialog.window.destroy()

        if rc != 1:
            return

        disks = dialog.selected
        name = dialog.name

        if not disks:
            self._error = _("No disks selected. Not saving changes.")
            self.set_info(self._error)
            log.error("No disks selected. Not saving changes.")
            return

        if (name != container_name and name in self._storage_playground.names or
                name in self._get_container_names() and new_container):
            self._error = _("Volume Group name %s is already in use. Not "
                            "saving changes.") % name
            self.set_info(self._error)
            log.error("Volume group name %s already in use.", name)
            return

        if (new_container or
                set(disks) != set(self._device_disks) or
                name != container_name or
                dialog.raid_level != self._device_container_raid_level or
                dialog.encrypted != self._device_container_encrypted or
                dialog.size_policy != self._device_container_size):
            self._applyButton.set_sensitive(True)

        if dialog.encrypted:
            self._container_encryption_change(self._device_container_encrypted,
                                              dialog.encrypted)
        self._device_disks = disks
        self._device_container_name = name
        self._device_container_raid_level = dialog.raid_level
        self._device_container_encrypted = dialog.encrypted
        self._device_container_size = dialog.size_policy
        self._set_devices_label()

        return True

    def _get_container_store_row(self, container):
        name = container.name
        free_space = getattr(container, "free_space", None)

        if free_space is not None:
            return [name, _("(%s free)") % free_space]
        else:
            return [name, ""]

    def on_modify_container_clicked(self, button):
        container_name = self._containerStore[self._containerCombo.get_active()][0]
        container = self._storage_playground.devicetree.get_device_by_name(container_name)

        # pass the name along with any found vg since we could be modifying a
        # vg that hasn't been instantiated yet
        if not self.run_container_editor(container=container, name=container_name):
            return

        if container_name == self._device_container_name:
            self.on_update_settings_clicked(None)
            return

        # Rename the container.
        if container:
            try:
                rename_container(
                    storage=self._storage_playground,
                    container=container,
                    name=self._device_container_name
                )
            except StorageError as e:
                self.set_detailed_error(_("Invalid device name."), e)
                self._device_container_name = container_name
                self.on_update_settings_clicked(None)
                return

        # Update the UI.
        idx = None

        for idx, data in enumerate(self._containerStore):
            # we're looking for the original vg name
            if data[0] == container_name:
                break

        if idx:
            container = self._storage_playground.devicetree.get_device_by_name(
                self._device_container_name
            )

            row = self._get_container_store_row(container)
            self._containerStore.insert(idx, row)
            self._containerCombo.set_active(idx)

            next_idx = self._containerStore.get_iter_from_string("%s" % (idx + 1))
            self._containerStore.remove(next_idx)

            self._modifyContainerButton.set_sensitive(
                not getattr(container, "exists", False)
            )

        self._update_selectors()
        self.on_update_settings_clicked(None)

    def on_container_changed(self, combo):
        ndx = combo.get_active()
        if ndx == -1:
            return

        container_name = self._containerStore[ndx][0]
        if container_name is None:
            return

        if self._device_container_name == container_name:
            return

        device_type = self._get_current_device_type()
        container_type_name = _(get_container_type(device_type).name).lower()
        new_text = _(NEW_CONTAINER_TEXT) % {"container_type": container_type_name}
        create_new_container = container_name == new_text
        user_changed_container = True
        if create_new_container:
            # run the vg editor dialog with a default name and disk set
            name = self._storage_playground.suggest_container_name()
            # user_changed_container flips to False if "cancel" picked
            user_changed_container = self.run_container_editor(name=name, new_container=True)
            for idx, data in enumerate(self._containerStore):
                if user_changed_container and data[0] == new_text:
                    container = self._storage_playground.devicetree.get_device_by_name(
                        self._device_container_name
                    )

                    if container:
                        row = self._get_container_store_row(container)
                    else:
                        row = [self._device_container_name, ""]

                    self._containerStore.insert(idx, row)
                    combo.set_active(idx)  # triggers a call to this method
                    return
                elif not user_changed_container and data[0] == self._device_container_name:
                    combo.set_active(idx)
                    return
        # else clause runs if an already existing container is picked
        else:
            self._device_container_name = container_name

        if user_changed_container:
            self._applyButton.set_sensitive(True)

        container = self._storage_playground.devicetree.get_device_by_name(
            self._device_container_name)
        container_exists = getattr(container, "exists", False)  # might not be in the tree

        if container:
            self._device_container_raid_level = get_device_raid_level(container)
            self._device_container_encrypted = container.encrypted
            self._device_container_size = getattr(container, "size_policy",
                                                  container.size)
        else:
            self._device_container_raid_level = None
            self._device_container_encrypted = False
            self._device_container_size = SIZE_POLICY_AUTO

        self._modifyContainerButton.set_sensitive(not container_exists)

    def _save_current_page(self, selector=None):
        if selector is None:
            selector = self._accordion.current_selector

        self._save_right_side(selector)

    def on_selector_clicked(self, old_selector, selector):
        if not self._initialized:
            return

        # one of them must be set and they need to differ
        if (old_selector or self._accordion.current_selector) \
                and (old_selector is self._accordion.current_selector):
            return

        # Take care of the previously chosen selector.
        if old_selector:
            self._save_current_page(old_selector)

        curr_selector = self._accordion.current_selector
        no_edit = False
        current_page_type = None
        if self._accordion.is_multiselection or not curr_selector:
            current_page_type = NOTEBOOK_LABEL_PAGE
            self._set_page_label_text()
            no_edit = True
        elif curr_selector.device.format.type == "luks" and \
                curr_selector.device.format.exists:
            current_page_type = NOTEBOOK_LUKS_PAGE
            selected_device_label = self._encryptedDeviceLabel
            selected_device_desc_label = self._encryptedDeviceDescLabel
            no_edit = True
        elif not getattr(curr_selector.device, "complete", True):
            current_page_type = NOTEBOOK_INCOMPLETE_PAGE
            selected_device_label = self._incompleteDeviceLabel
            selected_device_desc_label = self._incompleteDeviceDescLabel

            if isinstance(curr_selector.device, MDRaidArrayDevice):
                total = curr_selector.device.member_devices
                missing = total - len(curr_selector.device.parents)
                txt = _("This Software RAID array is missing %(missing)d of %(total)d "
                        "member partitions. You can remove it or select a different "
                        "device.") % {"missing": missing, "total": total}
            elif isinstance(curr_selector.device, LVMVolumeGroupDevice):
                total = curr_selector.device.pv_count
                missing = total - len(curr_selector.device.parents)
                txt = _("This LVM Volume Group is missing %(missingPVs)d of %(totalPVs)d "
                        "physical volumes. You can remove it or select a different "
                        "device.") % {"missingPVs": missing, "totalPVs": total}
            else:
                txt = _("This %(type)s device is missing member devices. You can remove "
                        "it or select a different device.") % curr_selector.device.type

            self._incompleteDeviceOptionsLabel.set_text(txt)
            no_edit = True
        elif devicefactory.get_device_type(curr_selector.device) is None:
            current_page_type = NOTEBOOK_UNEDITABLE_PAGE
            selected_device_label = self._uneditableDeviceLabel
            selected_device_desc_label = self._uneditableDeviceDescLabel
            no_edit = True

        if no_edit:
            self._partitionsNotebook.set_current_page(current_page_type)
            if current_page_type != NOTEBOOK_LABEL_PAGE:
                selected_device_label.set_text(curr_selector.device.name)
                desc = _(MOUNTPOINT_DESCRIPTIONS.get(curr_selector.device.type, ""))
                selected_device_desc_label.set_text(desc)

            self._configButton.set_sensitive(False)
            self._removeButton.set_sensitive(True)
            return

        # Make sure we're showing details instead of the "here's how you create
        # a new OS" label.
        self._partitionsNotebook.set_current_page(NOTEBOOK_DETAILS_PAGE)

        # Set up the newly chosen selector.
        self._populate_right_side(curr_selector)

        self._applyButton.set_sensitive(False)
        container_device = devicefactory.get_device_type(
            curr_selector.device) in CONTAINER_DEVICE_TYPES
        self._configButton.set_sensitive(not curr_selector.device.exists and
                                         not curr_selector.device.protected and
                                         not container_device)
        self._removeButton.set_sensitive(not curr_selector.device.protected)

    def on_page_clicked(self, page, mountpoint_to_show=None):
        if not self._initialized:
            return

        if self._accordion.is_current_selected:
            self._save_current_page()

        self._show_mountpoint(page=page, mountpoint=mountpoint_to_show)

        # This is called when a Page header is clicked upon so we can support
        # deleting an entire installation at once and displaying something
        # on the RHS.
        if isinstance(page, CreateNewPage):
            # Make sure we're showing "here's how you create a new OS" or
            # multiselection label instead of device/mountpoint details.
            self._partitionsNotebook.set_current_page(NOTEBOOK_LABEL_PAGE)
            self._set_page_label_text()
            self._removeButton.set_sensitive(False)
        else:
            self._removeButton.set_sensitive(True)

    @ui_storage_logged
    def _do_autopart(self, scheme):
        """Helper function for on_create_clicked.
           Assumes a non-final context in which at least some errors
           discovered by storage checker are not considered fatal because they
           will be dealt with later.

           Note: There are never any non-existent devices around when this runs.
        """
        log.debug("Running automatic partitioning.")
        self.clear_errors()

        request = PartitioningRequest()
        request.partitioning_scheme = scheme

        try:
            task = InteractiveAutoPartitioningTask(self._storage_playground, request)
            task.run()
        except (StorageConfigurationError, BootloaderConfigurationError) as e:
            self._reset_storage()
            self.set_detailed_error(_("Automatic partitioning failed."), e)

        if self._error:
            return

        report = storage_checker.check(self._storage_playground,
                                       skip=(verify_luks_devices_have_key,))
        report.log(log)

        if report.errors:
            messages = "\n".join(report.errors)
            log.error("The partitioning is not valid: %s", messages)
            self._reset_storage()
            self.set_detailed_error(_("Automatic partitioning failed."), messages)

    def on_create_clicked(self, button, autopart_type_combo):
        # Then do autopartitioning.  We do not do any clearpart first.  This is
        # custom partitioning, so you have to make your own room.
        self._do_autopart(self._get_autopart_type(autopart_type_combo))

        # Refresh the spoke to make the new partitions appear.
        self._do_refresh()
        self._update_space_display()

    def on_reformat_toggled(self, widget):
        active = widget.get_active()

        encrypt_sensitive = active
        if self._accordion.current_selector:
            device = self._accordion.current_selector.device.raw_device

            ancestors = device.ancestors
            ancestors.remove(device)
            if any(a.format.type == "luks" and a.format.exists for a in ancestors):
                # The encryption checkbutton should not be sensitive if there is
                # existing encryption below the leaf layer.
                encrypt_sensitive = False

        # you can't encrypt a btrfs subvolume -- only the volume/container
        device_type = self._get_current_device_type()
        if device_type == DEVICE_TYPE_BTRFS:
            self._encryptCheckbox.set_active(False)
            encrypt_sensitive = False

        fancy_set_sensitive(self._encryptCheckbox, encrypt_sensitive)
        self.on_encrypt_toggled(self._encryptCheckbox)

        fancy_set_sensitive(self._fsCombo, active)

    def on_fs_type_changed(self, combo):
        if not self._initialized:
            return

        fs_type = self._get_file_system_type()
        if fs_type is None:
            return

        fmt = get_format(fs_type)
        fancy_set_sensitive(self._mountPointEntry, fmt.mountable)

    def on_encrypt_toggled(self, encrypted):
        hide_or_show = really_show if encrypted.get_active() else really_hide

        for widget in [self._luksLabel, self._luksCombo]:
            hide_or_show(widget)

        fancy_set_sensitive(
            self._luksCombo,
            encrypted.get_active() and encrypted.get_sensitive()
        )

    def _populate_container(self, device):
        """ Set up the vg widgets for lvm or hide them for other types. """
        device_type = self._get_current_device_type()

        if device_type not in CONTAINER_DEVICE_TYPES:
            # just hide the buttons with no meaning for non-container devices
            for widget in [self._containerLabel,
                           self._containerCombo,
                           self._modifyContainerButton]:
                really_hide(widget)
            return

        # else really populate the container
        # set up the vg widgets and then bail out
        container = get_container(self._storage_playground, device_type, device.raw_device)
        default_container_name = getattr(container, "name", None)
        container_exists = getattr(container, "exists", False)
        container_size_policy = getattr(container, "size_policy", SIZE_POLICY_AUTO)
        container_type = get_container_type(device_type)

        self._containerLabel.set_text(
            C_("GUI|Custom Partitioning|Configure|Devices", container_type.label).title()
        )
        self._containerLabel.set_use_underline(True)
        self._containerStore.clear()

        containers = collect_containers(self._storage_playground, device_type)
        default_seen = False

        for c in containers:
            row = self._get_container_store_row(c)
            self._containerStore.append(row)

            if default_container_name and c.name == default_container_name:
                default_seen = True
                self._containerCombo.set_active(containers.index(c))

        if default_container_name is None:
            default_container_name = self._storage_playground.suggest_container_name()

        self._device_container_name = default_container_name
        self._device_container_size = container_size_policy

        if not default_seen:
            self._containerStore.append([default_container_name, ""])
            self._containerCombo.set_active(len(self._containerStore) - 1)

        container_type_name = _(container_type.name).lower()

        self._containerStore.append([
            _(NEW_CONTAINER_TEXT) % {"container_type": container_type_name}, ""
        ])
        self._containerCombo.set_tooltip_text(
            _(CONTAINER_TOOLTIP) % {"container_type": container_type_name}
        )

        if default_container_name is None:
            self._containerCombo.set_active(len(self._containerStore) - 1)

        for widget in [self._containerLabel,
                       self._containerCombo,
                       self._modifyContainerButton]:
            really_show(widget)

        # make the combo and button insensitive for existing LVs
        can_change_container = (device.raw_device is not None and not device.raw_device.exists and
                                device.raw_device != container)
        fancy_set_sensitive(self._containerCombo, can_change_container)
        self._modifyContainerButton.set_sensitive(not container_exists)

    def _update_fstype_combo(self, device_type):
        """ Set up device type dependent portion of filesystem combo.

            :param int device_type: an int representing the device type

            Generally speaking, the filesystem combo can be set up without
            reference to the device type because the choice of filesystem
            combo and of device type is orthogonal.

            However, choice of btrfs device type requires choice of btrfs
            filesystem type, and choice of any other device type precludes
            choice of btrfs filesystem type.

            Preconditions are:
            * the filesystem combo contains at least the default filesystem
            * the default filesystem is not the same as btrfs
            * if device_type is DEVICE_TYPE_BTRFS, btrfs is supported

            This method is idempotent, and must remain so.
        """
        # Find unique instance of btrfs in fsCombo, if any.
        model = self._fsCombo.get_model()
        btrfs_iter = ((idx, row) for idx, row in enumerate(model) if row[1] == "btrfs")
        btrfs_idx, btrfs_row = next(btrfs_iter, (None, None))

        if device_type == DEVICE_TYPE_BTRFS:
            # If no btrfs entry, add one, and select the new entry
            if btrfs_idx is None:
                fmt = get_format("btrfs")
                self._fsStore.append([fmt.name, fmt.type or ""])
                active_index = len(self._fsCombo.get_model()) - 1
            # Otherwise, select the already located btrfs entry
            else:
                active_index = btrfs_idx
        else:
            # Get the currently active index
            active_index = self._fsCombo.get_active()

            # If there is a btrfs entry, remove and adjust active_index
            if btrfs_idx is not None:
                self._fsStore.remove(btrfs_row.iter)

                # If btrfs previously selected, select default filesystem
                if active_index == btrfs_idx:
                    active_index = next(
                        idx for idx, data in enumerate(self._fsCombo.get_model())
                        if data[1] == self.storage.default_fstype
                    )
                # Otherwise, shift index left by one if after removed entry
                elif active_index > btrfs_idx:
                    active_index = active_index - 1
            # If there is no btrfs entry, stick with user's previous choice
            else:
                pass

        self._fsCombo.set_active(active_index)
        fancy_set_sensitive(
            self._fsCombo,
            self._reformatCheckbox.get_active() and device_type != DEVICE_TYPE_BTRFS
        )

    def on_device_type_changed(self, combo):
        if combo is not self._typeCombo:
            return

        if not self._initialized:
            return

        # The name of the device type is more informative than the numeric id
        new_type = self._get_current_device_type()

        # Quit if no device type is selected.
        if new_type is None:
            return

        # lvm uses the RHS to set disk set. no foolish minds here.
        exists = \
            self._accordion.current_selector and \
            self._accordion.current_selector.device.exists

        self._configButton.set_sensitive(
            not exists and new_type not in CONTAINER_DEVICE_TYPES
        )

        # this has to be done before calling populate_raid since it will need
        # the raid level combo to contain the relevant raid levels for the new
        # device type
        self._raidStoreFilter.refilter()

        self._populate_raid(get_default_raid_level(new_type))

        if self._accordion.current_selector:
            self._populate_container(self._accordion.current_selector.device)

        fancy_set_sensitive(self._nameEntry, new_type in NAMED_DEVICE_TYPES)
        self._nameEntry.set_text(self._get_device_name(new_type))
        fancy_set_sensitive(self._sizeEntry, new_type != DEVICE_TYPE_BTRFS)

        self._update_fstype_combo(new_type)

    def set_detailed_warning(self, msg, detailed_msg):
        self._error = detailed_msg
        self.set_warning(msg + _(" <a href=\"\">Click for details.</a>"))

    def set_detailed_error(self, msg, detailed_msg):
        self._error = detailed_msg
        self.set_error(msg + _(" <a href=\"\">Click for details.</a>"))

    def clear_errors(self):
        self._error = None
        self.clear_info()

    # This callback is for the button that just resets the UI to anaconda's
    # current understanding of the disk layout.
    def on_reset_clicked(self, *args):
        msg = _("Continuing with this action will reset all your partitioning selections "
                "to their current on-disk state.")

        dlg = Gtk.MessageDialog(
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            message_format=msg
        )
        dlg.set_decorated(False)
        dlg.add_buttons(
            C_("GUI|Custom Partitioning|Reset Dialog", "_Reset selections"),
            0,
            C_("GUI|Custom Partitioning|Reset Dialog", "_Preserve current selections"),
            1
        )
        dlg.set_default_response(1)

        with self.main_window.enlightbox(dlg):
            rc = dlg.run()
            dlg.destroy()

        if rc == 0:
            self.refresh()

    # This callback is for the button that has anaconda go back and rescan the
    # disks to pick up whatever changes the user made outside our control.
    def on_refresh_clicked(self, *args):
        dialog = RefreshDialog(self.data, self.storage)
        ignoreEscape(dialog.window)
        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()
            dialog.window.destroy()

        if rc == 1:
            # User hit OK on the dialog, indicating they stayed on the dialog
            # until rescanning completed and now needs to go back to the
            # main storage spoke.
            self.skipTo = "StorageSpoke"
        elif rc != 2:
            # User either hit cancel on the dialog or closed it via escape, so
            # there was no rescanning done.
            # NOTE: rc == 2 means the user clicked on the link that takes them
            # back to the hub.
            return

        # Can't use this spoke's on_back_clicked method as that will try to
        # save the right hand side, which is no longer valid.  The user must
        # go back and select their disks all over again since whatever they
        # did on the shell could have changed what disks are available.
        NormalSpoke.on_back_clicked(self, None)

    def on_info_bar_clicked(self, *args):
        log.debug("Clicked on the info bar: %s (%s)", self._error, args)
        if not self._error:
            return

        dlg = Gtk.MessageDialog(
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            message_format=str(self._error)
        )
        dlg.set_decorated(False)

        with self.main_window.enlightbox(dlg):
            dlg.run()
            dlg.destroy()

    @timed_action(delay=50, threshold=100)
    def on_update_settings_clicked(self, button):
        """ call _save_right_side, then, perhaps, populate_right_side. """
        self._save_right_side(self._accordion.current_selector)
        self._applyButton.set_sensitive(False)

    @timed_action(delay=50, threshold=100)
    def on_unlock_clicked(self, *args):
        """ try to open the luks device, populate, then call _do_refresh. """
        self.clear_errors()
        device = self._accordion.current_selector.device
        log.info("Trying to unlock device %s.", device.name)
        passphrase = self._passphraseEntry.get_text()
        unlocked = unlock_device(self._storage_playground, device, passphrase)

        if not unlocked:
            self._passphraseEntry.set_text("")
            self.set_detailed_warning(
                _("Failed to unlock encrypted block device."),
                "Failed to unlock {}.".format(device.name)
            )
            return

        # set the passphrase also to the original_format of the device (a
        # different object than '.format', but the same contents)
        device.original_format.passphrase = passphrase

        with ui_storage_logger():
            # look for new roots
            self._storage_playground.roots = find_existing_installations(
                self._storage_playground.devicetree)

        self._accordion.clear_current_selector()
        self._do_refresh()

    def on_value_changed(self, *args):
        self._applyButton.set_sensitive(True)
