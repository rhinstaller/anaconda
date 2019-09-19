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

from pykickstart.constants import AUTOPART_TYPE_LVM_THINP

from blivet.size import Size
from pyanaconda.core.constants import STORAGE_MIN_PARTITION_SIZES
from pyanaconda.installclasses.centos import CentOSBaseInstallClass
from pyanaconda.installclasses.rhel import RHELBaseInstallClass
from pyanaconda.kickstart import getAvailableDiskSpace
from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.platform import platform
from pyanaconda.product import productName
from pyanaconda.storage.autopart import swap_suggestion
from pyanaconda.storage.partspec import PartSpec

__all__ = ["OvirtInstallClass", "RHVInstallClass"]


class OvirtBaseClass:
    help_folder = "/usr/share/anaconda/help/rhv"

    def set_autopart_type(self):
        from pyanaconda.ui.gui.spokes.lib import accordion
        accordion.DEFAULT_AUTOPART_TYPE = AUTOPART_TYPE_LVM_THINP
        STORAGE.get_proxy(AUTO_PARTITIONING).SetType(AUTOPART_TYPE_LVM_THINP)

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
        # TODO: add checks on root_device_types and must_not_be_on_root once
        # those are added back to storage_utils
        # /var must be at least 10GB, /boot must be at least 1GB
        storage_checker.update_constraint(STORAGE_MIN_PARTITION_SIZES, {
            '/var': Size("10 GiB"),
            '/boot': Size("1 GiB")
        })


class OvirtInstallClass(OvirtBaseClass, CentOSBaseInstallClass):
    name = "oVirt Node Next"
    hidden = not productName.startswith("oVirt")
    sortPriority = 21000

    def configure(self, anaconda):
        CentOSBaseInstallClass.configure(self, anaconda)
        self.set_autopart_type()

class RHVInstallClass(OvirtBaseClass, RHELBaseInstallClass):
    name = "Red Hat Virtualization"
    hidden = not productName.startswith(("RHV", "Red Hat Virtualization"))

    def configure(self, anaconda):
        RHELBaseInstallClass.configure(self, anaconda)
        self.set_autopart_type()
