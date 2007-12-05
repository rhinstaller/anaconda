from installclass import BaseInstallClass
from rhpl.translate import N_,_
from constants import *
import os
import iutil

import installmethod
import yuminstall

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
    if productName.startswith("Red Hat Enterprise"):
        hidden = 1

    tasks = [(N_("Office and Productivity"), ["graphics", "office", "games"]),
             (N_("Software Development"), ["development-libs", "development-tools", "gnome-software-development", "x-software-development"],),
             (N_("Web server"), ["web-server"])]

    repos = { "Additional Fedora Software": (None, "http://mirrors.fedoraproject.org/mirrorlist?repo=%s&arch=%s" %(productVersion, rpmUtils.arch.getBaseArch())) }

    def setInstallData(self, anaconda):
	BaseInstallClass.setInstallData(self, anaconda)

        if not anaconda.isKickstart:
            BaseInstallClass.setDefaultPartitioning(self, anaconda.id.partitions,
                                                    CLEARPART_TYPE_LINUX)

    def setGroupSelection(self, anaconda):
        grps = anaconda.backend.getDefaultGroups(anaconda)
        map(lambda x: anaconda.backend.selectGroup(x), grps)

    def setSteps(self, anaconda):
	BaseInstallClass.setSteps(self, anaconda);
	anaconda.dispatch.skipStep("partition")

    def getBackend(self, methodstr):
        if methodstr.startswith("livecd://"):
            import livecd
            return livecd.LiveCDCopyBackend
        return yuminstall.YumBackend

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)
