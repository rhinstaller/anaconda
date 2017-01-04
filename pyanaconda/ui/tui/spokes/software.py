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
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget, CheckboxWidget
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.packaging import DependencyError, PackagePayload, payloadMgr, NoSuchGroup
from pyanaconda.i18n import N_, _, C_

from pyanaconda.constants import THREAD_PAYLOAD
from pyanaconda.constants import THREAD_CHECK_SOFTWARE
from pyanaconda.constants import THREAD_SOFTWARE_WATCHER
from pyanaconda.constants_text import INPUT_PROCESSED

__all__ = ["SoftwareSpoke"]


class SoftwareSpoke(NormalTUISpoke):
    """ Spoke used to read new value of text to represent source repo.

       .. inheritance-diagram:: SoftwareSpoke
          :parts: 3
    """
    title = N_("Software selection")
    category = SoftwareCategory

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.errors = []
        self._tx_id = None
        self._selection = None
        self.environment = None
        self._addons_selection = set()
        self.addons = set()

        # for detecting later whether any changes have been made
        self._origEnv = None
        self._origAddons = set()

        # are we taking values (package list) from a kickstart file?
        self._kickstarted = flags.automatedInstall and self.data.packages.seen

        # Register event listeners to update our status on payload events
        payloadMgr.addListener(payloadMgr.STATE_START, self._payload_start)
        payloadMgr.addListener(payloadMgr.STATE_FINISHED, self._payload_finished)
        payloadMgr.addListener(payloadMgr.STATE_ERROR, self._payload_error)

    def initialize(self):
        # Start a thread to wait for the payload and run the first, automatic
        # dependency check
        super(SoftwareSpoke, self).initialize()
        threadMgr.add(AnacondaThread(name=THREAD_SOFTWARE_WATCHER,
            target=self._initialize))

    def _initialize(self):
        threadMgr.wait(THREAD_PAYLOAD)

        if not self._kickstarted:
            # If an environment was specified in the instclass, use that.
            # Otherwise, select the first environment.
            if self.payload.environments:
                environments = self.payload.environments
                instclass = self.payload.instclass

                if instclass and instclass.defaultPackageEnvironment and \
                        instclass.defaultPackageEnvironment in environments:
                    self._selection = environments.index(instclass.defaultPackageEnvironment)
                else:
                    self._selection = 0

        # Apply the initial selection
        self._apply()

    def _payload_start(self):
        # Source is changing, invalidate the software selection and clear the
        # errors
        self._selection = None
        self._addons_selection = set()
        self.errors = []

    def _payload_finished(self):
        self.environment = self.data.packages.environment
        self.addons = self._get_selected_addons()

    def _payload_error(self):
        self.errors = [payloadMgr.error]

    def _get_environment(self, selection):
        """ Return the selected environment or None.
            Selection can be None during kickstart installation.
        """
        if selection is not None and 0 <= selection < len(self.payload.environments):
            return self.payload.environments[selection]
        else:
            return None

    def _get_environment_id(self, environment):
        """ Return the id of the selected environment or None. """
        if environment is None:
            return None
        try:
            return self.payload.environmentId(environment)
        except NoSuchGroup:
            return None

    def _get_available_addons(self, environment_id):
        """ Return all add-ons of the specific environment. """
        addons = []

        if environment_id in self.payload.environmentAddons:
            for addons_list in self.payload.environmentAddons[environment_id]:
                addons.extend(addons_list)

        return addons

    def _get_selected_addons(self):
        """ Return selected add-ons. """
        return {group.name for group in self.payload.data.packages.groupList}

    @property
    def showable(self):
        return isinstance(self.payload, PackagePayload)

    @property
    def status(self):
        """ Where we are in the process """
        if self.errors:
            return _("Error checking software selection")
        if not self.ready:
            return _("Processing...")
        if not self.payload.baseRepo:
            return _("Installation source not set up")
        if not self.txid_valid:
            return _("Source changed - please verify")

        if not self.environment:
            # Ks installs with %packages will have an env selected, unless
            # they did an install without a desktop environment. This should
            # catch that one case.
            if self._kickstarted:
                return _("Custom software selected")
            return _("Nothing selected")

        return self.payload.environmentDescription(self.environment)[0]

    @property
    def completed(self):
        """ Make sure our threads are done running and vars are set.

           WARNING: This can be called before the spoke is finished initializing
           if the spoke starts a thread. It should make sure it doesn't access
           things until they are completely setup.
        """
        processingDone = self.ready and not self.errors and self.txid_valid

        if flags.automatedInstall or self._kickstarted:
            return processingDone and self.payload.baseRepo and self.data.packages.seen
        else:
            return processingDone and self.payload.baseRepo and self.environment is not None

    def refresh(self, args=None):
        """ Refresh screen. """
        NormalTUISpoke.refresh(self, args)

        threadMgr.wait(THREAD_PAYLOAD)

        if not self.payload.baseRepo:
            message = TextWidget(_("Installation source needs to be set up first."))
            self._window.append(message)

            # add some more space below
            self._window.append(TextWidget(""))
            return True

        threadMgr.wait(THREAD_CHECK_SOFTWARE)
        displayed = []

        # Display the environments
        if args is None:
            environments = self.payload.environments
            length = len(environments)
            msg = _("Base environment")

            for env in environments:
                name = self.payload.environmentDescription(env)[0]
                selected = environments.index(env) == self._selection
                displayed.append(CheckboxWidget(title="%s" % name, completed=selected))

        # Display the add-ons
        else:
            length = len(args)

            if length > 0:
                msg = _("Add-ons for selected environment")
            else:
                msg = _("No add-ons to select.")

            for addon_id in args:
                name = self.payload.groupDescription(addon_id)[0]
                selected = addon_id in self._addons_selection
                displayed.append(CheckboxWidget(title="%s" % name, completed=selected))

        def _prep(i, w):
            """ Do some format magic for display. """
            num = TextWidget("%2d)" % (i + 1))
            return ColumnWidget([(4, [num]), (None, [w])], 1)

        # split list of DE's into two columns
        mid = length / 2
        left = [_prep(i, w) for i, w in enumerate(displayed) if i <= mid]
        right = [_prep(i, w) for i, w in enumerate(displayed) if i > mid]

        cw = ColumnWidget([(38, left), (38, right)], 2)
        self._window += [TextWidget(msg), "", cw, ""]

        return True

    def input(self, args, key):
        """ Handle the input; this chooses the desktop environment. """
        try:
            keyid = int(key) - 1
        except ValueError:
            # TRANSLATORS: 'c' to continue
            if key.lower() == C_('TUI|Spoke Navigation', 'c'):

                # No environment was selected, close
                if self._selection is None:
                    self.close()

                # The environment was selected, switch screen
                elif args is None:
                    # Get addons for the selected environment
                    environment = self._get_environment(self._selection)
                    environment_id = self._get_environment_id(environment)
                    addons = self._get_available_addons(environment_id)

                    # Switch the screen
                    self.app.switch_screen(self, addons)

                # The addons were selected, apply and close
                else:
                    self.apply()
                    self.close()

                return INPUT_PROCESSED
            else:
                return key

        # Process the environment selection
        if args is None:
            if 0 <= keyid < len(self.payload.environments):
                self._selection = keyid

        # Process the addons selection
        else:
            if 0 <= keyid < len(args):
                addon = args[keyid]
                if addon not in self._addons_selection:
                    self._addons_selection.add(addon)
                else:
                    self._addons_selection.remove(addon)

        return INPUT_PROCESSED

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
        self.environment = self._get_environment(self._selection)
        self.addons = self._addons_selection if self.environment is not None else set()

        changed = False

        # Not a kickstart with packages, setup the selected environment and addons
        if not self._kickstarted:

            # Changed the environment or addons, clear and setup
            if not self._origEnv \
                    or self._origEnv != self.environment \
                    or set(self._origAddons) != set(self.addons):

                self.payload.data.packages.packageList = []
                self.data.packages.groupList = []
                self.payload.selectEnvironment(self.environment)

                environment_id = self._get_environment_id(self.environment)
                available_addons = self._get_available_addons(environment_id)

                for addon_id in available_addons:
                    if addon_id in self.addons:
                        self.payload.selectGroup(addon_id)

                changed = True

            self._origEnv = self.environment
            self._origAddons = set(self.addons)

        # Check the software selection
        if changed or self._kickstarted:
            threadMgr.add(AnacondaThread(name=THREAD_CHECK_SOFTWARE,
                                         target=self.checkSoftwareSelection))


    def checkSoftwareSelection(self):
        """ Depsolving """
        try:
            self.payload.checkSoftwareSelection()
        except DependencyError as e:
            self.errors = [str(e)]
            self._tx_id = None
        else:
            self._tx_id = self.payload.txID

    @property
    def txid_valid(self):
        """ Whether we have a valid dnf tx id. """
        return self._tx_id == self.payload.txID
