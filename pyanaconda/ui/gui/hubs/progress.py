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

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

from pyanaconda.ui.gui.hubs import Hub
from pyanaconda.ui.gui.utils import gdk_threaded

__all__ = ["ProgressHub"]

class ProgressHub(Hub):
    builderObjects = ["progressWindow"]
    mainWidgetName = "progressWindow"
    uiFile = "hubs/progress.ui"

    def __init__(self, data, devicetree, payload, instclass):
        Hub.__init__(self, data, devicetree, payload, instclass)

        self._totalSteps = 0
        self._currentStep = 0

        # Register this interface with the top-level ProgressHandler.
        from pyanaconda.progress import progress
        progress.register(self.initCB, self.updateCB, self.completeCB)

    def initialize(self):
        Hub.initialize(self)

        self._progressBar = self.builder.get_object("progressBar")
        self._progressLabel = self.builder.get_object("progressLabel")

    def refresh(self):
        Hub.refresh(self)

        # There's nothing to install yet, so just jump to the reboot button.
        notebook = self.builder.get_object("progressNotebook")
        notebook.next_page()

    @property
    def quitButton(self):
        return self.builder.get_object("rebootButton")

    def initCB(self, steps):
        self._totalSteps = steps
        self._currentStep = 0

        with gdk_threaded():
            self._progressBar.set_fraction(0.0)
            self._progressLabel.set_text("")

    def updateCB(self, message):
        if not self._totalSteps:
            return

        with gdk_threaded():
            self._progressBar.set_fraction(self._currentStep/self._totalSteps)
            self._progressLabel.set_text(message)

    def completeCB(self):
        with gdk_threaded():
            self._progressBar.set_fraction(1.0)
            self._progressLabel.set_text(_("Complete!"))
