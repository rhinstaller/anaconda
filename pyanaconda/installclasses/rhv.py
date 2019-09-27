#
# rhv.py
#
# Copyright (C) 2019  Red Hat, Inc.  All rights reserved.
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

from blivet.devicefactory import DEVICE_TYPE_LVM_THINP
from blivet.size import Size
from pykickstart.constants import AUTOPART_TYPE_LVM_THINP

from pyanaconda.core.constants import STORAGE_ROOT_DEVICE_TYPES, STORAGE_MUST_NOT_BE_ON_ROOT, \
    STORAGE_REQ_PARTITION_SIZES
from pyanaconda.installclasses.centos import CentOSBaseInstallClass
from pyanaconda.installclasses.rhel import RHELBaseInstallClass
from pyanaconda.kickstart import getAvailableDiskSpace
from pyanaconda.platform import platform
from pyanaconda.product import productName
from pyanaconda.storage.autopart import swap_suggestion
from pyanaconda.storage.partspec import PartSpec

__all__ = ["OvirtInstallClass", "RHEVInstallClass"]


class OvirtBaseClass(object):
    default_autopart_type = AUTOPART_TYPE_LVM_THINP
    help_folder = "/usr/share/anaconda/help/rhv"

    def setDefaultPartitioning(self, storage):
        autorequests = [PartSpec(mountpoint="/", fstype=storage.default_fstype,
                                 size=Size("6GiB"), thin=True,
                                 grow=True, lv=True),
                        PartSpec(mountpoint="/home",
                                 fstype=storage.default_fstype,
                                 size=Size("1GiB"), thin=True, lv=True),
                        PartSpec(mountpoint="/tmp",
                                 fstype=storage.default_fstype,
                                 size=Size("1GiB"), thin=True, lv=True),
                        PartSpec(mountpoint="/var",
                                 fstype=storage.default_fstype,
                                 size=Size("15GiB"), thin=True, lv=True),
                        PartSpec(mountpoint="/var/log",
                                 fstype=storage.default_fstype,
                                 size=Size("8GiB"), thin=True, lv=True),
                        PartSpec(mountpoint="/var/log/audit",
                                 fstype=storage.default_fstype,
                                 size=Size("2GiB"), thin=True, lv=True)]

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
                    autoreq.size = Size("1GiB")
                else:
                    autoreq.fstype = storage.default_fstype

        storage.autopart_requests = autorequests

    def setStorageChecker(self, storage_checker):
        # / needs to be thin LV
        storage_checker.add_constraint(STORAGE_ROOT_DEVICE_TYPES, {
            DEVICE_TYPE_LVM_THINP
        })

        # /var must be on a separate LV or partition
        storage_checker.update_constraint(STORAGE_MUST_NOT_BE_ON_ROOT, {
            '/var'
        })

        # /var must be at least 10GB, /boot must be at least 1GB
        storage_checker.update_constraint(STORAGE_REQ_PARTITION_SIZES, {
            '/var': Size("10 GiB"),
            '/boot': Size("1 GiB")
        })


class OvirtInstallClass(OvirtBaseClass, CentOSBaseInstallClass):
    name = "oVirt Node Next"
    hidden = not productName.startswith("oVirt")


class RHEVInstallClass(OvirtBaseClass, RHELBaseInstallClass):
    name = "Red Hat Virtualization"
    hidden = not productName.startswith(
        ("RHV", "Red Hat Virtualization")
    )
