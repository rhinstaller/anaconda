from snack import *
from constants_text import *
from translate import _

class FinishedWindow:
    def __call__ (self, screen):


        screen.pushHelpLine (_("                              <Return> to reboot                              "))

	rc = ButtonChoiceWindow (screen, _("Complete"), 
		 _("Congratulations, installation is complete.\n\n"
		   "Press return to reboot, and be sure to remove your "
		   "boot medium after the system reboots, or your system "
		   "will rerun the install. For information on fixes which "
		   "are available for this release of Red Hat Linux, "
		   "consult the "
		   "Errata available from http://www.redhat.com/errata.\n\n"
		   "Information on configuring and using your Red Hat "
		   "Linux system is contained in the Red Hat Linux "
		   "manuals."),
		[ _("OK") ], help = "finished")

        return INSTALL_OK


class ReconfigFinishedWindow:
    def __call__ (self, screen):

        screen.pushHelpLine (_("                                <Return> to exit                              "))

        rc = ButtonChoiceWindow (screen, _("Complete"), 
                                 _("Congratulations, configuration is complete.\n\n"
                                   " For information on fixes which "
                                   "are available for this release of Red Hat Linux, "
                                   "consult the "
                                   "Errata available from http://www.redhat.com.\n\n"
                                   "Information on further configuring your system is "
                                   "available at http://www.redhat.com/support/manuals/"),

                                 [ _("OK") ], help = "reconfigfinished")

        return INSTALL_OK
