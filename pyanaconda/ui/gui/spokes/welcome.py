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
#

import sys
import re

# pylint: disable-msg=E0611
from gi.repository import AnacondaWidgets, Gtk, Pango
from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.spokes import StandaloneSpoke
from pyanaconda.ui.gui.utils import enlightbox

from pyanaconda.localization import Language, LOCALE_PREFERENCES, expand_langs
from pyanaconda.product import distributionText, isFinal, productName, productVersion
from pyanaconda import keyboard
from pyanaconda import timezone
from pyanaconda import flags
from pyanaconda import geoloc
from pyanaconda.i18n import _, N_

import logging
log = logging.getLogger("anaconda")

__all__ = ["WelcomeLanguageSpoke"]

class WelcomeLanguageSpoke(StandaloneSpoke):
    mainWidgetName = "welcomeWindow"
    uiFile = "spokes/welcome.glade"
    builderObjects = ["languageStore", "languageStoreFilter", "welcomeWindow", "betaWarnDialog"]

    preForHub = SummaryHub
    priority = 0

    def __init__(self, *args, **kwargs):
        StandaloneSpoke.__init__(self, *args, **kwargs)
        self._xklwrapper = keyboard.XklWrapper.get_instance()
        self._origStrings = {}

    def apply(self):
        selected = self.builder.get_object("languageViewSelection")
        (store, itr) = selected.get_selected()

        lang = store[itr][2]
        self.language.select_translation(lang)
        self.data.lang.lang = lang

        # Skip timezone and keyboard default setting for kickstart installs.
        # The user may have provided these values via kickstart and if not, we
        # need to prompt for them.
        if flags.flags.automatedInstall:
            return

        lang_timezone = None
        # check if the geolocation lookup returned a time zone
        # (the geolocation module makes sure that the returned timezone is
        # either a valid timezone or None)
        geoloc_timezone = geoloc.get_timezone()
        if geoloc_timezone:
            lang_timezone = geoloc_timezone
        # if no data is provided by Geolocation,
        # try to get timezone from the current language
        elif self.language.territory and not self.data.timezone.timezone:
            lang_timezone = timezone.get_preferred_timezone(self.language.territory)

        if lang_timezone:
            self.data.timezone.timezone = lang_timezone

        lang_country = self.language.preferred_locale.territory
        self._set_keyboard_defaults(store[itr][1], lang_country)

    def _set_keyboard_defaults(self, lang_name, country):
        """
        Set default keyboard settings (layouts, layout switching).

        :param lang_name: name of the selected language (e.g. "Czech")

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

        #get language name without any additional specifications
        #e.g. 'English (United States)' -> 'English'
        lang_name = lang_name.split()[0]

        default_layout = self._xklwrapper.get_default_lang_country_layout(lang_name,
                                                                          country)
        if default_layout:
            new_layouts = [default_layout]
        else:
            new_layouts = ["us"]

        checkbutton = self.builder.get_object("setKeyboardCheckButton")
        if not checkbutton.get_active() and "us" not in new_layouts:
            #user doesn't want only the language-default layout, prepend
            #'English (US)' layout
            new_layouts.insert(0, "us")

        self.data.keyboard.x_layouts = new_layouts
        if flags.can_touch_runtime_system("replace runtime X layouts"):
            self._xklwrapper.replace_layouts(new_layouts)

        if len(new_layouts) >= 2 and not self.data.keyboard.switch_options:
            #initialize layout switching if needed
            self.data.keyboard.switch_options = ["grp:alt_shift_toggle"]

            if flags.can_touch_runtime_system("init layout switching"):
                self._xklwrapper.set_switching_options(["grp:alt_shift_toggle"])

    @property
    def completed(self):
        if flags.flags.automatedInstall:
            return self.data.lang.lang and self.data.lang.lang != ""
        else:
            return False

    def _row_is_separator(self, model, itr, *args):
        return model[itr][3]

    def initialize(self):
        store = self.builder.get_object("languageStore")
        self._languageStoreFilter = self.builder.get_object("languageStoreFilter")
        self._languageEntry = self.builder.get_object("languageEntry")
        self._selection = self.builder.get_object("languageViewSelection")
        self._view = self.builder.get_object("languageView")

        # We need to tell the view whether something is a separator or not.
        self._view.set_row_separator_func(self._row_is_separator, None)

        # We can use the territory from geolocation here
        # to preselect the translation, when it's available.
        territory = geoloc.get_territory_code()
        self.language = Language(LOCALE_PREFERENCES, territory=territory)

        # check if there is one and only one locale for the territory
        if len(self.language.preferred_locales) != 1:
            log.info("Didn't get a single locale from Geolocation,"
                        " falling back to default locale.")
            self.language = Language(LOCALE_PREFERENCES, territory=None)
            # Explanation:
            # Some territories have multiple locales,
            # for example, the Switzerland has:
            # de_CH, it_CH and fr_CH
            # As there is no clear order of preference for them,
            # it is safer to just fall back to the default locale

        # fill the list with available translations
        for _code, trans in sorted(self.language.translations.items()):
            self._addLanguage(store, trans.display_name,
                              trans.english_name, trans.short_name)

        # Move the default language (whatever was provided on the command line,
        # or by kickstart, or by geoip, or English if nothing else) to the top
        # of the list and select it by default.  People find it confusing to be
        # dropped into the middle of a scrollable list.
        (store, itr) = self._selection.get_selected()
        if not itr:
            # check if a language was set by kickstart
            # NOTE: seen means the language was "seen" in
            # kickstart or boot option, so it overrides
            # the language detected by geolocation
            if self.data.lang.lang and self.data.lang.seen:
                lang = self.data.lang.lang
            else:
                lang = self.language.preferred_translation.short_name

            itr = self._selectLanguage(lang)

        # store is the filtered store, and itr is an iter on it.  We need to
        # convert to an iter on the underlying store.
        itr = store.convert_iter_to_child_iter(itr)
        store = store.get_model()
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
                     "quitButton", "continueButton", "setKeyboardCheckButton"]:
            self._retranslate_one(name)

        # The welcome label is special - it has text that needs to be
        # substituted.
        welcomeLabel = self.builder.get_object("welcomeLabel")

        if not welcomeLabel in self._origStrings:
            self._origStrings[welcomeLabel] = welcomeLabel.get_label()

        before = self._origStrings[welcomeLabel]
        xlated = _(before) % (productName.upper(), productVersion)
        welcomeLabel.set_label(xlated)

        # And of course, don't forget the underlying window.
        self.window.set_property("distribution", distributionText().upper())
        self.window.retranslate(lang)

    def refresh(self):
        self._selectLanguage(self.data.lang.lang)

        # Rip the label and language selection window
        # from where it is right now and add it to this
        # spoke.
        # This way we can share the dialog and code
        # between Welcome and Language spokes
        langLabel = self.builder.get_object("pickLanguageLabel")
        langLabel.get_parent().remove(langLabel)
        langAlign = self.builder.get_object("languageAlignment")
        langAlign.get_parent().remove(langAlign)

        content = self.builder.get_object("welcomeWindowContentBox")
        content.pack_start(child = langLabel, fill = True, expand = False, padding = 0)
        content.pack_start(child = langAlign, fill = True, expand = True, padding = 0)

        self._languageEntry.set_text("")
        self._languageStoreFilter.refilter()

    def _addLanguage(self, store, native, english, setting):
        lang = '<span lang="%s">%s</span>' % (re.sub('\..*', '', setting), native)
        store.append([lang, english, setting, False])

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

    def _selectLanguage(self, language):
        treeview = self.builder.get_object("languageView")
        selection = treeview.get_selection()
        store = treeview.get_model()
        itr = store.get_iter_first()
        # store[itr][3] is True if this row is a separator in the view, so we
        # want to skip those.
        while itr and not store[itr][3] and language not in expand_langs(store[itr][2]):
            itr = store.iter_next(itr)

        # If we were provided with an unsupported language, just use the default.
        if not itr:
            return

        selection.select_iter(itr)
        path = store.get_path(itr)
        # row_align=0.5 tells GTK to move the cell to the middle of the
        # treeview viewport (0.0 should align it with the top, 1.0 with bottom)
        # If the cell is the uppermost one, it should align it with the top
        # of the viewport.
        #
        # Unfortunately, this does not work as expected due to a bug in GTK.
        # So currently if the cell is the upper most one, it will sort of
        # align it with the top of the viewport, leaving about 30% of
        # it hidden. If the target cell is not the upper most one,
        # it seems to just scroll the treeview a bit, leaving the
        # target cell well out of the viewport.
        #
        # In short, once that GTK bug is fixed, row_align=0.5 should work
        # correctly for showing both upper most cells and all other cells
        # in the tree view.
        treeview.scroll_to_cell(path, use_align=True, row_align=0.5)

        return itr

    # Signal handlers.
    def on_selection_changed(self, selection):
        (store, selected) = selection.get_selected_rows()
        if hasattr(self.window, "set_may_continue"):
            self.window.set_may_continue(len(selected) > 0)

        if selected:
            lang = store[selected[0]][2]
            self.language.set_install_lang(lang)
            self.language.set_system_lang(lang)
            self.retranslate(lang)

    def on_clear_icon_clicked(self, entry, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            entry.set_text(entry.get_placeholder_text())

    def on_entry_changed(self, *args):
        self._languageStoreFilter.refilter()

    # Override the default in StandaloneSpoke so we can display the beta
    # warning dialog first.
    def _on_continue_clicked(self, cb):
        # Don't display the betanag dialog if this is the final release.
        if isFinal:
            StandaloneSpoke._on_continue_clicked(self, cb)
            return

        dlg = self.builder.get_object("betaWarnDialog")

        with enlightbox(self.window, dlg):
            rc = dlg.run()
            dlg.destroy()

        if rc == 0:
            sys.exit(0)
        else:
            StandaloneSpoke._on_continue_clicked(self, cb)
