from gtk import *
from gnome.ui import *
from iw_gui import *
from translate import _

class CongratulationWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Congratulations"))
        ics.setPrevEnabled (FALSE)
        ics.setNextButton (STOCK_PIXMAP_QUIT, _("Exit"))
        ics.setNextEnabled (TRUE)
        ics.setHelpButtonEnabled (FALSE)
	ics.setGrabNext (1)

    # CongratulationWindow tag=NA
    def getScreen (self):
        self.ics.setHelpEnabled (FALSE)

        hbox = GtkHBox (TRUE, 5)
        
        im = self.ics.readPixmap ("done.png")
        if im:
            im.render ()
            pix = im.make_pixmap ()
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
            hbox.pack_start (a, FALSE)

	label = GtkLabel(
                     _("Congratulations, installation is complete.\n\n"
                       "Press return to reboot, and be sure to remove your "
		       "boot medium after the system reboots, or your system "
		       "will rerun the install. For information on fixes which "
                       "are available for this release of Red Hat Linux, "
                       "consult the "
                       "Errata available from http://www.redhat.com/errata.\n\n"
                       "Information on configuring and using your Red Hat "
		       "Linux system is contained in the Red Hat Linux "
		       "manuals."))
                
        label.set_line_wrap (TRUE)
        label.set_alignment (0.0, 0.5)

        box = GtkVBox (FALSE, 10)
        box.pack_start (label, TRUE, TRUE, 0)

        hbox.pack_start (box)
        return hbox


class ReconfigCongratulationWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Congratulations"))
        ics.setPrevEnabled (0)
        ics.setNextButton (STOCK_PIXMAP_QUIT, _("Exit"))
        ics.setNextEnabled (1)
	ics.setGrabNext (1)

    # ReconfigCongratulationWindow tag=NA
    def getScreen (self):
        self.ics.setHelpEnabled (0)

        hbox = GtkHBox (TRUE, 5)
        
        im = self.ics.readPixmap ("done.png")
        if im:
            im.render ()
            pix = im.make_pixmap ()
            a = GtkAlignment ()
            a.add (pix)
            a.set (0.5, 0.5, 1.0, 1.0)
            hbox.pack_start (a, FALSE)

        self.ics.cw.todo.writeConfiguration()

        label = GtkLabel(_("Congratulations, configuration is complete.\n\n"
                           "For information on fixes which are "
                           "available for this release of Red Hat Linux, consult the "
                           "Errata available from http://www.redhat.com.\n\n"
                           "Information on further configuring your system is available in the Official "
                           "Red Hat Linux Manuals available at http://www.redhat.com/support/manuals/."))
        
        label.set_line_wrap (TRUE)
        label.set_alignment (0.0, 0.5)
        
        box = GtkVBox (FALSE, 10)
        box.pack_start (label, TRUE, TRUE, 0)

        hbox.pack_start (box)
        return hbox

