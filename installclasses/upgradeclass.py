from installclass import BaseInstallClass
from rhpl.translate import N_, _

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
                    "findrootparts",
		    "findinstall",
                    "partitionobjinit",
                    "upgrademount",
                    "upgradeswapsuggestion",
		    "addswap",
                    "upgrademigfind",
                    "upgrademigratefs",
                    "upgradecontinue",
                    "readcomps",
                    "findpackages",
                    "upgbootloader",
                    "checkdeps",
		    "dependencies",
		    "confirmupgrade",
		    "install",
                    "migratefilesystems",
                    "preinstallconfig",
                    "installpackages",
                    "postinstallconfig",
                    "instbootloader",
                    "dopostaction",
		    "bootdisk",
		    "complete"
		)

        if iutil.getArch() == "alpha" or iutil.getArch() == "ia64":
	    dispatch.skipStep("bootdisk")
            dispatch.skipStep("bootloader")
            dispatch.skipStep("bootloaderadvanced")

    def setInstallData(self, id):
        BaseInstallClass.setInstallData(self, id)
        id.upgrade.set(1)
    
    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
