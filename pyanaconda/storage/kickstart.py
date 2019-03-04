#
# Copyright (C) 2019  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import CLEAR_PARTITIONS_NONE
from pyanaconda.modules.common.constants.objects import DISK_SELECTION, AUTO_PARTITIONING, \
    DISK_INITIALIZATION
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.disk_initialization.initialization import DiskInitializationModule

log = get_module_logger(__name__)

__all__ = ["update_storage_ksdata"]


def update_storage_ksdata(storage, ksdata):
    """Update kickstart data to reflect the current storage configuration.

    FIXME: This is a temporary workaround for UI.

    :param storage: an instance of the storage
    :param ksdata: an instance of kickstart data
    """
    if not ksdata or not storage.mountpoints:
        return

    _update_disk_selection(storage)
    _update_autopart(storage)
    _update_clearpart(storage)
    _update_custom_storage(storage, ksdata)


def _update_disk_selection(storage):
    """Update data for disk selection.

    :param storage: an instance of the storage
    """
    disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)

    if storage.ignored_disks:
        disk_select_proxy.SetIgnoredDisks(storage.ignored_disks)
    elif storage.exclusive_disks:
        disk_select_proxy.SetSelectedDisks(storage.exclusive_disks)


def _update_autopart(storage):
    """Update data for automatic partitioning.

    :param storage: an instance of the storage
    """
    auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)
    auto_part_proxy.SetEnabled(storage.do_autopart)
    auto_part_proxy.SetType(storage.autopart_type)
    auto_part_proxy.SetEncrypted(storage.encrypted_autopart)

    if storage.encrypted_autopart:
        auto_part_proxy.SetLUKSVersion(storage.autopart_luks_version)

        if storage.autopart_pbkdf_args:
            auto_part_proxy.SetPBKDF(storage.autopart_pbkdf_args.type or "")
            auto_part_proxy.SetPBKDFMemory(storage.autopart_pbkdf_args.max_memory_kb)
            auto_part_proxy.SetPBKDFIterations(storage.autopart_pbkdf_args.iterations)
            auto_part_proxy.SetPBKDFTime(storage.autopart_pbkdf_args.time_ms)


def _update_clearpart(storage):
    """Update data for clearpart.

    :param storage: an instance of the storage
    """
    disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)
    disk_init_proxy.SetInitializationMode(storage.config.clear_part_type)
    disk_init_proxy.SetDrivesToClear(storage.config.clear_part_disks)
    disk_init_proxy.SetDevicesToClear(storage.config.clear_part_devices)
    disk_init_proxy.SetInitializeLabelsEnabled(storage.config.initialize_disks)

    if disk_init_proxy.InitializationMode == CLEAR_PARTITIONS_NONE:
        # FIXME: This is an ugly temporary workaround for UI.
        mode, drives, devices = DiskInitializationModule._find_cleared_devices(storage)

        disk_init_proxy.SetInitializationMode(mode.value)
        disk_init_proxy.SetDrivesToClear(drives)
        disk_init_proxy.SetDevicesToClear(devices)


def _update_custom_storage(storage, ksdata):
    """Update kickstart data for custom storage.

    :param storage: an instance of the storage
    :param ksdata: an instance of kickstart data
    """
    # clear out whatever was there before
    ksdata.partition.partitions = []
    ksdata.logvol.lvList = []
    ksdata.raid.raidList = []
    ksdata.volgroup.vgList = []
    ksdata.btrfs.btrfsList = []

    if storage.do_autopart:
        return

    # FIXME: This is an ugly temporary workaround for UI.
    PartitioningModule._setup_kickstart_from_storage(ksdata, storage)
