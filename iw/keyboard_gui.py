from gtk import *
from iw_gui import *
import xkb
import string
from translate import _
from kbd import Keyboard
import iutil
import isys

class KeyboardWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Keyboard Configuration"))
        ics.readHTML ("kybd")
        ics.setNextEnabled (TRUE)
	self.kb = xkb.XKB ()
	self.rules = self.kb.getRules ()
	rules = self.kb.getRulesBase ()
	self.rulesbase = rules[string.rfind (rules, "/")+1:]
        self.model = "pc101"
        self.layout = "en_US"
	if self.todo.keyboard.type == "Sun":
	    self.model = self.todo.keyboard.model
	    self.layout = self.todo.keyboard.layout
        self.variant = ""
        self.hasrun = 0

    def getNext (self):
        if self.hasrun:
            self.todo.x.setKeyboard (self.rulesbase, self.model,
                                     self.layout, self.variant, "")
            self.todo.keyboard.setfromx (self.model, self.layout)
	    isys.loadKeymap(self.todo.keyboard.get())
        return None

    def select_row (self, clist, row, col, event):
	self.model = self.modelList.get_row_data (self.modelList.selection[0])
	self.layout = self.layoutList.get_row_data (self.layoutList.selection[0])
	self.variant = self.variantList.get_row_data (self.variantList.selection[0])
        
	self.kb.setRule (self.model, self.layout, self.variant, "complete")

    def getScreen (self):
        if not self.hasrun:
            default = iutil.defaultKeyboard()
            if Keyboard.console2x.has_key (default):
                self.model = Keyboard.console2x[default][0]
                self.layout = Keyboard.console2x[default][1]
                self.kb.setRule (self.model, self.layout, self.variant, "complete")

	box = GtkVBox (FALSE, 5)
        im = self.ics.readPixmap ("gnome-keyboard.png")
        if im:
            im.render ()
            pix = im.make_pixmap ()
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.0, 0.0, 0.0, 0.0)
            box.pack_start (a, FALSE)

	def moveto (widget, *args):
            widget.moveto (widget.selection[0], 0, 0.5, 0.5)

	box.pack_start (GtkLabel (_("Model")), FALSE)
        sw = GtkScrolledWindow ()
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.modelList = GtkCList ()
	self.modelList.freeze ()
        self.modelList.set_selection_mode (SELECTION_BROWSE)
        for (key, model) in self.rules[0].items ():
            loc = self.modelList.append ((model,))
	    self.modelList.set_row_data (loc, key)
            if key == self.model:
                self.modelList.select_row (loc, 0)
        self.modelList.sort ()
        self.modelList.connect ("select_row", self.select_row)
        self.modelList.columns_autosize ()
        self.modelList.connect_after ("map", moveto)
	self.modelList.thaw ()
        sw.add (self.modelList)
	box.pack_start (sw, TRUE)

	box.pack_start (GtkLabel (_("Layout")), FALSE)
        sw = GtkScrolledWindow ()
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.layoutList = GtkCList ()
	self.layoutList.freeze ()
        self.layoutList.set_selection_mode (SELECTION_BROWSE)
        for (key, layout) in self.rules[1].items ():
            loc = self.layoutList.append ((layout,))
	    self.layoutList.set_row_data (loc, key)
            if key == self.layout:
                self.layoutList.select_row (loc, 0)
        self.layoutList.sort ()
        self.layoutList.connect ("select_row", self.select_row)
        self.layoutList.columns_autosize ()
	self.layoutList.connect_after ("map", moveto)
	self.layoutList.thaw ()
        sw.add (self.layoutList)
	box.pack_start (sw, TRUE)

	box.pack_start (GtkLabel (_("Dead Keys")), FALSE)
        sw = GtkScrolledWindow ()
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.variantList = GtkCList ()
        self.variantList.set_selection_mode (SELECTION_BROWSE)
#  For now, the only variant is deadkeys, so we'll just handle that
#  as special case, so the text can be less confusing.
#        self.variantList.append (("None",))
#        for (key, variant) in self.rules[2].items ():
        for (key, variant) in ((None, (_("Enable dead keys"))),
                               ("nodeadkeys", (_("Disable dead keys")))):
            loc = self.variantList.append ((variant,))
	    self.variantList.set_row_data (loc, key)
        self.variantList.sort ()
        self.variantList.connect ("select_row", self.select_row)
        self.variantList.columns_autosize ()
        sw.add (self.variantList)
	box.pack_start (sw, FALSE)

        label = GtkLabel (_("Test your selection here:"))
        label.set_alignment (0.0, 0.5)
        box.pack_start (label, FALSE)

        entry = GtkEntry ()
        box.pack_start (entry, FALSE)

        box.set_border_width (5)
        self.hasrun = 1
        return box
