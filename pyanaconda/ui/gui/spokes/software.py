# Software selection spoke classes
#
# Copyright (C) 2011  Red Hat, Inc.
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
N_ = lambda x: x

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.software import SoftwareCategory

__all__ = ["SoftwareSelectionSpoke"]

class SoftwareSelectionSpoke(NormalSpoke):
    builderObjects = ["addonStore", "desktopStore", "softwareWindow"]
    mainWidgetName = "softwareWindow"
    uiFile = "spokes/software.ui"

    category = SoftwareCategory

    icon = "package-x-generic-symbolic"
    title = N_("SOFTWARE SELECTION")

    def apply(self):
        pass

    @property
    def completed(self):
        return self._get_selected_desktop() is not None

    @property
    def status(self):
        row = self._get_selected_desktop()
        if not row:
            return _("Nothing selected")

        return row[2]

    def initialize(self, readyCB=None):
        NormalSpoke.initialize(self, readyCB)

        self._desktopStore = self.builder.get_object("desktopStore")
        self._addSelection(self._desktopStore, "Desktop", "The default Fedora desktop.")
        self._addSelection(self._desktopStore, "KDE Plasma Desktop", "A complete, modern desktop built using KDE Plasma.")
        self._addSelection(self._desktopStore, "LXDE Desktop", "A light, fast, less resource-hungry desktop.")
        self._addSelection(self._desktopStore, "XFCE Desktop", "A complete, well-integrated desktop.")

        self._addonStore = self.builder.get_object("addonStore")
        self._addSelection(self._addonStore, "Security", "Security analysis tools.")
        self._addSelection(self._addonStore, "Games", "A perfect showcase of the best games available in Fedora.")
        self._addSelection(self._addonStore, "Electronic Lab", "Fedora's high-end hardware design and simulation platform.")
        self._addSelection(self._addonStore, "Design Suite", "Open creativity.")

    def _addSelection(self, store, name, description):
        store.append([False, "<b>%s</b>\n%s" % (name, description), name])

    # Returns the row in the store corresponding to what's selected on the
    # left hand panel, or None if nothing's selected.
    def _get_selected_desktop(self):
        desktopView = self.builder.get_object("desktopView")
        (store, itr) = desktopView.get_selection().get_selected()
        if not itr:
            return None

        return self._desktopStore[itr]

    # Signal handlers
    def on_row_toggled(self, renderer, path):
        self._addonStore[path][0] = not self._addonStore[path][0]

    def on_custom_clicked(self, button):
        # FIXME: does nothing for now
        pass
