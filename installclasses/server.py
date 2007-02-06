from installclass import BaseInstallClass
from rhpl.translate import *
from constants import *
import os
import iutil

class InstallClass(BaseInstallClass):

    # name has underscore used for mnemonics, strip if you dont need it
    id = "server"
    name = N_("_Server")
    pixmap = "server.png"
    _description = N_("Select this installation type if you would like to "
		     "set up file sharing, print sharing, and Web services. "
		     "Additional services can also be enabled, and you "
		     "can choose whether or not to install a graphical "
		     "environment.")
    
    sortPriority = 10
    showLoginChoice = 1
    hidden = 1

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);

    def setGroupSelection(self, anaconda):
	BaseInstallClass.__init__(self, anaconda.backend)

        anaconda.backend.unselectAll()
        anaconda.backend.selectGroup("server", asMeta = 1)
        anaconda.backend.selectGroup("compat-arch-support", asMeta = 1, missingOk = 1)

    def setInstallData(self, anaconda):
	BaseInstallClass.setInstallData(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self, anaconda.id.partitions,
                                                CLEARPART_TYPE_ALL)

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
