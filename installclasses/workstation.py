import personal_desktop
from rhpl.translate import N_, _
import os

class InstallClass(personal_desktop.InstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "workstation"
    name = N_("_Workstation")
    pixmap = "workstation.png"
    description = N_("This option installs a graphical desktop "
		     "environment with tools for software "
		     "development and system administration. ")

    pkgstext = N_("\tDesktop shell (GNOME)\n"
                  "\tOffice suite (OpenOffice.org)\n"
                  "\tWeb browser (Mozilla) \n"
                  "\tEmail (Evolution)\n"
                  "\tInstant messaging\n"
                  "\tSound and video applications\n"
                  "\tGames\n"
                  "\tSoftware Development Tools\n"
                  "\tAdministration Tools\n")
    

    sortPriority = 2
    showLoginChoice = 0

    def setGroupSelection(self, grpset, intf):
        personal_desktop.InstallClass.setGroupSelection(self, grpset, intf)
        grpset.selectGroup("emacs")
        grpset.selectGroup("gnome-software-development")
	grpset.selectGroup("x-software-development")
        grpset.selectGroup("development-tools")

    def __init__(self, expert):
	personal_desktop.InstallClass.__init__(self, expert)
