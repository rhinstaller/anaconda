from installclass import BaseInstallClass
from installclass import FSEDIT_CLEAR_LINUX
from translate import N_
import os
import iutil

class InstallClass(BaseInstallClass):
    name = N_("Workstation")
    pixmap = "workstation.png"

    sortPriority = 1

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);

	if self.skipLilo:
	    dispatch.skipStep("bootloader")

	dispatch.skipStep("authentication")
	dispatch.skipStep("bootdisk", skip = 0)

    def setGroupSelection(self, comps):
	BaseInstallClass.__init__(self, comps)
	self.showGroups(comps, [ "KDE", ("GNOME", 1), "Games" ] )

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)
	self.setHostname(id, "localhost.localdomain")

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

	if expert:
	    self.skipLilo = 1
	else:
	    self.skipLilo = 0
