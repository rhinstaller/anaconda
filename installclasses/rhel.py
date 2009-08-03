from installclass import BaseInstallClass
import rhpl
from rhpl.translate import N_,_
from constants import *
from flags import flags
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
    _description = N_("The default installation of %s includes a set of "
                     "software applicable for general internet usage. "
                     "What additional tasks would you like your system "
                     "to include support for?")
    _descriptionFields = (productName,)
    sortPriority = 10000
    allowExtraRepos = False
    if 0: # not productName.startswith("Red Hat Enterprise"):
        hidden = 1

    taskMap = {'client'        : [(N_("Office"), ["office"]),
                                  (N_("Multimedia"), ["graphics", 
                                                      "sound-and-video"])],
               'server'        : [(N_("Software Development"), 
                                   ["development-libs", "development-tools",
                                    "gnome-software-development", 
                                    "x-software-development"],),
                                  (N_("Web server"), ["web-server"])],
               'workstation'   : [(N_("Software Development"), 
                                   ["development-libs", "development-tools",
                                    "gnome-software-development", 
                                    "x-software-development"],)],
               'vt'            : [(N_("Virtualization"), ["xen"])],
               'cluster'       : [(N_("Clustering"), ["clustering"])],
               'clusterstorage': [(N_("Storage Clustering"), 
                                   ["cluster-storage"])]
             }

    instkeyname = N_("Installation Number")
    instkeydesc = N_("Would you like to enter an Installation Number "
                     "(sometimes called Subscription Number) now? This feature "
                     "enables the installer to access any extra components "
                     "included with your subscription.  If you skip this step, "
                     "additional components can be installed manually later.\n\n"
                     "See http://www.redhat.com/InstNum/ for more information.")
    skipkeytext = N_("If you cannot locate the Installation Number, consult "
                     "http://www.redhat.com/InstNum/")

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
            if not type(uri) == types.ListType:
                uri = [uri,]
            if not type(path) == types.ListType:
                path = [path,]

            lst = []
            for i in uri:
                for p in path:
                    lst.append("%s/%s" % (i, p))

            rc[name] = lst

        log.info("package paths is %s" %(rc,))
        return rc

    def handleRegKey(self, key, intf, interactive = True):
        self.repopaths = { "base": "%s" %(productPath,) }
        self.tasks = self.taskMap[productPath.lower()]
        self.installkey = key

        try:
            inum = instnum.InstNum(key)
        except Exception, e:
            if True or not BETANAG: # disable hack keys for non-beta
                # make sure the log is consistent
                log.info("repopaths is %s" %(self.repopaths,))
                raise
            else:
                inum = None

        if inum is not None:
            # make sure the base products match
            if inum.get_product_string().lower() != productPath.lower():
                raise ValueError, "Installation number incompatible with media"

            for name, path in inum.get_repos_dict().items():
                # virt is only supported on i386/x86_64.  so, let's nuke it
                # from our repo list on other arches unless you boot with
                # 'linux debug'
                if name.lower() == "virt" and ( \
                        rhpl.getArch() not in ("x86_64","i386","ia64")
                        and not flags.debug):
                    continue
                self.repopaths[name.lower()] = path
                log.info("Adding %s repo" % (name,))

        else:
            key = key.upper()
            # simple and stupid for now... if C is in the key, add Clustering
            # if V is in the key, add Virtualization. etc
            if key.find("C") != -1:
                self.repopaths["cluster"] = "Cluster"
                log.info("Adding Cluster option")
            if key.find("S") != -1:
                self.repopaths["clusterstorage"] = "ClusterStorage"
                log.info("Adding ClusterStorage option")
            if key.find("W") != -1:
                self.repopaths["workstation"] = "Workstation"
                log.info("Adding Workstation option")
            if key.find("V") != -1:
                self.repopaths["virt"] = "VT"
                log.info("Adding Virtualization option")

        for repo in self.repopaths.values():
            if not self.taskMap.has_key(repo.lower()):
                continue

            for task in self.taskMap[repo.lower()]:
                if task not in self.tasks:
                    self.tasks.append(task)
        self.tasks.sort()

        log.info("repopaths is %s" %(self.repopaths,))

    def __init__(self, expert):
	BaseInstallClass.__init__(self, expert)

        self.repopaths = { "base": "%s" %(productPath,) }

        # minimally set up tasks in case no key is provided
        self.tasks = self.taskMap[productPath.lower()]

