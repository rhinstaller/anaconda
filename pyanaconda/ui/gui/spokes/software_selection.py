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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import sys
import copy
import gi

from pyanaconda.flags import flags
from pyanaconda.core.i18n import _, C_, CN_
from pyanaconda.core.constants import PAYLOAD_TYPE_DNF, THREAD_SOFTWARE_WATCHER, THREAD_PAYLOAD, \
    THREAD_CHECK_SOFTWARE
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.payload.manager import payloadMgr, PayloadState
from pyanaconda.payload.errors import NoSuchGroup, DependencyError, PayloadError
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.core import util, constants

from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.context import context
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.detailederror import DetailedErrorDialog
from pyanaconda.ui.gui.utils import blockedHandler, escape_markup
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.lib.subscription import check_cdn_is_installation_source
from pyanaconda.ui.lib.software import FEATURE_UPSTREAM, FEATURE_64K, KernelFeatures, \
    get_kernel_from_properties, get_available_kernel_features, get_kernel_titles_and_descriptions

from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.util import is_module_available

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Pango


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

    # Add-on selection states
    # no user interaction with this add-on
    _ADDON_DEFAULT = 0
    # user selected
    _ADDON_SELECTED = 1
    # user de-selected
    _ADDON_DESELECTED = 2

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
        self._error_msgs = None
        self._tx_id = None
        self._select_flag = False

        self._environment_list_box = self.builder.get_object("environmentListBox")
        self._addon_list_box = self.builder.get_object("addonListBox")

        # Connect viewport scrolling with listbox focus events
        environment_viewport = self.builder.get_object("environmentViewport")
        addon_viewport = self.builder.get_object("addonViewport")
        self._environment_list_box.set_focus_vadjustment(
            Gtk.Scrollable.get_vadjustment(environment_viewport))
        self._addon_list_box.set_focus_vadjustment(
            Gtk.Scrollable.get_vadjustment(addon_viewport))

        # Used to store how the user has interacted with add-ons for the default add-on
        # selection logic. The dictionary keys are group IDs, and the values are selection
        # state constants. See refresh_addons for how the values are used.
        self._addon_states = {}

        # Get the packages configuration.
        self._selection = self.payload.get_packages_data()

        # Whether we are using package selections from a kickstart
        self._kickstarted = flags.automatedInstall and self.payload.proxy.PackagesKickstarted

        # Whether the payload is in an error state
        self._error = False

        # Register event listeners to update our status on payload events
        payloadMgr.add_listener(PayloadState.DOWNLOADING_PKG_METADATA,
                                self._downloading_package_md)
        payloadMgr.add_listener(PayloadState.DOWNLOADING_GROUP_METADATA,
                                self._downloading_group_md)
        payloadMgr.add_listener(PayloadState.ERROR, self._payload_error)

        # Add an invisible radio button so that we can show the environment
        # list with no radio buttons ticked
        self._fake_radio = Gtk.RadioButton(group=None)
        self._fake_radio.set_active(True)

        # Display a group of options for selecting desired properties of a kernel
        self._kernel_box = self.builder.get_object("kernelBox")
        self._combo_kernel_page_size = self.builder.get_object("kernelPageSizeCombo")
        self._label_kernel_page_size = self.builder.get_object("kernelPageSizeLabel")
        self._combo_kernel_version = self.builder.get_object("kernelVersionCombo")
        self._label_kernel_version = self.builder.get_object("kernelVersionLabel")

        # Normally I would create these in the .glade file but due to a bug they weren't
        # created properly
        self._model_kernel_page_size = Gtk.ListStore(str, str)
        self._model_kernel_version = Gtk.ListStore(str, str)

        kernel_labels = get_kernel_titles_and_descriptions()
        for i in ["4k", "64k"]:
            self._model_kernel_page_size.append([i, "<b>%s</b>\n%s" % \
                                                (escape_markup(kernel_labels[i][0]),
                                                escape_markup(kernel_labels[i][1]))])
        for i in ["upstream", "standard"]:
            self._model_kernel_version.append([i, "<b>%s</b>\n%s" % \
                                              (escape_markup(kernel_labels[i][0]),
                                              escape_markup(kernel_labels[i][1]))])
        self._combo_kernel_page_size.set_model(self._model_kernel_page_size)
        self._combo_kernel_version.set_model(self._model_kernel_version)

        # Will be initialized during the screen refresh
        self._available_kernels = {}

    # Payload event handlers
    def _downloading_package_md(self):
        # Reset the error state from previous payloads
        self._error = False

        hubQ.send_message(self.__class__.__name__, _(constants.PAYLOAD_STATUS_PACKAGE_MD))

    def _downloading_group_md(self):
        hubQ.send_message(self.__class__.__name__, _(constants.PAYLOAD_STATUS_GROUP_MD))

    def get_environment_id(self, environment):
        """Return the "machine readable" environment id

        Alternatively we could have just "canonicalized" the
        environment description to the "machine readable" format
        when reading it from kickstart for the first time.
        But this could result in input and output kickstart,
        which would be rather confusing for the user.
        So we don't touch the specification from kickstart
        if it is valid and use this property when we need
        the "machine readable" form.
        """
        if not environment:
            # None means environment is not set, no need to try translate that to an id
            return None
        try:
            return self.payload.environment_id(environment)
        except NoSuchGroup:
            return None

    def is_environment_valid(self, environment):
        """Return if the currently set environment is valid
        (represents an environment known by the payload)
        """
        # None means the environment has not been set by the user,
        # which means:
        # * set the default environment during interactive installation
        # * ask user to specify an environment during kickstart installation
        if not environment:
            return True
        else:
            return self.get_environment_id(environment) in self.payload.environments

    def _payload_error(self):
        self._error = True
        hubQ.send_message(self.__class__.__name__, payloadMgr.error)

    def apply(self):
        """Apply the changes."""
        self._kickstarted = False

        # Clear packages data.
        self._selection.packages = []
        self._selection.excluded_packages = []

        # Clear groups data.
        self._selection.excluded_groups = []
        self._selection.groups_package_types = {}

        # Select new groups.
        self._selection.groups = []

        for group_name in self._get_selected_addons():
            self._selection.groups.append(group_name)

        # Select kernel
        property_64k = self._available_kernels[FEATURE_64K] and \
            self._combo_kernel_page_size.get_active_id() == FEATURE_64K
        property_upstream = self._available_kernels[FEATURE_UPSTREAM] and \
            self._combo_kernel_version.get_active_id() == FEATURE_UPSTREAM

        kernel_properties = KernelFeatures(property_upstream, property_64k)
        kernel = get_kernel_from_properties(kernel_properties)
        if kernel is not None:
            log.debug("Selected kernel package: %s", kernel)
            self._selection.packages.append(kernel)
            self._selection.excluded_packages.append("kernel")

        log.debug("Setting new software selection: %s", self._selection)
        self.payload.set_packages_data(self._selection)

        hubQ.send_not_ready(self.__class__.__name__)
        hubQ.send_not_ready("SourceSpoke")

    def execute(self):
        """Execute the changes."""
        threadMgr.add(AnacondaThread(
            name=constants.THREAD_CHECK_SOFTWARE,
            target=self.checkSoftwareSelection
        ))

    def checkSoftwareSelection(self):
        hubQ.send_message(self.__class__.__name__, _("Checking software dependencies..."))
        try:
            self.payload.check_software_selection()
        except DependencyError as e:
            self._error_msgs = str(e)
            hubQ.send_message(self.__class__.__name__, _("Error checking software dependencies"))
            self._tx_id = None
        else:
            self._error_msgs = None
            self._tx_id = self.payload.tx_id
        finally:
            hubQ.send_ready(self.__class__.__name__)
            hubQ.send_ready("SourceSpoke")

    @property
    def completed(self):
        processing_done = bool(not threadMgr.get(constants.THREAD_CHECK_SOFTWARE) and
                               not threadMgr.get(constants.THREAD_PAYLOAD) and
                               not self._error_msgs and self.txid_valid)

        # * we should always check processing_done before checking the other variables,
        #   as they might be inconsistent until processing is finished
        # * we can't let the installation proceed until a valid environment has been set
        if processing_done:
            if self._selection.environment:
                # if we have environment it needs to be valid
                return self.is_environment_valid(self._selection.environment)
            # if we don't have environment we need to at least have the %packages
            # section in kickstart
            elif self._kickstarted:
                return True
            # no environment and no %packages section -> manual intervention is needed
            else:
                return False
        else:
            return False

    @property
    def mandatory(self):
        return True

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
            and self.payload.base_repo is not None

    @property
    def status(self):
        if self._error_msgs:
            return _("Error checking software selection")

        cdn_source = check_cdn_is_installation_source(self.payload)

        subscribed = False
        if is_module_available(SUBSCRIPTION):
            subscription_proxy = SUBSCRIPTION.get_proxy()
            subscribed = subscription_proxy.IsSubscriptionAttached

        if cdn_source and not subscribed:
            return _("Red Hat CDN requires registration.")

        if not self.ready:
            return _("Installation source not set up")

        if not self.txid_valid:
            return _("Source changed - please verify")

        # kickstart installation
        if flags.automatedInstall:
            if self._kickstarted:
                # %packages section is present in kickstart but environment is not set
                if not self._selection.environment:
                    return _("Custom software selected")
                # environment is set to an invalid value
                elif not self.is_environment_valid(self._selection.environment):
                    return _("Invalid environment specified in kickstart")
            # we have no packages section in the kickstart and no environment has been set
            elif not self._selection.environment:
                return _("Please confirm software selection")

        if not flags.automatedInstall:
            if not self._selection.environment:
                # No environment yet set
                return _("Please confirm software selection")
            elif not self.is_environment_valid(self._selection.environment):
                # selected environment is not valid, this can happen when a valid environment
                # is selected (by default, manually or from kickstart) and then the installation
                # source is switched to one where the selected environment is no longer valid
                return _("Selected environment is not valid")

        return self.payload.environment_description(self._selection.environment)[0]

    def initialize(self):
        """Initialize the spoke."""
        super().initialize()
        self.initialize_start()

        threadMgr.add(AnacondaThread(
            name=constants.THREAD_SOFTWARE_WATCHER,
            target=self._initialize
        ))

    def _initialize(self):
        """Initialize the spoke in a separate thread."""
        threadMgr.wait(constants.THREAD_PAYLOAD)

        # Initialize and check the software selection.
        self._initialize_selection()

        # Update the status.
        hubQ.send_ready(self.__class__.__name__)

        # Report that the software spoke has been initialized.
        self.initialize_done()

    def _initialize_selection(self):
        """Initialize and check the software selection."""
        if self._error or not self.payload.base_repo:
            log.debug("Skip the initialization of the software selection.")
            return

        if not self._kickstarted:
            # Set the environment.
            self.set_default_environment()

            # Find out if alternative kernel packages are available
            self._available_kernels = get_available_kernel_features(self.payload)

            # Apply the initial selection.
            self.apply()

        # Check the initial software selection.
        self.execute()

        # Wait for the software selection thread that might be started by execute().
        # We are already running in a thread, so it should not needlessly block anything
        # and only like this we can be sure we are really initialized.
        threadMgr.wait(constants.THREAD_CHECK_SOFTWARE)

    def set_default_environment(self):
        # If an environment was specified in the configuration, use that.
        # Otherwise, select the first environment.
        if self.payload.environments:
            environments = self.payload.environments

            if conf.payload.default_environment in environments:
                self._selection.environment = conf.payload.default_environment
            else:
                self._selection.environment = environments[0]

    def _add_row(self, listbox, name, desc, button, clicked):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        button.set_valign(Gtk.Align.START)
        button.connect("toggled", clicked, row)
        box.add(button)

        label = Gtk.Label(label="<b>%s</b>\n%s" % (escape_markup(name), escape_markup(desc)),
                          use_markup=True, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                          hexpand=True, xalign=0, yalign=0.5)
        box.add(label)

        row.add(box)
        listbox.insert(row, -1)

    def refresh(self):
        super().refresh()
        threadMgr.wait(constants.THREAD_PAYLOAD)

        # Get the packages configuration.
        self._selection = self.payload.get_packages_data()

        # Set up the environment.
        if not self._selection.environment \
                or not self.is_environment_valid(self._selection.environment):
            self.set_default_environment()

        # Create rows for all valid environments.
        self._clear_listbox(self._environment_list_box)

        for environment_id in self.payload.environments:
            (name, desc) = self.payload.environment_description(environment_id)

            # use the invisible radio button as a group for all environment
            # radio buttons
            radio = Gtk.RadioButton(group=self._fake_radio)

            # check if the selected environment (if any) does match the current row
            # and tick the radio button if it does
            radio.set_active(
                self.is_environment_valid(self._selection.environment) and
                self.get_environment_id(self._selection.environment) == environment_id
            )

            self._add_row(self._environment_list_box,
                          name, desc, radio,
                          self.on_radio_button_toggled)

        # Set up states of selected groups.
        self._addon_states = {}

        for group in self._selection.groups:
            try:
                group_id = self.payload.group_id(group)
                self._mark_addon_selection(group_id, True)
            except PayloadError as e:
                log.warning(e)

        self.refresh_addons()
        self._environment_list_box.show_all()
        self._addon_list_box.show_all()
        self._refresh_kernel_features()

    def _add_addon(self, grp):
        (name, desc) = self.payload.group_description(grp)

        if grp in self._addon_states:
            # If the add-on was previously selected by the user, select it
            if self._addon_states[grp] == self._ADDON_SELECTED:
                selected = True
            # If the add-on was previously de-selected by the user, de-select it
            elif self._addon_states[grp] == self._ADDON_DESELECTED:
                selected = False
            # Otherwise, use the default state
            else:
                selected = self.payload.environment_option_is_default(
                    self.get_environment_id(self._selection.environment), grp
                )
        else:
            selected = self.payload.environment_option_is_default(
                self.get_environment_id(self._selection.environment), grp
            )

        check = Gtk.CheckButton()
        check.set_active(selected)
        self._add_row(self._addon_list_box, name, desc, check, self.on_checkbox_toggled)

    @property
    def _add_sep(self):
        """ Whether the addon list contains a separator. """
        environment_id = self.get_environment_id(self._selection.environment)

        return len(self.payload.environment_addons[environment_id][0]) > 0 and \
            len(self.payload.environment_addons[environment_id][1]) > 0

    def refresh_addons(self):
        environment = self._selection.environment
        environment_id = self.get_environment_id(self._selection.environment)

        if environment and (environment_id in self.payload.environment_addons):
            self._clear_listbox(self._addon_list_box)

            # We have two lists:  One of addons specific to this environment,
            # and one of all the others.  The environment-specific ones will be displayed
            # first and then a separator, and then the generic ones.  This is to make it
            # a little more obvious that the thing on the left side of the screen and the
            # thing on the right side of the screen are related.
            #
            # If a particular add-on was previously selected or de-selected by the user, that
            # state will be used. Otherwise, the add-on will be selected if it is a default
            # for this environment.

            for grp in self.payload.environment_addons[environment_id][0]:
                self._add_addon(grp)

            # This marks a separator in the view - only add it if there's both environment
            # specific and generic addons.
            if self._add_sep:
                self._addon_list_box.insert(Gtk.Separator(), -1)

            for grp in self.payload.environment_addons[environment_id][1]:
                self._add_addon(grp)

        self._select_flag = True

        if self._error_msgs:
            self.set_warning(_("Error checking software dependencies. "
                               " <a href=\"\">Click for details.</a>"))
        else:
            self.clear_info()

    def _all_addons(self):
        environment_id = self.get_environment_id(self._selection.environment)

        if environment_id in self.payload.environment_addons:
            addons = copy.copy(self.payload.environment_addons[environment_id][0])

            if self._add_sep:
                addons.append('')

            addons += self.payload.environment_addons[environment_id][1]
        else:
            addons = []

        return addons

    def _get_selected_addons(self):
        retval = []
        addons = self._all_addons()

        for (ndx, row) in enumerate(self._addon_list_box.get_children()):
            box = row.get_children()[0]

            if isinstance(box, Gtk.Separator):
                continue

            button = box.get_children()[0]
            if button.get_active():
                retval.append(addons[ndx])

        return retval

    def _mark_addon_selection(self, grpid, selected):
        # Mark selection or return its state to the default state
        if selected:
            if self.payload.environment_option_is_default(self._selection.environment, grpid):
                self._addon_states[grpid] = self._ADDON_DEFAULT
            else:
                self._addon_states[grpid] = self._ADDON_SELECTED
        else:
            if not self.payload.environment_option_is_default(self._selection.environment, grpid):
                self._addon_states[grpid] = self._ADDON_DEFAULT
            else:
                self._addon_states[grpid] = self._ADDON_DESELECTED

    def _clear_listbox(self, listbox):
        for child in listbox.get_children():
            listbox.remove(child)
            del(child)

    def _refresh_kernel_features(self):
        """Display options for selecting kernel features."""

        # Only showing parts of kernel box relevant for current system.
        self._available_kernels = get_available_kernel_features(self.payload)
        show_kernels = False
        for (_key, val) in self._available_kernels.items():
            if val:
                show_kernels = True
                break

        if show_kernels:
            self._kernel_box.set_visible(True)
            self._kernel_box.set_no_show_all(False)

            # Kernel version combo
            self._combo_kernel_version.set_visible(self._available_kernels[FEATURE_UPSTREAM])
            self._combo_kernel_version.set_no_show_all(not self._available_kernels[FEATURE_UPSTREAM])
            self._label_kernel_version.set_visible(self._available_kernels[FEATURE_UPSTREAM])
            self._label_kernel_version.set_no_show_all(not self._available_kernels[FEATURE_UPSTREAM])

            # Arm 64k page size kernel combo
            self._combo_kernel_page_size.set_visible(self._available_kernels[FEATURE_64K])
            self._combo_kernel_page_size.set_no_show_all(not self._available_kernels[FEATURE_64K])
            self._label_kernel_page_size.set_visible(self._available_kernels[FEATURE_64K])
            self._label_kernel_page_size.set_no_show_all(not self._available_kernels[FEATURE_64K])
        else:
            # Hide the entire box.
            self._kernel_box.set_visible(False)
            self._kernel_box.set_no_show_all(True)

    @property
    def txid_valid(self):
        return self._tx_id == self.payload.tx_id

    # Signal handlers
    def on_radio_button_toggled(self, radio, row):
        # If the radio button toggled to inactive, don't reactivate the row
        if not radio.get_active():
            return
        row.activate()

    def on_environment_activated(self, listbox, row):
        if not self._select_flag:
            return

        # GUI selections means that packages are no longer coming from kickstart
        self._kickstarted = False

        box = row.get_children()[0]
        button = box.get_children()[0]

        with blockedHandler(button, self.on_radio_button_toggled):
            button.set_active(True)

        # Mark the clicked environment as selected and update the screen.
        self._selection.environment = self.payload.environments[row.get_index()]
        self.refresh_addons()
        self._addon_list_box.show_all()

    def on_checkbox_toggled(self, button, row):
        # Select the addon. The button is already toggled.
        self._select_addon_at_row(row, button.get_active())

    def on_addon_activated(self, listbox, row):
        # Skip the separator.
        box = row.get_children()[0]
        if isinstance(box, Gtk.Separator):
            return

        # Select the addon. The button is not toggled yet.
        button = box.get_children()[0]
        self._select_addon_at_row(row, not button.get_active())

    def _select_addon_at_row(self, row, is_selected):
        # GUI selections means that packages are no longer coming from kickstart.
        self._kickstarted = False

        # Activate the row.
        with blockedHandler(row.get_parent(), self.on_addon_activated):
            row.activate()

        # Activate the button.
        box = row.get_children()[0]
        button = box.get_children()[0]
        with blockedHandler(button, self.on_checkbox_toggled):
            button.set_active(is_selected)

        # Mark the selection.
        addons = self._all_addons()
        group = addons[row.get_index()]
        self._mark_addon_selection(group, is_selected)

    def on_info_bar_clicked(self, *args):
        if not self._error_msgs:
            return

        label = _("The software marked for installation has the following errors.  "
                  "This is likely caused by an error with your installation source.  "
                  "You can quit the installer, change your software source, or change "
                  "your software selections.")
        dialog = DetailedErrorDialog(
            self.data,
            buttons=[C_("GUI|Software Selection|Error Dialog", "_Quit"),
                     C_("GUI|Software Selection|Error Dialog", "_Modify Software Source"),
                     C_("GUI|Software Selection|Error Dialog", "Modify _Selections")],
            label=label)
        with self.main_window.enlightbox(dialog.window):
            dialog.refresh(self._error_msgs)
            rc = dialog.run()

        dialog.window.destroy()

        if rc == 0:
            # Quit.
            util.ipmi_abort(scripts=self.data.scripts)
            sys.exit(0)
        elif rc == 1:
            # Send the user to the installation source spoke.
            self.skipTo = "SourceSpoke"
            self.window.emit("button-clicked")
        elif rc == 2:
            # Close the dialog so the user can change selections.
            pass
        else:
            pass
