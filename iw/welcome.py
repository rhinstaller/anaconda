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
            box = GtkEventBox ()
            pix = im.make_pixmap ()
            style = box.get_style ().copy ()
            style.bg[STATE_NORMAL] = style.white
            box.set_style (style)
            box.add (pix)
            frame.add (box)

        return frame

