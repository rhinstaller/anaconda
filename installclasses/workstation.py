from installclass import BaseInstallClass
from installclass import FSEDIT_CLEAR_LINUX
from translate import N_
import os
import iutil

class InstallClass(BaseInstallClass):
    name = N_("Workstation")
    pixmap = "workstation.png"

    sortPriority = 1

    def __init__(self, expert):
	BaseInstallClass.__init__(self)
	self.setGroups(["Workstation Common"])
	self.setHostname("localhost.localdomain")
	if not expert:
	    self.addToSkipList("lilo")
	self.addToSkipList("authentication")
	self.setMakeBootdisk(1)

        self.showgroups = [ "KDE",
                            (1, "GNOME"),
                            "Games" ]

	if os.uname ()[4] != 'sparc64':
	    self.addNewPartition('/boot', (32, -1, 0), (None,-1,0), (0,0))
	self.addNewPartition('/', (1100, -1, 1), (None, -1, 0), (0,0))
	self.setClearParts(FSEDIT_CLEAR_LINUX, 
#	    warningText = N_("You are about to erase any preexisting Linux "
#			     "installations on your system."))
	    warningText = N_("any preexisting Linux "
			     "installations on your system."))

        # 2.4 kernel requires more swap, so base amount we try to get
        # on amount of memory
        (minswap, maxswap) = iutil.swapSuggestion()
	self.addNewPartition('swap', (minswap, maxswap, 1), (None, -1, 0), (0,0))
