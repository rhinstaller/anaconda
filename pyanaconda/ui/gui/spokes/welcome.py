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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#                    Vratislav Podzimek <vpodzime@redhat.com>
#

import sys
import re
import langtable

from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.spokes import StandaloneSpoke
from pyanaconda.ui.gui.utils import enlightbox, setup_gtk_direction
from pyanaconda.ui.gui.spokes.lib.lang_locale_handler import LangLocaleHandler

from pyanaconda import localization
from pyanaconda.product import distributionText, isFinal, productName, productVersion
from pyanaconda import keyboard
from pyanaconda import flags
from pyanaconda import geoloc
from pyanaconda.i18n import _
from pyanaconda.iutil import is_unsupported_hw
from pyanaconda.constants import DEFAULT_LANG, DEFAULT_KEYBOARD

import logging
log = logging.getLogger("anaconda")

__all__ = ["WelcomeLanguageSpoke"]

class WelcomeLanguageSpoke(LangLocaleHandler, StandaloneSpoke):
    mainWidgetName = "welcomeWindow"
    uiFile = "spokes/welcome.glade"
    builderObjects = ["languageStore", "languageStoreFilter", "localeStore",
                      "welcomeWindow", "betaWarnDialog", "unsupportedHardwareDialog"]

    preForHub = SummaryHub
    priority = 0

    def __init__(self, *args, **kwargs):
        StandaloneSpoke.__init__(self, *args, **kwargs)
        LangLocaleHandler.__init__(self)
        self._xklwrapper = keyboard.XklWrapper.get_instance()
        self._origStrings = {}

    def apply(self):
        (store, itr) = self._localeSelection.get_selected()

        locale = store[itr][1]
        localization.setup_locale(locale, self.data.lang)

        # Skip timezone and keyboard default setting for kickstart installs.
        # The user may have provided these values via kickstart and if not, we
        # need to prompt for them.
        if flags.flags.automatedInstall:
            return

        geoloc_timezone = geoloc.get_timezone()
        loc_timezones = localization.get_locale_timezones(self.data.lang.lang)
        if geoloc_timezone:
            # (the geolocation module makes sure that the returned timezone is
            # either a valid timezone or None)
            self.data.timezone.timezone = geoloc_timezone
        elif loc_timezones and not self.data.timezone.timezone:
            # no data is provided by Geolocation, try to get timezone from the
            # current language
            self.data.timezone.timezone = loc_timezones[0]

        # setup Gtk direction (RTL/LTR) now that we have the language
        # configuration applied
        setup_gtk_direction()
        self._set_keyboard_defaults(self.data.lang.lang)

    def _set_keyboard_defaults(self, locale):
        """
        Set default keyboard settings (layouts, layout switching).

        :param locale: locale string (see localization.LANGCODE_RE)
        :type locale: str
        :return: list of preferred keyboard layouts
        :rtype: list of strings
        :raise InvalidLocaleSpec: if an invalid locale is given (see
                                  localization.LANGCODE_RE)

        """

        #remove all X layouts that are not valid X layouts (unsupported)
        #from the ksdata
        #XXX: could go somewhere else, but we need X running and we have
        #     XklWrapper instance here
        for layout in self.data.keyboard.x_layouts:
            if not self._xklwrapper.is_valid_layout(layout):
                self.data.keyboard.x_layouts.remove(layout)

        if self.data.keyboard.x_layouts:
            #do not add layouts if there are any specified in the kickstart
            return

        layouts = localization.get_locale_keyboards(locale)
        if layouts:
            # take the first locale (with highest rank) from the list and
            # store it normalized
            new_layouts = [keyboard.normalize_layout_variant(layouts[0])]
            if not langtable.supports_ascii(layouts[0]):
                # does not support typing ASCII chars, append the default layout
                new_layouts.append(DEFAULT_KEYBOARD)
        else:
            log.error("Failed to get layout for chosen locale '%s'", locale)
            new_layouts = [DEFAULT_KEYBOARD]

        self.data.keyboard.x_layouts = new_layouts
        if flags.can_touch_runtime_system("replace runtime X layouts", touch_live=True):
            self._xklwrapper.replace_layouts(new_layouts)

        if len(new_layouts) >= 2 and not self.data.keyboard.switch_options:
            #initialize layout switching if needed
            self.data.keyboard.switch_options = ["grp:alt_shift_toggle"]

            if flags.can_touch_runtime_system("init layout switching", touch_live=True):
                self._xklwrapper.set_switching_options(["grp:alt_shift_toggle"])
                # activate the language-default layout instead of the additional
                # one
                self._xklwrapper.activate_default_layout()

    @property
    def completed(self):
        if flags.flags.automatedInstall:
            return self.data.lang.lang and self.data.lang.lang != ""
        else:
            return False

    def _row_is_separator(self, model, itr, *args):
        return model[itr][3]

    def initialize(self):
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

        # We can use the territory from geolocation here
        # to preselect the translation, when it's available.
        territory = geoloc.get_territory_code(wait=True)

        # bootopts and kickstart have priority over geoip
        if self.data.lang.lang and self.data.lang.seen:
            locales = [self.data.lang.lang]
        else:
            locales = localization.get_territory_locales(territory) or [DEFAULT_LANG]

        # get the data models
        filter_store = self._languageStoreFilter
        store = filter_store.get_model()

        # get language codes for the locales
        langs = [localization.parse_langcode(locale)['language'] for locale in locales]

        # check which of the geolocated languages have translations
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
            localization.setup_locale(DEFAULT_LANG, self.data.lang)
            lang_itr, _locale_itr = self._select_locale(self.data.lang.lang)
            langs_with_translations[DEFAULT_LANG] = lang_itr
            locales = [DEFAULT_LANG]

        # go over all geolocated languages in reverse order
        # and move those we have translation for to the top of the
        # list, above the separator
        for lang in reversed(langs):
            itr = langs_with_translations.get(lang)
            if itr:
                store.move_after(itr, None)
            else:
                # we don't have translation for this language,
                # so dump all locales for it
                locales = [l for l in locales
                           if localization.parse_langcode(l)['language'] != lang]

        # And then we add a separator after the selected best language
        # and any additional languages (that have translations) from geoip
        newItr = store.insert(len(langs_with_translations))
        store.set(newItr, 0, "", 1, "", 2, "", 3, True)

        # setup the "best" locale
        localization.setup_locale(locales[0], self.data.lang)
        self._select_locale(self.data.lang.lang)

    def _retranslate_one(self, widgetName):
        widget = self.builder.get_object(widgetName)
        if not widget:
            return

        if not widget in self._origStrings:
            self._origStrings[widget] = widget.get_label()

        before = self._origStrings[widget]
        widget.set_label(_(before))

    def retranslate(self, lang):
        # Change the translations on labels and buttons that do not have
        # substitution text.
        for name in ["pickLanguageLabel", "betaWarnTitle", "betaWarnDesc",
                     "quitButton", "continueButton"]:
            self._retranslate_one(name)

        # The welcome label is special - it has text that needs to be
        # substituted.
        welcomeLabel = self.builder.get_object("welcomeLabel")

        if not welcomeLabel in self._origStrings:
            self._origStrings[welcomeLabel] = welcomeLabel.get_label()

        before = self._origStrings[welcomeLabel]
        # pylint: disable-msg=E1103
        xlated = _(before) % {"name" : productName.upper(), "version" : productVersion}
        welcomeLabel.set_label(xlated)

        # Retranslate the language (filtering) entry's placeholder text
        languageEntry = self.builder.get_object("languageEntry")
        if not languageEntry in self._origStrings:
            self._origStrings[languageEntry] = languageEntry.get_placeholder_text()

        languageEntry.set_placeholder_text(_(self._origStrings[languageEntry]))

        # And of course, don't forget the underlying window.
        self.window.set_property("distribution", distributionText().upper())
        self.window.retranslate(lang)

    def refresh(self):
        self._select_locale(self.data.lang.lang)
        self._languageEntry.set_text("")
        self._languageStoreFilter.refilter()

    def _add_language(self, store, native, english, lang):
        native_span = '<span lang="%s">%s</span>' % (lang, native)
        store.append([native_span, english, lang, False])

    def _add_locale(self, store, native, locale):
        native_span = '<span lang="%s">%s</span>' % (re.sub(r'\..*', '', locale), native)
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
            localization.setup_locale(lang)
            self.retranslate(lang)

    # Override the default in StandaloneSpoke so we can display the beta
    # warning dialog first.
    def _on_continue_clicked(self, cb):
        # Don't display the betanag dialog if this is the final release.
        if not isFinal:
            dlg = self.builder.get_object("betaWarnDialog")
            with enlightbox(self.window, dlg):
                rc = dlg.run()
                dlg.destroy()
            if rc == 0:
                sys.exit(0)

        if productName.startswith("Red Hat Enterprise Linux") and \
          is_unsupported_hw() and not self.data.unsupportedhardware.unsupported_hardware:
            dlg = self.builder.get_object("unsupportedHardwareDialog")
            with enlightbox(self.window, dlg):
                rc = dlg.run()
                dlg.destroy()
            if rc == 0:
                sys.exit(0)

        StandaloneSpoke._on_continue_clicked(self, cb)
