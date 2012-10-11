#
# fedora.py
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

from pyanaconda.installclass import BaseInstallClass
from pyanaconda.constants import *
from pyanaconda.product import *
from pyanaconda import network
from pyanaconda import isys

import os, types
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

from decimal import Decimal

class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "fedora"
    name = N_("_Fedora")
    _description = N_("The default installation of %s includes a set of "
                      "software applicable for general internet usage. "
                      "You can optionally select a different set of software "
                      "now.")
    _descriptionFields = (productName,)
    sortPriority = 10000
    if productName.startswith("Red Hat Enterprise"):
        hidden = 1

    tasks = [(N_("Graphical Desktop"),
              ["admin-tools", "base", "base-x", "core", "editors", "fonts",
               "games", "gnome-desktop", "graphical-internet", "graphics",
               "hardware-support", "input-methods", "java", "office",
               "printing", "sound-and-video", "text-internet"]),
             (N_("Software Development"),
              ["base", "base-x", "core", "development-libs",
               "development-tools", "editors", "fonts", "gnome-desktop",
               "gnome-software-development", "graphical-internet", "graphics",
               "hardware-support", "input-methods", "java", "sound-and-video", "text-internet",
               "x-software-development"]),
             (N_("Web Server"),
              ["admin-tools", "base", "base-x", "core", "editors",
               "gnome-desktop", "graphical-internet", "hardware-support",
               "java", "text-internet", "web-server"]),
             (N_("Minimal"), ["core"])]

    _l10n_domain = "anaconda"

    efi_dir = "fedora"

    def getPackagePaths(self, uri):
        if not type(uri) == types.ListType:
            uri = [uri,]

        return {'Installation Repo': uri}

    def configure(self, anaconda):
	BaseInstallClass.configure(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self, anaconda.storage)

    def setGroupSelection(self, anaconda):
        BaseInstallClass.setGroupSelection(self, anaconda)
        map(lambda x: anaconda.backend.selectGroup(x), ["core"])

    def productMatches(self, oldprod):
        if oldprod is None:
            return False

        if oldprod.startswith(productName):
            return True

        productUpgrades = {
                "Fedora Core": ("Red Hat Linux", ),
                "Fedora": ("Fedora Core", )
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
        if oldver is None:
            return False

        try:
            oldVer = Decimal(oldver)
            # Trim off any "-Alpha" or "-Beta".
            newVer = Decimal(productVersion.split('-')[0])
        except Exception:
            return True

        # This line means we do not support upgrading from anything older
        # than two versions ago!
        return newVer >= oldVer and newVer - oldVer <= 2

    def setNetworkOnbootDefault(self, ksdata):
        # if something's already enabled, we can just leave the config alone
        for devName in network.getDevices():
            if not isys.isWirelessDevice(devName) and \
               network.get_ifcfg_value(devName, "ONBOOT", ROOT_PATH) == "yes":
                return

        # the default otherwise: bring up the first wired netdev with link
        for devName in network.getDevices():
            if (not isys.isWirelessDevice(devName) and
                isys.getLinkStatus(devName)):
                dev = network.NetworkDevice(ROOT_PATH + network.netscriptsDir, devName)
                dev.loadIfcfgFile()
                dev.set(('ONBOOT', 'yes'))
                dev.writeIfcfgFile()
                for nd in ksdata.network.network:
                    if nd.device == dev.iface:
                        nd.onboot = True
                        break
                break

    def __init__(self):
	BaseInstallClass.__init__(self)
