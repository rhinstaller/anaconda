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
from meh.filer import *
from flags import flags
import os
import types
import iutil

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import installmethod
import yuminstall

import rpmUtils.arch

class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "rhel"
    name = N_("Red Hat Enterprise Linux")
    _description = N_("The default installation of %s is a minimal install. "
                      "You can optionally select a different set of software "
                      "now.")
    _descriptionFields = (productName,)
    sortPriority = 10000
    if not productName.startswith("Red Hat Enterprise"):
        hidden = 1

    bootloaderTimeoutDefault = 5

    tasks = [(N_("Minimal"), ["core"]),
             (N_("Desktop"),
              ["backup-client", "base", "compat-libraries", "console-internet",
               "debugging", "directory-client", "fonts",
               "legacy-unix", "core", "network-file-system-client",
               "network-tools", "print-client", "virtualization", "vpn",
               "basic-desktop", "desktop-debugging", "desktop-platform",
               "general-desktop", "graphical-admin-tools", "input-methods",
               "legacy-x", "x11","office-suite", "graphics",
               "virtualization-client"]),
             (N_("Software Development"),
              ["backup-client", "base", "compat-libraries", "console-internet",
               "debugging", "directory-client", "fonts",
               "legacy-unix", "core", "network-file-system-client",
               "network-tools", "print-client", "virtualization", "vpn",
               "basic-desktop", "desktop-debugging", "desktop-platform",
               "general-desktop", "graphical-admin-tools", "input-methods",
               "legacy-x", "x11", "virtualization-client", "emacs", "tex",
               "desktop-platform-devel", "development", "eclipse",
               "server-platform-devel", "technical-writing"]),
             (N_("Web Server"),
              ["backup-client", "base", "compat-libraries", "console-internet",
               "debugging", "directory-client", "legacy-unix",
               "core", "network-file-system-client", "network-tools",
               "web-server", "additional-web-server", "server-platform",
               "mysql", "php", "postgresql", "rails", "turbogears",
               "system-admin-tools"]),
             (N_("Advanced Server"),
              ["backup-client", "base", "compat-libraries", "console-internet",
               "debugging", "directory-client", "legacy-unix",
               "core", "network-file-system-client", "network-tools",
               "web-server", "server-platform",
               "mysql", "php", "postgresql", "rails", "turbogears",
               "cifs-file-server", "clustering", "clustered-storage",
               "directory-server", "mail-server", "ftp-server",
               "network-server", "nfs-file-server", "print-server",
               "system-admin-tools"])]

    bugFiler = BugzillaFiler("https://bugzilla.redhat.com/xmlrpc.cgi",
                             "https://bugzilla.redhat.com/",
                             product.productVersion, product.productName)

    def getPackagePaths(self, uri):
        if not type(uri) == types.ListType:
            uri = [uri,]

        return {'Installation Repo': uri}

    def configure(self, anaconda):
        BaseInstallClass.configure(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self,
                                                anaconda.storage,
                                                anaconda.platform)

    def setGroupSelection(self, anaconda):
        BaseInstallClass.setGroupSelection(self, anaconda)
        map(lambda x: anaconda.backend.selectGroup(x), ["core"])

    def setSteps(self, anaconda):
        BaseInstallClass.setSteps(self, anaconda)
        anaconda.dispatch.skipStep("partition")

    def getBackend(self):
        if flags.livecdInstall:
            import livecd
            return livecd.LiveCDCopyBackend
        else:
            return yuminstall.YumBackend

    def productMatches(self, oldprod):
        if oldprod is None:
            return False

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
