#
# keyboard_gui.py: keyboard configuration gui dialog
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

import isys
import iutil
import string
import xkb
import gtk
from iw_gui import *
from kbd import Keyboard
from log import log
from flags import flags
from translate import _, N_

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

    def select_row(self, clist, row, col, event):
	self.model = self.modelList.get_row_data(self.modelList.selection[0])
	self.layout = self.layoutList.get_row_data(self.layoutList.selection[0])
	self.variant = self.variantList.get_row_data(self.variantList.selection[0])

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
        label.set_usize(350, -1)
        hbox.pack_start(label, gtk.FALSE)
        box.pack_start(hbox, gtk.FALSE)

	def moveto(widget, *args):
            widget.moveto(widget.selection[0], 0, 0.5, 0.5)

	box.pack_start(gtk.Label(_("Model")), gtk.FALSE)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.modelList = gtk.CList(1)
	self.modelList.freeze()
        self.modelList.set_selection_mode(gtk.SELECTION_BROWSE)
        for key, model in self.rules[0].items():
            loc = self.modelList.append((model,))
	    self.modelList.set_row_data(loc, key)
            if key == self.model:
                self.modelList.select_row(loc, 0)
        self.modelList.sort()
        self.modelList.connect("select_row", self.select_row)
        self.modelList.columns_autosize()
        self.modelList.connect_after("size-allocate", moveto)
	self.modelList.thaw()
        sw.add(self.modelList)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        box.pack_start(sw, gtk.TRUE)

	box.pack_start(gtk.Label(_("Layout")), gtk.FALSE)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.layoutList = gtk.CList(1)
	self.layoutList.freeze()
        self.layoutList.set_selection_mode(gtk.SELECTION_BROWSE)
        for key, layout in self.rules[1].items():
            loc = self.layoutList.append((layout,))
	    self.layoutList.set_row_data(loc, key)
            if key == self.layout:
                self.layoutList.select_row(loc, 0)
        self.layoutList.sort()
        self.layoutList.connect("select_row", self.select_row)
        self.layoutList.columns_autosize()
	self.layoutList.connect_after("size-allocate", moveto)
	self.layoutList.thaw()
        sw.add(self.layoutList)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
	box.pack_start(sw, gtk.TRUE)

	box.pack_start(gtk.Label(_("Dead Keys")), gtk.FALSE)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.variantList = gtk.CList(1)
        self.variantList.set_selection_mode(gtk.SELECTION_BROWSE)
#  For now, the only variant is deadkeys, so we'll just handle that
#  as special case, so the text can be less confusing.
#        self.variantList.append(("None",))
#        for (key, variant) in self.rules[2].items():
        count = 0
        for key, variant in(("basic",(_("Enable dead keys"))),
                            ("nodeadkeys",(_("Disable dead keys")))):
            loc = self.variantList.append((variant,))
	    self.variantList.set_row_data(loc, key)
            if self.variant == "nodeadkeys":
                self.variantList.select_row(count, 0)
            count = count + 1
            
        self.variantList.sort()
        self.variantList.connect("select_row", self.select_row)
        self.variantList.columns_autosize()
        sw.add(self.variantList)
	box.pack_start(sw, gtk.FALSE)

        label = gtk.Label(_("Test your selection here:"))
        label.set_alignment(0.0, 0.5)
        box.pack_start(label, gtk.FALSE)

        entry = gtk.Entry()
        box.pack_start(entry, gtk.FALSE)

        entry.connect("grab-focus", self.setMap)

        box.set_border_width(5)
        return box
