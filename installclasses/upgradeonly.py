from installclass import BaseInstallClass
from translate import N_
import os

class InstallClass(BaseInstallClass):
    name = N_("upgradeonly")
    pixmap = ""
    hidden = 1
    sortPriority = 1

    def __init__(self, expert):
	BaseInstallClass.__init__(self)

        self.installType = "upgrade"

	self.addToSkipList("bootdisk")
	self.addToSkipList("language")
	self.addToSkipList("keyboard")
        self.addToSkipList("welcome")
        self.addToSkipList("package-selection")
        self.addToSkipList("confirm-install")
        self.addToSkipList("custom-upgrade")
        self.addToSkipList("network")
