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

from gi.repository import Gkbd, Gdk, Gtk

from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.categories.localization import LocalizationCategory
from pyanaconda.ui.gui.utils import gtk_call_once, escape_markup, gtk_batch_map, timed_action
from pyanaconda.ui.gui.utils import override_cell_property
from pyanaconda.ui.gui.xkl_wrapper import XklWrapper, XklWrapperError
from pyanaconda import keyboard
from pyanaconda import flags
from pyanaconda.i18n import _, N_, CN_
from pyanaconda.constants import DEFAULT_KEYBOARD, THREAD_KEYBOARD_INIT, THREAD_ADD_LAYOUTS_INIT
from pyanaconda.ui.communication import hubQ
from pyanaconda.iutil import strip_accents
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.iutil import have_word_match

import locale as locale_mod

import logging
log = logging.getLogger("anaconda")

__all__ = ["KeyboardSpoke"]

# %s will be replaced by key combination like Alt+Shift
LAYOUT_SWITCHING_INFO = N_("%s to switch layouts.")

ADD_LAYOUTS_INITIALIZE_THREAD = "AnaAddLayoutsInitializeThread"

def _show_layout(column, renderer, model, itr, wrapper):
    return wrapper.get_layout_variant_description(model[itr][0])

def _show_description(column, renderer, model, itr, wrapper):
    value = wrapper.get_switch_opt_description(model[itr][0])
    if model[itr][1]:
        value = "<b>%s</b>" % escape_markup(value)
    return value

class AddLayoutDialog(GUIObject):
    builderObjects = ["addLayoutDialog", "newLayoutStore",
                      "newLayoutStoreFilter", "newLayoutStoreSort"]
    mainWidgetName = "addLayoutDialog"
    uiFile = "spokes/keyboard.glade"

    def __init__(self, *args):
        GUIObject.__init__(self, *args)
        self._xkl_wrapper = XklWrapper.get_instance()
        self._chosen_layouts = []

    def matches_entry(self, model, itr, user_data=None):
        entry_text = self._entry.get_text()
        if not entry_text:
            # everything matches empty string
            return True

        value = model[itr][0]
        eng_value = self._xkl_wrapper.get_layout_variant_description(value, xlated=False)
        xlated_value = self._xkl_wrapper.get_layout_variant_description(value)
        translit_value = strip_accents(xlated_value).lower()
        entry_text = unicode(entry_text, "utf-8").lower()

        return have_word_match(entry_text, eng_value) or have_word_match(entry_text, xlated_value) \
            or have_word_match(entry_text, translit_value)

    def compare_layouts(self, model, itr1, itr2, user_data=None):
        """
        We want to sort layouts by their show strings not their names.
        This function is an instance of GtkTreeIterCompareFunc().

        """

        value1 = model[itr1][0]
        value2 = model[itr2][0]
        show_str1 = self._xkl_wrapper.get_layout_variant_description(value1)
        show_str2 = self._xkl_wrapper.get_layout_variant_description(value2)

        return locale_mod.strcoll(show_str1, show_str2)

    def refresh(self):
        selected = self._newLayoutSelection.count_selected_rows()
        self._confirmAddButton.set_sensitive(selected)
        self._entry.grab_focus()

    def initialize(self):
        # We want to store layouts' names but show layouts as
        # 'language (description)'.
        self._entry = self.builder.get_object("addLayoutEntry")
        layoutColumn = self.builder.get_object("newLayoutColumn")
        layoutRenderer = self.builder.get_object("newLayoutRenderer")
        override_cell_property(layoutColumn, layoutRenderer, "text", _show_layout,
                               self._xkl_wrapper)
        self._treeModelFilter = self.builder.get_object("newLayoutStoreFilter")
        self._treeModelFilter.set_visible_func(self.matches_entry, None)
        self._treeModelSort = self.builder.get_object("newLayoutStoreSort")
        self._treeModelSort.set_default_sort_func(self.compare_layouts, None)

        self._confirmAddButton = self.builder.get_object("confirmAddButton")
        self._newLayoutSelection = self.builder.get_object("newLayoutSelection")

        self._store = self.builder.get_object("newLayoutStore")
        threadMgr.add(AnacondaThread(name=THREAD_ADD_LAYOUTS_INIT,
                                     target=self._initialize))

    def _initialize(self):
        gtk_batch_map(self._addLayout, self._xkl_wrapper.get_available_layouts(),
                      args=(self._store,), batch_size=20)

    def wait_initialize(self):
        threadMgr.wait(THREAD_ADD_LAYOUTS_INIT)

    def run(self):
        self.window.show()
        rc = self.window.run()
        self.window.hide()
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

    @timed_action()
    def on_entry_changed(self, *args):
        self._treeModelFilter.refilter()

    def on_entry_icon_clicked(self, *args):
        self._entry.set_text("")

    def on_layout_view_button_press(self, widget, event, *args):
        if event.type == Gdk.EventType._2BUTTON_PRESS and \
                self._confirmAddButton.get_sensitive():
            # double-click should close the dialog if something is selected
            # (i.e. the Add button is sensitive)
            # @see on_add_layout_selection_changed
            self._confirmAddButton.emit("clicked")

        # let the other actions happen as well
        return False

    def _addLayout(self, name, store):
        store.append([name])


class ConfigureSwitchingDialog(GUIObject):
    """Class representing a dialog for layout switching configuration"""

    builderObjects = ["switchingDialog", "switchingOptsStore",
                      "switchingOptsSort",]
    mainWidgetName = "switchingDialog"
    uiFile = "spokes/keyboard.glade"

    def __init__(self, *args):
        GUIObject.__init__(self, *args)
        self._xkl_wrapper = XklWrapper.get_instance()

        self._switchingOptsStore = self.builder.get_object("switchingOptsStore")

    def initialize(self):
        # we want to display "Alt + Shift" rather than "grp:alt_shift_toggle"
        descColumn = self.builder.get_object("descColumn")
        descRenderer = self.builder.get_object("descRenderer")
        override_cell_property(descColumn, descRenderer, "markup", _show_description,
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
        show_str1 = self._xkl_wrapper.get_switch_opt_description(value1)
        show_str2 = self._xkl_wrapper.get_switch_opt_description(value2)

        if show_str1 < show_str2:
            return -1
        elif show_str1 == show_str2:
            return 0
        else:
            return 1

    @property
    def checked_options(self):
        """Property returning all checked options from the list"""

        ret = [row[0] for row in self._switchingOptsSort if row[1] and row[0]]
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
    helpFile = "KeyboardSpoke.xml"

    category = LocalizationCategory

    icon = "input-keyboard-symbolic"
    title = CN_("GUI|Spoke", "_KEYBOARD")

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        self._remove_last_attempt = False
        self._confirmed = False
        self._xkl_wrapper = XklWrapper.get_instance()
        self._add_dialog = None
        self._ready = False

        self._upButton = self.builder.get_object("upButton")
        self._downButton = self.builder.get_object("downButton")
        self._removeButton = self.builder.get_object("removeLayoutButton")
        self._previewButton = self.builder.get_object("previewButton")

    def apply(self):
        # the user has confirmed (seen) the configuration
        self._confirmed = True

        # Clear and repopulate self.data with actual values
        self.data.keyboard.x_layouts = list()
        self.data.keyboard.seen = True

        for row in self._store:
            self.data.keyboard.x_layouts.append(row[0])

    @property
    def completed(self):
        if flags.flags.automatedInstall and not self.data.keyboard.seen:
            return False
        elif not self._confirmed and \
                self._xkl_wrapper.get_current_layout() != self.data.keyboard.x_layouts[0] and \
                not flags.flags.usevnc:
            # the currently activated layout is a different one from the
            # installed system's default. Ignore VNC, since VNC keymaps are
            # weird and more on the client side.
            return False
        else:
            return True

    @property
    def status(self):
        # We don't need to check that self._store is empty, because that isn't allowed.
        descriptions = (self._xkl_wrapper.get_layout_variant_description(row[0])
                        for row in self._store)
        return ", ".join(descriptions)

    @property
    def ready(self):
        return self._ready and threadMgr.get(ADD_LAYOUTS_INITIALIZE_THREAD) is None

    def initialize(self):
        NormalSpoke.initialize(self)
        self._add_dialog = AddLayoutDialog(self.data)
        self._add_dialog.initialize()

        if flags.can_touch_runtime_system("hide runtime keyboard configuration "
                                          "warning", touch_live=True):
            self.builder.get_object("warningBox").hide()

        # We want to store layouts' names but show layouts as
        # 'language (description)'.
        layoutColumn = self.builder.get_object("layoutColumn")
        layoutRenderer = self.builder.get_object("layoutRenderer")
        override_cell_property(layoutColumn, layoutRenderer, "text", _show_layout,
                                            self._xkl_wrapper)

        self._store = self.builder.get_object("addedLayoutStore")
        self._add_data_layouts()

        self._selection = self.builder.get_object("layoutSelection")

        self._switching_dialog = ConfigureSwitchingDialog(self.data)
        self._switching_dialog.initialize()

        self._layoutSwitchLabel = self.builder.get_object("layoutSwitchLabel")

        if not flags.can_touch_runtime_system("test X layouts", touch_live=True):
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

        hubQ.send_not_ready(self.__class__.__name__)
        hubQ.send_message(self.__class__.__name__,
                          _("Getting list of layouts..."))
        threadMgr.add(AnacondaThread(name=THREAD_KEYBOARD_INIT,
                                     target=self._wait_ready))

    def _wait_ready(self):
        self._add_dialog.wait_initialize()
        self._ready = True
        hubQ.send_ready(self.__class__.__name__, False)

    def refresh(self):
        NormalSpoke.refresh(self)

        # Clear out the layout testing box every time the spoke is loaded.  It
        # doesn't make sense to leave temporary data laying around.
        buf = self.builder.get_object("layoutTestBuffer")
        buf.set_text("")

        # Clear and repopulate addedLayoutStore with values from self.data
        self._store.clear()
        self._add_data_layouts()

        # Start with no buttons enabled, since nothing is selected.
        self._upButton.set_sensitive(False)
        self._downButton.set_sensitive(False)
        self._removeButton.set_sensitive(False)
        self._previewButton.set_sensitive(False)

        self._refresh_switching_info()

    def _addLayout(self, store, name):
        # first try to add the layout
        if flags.can_touch_runtime_system("add runtime X layout", touch_live=True):
            self._xkl_wrapper.add_layout(name)

        # valid layout, append it to the store
        store.append([name])

    def _removeLayout(self, store, itr):
        """
        Remove the layout specified by store iterator from the store and
        X runtime configuration.

        """

        if flags.can_touch_runtime_system("remove runtime X layout", touch_live=True):
            self._xkl_wrapper.remove_layout(store[itr][0])
        store.remove(itr)

    def _refresh_switching_info(self):
        if self.data.keyboard.switch_options:
            first_option = self.data.keyboard.switch_options[0]
            desc = self._xkl_wrapper.get_switch_opt_description(first_option)

            self._layoutSwitchLabel.set_text(_(LAYOUT_SWITCHING_INFO) % desc)
        else:
            self._layoutSwitchLabel.set_text(_("Layout switching not "
                                               "configured."))

    # Signal handlers.
    def on_add_clicked(self, button):
        self._add_dialog.refresh()

        with self.main_window.enlightbox(self._add_dialog.window):
            response = self._add_dialog.run()

        if response == 1:
            duplicates = set()
            for row in self._store:
                item = row[0]
                if item in self._add_dialog.chosen_layouts:
                    duplicates.add(item)

            for layout in self._add_dialog.chosen_layouts:
                if layout not in duplicates:
                    self._addLayout(self._store, layout)

            if self._remove_last_attempt:
                itr = self._store.get_iter_first()
                if not self._store[itr][0] in self._add_dialog.chosen_layouts:
                    self._removeLayout(self._store, itr)
                self._remove_last_attempt = False

            # Update the selection information
            self._selection.emit("changed")

    def on_remove_clicked(self, button):
        if not self._selection.count_selected_rows():
            return

        (store, itr) = self._selection.get_selected()
        itr2 = store.get_iter_first()
        #if the first item is selected, try to select the next one
        if store[itr][0] == store[itr2][0]:
            itr2 = store.iter_next(itr2)
            if itr2: #next one existing
                self._selection.select_iter(itr2)
                self._removeLayout(store, itr)
                # Re-emit the selection changed signal now that the backing store is updated
                # in order to update the first/last/only-based button sensitivities
                self._selection.emit("changed")
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
        self._selection.select_iter(itr2)

    def on_up_clicked(self, button):
        if not self._selection.count_selected_rows():
            return

        (store, cur) = self._selection.get_selected()
        prev = store.iter_previous(cur)
        if not prev:
            return

        store.swap(cur, prev)
        if flags.can_touch_runtime_system("reorder runtime X layouts", touch_live=True):
            self._flush_layouts_to_X()

        if not store.iter_previous(cur):
            #layout is first in the list (set as default), activate it
            self._xkl_wrapper.activate_default_layout()

        self._selection.emit("changed")

    def on_down_clicked(self, button):
        if not self._selection.count_selected_rows():
            return

        (store, cur) = self._selection.get_selected()

        #if default layout (first in the list) changes we need to activate it
        activate_default = not store.iter_previous(cur)

        nxt = store.iter_next(cur)
        if not nxt:
            return

        store.swap(cur, nxt)
        if flags.can_touch_runtime_system("reorder runtime X layouts", touch_live=True):
            self._flush_layouts_to_X()

        if activate_default:
            self._xkl_wrapper.activate_default_layout()

        self._selection.emit("changed")

    def on_preview_clicked(self, button):
        (store, cur) = self._selection.get_selected()
        layout_row = store[cur]
        if not layout_row:
            return

        layout, variant = keyboard.parse_layout_variant(layout_row[0])

        if variant:
            lay_var_spec = "%s\t%s" % (layout, variant)
        else:
            lay_var_spec = layout

        dialog = Gkbd.KeyboardDrawing.dialog_new()
        Gkbd.KeyboardDrawing.dialog_set_layout(dialog, self._xkl_wrapper.configreg,
                                               lay_var_spec)
        dialog.set_size_request(750, 350)
        dialog.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        with self.main_window.enlightbox(dialog):
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

        # If only one row is available, disable both the Up and Down button
        if len(store) == 1:
            self._upButton.set_sensitive(False)
            self._downButton.set_sensitive(False)
        else:
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

        with self.main_window.enlightbox(self._switching_dialog.window):
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
        if not self.data.keyboard.x_layouts:
            # nothing specified, just add the default
            self._addLayout(self._store, DEFAULT_KEYBOARD)
            return

        valid_layouts = []
        for layout in self.data.keyboard.x_layouts:
            try:
                self._addLayout(self._store, layout)
                valid_layouts += layout
            except XklWrapperError:
                log.error("Failed to add layout '%s'", layout)

        if not valid_layouts:
            log.error("No valid layout given, falling back to default %s", DEFAULT_KEYBOARD)
            self._addLayout(self._store, DEFAULT_KEYBOARD)
            self.data.keyboard.x_layouts = [DEFAULT_KEYBOARD]

    def _flush_layouts_to_X(self):
        layouts_list = list()

        for row in self._store:
            layouts_list.append(row[0])

        self._xkl_wrapper.replace_layouts(layouts_list)
