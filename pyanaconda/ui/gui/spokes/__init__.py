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
from pyanaconda.ui.common import collect
from pyanaconda.ui.gui import GUIObject
import os.path

__all__ = ["StandaloneSpoke", "NormalSpoke", "PersonalizationSpoke",
           "collect_spokes"]

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

class StandaloneSpoke(Spoke, common.StandaloneSpoke):
    def __init__(self, data, storage, payload, instclass):
        Spoke.__init__(self, data)
        common.StandaloneSpoke.__init__(self, data, storage, payload, instclass)

    def _on_continue_clicked(self, cb):
        self.apply()
        cb()

    def register_event_cb(self, event, cb):
        if event == "continue":
            self.window.connect("continue-clicked", lambda *args: self._on_continue_clicked(cb))
        elif event == "quit":
            self.window.connect("quit-clicked", lambda *args: cb())

class NormalSpoke(Spoke, common.NormalSpoke):
    def __init__(self, data, storage, payload, instclass):
        Spoke.__init__(self, data)
        common.NormalSpoke.__init__(self, data, storage, payload, instclass)

    def on_back_clicked(self, window):
        from gi.repository import Gtk

        # Look for failed checks
        failed_check = next(self.failed_checks, None)
        if failed_check:
            # Set the focus to the first failed check and stay in the spoke
            failed_check.editable.grab_focus()
            return

        self.window.hide()
        Gtk.main_quit()

class PersonalizationSpoke(Spoke, common.PersonalizationSpoke):
    def __init__(self, data, storage, payload, instclass):
        Spoke.__init__(self, data)
        common.PersonalizationSpoke.__init__(self, data, storage, payload, instclass)

def collect_spokes(mask_paths, category):
    """Return a list of all spoke subclasses that should appear for a given
       category. Look for them in files imported as module_path % basename(f)

       :param mask_paths: list of mask, path tuples to search for classes
       :type mask_paths: list of (mask, path)

       :return: list of Spoke classes belonging to category
       :rtype: list of Spoke classes

    """
    spokes = []
    for mask, path in mask_paths:
        spokes.extend(collect(mask, path, lambda obj: hasattr(obj, "category") and obj.category != None and obj.category.__name__ == category))
        
    return spokes
