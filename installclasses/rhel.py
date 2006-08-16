from installclass import BaseInstallClass
import rhpl
from rhpl.translate import N_
from constants import *
import os
import iutil

# custom installs are easy :-)
class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "custom"
    name = N_("Red Hat Enterprise Linux")
    pixmap = "custom.png"
    description = N_("Select this installation type to gain complete "
		     "control over the installation process, including "
		     "software package selection and partitioning.")
    sortPriority = 10000
    showLoginChoice = 1
    showMinimal = 1
    if not productName.startswith("Red Hat Enterprise"):
        hidden = 1

    tasks = [(N_("Office and Productivity"), ["graphics", "office", "games", "sound-and-video"]),
             (N_("Software Development"), ["development-libs", "development-tools", "gnome-software-development", "x-software-development"],),
             (N_("Web server"), ["web-server"])]

    def setInstallData(self, anaconda):
	BaseInstallClass.setInstallData(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self, anaconda.id.partitions,
                                                CLEARPART_TYPE_LINUX)

    def setGroupSelection(self, anaconda):
        grps = anaconda.backend.getDefaultGroups()
        map(lambda x: anaconda.backend.selectGroup(x), grps)

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
	dispatch.skipStep("partition")
	dispatch.skipStep("regkey", skip = 0)        

    # for rhel, we're putting the metadata under productpath
    def getPackagePaths(self, uri):
        rc = {}
        for (name, path) in self.repopaths.items():
            rc[name] = "%s/%s" %(uri, path)
        return rc

    def handleRegKey(self, key, intf):
#         if key is None or len(key) == 0:
#             intf.messageWindow(_("Registration Key Required"),
#                                _("A registration key is required to "
#                                  "install %s.  Please contact your support "
#                                  "representative if you did not receive a "
#                                  "key with your product." %(productName,)),
#                                type = "ok", custom_icon="error")
#             raise NoKeyError

        # simple and stupid for now... if C is in the key, add Clustering
        # if V is in the key, add Virtualization.
        if productPath == "Server" and rhpl.getArch() in ("i386", "x86_64", "ia64"):
            if key.find("C") != -1:
                self.repopaths["cluster"] = "Cluster"
            if key.find("S") != -1:
                self.repopaths["cs"] = "ClusterStorage"

        if productPath == "Client":
            if key.find("D") != -1:
                self.repopaths["desktop"] = "Desktop"
            if key.find("W") != -1:
                self.repopaths["desktop"] = "Workstation"

        if rhpl.getArch() in ("i386", "x86_64", "ia64"):
            if key.find("V") != -1:
                self.repopaths["virt"] = "VT"

        self.regkey = key

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

        self.repopaths = { "base": "%s" %(productPath,) }
        self.regkey = None
