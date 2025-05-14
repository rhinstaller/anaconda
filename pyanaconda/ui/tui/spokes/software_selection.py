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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from simpleline.render.containers import ListColumnContainer
from simpleline.render.prompt import Prompt
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import CheckboxWidget, TextWidget

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    PAYLOAD_TYPE_DNF,
    THREAD_CHECK_SOFTWARE,
    THREAD_PAYLOAD,
    THREAD_SOFTWARE_WATCHER,
)
from pyanaconda.core.i18n import N_, _
from pyanaconda.flags import flags
from pyanaconda.payload.errors import DependencyError, NoSuchGroup
from pyanaconda.payload.manager import PayloadState, payloadMgr
from pyanaconda.threading import AnacondaThread, threadMgr
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.context import context
from pyanaconda.ui.lib.software import (
    FEATURE_64K,
    FEATURE_UPSTREAM,
    KernelFeatures,
    get_available_kernel_features,
    get_kernel_from_properties,
    get_kernel_titles_and_descriptions,
)
from pyanaconda.ui.tui.spokes import NormalTUISpoke

log = get_module_logger(__name__)

__all__ = ["SoftwareSpoke"]


class SoftwareSpoke(NormalTUISpoke):
    """ Spoke used to read new value of text to represent source repo.

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
        self.errors = []
        self._tx_id = None

        self._available_kernels = None
        self._kernel_selection = None

        # Get the packages configuration.
        self._selection = self.payload.get_packages_data()

        # are we taking values (package list) from a kickstart file?
        self._kickstarted = flags.automatedInstall and self.payload.proxy.PackagesKickstarted

        # Register event listeners to update our status on payload events
        payloadMgr.add_listener(PayloadState.STARTED, self._payload_start)
        payloadMgr.add_listener(PayloadState.ERROR, self._payload_error)

    def initialize(self):
        """Initialize the spoke."""
        super().initialize()
        self.initialize_start()

        threadMgr.add(AnacondaThread(
            name=THREAD_SOFTWARE_WATCHER,
            target=self._initialize
        ))

    def _initialize(self):
        """Initialize the spoke in a separate thread."""
        threadMgr.wait(THREAD_PAYLOAD)

        self._available_kernels = get_available_kernel_features(self.payload)
        self._kernel_selection = dict.fromkeys(self._available_kernels, False)

        # kernel-redhat should be the default when available
        if FEATURE_UPSTREAM in self._kernel_selection:
            self._kernel_selection[FEATURE_UPSTREAM] = True

        # Initialize and check the software selection.
        self._initialize_selection()

        # Report that the software spoke has been initialized.
        self.initialize_done()

    def _initialize_selection(self):
        """Initialize and check the software selection."""
        if self.errors or not self.payload.base_repo:
            log.debug("Skip the initialization of the software selection.")
            return

        if not self._kickstarted:
            # Set the environment.
            self.set_default_environment()

            # Apply the initial selection.
            self.apply()

        # Check the initial software selection.
        self.execute()

        # Wait for the software selection thread that might be started by execute().
        # We are already running in a thread, so it should not needlessly block anything
        # and only like this we can be sure we are really initialized.
        threadMgr.wait(THREAD_CHECK_SOFTWARE)

    def set_default_environment(self):
        # If an environment was specified in the configuration, use that.
        # Otherwise, select the first environment.
        if self.payload.environments:
            environments = self.payload.environments

            if conf.payload.default_environment in environments:
                self._selection.environment = conf.payload.default_environment
            else:
                self._selection.environment = environments[0]

    def _payload_start(self):
        self.errors = []

    def _payload_error(self):
        self.errors = [payloadMgr.error]

    def _translate_env_name_to_id(self, environment):
        """ Return the id of the selected environment or None. """
        if not environment:
            # None means environment is not set, no need to try translate that to an id
            return None
        try:
            return self.payload.environment_id(environment)
        except NoSuchGroup:
            return None

    def _get_available_addons(self, environment_id):
        """ Return all add-ons of the specific environment. """
        addons = []

        if environment_id in self.payload.environment_addons:
            for addons_list in self.payload.environment_addons[environment_id]:
                addons.extend(addons_list)

        return addons

    @property
    def status(self):
        """ Where we are in the process """
        if self.errors:
            return _("Error checking software selection")
        if not self.ready:
            return _("Processing...")
        if not self.payload.base_repo:
            return _("Installation source not set up")
        if not self.txid_valid:
            return _("Source changed - please verify")
        if not self._selection.environment:
            # KS installs with %packages will have an env selected, unless
            # they did an install without a desktop environment. This should
            # catch that one case.
            if self._kickstarted:
                return _("Custom software selected")
            return _("Nothing selected")

        return self.payload.environment_description(self._selection.environment)[0]

    @property
    def completed(self):
        """ Make sure our threads are done running and vars are set.

           WARNING: This can be called before the spoke is finished initializing
           if the spoke starts a thread. It should make sure it doesn't access
           things until they are completely setup.
        """
        processing_done = self.ready and not self.errors and self.txid_valid

        if flags.automatedInstall or self._kickstarted:
            return processing_done and self.payload.base_repo and self.payload.proxy.PackagesKickstarted
        else:
            return processing_done and self.payload.base_repo and self._selection.environment

    def setup(self, args):
        """Set up the spoke right before it is used."""
        super().setup(args)

        # Join the initialization thread to block on it
        threadMgr.wait(THREAD_SOFTWARE_WATCHER)

        # Get the packages configuration.
        self._selection = self.payload.get_packages_data()

        return True

    def refresh(self, args=None):
        """ Refresh screen. """
        NormalTUISpoke.refresh(self, args)

        threadMgr.wait(THREAD_PAYLOAD)
        self._container = None

        if not self.payload.base_repo:
            message = TextWidget(_("Installation source needs to be set up first."))
            self.window.add_with_separator(message)
            return

        threadMgr.wait(THREAD_CHECK_SOFTWARE)
        self._container = ListColumnContainer(2, columns_width=38, spacing=2)

        # Environment selection screen
        environments = self.payload.environments

        for env in environments:
            name = self.payload.environment_description(env)[0]
            selected = (env == self._selection.environment)
            widget = CheckboxWidget(title="%s" % name, completed=selected)
            self._container.add(widget, callback=self._set_environment_callback, data=env)

        text = TextWidget(_("Base environment"))
        self.window.add_with_separator(text)
        self.window.add_with_separator(self._container)

    def _set_environment_callback(self, data):
        self._selection.environment = data

    def input(self, args, key):
        """ Handle the input; this chooses the desktop environment. """
        if self._container is not None and self._container.process_user_input(key):
            self.redraw()
            return InputState.PROCESSED

        if key.lower() == Prompt.CONTINUE:
            # No environment was selected, close
            if not self._selection.environment:
                self.close()

            # The environment was selected, switch screen
            else:
                environment = self._selection.environment
                environment_id = self._translate_env_name_to_id(environment)
                addons = self._get_available_addons(environment_id)
                spoke = AdditionalSoftwareSpoke(
                    self.data,
                    self.storage,
                    self.payload,
                    self._selection,
                    self._kernel_selection,
                )
                ScreenHandler.push_screen_modal(spoke, addons)
                self.apply()
                self.execute()
                self.close()
        else:
            return super().input(args, key)

        return InputState.PROCESSED

    @property
    def ready(self):
        """Is the spoke ready?

        By default, the software selection spoke is not ready. We have to
        wait until the installation source spoke is completed. This could be
        because the user filled something out, or because we're done fetching
        repo metadata from the mirror list, or we detected a DVD/CD.
        """
        return not threadMgr.get(THREAD_SOFTWARE_WATCHER) \
            and not threadMgr.get(THREAD_PAYLOAD) \
            and not threadMgr.get(THREAD_CHECK_SOFTWARE) \
            and ((self.payload.base_repo is not None) or self.errors)

    def apply(self):
        """Apply the changes."""
        self._kickstarted = False

        # Clear packages data.
        self._selection.packages = []
        self._selection.excluded_packages = []

        # Clear groups data.
        self._selection.excluded_groups = []
        self._selection.groups_package_types = {}

        # Select valid groups.
        # FIXME: Remove invalid groups from selected groups.

        self._available_kernels = get_available_kernel_features(self.payload)

        # Processing chosen kernel
        feature_upstream = self._available_kernels[FEATURE_UPSTREAM] and \
            self._kernel_selection[FEATURE_UPSTREAM]
        feature_64k = self._available_kernels[FEATURE_64K] and \
            self._kernel_selection[FEATURE_64K]

        features = KernelFeatures(feature_upstream, feature_64k)
        kernel = get_kernel_from_properties(features)
        if kernel:
            log.debug("Selected kernel package: %s", kernel)
            self._selection.packages.append(kernel)
            self._selection.excluded_packages.append("kernel")

        log.debug("Setting new software selection: %s", self._selection)
        self.payload.set_packages_data(self._selection)

    def execute(self):
        """Execute the changes."""
        threadMgr.add(AnacondaThread(
            name=THREAD_CHECK_SOFTWARE,
            target=self._check_software_selection
        ))

    def _check_software_selection(self):
        """Check the software selection."""
        try:
            self.payload.check_software_selection()
        except DependencyError as e:
            self.errors = [str(e)]
            self._tx_id = None
            log.warning("Transaction error %s", str(e))
        else:
            self._tx_id = self.payload.tx_id

    @property
    def txid_valid(self):
        """ Whether we have a valid dnf tx id. """
        return self._tx_id == self.payload.tx_id


class AdditionalSoftwareSpoke(NormalTUISpoke):
    """The spoke for choosing the additional software."""
    category = SoftwareCategory

    def __init__(self, data, storage, payload, selection, kernel_selection):
        super().__init__(data, storage, payload)
        self.title = N_("Software selection")
        self._container = None
        self._selection = selection
        self._kernel_selection = kernel_selection

    def refresh(self, args=None):
        """Refresh the screen."""
        NormalTUISpoke.refresh(self, args)

        self._container = ListColumnContainer(
            columns=2,
            columns_width=38,
            spacing=2
        )

        if args:
            msg = _("Additional software for selected environment")
        else:
            msg = _("No additional software to select.")

        for addon_id in args:
            name = self.payload.group_description(addon_id)[0]
            selected = addon_id in self._selection.groups
            widget = CheckboxWidget(title="%s" % name, completed=selected)
            self._container.add(widget, callback=self._set_addons_callback, data=addon_id)

        self.window.add_with_separator(TextWidget(msg))
        self.window.add_with_separator(self._container)

    def _set_addons_callback(self, data):
        if data not in self._selection.groups:
            self._selection.groups.append(data)
        else:
            self._selection.groups.remove(data)

    def _show_kernel_features_screen(self, kernels):
        """Returns True if at least one non-standard kernel is available.
        """
        for val in kernels.values():
            if val:
                return True
        return False

    def input(self, args, key):
        if self._container.process_user_input(key):
            return InputState.PROCESSED_AND_REDRAW

        if key.lower() == Prompt.CONTINUE:
            available_kernels = get_available_kernel_features(self.payload)
            if self._show_kernel_features_screen(available_kernels):
                spoke = KernelSelectionSpoke(self.data, self.storage, self.payload,
                                             self._selection, self._kernel_selection,
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
    def __init__(self, data, storage, payload, selection, kernel_selection, available_kernels):
        super().__init__(data, storage, payload)
        self.title = N_("Kernel Options")
        self._container = None
        self._selection = selection
        self._kernel_selection = kernel_selection
        self._available_kernels = available_kernels

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self)

        # Retrieving translated UI strings
        labels = get_kernel_titles_and_descriptions()
        # Updating kernel availability
        self._available_kernels = get_available_kernel_features(self.payload)
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
