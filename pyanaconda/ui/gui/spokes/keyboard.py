# Keyboard selection and configuration spoke class
#
# Copyright (C) 2011-2012  Red Hat, Inc.
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
#                    Vratislav Podzimek <vpodzime@redhat.com>
#

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x

from gi.repository import GLib, AnacondaWidgets, Gkbd

from pyanaconda.ui.gui import UIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.localization import LocalizationCategory
from pyanaconda.ui.gui.utils import enlightbox
from pyanaconda import xklavier

__all__ = ["KeyboardSpoke"]

def _show_layout(column, renderer, model, itr, wrapper):
    value = wrapper.name_to_show_str[model[itr][0]]
    renderer.set_property("text", value)

class AddLayoutDialog(UIObject):
    builderObjects = ["addLayoutDialog", "newLayoutStore", "newLayoutStoreFilter"]
    mainWidgetName = "addLayoutDialog"
    uiFile = "spokes/keyboard.ui"

    def __init__(self, *args):
        UIObject.__init__(self, *args)
        self._xkl_wrapper = xklavier.XklWrapper.get_instance()

    def matches_entry(self, model, itr, user_data=None):
        value = model[itr][0]
        value = self._xkl_wrapper.name_to_show_str[value]
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

    def refresh(self):
        self._treeModelFilter = self.builder.get_object("newLayoutStoreFilter")
        self._treeModelFilter.set_visible_func(self.matches_entry, None)
        self._entry = self.builder.get_object("addLayoutEntry")
        self._entry.grab_focus()

    def initialize(self):
        # We want to store layouts' names but show layouts as
        # 'language (description)'.
        layoutColumn = self.builder.get_object("newLayoutColumn")
        layoutRenderer = self.builder.get_object("newLayoutRenderer")
        layoutColumn.set_cell_data_func(layoutRenderer, _show_layout,
                                            self._xkl_wrapper)

        self._store = self.builder.get_object("newLayoutStore")
        for layout in self._xkl_wrapper.get_available_layouts():
            self._addLayout(self._store, layout)

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    @property
    def chosen_layouts(self):
        return self._chosen_layouts

    def on_confirm_add_clicked(self, *args):
        treeview = self.builder.get_object("newLayoutView")
        selection = treeview.get_selection()
        (store, pathlist) = selection.get_selected_rows()
        self._chosen_layouts = []
        for path in pathlist:
            itr = store.get_iter(path)
            self._chosen_layouts.append(store[itr][0])

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
                      "addImage", "removeImage", "upImage", "downImage", "previewImage"]
    mainWidgetName = "keyboardWindow"
    uiFile = "spokes/keyboard.ui"

    category = LocalizationCategory

    icon = "input-keyboard-symbolic"
    title = N_("KEYBOARD")

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        self._remove_last_attempt = False
        self._xkl_wrapper = xklavier.XklWrapper.get_instance()

    def apply(self):
        # Clear and repopulate self.data with actual values
        self.data.keyboard.layouts_list = list()
        itr = self._store.get_iter_first()
        while itr:
            self.data.keyboard.layouts_list.append(self._store[itr][0])
            itr = self._store.iter_next(itr)
        # FIXME:  Set the keyboard layout here, too.

    @property
    def completed(self):
        # The keyboard spoke is always completed, as it does not require you do
        # anything.  There's always a default selected.
        return True

    @property
    def status(self):
        # We don't need to check that self._store is empty, because that isn't allowed.
        return self._xkl_wrapper.name_to_show_str[self._store[0][0]]

    def initialize(self):
        NormalSpoke.initialize(self)

        # We want to store layouts' names but show layouts as
        # 'language (description)'.
        layoutColumn = self.builder.get_object("layoutColumn")
        layoutRenderer = self.builder.get_object("layoutRenderer")
        layoutColumn.set_cell_data_func(layoutRenderer, _show_layout,
                                            self._xkl_wrapper)

        self._store = self.builder.get_object("addedLayoutStore")
        self._addLayout(self._store, "us")
        self._addLayout(self._store, "ie")
        self._addLayout(self._store, "cz (qwerty)")

    def refresh(self):
        NormalSpoke.refresh(self)

        # Clear and repopulate addedLayoutStore with values from self.data
        self._store.clear()
        for layout in self.data.keyboard.layouts_list:
            self._addLayout(self._store, layout)

        self._upButton = self.builder.get_object("upButton")
        self._downButton = self.builder.get_object("downButton")
        self._removeButton = self.builder.get_object("removeLayoutButton")
        self._previewButton = self.builder.get_object("previewButton")

        # Start with no buttons enabled, since nothing is selected.
        self._upButton.set_sensitive(False)
        self._downButton.set_sensitive(False)
        self._removeButton.set_sensitive(False)
        self._previewButton.set_sensitive(False)

    def _addLayout(self, store, name):
        store.append([name])

    # Signal handlers.
    def on_add_clicked(self, button):
        dialog = AddLayoutDialog(self.data)
        dialog.refresh()
        dialog.initialize()

        with enlightbox(self.window, dialog.window):
            response = dialog.run()

        if response == 1:
            duplicates = set()
            itr = self._store.get_iter_first()
            while itr:
                item = self._store[itr][0]
                if item in dialog.chosen_layouts:
                    duplicates.add(item)
                itr = self._store.iter_next(itr)

            if self._remove_last_attempt:
                self._store.remove(self._store.get_iter_first())
                self._remove_last_attempt = False

            for layout in dialog.chosen_layouts:
                if layout not in duplicates:
                    self._addLayout(self._store, layout)

    def on_remove_clicked(self, button):
        selection = self.builder.get_object("layoutSelection")
        if not selection.count_selected_rows():
            return

        (store, itr) = selection.get_selected()
        itr2 = store.get_iter_first()
        #if the first item is selected, try to select the next one
        if store[itr][0] == store[itr2][0]:
            itr2 = store.iter_next(itr2)
            if itr2: #next one existing
                selection.select_iter(itr2)
                store.remove(itr)
                return

            #nothing left, run AddLayout dialog to replace the current layout
            #add it to GLib.idle to make sure the underlaying gui is correctly
            #redrawn
            self._remove_last_attempt = True
            add_button = self.builder.get_object("addLayoutButton")
            GLib.idle_add(self.on_add_clicked, add_button)
            return

        #the selected item is not the first, select the previous one
        #XXX: there is no model.iter_previous() so we have to find it this way
        itr3 = store.iter_next(itr2) #look-ahead iterator
        while itr3 and (store[itr3][0] != store[itr][0]):
            itr2 = store.iter_next(itr2)
            itr3 = store.iter_next(itr3)
        store.remove(itr)
        selection.select_iter(itr2)

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

    def on_preview_clicked(self, button):
        selection = self.builder.get_object("layoutSelection")
        (store, cur) = selection.get_selected()
        layout_row = store[cur]
        if not layout_row:
            return

        dialog = Gkbd.KeyboardDrawing.dialog_new()
        Gkbd.KeyboardDrawing.dialog_set_layout(dialog, self._xkl_wrapper.configreg,
                                               layout_row[0])
        with enlightbox(self.window, dialog):
            dialog.show_all()
            dialog.run()

    def on_selection_changed(self, *args):
        self.layout_selection_changed(self.builder.get_object("layoutSelection"))

    def layout_selection_changed(self, selection):
        # We don't have to worry about multiple rows being selected in this
        # function, because that's disabled by the widget.
        if not selection.count_selected_rows():
            self._upButton.set_sensitive(False)
            self._downButton.set_sensitive(False)
            self._removeButton.set_sensitive(False)
            self._previewButton.set_sensitive(False)
            return

        (store, selected) = selection.get_selected_rows()

        # If something's selected, always enable the remove and preview buttons.
        self._removeButton.set_sensitive(True)
        self._previewButton.set_sensitive(True)

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

