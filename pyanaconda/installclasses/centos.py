#
# centos.py
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
from pyanaconda.network import NetworkOnBoot
from pyanaconda.product import productName

__all__ = ["CentOSBaseInstallClass"]


class CentOSBaseInstallClass(BaseInstallClass):
    name = "CentOS Linux"
    sortPriority = 10000
    if not productName.startswith("CentOS"):          # pylint: disable=no-member
        hidden = True
    defaultFS = "xfs"

    ignoredPackages = ["ntfsprogs"]

    installUpdates = False

    efi_dir = "centos"

    network_on_boot = NetworkOnBoot.DEFAULT_ROUTE_DEVICE
