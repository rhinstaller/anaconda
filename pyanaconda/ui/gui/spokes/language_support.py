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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import gi
gi.require_version("Pango", "1.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Pango, Gdk

from pyanaconda.core.constants import PAYLOAD_LIVE_TYPES
from pyanaconda.modules.common.constants.services import LOCALIZATION
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.core.i18n import CN_
from pyanaconda.ui.context import context
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.utils import escape_markup, override_cell_property
from pyanaconda.ui.categories.localization import LocalizationCategory
from pyanaconda.ui.gui.spokes.lib.lang_locale_handler import LangLocaleHandler
from pyanaconda import localization

import re

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["LangsupportSpoke"]

# #fdfbc0
# Sure would be nice if gdk_rgba_parse returned a new object instead of
# modifying an existing one.
_HIGHLIGHT_COLOR = Gdk.RGBA(red=0.992157, green=0.984314, blue=0.752941, alpha=1.0)


class LangsupportSpoke(NormalSpoke, LangLocaleHandler):
    """
       .. inheritance-diagram:: LangsupportSpoke
          :parts: 3
    """
    builderObjects = ["languageStore", "languageStoreFilter", "localeStore", "langsupportWindow"]
    mainWidgetName = "langsupportWindow"
    focusWidgetName = "languageEntry"
    uiFile = "spokes/language_support.glade"
    category = LocalizationCategory
    icon = "accessories-character-map-symbolic"
    title = CN_("GUI|Spoke", "_Language Support")

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "language-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Should the spoke run?"""
        if not is_module_available(LOCALIZATION):
            return False

        if not NormalSpoke.should_run(environment, data):
            return False

        # Don't show the language support spoke on live media.
        return context.payload_type not in PAYLOAD_LIVE_TYPES

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        LangLocaleHandler.__init__(self)
        self._selected_locales = set()

        self._l12_module = LOCALIZATION.get_proxy()

    def initialize(self):
        self.initialize_start()
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

        languageNameColumn = self.builder.get_object("nameColumn")
        nativeNameRenderer = self.builder.get_object("nativeNameRenderer")
        englishNameRenderer = self.builder.get_object("englishNameRenderer")
        override_cell_property(languageNameColumn, nativeNameRenderer, "weight", self._mark_selected_language_bold)
        override_cell_property(languageNameColumn, englishNameRenderer, "weight", self._mark_selected_language_bold)

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

        # report that we are done
        self.initialize_done()

    def apply(self):
        # store only additional langsupport locales
        added = sorted(self._selected_locales - set([self._l12_module.Language]))
        self._l12_module.LanguageSupport = added

    def refresh(self):
        self._languageEntry.set_text("")
        self._selected_locales = set(self._installed_langsupports)

        # select the first locale from the "to be installed" langsupports
        self._select_locale(self._installed_langsupports[0])

    @property
    def _installed_langsupports(self):
        return [self._l12_module.Language] + sorted(self._l12_module.LanguageSupport)

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
                      locale != self._l12_module.Language])

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
