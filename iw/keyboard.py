from gtk import *
from iw import *
import xkb
from gui import _

class KeyboardWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Keyboard Configuration"))
        ics.readHTML ("kybd")
        ics.setNextEnabled (TRUE)
	self.kb = xkb.XKB ()
	self.rules = self.kb.getRules ()

    def getNext (self):
#        self.todo.keyboard.set (self.keyboardList.get_selection ()[0].children ()[0].get ())
        return None

    def select_row (self, clist, row, col, event):
	self.kb.setRule (self.modelList.get_row_data (self.modelList.selection[0]),
                         self.layoutList.get_row_data (self.layoutList.selection[0]),
                         self.variantList.get_row_data (self.variantList.selection[0]),
                         "complete")

    def getScreen (self):
	box = GtkVBox (FALSE, 5)
        im = self.ics.readPixmap ("gnome-keyboard.png")
        if im:
            im.render ()
            pix = im.make_pixmap ()
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.0, 0.0, 0.0, 0.0)
            box.pack_start (a, FALSE)

	box.pack_start (GtkLabel (_("Model")), FALSE)
        sw = GtkScrolledWindow ()
#        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.modelList = GtkCList ()
        self.modelList.set_selection_mode (SELECTION_BROWSE)
        for (key, model) in self.rules[0].items ():
            loc = self.modelList.append ((model,))
	    self.modelList.set_row_data (loc, key)
            if key == "pc104":
                self.modelList.select_row (loc, 0)
        self.modelList.sort ()
        self.modelList.connect ("select_row", self.select_row)
        self.modelList.columns_autosize ()
        sw.add (self.modelList)
	box.pack_start (sw, TRUE)

	box.pack_start (GtkLabel (_("Layout")), FALSE)
        sw = GtkScrolledWindow ()
#        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.layoutList = GtkCList ()
        self.layoutList.set_selection_mode (SELECTION_BROWSE)
        for (key, layout) in self.rules[1].items ():
            loc = self.layoutList.append ((layout,))
	    self.layoutList.set_row_data (loc, key)
            if key == "en_US":
                self.layoutList.select_row (loc, 0)
        self.layoutList.sort ()
        self.layoutList.connect ("select_row", self.select_row)
        self.layoutList.columns_autosize ()
        sw.add (self.layoutList)
	box.pack_start (sw, TRUE)

	box.pack_start (GtkLabel (_("Variant")), FALSE)
        sw = GtkScrolledWindow ()
#        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.variantList = GtkCList ()
        self.variantList.set_selection_mode (SELECTION_BROWSE)
        self.variantList.append (("None",))
        for (key, variant) in self.rules[2].items ():
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
        return box
