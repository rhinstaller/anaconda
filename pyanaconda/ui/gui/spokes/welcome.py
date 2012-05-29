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

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x

from gi.repository import AnacondaWidgets, Gtk
from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.spokes import StandaloneSpoke, NormalSpoke
from pyanaconda.ui.gui.utils import enlightbox
from pyanaconda.ui.gui.categories.localization import LocalizationCategory

from pyanaconda.localization import Language, LOCALE_PREFERENCES
from pyanaconda.product import productName, productVersion
from pyanaconda import xklavier
from pyanaconda import localization

__all__ = ["WelcomeLanguageSpoke", "LanguageSpoke"]

class LanguageMixIn(object):
    builderObjects = ["languageStore"]

    def __init__(self, labelName = "welcomeLabel",
                 viewName = "languageView", selectionName = "languageViewSelection"):
        self._xklwrapper = xklavier.XklWrapper.get_instance()
        self._origStrings = {}
        self._labelName = labelName
        self._viewName = viewName
        self._selectionName = selectionName

    def apply(self):
        selected = self.builder.get_object(self._selectionName)
        (store, itr) = selected.get_selected()

        lang = store[itr][2]
        self.language.select_translation(lang)
        self.data.lang.lang = lang

        #TODO: better use GeoIP data once it is available
        if self.language.territory and not self.data.timezone.timezone:
            lang_timezone = localization.get_preferred_timezone(self.language.territory)
            if lang_timezone:
                self.data.timezone.timezone = lang_timezone

        if self.data.keyboard.layouts_list:
            #do not add layouts if there are any specified in the kickstart
            return

        #get language name without any additional specifications
        #e.g. 'English (United States)' -> 'English'
        lang_name = store[itr][1]
        lang_name = lang_name.split()[0]

        #add one language-related and 'English (US)' layouts by default
        new_layouts = ['us']
        language_layout = self._xklwrapper.get_default_language_layout(lang_name)
        if language_layout:
            new_layouts.append(language_layout)

        for layout in new_layouts:
            if layout not in self.data.keyboard.layouts_list:
                self.data.keyboard.layouts_list.append(layout)
                self._xklwrapper.add_layout(layout)

    @property
    def completed(self):
        return self.data.lang.lang and self.data.lang.lang != ""

    def initialize(self):
        store = self.builder.get_object("languageStore")

        # TODO We can use the territory from geoip here
        # to preselect the translation, when it's available.
        # Until then, use None.
        territory = None
        self.language = Language(LOCALE_PREFERENCES, territory=territory)

        # fill the list with available translations
        for _code, trans in sorted(self.language.translations.items()):
            self._addLanguage(store, trans.display_name,
                              trans.english_name, trans.short_name)

        # select the preferred translation
        self._selectLanguage(store, self.language.preferred_translation.short_name)

    def retranslate(self):
        welcomeLabel = self.builder.get_object(self._labelName)

        if not welcomeLabel in self._origStrings:
            self._origStrings[welcomeLabel] = welcomeLabel.get_label()

        before = self._origStrings[welcomeLabel]
        xlated = _(before) % (productName.upper(), productVersion)
        welcomeLabel.set_label(xlated)

    def refresh(self, displayArea):
        store = self.builder.get_object("languageStore")
        self._selectLanguage(store, self.data.lang.lang)

        # Rip the label and language selection window
        # from where it is right now and add it to this
        # spoke.
        # This way we can share the dialog and code
        # between Welcome and Language spokes
        langList = self.builder.get_object("languageWindow")
        langList.get_parent().remove(langList)
        langLabel = self.builder.get_object("pickLanguageLabel")
        langLabel.get_parent().remove(langLabel)

        content = self.builder.get_object(displayArea)
        content.pack_start(child = langLabel, fill = True, expand = False, padding = 0)
        content.pack_start(child = langList, fill = True, expand = True, padding = 0)


    def _addLanguage(self, store, native, english, setting):
        store.append([native, english, setting])

    def _selectLanguage(self, store, language):
        itr = store.get_iter_first()
        while itr and store[itr][2] != language:
            itr = store.iter_next(itr)

        # If we were provided with an unsupported language, just use the default.
        if not itr:
            return

        treeview = self.builder.get_object(self._viewName)
        selection = treeview.get_selection()
        selection.select_iter(itr)
        path = store.get_path(itr)
        treeview.scroll_to_cell(path)

    # Signal handlers.
    def on_selection_changed(self, selection):
        (store, selected) = selection.get_selected_rows()
        if hasattr(self.window, "set_may_continue"):
            self.window.set_may_continue(len(selected) > 0)

        if selected:
            lang = store[selected[0]][2]
            self.language.set_install_lang(lang)
            self.language.set_system_lang(lang)
            self.retranslate()


class WelcomeLanguageSpoke(LanguageMixIn, StandaloneSpoke):
    mainWidgetName = "welcomeWindow"
    uiFile = "spokes/welcome.ui"
    builderObjects = LanguageMixIn.builderObjects + [mainWidgetName, "betaWarnDialog"]

    preForHub = SummaryHub
    priority = 0

    def __init__(self, *args):
        StandaloneSpoke.__init__(self, *args)
        LanguageMixIn.__init__(self)

    def retranslate(self):
        StandaloneSpoke.retranslate(self)
        LanguageMixIn.retranslate(self)

    def refresh(self):
        StandaloneSpoke.refresh(self)
        LanguageMixIn.refresh(self, "welcomeWindowContentBox")

    # Override the default in StandaloneSpoke so we can display the beta
    # warning dialog first.
    def _on_continue_clicked(self, cb):
        dlg = self.builder.get_object("betaWarnDialog")

        with enlightbox(self.window, dlg):
            rc = dlg.run()
            dlg.destroy()

        if rc == 0:
            sys.exit(0)
        else:
            StandaloneSpoke._on_continue_clicked(self, cb)


class LanguageSpoke(LanguageMixIn, NormalSpoke):
    mainWidgetName = "languageSpokeWindow"
    uiFile = "spokes/welcome.ui"
    builderObjects = LanguageMixIn.builderObjects + [mainWidgetName, WelcomeLanguageSpoke.mainWidgetName]

    category = LocalizationCategory

    icon = "accessories-character-map-symbolic"
    title = N_("LANGUAGE")

    def __init__(self, *args):
        NormalSpoke.__init__(self, *args)
        LanguageMixIn.__init__(self)

    def initialize(self):
        LanguageMixIn.initialize(self)
        NormalSpoke.initialize(self)

    def retranslate(self):
        NormalSpoke.retranslate(self)
        LanguageMixIn.retranslate(self)

    def refresh(self):
        NormalSpoke.refresh(self)
        LanguageMixIn.refresh(self, "languageSpokeWindowContentBox")

    @property
    def completed(self):
        # The language spoke is always completed, as it does not require you do
        # anything.  There's always a default selected.
        return True

    @property
    def status(self):
        selected = self.builder.get_object(self._selectionName)
        (store, itr) = selected.get_selected()

        return store[itr][0]
