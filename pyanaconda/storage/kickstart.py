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
from blivet.devices import PartitionDevice, TmpFSDevice, LVMLogicalVolumeDevice, \
    LVMVolumeGroupDevice, MDRaidArrayDevice, BTRFSDevice

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import CLEAR_PARTITIONS_NONE, CLEAR_PARTITIONS_LIST, \
    CLEAR_PARTITIONS_ALL
from pyanaconda.modules.common.constants.objects import DISK_SELECTION, AUTO_PARTITIONING, \
    DISK_INITIALIZATION
from pyanaconda.modules.common.constants.services import STORAGE

log = get_module_logger(__name__)

__all__ = ["update_storage_ksdata"]


def update_storage_ksdata(storage, ksdata):
    """Update kickstart data to reflect the current storage configuration.

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
        # Make a list of initialized disks and of removed partitions. If any
        # partitions were removed from disks that were not completely
        # cleared we'll have to use CLEAR_PARTITIONS_LIST and provide a list
        # of all removed partitions. If no partitions were removed from a
        # disk that was not cleared/reinitialized we can use
        # CLEAR_PARTITIONS_ALL.
        disk_init_proxy.SetDrivesToClear([])
        disk_init_proxy.SetDevicesToClear([])

        fresh_disks = [d.name for d in storage.disks if d.partitioned and
                       not d.format.exists]

        destroy_actions = storage.devicetree.actions.find(
            action_type="destroy",
            object_type="device"
        )

        cleared_partitions = []
        partial = False
        for action in destroy_actions:
            if action.device.type == "partition":
                if action.device.disk.name not in fresh_disks:
                    partial = True

                cleared_partitions.append(action.device.name)

        if not destroy_actions:
            pass
        elif partial:
            # make a list of removed partitions
            disk_init_proxy.SetInitializationMode(CLEAR_PARTITIONS_LIST)
            disk_init_proxy.SetDevicesToClear(cleared_partitions)
        else:
            # if they didn't partially clear any disks, use the shorthand
            disk_init_proxy.SetInitializationMode(CLEAR_PARTITIONS_ALL)
            disk_init_proxy.SetDrivesToClear(fresh_disks)


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

    # custom storage
    ks_map = {
        PartitionDevice: ("PartData", "partition"),
        TmpFSDevice: ("PartData", "partition"),
        LVMLogicalVolumeDevice: ("LogVolData", "logvol"),
        LVMVolumeGroupDevice: ("VolGroupData", "volgroup"),
        MDRaidArrayDevice: ("RaidData", "raid"),
        BTRFSDevice: ("BTRFSData", "btrfs")
    }

    # list comprehension that builds device ancestors should not get None as a member
    # when searching for bootloader devices
    bootloader_devices = []
    if storage.bootloader_device is not None:
        bootloader_devices.append(storage.bootloader_device)

    # biosboot is a special case
    for device in storage.devices:
        if device.format.type == 'biosboot':
            bootloader_devices.append(device)

    # make a list of ancestors of all used devices
    used_devices = list(storage.mountpoints.values()) + storage.swaps + bootloader_devices

    devices = list(set(a for d in used_devices for a in d.ancestors))
    devices.sort(key=lambda d: len(d.ancestors))

    # devices which share information with their distinct raw device
    complementary_devices = [d for d in devices if d.raw_device is not d]

    for device in devices:
        cls = next((c for c in ks_map if isinstance(device, c)), None)
        if cls is None:
            log.info("omitting ksdata: %s", device)
            continue

        class_attr, list_attr = ks_map[cls]

        cls = getattr(ksdata, class_attr)
        data = cls()    # all defaults

        complements = [d for d in complementary_devices if d.raw_device is device]

        if len(complements) > 1:
            log.warning("omitting ksdata for %s, found too many (%d) complementary devices",
                        device, len(complements))
            continue

        device = complements[0] if complements else device
        device.populate_ksdata(data)

        parent = getattr(ksdata, list_attr)
        parent.dataList().append(data)
