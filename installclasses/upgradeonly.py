from installclass import BaseInstallClass
from translate import N_
import os
import iutil

class InstallClass(BaseInstallClass):
    name = "upgradeonly"
    pixmap = ""
    hidden = 1
    sortPriority = 1

    def requiredDisplayMode(self):
        return 't'

    def setSteps(self, dispatch):
	dispatch.setStepList(
		    "mouse",
		    "findinstall",
                    "partitionobjinit",
                    "upgrademount",
                    "upgradeswapsuggestion",
		    "addswap",
                    "upgrademigfind",
                    "upgrademigratefs",
                    "upgradecontinue",
                    "bootloadersetup",
		    "bootloader",
                    "bootloaderpassword",
                    "checkdeps",
		    "dependencies",
		    "confirmupgrade",
		    "install",
                    "preinstallconfig",
                    "installpackages",
                    "postinstallconfig",
                    "instbootloader",
		    "bootdisk",
		    "complete"
		)

        if iutil.getArch() == "alpha" or iutil.getArch() == "ia64":
	    dispatch.skipStep("bootdisk")
            dispatch.skipStep("bootloader")
            dispatch.skipStep("bootloaderpassword")
    
    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

        self.installType = "upgrade"
