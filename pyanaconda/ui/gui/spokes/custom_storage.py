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
import copy

import gi
from dasbus.structure import compare_data

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    PARTITIONING_METHOD_INTERACTIVE,
    THREAD_EXECUTE_STORAGE,
    THREAD_STORAGE,
)
from pyanaconda.core.i18n import C_, CP_, N_, _
from pyanaconda.core.product import get_product_name, get_product_version
from pyanaconda.core.storage import (
    CONTAINER_DEVICE_TYPES,
    DEVICE_TEXT_MAP,
    DEVICE_TYPE_BTRFS,
    DEVICE_TYPE_MD,
    DEVICE_TYPE_UNSUPPORTED,
    MOUNTPOINT_DESCRIPTIONS,
    NAMED_DEVICE_TYPES,
    PROTECTED_FORMAT_TYPES,
    Size,
    device_type_from_autopart,
)
from pyanaconda.core.threads import thread_manager
from pyanaconda.modules.common.constants.objects import BOOTLOADER, DISK_SELECTION
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.configuration import (
    BootloaderConfigurationError,
    StorageConfigurationError,
)
from pyanaconda.modules.common.structures.device_factory import (
    DeviceFactoryPermissions,
    DeviceFactoryRequest,
)
from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.modules.common.structures.storage import (
    DeviceData,
    DeviceFormatData,
    OSData,
)
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.modules.common.task import sync_run_task
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.accordion import (
    Accordion,
    CreateNewPage,
    MountPointSelector,
    Page,
    UnknownPage,
)
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.gui.spokes.lib.custom_storage_helpers import (
    CONTAINER_TOOLTIP,
    DESIRED_CAPACITY_ERROR,
    NEW_CONTAINER_TEXT,
    NOTEBOOK_DETAILS_PAGE,
    NOTEBOOK_INCOMPLETE_PAGE,
    NOTEBOOK_LABEL_PAGE,
    NOTEBOOK_LUKS_PAGE,
    NOTEBOOK_UNEDITABLE_PAGE,
    AddDialog,
    ConfirmDeleteDialog,
    ContainerDialog,
    DisksDialog,
    generate_request_description,
    get_container_type,
    get_default_raid_level,
    get_selected_raid_level,
    get_size_from_entry,
    get_supported_device_raid_levels,
)
from pyanaconda.ui.gui.spokes.lib.passphrase import PassphraseDialog
from pyanaconda.ui.gui.spokes.lib.refresh import RefreshDialog
from pyanaconda.ui.gui.spokes.lib.summary import ActionSummaryDialog
from pyanaconda.ui.gui.utils import (
    escape_markup,
    fancy_set_sensitive,
    ignoreEscape,
    really_hide,
    really_show,
    set_password_visibility,
    setViewportBackground,
    timed_action,
)
from pyanaconda.ui.helpers import StorageCheckHandler
from pyanaconda.ui.lib.storage import (
    apply_partitioning,
    create_partitioning,
    filter_disks_by_names,
)

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

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
                      "mountPointCompletion", "mountPointStore", "fileSystemStore"]
    mainWidgetName = "customStorageWindow"
    uiFile = "spokes/custom_storage.glade"
    category = SystemCategory
    title = N_("MANUAL PARTITIONING")

    # The maximum number of places to show when displaying a size
    MAX_SIZE_PLACES = 2

    # If the user enters a smaller size, the GUI changes it to this value
    MIN_SIZE_ENTRY = Size("1 MiB")

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "interactive-partitioning"

    def __init__(self, data, storage, payload):
        StorageCheckHandler.__init__(self)
        NormalSpoke.__init__(self, data, storage, payload)
        self._back_already_clicked = False
        self._initialized = False
        self._error = None
        self._accordion = None

        self._partitioning_scheme = conf.storage.default_scheme
        self._partitioning_encrypted = False

        self._default_file_system = ""
        self._available_disks = []
        self._selected_disks = []
        self._passphrase = ""
        self._os_name = ""
        self._supported_raid_levels = {}

        self._partitioning = None
        self._device_tree = None
        self._request = DeviceFactoryRequest()
        self._original_request = DeviceFactoryRequest()
        self._permissions = DeviceFactoryPermissions()

        self._storage_module = STORAGE.get_proxy()
        self._boot_loader = STORAGE.get_proxy(BOOTLOADER)
        self._disk_selection = STORAGE.get_proxy(DISK_SELECTION)

    def apply(self):
        self.clear_errors()
        hubQ.send_ready("StorageSpoke")

    @property
    def indirect(self):
        return True

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

    def _get_unused_devices(self):
        return self._device_tree.CollectUnusedDevices()

    @property
    def _boot_drive(self):
        return self._boot_loader.Drive

    def _get_new_devices(self):
        return self._device_tree.CollectNewDevices(self._boot_drive)

    def _get_all_devices(self):
        return self._device_tree.GetDevices()

    def _update_permissions(self):
        self._permissions = self._get_permissions(self._request)

    def _get_permissions(self, request):
        return DeviceFactoryPermissions.from_structure(
            self._device_tree.GenerateDeviceFactoryPermissions(
                DeviceFactoryRequest.to_structure(request)
            )
        )

    def _update_space_display(self):
        # Set up the free space/available space displays in the bottom left.
        disks = self._selected_disks
        free_space = Size(self._device_tree.GetDiskFreeSpace(disks))
        total_space = Size(self._device_tree.GetDiskTotalSpace(disks))

        self._availableSpaceLabel.set_text(str(free_space))
        self._totalSpaceLabel.set_text(str(total_space))

        count = len(disks)
        summary = CP_("GUI|Custom Partitioning",
                      "%d _storage device selected",
                      "%d _storage devices selected",
                      count) % count

        self._summaryLabel.set_text(summary)
        self._summaryLabel.set_use_underline(True)

    def _reset_storage(self):
        # FIXME: Reset only the current partitioning module.
        self._storage_module.ResetPartitioning()

    def refresh(self):
        self.reset_state()
        NormalSpoke.refresh(self)

        # Make sure the storage spoke execute method has finished before we
        # copy the storage instance.
        for thread_name in [THREAD_EXECUTE_STORAGE, THREAD_STORAGE]:
            thread_manager.wait(thread_name)

        if not self._partitioning:
            # Create the partitioning now. It cannot by done earlier, because
            # the storage spoke would use it as a default partitioning.
            self._partitioning = create_partitioning(PARTITIONING_METHOD_INTERACTIVE)
            self._device_tree = STORAGE.get_proxy(self._partitioning.GetDeviceTree())

        # Get the name of the new installation.
        self._os_name = self._device_tree.GenerateSystemName()

        # Get the default file system type.
        self._default_file_system = self._device_tree.GetDefaultFileSystem()

        # Initialize the selected disks.
        self._available_disks = self._disk_selection.GetUsableDisks()
        self._selected_disks = self._disk_selection.SelectedDisks

        # Get the available selected disks.
        self._selected_disks = filter_disks_by_names(self._available_disks, self._selected_disks)

        # Update the UI elements.
        self._do_refresh(init_expanded_pages=True)
        self._applyButton.set_sensitive(False)

    def _get_file_system_type(self):
        itr = self._fsCombo.get_active_iter()
        if not itr:
            return None

        model = self._fsCombo.get_model()
        return model[itr][1]

    def _on_autopart_type_changed(self, autopart_type_combo):
        """
        This is called when the autopart type combo on the left hand side of
        custom partitioning is changed.  We already know how to handle the case
        where the user changes the type and then clicks the autopart link
        button.  This handles the case where the user changes the type and then
        clicks the '+' button.

        """
        itr = autopart_type_combo.get_active_iter()
        if not itr:
            return

        model = autopart_type_combo.get_model()
        self._partitioning_scheme = model[itr][1]

    def _on_autopart_encrypted_toggled(self, checkbox):
        """The callback for the autopart encryption checkbox."""
        self._partitioning_encrypted = checkbox.get_active()

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
                                         escape_markup(page.page_title))

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
                % {"name": get_product_name(), "version": get_product_version()})

    def _populate_accordion(self):
        # Make sure we start with a clean state.
        self._accordion.remove_all_pages()

        new_devices = self._get_new_devices()
        all_devices = self._get_all_devices()
        unused_devices = self._get_unused_devices()

        # Collect the existing roots.
        ui_roots = OSData.from_structure_list(
            self._device_tree.CollectSupportedSystems()
        )

        # Now it's time to populate the accordion.
        log.debug("Populating accordion for devices %s (unused %s, new %s).",
                  all_devices, unused_devices, new_devices)

        # Add the initial page.
        if not new_devices:
            self._add_initial_page(reuse_existing=bool(ui_roots or unused_devices))
        else:
            new_root = OSData.from_structure(
                self._device_tree.GenerateSystemData(self._boot_drive)
            )
            ui_roots.insert(0, new_root)

        # Add root pages.
        for root in ui_roots:
            self._add_root_page(root)

        # Add the unknown page.
        if unused_devices:
            self._add_unknown_page(unused_devices)

    def _add_initial_page(self, reuse_existing=False):
        page = CreateNewPage(
            self._os_name,
            self.on_create_clicked,
            self._on_autopart_type_changed,
            self._on_autopart_encrypted_toggled,
            default_scheme=self._partitioning_scheme,
            default_encryption=self._partitioning_encrypted,
            partitions_to_reuse=reuse_existing
        )

        self._accordion.add_page(page, cb=self.on_page_clicked)
        self._partitionsNotebook.set_current_page(NOTEBOOK_LABEL_PAGE)
        self._set_page_label_text()

    def _add_root_page(self, root: OSData):
        page = Page(root.os_name)
        self._accordion.add_page(page, cb=self.on_page_clicked)

        for mount_point, device_id in root.mount_points.items():
            selector = MountPointSelector()
            self._update_selector(
                selector,
                device_id=device_id,
                root_name=root.os_name,
                mount_point=mount_point
            )
            page.add_selector(selector, self.on_selector_clicked)

        for device_id in root.devices:

            # Skip devices that already have a selector.
            if device_id in root.mount_points.values():
                continue

            selector = MountPointSelector()
            self._update_selector(
                selector,
                device_id=device_id,
                root_name=root.os_name
            )
            page.add_selector(selector, self.on_selector_clicked)

        page.show_all()

    def _add_unknown_page(self, devices):
        page = UnknownPage(_("Unknown"))
        self._accordion.add_page(page, cb=self.on_page_clicked)

        for device_id in sorted(devices):
            selector = MountPointSelector()
            self._update_selector(selector, device_id)
            page.add_selector(selector, self.on_selector_clicked)

        page.show_all()

    def _update_selector(self, selector, device_id="", root_name="", mount_point=""):
        if not selector:
            return

        if not device_id:
            device_id = selector.device_id

        if not root_name:
            root_name = selector.root_name

        device_data = DeviceData.from_structure(
            self._device_tree.GetDeviceData(device_id)
        )

        format_data = DeviceFormatData.from_structure(
            self._device_tree.GetFormatData(device_id)
        )

        mount_point = self._get_mount_point_description(
            mount_point, format_data
        )

        selector.props.name = device_data.name
        selector.props.size = str(Size(device_data.size))
        selector.props.mountpoint = mount_point
        selector.root_name = root_name
        selector.device_id = device_id

    def _get_mount_point_description(self, mount_point, format_data):
        """Generate the selector's mount point description."""
        return \
            format_data.attrs.get("mount-point", "") or \
            mount_point or \
            format_data.description or \
            _("Unknown")

    def _get_mount_point_description_for_request(self, request):
        """Generate the selector's mount point description from a request."""
        mount_point = request.mount_point
        format_type = request.format_type

        format_data = DeviceFormatData.from_structure(
            self._device_tree.GetFormatTypeData(format_type)
        )

        return self._get_mount_point_description(
            mount_point, format_data
        )

    def _do_refresh(self, mountpoint_to_show=None, init_expanded_pages=False):
        # block mountpoint selector signal handler for now
        self._initialized = False
        expanded_pages = self._accordion.get_expanded_pages()
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
        if init_expanded_pages:
            expanded_pages = [first_page.page_title]
        self._accordion.expand_pages(expanded_pages)
        self._show_mountpoint(page=first_page, mountpoint=mountpoint_to_show)

        self._applyButton.set_sensitive(False)
        self._resetButton.set_sensitive(bool(self._device_tree.GetActions()))

        # Set up the free space/available space labels.
        self._update_space_display()

    ###
    ### RIGHT HAND SIDE METHODS
    ###
    def _save_right_side(self, selector):
        """ Save settings from RHS and apply changes to the device.

            This method must never trigger a call to self._do_refresh.
        """
        # check if initialized and have something to operate on
        if not self._initialized or not selector:
            return

        # only call _save_right_side if on the right page and some changes need
        # to be saved (sensitivity of the Update Settings button reflects that)
        if self._partitionsNotebook.get_current_page() != NOTEBOOK_DETAILS_PAGE or \
                not self._applyButton.get_sensitive():
            return

        device_name = selector.device_name
        device_id = selector.device_id
        if device_id not in self._device_tree.GetDevices():
            # just-removed device
            return

        self.reset_state()

        log.debug("Saving the right side for device: %s", device_name)

        # Get the device factory request.
        old_request = self._original_request
        new_request = self._request

        if compare_data(old_request, new_request):
            log.debug("Nothing to do.")
            return

        # Log the results.
        description = generate_request_description(new_request, old_request)
        log.debug("Device request: %s", description)

        # Validate the device info.
        report = ValidationReport.from_structure(
            self._device_tree.ValidateDeviceFactoryRequest(
                DeviceFactoryRequest.to_structure(new_request)
            )
        )

        if not report.is_valid():
            log.debug("Validation has failed: %s", report)
            self.set_warning(" ".join(report.get_messages()))
            self._populate_right_side(selector)
            return

        # Apply the changes.
        try:
            self._device_tree.ChangeDevice(
                DeviceFactoryRequest.to_structure(new_request),
                DeviceFactoryRequest.to_structure(old_request)
            )
        except StorageConfigurationError as e:
            log.error("Failed to reconfigure the device: %s", e)
            self.set_detailed_error(_("Device reconfiguration failed."), e)
            self._reset_storage()
            self._do_refresh()
            return

        # Update UI.
        log.debug("The device request changes are applied.")
        mount_point = self._get_mount_point_description_for_request(new_request)
        self._do_refresh(mountpoint_to_show=mount_point)

    def _raid_level_visible(self, model, itr, user_data):
        raid_level = model[itr][1]
        return raid_level in self._supported_raid_levels

    def _populate_raid(self, raid_level=""):
        """Set up the raid-specific portion of the device details.

        :param str raid_level: RAID level name or an empty string
        """
        self._supported_raid_levels = get_supported_device_raid_levels(
            self._device_tree, self._get_current_device_type()
        )

        self._raidStoreFilter.refilter()

        if not self._supported_raid_levels:
            for widget in [self._raidLevelLabel, self._raidLevelCombo]:
                really_hide(widget)
            return

        device_type = self._get_current_device_type()
        raid_level = raid_level or get_default_raid_level(device_type)

        # Set a default RAID level in the combo.
        index = self._raidLevelCombo.get_active()

        for (i, row) in enumerate(self._raidLevelCombo.get_model()):
            if row[1] == raid_level:
                index = i
                break

        for widget in [self._raidLevelLabel, self._raidLevelCombo]:
            really_show(widget)

        self._raidLevelCombo.set_active(index)

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
            fmt = DeviceFormatData.from_structure(
                self._device_tree.GetFormatTypeData(fs_type)
            )
            self._fsStore.append([fmt.description, fmt.type])

        # set the active filesystem type
        model = self._fsCombo.get_model()
        idx = next(i for i, data in enumerate(model) if data[1] == default_type)
        self._fsCombo.set_active(idx)

        # do additional updating handled by other method
        self._update_fstype_combo(device_type)

    def _setup_device_type_combo(self, device_type, device_types):
        """Set up device type combo."""
        # Include md only if there are two or more disks.
        if len(self._selected_disks) <= 1:
            device_types.remove(DEVICE_TYPE_MD)

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
        if device_type == self._original_request.device_type:
            return self._original_request.device_name

        if device_type in NAMED_DEVICE_TYPES:
            return self._device_tree.GenerateDeviceName(
                self._request.mount_point,
                self._request.format_type
            )

        return ""

    def _set_devices_label(self):
        disks = self._request.disks

        if not disks:
            description = _("No disks assigned")
        else:
            device_data = DeviceData.from_structure(
                self._device_tree.GetDeviceData(disks[0])
            )
            description = "{} ({})".format(
                device_data.description,
                device_data.name
            )
            num_disks = len(disks)

            if num_disks > 1:
                description += CP_(
                    "GUI|Custom Partitioning|Devices",
                    " and {} other", " and {} others",
                    num_disks - 1
                ).format(num_disks - 1)

        self._deviceDescLabel.set_text(description)

    def _populate_right_side(self, selector):
        device_id = selector.device_id
        device_name = selector.device_name

        self._request = DeviceFactoryRequest.from_structure(
            self._device_tree.GenerateDeviceFactoryRequest(device_id)
        )

        self._original_request = copy.deepcopy(self._request)
        self._update_permissions()

        description = generate_request_description(self._request)
        log.debug("Populating the right side for device %s: %s", device_name, description)

        self._selectedDeviceLabel.set_text(device_name)
        self._selectedDeviceDescLabel.set_text(
            _(MOUNTPOINT_DESCRIPTIONS.get(device_name, ""))
        )

        self._set_devices_label()

        self._mountPointEntry.set_text(self._request.mount_point)
        fancy_set_sensitive(self._mountPointEntry, self._permissions.mount_point)

        self._labelEntry.set_text(self._request.label)
        fancy_set_sensitive(self._labelEntry, self._permissions.label)

        self._sizeEntry.set_text(
            Size(self._request.device_size).human_readable(max_places=self.MAX_SIZE_PLACES)
        )

        self._reformatCheckbox.set_active(self._request.reformat)
        fancy_set_sensitive(self._reformatCheckbox, self._permissions.reformat)

        # Set up the encryption.
        self._encryptCheckbox.set_active(self._request.device_encrypted)
        fancy_set_sensitive(self._encryptCheckbox, self._permissions.device_encrypted)

        self._encryptCheckbox.set_inconsistent(self._request.container_encrypted)
        text = _("The container is encrypted.") if self._request.container_encrypted else ""
        self._encryptCheckbox.set_tooltip_text(text)

        # Set up the filesystem type combo.
        format_types = self._device_tree.GetFileSystemsForDevice(device_id)
        self._setup_fstype_combo(self._request.device_type, self._request.format_type, format_types)
        fancy_set_sensitive(self._fsCombo, self._permissions.format_type)

        # Set up the device type combo.
        device_types = self._device_tree.GetDeviceTypesForDevice(device_id)
        self._setup_device_type_combo(self._request.device_type, device_types)
        fancy_set_sensitive(self._typeCombo, self._permissions.device_type)

        # FIXME: device encryption should be mutually exclusive with container
        # encryption

        # FIXME: device raid should be mutually exclusive with container raid

        # The size entry is only sensitive for resizable existing devices and
        # new devices that are not btrfs subvolumes.
        # Do this after the device type combo is set since
        # on_device_type_changed doesn't account for device existence.
        fancy_set_sensitive(self._sizeEntry, self._permissions.device_size)

        if self._permissions.device_size:
            self._sizeEntry.props.has_tooltip = False
        elif self._request.format_type == "btrfs":
            self._sizeEntry.set_tooltip_text(_(
                "The space available to this mount point can "
                "be changed by modifying the volume below."
            ))
        else:
            self._sizeEntry.set_tooltip_text(_(
                "This file system may not be resized."
            ))

        self._populate_raid(self._request.device_raid_level)
        fancy_set_sensitive(self._raidLevelCombo, self._permissions.device_raid_level)

        self._populate_container()

        self._nameEntry.set_text(self._request.device_name)
        fancy_set_sensitive(self._nameEntry, self._permissions.device_name)

        self._configButton.set_sensitive(self._permissions.disks)

    ###
    ### SIGNAL HANDLERS
    ###

    def on_key_pressed(self, widget, event, *args):
        if not event or (event and event.type != Gdk.EventType.KEY_RELEASE):
            return

        if event.keyval in [Gdk.KEY_Delete, Gdk.KEY_minus]:
            # But we only want delete to work if you have focused a MountPointSelector,
            # and not just any random widget.  For those, it's likely the user wants
            # to delete a character.
            if isinstance(self.main_window.get_focus(), MountPointSelector):
                self._removeButton.emit("clicked")
        elif event.keyval == Gdk.KEY_plus:
            # And we only want '+' to work if you don't have a text entry focused, since
            # the user might be entering some free-form text that can include a plus.
            if not isinstance(self.main_window.get_focus(), Gtk.Entry):
                self._addButton.emit("clicked")

    def _setup_passphrase(self):
        # Find new LUKS devices without a passphrase.
        devices = self._device_tree.FindUnconfiguredLUKS()

        if not devices:
            return True

        # Ask for a passphrase.
        dialog = PassphraseDialog(self.data, default_passphrase=self._passphrase)
        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()

        # Cancel. Leave the old passphrase set if there was one.
        if rc != 1:
            return False

        # Set the new passphrase.
        self._passphrase = dialog.passphrase

        # Configure the devices.
        for device_id in devices:
            self._device_tree.SetDevicePassphrase(device_id, self._passphrase)

        return True

    def _do_check(self):
        self.clear_errors()

        report = apply_partitioning(
            partitioning=self._partitioning,
            show_message_cb=log.debug,
            reset_storage_cb=self._reset_storage
        )

        StorageCheckHandler.errors = list(report.error_messages)
        StorageCheckHandler.warnings = list(report.warning_messages)

        if self.errors:
            self.set_warning(_(
                "Error checking storage configuration. <a href=\"\">Click for details</a> "
                "or press Done again to continue."))
        elif self.warnings:
            self.set_warning(_(
                "Warning checking storage configuration. <a href=\"\">Click for details</a> "
                "or press Done again to continue."))

        # on_info_bar_clicked requires self._error to be set, so set it to the
        # list of all errors and warnings that storage checking found.
        self._error = "\n".join(self.errors + self.warnings)

        return self._error == ""

    def on_back_clicked(self, button):
        # Clear any existing errors
        self.clear_errors()

        # Save anything from the currently displayed mount point.
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

            if not self._setup_passphrase():
                return

            if not self._do_check():
                return

        dialog = ActionSummaryDialog(self.data, self._device_tree)
        dialog.refresh()

        if dialog.actions:
            with self.main_window.enlightbox(dialog.window):
                rc = dialog.run()

            if rc != 1:
                # Cancel.  Stay on the custom screen.
                return

        NormalSpoke.on_back_clicked(self, button)

    def on_add_clicked(self, button):
        # Clear any existing errors
        self.reset_state()

        # Save anything from the currently displayed mount point.
        self._save_right_side(self._accordion.current_selector)

        # Initialize and run the AddDialog.
        dialog = AddDialog(self.data, self._device_tree)
        dialog.refresh()

        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()

            if rc != 1:
                # user cancel
                dialog.window.destroy()
                return

        # Gather data about the added mount point.
        request = DeviceFactoryRequest()
        request.mount_point = dialog.mount_point
        request.device_size = dialog.size.get_bytes()
        request.device_type = device_type_from_autopart(self._partitioning_scheme)
        request.disks = self._selected_disks

        # Clear errors and try to add the mountpoint/device.
        self.reset_state()

        try:
            self._device_tree.AddDevice(
                DeviceFactoryRequest.to_structure(request)
            )
        except StorageConfigurationError as e:
            self.set_detailed_error(_("Failed to add new device."), e)
            self._do_refresh()
        else:
            mount_point = self._get_mount_point_description_for_request(request)
            self._do_refresh(mountpoint_to_show=mount_point)

    def _show_mountpoint(self, page, mountpoint=None):
        if not self._initialized:
            return

        # Make sure there's something displayed on the RHS.  If a page and
        # mountpoint within that page is given, display that.
        log.debug("Showing mount point: %s", page.page_title)

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

    def _show_confirmation_dialog(self, root_name, device_id):
        dialog = ConfirmDeleteDialog(self.data, self._device_tree, root_name, device_id,
                                     self._accordion.is_multiselection)
        dialog.refresh()

        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()
            option_checked = dialog.option_checked
            dialog.window.destroy()
            return rc, option_checked

    def on_remove_clicked(self, button):
        # Nothing selected?  Nothing to remove.
        if not self._accordion.is_current_selected and not self._accordion.is_multiselection:
            return

        # No items are selected.
        if not self._accordion.selected_items:
            return

        # Remove selected items.
        self.reset_state()

        try:
            self._remove_selected_devices()
        except StorageConfigurationError as e:
            log.error("The device removal has failed: %s", e)
            self.set_detailed_warning(_("Device removal request failed."), e)

        # Now that devices have been removed from the installation root,
        # refreshing the display will have the effect of making them disappear.
        # It's like they never existed.
        task_path = self._device_tree.FindExistingSystemsWithTask()
        task_proxy = STORAGE.get_proxy(task_path)
        sync_run_task(task_proxy)

        # Refresh UI.
        self._do_refresh()

    def _remove_selected_devices(self):
        option_checked = False
        is_multiselection = self._accordion.is_multiselection

        for selector in self._accordion.selected_items:
            page = self._accordion.page_for_selector(selector)
            device_name = selector.device_name
            device_id = selector.device_id
            root_name = selector.root_name or page.page_title
            log.debug("Removing device %s from page %s.", device_name, root_name)

            # Skip if the device isn't in the device tree.
            if not self._device_tree.IsDevice(device_id):
                log.debug("Device %s isn't in the device tree.", device_name)
                continue

            if root_name == self._os_name:
                if is_multiselection and not option_checked:
                    (rc, option_checked) = self._show_confirmation_dialog(root_name, device_id)

                    if rc != 1:
                        if option_checked:
                            break  # skip evaluation of all other mountpoints
                        continue

                self._device_tree.ResetDevice(device_id)
            else:
                # This is a device that exists on disk and most likely has data
                # on it.  Thus, we first need to confirm with the user and then
                # schedule actions to delete the thing.
                # In multiselection user could confirm once for all next
                # selections.
                if not option_checked:
                    (rc, option_checked) = self._show_confirmation_dialog(root_name, device_id)

                    if rc != 1:
                        if option_checked:
                            break  # skip evaluation of all other mountpoints
                        continue

                if is_multiselection or not option_checked:
                    self._device_tree.DestroyDevice(device_id)
                    continue

                # We never want to delete known-shared devs here.
                # The same rule applies for selected device. If it's shared do not
                # remove it in other pages when Delete all option is checked.
                for other_id in self._find_unshared_devices(page):
                    # Skip if the device isn't in the device tree.
                    if not self._device_tree.IsDevice(other_id):
                        log.debug("Device %s isn't in the device tree.", other_id)
                        continue

                    # we only want to delete boot partitions if they're not
                    # shared *and* we have no unknown partitions
                    other_format = DeviceFormatData.from_structure(
                        self._device_tree.GetFormatData(other_id)
                    )

                    other_data = DeviceData.from_structure(
                        self._device_tree.GetDeviceData(other_id)
                    )

                    can_destroy = not self._get_unused_devices() \
                        or other_format.type not in PROTECTED_FORMAT_TYPES

                    if not can_destroy:
                        log.debug("Device %s cannot be removed.", other_data.name)
                        continue

                    self._device_tree.DestroyDevice(other_id)

    def _find_unshared_devices(self, page):
        """Get unshared devices of the page."""
        other_devices = set()

        for p in self._accordion.all_pages:
            if p is page:
                continue

            for s in p.members:
                other_devices.add(s.device_id)

        unshared_devices = []
        for s in page.members:
            if s.device_id in other_devices:
                continue

            unshared_devices.append(s.device_id)

        return unshared_devices

    def on_summary_clicked(self, button):
        disks = self._selected_disks
        dialog = SelectedDisksDialog(self.data, disks, show_remove=False, set_boot=False)

        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

    def on_configure_clicked(self, button):
        selector = self._accordion.current_selector
        if not selector:
            return

        if self._get_current_device_type() in CONTAINER_DEVICE_TYPES:
            # disk set management happens through container edit on RHS
            return

        self.reset_state()

        is_md = self._get_current_device_type() == DEVICE_TYPE_MD

        dialog = DisksDialog(
            self.data,
            self._device_tree,
            self._selected_disks,
            self._request.disks,
            is_md
        )
        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()
            dialog.window.destroy()

        if rc != 1:
            return

        disks = dialog.selected_disks

        if not disks:
            self._error = _("No disks selected. Keeping previous disk set.")
            self.set_info(self._error)
            return

        self._request.disks = disks
        self._set_devices_label()
        self._populate_raid(get_selected_raid_level(self._raidLevelCombo))
        self.on_value_changed()

    def _run_container_editor(self, container_name=None):
        """ Run container edit dialog and return True if changes were made. """
        # Get a set of container names.
        container_names = set(self._get_container_names())
        container_names.discard(container_name)

        # Generate a new container name if necessary.
        container_name = container_name or self._device_tree.GenerateContainerName()

        # Generate a new request.
        request = DeviceFactoryRequest.from_structure(
            self._device_tree.UpdateContainerData(
                DeviceFactoryRequest.to_structure(self._request),
                container_name
            )
        )

        # Generate new permissions.
        permissions = self._get_permissions(request)

        # Run the dialog.
        dialog = ContainerDialog(
            self.data,
            self._device_tree,
            request=request,
            permissions=permissions,
            disks=self._selected_disks,
            names=container_names
        )

        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()
            dialog.window.destroy()

        if rc != 1:
            return False

        # Has the encryption changed?
        encryption_changed = self._request.container_encrypted != request.container_encrypted

        # Set the request.
        self._request = request
        self._update_permissions()

        # Update device encryption.
        if encryption_changed:
            # container set to be encrypted, we should make sure the leaf device
            # is not encrypted and make the encryption checkbox insensitive
            if request.container_encrypted:
                self._encryptCheckbox.set_active(False)
                self._encryptCheckbox.set_inconsistent(True)

            fancy_set_sensitive(self._encryptCheckbox, self._permissions.device_encrypted)

        # Update the UI.
        self._set_devices_label()
        self.on_value_changed()
        return True

    def _get_container_names(self):
        for data in self._containerStore:
            yield data[0]

    def _get_container_store_row(self, container_name):
        description = container_name
        free_space_text = ""

        if container_name in self._device_tree.GetDevices():
            free_space = self._device_tree.GetContainerFreeSpace(container_name)
            free_space_text = _("({} free)").format(Size(free_space))

        return [container_name, description, free_space_text]

    def on_modify_container_clicked(self, button):
        # Get the selected container name.
        container_name = self._containerStore[self._containerCombo.get_active()][0]

        # pass the name along with any found vg since we could be modifying a
        # vg that hasn't been instantiated yet
        if not self._run_container_editor(container_name):
            return

        if container_name == self._request.container_name:
            self.on_update_settings_clicked(None)
            return

        # Update the UI.
        idx = None

        for idx, data in enumerate(self._containerStore):
            # we're looking for the original vg name
            if data[0] == container_name:
                break

        if idx:
            row = self._get_container_store_row(
                self._request.container_name
            )
            self._containerStore.insert(idx, row)
            self._containerCombo.set_active(idx)

            next_idx = self._containerStore.get_iter_from_string(
                "%s" % (idx + 1)
            )
            self._containerStore.remove(next_idx)

        # Update permissions.
        self._update_permissions()

        # Enable widgets.
        self._modifyContainerButton.set_sensitive(self._permissions.can_modify_container())

        # Save the right side.
        self.on_update_settings_clicked(None)

    def on_container_changed(self, combo):
        """Choose a different container or create a new one."""
        ndx = combo.get_active()
        if ndx == -1:
            return

        container_name = self._containerStore[ndx][0]
        if container_name is None:
            return

        if container_name != "" and self._request.container_name == container_name:
            return

        if container_name:
            # an already existing container is picked
            self._request = DeviceFactoryRequest.from_structure(
                self._device_tree.UpdateContainerData(
                    DeviceFactoryRequest.to_structure(self._request),
                    container_name
                )
            )
        else:
            # user_changed_container flips to False if "cancel" picked
            user_changed_container = self._run_container_editor()

            for idx, data in enumerate(self._containerStore):
                if user_changed_container and data[0] == "":
                    row = self._get_container_store_row(self._request.container_name)
                    self._containerStore.insert(idx, row)
                    combo.set_active(idx)  # triggers a call to this method
                    return
                elif not user_changed_container and data[0] == self._request.container_name:
                    combo.set_active(idx)  # triggers a call to this method
                    return

        # Update permissions.
        self._update_permissions()

        # Update UI.
        self._modifyContainerButton.set_sensitive(self._permissions.can_modify_container())
        self.on_value_changed()

    def on_selector_clicked(self, old_selector, selector):
        if not self._initialized:
            return

        # one of them must be set and they need to differ
        if (old_selector or self._accordion.current_selector) \
                and (old_selector is self._accordion.current_selector):
            return

        # Take care of the previously chosen selector.
        if old_selector:
            self._save_right_side(old_selector)

        # There is no device to show.
        if self._accordion.is_multiselection or not self._accordion.current_selector:
            self._partitionsNotebook.set_current_page(NOTEBOOK_LABEL_PAGE)
            self._set_page_label_text()
            return

        device_id = self._accordion.current_selector.device_id
        device_data = DeviceData.from_structure(
            self._device_tree.GetDeviceData(device_id)
        )
        completeness = ValidationReport.from_structure(
            self._device_tree.CheckCompleteness(device_id)
        )
        description = _(MOUNTPOINT_DESCRIPTIONS.get(device_data.type, ""))

        if self._device_tree.IsDeviceLocked(device_id):
            self._partitionsNotebook.set_current_page(NOTEBOOK_LUKS_PAGE)
            self._encryptedDeviceLabel.set_text(device_data.name)
            self._encryptedDeviceDescLabel.set_text(description)
        elif not completeness.is_valid():
            self._partitionsNotebook.set_current_page(NOTEBOOK_INCOMPLETE_PAGE)
            self._incompleteDeviceLabel.set_text(device_data.name)
            self._incompleteDeviceDescLabel.set_text(description)
            self._incompleteDeviceOptionsLabel.set_text(" ".join(completeness.get_messages()))
        elif not self._device_tree.IsDeviceEditable(device_id):
            self._partitionsNotebook.set_current_page(NOTEBOOK_UNEDITABLE_PAGE)
            self._uneditableDeviceLabel.set_text(device_data.name)
            self._uneditableDeviceDescLabel.set_text(description)
        else:
            self._partitionsNotebook.set_current_page(NOTEBOOK_DETAILS_PAGE)
            self._populate_right_side(self._accordion.current_selector)
            self._applyButton.set_sensitive(False)
            self._removeButton.set_sensitive(not device_data.protected)

    def on_page_clicked(self, page, mountpoint_to_show=None):
        if not self._initialized:
            return

        if self._accordion.is_current_selected:
            self._save_right_side(self._accordion.current_selector)

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

    def _do_autopart(self, scheme, encrypted):
        """Helper function for on_create_clicked.
           Assumes a non-final context in which at least some errors
           discovered by storage checker are not considered fatal because they
           will be dealt with later.

           Note: There are never any non-existent devices around when this runs.
        """
        self.reset_state()

        # Create the partitioning request.
        request = PartitioningRequest()
        request.partitioning_scheme = scheme
        request.encrypted = encrypted

        try:
            # Schedule the partitioning.
            log.debug("Running automatic partitioning.")
            task_path = self._device_tree.SchedulePartitionsWithTask(
                PartitioningRequest.to_structure(request)
            )
            task_proxy = STORAGE.get_proxy(task_path)
            sync_run_task(task_proxy)
        except (StorageConfigurationError, BootloaderConfigurationError) as e:
            # Reset the partitioning.
            self._reset_storage()
            self.set_detailed_error(_("Automatic partitioning failed."), e)

    def on_create_clicked(self, button, autopart_type_combo):
        # Then do autopartitioning.  We do not do any clearpart first.  This is
        # custom partitioning, so you have to make your own room.
        self._do_autopart(
            scheme=self._partitioning_scheme,
            encrypted=self._partitioning_encrypted
        )

        # Refresh the spoke to make the new partitions appear.
        self._do_refresh()

    def on_reformat_toggled(self, widget):
        reformat = widget.get_active()

        # Skip if the value is the same.
        if self._request.reformat == reformat:
            return

        # Set the reformat flag.
        self._request.reformat = widget.get_active()
        self._update_permissions()

        # Update the UI.
        fancy_set_sensitive(self._labelEntry, self._permissions.label)
        fancy_set_sensitive(self._encryptCheckbox, self._permissions.device_encrypted)
        fancy_set_sensitive(self._fsCombo, self._permissions.format_type)
        self.on_value_changed()

    def on_fs_type_changed(self, combo):
        if not self._initialized:
            return

        # Skip if no file system type is set.
        fs_type = self._get_file_system_type()
        if fs_type is None:
            return

        # Skip if the file system type is the same.
        if self._request.format_type == fs_type:
            return

        # Set the new file system type.
        self._request.format_type = fs_type
        self._update_permissions()

        # Update UI.
        fancy_set_sensitive(self._labelEntry, self._permissions.label)
        fancy_set_sensitive(self._mountPointEntry, self._permissions.mount_point)
        self.on_value_changed()

    def on_encrypt_toggled(self, widget):
        self._encryptCheckbox.set_inconsistent(False)
        self._request.device_encrypted = self._encryptCheckbox.get_active()
        self.on_value_changed()

    def on_mount_point_changed(self, widget):
        self._request.mount_point = self._mountPointEntry.get_text()
        self.on_value_changed()

    def on_label_changed(self, widget):
        self._request.label = self._labelEntry.get_text()
        self.on_value_changed()

    def on_name_changed(self, widget):
        self._request.device_name = self._nameEntry.get_text()
        self.on_value_changed()

    def on_raid_level_changed(self, widget):
        self._request.device_raid_level = get_selected_raid_level(self._raidLevelCombo)
        self.on_value_changed()

    @timed_action(750, 1500, False)
    def on_size_changed(self, *args):
        """Callback for text change in "desired capacity" widget"""
        if not self._sizeEntry.get_sensitive():
            return

        size = get_size_from_entry(self._sizeEntry)

        # Show warning if the size string is invalid. Field self._error is used as a "flag" that
        # the last error was the same. This is done because this warning can fire on every change,
        # so it would keep flickering at the bottom as you type.
        if size is None:
            if self._error != DESIRED_CAPACITY_ERROR:
                self.clear_errors()
                self.set_detailed_warning(
                    _("Invalid input. Specify the Desired Capacity in whole or decimal numbers, "
                      "with an appropriate unit."),
                    _(DESIRED_CAPACITY_ERROR)
                )
            return
        elif self._error == DESIRED_CAPACITY_ERROR:
            self.clear_errors()

        current_size = Size(self._request.device_size)
        displayed_size = current_size.human_readable(max_places=self.MAX_SIZE_PLACES)

        if displayed_size == self._sizeEntry.get_text():
            return

        self._request.device_size = size.get_bytes()
        self.on_value_changed()

    def _populate_container(self):
        """ Set up the vg widgets for lvm or hide them for other types. """
        device_type = self._get_current_device_type()

        container_widgets = [
            self._containerLabel,
            self._containerCombo,
            self._modifyContainerButton
        ]

        # Hide all container widgets and quit.
        if device_type not in CONTAINER_DEVICE_TYPES:
            for widget in container_widgets:
                really_hide(widget)
            return

        # Collect the containers.
        container_name = self._request.container_name
        containers = self._device_tree.CollectContainers(device_type)

        if container_name and container_name not in containers:
            containers.append(container_name)

        # Add all containers to the store.
        self._containerStore.clear()

        for i, name in enumerate(containers):
            row = self._get_container_store_row(name)
            self._containerStore.append(row)

            if name == container_name:
                self._containerCombo.set_active(i)

        # Add an item for creating a new container.
        container_type = get_container_type(device_type)
        container_type_name = _(container_type.name).lower()
        description = _(NEW_CONTAINER_TEXT) % {"container_type": container_type_name}
        self._containerStore.append(["", description, ""])

        # Set up the tooltip.
        tooltip = _(CONTAINER_TOOLTIP) % {"container_type": container_type_name}
        self._containerCombo.set_tooltip_text(tooltip)

        if not container_name:
            self._containerCombo.set_active(len(self._containerStore) - 1)

        # Set up the label.
        label = C_("GUI|Custom Partitioning|Configure|Devices", container_type.label).title()
        self._containerLabel.set_text(label)
        self._containerLabel.set_use_underline(True)

        # Show all container widgets.
        for widget in container_widgets:
            really_show(widget)

        # Enable container widgets.
        # Make the combo and button insensitive for existing LVs
        fancy_set_sensitive(self._containerCombo, self._permissions.can_replace_container())
        self._modifyContainerButton.set_sensitive(self._permissions.can_modify_container())

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
                fmt = DeviceFormatData.from_structure(
                    self._device_tree.GetFormatTypeData("btrfs")
                )
                self._fsStore.append([fmt.description, fmt.type])
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
                        if data[1] == self._default_file_system
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

        # Skip if no device type is selected.
        new_type = self._get_current_device_type()

        if new_type is None:
            return

        # Skip if the device type is the same.
        if self._request.device_type == new_type:
            return

        # Set the new device type.
        self._request.device_type = new_type
        self._update_permissions()

        # lvm uses the RHS to set disk set. no foolish minds here.
        self._configButton.set_sensitive(self._permissions.disks)

        # this has to be done before calling populate_raid since it will need
        # the raid level combo to contain the relevant raid levels for the new
        # device type
        self._request.device_raid_level = get_default_raid_level(new_type)
        self._populate_raid(self._request.device_raid_level)

        # Generate a new container configuration for the new type.
        self._request = DeviceFactoryRequest.from_structure(
            self._device_tree.GenerateContainerData(
                DeviceFactoryRequest.to_structure(self._request)
            )
        )

        self._populate_container()

        # Set up the device name.
        fancy_set_sensitive(self._nameEntry, self._permissions.device_name)
        self._nameEntry.set_text(self._get_device_name(new_type))

        # Set up the device size.
        fancy_set_sensitive(self._sizeEntry, self._permissions.device_size)

        # Set up the file system type.
        self._update_fstype_combo(new_type)
        self.on_value_changed()

    def set_detailed_warning(self, msg, detailed_msg):
        self._error = detailed_msg
        self.set_warning(msg + _(" <a href=\"\">Click for details.</a>"))

    def set_detailed_error(self, msg, detailed_msg):
        self._error = detailed_msg
        self.set_error(msg + _(" <a href=\"\">Click for details.</a>"))

    def clear_errors(self):
        self._error = None
        self.clear_info()

    def reset_state(self):
        self.clear_errors()
        self._back_already_clicked = False

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
            self._reset_storage()
            self.refresh()

    # This callback is for the button that has anaconda go back and rescan the
    # disks to pick up whatever changes the user made outside our control.
    def on_refresh_clicked(self, *args):
        dialog = RefreshDialog(self.data)
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

    def on_update_settings_clicked(self, button):
        self._update_settings(self._accordion.current_selector)

    @timed_action(delay=50, threshold=100)
    def _update_settings(self, selector):
        """ call _save_right_side, then, perhaps, populate_right_side. """
        if not selector:
            return

        # Clear any existing errors
        self.reset_state()

        # Save anything from the currently displayed mount point.
        self._save_right_side(selector)
        self._applyButton.set_sensitive(False)

    def on_unlock_clicked(self, *args):
        # hide the passphrase during unlocking
        set_password_visibility(self._passphraseEntry, False)

        self._unlock_device(self._accordion.current_selector)

    @timed_action(delay=50, threshold=100)
    def _unlock_device(self, selector):
        """ try to open the luks device, populate, then call _do_refresh. """
        if not selector:
            return

        self.reset_state()

        device_name = selector.device_name
        device_id = selector.device_id
        passphrase = self._passphraseEntry.get_text()

        log.info("Trying to unlock device %s.", device_name)
        unlocked = self._device_tree.UnlockDevice(device_id, passphrase)

        if not unlocked:
            self._passphraseEntry.set_text("")
            self.set_detailed_warning(
                _("Failed to unlock encrypted block device."),
                "Failed to unlock {}.".format(device_name)
            )
            return

        # TODO: Run the task asynchronously.
        task_path = self._device_tree.FindExistingSystemsWithTask()
        task_proxy = STORAGE.get_proxy(task_path)
        sync_run_task(task_proxy)

        self._accordion.clear_current_selector()
        self._do_refresh()

    def on_passphrase_icon_clicked(self, entry, icon_pos, event):
        """Called by Gtk callback when the icon of a passphrase entry is clicked."""
        set_password_visibility(entry, not entry.get_visibility())

    def on_passphrase_entry_map(self, entry):
        """Called when a passphrase entry widget is going to be displayed.

        - Without this the passphrase visibility toggle icon would not be shown.
        - The passphrase should be hidden every time the entry widget is displayed
          to avoid showing the passphrase in plain text in case the user previously
          displayed the passphrase and then left the screen.
        """
        set_password_visibility(entry, False)

    def on_value_changed(self, *args):
        self._applyButton.set_sensitive(True)
