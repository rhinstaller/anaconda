#
# langauge_gui.py: installtime language selection.
#
# Copyright (C) 2000, 2001, 2002  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import gobject
import gtk
import gui
from iw_gui import *
from constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

from gui import setupTreeViewFixupIdleHandler, StayOnScreen

class LanguageWindow (InstallWindow):

    windowTitle = N_("Language Selection")

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

    def getNext (self):
        anaconda = self.ics.getICW().anaconda

        (model, iter) = self.listView.get_selection().get_selected()
        if not iter:
            raise StayOnScreen

	choice = self.listStore.get_value(iter, 1)
        self.lang = self.instLang.getLangByName(choice)

        if self.lang in self.instLang.getCurrentLangSearchList():
            return None

        self.instLang.instLang = self.lang
        self.instLang.systemLang = self.lang
        anaconda.timezone.setTimezoneInfo(anaconda.instLanguage.getDefaultTimeZone(anaconda.rootPath))
	self.ics.getICW().setLanguage()

        return None

    def listScroll(self, widget, *args):
        # recenter the list
        (model, iter) = self.listView.get_selection().get_selected()
        if iter is None:
            return

        path = self.listStore.get_path(iter)
        col = self.listView.get_column(0)
        self.listView.scroll_to_cell(path, col, True, 0.5, 0.5)
	self.listView.set_cursor(path, col, False)

    # LanguageWindow tag="lang"
    def getScreen (self, anaconda):
        self.running = 0
        mainBox = gtk.VBox (False, 10)

        hbox = gtk.HBox(False, 5)
        pix = gui.readImageFromFile ("config-language.png")
        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            hbox.pack_start (a, False)

        label = gtk.Label (_("What language would you like to use during the "
                         "installation process?"))
        label.set_line_wrap (True)
        label.set_size_request(350, -1)
        hbox.pack_start(label, False)

	self.instLang = anaconda.instLanguage

        self.listStore = gtk.ListStore(gobject.TYPE_STRING,
                                       gobject.TYPE_STRING,
                                       gobject.TYPE_STRING)

        for locale in self.instLang.available():
            iter = self.listStore.append()
            nick = self.instLang.getLangByName(locale)
            lang = '%s (<span lang="%s">%s</span>)' % (
                _(locale), "%s" % (nick.split('.')[0],),
                self.instLang.getNativeLangName(locale))
            self.listStore.set_value(iter, 0, lang)
            self.listStore.set_value(iter, 1, locale)
            self.listStore.set_value(iter, 2, _(locale))

        self.listStore.set_sort_column_id(2, gtk.SORT_ASCENDING)

        self.listView = gtk.TreeView(self.listStore)
        col = gtk.TreeViewColumn(None, gtk.CellRendererText(), markup=0)
        self.listView.append_column(col)
        self.listView.set_property("headers-visible", False)

        current = self.instLang.getLangName(self.instLang.instLang)
        iter = self.listStore.get_iter_first()
        while iter:
            if self.listStore.get_value(iter, 1) == current:
                selection = self.listView.get_selection()
                selection.unselect_all()
                selection.select_iter(iter)
                break
            iter = self.listStore.iter_next(iter)
        self.listView.connect("size-allocate", self.listScroll)

        sw = gtk.ScrolledWindow ()
        sw.set_border_width (5)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.add (self.listView)

	setupTreeViewFixupIdleHandler(self.listView, self.listStore)

        mainBox.pack_start (hbox, False, False, 10)
        mainBox.pack_start (sw, True, True)

        self.running = 1

        return mainBox
