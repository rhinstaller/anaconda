#
# fedora.py
#
# Copyright (C) 2017  Red Hat, Inc.  All rights reserved.
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

from pyanaconda.installclasses.fedora import FedoraBaseInstallClass
from pyanaconda.product import productName
from pyanaconda.kickstart import getAvailableDiskSpace
from blivet.partspec import PartSpec
from blivet.autopart import swap_suggestion
from blivet.platform import platform
from blivet.size import Size

__all__ = ["FedoraServerInstallClass"]


class FedoraServerInstallClass(FedoraBaseInstallClass):
    name = "Fedora Server"
    stylesheet = "/usr/share/anaconda/fedora-server.css"
    defaultFS = "xfs"
    sortPriority = FedoraBaseInstallClass.sortPriority + 1
    if not productName.startswith("Fedora Server"):          # pylint: disable=no-member
        hidden = True
    defaultPackageEnvironment = "server-product-environment"

    def setDefaultPartitioning(self, storage):
        autorequests = [PartSpec(mountpoint="/", fstype=storage.default_fstype,
                                 size=Size("2GiB"),
                                 max_size=Size("15GiB"),
                                 grow=True,
                                 btr=True, lv=True, thin=True, encrypted=True)]

        bootreqs = platform.set_default_partitioning()
        if bootreqs:
            autorequests.extend(bootreqs)


        disk_space = getAvailableDiskSpace(storage)
        swp = swap_suggestion(disk_space=disk_space)
        autorequests.append(PartSpec(fstype="swap", size=swp, grow=False,
                                     lv=True, encrypted=True))

        for autoreq in autorequests:
            if autoreq.fstype is None:
                if autoreq.mountpoint == "/boot":
                    autoreq.fstype = storage.default_boot_fstype
                else:
                    autoreq.fstype = storage.default_fstype

        storage.autopart_requests = autorequests
