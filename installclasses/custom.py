from installclass import BaseInstallClass
from rhpl.translate import N_
from constants import *
import os
import iutil

# custom installs are easy :-)
class InstallClass(BaseInstallClass):
    name = N_("Custom")
    pixmap = "custom.png"
    showMinimal = 1
    showLoginChoice = 1
    description = N_("Select this installation type to gain complete "
		     "control over the installation process, including "
		     "software package selection and authentication "
		     "preferences.")
    sortPriority = 10000

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)
        BaseInstallClass.setDefaultPartitioning(self, id, CLEARPART_TYPE_LINUX)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
