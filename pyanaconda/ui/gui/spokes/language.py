# Language selection and configuration spoke class
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

from gi.repository import Gtk

from pyanaconda.ui.gui import UIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.localization import LocalizationCategory

__all__ = ["LanguageSpoke"]

class AddLayoutDialog(UIObject):
    builderObjects = ["addLayoutDialog", "newLayoutStore"]
    mainWidgetName = "addLayoutDialog"
    uiFile = "spokes/language.ui"

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    def on_confirm_add_clicked(self, *args):
        print "ADDING LAYOUT"

    def on_cancel_clicked(self, *args):
        print "CANCELING"

class LanguageSpoke(NormalSpoke):
    builderObjects = ["addedLayoutStore", "languageWindow",
                      "addImage", "removeImage", "upImage", "downImage", "settingsImage"]
    mainWidgetName = "languageWindow"
    uiFile = "spokes/language.ui"

    category = LocalizationCategory

    icon = "accessories-character-map"
    title = N_("LANGUAGE")

    def apply(self):
        pass

    @property
    def completed(self):
        # The language spoke is always completed, as it does not require you do
        # anything.  There's always a default selected.
        return True

    @property
    def status(self):
        return _("Something selected")

    def populate(self):
        NormalSpoke.populate(self)

        self._store = self.builder.get_object("addedLayoutStore")
        self._addLayout(self._store, "English (US)")
        self._addLayout(self._store, "Irish")
        self._addLayout(self._store, "English (US, with some other stuff)")

    def setup(self):
        NormalSpoke.setup(self)

        self._upButton = self.builder.get_object("upButton")
        self._downButton = self.builder.get_object("downButton")
        self._removeButton = self.builder.get_object("removeLayoutButton")

        # Start with no buttons enabled, since nothing is selected.
        self._upButton.set_sensitive(False)
        self._downButton.set_sensitive(False)
        self._removeButton.set_sensitive(False)

    def _addLayout(self, store, name):
        store.append([name])

    # Signal handlers.
    def on_add_clicked(self, button):
        dialog = AddLayoutDialog(self.data)
        dialog.setup()
        print "RESPONSE = %s" % dialog.run()

    def on_remove_clicked(self, button):
        selection = self.builder.get_object("layoutSelection")
        if not selection.count_selected_rows():
            return

        (store, itr) = selection.get_selected()
        store.remove(itr)

    def on_up_clicked(self, button):
        selection = self.builder.get_object("layoutSelection")
        if not selection.count_selected_rows():
            return

        (store, cur) = selection.get_selected()
        prev = cur.copy()
        if not store.iter_previous(prev):
            return

        store.swap(cur, prev)
        selection.emit("changed")

    def on_down_clicked(self, button):
        selection = self.builder.get_object("layoutSelection")
        if not selection.count_selected_rows():
            return

        (store, cur) = selection.get_selected()
        nxt = store.iter_next(cur)
        if not nxt:
            return

        store.swap(cur, nxt)
        selection.emit("changed")

    def on_settings_clicked(self, button):
        pass

    def layout_selection_changed(self, selection):
        # We don't have to worry about multiple rows being selected in this
        # function, because that's disabled by the widget.
        if not selection.count_selected_rows():
            self._upButton.set_sensitive(False)
            self._downButton.set_sensitive(False)
            self._removeButton.set_sensitive(False)
            return

        (store, selected) = selection.get_selected_rows()

        # If something's selected, always enable the remove button.
        self._removeButton.set_sensitive(True)

        # Disable the Up button if the top row's selected, and disable the
        # Down button if the bottom row's selected.
        if selected[0].get_indices() == [0]:
            self._upButton.set_sensitive(False)
            self._downButton.set_sensitive(True)
        elif selected[0].get_indices() == [len(store)-1]:
            self._upButton.set_sensitive(True)
            self._downButton.set_sensitive(False)
        else:
            self._upButton.set_sensitive(True)
            self._downButton.set_sensitive(True)

    def on_back_clicked(self, window):
        self.window.hide()
        Gtk.main_quit()
