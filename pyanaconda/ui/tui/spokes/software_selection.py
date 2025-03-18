# Software selection text spoke
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.flags import flags
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.context import context
from pyanaconda.ui.lib.software import get_software_selection_status, \
    is_software_selection_complete, SoftwareSelectionCache, get_group_data, get_environment_data
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.core.threads import thread_manager
from pyanaconda.ui.lib.software import FEATURE_64K, KernelFeatures, \
    get_kernel_from_properties, get_available_kernel_features, get_kernel_titles_and_descriptions
from pyanaconda.core.i18n import N_, _
from pyanaconda.core.constants import THREAD_PAYLOAD, THREAD_CHECK_SOFTWARE, \
    THREAD_SOFTWARE_WATCHER, PAYLOAD_TYPE_DNF
from pyanaconda.core.configuration.anaconda import conf

from simpleline.render.containers import ListColumnContainer
from simpleline.render.prompt import Prompt
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import TextWidget, CheckboxWidget

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["SoftwareSpoke"]


class SoftwareSpoke(NormalTUISpoke):
    """The spoke for choosing the software.

       .. inheritance-diagram:: SoftwareSpoke
          :parts: 3
    """
    category = SoftwareCategory

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "software-selection"

    @classmethod
    def should_run(cls, environment, data):
        """Don't run for any non-package payload."""
        if not NormalTUISpoke.should_run(environment, data):
            return False

        return context.payload_type == PAYLOAD_TYPE_DNF

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)
        self.title = N_("Software selection")
        self._container = None
        self._errors = []
        self._warnings = []

        # Get the packages configuration.
        self._selection_cache = SoftwareSelectionCache(self.payload.proxy)
        self._kernel_selection = None
        self._available_kernels = None

        # Are we taking values (package list) from a kickstart file?
        self._kickstarted = flags.automatedInstall and self.payload.proxy.PackagesKickstarted

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

        self._available_kernels = get_available_kernel_features(self.payload.proxy)
        self._kernel_selection = dict.fromkeys(self._available_kernels, False)

        # Initialize and check the software selection.
        self._initialize_selection()

        # Report that the software spoke has been initialized.
        self.initialize_done()

    def _initialize_selection(self):
        """Initialize and check the software selection."""
        if not self._source_is_set:
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

    def setup(self, args):
        """Set up the spoke right before it is used."""
        super().setup(args)

        # Wait for the payload to be ready.
        thread_manager.wait(THREAD_SOFTWARE_WATCHER)
        thread_manager.wait(THREAD_PAYLOAD)

        # Create a new software selection cache.
        self._selection_cache = SoftwareSelectionCache(self._payload.proxy)
        self._selection_cache.apply_selection_data(self._selection)

        return True

    def refresh(self, args=None):
        """ Refresh screen. """
        NormalTUISpoke.refresh(self, args)
        self._container = None

        if not self._source_is_set:
            message = TextWidget(_("Installation source needs to be set up first."))
            self.window.add_with_separator(message)
            return

        thread_manager.wait(THREAD_CHECK_SOFTWARE)
        self._container = ListColumnContainer(
            columns=2,
            columns_width=38,
            spacing=2
        )

        for environment in self._selection_cache.available_environments:
            data = get_environment_data(self.payload.proxy, environment)
            selected = self._selection_cache.is_environment_selected(environment)

            widget = CheckboxWidget(
                title=data.name,
                completed=selected
            )

            self._container.add(
                widget,
                callback=self._select_environment,
                data=data.id
            )

        self.window.add_with_separator(TextWidget(_("Base environment")))
        self.window.add_with_separator(self._container)

        if self._errors or self._warnings:
            messages = "\n".join(self._errors or self._warnings)
            self.window.add_with_separator(TextWidget(messages))

    def _select_environment(self, data):
        self._selection_cache.select_environment(data)

    def input(self, args, key):
        """Handle the user input."""
        if self._container is None:
            return super().input(args, key)

        if self._container.process_user_input(key):
            return InputState.PROCESSED_AND_REDRAW

        if key.lower() == Prompt.CONTINUE:
            if self._selection_cache.environment:
                # The environment was selected, switch the screen.
                spoke = AdditionalSoftwareSpoke(
                    self.data,
                    self.storage,
                    self.payload,
                    self._selection_cache,
                    self._kernel_selection
                )
                ScreenHandler.push_screen_modal(spoke)
                self.apply()
                self.execute()

            return InputState.PROCESSED_AND_CLOSE

        return super().input(args, key)

    def apply(self):
        """Apply the changes."""
        self._kickstarted = False

        selection = self._selection_cache.get_selection_data()
        log.debug("Setting new software selection: %s", selection)

        # Processing chosen kernel
        if conf.ui.show_kernel_options:
            self._available_kernels = get_available_kernel_features(self.payload.proxy)
            feature_64k = self._available_kernels[FEATURE_64K] and \
                self._kernel_selection[FEATURE_64K]
            features = KernelFeatures(feature_64k)
            kernel = get_kernel_from_properties(features)
            if kernel:
                log.debug("Selected kernel package: %s", kernel)
                selection.packages.append(kernel)
                selection.excluded_packages.append("kernel")

        log.debug("Setting new software selection: %s", self._selection)
        self.payload.set_packages_selection(selection)

    def execute(self):
        """Execute the changes."""
        thread_manager.add_thread(
            name=THREAD_CHECK_SOFTWARE,
            target=self._check_software_selection
        )

    def _check_software_selection(self):
        """Check the software selection."""
        report = self.payload.check_software_selection(self._selection)
        self._errors = list(report.error_messages)
        self._warnings = list(report.warning_messages)
        print("\n".join(report.get_messages()))

    def closed(self):
        """The spoke has been closed."""
        super().closed()

        # Run the setup method again on entry.
        self.screen_ready = False


class AdditionalSoftwareSpoke(NormalTUISpoke):
    """The spoke for choosing the additional software."""
    category = SoftwareCategory

    def __init__(self, data, storage, payload, selection_cache, kernel_selection):
        super().__init__(data, storage, payload)
        self.title = N_("Software selection")
        self._container = None
        self._selection_cache = selection_cache
        self._kernel_selection = kernel_selection

    def refresh(self, args=None):
        """Refresh the screen."""
        NormalTUISpoke.refresh(self, args)

        self._container = ListColumnContainer(
            columns=2,
            columns_width=38,
            spacing=2
        )

        for group in self._selection_cache.available_groups:
            data = get_group_data(self.payload.proxy, group)
            selected = self._selection_cache.is_group_selected(group)

            widget = CheckboxWidget(
                title=data.name,
                completed=selected
            )

            self._container.add(
                widget,
                callback=self._select_group,
                data=data.id
            )

        if self._selection_cache.available_groups:
            msg = _("Additional software for selected environment")
        else:
            msg = _("No additional software to select.")

        self.window.add_with_separator(TextWidget(msg))
        self.window.add_with_separator(self._container)

    def _select_group(self, group):
        if not self._selection_cache.is_group_selected(group):
            self._selection_cache.select_group(group)
        else:
            self._selection_cache.deselect_group(group)

    def _show_kernel_features_screen(self, kernels):
        """Returns True if at least one non-standard kernel is available.
        """
        if not conf.ui.show_kernel_options:
            return False
        for val in kernels.values():
            if val:
                return True
        return False

    def input(self, args, key):
        if self._container.process_user_input(key):
            return InputState.PROCESSED_AND_REDRAW
        if key.lower() == Prompt.CONTINUE:
            available_kernels = get_available_kernel_features(self.payload.proxy)
            if self._show_kernel_features_screen(available_kernels):
                spoke = KernelSelectionSpoke(self.data, self.storage, self.payload,
                                             self._selection_cache, self._kernel_selection,
                                             available_kernels)
                ScreenHandler.push_screen_modal(spoke)
            self.execute()
            self.close()
            return InputState.PROCESSED

        return super().input(args, key)

    def apply(self):
        pass


class KernelSelectionSpoke(NormalTUISpoke):
    """A subspoke for selecting kernel features.
    """
    def __init__(self, data, storage, payload, selection_cache,
                 _kernel_selection, available_kernels):
        super().__init__(data, storage, payload)
        self.title = N_("Kernel Options")
        self._container = None
        self._selection_cache = selection_cache
        self._kernel_selection = _kernel_selection
        self._available_kernels = available_kernels

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self)

        # Retrieving translated UI strings
        labels = get_kernel_titles_and_descriptions()

        # Updating kernel availability
        self._available_kernels = get_available_kernel_features(self.payload.proxy)
        self._container = ListColumnContainer(2, columns_width=38, spacing=2)

        # Rendering kernel checkboxes
        for (name, val) in self._kernel_selection.items():
            if not self._available_kernels[name]:
                continue
            (title, text) = labels[name]
            widget = CheckboxWidget(title="%s" % title, text="%s" % text, completed=val)
            self._container.add(widget, callback=self._set_kernel_callback, data=name)

        self.window.add_with_separator(TextWidget(_("Kernel options")))
        self.window.add_with_separator(self._container)

    def _set_kernel_callback(self, data):
        self._kernel_selection[data] = not self._kernel_selection[data]

    def input(self, args, key):
        if self._container.process_user_input(key):
            return InputState.PROCESSED_AND_REDRAW

        if key.lower() == Prompt.CONTINUE:
            self.close()
            return InputState.PROCESSED

        return super().input(args, key)

    def apply(self):
        pass
