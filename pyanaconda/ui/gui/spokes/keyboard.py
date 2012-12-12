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

# pylint: disable-msg=E0611
from gi.repository import GLib, Gkbd, Gtk, Gdk

from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.localization import LocalizationCategory
from pyanaconda.ui.gui.utils import enlightbox, gtk_call_once
from pyanaconda import keyboard
from pyanaconda import flags

__all__ = ["KeyboardSpoke"]

# %s will be replaced by key combination like Alt+Shift
LAYOUT_SWITCHING_INFO = N_("%s to switch layouts.")

def _show_layout(column, renderer, model, itr, wrapper):
    value = wrapper.name_to_show_str[model[itr][0]]
    renderer.set_property("text", value)

def _show_description(column, renderer, model, itr, wrapper):
    value = wrapper.switch_to_show_str[model[itr][0]]
    if model[itr][1]:
        value = "<b>%s</b>" % value
    renderer.set_property("markup", value)

class AddLayoutDialog(GUIObject):
    builderObjects = ["addLayoutDialog", "newLayoutStore",
                      "newLayoutStoreFilter", "newLayoutStoreSort"]
    mainWidgetName = "addLayoutDialog"
    uiFile = "spokes/keyboard.glade"

    def __init__(self, *args):
        GUIObject.__init__(self, *args)
        self._xkl_wrapper = keyboard.XklWrapper.get_instance()

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

    def compare_layouts(self, model, itr1, itr2, user_data=None):
        """
        We want to sort layouts by their show strings not their names.
        This function is an instance of GtkTreeIterCompareFunc().

        """

        value1 = model[itr1][0]
        value2 = model[itr2][0]
        show_str1 = self._xkl_wrapper.name_to_show_str[value1]
        show_str2 = self._xkl_wrapper.name_to_show_str[value2]

        if show_str1 < show_str2:
            return -1
        elif show_str1 == show_str2:
            return 0
        else:
            return 1

    def refresh(self):
        self._entry.grab_focus()

    def initialize(self):
        # We want to store layouts' names but show layouts as
        # 'language (description)'.
        self._entry = self.builder.get_object("addLayoutEntry")
        layoutColumn = self.builder.get_object("newLayoutColumn")
        layoutRenderer = self.builder.get_object("newLayoutRenderer")
        layoutColumn.set_cell_data_func(layoutRenderer, _show_layout,
                                            self._xkl_wrapper)
        self._treeModelFilter = self.builder.get_object("newLayoutStoreFilter")
        self._treeModelFilter.set_visible_func(self.matches_entry, None)
        self._treeModelSort = self.builder.get_object("newLayoutStoreSort")
        self._treeModelSort.set_default_sort_func(self.compare_layouts, None)

        self._store = self.builder.get_object("newLayoutStore")
        for layout in self._xkl_wrapper.get_available_layouts():
            self._addLayout(self._store, layout)

        self._confirmAddButton = self.builder.get_object("confirmAddButton")

        self._newLayoutSelection = self.builder.get_object("newLayoutSelection")
        selected = self._newLayoutSelection.count_selected_rows()
        self._confirmAddButton.set_sensitive(selected)

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

    def on_add_layout_selection_changed(self, selection):
        selected = selection.count_selected_rows()
        self._confirmAddButton.set_sensitive(selected)

    def on_entry_changed(self, *args):
        self._treeModelFilter.refilter()

    def on_entry_icon_clicked(self, *args):
        self._entry.set_text("")

    def on_layout_view_button_press(self, widget, event, *args):
        # BUG: Gdk.EventType.2BUTTON_PRESS results in syntax error
        if event.type == getattr(Gdk.EventType, "2BUTTON_PRESS"):
            # double-click should close the dialog
            button = self.builder.get_object("confirmAddButton")
            button.emit("clicked")

        # let the other actions happen as well
        return False

    def _addLayout(self, store, name):
        store.append([name])


class ConfigureSwitchingDialog(GUIObject):
    """Class representing a dialog for layout switching configuration"""

    builderObjects = ["switchingDialog", "switchingOptsStore",
                      "switchingOptsSort",]
    mainWidgetName = "switchingDialog"
    uiFile = "spokes/keyboard.glade"

    def __init__(self, *args):
        GUIObject.__init__(self, *args)
        self._xkl_wrapper = keyboard.XklWrapper.get_instance()

        self._switchingOptsStore = self.builder.get_object("switchingOptsStore")

    def initialize(self):
        # we want to display "Alt + Shift" rather than "grp:alt_shift_toggle"
        descColumn = self.builder.get_object("descColumn")
        descRenderer = self.builder.get_object("descRenderer")
        descColumn.set_cell_data_func(descRenderer, _show_description,
                                            self._xkl_wrapper)

        self._switchingOptsSort = self.builder.get_object("switchingOptsSort")
        self._switchingOptsSort.set_default_sort_func(self._compare_options, None)

        for opt in self._xkl_wrapper.get_switching_options():
            self._add_option(opt)

    def refresh(self):
        itr = self._switchingOptsStore.get_iter_first()
        while itr:
            option = self._switchingOptsStore[itr][0]
            if option in self.data.keyboard.switch_options:
                self._switchingOptsStore.set_value(itr, 1, True)
            else:
                self._switchingOptsStore.set_value(itr, 1, False)

            itr = self._switchingOptsStore.iter_next(itr)

    def run(self):
        rc = self.window.run()
        self.window.hide()
        return rc

    def _add_option(self, option):
        """Add option to the list as unchecked"""

        self._switchingOptsStore.append([option, False])

    def _compare_options(self, model, itr1, itr2, user_data=None):
        """
        We want to sort options by their show strings not their names.
        This function is an instance of GtkTreeIterCompareFunc().

        """

        value1 = model[itr1][0]
        value2 = model[itr2][0]
        show_str1 = self._xkl_wrapper.switch_to_show_str[value1]
        show_str2 = self._xkl_wrapper.switch_to_show_str[value2]

        if show_str1 < show_str2:
            return -1
        elif show_str1 == show_str2:
            return 0
        else:
            return 1

    @property
    def checked_options(self):
        """Property returning all checked options from the list"""

        ret = [row[0] for row in self._switchingOptsStore if row[1] and row[0]]
        return ret

    def on_use_option_toggled(self, renderer, path, *args):
        itr = self._switchingOptsSort.get_iter(path)

        # Get itr for the *store*.
        itr = self._switchingOptsSort.convert_iter_to_child_iter(itr)
        old_value = self._switchingOptsStore[itr][1]

        self._switchingOptsStore.set_value(itr, 1, not old_value)


class KeyboardSpoke(NormalSpoke):
    builderObjects = ["addedLayoutStore", "keyboardWindow",
                      "layoutTestBuffer"]
    mainWidgetName = "keyboardWindow"
    uiFile = "spokes/keyboard.glade"

    category = LocalizationCategory

    icon = "input-keyboard-symbolic"
    title = N_("KEYBOARD")

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        self._remove_last_attempt = False
        self._xkl_wrapper = keyboard.XklWrapper.get_instance()

    def apply(self):
        # Clear and repopulate self.data with actual values
        self.data.keyboard.x_layouts = list()
        for row in self._store:
            self.data.keyboard.x_layouts.append(row[0])
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

        if flags.can_touch_runtime_system("hide runtime keyboard configuration "
                                          "warning"):
            self.builder.get_object("warningBox").hide()

        # We want to store layouts' names but show layouts as
        # 'language (description)'.
        layoutColumn = self.builder.get_object("layoutColumn")
        layoutRenderer = self.builder.get_object("layoutRenderer")
        layoutColumn.set_cell_data_func(layoutRenderer, _show_layout,
                                            self._xkl_wrapper)

        self._store = self.builder.get_object("addedLayoutStore")
        self._add_data_layouts()

        self._switching_dialog = ConfigureSwitchingDialog(self.data)
        self._switching_dialog.initialize()

        self._layoutSwitchLabel = self.builder.get_object("layoutSwitchLabel")

        if not flags.can_touch_runtime_system("test X layouts"):
            # Disable area for testing layouts as we cannot make
            # it work without modifying runtime system

            widgets = [self.builder.get_object("testingLabel"),
                       self.builder.get_object("testingWindow"),
                       self.builder.get_object("layoutSwitchLabel")]

            # Use testingLabel's text to explain why this part is not
            # sensitive.
            widgets[0].set_text(_("Testing layouts configuration not "
                                  "available."))

            for widget in widgets:
                widget.set_sensitive(False)

    def refresh(self):
        NormalSpoke.refresh(self)

        # Clear out the layout testing box every time the spoke is loaded.  It
        # doesn't make sense to leave temporary data laying around.
        buf = self.builder.get_object("layoutTestBuffer")
        buf.set_text("")

        # Clear and repopulate addedLayoutStore with values from self.data
        self._store.clear()
        self._add_data_layouts()

        self._upButton = self.builder.get_object("upButton")
        self._downButton = self.builder.get_object("downButton")
        self._removeButton = self.builder.get_object("removeLayoutButton")
        self._previewButton = self.builder.get_object("previewButton")

        # Start with no buttons enabled, since nothing is selected.
        self._upButton.set_sensitive(False)
        self._downButton.set_sensitive(False)
        self._removeButton.set_sensitive(False)
        self._previewButton.set_sensitive(False)

        self._refresh_switching_info()

    def _addLayout(self, store, name):
        store.append([name])
        if flags.can_touch_runtime_system("add runtime X layout"):
            self._xkl_wrapper.add_layout(name)

    def _removeLayout(self, store, itr):
        """
        Remove the layout specified by store iterator from the store and
        X runtime configuration.

        """

        if flags.can_touch_runtime_system("remove runtime X layout"):
            self._xkl_wrapper.remove_layout(store[itr][0])
        store.remove(itr)

    def _refresh_switching_info(self):
        if self.data.keyboard.switch_options:
            first_option = self.data.keyboard.switch_options[0]
            desc = self._xkl_wrapper.switch_to_show_str[first_option]

            self._layoutSwitchLabel.set_text(_(LAYOUT_SWITCHING_INFO) % desc)
        else:
            self._layoutSwitchLabel.set_text(_("Layout switching not "
                                               "configured."))

    # Signal handlers.
    def on_add_clicked(self, button):
        dialog = AddLayoutDialog(self.data)
        dialog.initialize()
        dialog.refresh()

        with enlightbox(self.window, dialog.window):
            response = dialog.run()

        if response == 1:
            duplicates = set()
            for row in self._store:
                item = row[0]
                if item in dialog.chosen_layouts:
                    duplicates.add(item)

            for layout in dialog.chosen_layouts:
                if layout not in duplicates:
                    self._addLayout(self._store, layout)

            if self._remove_last_attempt:
                itr = self._store.get_iter_first()
                if not self._store[itr][0] in dialog.chosen_layouts:
                    self._removeLayout(self._store, itr)
                self._remove_last_attempt = False

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
                self._removeLayout(store, itr)
                return

            #nothing left, run AddLayout dialog to replace the current layout
            #add it to GLib.idle to make sure the underlaying gui is correctly
            #redrawn
            self._remove_last_attempt = True
            add_button = self.builder.get_object("addLayoutButton")
            gtk_call_once(self.on_add_clicked, add_button)
            return

        #the selected item is not the first, select the previous one
        #XXX: there is no model.iter_previous() so we have to find it this way
        itr3 = store.iter_next(itr2) #look-ahead iterator
        while itr3 and (store[itr3][0] != store[itr][0]):
            itr2 = store.iter_next(itr2)
            itr3 = store.iter_next(itr3)

        self._removeLayout(store, itr)
        selection.select_iter(itr2)

    def on_up_clicked(self, button):
        selection = self.builder.get_object("layoutSelection")
        if not selection.count_selected_rows():
            return

        (store, cur) = selection.get_selected()
        prev = cur.copy()
        prev = store.iter_previous(prev)
        if not prev:
            return

        store.swap(cur, prev)
        if flags.can_touch_runtime_system("reorder runtime X layouts"):
            self._flush_layouts_to_X()
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
        if flags.can_touch_runtime_system("reorder runtime X layouts"):
            self._flush_layouts_to_X()
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

    def on_selection_changed(self, selection, *args):
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

    def on_options_clicked(self, *args):
        self._switching_dialog.refresh()

        with enlightbox(self.window, self._switching_dialog.window):
            response = self._switching_dialog.run()

        if response != 1:
            # Cancel clicked, dialog destroyed
            return

        # OK clicked, set and save switching options.
        new_options = self._switching_dialog.checked_options
        self._xkl_wrapper.set_switching_options(new_options)
        self.data.keyboard.switch_options = new_options

        # Refresh switching info label.
        self._refresh_switching_info()

    def _add_data_layouts(self):
        if self.data.keyboard.x_layouts:
            for layout in self.data.keyboard.x_layouts:
                self._addLayout(self._store, layout)
        else:
            self._addLayout(self._store, "us")

    def _flush_layouts_to_X(self):
        layouts_list = list()

        for row in self._store:
            layouts_list.append(row[0])

        self._xkl_wrapper.replace_layouts(layouts_list)
