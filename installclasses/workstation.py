from installclass import BaseInstallClass
from translate import N_
import os
import iutil
from partitioning import *
from fsset import *

class InstallClass(BaseInstallClass):
    name = N_("Advanced Workstation")
    pixmap = "workstation.png"

    sortPriority = 1

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
	dispatch.skipStep("authentication")

    def setGroupSelection(self, comps):
	BaseInstallClass.__init__(self, comps)
	self.showGroups(comps, [ "KDE", ("GNOME", 1),
                                 ("Software Development", 1),
                                 "Games and Entertainment" ] )
        comps["Workstation Common"].select()

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)

        autorequests = [ ("/", None, 1100, None, 1, 1) ]

        bootreq = getAutopartitionBoot()
        if bootreq:
            autorequests.append(bootreq)

        (minswap, maxswap) = iutil.swapSuggestion()
        autorequests.append((None, "swap", minswap, maxswap, 1, 1))

        id.partitions.autoClearPartType = CLEARPART_TYPE_LINUX
        id.partitions.autoClearPartDrives = None
        id.partitions.autoPartitionRequests = autoCreatePartitionRequests(autorequests)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
