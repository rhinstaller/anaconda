from gtk import *
from iw import *
from gui import _
import GdkImlib

class WelcomeWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Welcome to Red Hat Linux!"))
        ics.setNextEnabled (1)
        ics.readHTML ("wel")

    def getScreen (self):
        box = GtkVBox (FALSE, 10)
        im = None
        try:
            im = GdkImlib.Image ("/usr/share/anaconda/pixmaps/splash.png")
        except:
            try:
                im = GdkImlib.Image ("pixmaps/splash.png")
            except:
                print "Unable to load splash.png"
        if im:
            im.render ()
            pix = im.make_pixmap ()
            box.pack_start (pix, TRUE, TRUE, 0)

        return box

