from installclass import BaseInstallClass
from rhpl.translate import N_
from constants import *
import os
import iutil
from autopart import getAutopartitionBoot, autoCreatePartitionRequests

# custom installs are easy :-)
class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    name = N_("_Custom")
    pixmap = "custom.png"
    description = N_("Select this installation type to gain complete "
		     "control over the installation process, including "
		     "software package selection and authentication "
		     "preferences.")
    sortPriority = 10000
    showLoginChoice = 1
    showMinimal = 1

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
