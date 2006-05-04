from installclass import BaseInstallClass
from rhpl.translate import N_, _
from constants import *
import os
import iutil

# custom installs are easy :-)
class InstallClass(BaseInstallClass):
    name = N_("Red Hat Enterprise Linux WS")
    pixmap = "workstation.png"
    description = N_("Red Hat Enterprise Linux WS")
    sortPriority = 100
    showLoginChoice = 0
    hidden = 1

    pkgstext = N_("\tDesktop shell (GNOME)\n"
                  "\tOffice suite (OpenOffice.org)\n"
                  "\tWeb browser \n"
                  "\tEmail (Evolution)\n"
                  "\tInstant messaging\n"
                  "\tSound and video applications\n"
                  "\tGames\n"
                  "\tSoftware Development Tools\n"
                  "\tAdministration Tools\n")

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
        dispatch.skipStep("desktopchoice", skip = 0)
        dispatch.skipStep("package-selection", skip = 1)

    def setGroupSelection(self, anaconda):
	BaseInstallClass.__init__(self, anaconda.backend)

        anaconda.backend.unselectAll()
        anaconda.backend.selectGroup("workstation-common", asMeta = 1)
        anaconda.backend.selectGroup("gnome-desktop")        
        anaconda.backend.selectGroup("development-tools")
        anaconda.backend.selectGroup("compat-arch-support", asMeta = 1, missingOk = 1)
        anaconda.backend.selectGroup("compat-arch-development", asMeta = 1, missingOk = 1)
        
    def setInstallData(self, anaconda):
	BaseInstallClass.setInstallData(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self, anaconda.id.partitions,
                                                CLEARPART_TYPE_LINUX)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
