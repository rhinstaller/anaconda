from installclass import BaseInstallClass
from installclass import FSEDIT_CLEAR_LINUX
from translate import N_
import os

# GNOME and KDE installs are derived from this
class Workstation(BaseInstallClass):

    def __init__(self, expert):
	BaseInstallClass.__init__(self)
	self.setHostname("localhost.localdomain")
	if not expert:
	    self.addToSkipList("lilo")
	self.addToSkipList("authentication")
	self.addToSkipList("package-selection")
	self.setMakeBootdisk(1)

	if os.uname ()[4] != 'sparc64':
	    self.addNewPartition('/boot', (16, -1, 0), (None,-1,0), (0,0))
	self.addNewPartition('/', (700, -1, 1), (None, -1, 0), (0,0))
	self.addNewPartition('swap', (64, -1, 0), (None, -1, 0), (0,0))
	self.setClearParts(FSEDIT_CLEAR_LINUX, 
	    warningText = N_("You are about to erase any preexisting Linux "
			     "installations on your system."))
