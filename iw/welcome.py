from gtk import *
from iw import *
from gui import _

class WelcomeWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Welcome"))
        ics.setNextEnabled (1)
        ics.readHTML ("wel")
        self.ics = ics

    def getScreen (self):
        frame = GtkFrame ()
        frame.set_shadow_type (SHADOW_IN)
        im = self.ics.readPixmap ("splash.png")
        
        if im:
            im.render ()
            pix = im.make_pixmap ()
            frame.add (pix)

        return frame

