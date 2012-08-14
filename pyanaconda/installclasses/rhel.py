#
# rhel.py
#
# Copyright (C) 2010  Red Hat, Inc.  All rights reserved.
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
import types

class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "rhel"
    name = N_("Red Hat Enterprise Linux")
    _description = N_("The default installation of %s is a minimum install. "
                     "You can optionally select a different set of software "
                     "now.")
    _descriptionFields = (productName,)
    sortPriority = 10000
    hidden = 1

    bootloaderTimeoutDefault = 5
    bootloaderExtraArgs = []

    tasks = [(N_("Minimal"),
              ["core"])]

    _l10n_domain = "comps"

    efi_dir = "redhat"

    def getPackagePaths(self, uri):
        if not type(uri) == types.ListType:
            uri = [uri,]

        return {productName: uri}

    def configure(self, anaconda):
        BaseInstallClass.configure(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self, anaconda.storage)

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
        if oldver is None:
            return False

        oldMajor = oldver.split(".")[0]
        newMajor = productVersion.split(".")[0]

        return oldMajor == newMajor

    def __init__(self):
        BaseInstallClass.__init__(self)
