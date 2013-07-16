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

from gi.repository import Gtk, Pango
from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.spokes import StandaloneSpoke
from pyanaconda.ui.gui.utils import enlightbox, set_treeview_selection

from pyanaconda import localization
from pyanaconda.product import distributionText, isFinal, productName, productVersion
from pyanaconda import keyboard
from pyanaconda import flags
from pyanaconda import geoloc
from pyanaconda.i18n import _
from pyanaconda.iutil import is_unsupported_hw
from pyanaconda.constants import DEFAULT_LANG

import logging
log = logging.getLogger("anaconda")

__all__ = ["WelcomeLanguageSpoke"]

class WelcomeLanguageSpoke(StandaloneSpoke):
    mainWidgetName = "welcomeWindow"
    uiFile = "spokes/welcome.glade"
    builderObjects = ["languageStore", "languageStoreFilter", "localeStore",
                      "welcomeWindow", "betaWarnDialog", "unsupportedHardwareDialog"]

    preForHub = SummaryHub
    priority = 0

    def __init__(self, *args, **kwargs):
        StandaloneSpoke.__init__(self, *args, **kwargs)
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
            # take the first locale (with highest rank) from the list
            new_layouts = [layouts[0]]
            if not langtable.supports_ascii(layouts[0]):
                # does not support typing ASCII chars, append the 'us' layout
                new_layouts.append("us")
        else:
            log.error("Failed to get layout for chosen locale '%s'" % locale)
            new_layouts = ["us"]

        self.data.keyboard.x_layouts = new_layouts
        if flags.can_touch_runtime_system("replace runtime X layouts"):
            self._xklwrapper.replace_layouts(new_layouts)

        if len(new_layouts) >= 2 and not self.data.keyboard.switch_options:
            #initialize layout switching if needed
            self.data.keyboard.switch_options = ["grp:alt_shift_toggle"]

            if flags.can_touch_runtime_system("init layout switching"):
                self._xklwrapper.set_switching_options(["grp:alt_shift_toggle"])
                # activate the first (language-default) layout instead of the
                # 'us' one
                self._xklwrapper.activate_default_layout()

    @property
    def completed(self):
        if flags.flags.automatedInstall:
            return self.data.lang.lang and self.data.lang.lang != ""
        else:
            return False

    def _row_is_separator(self, model, itr, *args):
        return model[itr][3]

    def _render_lang_selected(self, column, renderer, model, itr, user_data=None):
        (lang_store, sel_itr) = self._langSelection.get_selected()

        if sel_itr and lang_store[sel_itr][2] == model[itr][2]:
            renderer.set_property("pixbuf", self._right_arrow.get_pixbuf())
        else:
            renderer.set_property("pixbuf", None)

    def initialize(self):
        self._languageStore = self.builder.get_object("languageStore")
        self._languageStoreFilter = self.builder.get_object("languageStoreFilter")
        self._languageEntry = self.builder.get_object("languageEntry")
        self._langSelection = self.builder.get_object("languageViewSelection")
        self._langSelectedRenderer = self.builder.get_object("langSelectedRenderer")
        self._langSelectedColumn = self.builder.get_object("langSelectedColumn");
        self._langView = self.builder.get_object("languageView")
        self._localeView = self.builder.get_object("localeView")
        self._localeStore = self.builder.get_object("localeStore")
        self._localeSelection = self.builder.get_object("localeViewSelection")

        # We need to tell the view whether something is a separator or not.
        self._langView.set_row_separator_func(self._row_is_separator, None)

        # Render a right arrow for the chosen language
        self._right_arrow = Gtk.Image.new_from_file("/usr/share/anaconda/pixmaps/right-arrow-icon.png")
        self._langSelectedColumn.set_cell_data_func(self._langSelectedRenderer,
                                                    self._render_lang_selected)

        # We can use the territory from geolocation here
        # to preselect the translation, when it's available.
        territory = geoloc.get_territory_code()

        locales = localization.get_territory_locales(territory)
        if locales and not (self.data.lang.lang and self.data.lang.seen):
            # get something from the GeoIP lookup and not set in/on the
            # kickstart/command line
            localization.setup_locale(locales[0], self.data.lang)

        # fill the list with available translations
        for lang in localization.get_available_translations():
            self._addLanguage(self._languageStore,
                              localization.get_native_name(lang),
                              localization.get_english_name(lang), lang)

        # Move the default language (whatever was provided on the command line,
        # or by kickstart, or by geoip, or English if nothing else) to the top
        # of the list and select it by default.  People find it confusing to be
        # dropped into the middle of a scrollable list.
        lang_itr, locale_itr = self._select_locale(self.data.lang.lang)

        if not lang_itr or not locale_itr:
            log.error("Failed to select language %s, using the default %s",
                      self.data.lang.lang, DEFAULT_LANG)
            lang_itr, locale_itr = self._select_locale(DEFAULT_LANG)
            self.data.lang.lang = DEFAULT_LANG

        filter_store = self._languageStoreFilter
        # filtered store and lang_itr is an iter on it.  We need to
        # convert to an iter on the underlying store.
        itr = filter_store.convert_iter_to_child_iter(lang_itr)
        store = filter_store.get_model()
        store.move_after(itr, None)

        # And then we add a separator after the default chosen language.
        newItr = store.insert(1)
        store.set(newItr, 0, "", 1, "", 2, "", 3, True)

        self._languageStoreFilter.set_visible_func(self._matchesEntry, None)

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
        xlated = _(before) % {"name" : productName.upper(), "version" : productVersion}
        welcomeLabel.set_label(xlated)

        # And of course, don't forget the underlying window.
        self.window.set_property("distribution", distributionText().upper())
        self.window.retranslate(lang)

    def refresh(self):
        self._select_locale(self.data.lang.lang)
        self._languageEntry.set_text("")
        self._languageStoreFilter.refilter()

    def _addLanguage(self, store, native, english, lang):
        native_span = '<span lang="%s">%s</span>' % (lang, native)
        store.append([native_span, english, lang, False])

    def _addLocale(self, store, native, locale):
        native_span = '<span lang="%s">%s</span>' % (re.sub(r'\..*', '', locale), native)
        store.append([native_span, locale])

    def _matchesEntry(self, model, itr, *args):
        # Need to strip out the pango markup before attempting to match.
        # Otherwise, starting to type "span" for "spanish" will match everything
        # due to the enclosing span tag.
        (success, attrs, native, accel) = Pango.parse_markup(model[itr][0], -1, "_")
        english = model[itr][1]
        entry = self._languageEntry.get_text().strip()

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
            self._addLocale(self._localeStore,
                            localization.get_native_name(locale),
                            locale)

        # select the first locale (with the highest rank)
        set_treeview_selection(self._localeView, locales[0], col=1)

    # Signal handlers.
    def on_lang_selection_changed(self, selection):
        (store, selected) = selection.get_selected_rows()

        if selected:
            lang = store[selected[0]][2]
            self._refresh_locale_store(lang)
        else:
            if hasattr(self.window, "set_may_continue"):
                self.window.set_may_continue(False)
            self._localeStore.clear()

    def on_locale_selection_changed(self, selection):
        (store, selected) = selection.get_selected_rows()
        if hasattr(self.window, "set_may_continue"):
            self.window.set_may_continue(len(selected) > 0)

        if selected:
            lang = store[selected[0]][1]
            localization.setup_locale(lang)
            self.retranslate(lang)

    def on_clear_icon_clicked(self, entry, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            entry.set_text("")

    def on_entry_changed(self, *args):
        self._languageStoreFilter.refilter()

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
