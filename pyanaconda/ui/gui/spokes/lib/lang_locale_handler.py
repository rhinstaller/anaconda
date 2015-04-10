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
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

"""
Module providing the LangLocaleHandler class that could be used as a mixin for
screens handling languages or locales configuration.

"""

import os
from gi.repository import Gtk, Pango
from pyanaconda import localization
from pyanaconda.iutil import strip_accents
from pyanaconda.ui.gui.utils import set_treeview_selection, timed_action, override_cell_property

class LangLocaleHandler(object):
    """
    Class that could be used as a mixin for screens handling languages or
    locales configuration.

    """

    def __init__(self):
        # the class inheriting from this class is responsible for populating
        # these items with actual objects
        self._languageStore = None
        self._languageStoreFilter = None
        self._languageEntry = None
        self._langSelection = None
        self._langSelectedRenderer = None
        self._langSelectedColumn = None
        self._langView = None
        self._localeView = None
        self._localeStore = None
        self._localeSelection = None

        self._arrow = None

    def initialize(self):
        # Render an arrow for the chosen language
        datadir = os.environ.get("ANACONDA_WIDGETS_DATADIR", "/usr/share/anaconda")
        self._right_arrow = Gtk.Image.new_from_file(os.path.join(datadir, "pixmaps", "right-arrow-icon.png"))
        self._left_arrow = Gtk.Image.new_from_file(os.path.join(datadir, "pixmaps", "left-arrow-icon.png"))
        override_cell_property(self._langSelectedColumn, self._langSelectedRenderer,
                               "pixbuf", self._render_lang_selected)

        # fill the list with available translations
        for lang in localization.get_available_translations():
            self._add_language(self._languageStore,
                               localization.get_native_name(lang),
                               localization.get_english_name(lang), lang)

        # make filtering work
        self._languageStoreFilter.set_visible_func(self._matches_entry, None)

    def _matches_entry(self, model, itr, *args):
        # Nothing in the text entry?  Display everything.
        entry = self._languageEntry.get_text().strip()
        if not entry:
            return True

        # Need to strip out the pango markup before attempting to match.
        # Otherwise, starting to type "span" for "spanish" will match everything
        # due to the enclosing span tag.
        # (success, attrs, native, accel)
        native = Pango.parse_markup(model[itr][0], -1, "_")[2]
        english = model[itr][1]

        # Otherwise, filter the list showing only what is matched by the
        # text entry.  Either the English or native names can match.
        # Convert strings to unicode so lower() works.
        lowered = entry.decode('utf-8').lower()
        native = native.decode('utf-8').lower()
        english = english.decode('utf-8').lower()
        translit = strip_accents(native).lower()

        if lowered in native or lowered in english or lowered in translit:
            return True
        else:
            return False

    def _render_lang_selected(self, column, renderer, model, itr, user_data=None):
        (lang_store, sel_itr) = self._langSelection.get_selected()

        if Gtk.get_locale_direction() == Gtk.TextDirection.LTR:
            _arrow = self._right_arrow
        else:
            _arrow = self._left_arrow

        if sel_itr and lang_store[sel_itr][2] == model[itr][2]:
            return _arrow.get_pixbuf()
        else:
            return None

    def _add_language(self, store, native, english, lang):
        """Override this method with a valid implementation"""

        raise NotImplementedError()

    def _add_locale(self, store, native, locale):
        """Override this method with a valid implementation"""

        raise NotImplementedError()

    def _select_locale(self, locale):
        """
        Try to select the given locale in the language and locale
        treeviews. This method tries to find the best match for the given
        locale.

        :return: a pair of selected iterators (language and locale)
        :rtype: a pair of GtkTreeIter or None objects

        """

        # get lang and select it
        parts = localization.parse_langcode(locale)
        if "language" not in parts:
            # invalid locale, cannot select
            return (None, None)

        lang_itr = set_treeview_selection(self._langView, parts["language"], col=2)

        # find matches and use the one with the highest rank
        locales = localization.get_language_locales(locale)
        locale_itr = set_treeview_selection(self._localeView, locales[0], col=1)

        return (lang_itr, locale_itr)

    def _refresh_locale_store(self, lang):
        """Refresh the localeStore with locales for the given language."""

        self._localeStore.clear()
        locales = localization.get_language_locales(lang)
        for locale in locales:
            self._add_locale(self._localeStore,
                             localization.get_native_name(locale),
                             locale)

        # select the first locale (with the highest rank)
        set_treeview_selection(self._localeView, locales[0], col=1)

    def on_lang_selection_changed(self, selection):
        (store, selected) = selection.get_selected_rows()

        if selected:
            lang = store[selected[0]][2]
            self._refresh_locale_store(lang)
        else:
            self._localeStore.clear()

    def on_clear_icon_clicked(self, entry, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            entry.set_text("")

    @timed_action()
    def on_entry_changed(self, *args):
        self._languageStoreFilter.refilter()

