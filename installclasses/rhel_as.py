from installclass import BaseInstallClass
from rhpl.translate import N_, _
from constants import *
import os
import iutil

# custom installs are easy :-)
class InstallClass(BaseInstallClass):
    name = N_("Red Hat Enterprise Linux AS")
    pixmap = "server.png"
    description = N_("Red Hat Enterprise Linux AS")
    sortPriority = 100
    showLoginChoice = 1
    hidden = 1

    pkgstext = _("\tDesktop shell (GNOME)\n"
                 "\tAdministration Tools\n"
                 "\tServer Configuration Tools\n"
                 "\tWeb Server\n"
                 "\tWindows File Server (SMB)\n")

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
        dispatch.skipStep("desktopchoice", skip = 0)
        dispatch.skipStep("package-selection", skip = 1)

    def setGroupSelection(self, grpset, intf):
	BaseInstallClass.__init__(self, grpset)

        grpset.unselectAll()
        grpset.selectGroup("server", asMeta = 1)
        grpset.selectGroup("base-x")
        grpset.selectGroup("gnome-desktop")
        grpset.selectGroup("compat-arch-support", asMeta = 1, missingOk = 1)
        
    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)
        BaseInstallClass.setDefaultPartitioning(self, id.partitions,
                                                CLEARPART_TYPE_ALL)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
