import workstation
from translate import N_
import os
import pcmcia

class InstallClass(workstation.InstallClass):
    name = N_("Laptop")
    pixmap = "laptop-support.png"

    sortPriority = 5000

    if pcmcia.pcicType():
	default = 1

    def __init__(self, expert):
	workstation.InstallClass.__init__(self, expert)
        # XXX better interface for manipulating this stuff?
	self.groups.append("Laptop Support")
