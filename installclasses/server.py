from installclass import BaseInstallClass
from translate import *
import os
import iutil
from partitioning import autoCreatePartitionRequests
from autopart import CLEARPART_TYPE_LINUX
from autopart import CLEARPART_TYPE_ALL
from autopart import CLEARPART_TYPE_NONE

class InstallClass(BaseInstallClass):

    name = N_("Server")
    pixmap = "server.png"
    sortPriority = 10

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);

	if self.skipLilo:
	    dispatch.skipStep("bootloader")
	dispatch.skipStep("authentication")
	dispatch.skipStep("bootdisk", skip = 0)

    def setGroupSelection(self, comps):
	BaseInstallClass.__init__(self, comps)
	self.showGroups(comps, 
			  [ "KDE", 
			    ("GNOME", 0),
			    ("X Window System", 0),
			    "News Server",
                            "NFS Server",
                            "Web Server",
                            "SMB (Samba) Server",
                            "DNS Name Server" ])
	comps["Server"].select()

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)
	self.setHostname(id, "localhost.localdomain")

        autorequests = [ ("/", None,256, None, 1, 1),
                         ("/usr", None, 800, None, 0, 1),
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

	if expert:
	    self.skipLilo = 1
	else:
	    self.skipLilo = 0
