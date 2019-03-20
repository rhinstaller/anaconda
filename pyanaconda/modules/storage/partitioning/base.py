#
# The module for partitioning.
#
# Copyright (C) 2019 Red Hat, Inc.
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
from abc import abstractmethod

from blivet.devices import PartitionDevice, TmpFSDevice, LVMLogicalVolumeDevice, \
    LVMVolumeGroupDevice, MDRaidArrayDevice, BTRFSDevice

from pyanaconda.modules.common.base.base import KickstartBaseModule
from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

__all__ = ["PartitioningModule"]


class PartitioningModule(KickstartBaseModule):
    """The partitioning module."""

    def __init__(self):
        """Create the module."""
        super().__init__()
        self._current_storage = None
        self._storage_playground = None
        self._selected_disks = []

    @property
    def storage(self):
        """The storage model.

        Provides a copy of the current storage model,
        that can be safely used for partitioning.

        :return: an instance of Blivet
        """
        if self._current_storage is None:
            raise UnavailableStorageError()

        if self._storage_playground is None:
            self._storage_playground = self._current_storage.copy()
            self._storage_playground.select_disks(self._selected_disks)

        return self._storage_playground

    def on_storage_reset(self, storage):
        """Keep the instance of the current storage."""
        self._current_storage = storage

    def on_selected_disks_changed(self, selection):
        """Keep the current disk selection."""
        self._selected_disks = selection

    @abstractmethod
    def configure_with_task(self):
        """Schedule the partitioning actions.

        :return: a DBus path to a task
        """
        pass

    @abstractmethod
    def validate_with_task(self):
        """Validate the scheduled partitioning.

        Run sanity checks on the current storage model to
        verify if the partitioning is valid.

        :return: a DBus path to a task
        """
        pass

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        if not self._storage_playground:
            return

        self._setup_kickstart_from_storage(data, self._storage_playground)

    @staticmethod
    def _setup_kickstart_from_storage(data, storage):
        """Setup the kickstart data from the given storage.

        :param data: an instance of kickstart data
        :param storage: an instance of the storage model
        """
        # Map devices on kickstart commands and data.
        ks_map = {
            PartitionDevice: ("PartData", "partition"),
            TmpFSDevice: ("PartData", "partition"),
            LVMLogicalVolumeDevice: ("LogVolData", "logvol"),
            LVMVolumeGroupDevice: ("VolGroupData", "volgroup"),
            MDRaidArrayDevice: ("RaidData", "raid"),
            BTRFSDevice: ("BTRFSData", "btrfs")
        }

        # List comprehension that builds device ancestors should not get None
        # as a member when searching for bootloader devices
        bootloader_devices = []

        if storage.bootloader.stage1_device is not None:
            bootloader_devices.append(storage.bootloader.stage1_device)

        for device in storage.devices:
            if device.format.type == 'biosboot':
                bootloader_devices.append(device)

        # Make a list of ancestors of all used devices
        used_devices = list(storage.mountpoints.values()) + storage.swaps + bootloader_devices
        all_devices = list(set(a for d in used_devices for a in d.ancestors))
        all_devices.sort(key=lambda d: len(d.ancestors))

        # Devices which share information with their distinct raw device
        complementary_devices = [d for d in all_devices if d.raw_device is not d]

        # Generate the kickstart commands.
        for device in all_devices:
            cls = next((c for c in ks_map if isinstance(device, c)), None)

            if cls is None:
                log.info("Omitting kickstart data for: %s", device)
                continue

            class_attr, list_attr = ks_map[cls]

            cls = getattr(data, class_attr)
            device_data = cls()  # all defaults

            complements = [d for d in complementary_devices if d.raw_device is device]

            if len(complements) > 1:
                log.warning("Omitting kickstart data for %s, found too many (%d) "
                            "complementary devices.", device, len(complements))
                continue

            device = complements[0] if complements else device
            device.populate_ksdata(device_data)

            parent = getattr(data, list_attr)
            parent.dataList().append(device_data)
