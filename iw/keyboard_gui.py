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
from iw_gui import *
from gtk import *
from kbd import Keyboard
from log import log
from flags import flags
from translate import _, N_

class KeyboardWindow (InstallWindow):
    hasrun = 0

    windowTitle = N_("Keyboard Configuration")
    htmlTag = "kybd"

    def __init__(self, ics):
	InstallWindow.__init__(self, ics)

	self.kb = xkb.XKB()
	self.rules = self.kb.getRules()
	rules = self.kb.getRulesBase()
	self.rulesbase = rules[string.rfind(rules, "/")+1:]

    def getNext (self):
        if self.hasrun:
            if self.flags.setupFilesystems:
                self.kb.setRule(self.model, self.layout, self.variant,
                                 "complete")
            
            self.x.setKeyboard(self.rulesbase, self.model,
                                self.layout, self.variant, "")

            self.kbd.setfromx(self.model, self.layout, self.variant)

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

        rules, model, layout, variant, options = x.getKeyboard()
        self.model = model
        self.layout = layout
        self.variant = variant

        if not self.hasrun:
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


	box = GtkVBox(FALSE, 5)
        hbox = GtkHBox(FALSE, 5)
        im = self.ics.readPixmap("gnome-keyboard.png")
        if im:
            im.render()
            pix = im.make_pixmap()
            a = GtkAlignment()
            a.add(pix)
            a.set(0.0, 0.0, 0.0, 0.0)
            hbox.pack_start(a, FALSE)

        label = GtkLabel(_("Which model keyboard is attached to the computer?"))
        label.set_line_wrap(TRUE)
        label.set_usize(350, -1)
        hbox.pack_start(label, FALSE)
        box.pack_start(hbox, FALSE)

	def moveto(widget, *args):
            widget.moveto(widget.selection[0], 0, 0.5, 0.5)

	box.pack_start(GtkLabel(_("Model")), FALSE)
        sw = GtkScrolledWindow()
        sw.set_policy(POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.modelList = GtkCList()
	self.modelList.freeze()
        self.modelList.set_selection_mode(SELECTION_BROWSE)
        for key, model in self.rules[0].items():
            loc = self.modelList.append((model,))
	    self.modelList.set_row_data(loc, key)
            if key == self.model:
                self.modelList.select_row(loc, 0)
        self.modelList.sort()
        self.modelList.connect("select_row", self.select_row)
        self.modelList.columns_autosize()
        self.modelList.connect_after("draw", moveto)
	self.modelList.thaw()
        sw.add(self.modelList)
        sw.set_policy(POLICY_NEVER, POLICY_AUTOMATIC)
        box.pack_start(sw, TRUE)

	box.pack_start(GtkLabel(_("Layout")), FALSE)
        sw = GtkScrolledWindow()
        sw.set_policy(POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.layoutList = GtkCList()
	self.layoutList.freeze()
        self.layoutList.set_selection_mode(SELECTION_BROWSE)
        for key, layout in self.rules[1].items():
            loc = self.layoutList.append((layout,))
	    self.layoutList.set_row_data(loc, key)
            if key == self.layout:
                self.layoutList.select_row(loc, 0)
        self.layoutList.sort()
        self.layoutList.connect("select_row", self.select_row)
        self.layoutList.columns_autosize()
	self.layoutList.connect_after("draw", moveto)
	self.layoutList.thaw()
        sw.add(self.layoutList)
        sw.set_policy(POLICY_NEVER, POLICY_AUTOMATIC)
	box.pack_start(sw, TRUE)

	box.pack_start(GtkLabel(_("Dead Keys")), FALSE)
        sw = GtkScrolledWindow()
        sw.set_policy(POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.variantList = GtkCList()
        self.variantList.set_selection_mode(SELECTION_BROWSE)
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
	box.pack_start(sw, FALSE)

        label = GtkLabel(_("Test your selection here:"))
        label.set_alignment(0.0, 0.5)
        box.pack_start(label, FALSE)

        entry = GtkEntry()
        box.pack_start(entry, FALSE)

        entry.connect("grab-focus", self.setMap)

        box.set_border_width(5)
        KeyboardWindow.hasrun = 1
        return box
