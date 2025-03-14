# Software selection spoke classes
#
# Copyright (C) 2011-2013  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import sys

import gi

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    PAYLOAD_STATUS_CHECKING_SOFTWARE,
    PAYLOAD_TYPE_DNF,
    THREAD_CHECK_SOFTWARE,
    THREAD_PAYLOAD,
    THREAD_SOFTWARE_WATCHER,
)
from pyanaconda.core.i18n import C_, CN_, _
from pyanaconda.core.threads import thread_manager
from pyanaconda.core.util import ipmi_abort
from pyanaconda.flags import flags
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.context import context
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.detailederror import DetailedErrorDialog
from pyanaconda.ui.gui.spokes.lib.software_selection import (
    EnvironmentListBoxRow,
    GroupListBoxRow,
    SeparatorRow,
)
from pyanaconda.ui.gui.utils import escape_markup
from pyanaconda.ui.lib.software import (
    FEATURE_64K,
    KernelFeatures,
    SoftwareSelectionCache,
    get_available_kernel_features,
    get_environment_data,
    get_group_data,
    get_kernel_from_properties,
    get_kernel_titles_and_descriptions,
    get_software_selection_status,
    is_software_selection_complete,
)
from pyanaconda.ui.lib.subscription import is_cdn_registration_required

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

log = get_module_logger(__name__)

__all__ = ["SoftwareSelectionSpoke"]


class SoftwareSelectionSpoke(NormalSpoke):
    """
       .. inheritance-diagram:: SoftwareSelectionSpoke
          :parts: 3
    """
    builderObjects = ["addonStore", "environmentStore", "softwareWindow"]
    mainWidgetName = "softwareWindow"
    uiFile = "spokes/software_selection.glade"
    category = SoftwareCategory
    icon = "package-x-generic-symbolic"
    title = CN_("GUI|Spoke", "_Software Selection")

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "software-selection"

    @classmethod
    def should_run(cls, environment, data):
        """Don't run for any non-package payload."""
        if not NormalSpoke.should_run(environment, data):
            return False

        return context.payload_type == PAYLOAD_TYPE_DNF

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._errors = []
        self._warnings = []

        # Get the packages selection data.
        self._selection_cache = SoftwareSelectionCache(self.payload.proxy)
        self._kickstarted = flags.automatedInstall and self.payload.proxy.PackagesKickstarted

        # Get the UI elements.
        self._environment_list_box = self.builder.get_object("environmentListBox")
        self._addon_list_box = self.builder.get_object("addonListBox")

        # Connect viewport scrolling with listbox focus events
        environment_viewport = self.builder.get_object("environmentViewport")
        self._environment_list_box.set_focus_vadjustment(
            Gtk.Scrollable.get_vadjustment(environment_viewport)
        )

        addon_viewport = self.builder.get_object("addonViewport")
        self._addon_list_box.set_focus_vadjustment(
            Gtk.Scrollable.get_vadjustment(addon_viewport)
        )

        # Display a group of options for selecting desired properties of a kernel
        self._kernel_box = self.builder.get_object("kernelBox")
        self._combo_kernel_page_size = self.builder.get_object("kernelPageSizeCombo")
        self._label_kernel_page_size = self.builder.get_object("kernelPageSizeLabel")

        # Normally I would create these in the .glade file but due to a bug they weren't
        # created properly
        self._model_kernel_page_size = Gtk.ListStore(str, str)

        kernel_labels = get_kernel_titles_and_descriptions()
        for i in ["4k", "64k"]:
            self._model_kernel_page_size.append([i, "<b>%s</b>\n%s" %
                                                (escape_markup(kernel_labels[i][0]),
                                                 escape_markup(kernel_labels[i][1]))])
        self._combo_kernel_page_size.set_model(self._model_kernel_page_size)
        self._available_kernels = get_available_kernel_features(self.payload.proxy)

    @property
    def _selection(self):
        """The packages selection."""
        return self.payload.get_packages_selection()

    def initialize(self):
        """Initialize the spoke."""
        super().initialize()
        self.initialize_start()

        thread_manager.add_thread(
            name=THREAD_SOFTWARE_WATCHER,
            target=self._initialize
        )

    def _initialize(self):
        """Initialize the spoke in a separate thread."""
        thread_manager.wait(THREAD_PAYLOAD)

        # Initialize and check the software selection.
        self._initialize_selection()

        # Update the status.
        hubQ.send_ready(self.__class__.__name__)

        # Report that the software spoke has been initialized.
        self.initialize_done()

    def _initialize_selection(self):
        """Initialize and check the software selection."""
        if not self.payload.is_ready():
            log.debug("Skip the initialization of the software selection.")
            return

        if not self._kickstarted:
            # Use the default environment.
            self._selection_cache.select_environment(
                self.payload.proxy.GetDefaultEnvironment()
            )

            # Apply the default selection.
            self.apply()

        # Check the initial software selection.
        self.execute()

        # Wait for the software selection thread that might be started by execute().
        # We are already running in a thread, so it should not needlessly block anything
        # and only like this we can be sure we are really initialized.
        thread_manager.wait(THREAD_CHECK_SOFTWARE)

    @property
    def ready(self):
        """Is the spoke ready?

        By default, the software selection spoke is not ready. We have to
        wait until the installation source spoke is completed. This could be
        because the user filled something out, or because we're done fetching
        repo metadata from the mirror list, or we detected a DVD/CD.
        """
        return not self._processing_data and self._source_is_set

    @property
    def _source_is_set(self):
        """Is the installation source set?"""
        return self.payload.is_ready()

    @property
    def _source_has_changed(self):
        """Has the installation source changed?"""
        return self.payload.software_validation_required

    @property
    def _processing_data(self):
        """Is the spoke processing data?"""
        return thread_manager.get(THREAD_SOFTWARE_WATCHER) \
            or thread_manager.get(THREAD_PAYLOAD) \
            or thread_manager.get(THREAD_CHECK_SOFTWARE)

    @property
    def status(self):
        """The status of the spoke."""
        if self._processing_data:
            return _("Processing...")
        if is_cdn_registration_required(self.payload):
            return _("Red Hat CDN requires registration.")
        if not self._source_is_set:
            return _("Installation source not set up")
        if self._source_has_changed:
            return _("Source changed - please verify")
        if self._errors:
            return _("Error checking software selection")
        if self._warnings:
            return _("Warning checking software selection")

        return get_software_selection_status(
            dnf_proxy=self.payload.proxy,
            selection=self._selection,
            kickstarted=self._kickstarted
        )

    @property
    def completed(self):
        """Is the spoke complete?"""
        return self.ready \
            and not self._errors \
            and not self._source_has_changed \
            and is_software_selection_complete(
                dnf_proxy=self.payload.proxy,
                selection=self._selection,
                kickstarted=self._kickstarted
            )

    def refresh(self):
        super().refresh()
        thread_manager.wait(THREAD_PAYLOAD)

        # Create a new software selection cache.
        self._selection_cache = SoftwareSelectionCache(self.payload.proxy)
        self._selection_cache.apply_selection_data(self._selection)
        self._available_kernels = get_available_kernel_features(self.payload.proxy)

        # Refresh up the UI.
        self._refresh_environments()
        self._refresh_groups()
        self._refresh_kernel_features()

        # Set up the info bar.
        self.clear_info()

        if self._errors:
            self.set_warning(_(
                "Error checking software dependencies. "
                " <a href=\"\">Click for details.</a>"
            ))
        elif self._warnings:
            self.set_warning(_(
                "Warning checking software dependencies. "
                " <a href=\"\">Click for details.</a>"
            ))

    def _refresh_environments(self):
        """Create rows for all available environments."""
        self._clear_listbox(self._environment_list_box)

        for environment in self._selection_cache.available_environments:
            # Get the environment data.
            data = get_environment_data(self.payload.proxy, environment)
            selected = self._selection_cache.is_environment_selected(environment)

            # Add a new environment row.
            row = EnvironmentListBoxRow(data, selected)
            self._environment_list_box.insert(row, -1)

        self._environment_list_box.show_all()

    def _refresh_groups(self):
        """Create rows for all available groups."""
        self._clear_listbox(self._addon_list_box)

        if self._selection_cache.environment:
            # Get the environment data.
            environment_data = get_environment_data(
                dnf_proxy=self.payload.proxy,
                environment_name=self._selection_cache.environment,
            )

            # Add all optional groups.
            for group in environment_data.optional_groups:
                self._add_group_row(group)

            # Add the separator.
            if environment_data.optional_groups and environment_data.visible_groups:
                self._addon_list_box.insert(SeparatorRow(), -1)

            # Add user visible groups that are not optional.
            for group in environment_data.visible_groups:
                if group in environment_data.optional_groups:
                    continue

                self._add_group_row(group)

        self._addon_list_box.show_all()

    def _add_group_row(self, group):
        """Add a new row for the specified group."""
        # Get the group data.
        data = get_group_data(self.payload.proxy, group)
        selected = self._selection_cache.is_group_selected(group)

        # Add a new group row.
        row = GroupListBoxRow(data, selected)
        self._addon_list_box.insert(row, -1)

    def _clear_listbox(self, listbox):
        for child in listbox.get_children():
            listbox.remove(child)
            del child

    def _refresh_kernel_features(self):
        """Display options for selecting kernel features."""

        # Only showing parts of kernel box relevant for current system.
        self._available_kernels = get_available_kernel_features(self.payload.proxy)

        show_kernels = False
        if conf.ui.show_kernel_options:
            for (_key, val) in self._available_kernels.items():
                if val:
                    show_kernels = True
                    break

        if show_kernels:
            self._kernel_box.set_visible(True)
            self._kernel_box.set_no_show_all(False)

            # Arm 64k page size kernel combo
            self._combo_kernel_page_size.set_visible(self._available_kernels[FEATURE_64K])
            self._combo_kernel_page_size.set_no_show_all(not self._available_kernels[FEATURE_64K])
            self._label_kernel_page_size.set_visible(self._available_kernels[FEATURE_64K])
            self._label_kernel_page_size.set_no_show_all(not self._available_kernels[FEATURE_64K])
        else:
            # Hide the entire box.
            self._kernel_box.set_visible(False)
            self._kernel_box.set_no_show_all(True)

    def apply(self):
        """Apply the changes."""
        self._kickstarted = False

        selection = self._selection_cache.get_selection_data()
        log.debug("Setting new software selection: %s", selection)

        # Select kernel
        property_64k = self._available_kernels[FEATURE_64K] and \
            self._combo_kernel_page_size.get_active_id() == FEATURE_64K
        kernel_properties = KernelFeatures(property_64k)
        kernel = get_kernel_from_properties(kernel_properties)
        if kernel is not None and conf.ui.show_kernel_options:
            log.debug("Selected kernel package: %s", kernel)
            selection.packages.append(kernel)
            selection.excluded_packages.append("kernel")

        self.payload.set_packages_selection(selection)

        hubQ.send_not_ready(self.__class__.__name__)
        hubQ.send_not_ready("SourceSpoke")

    def execute(self):
        """Execute the changes."""
        thread_manager.add_thread(
            name=THREAD_CHECK_SOFTWARE,
            target=self._check_software_selection
        )

    def _check_software_selection(self):
        hubQ.send_message(self.__class__.__name__, _(PAYLOAD_STATUS_CHECKING_SOFTWARE))
        report = self.payload.check_software_selection(self._selection)
        self._errors = list(report.error_messages)
        self._warnings = list(report.warning_messages)

        hubQ.send_ready(self.__class__.__name__)
        hubQ.send_ready("SourceSpoke")

    # Signal handlers
    def on_environment_activated(self, listbox, row):
        if not isinstance(row, EnvironmentListBoxRow):
            return

        # Mark the environment as selected.
        environment = row.get_environment_id()
        self._selection_cache.select_environment(environment)

        # Update the row button.
        row.toggle_button(True)

        # Update the screen.
        self._refresh_groups()

    def on_addon_activated(self, listbox, row):
        # Skip the separator.
        if not isinstance(row, GroupListBoxRow):
            return

        # Mark the group as selected or deselected.
        group = row.get_group_id()
        selected = not self._selection_cache.is_group_selected(group)

        if selected:
            self._selection_cache.select_group(row.data.id)
        else:
            self._selection_cache.deselect_group(row.data.id)

        # Update the row button.
        row.toggle_button(selected)

    def on_info_bar_clicked(self, *args):
        if self._errors:
            self._show_error_dialog()
        elif self._warnings:
            self._show_warning_dialog()

    def _show_error_dialog(self):
        label = _(
            "The software marked for installation has the following errors.  "
            "This is likely caused by an error with your installation source.  "
            "You can quit the installer, change your software source, or change "
            "your software selections."
        )

        buttons = [
            C_("GUI|Software Selection|Error Dialog", "_Quit"),
            C_("GUI|Software Selection|Error Dialog", "_Modify Software Source"),
            C_("GUI|Software Selection|Error Dialog", "Modify _Selections")
        ]

        dialog = DetailedErrorDialog(self.data, buttons=buttons, label=label)

        with self.main_window.enlightbox(dialog.window):
            errors = "\n".join(self._errors)
            dialog.refresh(errors)
            rc = dialog.run()

        dialog.window.destroy()

        if rc == 0:
            # Quit the installation.
            ipmi_abort(scripts=self.data.scripts)
            sys.exit(0)
        elif rc == 1:
            # Send the user to the installation source spoke.
            self.skipTo = "SourceSpoke"
            self.window.emit("button-clicked")

    def _show_warning_dialog(self):
        label = _(
            "The software marked for installation has the following warnings. "
            "These are not fatal, but you may wish to make changes to your "
            "software selections."
        )

        buttons = [
            C_("GUI|Software Selection|Warning Dialog", "_OK")
        ]

        dialog = DetailedErrorDialog(self.data, buttons=buttons, label=label)

        with self.main_window.enlightbox(dialog.window):
            warnings = "\n".join(self._warnings)
            dialog.refresh(warnings)
            dialog.run()

        dialog.window.destroy()
