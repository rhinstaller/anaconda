# Progress hub classes
#
# Copyright (C) 2011-2012  Red Hat, Inc.
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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

from __future__ import division

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

from pyanaconda.ui.gui.hubs import Hub
from pyanaconda.ui.gui.utils import gdk_threaded

__all__ = ["ProgressHub"]

class ProgressHub(Hub):
    builderObjects = ["progressWindow"]
    mainWidgetName = "progressWindow"
    uiFile = "hubs/progress.ui"

    def _update_progress(self):
        from pyanaconda import progress
        import Queue

        q = progress.progressQ

        # Grab all messages may have appeared since last time this method ran.
        while True:
            # Attempt to get a message out of the queue for how we should update
            # the progress bar.  If there's no message, don't error out.
            try:
                (code, args) = q.get(False)
            except Queue.Empty:
                break

            if code == progress.PROGRESS_CODE_INIT:
                self._init_progress_bar(args[0])
            elif code == progress.PROGRESS_CODE_STEP:
                self._step_progress_bar()
            elif code == progress.PROGRESS_CODE_MESSAGE:
                self._update_progress_message(args[0])
            elif code == progress.PROGRESS_CODE_COMPLETE:
                self._progress_bar_complete()

            q.task_done()

        return True

    def __init__(self, data, storage, payload, instclass):
        Hub.__init__(self, data, storage, payload, instclass)

        self._totalSteps = 0
        self._currentStep = 0

    def initialize(self):
        Hub.initialize(self)

        self._progressBar = self.builder.get_object("progressBar")
        self._progressLabel = self.builder.get_object("progressLabel")

    def refresh(self):
        from gi.repository import GLib
        from pyanaconda.install import doInstall
        from pyanaconda.threads import threadMgr, AnacondaThread

        Hub.refresh(self)

        GLib.idle_add(self._update_progress)
        threadMgr.add(AnacondaThread(name="AnaInstallThread", target=doInstall,
                                     args=(self.storage, self.payload, self.data, self.instclass)))

    @property
    def quitButton(self):
        return self.builder.get_object("rebootButton")

    def _init_progress_bar(self, steps):
        self._totalSteps = steps
        self._currentStep = 0

        with gdk_threaded():
            self._progressBar.set_fraction(0.0)
            self._progressLabel.set_text("")

    def _step_progress_bar(self):
        if not self._totalSteps:
            return

        with gdk_threaded():
            self._currentStep += 1
            self._progressBar.set_fraction(self._currentStep/self._totalSteps)

    def _update_progress_message(self, message):
        if not self._totalSteps:
            return

        with gdk_threaded():
            self._progressLabel.set_text(message)

    def _progress_bar_complete(self):
        with gdk_threaded():
            self._progressBar.set_fraction(1.0)
            self._progressLabel.set_text(_("Complete!"))
