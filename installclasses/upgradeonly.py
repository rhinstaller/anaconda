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
		    "installtype",
		    "addswap",
		    "dependencies",
		    "monitor",
		    "install",
		    "complete"
		)
    
    def __init__(self, expert):
	BaseInstallClass.__init__(self)

        self.installType = "upgrade"
