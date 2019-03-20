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
from abc import ABCMeta, abstractmethod

from blivet.errors import NoDisksError
from blivet.formats.disklabel import DiskLabel
from pyanaconda.anaconda_loggers import get_module_logger

from pyanaconda.bootloader.execution import setup_bootloader
from pyanaconda.modules.common.constants.objects import DISK_INITIALIZATION
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.storage.partitioning.base_partitioning import PartitioningTask

log = get_module_logger(__name__)

__all__ = ["NonInteractivePartitioningTask"]


class NonInteractivePartitioningTask(PartitioningTask, metaclass=ABCMeta):
    """A task for the non-interactive partitioning configuration."""

    def _run(self, storage):
        """Do the partitioning."""
        self._clear_partitions(storage)
        self._prepare_bootloader(storage)
        self._configure_partitioning(storage)
        self._setup_bootloader(storage)

    def _clear_partitions(self, storage):
        """Clear partitions.

        :param storage: an instance of Blivet
        """
        disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)
        storage.config.clear_part_type = disk_init_proxy.InitializationMode
        storage.config.clear_part_disks = disk_init_proxy.DrivesToClear
        storage.config.clear_part_devices = disk_init_proxy.DevicesToClear
        storage.config.initialize_disks = disk_init_proxy.InitializeLabelsEnabled

        disk_label = disk_init_proxy.DefaultDiskLabel

        if disk_label and not DiskLabel.set_default_label_type(disk_label):
            log.warning("%s is not a supported disklabel type on this platform. "
                        "Using default disklabel %s instead.", disk_label,
                        DiskLabel.get_platform_label_types()[0])

        storage.clear_partitions()

        # Check the usable disks.
        if not any(d for d in storage.disks if not d.format.hidden and not d.protected):
            raise NoDisksError("No usable disks.")

    def _prepare_bootloader(self, storage):
        """Prepare the bootloader.

        :param storage: an instance of Blivet
        """
        setup_bootloader(storage, dry_run=True)

    @abstractmethod
    def _configure_partitioning(self, storage):
        """Configure the partitioning.

        :param storage: an instance of Blivet
        """
        pass

    def _setup_bootloader(self, storage):
        """Set up the bootloader.

        :param storage: an instance of Blivet
        """
        setup_bootloader(storage)
