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
##         ics.setHTML("<HTML><BODY><CENTER><H2>Welcome to<br>Red Hat Linux!</H2></CENTER>"
##                     ""
##                     "<P>This installation process is outlined in detail in the "
##                     "Official Red Hat Linux Installation Guide available from "
##                     "Red Hat Software. If you have access to this manual, you "
##                     "should read the installation section before continuing.</P><P>"
##                     "If you have purchased Official Red Hat Linux, be sure to "
##                     "register your purchase through our web site, "
##                     "http://www.redhat.com/.</BODY></HTML>")
        

    def getScreen (self):
        box = GtkVBox (FALSE, 10)
        im = None
        try:
            print "foo"
            im = GdkImlib.Image ("/usr/share/anaconda/pixmaps/splash.png")
        except:
            try:
                print "bar"
                im = GdkImlib.Image ("pixmaps/splash.png")
            except:
                print "Unable to load splash.png"
        if im:
            im.render ()
            pix = im.make_pixmap ()
            box.pack_start (pix, TRUE, TRUE, 0)

        return box
