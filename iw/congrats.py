from gtk import *
from iw import *

class CongratulationWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle ("Congratulations")
        ics.setPrevEnabled (0)
        ics.setNextEnabled (1)

    def getScreen (self):
        label = GtkLabel("install done")

        box = GtkVBox (FALSE, 10)
        box.pack_start (label, TRUE, TRUE, 0)

        return box
