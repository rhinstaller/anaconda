from installclass import BaseInstallClass
import rhpl
from rhpl.translate import N_
from constants import *
import os
import iutil
import types

import logging
log = logging.getLogger("anaconda")

# custom installs are easy :-)
class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "rhel"
    name = N_("Red Hat Enterprise Linux")
    description = N_("The default installation of %s includes a set of "
                     "software applicable for general internet usage. "
                     "What additional tasks would you like your system "
                     "to include support for?") %(productName,)
    sortPriority = 10000
    allowExtraRepos = False
    if not productName.startswith("Red Hat Enterprise"):
        hidden = 1

    tasks = [(N_("Office and Productivity"), ["graphics", "office", "games", "sound-and-video"]),
             (N_("Software Development"), ["development-libs", "development-tools", "gnome-software-development", "x-software-development"],),
             (N_("Web server"), ["web-server"])]

    def setInstallData(self, anaconda):
	BaseInstallClass.setInstallData(self, anaconda)

        if not anaconda.isKickstart:
            BaseInstallClass.setDefaultPartitioning(self, anaconda.id.partitions,
                                                    CLEARPART_TYPE_LINUX)

    def setGroupSelection(self, anaconda):
        grps = anaconda.backend.getDefaultGroups(anaconda)
        map(lambda x: anaconda.backend.selectGroup(x), grps)

    def setSteps(self, anaconda):
        dispatch = anaconda.dispatch
	BaseInstallClass.setSteps(self, dispatch);
	dispatch.skipStep("partition")
	dispatch.skipStep("regkey", skip = 0)        

    # for rhel, we're putting the metadata under productpath
    def getPackagePaths(self, uri):
        rc = {}
        for (name, path) in self.repopaths.items():
            if type(uri) == types.ListType:
                lst = []

                for i in uri:
                    lst.append("%s/%s" % (i, path))

                rc[name] = lst
            else:
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
        # if V is in the key, add Virtualization. etc
        if productPath == "Server" and rhpl.getArch() in ("i386", "x86_64", "ia64"):
            if key.find("C") != -1:
                self.repopaths["cluster"] = "Cluster"
                log.info("Adding Cluster option")
            if key.find("S") != -1:
                self.repopaths["cs"] = "ClusterStorage"
                log.info("Adding ClusterStorage option")

        if productPath == "Client":
#             if key.find("D") != -1:
#                 self.repopaths["desktop"] = "Desktop"
#                 log.info("Adding Desktop option")
            if key.find("W") != -1:
                self.repopaths["desktop"] = "Workstation"
                log.info("Adding Workstation option")

        if rhpl.getArch() in ("i386", "x86_64", "ia64"):
            if key.find("V") != -1:
                self.repopaths["virt"] = "VT"
                log.info("Adding Virtualization option")

        self.regkey = key

    def getMethod(self, methodstr):
        return BaseInstallClass.getMethod(self, methodstr)

    def getBackend(self, methodstr):
        return yuminstall.YumBackend

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

        self.repopaths = { "base": "%s" %(productPath,) }
        self.regkey = None
