#
# rhv.py
#
# Copyright (C) 2016  Red Hat, Inc.  All rights reserved.
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
from pyanaconda.kickstart import getAvailableDiskSpace
from blivet.partspec import PartSpec
from blivet.platform import platform
from blivet.devicelibs import swap
from blivet.size import Size
from pykickstart.constants import AUTOPART_TYPE_LVM_THINP
from blivet.devicefactory import DEVICE_TYPE_LVM_THINP


class OvirtBaseInstallClass(BaseInstallClass):
    name = "oVirt Node Next"
    sortPriority = 21000
    hidden = not productName.startswith("oVirt")

    efi_dir = "centos"
    default_autopart_type = AUTOPART_TYPE_LVM_THINP

    def configure(self, anaconda):
        BaseInstallClass.configure(self, anaconda)

    def setDefaultPartitioning(self, storage):
        autorequests = [PartSpec(mountpoint="/", fstype=storage.defaultFSType,
                                 size=Size("6GiB"), thin=True,
                                 grow=True, lv=True),
                        PartSpec(mountpoint="/home",
                                 fstype=storage.defaultFSType,
                                 size=Size("1GiB"), thin=True, lv=True),
                        PartSpec(mountpoint="/tmp",
                                 fstype=storage.defaultFSType,
                                 size=Size("1GiB"), thin=True, lv=True),
                        PartSpec(mountpoint="/var",
                                 fstype=storage.defaultFSType,
                                 size=Size("15GiB"), thin=True, lv=True),
                        PartSpec(mountpoint="/var/log",
                                 fstype=storage.defaultFSType,
                                 size=Size("8GiB"), thin=True, lv=True),
                        PartSpec(mountpoint="/var/log/audit",
                                 fstype=storage.defaultFSType,
                                 size=Size("2GiB"), thin=True, lv=True)]

        bootreqs = platform.setDefaultPartitioning()
        if bootreqs:
            autorequests.extend(bootreqs)

        disk_space = getAvailableDiskSpace(storage)
        swp = swap.swapSuggestion(disk_space=disk_space)
        autorequests.append(PartSpec(fstype="swap", size=swp, grow=False,
                                     lv=True, encrypted=True))

        for autoreq in autorequests:
            if autoreq.fstype is None:
                if autoreq.mountpoint == "/boot":
                    autoreq.fstype = storage.defaultBootFSType
                    autoreq.size = Size("1GiB")
                else:
                    autoreq.fstype = storage.defaultFSType

        storage.autoPartitionRequests = autorequests

    def setStorageChecker(self, storage_checker):
        # / needs to be thin LV
        storage_checker.add_constraint("root_device_types", {
            DEVICE_TYPE_LVM_THINP
        })

        # /var must be on a separate LV or partition
        storage_checker.update_constraint("must_not_be_on_root", {
            '/var'
        })

        # /var must be at least 10GB, /boot must be at least 1GB
        storage_checker.update_constraint("req_partition_sizes", {
            '/var': Size("10 GiB"),
            '/boot': Size("1 GiB")
        })

    def __init__(self):
        BaseInstallClass.__init__(self)


class RHEVInstallClass(OvirtBaseInstallClass):
    name = "Red Hat Virtualization"

    hidden = not productName.startswith(
        ("RHV", "Red Hat Virtualization")
    )

    efi_dir = "redhat"
