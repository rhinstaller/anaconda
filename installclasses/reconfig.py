from installclass import BaseInstallClass
from instdata import InstallData
from translate import N_
from translate import _
import os
import iutil

class ReconfigInstallData(InstallData):

    def write(self, instPath):
        self.langSupport.write (instPath)
        self.keyboard.write (instPath)
        self.network.write (instPath)
        self.auth.write (instPath)
	self.firewall.write (instPath)
	self.timezone.write (instPath)
        self.rootPassword.write (instPath, self.auth)
        self.accounts.write (instPath, self.auth)

    def writeKS(self, file):
	pass

class InstallClass(BaseInstallClass):
    name = "reconfig"
    pixmap = None
    sortPriority = 999999
    hidden = 1

    parentClass = None

    def setSteps(self, dispatch):
	dispatch.setStepList(
		    "reconfigwelcome",
		    "reconfigkeyboard",
		    "network",
		    "firewall",
		    "languagesupport",
		    "timezone",
		    "accounts",
		    "authentication",
		    "writeconfig",
		    "reconfigcomplete"
		)

    installDataClass = ReconfigInstallData

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

        if (iutil.getDefaultRunlevel() != '5' or
            not os.access("/etc/X11/XF86Config", os.R_OK)):
                forceTextMode = 1
