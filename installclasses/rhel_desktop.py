from installclass import BaseInstallClass
from rhpl.translate import N_, _
from constants import *
import os
import iutil

# custom installs are easy :-)
class InstallClass(BaseInstallClass):
    name = N_("Red Hat Enterprise Linux Desktop")
    pixmap = "workstation.png"
    description = N_("Red Hat Enterprise Linux Desktop")
    sortPriority = 100
    showLoginChoice = 0
    hidden = 1

    pkgstext = N_("\tDesktop shell (GNOME)\n"
                  "\tOffice suite (OpenOffice.org)\n"
                  "\tWeb browser \n"
                  "\tEmail (Evolution)\n"
                  "\tInstant messaging\n"
                  "\tSound and video applications\n"
                  "\tGames\n")

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
        dispatch.skipStep("desktopchoice", skip = 0)
        dispatch.skipStep("package-selection", skip = 1)

    def setGroupSelection(self, grpset, intf):
	BaseInstallClass.__init__(self, grpset)

        grpset.unselectAll()
        grpset.selectGroup("workstation-common", asMeta = 1)
        grpset.selectGroup("gnome-desktop")        
        grpset.selectGroup("compat-arch-support", asMeta = 1, missingOk = 1)
        
    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)
        BaseInstallClass.setDefaultPartitioning(self, id.partitions,
                                                CLEARPART_TYPE_LINUX)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
