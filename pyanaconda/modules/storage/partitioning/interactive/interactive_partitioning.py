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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from blivet.devicefactory import SIZE_POLICY_AUTO
from blivet.errors import StorageError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.storage.bootloader.execution import setup_bootloader
from pyanaconda.modules.storage.checker.utils import (
    storage_checker,
    verify_luks_devices_have_key,
)
from pyanaconda.modules.storage.partitioning.automatic.automatic_partitioning import (
    AutomaticPartitioningTask,
)
from pyanaconda.modules.storage.partitioning.base_partitioning import PartitioningTask

log = get_module_logger(__name__)

__all__ = ["InteractiveAutoPartitioningTask", "InteractivePartitioningTask"]


class InteractivePartitioningTask(PartitioningTask):
    """A task for the interactive partitioning configuration."""

    def _run(self, storage):
        """Only set up the bootloader."""
        self._prepare_bootloader(storage)
        self._set_fstab_swaps(storage)

    def _prepare_bootloader(self, storage):
        """Prepare the bootloader."""
        setup_bootloader(storage)

    def _set_fstab_swaps(self, storage):
        """Set swap devices that should appear in the fstab."""
        storage.set_fstab_swaps([
            d for d in storage.devices
            if d.direct and not d.format.exists and not d.partitioned and d.format.type == "swap"
        ])


class InteractiveAutoPartitioningTask(AutomaticPartitioningTask):
    """A task for the interactive auto partitioning configuration."""

    def _run(self, storage):
        """Do the partitioning."""
        super()._run(storage)
        self._update_size_policy(storage)
        self._verify_partitioning(storage)

    def _clear_partitions(self, storage):
        """Nothing to clear.

        The partitions should be already cleared by the user.
        """
        pass

    def _update_size_policy(self, storage):
        """Update the size policy of new devices.

        Mark all new containers for automatic size management.
        """
        for device in storage.devices:
            if not device.exists and hasattr(device, "size_policy"):
                device.size_policy = SIZE_POLICY_AUTO

    def _verify_partitioning(self, storage):
        """Verify the created partitioning."""
        report = storage_checker.check(storage, skip=(verify_luks_devices_have_key,))
        report.log(log)

        if not report.errors:
            return

        raise StorageError(" ".join(report.errors))
