from installclass import BaseInstallClass
from rhpl.translate import N_
from constants import *
import os
import iutil

# custom installs are easy :-)
class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "custom"
    name = N_("_Custom")
    pixmap = "custom.png"
    _description = N_("Select this installation type to gain complete "
		     "control over the installation process, including "
		     "software package selection and partitioning.")
    sortPriority = 10000
    showLoginChoice = 1
    showMinimal = 1
    hidden = 1

    def setInstallData(self, anaconda):
	BaseInstallClass.setInstallData(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self, anaconda.id.partitions,
                                                CLEARPART_TYPE_LINUX)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
