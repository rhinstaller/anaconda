from installclass import BaseInstallClass
from rhpl.translate import N_
from constants import *
import os
import iutil

# custom installs are easy :-)
class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "custom"
    name = N_("_Fedora")
    pixmap = "custom.png"
    description = N_("Select this installation type to gain complete "
		     "control over the installation process, including "
		     "software package selection and partitioning.")
    sortPriority = 10000
    showLoginChoice = 1
    showMinimal = 1

    tasks = [(N_("Office and Productivity"), ["graphics", "office", "games", "sound-and-video"]),
             (N_("Software Development"), ["development-libs", "development-tools", "gnome-software-development", "x-software-development"],),
             (N_("Web server"), ["web-server"])]

    def setInstallData(self, anaconda):
	BaseInstallClass.setInstallData(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self, anaconda.id.partitions,
                                                CLEARPART_TYPE_LINUX)

    def setGroupSelection(self, anaconda):
        grps = anaconda.backend.getDefaultGroups()
        map(lambda x: anaconda.backend.selectGroup(x), grps)

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
	dispatch.skipStep("partition")

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
