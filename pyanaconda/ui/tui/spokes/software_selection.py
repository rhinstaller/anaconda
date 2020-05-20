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
from pyanaconda.flags import flags
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.payload.manager import payloadMgr, PayloadState
from pyanaconda.payload.errors import DependencyError, NoSuchGroup
from pyanaconda.core.i18n import N_, _, C_
from pyanaconda.core.configuration.anaconda import conf

from pyanaconda.core.constants import THREAD_PAYLOAD, THREAD_CHECK_SOFTWARE, \
    THREAD_SOFTWARE_WATCHER, PAYLOAD_TYPE_DNF

from simpleline.render.containers import ListColumnContainer
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import TextWidget, CheckboxWidget

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["SoftwareSpoke"]


class SoftwareSpoke(NormalTUISpoke):
    """ Spoke used to read new value of text to represent source repo.

       .. inheritance-diagram:: SoftwareSpoke
          :parts: 3
    """
    help_id = "SoftwareSelectionSpoke"
    category = SoftwareCategory

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)
        self.title = N_("Software selection")
        self._container = None
        self.errors = []
        self._tx_id = None
        self._selected_environment = None
        self.environment = None
        self._addons_selection = set()
        self.addons = set()

        # for detecting later whether any changes have been made
        self._orig_env = None
        self._orig_addons = set()

        # are we taking values (package list) from a kickstart file?
        self._kickstarted = flags.automatedInstall and self.data.packages.seen

        # Register event listeners to update our status on payload events
        payloadMgr.add_listener(PayloadState.STARTED, self._payload_start)
        payloadMgr.add_listener(PayloadState.FINISHED, self._payload_finished)
        payloadMgr.add_listener(PayloadState.ERROR, self._payload_error)

    def initialize(self):
        # Start a thread to wait for the payload and run the first, automatic
        # dependency check
        self.initialize_start()
        super().initialize()
        threadMgr.add(AnacondaThread(name=THREAD_SOFTWARE_WATCHER,
                                     target=self._initialize))

    def _initialize(self):
        threadMgr.wait(THREAD_PAYLOAD)

        if not self._kickstarted:
            # If an environment was specified in the configuration, use that.
            # Otherwise, select the first environment.
            if self.payload.environments:
                environments = self.payload.environments

                if conf.payload.default_environment in environments:
                    self._selected_environment = conf.payload.default_environment
                else:
                    self._selected_environment = environments[0]

        # Apply the initial selection
        self._apply()

        # Wait for the software selection thread that might be started by _apply().
        # We are already running in a thread, so it should not needlessly block anything
        # and only like this we can be sure we are really initialized.
        threadMgr.wait(THREAD_CHECK_SOFTWARE)

        # report that the software spoke has been initialized
        self.initialize_done()

    def _payload_start(self):
        # Source is changing, invalidate the software selection and clear the
        # errors
        self._selected_environment = None
        self._addons_selection = set()
        self.errors = []

    def _payload_finished(self):
        self.environment = self.data.packages.environment
        self.addons = self._get_selected_addons()
        self._orig_env = None
        self._orig_addons = None
        log.debug("Payload restarted, set new info and clear the old one.")

    def _payload_error(self):
        self.errors = [payloadMgr.error]

    def _translate_env_name_to_id(self, environment):
        """ Return the id of the selected environment or None. """
        if environment is None:
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

    def _get_selected_addons(self):
        """ Return selected add-ons. """
        return {group.name for group in self.payload.data.packages.groupList}

    @property
    def showable(self):
        return self.payload.type == PAYLOAD_TYPE_DNF

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

        if not self.environment:
            # KS installs with %packages will have an env selected, unless
            # they did an install without a desktop environment. This should
            # catch that one case.
            if self._kickstarted:
                return _("Custom software selected")
            return _("Nothing selected")

        return self.payload.environment_description(self.environment)[0]

    @property
    def completed(self):
        """ Make sure our threads are done running and vars are set.

           WARNING: This can be called before the spoke is finished initializing
           if the spoke starts a thread. It should make sure it doesn't access
           things until they are completely setup.
        """
        processing_done = self.ready and not self.errors and self.txid_valid

        if flags.automatedInstall or self._kickstarted:
            return processing_done and self.payload.base_repo and self.data.packages.seen
        else:
            return processing_done and self.payload.base_repo and self.environment is not None

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

        if args is None:
            msg = self._refresh_environments()
        else:
            msg = self._refresh_addons(args)

        self.window.add_with_separator(TextWidget(msg))
        self.window.add_with_separator(self._container)

    def _refresh_environments(self):
        environments = self.payload.environments

        for env in environments:
            name = self.payload.environment_description(env)[0]
            selected = (env == self._selected_environment)
            widget = CheckboxWidget(title="%s" % name, completed=selected)
            self._container.add(widget, callback=self._set_environment_callback, data=env)

        return _("Base environment")

    def _refresh_addons(self, available_addons):
        for addon_id in available_addons:
            name = self.payload.group_description(addon_id)[0]
            selected = addon_id in self._addons_selection
            widget = CheckboxWidget(title="%s" % name, completed=selected)
            self._container.add(widget, callback=self._set_addons_callback, data=addon_id)

        if available_addons:
            return _("Additional software for selected environment")
        else:
            return _("No additional software to select.")

    def _set_environment_callback(self, data):
        self._selected_environment = data

    def _set_addons_callback(self, data):
        addon = data
        if addon not in self._addons_selection:
            self._addons_selection.add(addon)
        else:
            self._addons_selection.remove(addon)

    def input(self, args, key):
        """ Handle the input; this chooses the desktop environment. """
        if self._container is not None and self._container.process_user_input(key):
            self.redraw()
        else:
            # TRANSLATORS: 'c' to continue
            if key.lower() == C_('TUI|Spoke Navigation', 'c'):

                # No environment was selected, close
                if self._selected_environment is None:
                    self.close()

                # The environment was selected, switch screen
                elif args is None:
                    # Get addons for the selected environment
                    environment = self._selected_environment
                    environment_id = self._translate_env_name_to_id(environment)
                    addons = self._get_available_addons(environment_id)

                    # Switch the screen
                    ScreenHandler.replace_screen(self, addons)

                # The addons were selected, apply and close
                else:
                    self.apply()
                    self.close()
            else:
                return super().input(args, key)

        return InputState.PROCESSED

    @property
    def ready(self):
        """ If we're ready to move on. """
        return (not threadMgr.get(THREAD_PAYLOAD) and
                not threadMgr.get(THREAD_CHECK_SOFTWARE) and
                not threadMgr.get(THREAD_SOFTWARE_WATCHER))

    def apply(self):
        """ Apply our selections """
        # no longer using values from kickstart
        self._kickstarted = False
        self.data.packages.seen = True
        # _apply depends on a value of _kickstarted
        self._apply()

    def _apply(self):
        """ Private apply. """
        self.environment = self._selected_environment
        self.addons = self._addons_selection if self.environment is not None else set()

        log.debug("Apply called old env %s, new env %s and addons %s",
                  self._orig_env, self.environment, self.addons)

        if self.environment is None:
            return

        changed = False

        # Not a kickstart with packages, setup the selected environment and addons
        if not self._kickstarted:

            # Changed the environment or addons, clear and setup
            if not self._orig_env \
                    or self._orig_env != self.environment \
                    or set(self._orig_addons) != set(self.addons):

                log.debug("Setting new software selection old env %s, new env %s and addons %s",
                          self._orig_env, self.environment, self.addons)

                self.payload.data.packages.packageList = []
                self.data.packages.groupList = []
                self.payload.select_environment(self.environment)

                environment_id = self._translate_env_name_to_id(self.environment)
                available_addons = self._get_available_addons(environment_id)

                for addon_id in available_addons:
                    if addon_id in self.addons:
                        self.payload.select_group(addon_id)

                changed = True

            self._orig_env = self.environment
            self._orig_addons = set(self.addons)

        # Check the software selection
        if changed or self._kickstarted:
            threadMgr.add(AnacondaThread(name=THREAD_CHECK_SOFTWARE,
                                         target=self.check_software_selection))

    def check_software_selection(self):
        """ Depsolving """
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
