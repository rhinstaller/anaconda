from workstation import Workstation
from translate import N_

class InstallClass(Workstation):

    name = N_("Install GNOME Workstation")
    pixmap = "gnome-workstation.png"
    
    sortPriority = 1

    def __init__(self, expert):
	Workstation.__init__(self, expert)
        self.desktop = "GNOME"
	self.setGroups(["GNOME Workstation"])

