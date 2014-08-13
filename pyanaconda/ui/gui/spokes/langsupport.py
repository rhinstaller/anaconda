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
#                    Vratislav Podzimek <vpodzime@redhat.com>
#

from gi.repository import Pango, Gdk
from pyanaconda.flags import flags
from pyanaconda.i18n import CN_
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.utils import escape_markup, override_cell_property
from pyanaconda.ui.categories.localization import LocalizationCategory
from pyanaconda.ui.gui.spokes.lib.lang_locale_handler import LangLocaleHandler
from pyanaconda import localization

import re

import logging
log = logging.getLogger("anaconda")

__all__ = ["LangsupportSpoke"]

# #fdfbc0
# Sure would be nice if gdk_rgba_parse returned a new object instead of
# modifying an existing one.
_HIGHLIGHT_COLOR = Gdk.RGBA(red=0.992157, green=0.984314, blue=0.752941, alpha=1.0)

class LangsupportSpoke(LangLocaleHandler, NormalSpoke):
    builderObjects = ["languageStore", "languageStoreFilter", "localeStore", "langsupportWindow"]
    mainWidgetName = "langsupportWindow"
    focusWidgetName = "languageEntry"
    uiFile = "spokes/langsupport.glade"
    helpFile = "LangSupportSpoke.xml"

    category = LocalizationCategory

    icon = "accessories-character-map-symbolic"
    title = CN_("GUI|Spoke", "_LANGUAGE SUPPORT")

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        LangLocaleHandler.__init__(self)
        self._selected_locales = set()

    def initialize(self):
        self._languageStore = self.builder.get_object("languageStore")
        self._languageEntry = self.builder.get_object("languageEntry")
        self._languageStoreFilter = self.builder.get_object("languageStoreFilter")
        self._langView = self.builder.get_object("languageView")
        self._langSelectedRenderer = self.builder.get_object("langSelectedRenderer")
        self._langSelectedColumn = self.builder.get_object("langSelectedColumn")
        self._langSelection = self.builder.get_object("languageViewSelection")
        self._localeStore = self.builder.get_object("localeStore")
        self._localeView = self.builder.get_object("localeView")

        LangLocaleHandler.initialize(self)

        # mark selected locales and languages with selected locales bold
        localeNativeColumn = self.builder.get_object("localeNativeName")
        localeNativeNameRenderer = self.builder.get_object("localeNativeNameRenderer")
        override_cell_property(localeNativeColumn, localeNativeNameRenderer,
                "weight", self._mark_selected_locale_bold)

        for col, rend in [("nativeName", "nativeNameRenderer"),
                          ("englishName", "englishNameRenderer")]:
            column = self.builder.get_object(col)
            renderer = self.builder.get_object(rend)
            override_cell_property(column, renderer, "weight", self._mark_selected_language_bold)

        # If a language has selected locales, highlight every column so that
        # the row appears highlighted
        for col in self._langView.get_columns():
            for rend in col.get_cells():
                override_cell_property(col, rend, "cell-background-rgba",
                        self._highlight_selected_language)

        # and also set an icon so that we don't depend on a color to convey information
        highlightedColumn = self.builder.get_object("highlighted")
        highlightedRenderer = self.builder.get_object("highlightedRenderer")
        override_cell_property(highlightedColumn, highlightedRenderer,
                "icon-name", self._render_lang_highlighted)

    def apply(self):
        # store only additional langsupport locales
        self.data.lang.addsupport = sorted(self._selected_locales - set([self.data.lang.lang]))

    def refresh(self):
        self._languageEntry.set_text("")
        self._selected_locales = set(self._installed_langsupports)

        # select the first locale from the "to be installed" langsupports
        self._select_locale(self._installed_langsupports[0])

    @property
    def _installed_langsupports(self):
        return [self.data.lang.lang] + sorted(self.data.lang.addsupport)

    @property
    def showable(self):
        return not flags.livecdInstall

    @property
    def status(self):
        return ", ".join(localization.get_native_name(locale)
                         for locale in self._installed_langsupports)

    @property
    def mandatory(self):
        return False

    @property
    def completed(self):
        return True

    def _add_language(self, store, native, english, lang):
        native_span = '<span lang="%s">%s</span>' % \
                (escape_markup(lang), escape_markup(native))
        store.append([native_span, english, lang])

    def _add_locale(self, store, native, locale):
        native_span = '<span lang="%s">%s</span>' % \
                (escape_markup(re.sub(r'\..*', '', locale)),
                 escape_markup(native))

        # native, locale, selected, additional
        store.append([native_span, locale, locale in self._selected_locales,
                      locale != self.data.lang.lang])

    def _mark_selected_locale_bold(self, column, renderer, model, itr, user_data=None):
        if model[itr][2]:
            return Pango.Weight.BOLD.real
        else:
            return Pango.Weight.NORMAL.real

    def _is_lang_selected(self, lang):
        lang_locales = set(localization.get_language_locales(lang))
        return not lang_locales.isdisjoint(self._selected_locales)

    def _mark_selected_language_bold(self, column, renderer, model, itr, user_data=None):
        if self._is_lang_selected(model[itr][2]):
            return Pango.Weight.BOLD.real
        else:
            return Pango.Weight.NORMAL.real

    def _highlight_selected_language(self, column, renderer, model, itr, user_data=None):
        if self._is_lang_selected(model[itr][2]):
            return _HIGHLIGHT_COLOR
        else:
            return None

    def _render_lang_highlighted(self, column, renderer, model, itr, user_data=None):
        if self._is_lang_selected(model[itr][2]):
            return "emblem-ok-symbolic"
        else:
            return None

    # Signal handlers.
    def on_locale_toggled(self, renderer, path):
        itr = self._localeStore.get_iter(path)
        row = self._localeStore[itr]

        row[2] = not row[2]

        if row[2]:
            self._selected_locales.add(row[1])
        else:
            self._selected_locales.remove(row[1])
