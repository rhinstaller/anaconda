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
# Red Hat Author(s): Samantha N. Bueno <sbueno@redhat.com>
#

from pyanaconda.flags import flags
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget, CheckboxWidget
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.packaging import DependencyError, PackagePayload, payloadMgr
from pyanaconda.i18n import N_, _, C_

from pyanaconda.constants import THREAD_PAYLOAD
from pyanaconda.constants import THREAD_CHECK_SOFTWARE
from pyanaconda.constants import THREAD_SOFTWARE_WATCHER
from pyanaconda.constants_text import INPUT_PROCESSED

__all__ = ["SoftwareSpoke"]


class SoftwareSpoke(NormalTUISpoke):
    """ Spoke used to read new value of text to represent source repo. """
    title = N_("Software selection")
    category = SoftwareCategory

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.errors = []
        self._tx_id = None
        self._selection = None
        self.environment = None

        # for detecting later whether any changes have been made
        self._origEnv = None

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
        self.errors = []

    def _payload_finished(self):
        self.environment = self.data.packages.environment

    def _payload_error(self):
        self.errors = [payloadMgr.error]

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

        if flags.automatedInstall:
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

        # put a title above the list and some space below it
        self._window.append(TextWidget(_("Base environment")))
        self._window.append(TextWidget(""))

        environments = self.payload.environments

        displayed = []
        for env in environments:
            name = self.payload.environmentDescription(env)[0]

            displayed.append(CheckboxWidget(title="%s" % name, completed=(environments.index(env) == self._selection)))

        def _prep(i, w):
            """ Do some format magic for display. """
            num = TextWidget("%2d)" % (i + 1))
            return ColumnWidget([(4, [num]), (None, [w])], 1)

        # split list of DE's into two columns
        mid = len(environments) / 2
        left = [_prep(i, w) for i, w in enumerate(displayed) if i <= mid]
        right = [_prep(i, w) for i, w in enumerate(displayed) if i > mid]

        cw = ColumnWidget([(38, left), (38, right)], 2)
        self._window.append(cw)

        return True

    def input(self, args, key):
        """ Handle the input; this chooses the desktop environment. """
        try:
            keyid = int(key) - 1
        except ValueError:
            # TRANSLATORS: 'c' to continue
            if key.lower() == C_("TUI|Spoke Navigation", "c") and \
                    0 <= self._selection < len(self.payload.environments):
                self.apply()
                self.close()
                return INPUT_PROCESSED
            else:
                return key

        if 0 <= keyid < len(self.payload.environments):
            self._selection = keyid
        return INPUT_PROCESSED

    @property
    def ready(self):
        """ If we're ready to move on. """
        return (not threadMgr.get(THREAD_PAYLOAD) and
                not threadMgr.get(THREAD_CHECK_SOFTWARE) and
                not threadMgr.get(THREAD_SOFTWARE_WATCHER))

    def apply(self):
        """ Apply our selections """
        self._apply()

        # no longer using values from kickstart
        self._kickstarted = False
        self.data.packages.seen = True

    def _apply(self):
        """ Private apply. """
        if 0 <= self._selection < len(self.payload.environments):
            self.environment = self.payload.environments[self._selection]
        else:
            self.environment = None
            return

        changed = False

        # Not a kickstart with packages, setup the selected environment
        if not self._kickstarted:
            if not self._origEnv:
                # nothing selected before, select the environment
                self.payload.selectEnvironment(self.environment)
                changed = True
            elif self._origEnv != self.environment:
                # environment changed, clear the list of packages and select the new
                # one
                self.payload.data.packages.groupList = []
                self.payload.selectEnvironment(self.environment)
                changed = True

            self._origEnv = self.environment

        # Check the software selection
        if changed:
            threadMgr.add(AnacondaThread(name=THREAD_CHECK_SOFTWARE,
                                         target=self.checkSoftwareSelection))


    def checkSoftwareSelection(self):
        """ Depsolving """
        try:
            self.payload.checkSoftwareSelection()
        except DependencyError as e:
            self.errors = [e.message]
            self._tx_id = None
        else:
            self._tx_id = self.payload.txID

    @property
    def txid_valid(self):
        """ Whether we have a valid yum tx id. """
        return self._tx_id == self.payload.txID
