from gtk import *
from iw import *
from gui import _

class ConfirmWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)
        ics.setNextEnabled (1)
        ics.setPrevEnabled (1)
        ics.setTitle (_("About to Install"))
        ics.setHelpEnabled (FALSE)
        ics.readHTML ("aboutinstall")

    def getScreen (self):
        hbox = GtkHBox (TRUE, 5)
        box = GtkVBox (FALSE, 5)

        im = self.ics.readPixmap ("about-to-install.png")
        if im:
            im.render ()
            pix = im.make_pixmap ()
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
            hbox.pack_start (a, FALSE)
        
        label = GtkLabel (_("Click next to begin installation of Red Hat Linux."))
        label.set_line_wrap (TRUE)
        
        label2 = GtkLabel (_("A complete log of your installation will be in "
                              "/tmp/install.log after rebooting your system. You "
                              "may want to keep this file for later reference."))

        label2.set_line_wrap (TRUE)
        
        box.pack_start (label, FALSE)
        box.pack_start (label2, FALSE)
        box.set_border_width (5)

        a = GtkAlignment ()
        a.add (box)
        a.set (0.5, 0.5, 0.0, 0.0)        

        hbox.pack_start (a)
        return hbox
    
        
