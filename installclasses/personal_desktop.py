from installclass import BaseInstallClass
from rhpl.translate import N_, _
from constants import *
import os
import iutil
from fsset import *

class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "personal desktop"
    name = N_("_Personal Desktop")
    pixmap = "workstation.png"
    _description = N_("Perfect for personal computers or laptops, select this "
		     "installation type to install a graphical desktop "
		     "environment and create a system ideal for home "
		     "or desktop use.")
    
    pkgstext = N_("\tDesktop shell (GNOME)\n"
                  "\tOffice suite (OpenOffice.org)\n"
                  "\tWeb browser \n"
                  "\tEmail (Evolution)\n"
                  "\tInstant messaging\n"
                  "\tSound and video applications\n"
                  "\tGames\n")
    

    showLoginChoice = 0
    sortPriority = 1
    hidden = 1

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
	dispatch.skipStep("partition")
        dispatch.skipStep("desktopchoice", skip = 0)
        dispatch.skipStep("package-selection", skip = 1)

    def setGroupSelection(self, anaconda):
	BaseInstallClass.__init__(self, anaconda.backend)

        anaconda.backend.unselectAll()

        anaconda.backend.selectGroup("workstation-common", asMeta = 1)
        anaconda.backend.selectGroup("gnome-desktop")
        anaconda.backend.selectGroup("compat-arch-support", asMeta = 1, missingOk = 1)

    def setInstallData(self, anaconda):
	BaseInstallClass.setInstallData(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self, anaconda.id.partitions,
                                                CLEARPART_TYPE_LINUX)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
