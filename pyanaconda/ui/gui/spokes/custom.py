# Custom partitioning classes.
#
# Copyright (C) 2012  Red Hat, Inc.
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
from pyanaconda.ui.gui.utils import setViewportBackground
from pyanaconda.ui.gui.categories.storage import StorageCategory

from gi.repository import Gtk

__all__ = ["CustomPartitioningSpoke"]

class CustomPartitioningSpoke(NormalSpoke):
    builderObjects = ["customStorageWindow",
                      "partitionStore",
                      "addImage", "removeImage", "settingsImage"]
    mainWidgetName = "customStorageWindow"
    uiFile = "spokes/custom.ui"

    category = StorageCategory
    title = N_("MANUAL PARTITIONING")

    def apply(self):
        pass

    @property
    def indirect(self):
        return True

    def _addCategory(self, store, name):
        return store.append(None, ["""<span size="large" weight="bold" fgcolor="grey">%s</span>""" % name, ""])

    def _addPartition(self, store, itr, req):
        from pyanaconda.storage.size import Size

        name = self._partitionName(req)
        size = Size(spec=str(req.size) + " MB")

        return store.append(itr, ["""<span size="large" weight="bold">%s</span>\n<span size="small" fgcolor="grey">%s</span>""" % (name, req.mountpoint or ""), size.humanReadable()])

    def _grabObjects(self):
        self._configureBox = self.builder.get_object("configureBox")
        self._availableSpaceBox = self.builder.get_object("availableSpaceBox")
        self._totalSpaceBox = self.builder.get_object("totalSpaceBox")

        self._store = self.builder.get_object("partitionStore")
        self._view = self.builder.get_object("partitionView")
        self._selection = self.builder.get_object("partitionView-selection")

    def _setBoxBackground(self, box, color):
        provider = Gtk.CssProvider()
        provider.load_from_data("GtkBox { background-color: %s }" % color)
        context = box.get_style_context()
        context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def initialize(self, cb=None):
        NormalSpoke.initialize(self, cb)

        self._grabObjects()
        self._setBoxBackground(self._availableSpaceBox, "#db3279")
        self._setBoxBackground(self._totalSpaceBox, "#60605b")

        setViewportBackground(self.builder.get_object("partitionsViewport"))

    def _partitionName(self, req):
        # If there's a mountpoint, we can probably just use that.
        if req.mountpoint:
            if req.mountpoint == "/":
                return "Root"
            elif req.mountpoint.count("/") == 1:
                return req.mountpoint[1:].capitalize()
        else:
            # Otherwise, try to use the name of whatever format the request is.
            from pyanaconda.storage.formats import getFormat
            return getFormat(req.fstype).name

    def _isSystemPartition(self, req):
        if req.mountpoint and req.mountpoint in ["/", "/boot"]:
            return True
        elif not req.mountpoint:
            return True
        else:
            return False

    def refresh(self):
        NormalSpoke.refresh(self)
        self._store.clear()

        self._dataItr = self._addCategory(self._store, "DATA")
        self._systemItr = self._addCategory(self._store, "SYSTEM")

        # Now add all existing partition requests to the UI.
        for req in self.storage.autoPartitionRequests:
            if self._isSystemPartition(req):
                itr = self._systemItr
            else:
                itr = self._dataItr

            self._addPartition(self._store, itr, req)

        # And pre-select the very first system partition.  We're guaranteed to
        # have one of those but not necessarily a data partition.  This way
        # there's always something to display in the right hand side.
        itr = self._store.iter_nth_child(self._systemItr, 0)
        self._selection.select_iter(itr)

        self._view.expand_all()

    def on_back_clicked(self, button):
        self.skipTo = "StorageSpoke"
        NormalSpoke.on_back_clicked(self, button)

    # Use the default back action here, since the finish button takes the user
    # to the install summary screen.
    def on_finish_clicked(self, button):
        NormalSpoke.on_back_clicked(self, button)

    def on_add_clicked(self, button):
        pass

    def on_remove_clicked(self, button):
        pass

    def on_configure_clicked(self, button):
        pass

    def on_selection_changed(self, selection):
        if not selection.count_selected_rows():
            self._configureBox.set_sensitive(False)
            return

        (store, itr) = selection.get_selected()
        row = self._store[itr]

        # The user selected a section heading, don't change anything.
        if not row[1]:
            self._configureBox.set_sensitive(False)
            return

        self._configureBox.set_sensitive(True)
        self.builder.get_object("selectedDeviceLabel").set_text("Some mountpoint")
        self.builder.get_object("selectedDeviceDescLabel").set_text("This is where important text would go.")
