from gtk import *
from iw import *

class KeyboardWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle ("Keyboard Configuration")
        ics.setHTML ("<HTML><BODY>Select your keyboard."
                     "</BODY></HTML>")
        ics.setNextEnabled (TRUE)

    def getNext (self):
        self.todo.keyboard.set (self.keyboardList.get_selection ()[0].children ()[0].get ())
        return None

    def getScreen (self):
        
        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.keyboardList = GtkList ()
        self.keyboardList.set_selection_mode (SELECTION_BROWSE)
        sorted_keyboards = self.todo.keyboard.available ()
        sorted_keyboards.sort ()
        self.keyboardList.append_items (map (GtkListItem, sorted_keyboards))
        sw.add_with_viewport (self.keyboardList)

        return sw
