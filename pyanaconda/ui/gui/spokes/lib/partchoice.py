# Manual Partitioning choose dialog
#
# Copyright (C) 2019  Red Hat, Inc.
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

from pyanaconda.core.constants import PARTITIONING_METHOD_CUSTOM, PARTITIONING_METHOD_BLIVET
from pyanaconda.ui.gui import GUIObject

__all__ = ["PartitioningChoiceDialog"]


class PartitioningChoiceDialog(GUIObject):
    """Dialog to let user pick manual partitioning method from the anaconda one and blivet-gui."""
    builderObjects = ["pick_partchoice_dialog"]
    mainWidgetName = "pick_partchoice_dialog"
    uiFile = "spokes/lib/partchoice.glade"

    def __init__(self, data):
        super().__init__(data)

        self._manual_radio_button = self.builder.get_object("manual_radio_button")
        self._manual_radio_button.connect("toggled", self._on_radiobuttons_changed)

        self._blivet_radio_button = self.builder.get_object("blivet_radio_button")
        self._blivet_radio_button.connect("toggled", self._on_radiobuttons_changed)

        self._fake_radio_button = self.builder.get_object("fake_radio_button")
        self._fake_radio_button.connect("toggled", self._on_radiobuttons_changed)

        self._next_button = self.builder.get_object("next_button")

    def run(self):
        """Run the dialog to get the user choice for manual partitioning type.

        :return: Partitioning method type
        :rtype: None or str (PARTITIONING_METHOD_*)
        """
        rc = self.window.run()  # gives 0 for cancel, 1 for next
        self.window.destroy()

        if rc == 0:
            return None

        elif self._manual_radio_button.get_active():
            return PARTITIONING_METHOD_CUSTOM

        elif self._blivet_radio_button.get_active():
            return PARTITIONING_METHOD_BLIVET

    def _on_radiobuttons_changed(self, control):
        # Run only for an active radio button.

        if not control.get_active():
            return

        self._next_button.set_sensitive(not self._fake_radio_button.get_active())
