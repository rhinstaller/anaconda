import personal_desktop
from rhpl.translate import N_
import os

class InstallClass(personal_desktop.InstallClass):
    showLoginChoice = 0
    name = N_("Workstation")
    pixmap = "workstation.png"
    description = N_("This option installs a graphical desktop "
		     "environment with tools for software "
		     "development and system administration. ")

    sortPriority = 2

    def setGroupSelection(self, comps, intf):
        personal_desktop.InstallClass.setGroupSelection(self, comps, intf)
        comps["Emacs"].select()
        comps["GNOME Software Development"].select()
	comps["X Software Development"].select()
        comps["Development Tools"].select()

    def __init__(self, expert):
	personal_desktop.InstallClass.__init__(self, expert)
