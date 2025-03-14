#
# The interactive partitioning module
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.storage.disk_initialization.configuration import (
    DiskInitializationConfig,
)
from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.partitioning.constants import PartitioningMethod
from pyanaconda.modules.storage.partitioning.interactive.interactive_interface import (
    InteractivePartitioningInterface,
)
from pyanaconda.modules.storage.partitioning.interactive.interactive_partitioning import (
    InteractivePartitioningTask,
)
from pyanaconda.modules.storage.partitioning.interactive.scheduler_module import (
    DeviceTreeSchedulerModule,
)

log = get_module_logger(__name__)


class InteractivePartitioningModule(PartitioningModule):
    """The interactive partitioning module."""

    @property
    def partitioning_method(self):
        """Type of the partitioning method."""
        return PartitioningMethod.INTERACTIVE

    def for_publication(self):
        """Return a DBus representation."""
        return InteractivePartitioningInterface(self)

    def _create_device_tree(self):
        """Create the device tree module."""
        return DeviceTreeSchedulerModule()

    def _create_storage_playground(self):
        """Prepare the current storage model for partitioning."""
        storage = super()._create_storage_playground()

        # Ensure all disks have appropriate disk labels.
        config = DiskInitializationConfig()
        config.initialize_labels = True

        for disk in storage.disks:
            if config.can_initialize(storage, disk):
                storage.initialize_disk(disk)

        return storage

    def configure_with_task(self):
        """Complete the scheduled partitioning."""
        return InteractivePartitioningTask(self.storage)
