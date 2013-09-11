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
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget, CheckboxWidget
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.packaging import MetadataError, DependencyError
from pyanaconda.i18n import _

from pyanaconda.constants import THREAD_PAYLOAD, THREAD_PAYLOAD_MD
from pyanaconda.constants import THREAD_CHECK_SOFTWARE, THREAD_SOFTWARE_WATCHER
from pyanaconda.constants_text import INPUT_PROCESSED

__all__ = ["SoftwareSpoke"]


class SoftwareSpoke(NormalTUISpoke):
    """ Spoke used to read new value of text to represent source repo. """
    title = _("Software selection")
    category = "software"

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self._ready = False
        self.errors = []
        self._tx_id = None
        # default to first selection (Gnome) in list of environments
        self._selection = 0
        self.environment = None

        # for detecting later whether any changes have been made
        self._origEnv = None

        # are we taking values (package list) from a kickstart file?
        self._kickstarted = flags.automatedInstall and self.data.packages.seen

    def initialize(self):
        NormalTUISpoke.initialize(self)
        threadMgr.add(AnacondaThread(name=THREAD_SOFTWARE_WATCHER, target=self._initialize))

    def _initialize(self):
        """ Private initialize. """
        threadMgr.wait(THREAD_PAYLOAD)
        if self._kickstarted:
            threadMgr.wait(THREAD_PAYLOAD_MD)
        else:
            try:
                self.payload.environments
            except MetadataError:
                self.errors.append(_("No installation source available"))
                return
        self.payload.release()

        self._ready = True

    @property
    def status(self):
        """ Where we are in the process """
        if self.errors:
            return _("Error checking software selection")
        if not self.ready:
            return _("Processing...")
        if not self.txid_valid:
            return _("Source changed - please verify")

        ## FIXME:
        # quite ugly, but env isn't getting set to gnome (or anything) by
        # default, and it really should be so we can maintain consistency
        # with graphical behavior
        if self._selection >= 0 and not self.environment \
                and not self._kickstarted:
            self.apply()

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
        """ Make sure our threads are done running and vars are set. """
        processingDone = not threadMgr.get(THREAD_CHECK_SOFTWARE) and \
                         not self.errors and self.txid_valid

        if flags.automatedInstall:
            return processingDone and self.data.packages.seen
        else:
            return self.environment is not None and processingDone

    def refresh(self, args=None):
        """ Refresh screen. """
        NormalTUISpoke.refresh(self, args)

        environments = self.payload.environments

        displayed = []
        for env in environments:
            name = self.payload.environmentDescription(env)[0]

            displayed.append(CheckboxWidget(title="%s" % name, completed=(environments.index(env) == self._selection)))
        print(_("Base environment"))

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
            if key.lower() == "c" and 0 <= self._selection < len(self.payload.environments):
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
        return (not threadMgr.get(THREAD_SOFTWARE_WATCHER) and
                not threadMgr.get(THREAD_PAYLOAD_MD) and
                not threadMgr.get(THREAD_CHECK_SOFTWARE) and
                self.payload.baseRepo is not None)

    def apply(self):
        """ Apply our selections """
        self._apply()

        # no longer using values from kickstart
        self._kickstarted = False
        self.data.packages.seen = True

        threadMgr.add(AnacondaThread(name=THREAD_CHECK_SOFTWARE,
                                     target=self.checkSoftwareSelection))

    def _apply(self):
        """ Private apply. """
        self.environment = self.payload.environments[self._selection]
        if not self.environment:
            return

        if not self._origEnv:
            # nothing selected before, select the environment
            self.payload.selectEnvironment(self.environment)
        elif self._origEnv != self.environment:
            # environment changed, clear the list of packages and select the new
            # one
            self.payload.data.packages.groupList = []
            self.payload.selectEnvironment(self.environment)
        else:
            # no change
            return

        self._origEnv = self.environment

    def checkSoftwareSelection(self):
        """ Depsolving """
        try:
            self.payload.checkSoftwareSelection()
        except DependencyError:
            self._tx_id = None
        else:
            self._tx_id = self.payload.txID

    @property
    def txid_valid(self):
        """ Whether we have a valid yum tx id. """
        return self._tx_id == self.payload.txID
