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
from pyanaconda.product import productName
from pyanaconda import network
from pyanaconda import nm

class RHELBaseInstallClass(BaseInstallClass):
    name = "Red Hat Enterprise Linux"
    sortPriority = 10000
    if not productName.startswith("Red Hat "):          # pylint: disable=no-member
        hidden = True
    defaultFS = "xfs"

    bootloaderTimeoutDefault = 5

    ignoredPackages = ["ntfsprogs"]

    installUpdates = False

    _l10n_domain = "comps"

    efi_dir = "redhat"

    help_placeholder = "RHEL7Placeholder.html"
    help_placeholder_with_links = "RHEL7PlaceholderWithLinks.html"

    def configure(self, anaconda):
        BaseInstallClass.configure(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self, anaconda.storage)

    def setNetworkOnbootDefault(self, ksdata):
        if any(nd.onboot for nd in ksdata.network.network if nd.device):
            return
        # choose the device used during installation
        # (ie for majority of cases the one having the default route)
        dev = network.default_route_device() \
              or network.default_route_device(family="inet6")
        if not dev:
            return
        # ignore wireless (its ifcfgs would need to be handled differently)
        if nm.nm_device_type_is_wifi(dev):
            return
        network.update_onboot_value(dev, True, ksdata=ksdata)

    def __init__(self):
        BaseInstallClass.__init__(self)
