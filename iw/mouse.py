from gtk import *
from iw import *

class MouseWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle ("Mouse Configuration")
        ics.setHTML ("<HTML><BODY>Select your mouse."
                     "</BODY></HTML>")
        ics.setNextEnabled (TRUE)

    def getNext (self):
        self.todo.mouse.set (self.typeList.get_selection ()[0].children ()[0].get ())
        return None

    def getScreen (self):
        box = GtkVBox (FALSE, 5)
        
        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.locList = GtkList ()
        self.locList.set_selection_mode (SELECTION_BROWSE)
        devs = ("PS/2 Port (psaux)", "COM 1 (ttyS0)",
                "COM 2 (ttyS1)", "COM 3 (ttyS2)", "COM 4 (ttyS3)")
        self.locList.append_items (map (GtkListItem, devs))
        frame = GtkFrame ()
        frame.set_shadow_type (SHADOW_IN)
        frame.add (self.locList)
        frame.set_border_width (5)
        box.pack_start (frame, FALSE)

        sw = GtkScrolledWindow ()
        sw.set_border_width (5)
        sw.set_policy (POLICY_AUTOMATIC, POLICY_AUTOMATIC)
        self.typeList = GtkList ()
        self.typeList.set_selection_mode (SELECTION_BROWSE)
        sorted_mice = self.todo.mouse.available ()
        sorted_mice.sort ()
        self.typeList.append_items (map (GtkListItem, sorted_mice))
        sw.add_with_viewport (self.typeList)
        box.pack_start (sw)

        return box


   
