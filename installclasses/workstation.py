import personal_desktop
from rhpl.translate import N_
import os

class InstallClass(personal_desktop.InstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    name = N_("_Workstation")
    pixmap = "workstation.png"
    description = N_("This option installs a graphical desktop "
		     "environment with tools for software "
		     "development and system administration. ")

    sortPriority = 2
    showLoginChoice = 0

    def setGroupSelection(self, comps, intf):
        personal_desktop.InstallClass.setGroupSelection(self, comps, intf)
        comps["Emacs"].select()
        comps["GNOME Software Development"].select()
	comps["X Software Development"].select()
        comps["Development Tools"].select()

    def __init__(self, expert):
	personal_desktop.InstallClass.__init__(self, expert)
