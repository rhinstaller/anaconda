# Storage configuration spoke
#
# Copyright (C) 2011-2014  Red Hat, Inc.
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
import sys

import gi
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants, util
from pyanaconda.core.async_utils import async_action_nowait, async_action_wait
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    BOOTLOADER_ENABLED,
    CLEAR_PARTITIONS_NONE,
    PARTITIONING_METHOD_AUTOMATIC,
    PARTITIONING_METHOD_BLIVET,
    PARTITIONING_METHOD_INTERACTIVE,
    STORAGE_METADATA_RATIO,
    WARNING_NO_DISKS_DETECTED,
    WARNING_NO_DISKS_SELECTED,
)
from pyanaconda.core.i18n import C_, CN_, _
from pyanaconda.core.storage import suggest_swap_size
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.objects import (
    BOOTLOADER,
    DEVICE_TREE,
    DISK_INITIALIZATION,
    DISK_SELECTION,
)
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.threading import AnacondaThread, threadMgr
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui import MainWindow
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.cart import SelectedDisksDialog
from pyanaconda.ui.gui.spokes.lib.dasdfmt import DasdFormatDialog
from pyanaconda.ui.gui.spokes.lib.detailederror import DetailedErrorDialog
from pyanaconda.ui.gui.spokes.lib.passphrase import PassphraseDialog
from pyanaconda.ui.gui.spokes.lib.refresh import RefreshDialog
from pyanaconda.ui.gui.spokes.lib.resize import ResizeDialog
from pyanaconda.ui.gui.spokes.lib.storage_dialogs import (
    DASD_FORMAT_NO_CHANGE,
    DASD_FORMAT_REFRESH,
    DASD_FORMAT_RETURN_TO_HUB,
    RESPONSE_CANCEL,
    RESPONSE_MODIFY_SW,
    RESPONSE_OK,
    RESPONSE_QUIT,
    RESPONSE_RECLAIM,
    NeedSpaceDialog,
    NoSpaceDialog,
)
from pyanaconda.ui.gui.utils import ignoreEscape
from pyanaconda.ui.helpers import StorageCheckHandler
from pyanaconda.ui.lib.format_dasd import DasdFormatting
from pyanaconda.ui.lib.storage import (
    apply_disk_selection,
    apply_partitioning,
    create_partitioning,
    filter_disks_by_names,
    find_partitioning,
    get_disks_summary,
    is_local_disk,
    is_passphrase_required,
    select_default_disks,
    set_required_passphrase,
)

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("AnacondaWidgets", "3.3")
from gi.repository import AnacondaWidgets, Gdk, Gtk

log = get_module_logger(__name__)

__all__ = ["StorageSpoke"]


class StorageSpoke(NormalSpoke, StorageCheckHandler):
    """
       .. inheritance-diagram:: StorageSpoke
          :parts: 3
    """
    builderObjects = ["storageWindow", "addSpecializedImage"]
    mainWidgetName = "storageWindow"
    uiFile = "spokes/storage.glade"
    category = SystemCategory
    # other candidates: computer-symbolic, folder-symbolic
    icon = "drive-harddisk-symbolic"
    title = CN_("GUI|Spoke", "Installation _Destination")

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "storage-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Don't run the storage spoke on dir installations."""
        if not NormalSpoke.should_run(environment, data):
            return False

        return not conf.target.is_directory

    def __init__(self, *args, **kwargs):
        StorageCheckHandler.__init__(self)
        NormalSpoke.__init__(self, *args, **kwargs)
        self.applyOnSkip = True
        self._ready = False
        self._back_clicked = False
        self._disks_errors = []
        self._last_clicked_overview = None
        self._cur_clicked_overview = None

        self._storage_module = STORAGE.get_proxy()
        self._device_tree = STORAGE.get_proxy(DEVICE_TREE)
        self._bootloader_module = STORAGE.get_proxy(BOOTLOADER)
        self._disk_init_module = STORAGE.get_proxy(DISK_INITIALIZATION)
        self._disk_select_module = STORAGE.get_proxy(DISK_SELECTION)

        # This list contains all possible disks that can be included in the install.
        # All types of advanced disks should be set up for us ahead of time, so
        # there should be no need to modify this list.
        self._available_disks = []
        self._selected_disks = []
        self._last_selected_disks = []

        # Is the partitioning already configured?
        self._is_preconfigured = bool(self._storage_module.CreatedPartitioning)

        # Find a partitioning to use.
        self._partitioning = find_partitioning()
        self._last_partitioning_method = self._partitioning.PartitioningMethod

        # Create a partitioning request for the automatic partitioning.
        self._partitioning_request = PartitioningRequest()

        if self._last_partitioning_method == PARTITIONING_METHOD_AUTOMATIC:
            self._partitioning_request = PartitioningRequest.from_structure(
                self._partitioning.Request
            )

        # Get the UI elements.
        self._custom_part_radio_button = self.builder.get_object("customRadioButton")
        self._blivet_gui_radio_button = self.builder.get_object("blivetguiRadioButton")
        self._encrypted_checkbox = self.builder.get_object("encryptionCheckbox")
        self._encryption_revealer = self.builder.get_object("encryption_revealer")
        self._reclaim_checkbox = self.builder.get_object("reclaimCheckbox")
        self._reclaim_revealer = self.builder.get_object("reclaim_checkbox_revealer")
        self._local_disks_box = self.builder.get_object("local_disks_box")
        self._specialized_disks_box = self.builder.get_object("specialized_disks_box")
        self._local_viewport = self.builder.get_object("localViewport")
        self._specialized_viewport = self.builder.get_object("specializedViewport")
        self._main_viewport = self.builder.get_object("storageViewport")
        self._main_box = self.builder.get_object("storageMainBox")

        # Configure the partitioning methods.
        self._configure_partitioning_methods()

    def _configure_partitioning_methods(self):
        if "CustomPartitioningSpoke" in conf.ui.hidden_spokes:
            self._custom_part_radio_button.set_visible(False)
            self._custom_part_radio_button.set_no_show_all(True)

        if "BlivetGuiSpoke" in conf.ui.hidden_spokes or not conf.ui.blivet_gui_supported:
            self._blivet_gui_radio_button.set_visible(False)
            self._blivet_gui_radio_button.set_no_show_all(True)

    def _get_selected_partitioning_method(self):
        """Get the selected partitioning method.

        Return partitioning method according to which method selection
        radio button is currently active.
        """
        if self._custom_part_radio_button.get_active():
            return PARTITIONING_METHOD_INTERACTIVE

        if self._blivet_gui_radio_button.get_active():
            return PARTITIONING_METHOD_BLIVET

        return PARTITIONING_METHOD_AUTOMATIC

    def on_method_toggled(self, radio_button):
        """Triggered when one of the partitioning method radio buttons is toggled."""
        # Run only for a visible active radio button.
        if not radio_button.get_visible() or not radio_button.get_active():
            return

        # Get the selected patitioning method.
        current_partitioning_method = self._get_selected_partitioning_method()

        # Hide the encryption checkbox for Blivet GUI storage configuration,
        # as Blivet GUI handles encryption per encrypted device, not globally.
        # Hide it also for the interactive partitioning as CustomPartitioningSpoke
        # provides support for encryption of mount points.
        self._encryption_revealer.set_reveal_child(
            current_partitioning_method == PARTITIONING_METHOD_AUTOMATIC
        )

        # Hide the reclaim space checkbox if automatic storage configuration is not used.
        self._reclaim_revealer.set_reveal_child(
            current_partitioning_method == PARTITIONING_METHOD_AUTOMATIC
        )

        # Is this a change from the last used method ?
        method_changed = current_partitioning_method != self._last_partitioning_method

        # Are there any actions planned ?
        if self._storage_module.AppliedPartitioning:
            if method_changed:
                # clear any existing messages from the info bar
                # - this generally means various storage related error warnings
                self.clear_info()
                self.set_warning(_("Partitioning method changed - planned storage configuration "
                                   "changes will be cancelled."))
            else:
                self.clear_info()
                # reinstate any errors that should be shown to the user
                self._check_problems()

    def apply(self):
        self._disk_init_module.SetInitializationMode(CLEAR_PARTITIONS_NONE)
        self._disk_init_module.SetInitializeLabelsEnabled(True)
        apply_disk_selection(self._selected_disks, reset_boot_drive=True)

    @async_action_nowait
    def execute(self):
        """Apply a partitioning."""
        # Make sure that we apply a non-interactive partitioning.
        if self._last_partitioning_method == PARTITIONING_METHOD_INTERACTIVE:
            log.debug("Skipping the execute method for the INTERACTIVE partitioning method.")
            return

        if self._last_partitioning_method == PARTITIONING_METHOD_BLIVET:
            log.debug("Skipping the execute method for the BLIVET partitioning method.")
            return

        log.debug("Running the execute method for the %s partitioning method.",
                  self._last_partitioning_method)

        # Spawn storage execution as a separate thread so there's no big delay
        # going back from this spoke to the hub while StorageCheckHandler.run runs.
        # Yes, this means there's a thread spawning another thread.  Sorry.
        threadMgr.add(AnacondaThread(
            name=constants.THREAD_EXECUTE_STORAGE,
            target=self._do_execute
        ))

    def _do_execute(self):
        """Apply a non-interactive partitioning."""
        self._ready = False
        hubQ.send_not_ready(self.__class__.__name__)

        report = apply_partitioning(self._partitioning, self._show_execute_message)

        log.debug("Partitioning has been applied: %s", report)
        StorageCheckHandler.errors = list(report.error_messages)
        StorageCheckHandler.warnings = list(report.warning_messages)

        self._ready = True
        hubQ.send_ready(self.__class__.__name__)

    def _show_execute_message(self, msg):
        hubQ.send_message(self.__class__.__name__, msg)
        log.debug(msg)

    @property
    def completed(self):
        return self.ready and not self.errors and self._device_tree.GetRootDevice()

    @property
    def ready(self):
        # By default, the storage spoke is not ready.  We have to wait until
        # storageInitialize is done.
        return self._ready \
            and not threadMgr.get(constants.THREAD_STORAGE) \
            and not threadMgr.get(constants.THREAD_DASDFMT) \
            and not threadMgr.get(constants.THREAD_EXECUTE_STORAGE)

    @property
    def status(self):
        """ A short string describing the current status of storage setup. """
        if not self.ready:
            return _("Processing...")
        elif flags.automatedInstall and not self._device_tree.GetRootDevice():
            return _("Kickstart insufficient")
        elif not self._disk_select_module.SelectedDisks:
            return _("No disks selected")
        elif self.errors:
            return _("Error checking storage configuration")
        elif self.warnings:
            return _("Warning checking storage configuration")
        elif self._last_partitioning_method == PARTITIONING_METHOD_AUTOMATIC:
            return _("Automatic partitioning selected")
        else:
            return _("Custom partitioning selected")

    @property
    def local_overviews(self):
        return self._local_disks_box.get_children()

    @property
    def advanced_overviews(self):
        return [
            child for child in self._specialized_disks_box.get_children()
            if isinstance(child, AnacondaWidgets.DiskOverview)
        ]

    def _on_disk_clicked(self, overview, event):
        # This handler only runs for these two kinds of events, and only for
        # activate-type keys (space, enter) in the latter event's case.
        if event.type not in [Gdk.EventType.BUTTON_PRESS, Gdk.EventType.KEY_RELEASE]:
            return

        if event.type == Gdk.EventType.KEY_RELEASE and \
           event.keyval not in [Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_ISO_Enter,
                                Gdk.KEY_KP_Enter, Gdk.KEY_KP_Space]:
            return

        if event.type == Gdk.EventType.BUTTON_PRESS and \
                event.state & Gdk.ModifierType.SHIFT_MASK:
            # clicked with Shift held down

            if self._last_clicked_overview is None:
                # nothing clicked before, cannot apply Shift-click
                return

            local_overviews = self.local_overviews
            advanced_overviews = self.advanced_overviews

            # find out which list of overviews the clicked one belongs to
            if overview in local_overviews:
                from_overviews = local_overviews
            elif overview in advanced_overviews:
                from_overviews = advanced_overviews
            else:
                # should never happen, but if it does, no other actions should be done
                return

            if self._last_clicked_overview in from_overviews:
                # get index of the last clicked overview
                last_idx = from_overviews.index(self._last_clicked_overview)
            else:
                # overview from the other list clicked before, cannot apply "Shift-click"
                return

            # get index and state of the clicked overview
            cur_idx = from_overviews.index(overview)
            state = self._last_clicked_overview.get_chosen()

            if cur_idx > last_idx:
                copy_to = from_overviews[last_idx:cur_idx+1]
            else:
                copy_to = from_overviews[cur_idx:last_idx]

            # copy the state of the last clicked overview to the ones between it and the
            # one clicked with the Shift held down
            for disk_overview in copy_to:
                disk_overview.set_chosen(state)

        self._update_disk_list()
        self._update_summary()

    def _on_disk_focus_in(self, overview, event):
        self._last_clicked_overview = self._cur_clicked_overview
        self._cur_clicked_overview = overview

    def refresh(self):
        self._back_clicked = False

        self._available_disks = self._disk_select_module.GetUsableDisks()
        self._selected_disks = self._disk_select_module.SelectedDisks

        # Get the available selected disks.
        self._selected_disks = filter_disks_by_names(self._available_disks, self._selected_disks)

        # First, remove all non-button children.
        for child in self.local_overviews + self.advanced_overviews:
            child.destroy()

        # Then deal with local disks, which are really easy.  They need to be
        # handled here instead of refresh to take into account the user pressing
        # the rescan button on custom partitioning.
        # Advanced disks are different.  Because there can potentially be a lot
        # of them, we do not display them in the box by default.  Instead, only
        # those selected in the filter UI are displayed.  This means refresh
        # needs to know to create and destroy overviews as appropriate.
        for device_name in self._available_disks:

            # Get the device data.
            device_data = DeviceData.from_structure(
                self._device_tree.GetDeviceData(device_name)
            )

            if is_local_disk(device_data.type):
                # Add all available local disks.
                self._add_disk_overview(device_data, self._local_disks_box)

            elif device_name in self._selected_disks:
                # Add only selected advanced disks.
                self._add_disk_overview(device_data, self._specialized_disks_box)

        # update the selections in the ui
        for overview in self.local_overviews + self.advanced_overviews:
            name = overview.get_property("name")
            overview.set_chosen(name in self._selected_disks)

        # Update the encryption checkbox.
        if self._partitioning_request.encrypted:
            self._encrypted_checkbox.set_active(True)

        self._update_summary()
        self._check_problems()

    def _check_problems(self):
        if self.errors:
            self.set_warning(_("Error checking storage configuration.  "
                               "<a href=\"\">Click for details.</a>"))
            return True
        elif self.warnings:
            self.set_warning(_("Warning checking storage configuration.  "
                               "<a href=\"\">Click for details.</a>"))
            return True
        return False

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()

        # Connect the viewport adjustments to the child widgets
        # See also https://bugzilla.gnome.org/show_bug.cgi?id=744721
        self._local_disks_box.set_focus_hadjustment(
            Gtk.Scrollable.get_hadjustment(self._local_viewport))

        self._specialized_disks_box.set_focus_hadjustment(
            Gtk.Scrollable.get_hadjustment(self._specialized_viewport))

        self._main_box.set_focus_vadjustment(
            Gtk.Scrollable.get_vadjustment(self._main_viewport))

        threadMgr.add(AnacondaThread(name=constants.THREAD_STORAGE_WATCHER,
                                     target=self._initialize))

    def _add_disk_overview(self, device_data, box):
        if device_data.type == "dm-multipath":
            # We don't want to display the whole huge WWID for a multipath device.
            wwn = device_data.attrs.get("wwn", "")
            description = wwn[0:6] + "..." + wwn[-8:]
        elif device_data.type == "zfcp":
            # Manually mangle the desc of a zFCP device to be multi-line since
            # it's so long it makes the disk selection screen look odd.
            description = _("FCP device {hba_id}\nWWPN {wwpn}\nLUN {lun}").format(
                hba_id=device_data.attrs.get("hba-id", ""),
                wwpn=device_data.attrs.get("wwpn", ""),
                lun=device_data.attrs.get("fcp-lun", "")
            )
        elif device_data.type == "nvdimm":
            description = _("NVDIMM device {namespace}").format(
                namespace=device_data.attrs.get("namespace", "")
            )
        else:
            description = device_data.description

        kind = "drive-removable-media" if device_data.removable else "drive-harddisk"
        free_space = self._device_tree.GetDiskFreeSpace([device_data.name])
        serial_number = device_data.attrs.get("serial") or None

        overview = AnacondaWidgets.DiskOverview(
            description,
            kind,
            str(Size(device_data.size)),
            _("{} free").format(str(Size(free_space))),
            device_data.name,
            serial_number
        )

        box.pack_start(overview, False, False, 0)
        overview.set_chosen(device_data.name in self._selected_disks)
        overview.connect("button-press-event", self._on_disk_clicked)
        overview.connect("key-release-event", self._on_disk_clicked)
        overview.connect("focus-in-event", self._on_disk_focus_in)
        overview.show_all()

    def _initialize(self):
        """Finish the initialization.

        This method is expected to run only once during the initialization.
        """
        # Wait for storage.
        hubQ.send_message(self.__class__.__name__, _(constants.PAYLOAD_STATUS_PROBING_STORAGE))
        threadMgr.wait(constants.THREAD_STORAGE)

        # Automatically format DASDs if allowed.
        disks = self._disk_select_module.GetUsableDisks()
        DasdFormatting.run_automatically(disks, self._show_dasdfmt_report)
        hubQ.send_message(self.__class__.__name__, _(constants.PAYLOAD_STATUS_PROBING_STORAGE))

        # Update the selected disks.
        select_default_disks()

        # Automatically apply the preconfigured partitioning.
        # Do not set ready in the automated installation before
        # the execute method is run.
        if flags.automatedInstall and self._is_preconfigured:
            self._check_required_passphrase()
            self.execute()
        else:
            self._ready = True
            hubQ.send_ready(self.__class__.__name__)

        # Report that the storage spoke has been initialized.
        self.initialize_done()

    def _show_dasdfmt_report(self, msg):
        hubQ.send_message(self.__class__.__name__, msg)

    @async_action_wait
    def _check_required_passphrase(self):
        """Ask a user for a default passphrase if required."""
        if not is_passphrase_required(self._partitioning):
            return

        dialog = PassphraseDialog(self.data)

        # Use MainWindow.get() instead of self.main_window,
        # because the main_window property returns SpokeWindow
        # instead of MainWindow during the initialization.
        # We need the main window for showing the enlight box.
        with MainWindow.get().enlightbox(dialog.window):
            rc = dialog.run()

        if rc != 1:
            return

        set_required_passphrase(self._partitioning, dialog.passphrase)

    def _update_summary(self):
        """ Update the summary based on the UI. """
        disks = filter_disks_by_names(self._available_disks, self._selected_disks)
        summary = get_disks_summary(disks)

        summary_label = self.builder.get_object("summary_label")
        summary_label.set_text(summary)

        is_selected = bool(self._selected_disks)
        summary_label.set_sensitive(is_selected)

        # only show the "we won't touch your other disks" labels and summary button when
        # some disks are selected
        self.builder.get_object("summary_button_revealer").set_reveal_child(is_selected)
        self.builder.get_object("local_untouched_label_revealer").set_reveal_child(is_selected)
        self.builder.get_object("special_untouched_label_revealer").set_reveal_child(is_selected)
        self.builder.get_object("other_options_grid").set_sensitive(is_selected)

        if not self._available_disks:
            self.set_warning(_(WARNING_NO_DISKS_DETECTED))
        elif not self._selected_disks:
            # There may be an underlying reason that no disks were selected, give them priority.
            if not self._check_problems():
                self.set_warning(_(WARNING_NO_DISKS_SELECTED))
        else:
            self.clear_info()

    def _update_disk_list(self):
        """ Update self.selected_disks based on the UI. """
        for overview in self.local_overviews + self.advanced_overviews:
            selected = overview.get_chosen()
            name = overview.get_property("name")

            if selected and name not in self._selected_disks:
                self._selected_disks.append(name)

            if not selected and name in self._selected_disks:
                self._selected_disks.remove(name)

    # signal handlers
    def on_summary_clicked(self, button):
        # show the selected disks dialog
        disks = filter_disks_by_names(self._available_disks, self._selected_disks)
        dialog = SelectedDisksDialog(self.data, disks)
        dialog.refresh()

        self.run_lightbox_dialog(dialog)

        # update selected disks since some may have been removed
        self._selected_disks = list(dialog.disks)

        # update the UI to reflect changes to self.selected_disks
        for overview in self.local_overviews + self.advanced_overviews:
            name = overview.get_property("name")
            overview.set_chosen(name in self._selected_disks)

        self._update_summary()

        if self._bootloader_module.BootloaderMode != BOOTLOADER_ENABLED:
            self.set_warning(_("You have chosen to skip boot loader installation. "
                               "Your system may not be bootable."))
        else:
            self.clear_info()

    def run_lightbox_dialog(self, dialog):
        with self.main_window.enlightbox(dialog.window):
            rc = dialog.run()

        return rc

    def _check_dasd_formats(self):
        # No change by default.
        rc = DASD_FORMAT_NO_CHANGE

        # Do nothing if unsupported.
        if not DasdFormatting.is_supported():
            return rc

        # Allow to format DASDs.
        self._disk_init_module.SetFormatUnrecognizedEnabled(True)
        self._disk_init_module.SetFormatLDLEnabled(True)

        # Get selected disks.
        disks = filter_disks_by_names(self._available_disks, self._selected_disks)

        # Check if some of the disks should be formatted.
        dasd_formatting = DasdFormatting()
        dasd_formatting.search_disks(disks)

        if dasd_formatting.should_run():
            # We want to apply current selection before running dasdfmt to
            # prevent this information from being lost afterward
            apply_disk_selection(self._selected_disks)

            # Run the dialog.
            dialog = DasdFormatDialog(self.data, dasd_formatting)
            ignoreEscape(dialog.window)
            rc = self.run_lightbox_dialog(dialog)

        return rc

    def _check_space_and_run_dialog(self, partitioning, disks):
        # User wants to reclaim the space.
        if self._reclaim_checkbox.get_active():
            return RESPONSE_RECLAIM

        # Get the device tree of the partitioning module.
        device_tree = STORAGE.get_proxy(partitioning.GetDeviceTree())

        # Calculate the required and free space.
        disk_free = Size(device_tree.GetDiskFreeSpace(disks))
        fs_free = Size(device_tree.GetDiskReclaimableSpace(disks))
        disks_size = Size(device_tree.GetDiskTotalSpace(disks))
        sw_space = Size(self.payload.space_required)
        auto_swap = suggest_swap_size()

        log.debug("disk free: %s  fs free: %s  sw needs: %s  auto swap: %s",
                  disk_free, fs_free, sw_space, auto_swap)

        # We need enough space for the software, the swap and the metadata.
        # It is not an ideal estimate, but it works.
        required_space = sw_space + auto_swap + STORAGE_METADATA_RATIO * disk_free

        # There is enough space to continue.
        if disk_free >= required_space:
            return RESPONSE_OK

        # Ask user what to do.
        if disks_size >= required_space - auto_swap:
            dialog = NeedSpaceDialog(self.data, payload=self.payload)
            dialog.refresh(required_space, sw_space, auto_swap, disk_free, fs_free)
        else:
            dialog = NoSpaceDialog(self.data, payload=self.payload)
            dialog.refresh(required_space, sw_space, auto_swap, disk_free, fs_free)

        return self.run_lightbox_dialog(dialog)

    def on_back_clicked(self, button):
        if self._back_clicked:
            return

        # Skip if user is clicking multiple times on the back button.
        self._back_clicked = True

        # Clear the current warning message if any.
        self.clear_info()

        # No disks selected?  The user wants to back out of the storage spoke.
        if not self._selected_disks:
            NormalSpoke.on_back_clicked(self, button)
            return

        # Reset to a snapshot if necessary.
        self._reset_to_snapshot()

        # The disk selection has to make sense before we can proceed.
        if not self._check_disk_selection():
            self._back_clicked = False
            return

        # Check for unsupported DASDs.
        rc = self._check_dasd_formats()
        if rc == DASD_FORMAT_NO_CHANGE:
            pass
        elif rc == DASD_FORMAT_REFRESH:
            # User hit OK on the dialog
            self.refresh()
        elif rc == DASD_FORMAT_RETURN_TO_HUB:
            # User clicked uri to return to hub.
            NormalSpoke.on_back_clicked(self, button)
            return
        else:
            # User either hit cancel on the dialog or closed
            # it via escape, there was no formatting done.
            self._back_clicked = False
            return

        # Handle the partitioning.
        partitioning_method = self._get_selected_partitioning_method()
        self._last_partitioning_method = partitioning_method

        if partitioning_method == PARTITIONING_METHOD_AUTOMATIC:
            self._skip_to_automatic_partitioning()
            return

        if partitioning_method == PARTITIONING_METHOD_INTERACTIVE:
            self._skip_to_spoke("CustomPartitioningSpoke")
            return

        if partitioning_method == PARTITIONING_METHOD_BLIVET:
            self._skip_to_spoke("BlivetGuiSpoke")
            return

        self._back_clicked = False
        return

    def _reset_to_snapshot(self):
        # Can we reset the storage configuration?
        reset = False

        # Changing disk selection is really, really complicated and has
        # always been causing numerous hard bugs. Let's not play the hero
        # game and just revert everything and start over again.
        disks = self._last_selected_disks
        current_disks = set(self._selected_disks)
        self._last_selected_disks = set(current_disks)

        if disks and disks != current_disks:
            log.info("Disk selection has changed.")
            reset = True

        method = self._last_partitioning_method
        current_method = self._get_selected_partitioning_method()
        self._last_partitioning_method = current_method

        # Same thing for switching between different storage configuration
        # methods (auto/custom/blivet-gui), at least for now.
        if method != current_method:
            log.info("Partitioning method has changed from %s to %s.",
                     method, current_method)
            reset = True

        # Reset the storage configuration if necessary.
        # FIXME: Reset only the partitioning that we will use.
        if reset:
            log.info("Rolling back planed storage configuration changes.")
            self._storage_module.ResetPartitioning()

    def _check_disk_selection(self):
        # If there are some disk selection errors we don't let user to leave
        # the spoke, so these errors don't have to go to self.errors.
        report = ValidationReport.from_structure(
            self._disk_select_module.ValidateSelectedDisks(self._selected_disks)
        )

        if not report.is_valid():
            self._disks_errors = report.get_messages()
            self.set_error(_("There was a problem with your disk selection. "
                             "Click here for details."))
            return False

        self._disks_errors = []
        return True

    def _skip_to_spoke(self, name, apply_on_skip=True):
        """Skip to a spoke.

        The user has requested to skip to different spoke or to the
        summary hub.

        :param name: a name of the spoke or None to return to the hub
        :param apply_on_skip: should we call apply?
        """
        self.skipTo = name
        self.applyOnSkip = apply_on_skip
        NormalSpoke.on_back_clicked(self, None)

    def _skip_to_automatic_partitioning(self):
        """Skip to the automatic partitioning.

        The user has requested to create the partitioning automatically.
        Ask for missing information and set up the automatic partitioning,
        so it can be later applied in the execute method.
        """
        # Set up the encryption.
        self._partitioning_request.encrypted = self._encrypted_checkbox.get_active()

        # Ask for a passphrase.
        if self._partitioning_request.encrypted:
            dialog = PassphraseDialog(
                self.data,
                self._partitioning_request.passphrase
            )

            rc = self.run_lightbox_dialog(dialog)
            if rc != 1:
                self._back_clicked = False
                return

            self._partitioning_request.passphrase = dialog.passphrase

        # Set up the disk selection and initialization.
        self.apply()

        # Use the automatic partitioning and reset it.
        self._partitioning = create_partitioning(PARTITIONING_METHOD_AUTOMATIC)

        self._partitioning.SetRequest(
            PartitioningRequest.to_structure(self._partitioning_request)
        )

        # Reclaim space.
        disks = filter_disks_by_names(self._available_disks, self._selected_disks)
        rc = self._check_space_and_run_dialog(self._partitioning, disks)

        if rc == RESPONSE_RECLAIM:
            dialog = ResizeDialog(self.data, self.payload, self._partitioning, disks)
            dialog.refresh()
            rc = self.run_lightbox_dialog(dialog)

        # Plan the next action.
        if rc == RESPONSE_OK:
            # nothing special needed
            self._skip_to_spoke(None)
            return

        if rc == RESPONSE_CANCEL:
            # A cancel button was clicked on one of the dialogs.  Stay on this
            # spoke.  Generally, this is because the user wants to add more disks.
            self._back_clicked = False
            return

        if rc == RESPONSE_MODIFY_SW:
            # The "Fedora software selection" link was clicked on one of the
            # dialogs.  Send the user to the software spoke.
            self._skip_to_spoke("SoftwareSelectionSpoke")
            return

        if rc == RESPONSE_QUIT:
            # Not enough space, and the user can't do anything about it so
            # they chose to quit.
            raise SystemExit("user-selected exit")

        # I don't know how we'd get here, but might as well have a
        # catch-all.  Just stay on this spoke.
        self._back_clicked = False
        return

    def on_specialized_clicked(self, button):
        # Don't want to run apply or execute in this case, since we have to
        # collect some more disks first.  The user will be back to this spoke.
        self.applyOnSkip = False

        # However, we do want to apply current selections so the disk cart off
        # the filter spoke will display the correct information.
        apply_disk_selection(self._selected_disks)

        self.skipTo = "FilterSpoke"
        NormalSpoke.on_back_clicked(self, button)

    def on_info_bar_clicked(self, *args):
        if self._disks_errors:
            label = _("The following errors were encountered when checking your disk "
                      "selection. You can modify your selection or quit the "
                      "installer.")

            dialog = DetailedErrorDialog(self.data, buttons=[
                    C_("GUI|Storage|Error Dialog", "_Quit"),
                    C_("GUI|Storage|Error Dialog", "_Modify Disk Selection")],
                label=label)
            with self.main_window.enlightbox(dialog.window):
                errors = "\n".join(self._disks_errors)
                dialog.refresh(errors)
                rc = dialog.run()

            dialog.window.destroy()

            if rc == 0:
                # Quit.
                util.ipmi_abort(scripts=self.data.scripts)
                sys.exit(0)

        elif self.errors:
            label = _("The following errors were encountered when checking your storage "
                      "configuration.  You can modify your storage layout or quit the "
                      "installer.")

            dialog = DetailedErrorDialog(self.data, buttons=[
                    C_("GUI|Storage|Error Dialog", "_Quit"),
                    C_("GUI|Storage|Error Dialog", "_Modify Storage Layout")],
                label=label)
            with self.main_window.enlightbox(dialog.window):
                errors = "\n".join(self.errors)
                dialog.refresh(errors)
                rc = dialog.run()

            dialog.window.destroy()

            if rc == 0:
                # Quit.
                util.ipmi_abort(scripts=self.data.scripts)
                sys.exit(0)
        elif self.warnings:
            label = _("The following warnings were encountered when checking your storage "
                      "configuration.  These are not fatal, but you may wish to make "
                      "changes to your storage layout.")

            dialog = DetailedErrorDialog(self.data,
                    buttons=[C_("GUI|Storage|Warning Dialog", "_OK")], label=label)
            with self.main_window.enlightbox(dialog.window):
                warnings = "\n".join(self.warnings)
                dialog.refresh(warnings)
                rc = dialog.run()

            dialog.window.destroy()

    def on_disks_key_released(self, box, event):
        # we want to react only on Ctrl-A being pressed
        if not bool(event.state & Gdk.ModifierType.CONTROL_MASK) or \
                (event.keyval not in (Gdk.KEY_a, Gdk.KEY_A)):
            return

        # select disks in the right box
        if box is self._local_disks_box:
            overviews = self.local_overviews
        elif box is self._specialized_disks_box:
            overviews = self.advanced_overviews
        else:
            # no other box contains disk overviews
            return

        for overview in overviews:
            overview.set_chosen(True)

        self._update_disk_list()
        self._update_summary()

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
            # until rescanning completed.
            self.refresh()
            return
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
