from installclass import BaseInstallClass
from translate import N_

# custom installs are easy :-)
class InstallClass(BaseInstallClass):

    name = N_("Install Custom System")
    sortPriority = 10000

    def __init__(self, expert):
	BaseInstallClass.__init__(self)


