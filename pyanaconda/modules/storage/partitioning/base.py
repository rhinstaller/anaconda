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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from abc import abstractmethod

from blivet.devices import (
    BTRFSDevice,
    LVMLogicalVolumeDevice,
    LVMVolumeGroupDevice,
    MDRaidArrayDevice,
    PartitionDevice,
    TmpFSDevice,
)
from dasbus.server.publishable import Publishable

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.util import LazyObject
from pyanaconda.modules.common.base.base import KickstartBaseModule
from pyanaconda.modules.common.errors.storage import UnavailableStorageError
from pyanaconda.modules.storage.devicetree import DeviceTreeModule
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask

log = get_module_logger(__name__)

__all__ = ["PartitioningModule"]


class PartitioningModule(KickstartBaseModule, Publishable):
    """The partitioning module."""

    def __init__(self):
        """Create the module."""
        super().__init__()
        self._current_storage = None
        self._storage_playground = None
        self._selected_disks = []
        self._device_tree_module = None

    @property
    @abstractmethod
    def partitioning_method(self):
        """Type of the partitioning method."""
        return None

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
            self._storage_playground = self._create_storage_playground()

        return self._storage_playground

    @property
    def lazy_storage(self):
        """The lazy storage model.

        Provides a lazy access to the storage model. This property will not
        trigger a creation of the storage playground. The playground will be
        created on the first access of the storage attributes.
        """
        return LazyObject(lambda: self.storage)

    def _create_storage_playground(self):
        """Prepare the current storage model for partitioning."""
        log.debug(
            "Creating a new storage playground for %s with "
            "selected disks %s.", self, self._selected_disks
        )
        storage = self._current_storage.copy()
        storage.select_disks(self._selected_disks)
        return storage

    def on_storage_changed(self, storage):
        """Update the current storage."""
        self._current_storage = storage

    def on_partitioning_reset(self):
        """Drop the storage playground."""
        self._storage_playground = None

    def on_selected_disks_changed(self, selection):
        """Keep the current disk selection."""
        self._selected_disks = selection

    def get_device_tree(self):
        """Get the device tree module.

        :return: a device tree module
        """
        module = self._device_tree_module

        if not module:
            module = self._create_device_tree()
            module.on_storage_changed(self.lazy_storage)
            self._device_tree_module = module

        return module

    def _create_device_tree(self):
        """Create the device tree module.

        :return: a device tree module
        """
        return DeviceTreeModule()

    @abstractmethod
    def configure_with_task(self):
        """Schedule the partitioning actions.

        :return: a task
        """
        pass

    def validate_with_task(self):
        """Validate the scheduled partitioning.

        Run sanity checks on the current storage model to
        verify if the partitioning is valid.

        The result of the task is a validation report.

        :return: a task
        """
        return StorageValidateTask(self.storage)

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

            # Don't generate sensitive information.
            if hasattr(device_data, "passphrase"):
                device_data.passphrase = ""

            parent = getattr(data, list_attr)
            parent.dataList().append(device_data)

    def __str__(self):
        """Return the string representation."""
        return str(self.partitioning_method.value)
