#
# keyboard_gui.py: keyboard configuration gui dialog
#
# Copyright 2000-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import isys
import iutil
import string
import xkb
import gobject
import gtk
from iw_gui import *
from kbd import Keyboard
from flags import flags

from rhpl.log import log
from rhpl.translate import _, N_

class KeyboardWindow (InstallWindow):
    windowTitle = N_("Keyboard Configuration")
    htmlTag = "kybd"

    def __init__(self, ics):
	InstallWindow.__init__(self, ics)

	self.kb = xkb.XKB()
	self.rules = self.kb.getRules()
	rules = self.kb.getRulesBase()
	self.rulesbase = rules[string.rfind(rules, "/")+1:]

    def getNext (self):
        if self.flags.setupFilesystems:
            self.kb.setRule(self.model, self.layout, self.variant,
                             "complete")

	if (self.x != (None, None)):
            self.x.setKeyboard(self.rulesbase, self.model,
                            self.layout, self.variant, "")

        self.kbd.setfromx(self.model, self.layout, self.variant)
        self.kbd.beenset = 1

        try:
            isys.loadKeymap(self.kbd.get())
        except:
            log("failed to load keymap")

        return None

    def select_row(self, *args):        
        model, iter = self.modelView.get_selection().get_selected()
        self.model = model.get_value(iter, 0)

        model, iter = self.layoutView.get_selection().get_selected()
        self.layout = model.get_value(iter, 0)

        model, iter = self.variantView.get_selection().get_selected()
        self.variant = model.get_value(iter, 0)        

    def setMap(self, data):
        if self.flags.setupFilesystems:
            self.kb.setRule(self.model, self.layout, self.variant, "complete")

    # KeyboardWindow tag="kybd"
    def getScreen(self, instLang, kbd, x):
	self.flags = flags
	self.kbd = kbd
        self.x = x

	if (x == (None, None)):
            rules, model, layout, variant, options = Keyboard().getXKB()
        else:
            rules, model, layout, variant, options = x.getKeyboard()
        self.model = model
        self.layout = layout
        self.variant = variant

        if not self.kbd.beenset:
            default = instLang.getDefaultKeyboard()
            
            if Keyboard.console2x.has_key(default):
                self.model = Keyboard.console2x[default][0]
                self.layout = Keyboard.console2x[default][1]
                if flags.setupFilesystems:
                    self.kb.setRule(self.model, self.layout, self.variant, 
				     "complete")
		elif kbd.type == "Sun":
		    self.model = kbd.model
		    self.layout = kbd.layout


	box = gtk.VBox(gtk.FALSE, 5)
        hbox = gtk.HBox(gtk.FALSE, 5)
        pix = self.ics.readPixmap("gnome-keyboard.png")
        if pix:
            a = gtk.Alignment(0.0, 0.0, 0.0, 0.0)
            a.add(pix)
            hbox.pack_start(a, gtk.FALSE)

        label = gtk.Label(_("Which model keyboard is attached to the computer?"))
        label.set_line_wrap(gtk.TRUE)
        label.set_size_request(350, -1)
        hbox.pack_start(label, gtk.FALSE)
        box.pack_start(hbox, gtk.FALSE)

	box.pack_start(gtk.Label(_("Model")), gtk.FALSE)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)

        self.modelStore = gtk.ListStore(str, str)

        for key, model in self.rules[0].items():
            iter = self.modelStore.append()
            self.modelStore.set_value(iter, 0, key)
            self.modelStore.set_value(iter, 1, model)

        self.modelStore.set_sort_column_id(0, gtk.SORT_ASCENDING)

        self.modelView = gtk.TreeView(self.modelStore)
        col = gtk.TreeViewColumn(None, gtk.CellRendererText(), text=1)
        self.modelView.append_column(col)
        self.modelView.set_property("headers-visible", gtk.FALSE)

        iter = self.modelStore.get_iter_root()
        next = 1        
        while next:
            if self.modelStore.get_value(iter, 0) == self.model:
                path = self.modelStore.get_path(iter)
                self.modelView.set_cursor(path, col, gtk.FALSE)
                self.modelView.scroll_to_cell(path, col, gtk.TRUE, 0.5, 0.5)
                break
            next = self.modelStore.iter_next(iter)

        sw.add(self.modelView)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        box.pack_start(sw, gtk.TRUE)

	box.pack_start(gtk.Label(_("Layout")), gtk.FALSE)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)

        self.layoutStore = gtk.ListStore(str, str)

        for key, layout in self.rules[1].items():
            iter = self.layoutStore.append()
            self.layoutStore.set_value(iter, 0, key)
            self.layoutStore.set_value(iter, 1, layout)

        self.layoutStore.set_sort_column_id(0, gtk.SORT_ASCENDING)

        self.layoutView = gtk.TreeView(self.layoutStore)
        col = gtk.TreeViewColumn(None, gtk.CellRendererText(), text=1)
        self.layoutView.append_column(col)
        self.layoutView.set_property("headers-visible", gtk.FALSE)

        iter = self.layoutStore.get_iter_root()
        next = 1

        while next:
            if self.layoutStore.get_value(iter, 0) == self.layout:

                path = self.layoutStore.get_path(iter)
                self.layoutView.set_cursor(path, col, gtk.FALSE)
                self.layoutView.scroll_to_cell(path, col, gtk.TRUE, 0.5, 0.5)
                break
            next = self.layoutStore.iter_next(iter)
             

        sw.add(self.layoutView)
        box.pack_start(sw, gtk.TRUE)

	box.pack_start(gtk.Label(_("Dead Keys")), gtk.FALSE)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)

        self.variantStore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)

        iter = self.variantStore.append()
        self.variantStore.set_value(iter, 0, "basic")
        self.variantStore.set_value(iter, 1, (_("Enable dead keys")))
        iter = self.variantStore.append()
        self.variantStore.set_value(iter, 0, "nodeadkeys")
        self.variantStore.set_value(iter, 1, (_("Disable dead keys")))

        self.variantView = gtk.TreeView(self.variantStore)
        col = gtk.TreeViewColumn(None, gtk.CellRendererText(), text=1)
        self.variantView.append_column(col)
        self.variantView.set_property("headers-visible", gtk.FALSE)

        iter = self.variantStore.get_iter_root()
        next = 1

        while next:
            if self.variant == "nodeadkeys":
                path = self.variantStore.get_path(iter)
                self.variantView.set_cursor(path, col, gtk.FALSE)
                self.variantView.scroll_to_cell(path, col, gtk.FALSE, 0.5, 0.5)
                break
            else:
                path = self.variantStore.get_path(iter)
                self.variantView.set_cursor(path, col, gtk.FALSE)
                self.variantView.scroll_to_cell(path, col, gtk.FALSE, 0.5, 0.5)
            next = self.variantStore.iter_next(iter)

        selection = self.modelView.get_selection()
        selection.connect("changed", self.select_row)
        
        selection = self.layoutView.get_selection()
        selection.connect("changed", self.select_row)

        selection = self.variantView.get_selection()
        selection.connect("changed", self.select_row)
        sw.add(self.variantView)
 	box.pack_start(sw, gtk.FALSE)

        label = gtk.Label(_("Test your selection here:"))
        label.set_alignment(0.0, 0.5)
        box.pack_start(label, gtk.FALSE)

        entry = gtk.Entry()
        box.pack_start(entry, gtk.FALSE)

        entry.connect("grab-focus", self.setMap)

        box.set_border_width(5)
        return box
