from installclass import BaseInstallClass
from installclass import FSEDIT_CLEAR_LINUX
from translate import N_
import os

class InstallClass(BaseInstallClass):
    name = N_("Laptop")
    pixmap = "laptop-support.png"

    sortPriority = 5000

    def __init__(self, expert):
	BaseInstallClass.__init__(self)
	self.setGroups(["Workstation Common"])
	self.setHostname("localhost.localdomain")
	if not expert:
	    self.addToSkipList("lilo")
	self.addToSkipList("authentication")
	self.setMakeBootdisk(1)

        self.showgroups = [ "KDE",
                            "GNOME",
                            "Games" ]

	if os.uname ()[4] != 'sparc64':
	    self.addNewPartition('/boot', (16, -1, 0), (None,-1,0), (0,0))
	self.addNewPartition('/', (700, -1, 1), (None, -1, 0), (0,0))
	self.addNewPartition('swap', (64, -1, 0), (None, -1, 0), (0,0))
	self.setClearParts(FSEDIT_CLEAR_LINUX, 
	    warningText = N_("You are about to erase any preexisting Linux "
			     "installations on your system."))
