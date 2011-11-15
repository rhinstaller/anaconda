# Welcome spoke classes
#
# Copyright (C) 2011  Red Hat, Inc.
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

from gi.repository import Gtk
from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.spokes import StandaloneSpoke

__all__ = ["WelcomeLanguageSpoke"]

class WelcomeLanguageSpoke(StandaloneSpoke):
    mainWidgetName = "welcomeWindow"
    uiFile = "spokes/welcome.ui"

    preForHub = SummaryHub
    priority = 0

    def apply(self):
        selected = self.builder.get_object("languageViewSelection")
        (store, itr) = selected.get_selected()

        self.data.lang.lang = store[itr][2]

    def populate(self):
        StandaloneSpoke.populate(self)

        # I shouldn't have to do this outside of GtkBuilder, but see:
        # https://bugzilla.gnome.org/show_bug.cgi?id=614150
        completion = self.builder.get_object("languageEntryCompletion")
        completion.set_text_column(1)

        store = self.builder.get_object("languageStore")
        self._addLanguage(store, "English", "English", "en_US")
        self._addLanguage(store, "Language A", "Language A", "C")
        self._addLanguage(store, "Language B", "Language B", "C")
        self._addLanguage(store, "Language C", "Language C", "C")
        self._addLanguage(store, "Language D", "Language D", "C")
        self._addLanguage(store, "Language E", "Language E", "C")
        self._addLanguage(store, "Language F", "Language F", "C")
        self._addLanguage(store, "Language G", "Language G", "C")
        self._addLanguage(store, "Language H", "Language H", "C")
        self._addLanguage(store, "Language I", "Language I", "C")
        self._addLanguage(store, "Language J", "Language J", "C")
        self._addLanguage(store, "Language K", "Language K", "C")

    def setup(self):
        StandaloneSpoke.setup(self)
        self.window.set_may_continue(False)

    def _addLanguage(self, store, native, english, setting):
        store.append([native, english, setting])

    # Signal handlers.
    def clearLanguageEntry(self, entry, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            entry.set_text("")

    def on_selection_changed(self, selection):
        (store, selected) = selection.get_selected_rows()
        self.window.set_may_continue(len(selected) > 0)

    # Override the default in StandaloneSpoke so we can display the beta
    # warning dialog first.
    def _on_continue_clicked(self, cb):
        dlg = self.builder.get_object("betaWarnDialog")
        rc = dlg.run()
        dlg.destroy()

        if rc == 0:
            sys.exit(0)
        else:
            StandaloneSpoke._on_continue_clicked(self, cb)
