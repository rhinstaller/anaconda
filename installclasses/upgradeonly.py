from installclass import BaseInstallClass
from translate import N_
import os

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
    
    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

        self.installType = "upgrade"
