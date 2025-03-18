# Welcome spoke classes
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import sys
import re
import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.spokes import StandaloneSpoke
from pyanaconda.ui.gui.utils import setup_gtk_direction, escape_markup
from pyanaconda.core.async_utils import async_action_wait
from pyanaconda.ui.gui.spokes.lib.beta_warning_dialog import BetaWarningDialog
from pyanaconda.ui.gui.spokes.lib.lang_locale_handler import LangLocaleHandler
from pyanaconda.ui.gui.spokes.lib.unsupported_hardware import UnsupportedHardwareDialog

from pyanaconda import localization
from pyanaconda.product import distributionText, isFinal, productName, productVersion
from pyanaconda import flags
from pyanaconda.core.i18n import _
from pyanaconda.core.util import ipmi_abort
from pyanaconda.core.constants import DEFAULT_LANG, WINDOW_TITLE_TEXT, TIMEZONE_PRIORITY_LANGUAGE
from pyanaconda.modules.common.constants.services import TIMEZONE, LOCALIZATION
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

__all__ = ["WelcomeLanguageSpoke"]


class WelcomeLanguageSpoke(StandaloneSpoke, LangLocaleHandler):
    """
       .. inheritance-diagram:: WelcomeLanguageSpoke
          :parts: 3
    """
    mainWidgetName = "welcomeWindow"
    focusWidgetName = "languageEntry"
    uiFile = "spokes/welcome.glade"
    builderObjects = ["languageStore", "languageStoreFilter", "localeStore", "welcomeWindow"]

    preForHub = SummaryHub
    priority = 0

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "language-pre-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Should the spoke run?"""
        if not is_module_available(LOCALIZATION):
            return False

        return StandaloneSpoke.should_run(environment, data)

    def __init__(self, *args, **kwargs):
        StandaloneSpoke.__init__(self, *args, **kwargs)
        LangLocaleHandler.__init__(self)

        self._l12_module = LOCALIZATION.get_proxy()
        self._tz_module = None
        if is_module_available(TIMEZONE):
            self._tz_module = TIMEZONE.get_proxy()

        self._only_existing_locales = True

    def apply(self):
        (store, itr) = self._localeSelection.get_selected()

        if not itr:
            log.warning("No locale is selected. Skip.")
            return

        locale = store[itr][1]

        self._apply_selected_locale(locale)

    def _apply_selected_locale(self, locale):
        """Apply the selected locale."""
        locale = localization.setup_locale(locale, self._l12_module, text_mode=False)
        self._set_lang(locale)
        self._try_set_timezone(locale)

    @property
    def completed(self):
        if flags.flags.automatedInstall and self._l12_module.LanguageKickstarted:
            return bool(self._l12_module.Language)

    def _row_is_separator(self, model, itr, *args):
        return model[itr][3]

    def initialize(self):
        super().initialize()
        self.initialize_start()
        self._languageStore = self.builder.get_object("languageStore")
        self._languageStoreFilter = self.builder.get_object("languageStoreFilter")
        self._languageEntry = self.builder.get_object("languageEntry")
        self._langSelection = self.builder.get_object("languageViewSelection")
        self._langSelectedRenderer = self.builder.get_object("langSelectedRenderer")
        self._langSelectedColumn = self.builder.get_object("langSelectedColumn")
        self._langView = self.builder.get_object("languageView")
        self._localeView = self.builder.get_object("localeView")
        self._localeStore = self.builder.get_object("localeStore")
        self._localeSelection = self.builder.get_object("localeViewSelection")

        LangLocaleHandler.initialize(self)

        # We need to tell the view whether something is a separator or not.
        self._langView.set_row_separator_func(self._row_is_separator, None)

        # Start with the already set locale. Whether kickstart, geolocation, or default - it does
        # not matter, it's resolved and loaded by now.
        locales = [self._l12_module.Language] or [DEFAULT_LANG]

        # get the data models
        filter_store = self._languageStoreFilter
        store = filter_store.get_model()

        # get language codes for the locales
        langs = [localization.get_language_id(locale) for locale in locales]

        # get common languages and append them here
        common_langs = localization.get_common_languages()
        common_langs_len = len(set(common_langs).difference(set(langs)))
        langs += common_langs

        # check which of the geolocated or common languages have translations
        # and store the iterators for those languages in a dictionary
        langs_with_translations = {}
        itr = store.get_iter_first()
        while itr:
            row_lang = store[itr][2]
            if row_lang in langs:
                langs_with_translations[row_lang] = itr
            itr = store.iter_next(itr)

        # if there are no translations for the given locales,
        # use default
        if not langs_with_translations:
            self._set_lang(DEFAULT_LANG)
            localization.setup_locale(DEFAULT_LANG, self._l12_module, text_mode=False)
            lang_itr, _locale_itr = self._select_locale(self._l12_module.Language)
            langs_with_translations[DEFAULT_LANG] = lang_itr
            locales = [DEFAULT_LANG]

        # go over all geolocated and common languages in reverse order
        # and move those we have translation for to the top of the
        # list, above the separator
        for lang in reversed(langs):
            itr = langs_with_translations.get(lang)
            if itr:
                store.move_after(itr, None)
            else:
                # we don't have translation for this language,
                # so dump all locales for it
                locales = [l for l in locales if localization.get_language_id(l) != lang]

        # And then we add a separator after the selected best language
        # and any additional languages (that have translations) from geoip
        langs_with_translations_len = len(langs_with_translations)
        newItr = store.insert(langs_with_translations_len)
        store.set(newItr, 0, "", 1, "", 2, "", 3, True)

        # add a separator before common languages as well
        commonLangsItr = store.insert(langs_with_translations_len - common_langs_len)
        store.set(commonLangsItr, 0, "", 1, "", 2, "", 3, True)

        # setup the "best" locale
        best_locale = locales[0] if locales else DEFAULT_LANG
        locale = localization.setup_locale(best_locale, self._l12_module)
        self._set_lang(locale)
        self._select_locale(self._l12_module.Language)

        # report that we are done
        self.initialize_done()

    def retranslate(self):
        # Change the translations on labels and buttons that do not have substitution text.
        pickLabel = self.builder.get_object("pickLanguageLabel")
        pickLabel.set_text(_(
            "What language would you like to use during the installation process?"
        ))

        # The welcome label is special - it has text that needs to be substituted.
        welcomeLabel = self.builder.get_object("welcomeLabel")

        welcomeLabel.set_text(_("WELCOME TO %(name)s %(version)s.") %
                {"name" : productName.upper(), "version" : productVersion})         # pylint: disable=no-member

        # Retranslate the language (filtering) entry's placeholder text
        languageEntry = self.builder.get_object("languageEntry")
        languageEntry.set_placeholder_text(_("Type here to search."))

        # And of course, don't forget the underlying window.
        self.window.set_property("distribution", distributionText())
        self.window.retranslate()

        # Retranslate the window title text
        # - it looks like that the main window object is not yet
        #   properly initialized during the first run of the
        #   retranslate method (it is always triggered at startup)
        #   so make sure the object is actually what we think it is
        # - ignoring this run is OK as the initial title is
        #   already translated to the initial language
        if isinstance(self.main_window, Gtk.Window):
            self.main_window.set_title(_(WINDOW_TITLE_TEXT))

            # Correct the language attributes for labels
            self.main_window.reapply_language()

    def refresh(self):
        self._select_locale(self._l12_module.Language)
        self._languageEntry.set_text("")
        self._languageStoreFilter.refilter()

    def _add_language(self, store, native, english, lang):
        native_span = '<span lang="%s">%s</span>' % \
                (escape_markup(lang),
                 escape_markup(native))
        store.append([native_span, english, lang, False])

    def _add_locale(self, store, native, locale):
        native_span = '<span lang="%s">%s</span>' % \
                (escape_markup(re.sub(r'\..*', '', locale)),
                 escape_markup(native))
        store.append([native_span, locale])

    # Signal handlers.
    def on_lang_selection_changed(self, selection):
        (_store, selected) = selection.get_selected_rows()
        LangLocaleHandler.on_lang_selection_changed(self, selection)

        if not selected and hasattr(self.window, "set_may_continue"):
            self.window.set_may_continue(False)

    def on_locale_selection_changed(self, selection):
        (store, selected) = selection.get_selected_rows()
        if hasattr(self.window, "set_may_continue"):
            self.window.set_may_continue(len(selected) > 0)

        if selected:
            lang = store[selected[0]][1]
            lang = localization.setup_locale(lang)
            self._set_lang(lang)
            self.retranslate()

            # Reset the text direction
            setup_gtk_direction()

            # Redraw the window to reset the sidebar to where it needs to be
            self.window.queue_draw()

    # Override the default in StandaloneSpoke so we can display the beta
    # warning dialog first.
    def _on_continue_clicked(self, window, user_data=None):
        # Don't display the betanag dialog if this is the final release.
        if not isFinal:
            dialog = BetaWarningDialog(self.data)

            with self.main_window.enlightbox(dialog.window):
                rc = dialog.run()

            if rc != 1:
                ipmi_abort(scripts=self.data.scripts)
                sys.exit(0)

        dialog = UnsupportedHardwareDialog(self.data)
        if not dialog.supported:

            with self.main_window.enlightbox(dialog.window):
                dialog.refresh()
                rc = dialog.run()

            if rc != 1:
                ipmi_abort(scripts=self.data.scripts)
                sys.exit(0)

        StandaloneSpoke._on_continue_clicked(self, window, user_data)

    @async_action_wait
    def _set_lang(self, lang):
        # This is *hopefully* safe. The only threads that might be running
        # outside of the GIL are those doing file operations, the Gio dbus
        # proxy thread, and calls from the Gtk main loop. The file operations
        # won't be doing things that may access the environment, fingers
        # crossed, the GDbus thread shouldn't be doing anything weird since all
        # of our dbus calls are from python and synchronous. Using
        # gtk_action_wait ensures that this is Gtk main loop thread, and it's
        # holding the GIL.
        #
        # There is a lot of uncertainty and weasliness in those statements.
        # This is not good code.
        #
        # We cannot get around setting $LANG. Python's gettext implementation
        # differs from C in that consults only the environment for the current
        # language and not the data set via setlocale. If we want translations
        # from python modules to work, something needs to be set in the
        # environment when the language changes.

        # pylint: disable=environment-modify
        os.environ["LANG"] = lang

    def _try_set_timezone(self, locale):
        loc_timezones = localization.get_locale_timezones(locale)
        self._tz_module.SetTimezoneWithPriority(loc_timezones[0], TIMEZONE_PRIORITY_LANGUAGE)
