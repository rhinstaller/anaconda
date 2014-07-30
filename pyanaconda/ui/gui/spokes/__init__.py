# Base classes for Spokes
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
#                    Martin Sivak <msivak@redhat.com>

from pyanaconda.ui import common
from pyanaconda.ui.gui import GUIObject
from pyanaconda import ihelp

__all__ = ["StandaloneSpoke", "NormalSpoke"]

# Inherit abstract methods from common.StandaloneSpoke
# pylint: disable=abstract-method
class StandaloneSpoke(GUIObject, common.StandaloneSpoke):
    def __init__(self, data, storage, payload, instclass):
        GUIObject.__init__(self, data)
        common.StandaloneSpoke.__init__(self, storage, payload, instclass)

        # Add a continue-clicked handler to save the data before leaving the window
        self.window.connect("continue-clicked", self._on_continue_clicked)

    def _on_continue_clicked(self, win, user_data=None):
        self.apply()

# Inherit abstract methods from common.NormalSpoke
# pylint: disable=abstract-method
class NormalSpoke(GUIObject, common.NormalSpoke):
    def __init__(self, data, storage, payload, instclass):
        GUIObject.__init__(self, data)
        common.NormalSpoke.__init__(self, storage, payload, instclass)

        # Add a help handler
        self.window.connect_after("help-button-clicked", self._on_help_clicked)

    def _on_help_clicked(self, window):
        # the help button has been clicked, start the yelp viewer with
        # content for the current spoke
        ihelp.start_yelp(ihelp.get_help_path(self.helpFile, self.instclass))

    def on_back_clicked(self, window):
        # Notify the hub that we're finished.
        # The hub will be the current-action of the main window.
        self.main_window.current_action.spoke_done(self)
