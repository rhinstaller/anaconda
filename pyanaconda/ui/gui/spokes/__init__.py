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
import os.path

__all__ = ["StandaloneSpoke", "NormalSpoke"]

class Spoke(GUIObject):
    def __init__(self, data):
        GUIObject.__init__(self, data)

    def apply(self):
        """Apply the selections made on this Spoke to the object's preset
           data object.  This method must be provided by every subclass.
        """
        raise NotImplementedError

    @property
    def completed(self):
        """Has this spoke been visited and completed?  If not, a special warning
           icon will be shown on the Hub beside the spoke, and a highlighted
           message will be shown at the bottom of the Hub.  Installation will not
           be allowed to proceed until all spokes are complete.

           WARNING: This can be called before the spoke is finished initializing
           if the spoke starts a thread. It should make sure it doesn't access
           things until they are completely setup.
        """
        return False

    def execute(self):
        """Cause the data object to take effect on the target system.  This will
           usually be as simple as calling one or more of the execute methods on
           the data object.  This method does not need to be provided by all
           subclasses.

           This method will be called in two different places:  (1) Immediately
           after initialize on kickstart installs.  (2) Immediately after apply
           in all cases.
        """
        pass

# Inherit abstract methods from Spoke and common.StandaloneSpoke
# pylint: disable=abstract-method
class StandaloneSpoke(Spoke, common.StandaloneSpoke):
    def __init__(self, data, storage, payload, instclass):
        Spoke.__init__(self, data)
        common.StandaloneSpoke.__init__(self, data, storage, payload, instclass)

        # Add a continue-clicked handler to save the data before leaving the window
        self.window.connect("continue-clicked", self._on_continue_clicked)

    def _on_continue_clicked(self, win, user_data=None):
        self.apply()

# Inherit abstract methods from common.NormalSpoke
# pylint: disable=abstract-method
class NormalSpoke(Spoke, common.NormalSpoke):
    def __init__(self, data, storage, payload, instclass):
        if self.__class__ is NormalSpoke:
            raise TypeError("NormalSpoke is an abstract class")

        Spoke.__init__(self, data)
        common.NormalSpoke.__init__(self, data, storage, payload, instclass)

    def on_back_clicked(self, window):
        from gi.repository import Gtk

        self.window.hide()
        Gtk.main_quit()
