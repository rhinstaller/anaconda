from installclass import BaseInstallClass
from translate import *
from installclass import FSEDIT_CLEAR_ALL
import os
import iutil

class InstallClass(BaseInstallClass):

    name = N_("Server System")
    pixmap = "server.png"
    sortPriority = 10

    def __init__(self, expert):
	BaseInstallClass.__init__(self)
	self.setGroups(["Server"])
	self.setHostname("localhost.localdomain")
	if not expert:
	    self.addToSkipList("lilo")
	self.addToSkipList("authentication")
	self.setMakeBootdisk(1)

        self.showgroups = [ "KDE", 
			    (0, "GNOME"),
                            (0, "X Window System"),
			    "News Server",
                            "NFS Server",
                            "Web Server",
                            "SMB (Samba) Server",
                            "DNS Name Server" ]

	if os.uname ()[4] != 'sparc64':
	    self.addNewPartition('/boot', (32, -1, 0), (None, -1, 0), (0,0))
	self.addNewPartition('/', (256, -1, 0), (None, -1, 0), (0,0))
	self.addNewPartition('/usr', (512, -1, 1), (None, -1, 0), (0,0))
	self.addNewPartition('/var', (256, -1, 0), (None, -1, 0), (0,0))
	self.addNewPartition('/home',(512, -1, 1), (None, -1, 0), (0,0))
	self.setClearParts(FSEDIT_CLEAR_ALL, 
	    warningText = N_("Automatic partitioning will erase ALL DATA on your hard "
			     "drive to make room for your Linux installation."))

#	self.addNewPartition('swap', (64, 256, 1), (None, -1, 0), (0,0))

        # 2.4 kernel requires more swap, so base amount we try to get
        # on amount of memory
        (minswap, maxswap) = iutil.swapSuggestion()
	self.addNewPartition('swap', (minswap, maxswap, 1), (None, -1, 0), (0,0))
