from installclass import BaseInstallClass
from rhpl.translate import N_,_
from constants import *
import os
import iutil

import rpmUtils.arch

class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "fedora"
    name = N_("_Fedora")
    _description = N_("The default installation of %s includes a set of "
                    "software applicable for general internet usage. "
                    "What additional tasks would you like your system "
                    "to include support for?") 
    _descriptionFields = (productName,)
    sortPriority = 10000
    if productName.startswith("Red Hat Enterprise") or 1:
        hidden = 1

    tasks = [(N_("Office and Productivity"), ["graphics", "office", "games", "sound-and-video"]),
             (N_("Software Development"), ["development-libs", "development-tools", "gnome-software-development", "x-software-development"],),
             (N_("Web server"), ["web-server"])]

    repos = { "Fedora Extras": ("http://download.fedora.redhat.com/pub/fedora/linux/extras/development/%s" %(rpmUtils.arch.getBaseArch() ,), None) }

    def setInstallData(self, anaconda):
	BaseInstallClass.setInstallData(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self, anaconda.id.partitions,
                                                CLEARPART_TYPE_LINUX)

    def setGroupSelection(self, anaconda):
        grps = anaconda.backend.getDefaultGroups(anaconda)
        map(lambda x: anaconda.backend.selectGroup(x), grps)

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
	dispatch.skipStep("partition")

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
