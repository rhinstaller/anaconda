from snack import *
from constants_text import *
from translate import _
import os

class WelcomeWindow:
    def __call__(self, screen):
        rc = ButtonChoiceWindow(screen, _("Red Hat Linux"), 
                                _("Welcome to Red Hat Linux!\n\n"
                                  "This installation process is outlined in detail in the "
                                  "Official Red Hat Linux Installation Guide available from "
                                  "Red Hat, Inc. If you have access to this manual, you "
                                  "should read the installation section before continuing.\n\n"
                                  "If you have purchased Official Red Hat Linux, be sure to "
                                  "register your purchase through our web site, "
                                  "http://www.redhat.com/."),
                                buttons = [TEXT_OK_BUTTON, TEXT_BACK_BUTTON], width = 50,
				help = "welcome")

	if rc == TEXT_BACK_CHECK:
	    return INSTALL_BACK

        return INSTALL_OK

class ReconfigWelcomeWindow:
    def __call__(self, screen):
        rc = ButtonChoiceWindow(screen, _("Red Hat Linux"), 
                                _("Welcome to the Red Hat Linux!\n\n"
                                  "You have entered reconfiguration mode, "
                                  "which will allow you to configure "
                                  "site-specific options of your computer."
                                  "\n\n"
                                  "To exit without changing your setup "
                                  "select the ""Cancel"" button below."),
                                buttons = [TEXT_OK_BUTTON, _("Cancel")], width = 50,
				help = "reconfigwelcome")

	if rc == string.lower(_("Cancel")):
            screen.finish()
	    os._exit(0)

        return INSTALL_OK

