from installclass import BaseInstallClass
from installclass import FSEDIT_CLEAR_LINUX
from translate import N_
import os
import iutil

# custom installs are easy :-)
class InstallClass(BaseInstallClass):

    name = N_("Custom System")
    pixmap = "custom.png"
    
    sortPriority = 10000

    def __init__(self, expert):
	BaseInstallClass.__init__(self)

	if os.uname ()[4] != 'sparc64':
	    self.addNewPartition('/boot', (32, -1, 0), (None,-1,0), (0,0))
	self.addNewPartition('/', (700, -1, 1), (None, -1, 0), (0,0))
	self.setClearParts(FSEDIT_CLEAR_LINUX, 
	    warningText = N_("You are about to erase any preexisting Linux "
			     "installations on your system."))

        # 2.4 kernel requires more swap, so base amount we try to get
        # on amount of memory
        (minswap, maxswap) = iutil.swapSuggestion()
	self.addNewPartition('swap', (minswap, maxswap, 1), (None, -1, 0), (0,0))

