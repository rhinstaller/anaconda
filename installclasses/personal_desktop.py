from installclass import BaseInstallClass
from rhpl.translate import N_
from constants import *
import os
import iutil
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

    def setGroupSelection(self, grpset, intf):
	BaseInstallClass.__init__(self, grpset)

        grpset.unselectAll()

        grpset.selectGroup("workstation-common", asMeta = 1)
        grpset.selectGroup("gnome-desktop")

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)
        BaseInstallClass.setDefaultPartitioning(self, id.partitions,
                                                CLEARPART_TYPE_LINUX)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
