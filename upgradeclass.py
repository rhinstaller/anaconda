from installclass import BaseInstallClass
from translate import N_
from translate import _
import os
import iutil

class InstallClass(BaseInstallClass):
    name = N_("Upgrade Existing System")
    pixmap = "upgrade.png"
    sortPriority = 999999

    parentClass = ( _("Upgrade"), "upgrade.png" )

    def requiredDisplayMode(self):
        return 't'

    def setSteps(self, dispatch):
	dispatch.setStepList(
		    "language",
		    "keyboard",
		    "mouse",
		    "welcome",
		    "installtype",
		    "custom-upgrade",
		    "addswap",
                    "upgradecontinue",
		    "indivpackage",
		    "bootloader",
		    "dependencies",
		    "monitor",
		    "confirminstall",
		    "install",
		    "bootdisk",
		    "complete"
		)

        if iutil.getArch() == "alpha" or iutil.getArch() == "ia64":
	    dispatch.skipStep("bootdisk")
    
    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
