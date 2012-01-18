# Keyboard selection and configuration spoke class
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

from gi.repository import Gtk, AnacondaWidgets

from pyanaconda.ui.gui import UIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.localization import LocalizationCategory

__all__ = ["KeyboardSpoke"]

class AddLayoutDialog(UIObject):
    builderObjects = ["addLayoutDialog", "newLayoutStore", "newLayoutStoreFilter"]
    mainWidgetName = "addLayoutDialog"
    uiFile = "spokes/keyboard.ui"

    def matches_entry(self, model, itr, user_data=None):
        value = model.get_value(itr, 0)
        entry_text = self._entry.get_text()
        if entry_text is not None:
            entry_text = entry_text.lower()
            entry_text_words = entry_text.split()
        else:
            return False
        try:
            if value:
                value = value.lower()
                for word in entry_text_words:
                    value.index(word)
                return True
            return False
        except ValueError as valerr:
            return False

    def setup(self):
        self._treeModelFilter = self.builder.get_object("newLayoutStoreFilter")
        self._treeModelFilter.set_visible_func(self.matches_entry, None)
        self._entry = self.builder.get_object("addLayoutEntry")
        self._entry.grab_focus()

    def populate(self):
        self._store = self.builder.get_object("newLayoutStore")
        #XXX: will use values from the libxklavier
        self._addLayout(self._store, "English (US)")
        self._addLayout(self._store, "English (US, with some other stuff)")
        self._addLayout(self._store, "Czech")
        self._addLayout(self._store, "Czech (qwerty)")
        self._addLayout(self._store, "values from libxklavier")

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    @property
    def chosen_layout(self):
        return self._chosen_layout

    def on_confirm_add_clicked(self, *args):
        treeview = self.builder.get_object("newLayoutView")
        selection = treeview.get_selection()
        (model, itr) = selection.get_selected()
        self._chosen_layout = model[itr][0]

    def on_cancel_clicked(self, *args):
        print "CANCELING"

    def on_entry_changed(self, *args):
        self._treeModelFilter.refilter()

    def on_entry_icon_clicked(self, *args):
        self._entry.set_text("")

    def _addLayout(self, store, name):
        store.append([name])

class KeyboardSpoke(NormalSpoke):
    builderObjects = ["addedLayoutStore", "keyboardWindow",
                      "addImage", "removeImage", "upImage", "downImage", "settingsImage"]
    mainWidgetName = "keyboardWindow"
    uiFile = "spokes/keyboard.ui"

    category = LocalizationCategory

    icon = "accessories-character-map"
    title = N_("KEYBOARD")

    def apply(self):
        pass

    @property
    def completed(self):
        # The keyboard spoke is always completed, as it does not require you do
        # anything.  There's always a default selected.
        return True

    @property
    def status(self):
        return _("Something selected")

    def populate(self, readyCB=None):
        NormalSpoke.populate(self, readyCB)

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
        dialog.populate()
        lightbox = AnacondaWidgets.lb_show_over(self.window)
        dialog.window.set_transient_for(lightbox)
        response = dialog.run()
        lightbox.destroy()
        if response == 1:
            found = False
            itr = self._store.get_iter_first()
            while itr and not found:
                found = self._store[itr][0] == dialog.chosen_layout
                itr = self._store.iter_next(itr)
            if not found:
                self._addLayout(self._store, dialog.chosen_layout)

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

    def on_selection_changed(self, *args):
        self.layout_selection_changed(self.builder.get_object("layoutSelection"))

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
