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

    pkgstext = _("\tDesktop shell (GNOME)\n"
                 "\tOffice suite (OpenOffice)\n"
                 "\tWeb browser (Mozilla) \n"
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

    def setGroupSelection(self, grpset, intf):
	BaseInstallClass.__init__(self, grpset)

        grpset.unselectAll()
        grpset.selectGroup("workstation-common", asMeta = 1)
        grpset.selectGroup("gnome-desktop")        
        grpset.selectGroup("development-tools")

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)
        BaseInstallClass.setDefaultPartitioning(self, id.partitions,
                                                CLEARPART_TYPE_LINUX)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
