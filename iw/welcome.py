from gtk import *
from iw import *

class WelcomeWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle ("Welcome to Red Hat Linux!")
        ics.setPrevEnabled (0)
        ics.setNextEnabled (1)
        ics.setHTML("<HTML><BODY><CENTER><H2>Welcome to<br>Red Hat Linux!</H2></CENTER>"
                    ""
                    "<P>This installation process is outlined in detail in the "
                    "Official Red Hat Linux Installation Guide available from "
                    "Red Hat Software. If you have access to this manual, you "
                    "should read the installation section before continuing.</P><P>"
                    "If you have purchased Official Red Hat Linux, be sure to "
                    "register your purchase through our web site, "
                    "http://www.redhat.com/.</P></BODY></HTML>")

    def getScreen (self):
        label = GtkLabel("(insert neat logo graphic here)")

        box = GtkVBox (FALSE, 10)
        box.pack_start (label, TRUE, TRUE, 0)

        try:
            im = GdkImlib.Image ("shadowman-200.png")
            im.render ()
            pix = im.make_pixmap ()
            box.pack_start (pix, TRUE, TRUE, 0)

        except:
            print "Unable to load shadowman-200.png"

        return box
