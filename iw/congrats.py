from gtk import *
from gnome.ui import *
from iw import *
import gettext

cat = gettext.Catalog ("anaconda", "/usr/share/locale")
_ = cat.gettext

class CongratulationWindow (InstallWindow):		

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        ics.setTitle (_("Congratulations"))
        ics.setPrevEnabled (0)
        ics.setNextButton (STOCK_PIXMAP_QUIT, _("Exit"))
        ics.setNextEnabled (1)

    def getScreen (self):
        label = GtkLabel(_("Congratulations, installation is complete.\n\n"
                         "Remove the boot media and "
                         "press return to reboot. For information on fixes which are "
                         "available for this release of Red Hat Linux, consult the "
                         "Errata available from http://www.redhat.com.\n\n"
                         "Information on configuring your system is available in the post "
                         "install chapter of the Official Red Hat Linux User's Guide."))
        label.set_line_wrap (TRUE)
        label.set_line_wrap (TRUE)
        label.set_alignment (0.0, 0.5)

        box = GtkVBox (FALSE, 10)
        box.pack_start (label, TRUE, TRUE, 0)

        return box
