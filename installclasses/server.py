from installclass import BaseInstallClass
from translate import *
from installclass import FSEDIT_CLEAR_ALL
import os
import iutil

class InstallClass(BaseInstallClass):

    name = N_("Server System")
    pixmap = "server.png"
    sortPriority = 10

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);

	if self.skipLilo:
	    dispatch.skipStep("bootloader")
	dispatch.skipStep("authentication")
	dispatch.skipStep("bootdisk", skip = 0)

    def setGroupSelection(self, comps):
	BaseInstallClass.__init__(self, comps)
	self.showGroups(comps, 
			  [ "KDE", 
			    ("GNOME", 0),
			    ("X Window System", 0),
			    "News Server",
                            "NFS Server",
                            "Web Server",
                            "SMB (Samba) Server",
                            "DNS Name Server" ])
	comps["Server"].select()

    def setInstallData(self, id):
	BaseInstallClass.setInstallData(self, id)
	self.setHostname(id, "localhost.localdomain")

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

	if expert:
	    self.skipLilo = 1
	else:
	    self.skipLilo = 0

