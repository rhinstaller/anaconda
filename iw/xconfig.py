from gtk import *
from iw import *
from gui import _

import string
import sys

class XConfigWindow (InstallWindow):
    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle (_("X Configuration"))
        ics.setNextEnabled (1)
        ics.setHTML ("<HTML><BODY>This is the X configuration screen<</BODY></HTML>")

    def getScreen (self):
        self.todo.x.probe ()

        box = GtkVBox (FALSE, 50)
        box.set_border_width (5)

        label = GtkLabel (_("In most cases your video hardware can "
                            "be probed to automatically determine the "
                            "best settings for your display."))
        label.set_justify (JUSTIFY_LEFT)
        label.set_line_wrap (TRUE)        
        label.set_alignment (0.0, 0.5)
        box.pack_start (label, FALSE)
        
        label = GtkLabel (_("Autoprobe results:"))
        label.set_alignment (0.0, 0.5)
        box.pack_start (label, FALSE)

        report = self.todo.x.probeReport ()
        report = string.replace (report, '\t', '       ')
        
        result = GtkLabel (report)
        result.set_alignment (0.2, 0.5)
        result.set_justify (JUSTIFY_LEFT)
        box.pack_start (result, FALSE)
        
        test = GtkAlignment ()
        test.set (0.5, 0.5, 0.0, 0.0)
        button = GtkButton (_("Test this configuration"))
        test.add (button)

        custom = GtkCheckButton (_("Customize X Configuration"))

        box.pack_start (test, FALSE)
        box.pack_start (custom, FALSE)
        
        top = GtkAlignment ()
        top.set (0.5, 0.5, 1.0, 0.0)
        top.add (box)

        return top
