from installclass import BaseInstallClass
from rhpl.translate import *
from constants import *
import os
import iutil
from autopart import getAutopartitionBoot, autoCreatePartitionRequests

class InstallClass(BaseInstallClass):

    name = N_("Server")
    pixmap = "server.png"
    sortPriority = 10

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
	dispatch.skipStep("authentication")

    def setGroupSelection(self, comps):
	BaseInstallClass.__init__(self, comps)
	self.showGroups(comps, 
			  [ "KDE", 
			    ("GNOME", 0),
                            "Classic X Window System",
			    ("X Window System", 0),
                            "DNS Name Server",
                            "Web Server",
                            "SQL Database Server",
                            "NFS File Server",
                            "Windows File Server",
                            "Anonymous FTP Server",
			    "News Server"])

	comps["Server"].select()

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)

        autorequests = [ ("/", None,384, None, 0, 1),
                         ("/usr", None, 1400, None, 1, 1),
                         ("/var", None, 256, None, 0, 1),
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
