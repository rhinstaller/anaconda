from snack import *
from constants_text import *
from translate import _

class BeginInstallWindow:
    def __call__ (self, screen):
        rc = ButtonChoiceWindow (screen, _("Installation to begin"),
                                _("A complete log of your installation will be in "
                                  "/tmp/install.log after rebooting your system. You "
                                  "may want to keep this file for later reference."),
                                buttons = [ _("OK"), _("Back") ],
				help = "begininstall")
        if rc == string.lower (_("Back")):
            return INSTALL_BACK
        return INSTALL_OK

class BeginUpgradeWindow:
    def __call__ (self, screen) :
        rc = ButtonChoiceWindow (screen, _("Upgrade to begin"),
                                _("A complete log of your upgrade will be in "
                                  "/tmp/upgrade.log after rebooting your system. You "
                                  "may want to keep this file for later reference."),
                                buttons = [ _("OK"), _("Back") ],
				help = "beginupgrade")
        if rc == string.lower (_("Back")):
            return INSTALL_BACK
        return INSTALL_OK
