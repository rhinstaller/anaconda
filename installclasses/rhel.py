#
# rhel.py
#
# Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from installclass import BaseInstallClass
from constants import *
from product import *
from filer import *
from flags import flags
import os
import iutil
import types
import yuminstall
try:
    import instnum
except ImportError:
    instnum = None

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

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
    if not productName.startswith("Red Hat Enterprise"):
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
               'vt'            : [(N_("Virtualization"), ["virtualization"])],
               'cluster'       : [(N_("Clustering"), ["clustering"])],
               'clusterstorage': [(N_("Storage Clustering"), 
                                   ["cluster-storage"])]
             }

    instkeyname = N_("Installation Number")
    instkeydesc = N_("To install the full set of supported packages included "
                    "in your subscription, please enter your Installation "
                    "Number")
    skipkeytext = N_("If you're unable to locate the Installation Number, "
                    "consult http://www.redhat.com/apps/support/in.html.\n\n"
                    "If you skip:\n"
                    "* You may not get access to the full set of "
                    "packages included in your subscription.\n"
                    "* It may result in an unsupported/uncertified "
                    "installation of Red Hat Enterprise Linux.\n"
                    "* You will not get software and security updates "
                    "for packages not included in your subscription.")

    bugFiler = BugzillaFiler(bugUrl="https://bugzilla.redhat.com/xmlrpc.cgi")

    def setInstallData(self, anaconda):
	BaseInstallClass.setInstallData(self, anaconda)
        if not anaconda.isKickstart:
            BaseInstallClass.setDefaultPartitioning(self, 
                                                    anaconda.id.partitions,
                                                    CLEARPART_TYPE_LINUX)

    def setSteps(self, anaconda):
        dispatch = anaconda.dispatch
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
                if name.lower() == "virt" and \
                        (not iutil.isX86() and not flags.debug):
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

    def getBackend(self):
        return yuminstall.YumBackend

    def productMatches(self, oldprod):
        if oldprod.startswith(productName):
            return True

        productUpgrades = {
            "Red Hat Enterprise Linux AS": ("Red Hat Linux Advanced Server", ),
            "Red Hat Enterprise Linux WS": ("Red Hat Linux Advanced Workstation",),
            # FIXME: this probably shouldn't be in a release...
            "Red Hat Enterprise Linux": ("Red Hat Linux Advanced Server",
                                         "Red Hat Linux Advanced Workstation",
                                         "Red Hat Enterprise Linux AS",
                                         "Red Hat Enterprise Linux ES",
                                         "Red Hat Enterprise Linux WS"),
            "Red Hat Enterprise Linux Server": ("Red Hat Enterprise Linux AS",
                                                "Red Hat Enterprise Linux ES",
                                                "Red Hat Enterprise Linux WS",
                                                "Red Hat Enterprise Linux"),
            "Red Hat Enterprise Linux Client": ("Red Hat Enterprise Linux WS",
                                                "Red Hat Enterprise Linux Desktop",
                                                "Red Hat Enterprise Linux"),
        }

        if productUpgrades.has_key(productName):
            acceptable = productUpgrades[productName]
        else:
            acceptable = ()

        for p in acceptable:
            if oldprod.startswith(p):
                return True

        return False

    def versionMatches(self, oldver):
        return True

    def __init__(self):
	BaseInstallClass.__init__(self)

        self.repopaths = { "base": "%s" %(productPath,) }

        # minimally set up tasks in case no key is provided
        self.tasks = self.taskMap[productPath.lower()]

