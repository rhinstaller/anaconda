from gtk import *
from iw import *
import xkb
from gui import _

class KeyboardWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Keyboard Configuration"))
##         ics.setHTML ("<HTML><BODY>Select your keyboard."
##                      "</BODY></HTML>")
        ics.readHTML ("kybd")
        ics.setNextEnabled (TRUE)
	self.kb = xkb.XKB ()
	self.rules = self.kb.getRules ()

    def getNext (self):
#        self.todo.keyboard.set (self.keyboardList.get_selection ()[0].children ()[0].get ())
        return None

    def getScreen (self):
#        print self.todo.keyboard.available ()
	box = GtkVBox (FALSE)
        
	box.pack_start (GtkLabel (_("Model")), FALSE)
        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.modelList = GtkCList ()
        self.modelList.set_selection_mode (SELECTION_BROWSE)
	for model in self.rules[0].values ():
            self.modelList.append ((model,))
        self.modelList.columns_autosize ()
        sw.add (self.modelList)
	box.pack_start (sw, TRUE)

	box.pack_start (GtkLabel (_("Layout")), FALSE)
        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.layoutList = GtkCList ()
        self.layoutList.set_selection_mode (SELECTION_BROWSE)
        layouts = self.rules[1].values ()
        layouts.sort ()
        for layout in layouts:
            self.layoutList.append ((layout,))
        self.layoutList.columns_autosize ()
        sw.add (self.layoutList)
	box.pack_start (sw, TRUE)

	box.pack_start (GtkLabel (_("Variant")), FALSE)
        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.variantList = GtkCList ()
        self.variantList.set_selection_mode (SELECTION_BROWSE)
        self.variantList.append (("None",))
	for variant in self.rules[2].values ():
            self.variantList.append ((variant,))
        self.variantList.columns_autosize ()
        sw.add (self.variantList)
	box.pack_start (sw, FALSE)

#	print self.kb.getOptions ()

        return box
