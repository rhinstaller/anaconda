# Language support selection spoke classes
#
# Copyright (C) 2013  Red Hat, Inc.
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

from gi.repository import Gtk, Pango
from pyanaconda.flags import flags
from pyanaconda.i18n import _, N_
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.categories.localization import LocalizationCategory
from pyanaconda.localization import Language, LOCALE_PREFERENCES, expand_langs

import re

import logging
log = logging.getLogger("anaconda")

__all__ = ["LangsupportSpoke"]

COL_NATIVE_NAME   = 0
COL_ENGLISH_NAME  = 1
COL_LANG_SETTING  = 2
COL_SELECTED      = 3
COL_IS_ADDITIONAL = 4

class LangsupportSpoke(NormalSpoke):
    builderObjects = ["langsupportStore", "langsupportStoreFilter", "langsupportWindow"]
    mainWidgetName = "langsupportWindow"
    uiFile = "spokes/langsupport.glade"

    category = LocalizationCategory

    icon = "accessories-character-map-symbolic"
    title = N_("_LANGUAGE SUPPORT")

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)

    def initialize(self):
        self._langsupportStore = self.builder.get_object("langsupportStore")
        self._langsupportEntry = self.builder.get_object("langsupportEntry")
        self._langsupportStoreFilter = self.builder.get_object("langsupportStoreFilter")
        self._langsupportStoreFilter.set_visible_func(self._matches_entry, None)

        # mark selected items in language list bold
        for col, rend, idx in (("englishNameCol", "englishNameRenderer", COL_ENGLISH_NAME),
                               ("nativeNameCol", "nativeNameRenderer", COL_NATIVE_NAME)):
            column = self.builder.get_object(col)
            renderer = self.builder.get_object(rend)
            column.set_cell_data_func(renderer, self._mark_selected_bold, idx)

        language = Language(LOCALE_PREFERENCES, territory=None)
        # source of lang code <-> UI name mapping
        self.locale_infos_for_data = language.translations
        self.locale_infos_for_ui = language.translations

        for code, info in sorted(self.locale_infos_for_ui.items()):
            self._add_language(self._langsupportStore, info.display_name,
                               info.english_name, info.short_name,
                               False, True)

        self._select_language(self._langsupportStore, self.data.lang.lang)

    def apply(self):
        self.data.lang.addsupport = [row[COL_LANG_SETTING]
                                     for row in self._langsupportStore
                                     if row[COL_SELECTED] and row[COL_IS_ADDITIONAL]]

    def refresh(self):
        self._langsupportEntry.set_text("")
        lang_infos = self._find_localeinfos_for_code(self.data.lang.lang, self.locale_infos_for_ui)
        lang_short_names = [info.short_name for info in lang_infos]
        if len(lang_short_names) > 1:
            log.warning("Found multiple locales for lang %s: %s, picking first" %
                        (self.data.lang.lang, lang_short_names))
        # Just take the first found
        # TODO - for corner cases choose the one that is common prefix
        lang_short_names = lang_short_names[:1]

        addsupp_short_names = []
        for code in self.data.lang.addsupport:
            code_infos = self._find_localeinfos_for_code(code, self.locale_infos_for_ui)
            addsupp_short_names.extend(info.short_name for info in code_infos)

        for row in self._langsupportStore:
            if row[COL_LANG_SETTING] in addsupp_short_names:
                row[COL_SELECTED] = True
            if row[COL_LANG_SETTING] in lang_short_names:
                row[COL_SELECTED] = True
                row[COL_IS_ADDITIONAL] = False

    @property
    def showable(self):
        return not flags.livecdInstall

    @property
    def status(self):
        # TODO: translate
        infos = self._find_localeinfos_for_code(self.data.lang.lang, self.locale_infos_for_data)[:1]
        for code in self.data.lang.addsupport:
            for info in self._find_localeinfos_for_code(code, self.locale_infos_for_data):
                if info not in infos:
                    infos.append(info)
        return ", ".join(info.english_name for info in infos)

    @property
    def mandatory(self):
        return False

    @property
    def completed(self):
        return True

    def _find_localeinfos_for_code(self, code, infos):
        try:
            retval = [infos[code]]
        except KeyError:
            retval = [info for _code, info in infos.items()
                      if code in expand_langs(_code)]
            log.debug("locale info found for %s: %s" % (code, retval))
        return retval

    def _add_language(self, store, native, english, setting, selected, additional):
        store.append(['<span lang="%s">%s</span>' % (re.sub('\..*', '', setting), native),
                     english, setting, selected, additional])

    def _select_language(self, store, language):
        itr = store.get_iter_first()
        while itr and language not in expand_langs(store[itr][COL_LANG_SETTING]):
            itr = store.iter_next(itr)

        # If we were provided with an unsupported language, just use the default.
        if not itr:
            return

        treeview = self.builder.get_object("langsupportView")
        selection = treeview.get_selection()
        selection.select_iter(itr)
        path = store.get_path(itr)
        treeview.scroll_to_cell(path)

    def _matches_entry(self, model, itr, *args):
        # Need to strip out the pango markup before attempting to match.
        # Otherwise, starting to type "span" for "spanish" will match everything
        # due to the enclosing span tag.
        (success, attrs, native, accel) = Pango.parse_markup(model[itr][COL_NATIVE_NAME], -1, "_")
        english = model[itr][COL_ENGLISH_NAME]
        entry = self._langsupportEntry.get_text().strip()

        # Nothing in the text entry?  Display everything.
        if not entry:
            return True

        # Otherwise, filter the list showing only what is matched by the
        # text entry.  Either the English or native names can match.
        lowered = entry.lower()
        if lowered in native.lower() or lowered in english.lower():
            return True
        else:
            return False

    def _mark_selected_bold(self, column, renderer, model, itr, idx):
        value = model[itr][idx]
        if model[itr][COL_SELECTED]:
            value = "<b>%s</b>" % value
        renderer.set_property("markup", value)

    def on_langsupport_toggled(self, renderer, path):
        selected = not self._langsupportStoreFilter[path][COL_SELECTED]
        itr = self._langsupportStoreFilter.get_iter(path)
        itr = self._langsupportStoreFilter.convert_iter_to_child_iter(itr)
        self._langsupportStore[itr][COL_SELECTED] = selected

    def on_clear_icon_clicked(self, entry, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            entry.set_text("")

    def on_entry_changed(self, *args):
        self._langsupportStoreFilter.refilter()
