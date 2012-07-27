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
#

from pyanaconda.ui import collect, common
from pyanaconda.ui.gui import GUIObject
import os.path

__all__ = ["Spoke", "StandaloneSpoke", "NormalSpoke", "PersonalizationSpoke",
           "collect_spokes"]

class Spoke(GUIObject, common.Spoke):
    def __init__(self, data, storage, payload, instclass):
        GUIObject.__init__(self, data)
        common.Spoke.__init__(self, data, storage, payload, instclass)

    def initialize(self):
        GUIObject.initialize(self)

        self.window.set_property("window-name", self.title or "")

class StandaloneSpoke(Spoke, common.StandaloneSpoke):
    def _on_continue_clicked(self, cb):
        self.apply()
        cb()

    def register_event_cb(self, event, cb):
        if event == "continue":
            self.window.connect("continue-clicked", lambda *args: self._on_continue_clicked(cb))
        elif event == "quit":
            self.window.connect("quit-clicked", lambda *args: cb())

class NormalSpoke(Spoke, common.NormalSpoke):
    def on_back_clicked(self, window):
        from gi.repository import Gtk

        self.window.hide()
        Gtk.main_quit()

class PersonalizationSpoke(Spoke, common.PersonalizationSpoke):
    pass

def collect_spokes(category):
    """Return a list of all spoke subclasses that should appear for a given
       category.
    """
    return collect("pyanaconda.ui.gui.spokes.%s", os.path.dirname(__file__), lambda obj: hasattr(obj, "category") and obj.category != None and obj.category.__name__ == category)
