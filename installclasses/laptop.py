import workstation
from translate import N_
import os

class InstallClass(workstation.InstallClass):
    name = N_("Laptop")
    pixmap = "laptop-support.png"

    sortPriority = 5000

    def __init__(self, expert):
	workstation.InstallClass.__init__(self, expert)
