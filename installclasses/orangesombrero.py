#
# orangesombrero.py
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from installclass import BaseInstallClass
from rhpl.translate import N_,_
from constants import *
import os, types
import iutil

import installmethod
import yuminstall

import rpmUtils.arch

class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "orangesombrero"
    name = N_("_Orange Sombrero")
    _description = N_("The default installation of %s includes a set of "
                    "software applicable for general internet usage. "
                    "What additional tasks would you like your system "
                    "to include support for?")
    _descriptionFields = (productName,)
    sortPriority = 100000
    if productName.startswith("Red Hat Enterprise"):
        hidden = 1

    tasks = [(N_("Base System"), ["core", "base"])]

    repos = { "Additional Software from Fedora": (None, "http://mirrors.fedoraproject.org/mirrorlist?repo=%s&arch=%s" %(productVersion, rpmUtils.arch.getBaseArch())) }

    def getPackagePaths(self, uri):
        if not type(uri) == types.ListType:
            uri = [uri,]

        return {'Orange Sombrero': uri}

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
