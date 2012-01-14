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

from gi.repository import AnacondaWidgets, Gtk
from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.spokes import StandaloneSpoke

from pyanaconda.localization import Language, LOCALE_PREFERENCES

__all__ = ["WelcomeLanguageSpoke"]

class WelcomeLanguageSpoke(StandaloneSpoke):
    mainWidgetName = "welcomeWindow"
    uiFile = "spokes/welcome.ui"

    preForHub = SummaryHub
    priority = 0

    def apply(self):
        selected = self.builder.get_object("languageViewSelection")
        (store, itr) = selected.get_selected()

        lang = store[itr][2]
        self.language.select_translation(lang)

        self.data.lang.lang = lang

    def populate(self):
        StandaloneSpoke.populate(self)

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

    def setup(self):
        StandaloneSpoke.setup(self)

    def _addLanguage(self, store, native, english, setting):
        store.append([native, english, setting])

    def _selectLanguage(self, store, language):
        itr = store.get_iter_first()
        while itr and store[itr][2] != language:
            itr = store.iter_next(itr)

        treeview = self.builder.get_object("languageView")
        selection = treeview.get_selection()
        selection.select_iter(itr)
        path = store.get_path(itr)
        treeview.scroll_to_cell(path)

    # Signal handlers.
    def on_selection_changed(self, selection):
        (store, selected) = selection.get_selected_rows()
        self.window.set_may_continue(len(selected) > 0)

        if selected:
            lang = store[selected[0]][2]
            self.language.set_install_lang(lang)
            self.language.set_system_lang(lang)
            self.retranslate()

    # Override the default in StandaloneSpoke so we can display the beta
    # warning dialog first.
    def _on_continue_clicked(self, cb):
        dlg = self.builder.get_object("betaWarnDialog")

        lightbox = AnacondaWidgets.lb_show_over(self.window)
        dlg.set_transient_for(lightbox)
        rc = dlg.run()
        dlg.destroy()
        lightbox.destroy()

        if rc == 0:
            sys.exit(0)
        else:
            StandaloneSpoke._on_continue_clicked(self, cb)
