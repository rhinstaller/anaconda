from installclass import BaseInstallClass
from rhpl.translate import N_
from constants import *
import os
import iutil
from autopart import getAutopartitionBoot, autoCreatePartitionRequests
from fsset import *

class InstallClass(BaseInstallClass):
    showLoginChoice = 0
    name = N_("Personal Desktop")
    pixmap = "workstation.png"
    description = N_("Perfect for personal computers or laptops, select this "
		     "installation type to install a graphical desktop "
		     "environment and create a system ideal for home "
		     "or desktop use.")

    sortPriority = 1

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
	dispatch.skipStep("partition")
	dispatch.skipStep("authentication")

        dispatch.skipStep("desktopchoice", skip = 0)
        dispatch.skipStep("package-selection", skip = 1)

    def setGroupSelection(self, comps, intf):
	BaseInstallClass.__init__(self, comps)

        for comp in comps.comps:
            comp.unselect()

        comps["Workstation Common"].includeMembers()
        comps["GNOME Desktop Environment"].select()

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
