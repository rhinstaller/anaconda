import workstation
from rhpl.translate import N_
import os

class InstallClass(workstation.InstallClass):
    name = N_("Developer Workstation")
    pixmap = "workstation.png"
    description = N_("Select this "
		     "installation type to install a graphical desktop "
		     "environment which includes tools for software "
		     "development.")

    sortPriority = 2

    def setGroupSelection(self, comps):
	workstation.InstallClass.__init__(self, comps)
        comps["Emacs"].select()
        comps["GNOME Development"].select()
	comps["X Development"].select()

    def __init__(self, expert):
	workstation.InstallClass.__init__(self, expert)
