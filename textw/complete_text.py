from snack import *
from constants_text import *
from translate import _

class FinishedWindow:
    def __call__ (self, screen):


        screen.pushHelpLine (_("                              <Return> to reboot                              "))

	rc = ButtonChoiceWindow (screen, _("Complete"), 
             _("Congratulations, your Red Hat Linux installation is "
               "complete.\n\n"
               "Remove any CD-ROMs or floppy diskettes you used during the "
               "installation process and press <Enter> to reboot your system. "
               "\n\n"
               "If you created a boot disk to use to boot your Red Hat Linux "
               "system, insert it before you press <Enter> to reboot.\n\n"
               "For information on errata (updates and bug fixes), visit "
               "http://www.redhat.com/errata.\n\n"
               "Information on using and configuring your "
               "system is available in the Red Hat Linux manuals."),
		[ _("OK") ], help = "finished", width=60)

        return INSTALL_OK


class ReconfigFinishedWindow:
    def __call__ (self, screen):

        screen.pushHelpLine (_("                                <Return> to exit                              "))

        rc = ButtonChoiceWindow (screen, _("Complete"), 
                _("Congratulations, configuration is complete.\n\n"
                  "For information on errata (updates and bug fixes), visit "
                  "http://www.redhat.com/errata.\n\n"
                  "Information on using and configuring your "
                  "system is available in the Red Hat Linux manuals."),
                   [ _("OK") ], help = "reconfigfinished")

        return INSTALL_OK
