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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.

from pyanaconda.ui import common
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.lib.help import show_graphical_help_for_screen

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["StandaloneSpoke", "NormalSpoke"]


# Inherit abstract methods from common.StandaloneSpoke
# pylint: disable=abstract-method
class StandaloneSpoke(GUIObject, common.StandaloneSpoke):
    """
       .. inheritance-diagram:: StandaloneSpoke
          :parts: 3
    """

    def __init__(self, data, storage, payload):
        GUIObject.__init__(self, data)
        common.StandaloneSpoke.__init__(self, storage, payload)

        # Add a continue-clicked handler to save the data before leaving the window
        self.window.connect("continue-clicked", self._on_continue_clicked)

    def _on_continue_clicked(self, window, user_data=None):
        self.apply()


# Inherit abstract methods from common.NormalSpoke
# pylint: disable=abstract-method
class NormalSpoke(GUIObject, common.NormalSpoke):
    """
       .. inheritance-diagram:: NormalSpoke
          :parts: 3
    """
    def __init__(self, data, storage, payload):
        GUIObject.__init__(self, data)
        common.NormalSpoke.__init__(self, storage, payload)

        # Add a help handler
        self.window.connect_after("help-button-clicked", self._on_help_clicked)

        # warning message
        self._current_warning_message = ""

    def _on_help_clicked(self, window):
        # the help button has been clicked, start the yelp viewer with
        # content for the current spoke
        show_graphical_help_for_screen(self.get_screen_id())

    def on_back_clicked(self, button):
        # Notify the hub that we're finished.
        # The hub will be the current-action of the main window.
        self.main_window.current_action.spoke_done(self)

    def clear_info(self):
        """Clear the last set warning message and call the ancestors method."""
        self._current_warning_message = ""
        super().clear_info()

    def show_warning_message(self, message):
        """Show error message in the status bar.

        As set_warning() animates the error bar only set new message
        when it is different from the current one.
        """
        if not message:
            self.clear_info()
        elif self._current_warning_message != message:
            self.clear_info()
            self._current_warning_message = message
            self.set_warning(message)
