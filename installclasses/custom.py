from installclass import BaseInstallClass
from translate import N_
import os
import iutil
from autopart import CLEARPART_TYPE_LINUX
from autopart import CLEARPART_TYPE_ALL
from autopart import CLEARPART_TYPE_NONE
from partitioning import *

# custom installs are easy :-)
class InstallClass(BaseInstallClass):
    name = N_("Custom")
    pixmap = "custom.png"
        
    sortPriority = 10000

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)

        autorequests = [ ("/", None, 700, None, 1, 1) ]

        bootreq = getAutopartitionBoot()
        if bootreq:
            autorequests.append(bootreq)

        (minswap, maxswap) = iutil.swapSuggestion()
        autorequests.append((None, "swap", minswap, maxswap, 1, 1))
        id.partitions.autoClearPartType = CLEARPART_TYPE_LINUX
        id.partitions.autoClearPartDrives = []
        id.partitions.autoPartitionRequests = autoCreatePartitionRequests(autorequests)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

	if expert:
	    self.skipLilo = 1
	else:
	    self.skipLilo = 0
