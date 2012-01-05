# Network configuration spoke classes
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
# Red Hat Author(s): Radek Vykydal <rvykydal@redhat.com>
#

# TODO:
# - which type of spoke or category?

from gi.repository import Gtk, AnacondaWidgets

from pyanaconda.ui.gui import UIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.software import SoftwareCategory

__all__ = ["NetworkSpoke"]

class NetworkSpoke(NormalSpoke):
    builderObjects = ["networkWindow"]
    mainWidgetName = "networkWindow"
    uiFile = "spokes/network.ui"

    category = SoftwareCategory

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)

    def apply(self):
        pass

    @property
    def completed(self):
        # enabled?
        pass

    @property
    def status(self):
        # active connections?
        pass

    def _grabObjects(self):
        pass

    def populate(self):
        NormalSpoke.populate(self)

        self._grabObjects()

    def setup(self):
        NormalSpoke.setup(self)

    # Signal handlers.
    def on_configure_clicked(self, button):
        pass

    def on_back_clicked(self, window):
        self.window.hide()
        Gtk.main_quit()
