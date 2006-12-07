from installclass import BaseInstallClass
import rhpl
from rhpl.translate import N_,_
from constants import *
import os
import iutil
import types
try:
    import instnum
except ImportError:
    instnum = None

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
    if 0: # not productName.startswith("Red Hat Enterprise"):
        hidden = 1

    tasks = [(N_("Office"), ["office"]),
             (N_("Multimedia"), ["graphics", "sound-and-video"]),
             (N_("Software Development"), ["development-libs", "development-tools", "gnome-software-development", "x-software-development"],),
             (N_("Web server"), ["web-server"]),
             (N_("Virtualization"), ["virtualization"]),
             (N_("Clustering"), ["clustering"]),
             (N_("Storage Clustering"), ["cluster-storage"])
             ]

    instkeyname = _("Installation Number")
    instkeydesc = _("To install the full set of supported packages included "
                    "in your subscription, please enter your Installation "
                    "Number")
    skipkeytext = _("If you're unable to locate the Installation Number, "
                    "consult http://www.redhat.com/apps/support/in.html.\n\n"
                    "If you skip:\n"
                    "* You may not get access to the full set of "
                    "packages included in your subscription.\n"
                    "* It may result in an unsupported/uncertified "
                    "installation of Red Hat Enterprise Linux.\n"
                    "* You will not get software and security updates "
                    "for packages not included in your subscription.")
 

    def setInstallData(self, anaconda):
	BaseInstallClass.setInstallData(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self, anaconda.id.partitions,
                                                CLEARPART_TYPE_LINUX)

    def setGroupSelection(self, anaconda):
        grps = anaconda.backend.getDefaultGroups(anaconda)
        map(lambda x: anaconda.backend.selectGroup(x), grps)

    def setSteps(self, dispatch):
	BaseInstallClass.setSteps(self, dispatch);
	dispatch.skipStep("partition")
	dispatch.skipStep("regkey", skip = 0)        

    # for rhel, we're putting the metadata under productpath
    def getPackagePaths(self, uri):
        rc = {}
        for (name, path) in self.repopaths.items():
            lst = []
            if type(uri) == types.ListType:
                for i in uri:
                    for p in path:
                        lst.append("%s/%s" % (i, p))
            else:
                for p in path:
                    lst.append("%s/%s" % (uri, p))

            rc[name] = lst

        log.info("package paths is %s" %(rc,))
        return rc

    def handleRegKey(self, key, intf, interactive = True):
        try:
            inum = instnum.InstNum(key)
        except Exception, e:
            if not BETANAG: # disable hack keys for non-beta
                raise
            else:
                inum = None

        if inum is not None:
            for name, path in inum.get_repos_dict().items():
                self.repopaths[name.lower()] = path
                log.info("Adding %s repo" % (path,))

            # if we've got a real installation number, use it to base
            # what tasks we show.  this is pretty ugly, but alas.
            tasks = []
            if inum.get_product_string() == "client":
                tasks += [(N_("Office"), ["office"]),
                          (N_("Multimedia"), ["graphics", "sound-and-video"])]
            elif inum.get_product_string() == "server":
                tasks.append( (N_("Web server"), ["web-server"]) )
                
            if "VT" in inum.get_repos():
                tasks.append( (N_("Virtualization"), ["virtualization"]) )
            if "Cluster" in inum.get_repos():
                tasks.append( (N_("Clustering"), ["clustering"]) )
            if "ClusterStorage" in inum.get_repos():
                tasks.append( (N_("Storage Clustering"), ["cluster-storage"]) )

            if inum.get_product_string() == "server" or "Workstation" in inum.get_repos():
                tasks.append( (N_("Software Development"),
                               ["development-libs", "development-tools",
                                "gnome-software-development",
                                "x-software-development"],) )
            self.tasks = tasks
            
        else:
            key = key.upper()
            # simple and stupid for now... if C is in the key, add Clustering
            # if V is in the key, add Virtualization. etc
            if key.find("C") != -1:
                self.repopaths["cluster"] = ["Cluster"]
                log.info("Adding Cluster option")
            if key.find("S") != -1:
                self.repopaths["clusterstorage"] = ["ClusterStorage"]
                log.info("Adding ClusterStorage option")
            if key.find("W") != -1:
                self.repopaths["workstation"] = ["Workstation"]
                log.info("Adding Workstation option")
            if key.find("V") != -1:
                self.repopaths["virt"] = ["VT"]
                log.info("Adding Virtualization option")

        log.info("repopaths is %s" %(self.repopaths,))

        self.installkey = key

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

        self.repopaths = { "base": [ "%s" %(productPath,) ] }
