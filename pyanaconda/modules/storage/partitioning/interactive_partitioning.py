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
from blivet.devicefactory import SIZE_POLICY_AUTO

from pyanaconda.modules.storage.partitioning.automatic_partitioning import \
    AutomaticPartitioningTask
from pyanaconda.modules.storage.partitioning.base_partitioning import PartitioningTask

__all__ = ["InteractivePartitioningTask", "InteractiveAutoPartitioningTask"]


class InteractivePartitioningTask(PartitioningTask):
    """A task for the interactive partitioning configuration."""

    def _run(self, storage):
        """Only set up the bootloader."""
        self._prepare_bootloader(storage)
        self._organize_actions(storage)

    def _prepare_bootloader(self, storage):
        """Prepare the bootloader."""
        storage.set_up_bootloader()

    def _organize_actions(self, storage):
        """Prune and sort the scheduled actions."""
        storage.devicetree.actions.prune()
        storage.devicetree.actions.sort()


class InteractiveAutoPartitioningTask(AutomaticPartitioningTask):
    """A task for the interactive auto partitioning configuration."""

    def _run(self, storage):
        """Do the partitioning."""
        self._prepare_bootloader(storage)
        self._configure_partitioning(storage)
        self._update_size_policy(storage)

    def _prepare_bootloader(self, storage):
        """Prepare the bootloader.

        Autopart needs stage1_disk setup so it will reuse existing partitions.
        """
        storage.set_up_bootloader(early=True)

    def _update_size_policy(self, storage):
        """Update the size policy of new devices.

        Mark all new containers for automatic size management.
        """
        for device in storage.devices:
            if not device.exists and hasattr(device, "size_policy"):
                device.size_policy = SIZE_POLICY_AUTO
