from installclass import BaseInstallClass
from rhpl.translate import *
from constants import *
import os
import iutil
from autopart import getAutopartitionBoot, autoCreatePartitionRequests

class InstallClass(BaseInstallClass):

    showLoginChoice = 1
    name = N_("Server")
    pixmap = "server.png"
    description = N_("Select this installation type if you would like to "
		     "set up file sharing, print sharing, and Web services. "
		     "Additional services can also be enabled, and you "
		     "can choose whether or not to install a graphical "
		     "environment.")
    
    sortPriority = 10

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
	dispatch.skipStep("authentication")

    def setGroupSelection(self, comps):
	BaseInstallClass.__init__(self, comps)

        for comp in comps.comps:
            comp.unselect()
	comps["Server"].includeMembers()

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)

        autorequests = [ ("/", None, 512, None, 0, 1),
                         ("/usr", None, 1400, None, 1, 1),
                         ("/var", None, 384, 1024, 1, 1),
                         ("/home", None, 512, None, 1, 1) ]

        bootreq = getAutopartitionBoot()
        if bootreq:
            autorequests.append(bootreq)
        
        (minswap, maxswap) = iutil.swapSuggestion()
        autorequests.append((None, "swap", minswap, maxswap, 1, 1))

        id.partitions.autoClearPartType = CLEARPART_TYPE_ALL
        id.partitions.autoClearPartDrives = []
        id.partitions.autoPartitionRequests = autoCreatePartitionRequests(autorequests)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
