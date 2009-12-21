# this is the prototypical class for upgrades
#
# Copyright 2001-2004 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
from installclass import getBaseInstallClass
from rhpl.translate import N_, _

import os
import iutil
import rhpl

baseclass = getBaseInstallClass()

class InstallClass(baseclass):
    name = N_("Upgrade Existing System")
    pixmap = "upgrade.png"
    sortPriority = 999999

    parentClass = ( _("Upgrade"), "upgrade.png" )

    def requiredDisplayMode(self):
        return 't'

    def setSteps(self, dispatch):
	dispatch.setStepList(
		    "language",
		    "keyboard",
		    "welcome",
		    "installtype",
                    "findrootparts",
		    "findinstall",
                    "partitionobjinit",
                    "upgrademount",
                    "upgrademigfind",
                    "upgrademigratefs",
                    "upgradecontinue",
                    "reposetup",
                    "upgbootloader",
                    "reipl",
                    "checkdeps",
		    "dependencies",
		    "confirmupgrade",
                    "postselection",
		    "install",
                    "migratefilesystems",
                    "preinstallconfig",
                    "installpackages",
                    "postinstallconfig",
                    "instbootloader",
                    "dopostaction",
                    "writeregkey",
                    "methodcomplete",
                    "copylogs",
		    "complete"
		)

        if rhpl.getArch() != "i386" and rhpl.getArch() != "x86_64":
            dispatch.skipStep("bootloader")
            dispatch.skipStep("bootloaderadvanced")

        if rhpl.getArch() != "i386" and rhpl.getArch() != "x86_64":
            dispatch.skipStep("upgbootloader")            

    def setInstallData(self, anaconda):
        baseclass.setInstallData(self, anaconda)
        anaconda.id.setUpgrade(True)
    
    def __init__(self, expert):
	baseclass.__init__(self, expert)
