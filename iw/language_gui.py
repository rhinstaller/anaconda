#
# langauge_gui.py: installtime language selection.
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gobject
import gtk
from iw_gui import *
from translate import _, N_

class LanguageWindow (InstallWindow):

    windowTitle = N_("Language Selection")
    htmlTag = "lang"

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

    def getNext (self):
        rc = self.listView.get_selection().get_selected()
        if rc:
            model, iter = rc
            self.lang = self.listStore.get_value(iter, 1)

	self.instLang.setRuntimeLanguage(self.lang)
	self.ics.getICW().setLanguage (self.instLang.getLangNick(self.lang))

        return None

    def listScroll(self, widget, *args):
        # recenter the list
        rc = self.listView.get_selection().get_selected()
        if rc is None:
            return
        model, iter = rc
        
        path = self.listStore.get_path(iter)
        col = self.listView.get_column(0)
        self.listView.scroll_to_cell(path, col, gtk.TRUE, 0.5, 0.5)

    # LanguageWindow tag="lang"
    def getScreen (self, intf, instLang):
        self.running = 0
        mainBox = gtk.VBox (gtk.FALSE, 10)

        hbox = gtk.HBox(gtk.FALSE, 5)
        pix = self.ics.readPixmap ("gnome-globe.png")
        if pix:
            a = gtk.Alignment ()
            a.add (pix)
            hbox.pack_start (a, gtk.FALSE)
            
        label = gtk.Label (_("What language would you like to use during the "
                         "installation process?"))
        label.set_line_wrap (gtk.TRUE)
        label.set_usize(350, -1)
        hbox.pack_start(label, gtk.FALSE)
        
	self.instLang = instLang

        self.listStore = gtk.ListStore(gobject.TYPE_STRING,
                                       gobject.TYPE_STRING)

        for locale in instLang.available():
            iter = self.listStore.append()
            self.listStore.set_value(iter, 0, _(locale))
            self.listStore.set_value(iter, 1, locale)

        self.listStore.set_sort_column_id(0, gtk.SORT_ASCENDING)

        self.listView = gtk.TreeView(self.listStore)
        col = gtk.TreeViewColumn(None, gtk.CellRendererText(), text=0)
        self.listView.append_column(col)
        self.listView.set_property("headers-visible", gtk.FALSE)

        current = instLang.getCurrent()
        iter = self.listStore.get_iter_root()
        next = 1
        while next:
            if self.listStore.get_value(iter, 1) == current:
                selection = self.listView.get_selection()
                selection.unselect_all()
                selection.select_iter(iter)
                break
            next = self.listStore.iter_next(iter)
        self.listView.connect("size-allocate", self.listScroll)

        sw = gtk.ScrolledWindow ()
        sw.set_border_width (5)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.set_policy (gtk.POLICY_NEVER, gtk.POLICY_NEVER)
        sw.add (self.listView)
        
        mainBox.pack_start (hbox, gtk.FALSE, gtk.FALSE, 10)
        mainBox.pack_start (sw, gtk.TRUE, gtk.TRUE)

        self.running = 1
        
        return mainBox
