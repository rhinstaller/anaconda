import workstation
from translate import N_
import os
import pcmcia

class InstallClass(workstation.InstallClass):
    name = N_("Laptop")
    pixmap = "laptop-class.png"

    sortPriority = 5000
    arch = 'i386'

    def setGroupSelection(self, comps):
	workstation.InstallClass.setGroupSelection(self, comps)
	comps["Laptop Support"].select()

    if pcmcia.pcicType():
	default = 1

    def __init__(self, expert):
	workstation.InstallClass.__init__(self, expert)
