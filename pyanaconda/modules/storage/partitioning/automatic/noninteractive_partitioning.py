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
from abc import ABCMeta, abstractmethod

from blivet.errors import NoDisksError
from blivet.formats.disklabel import DiskLabel

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.constants.objects import DISK_INITIALIZATION
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.storage.bootloader.execution import setup_bootloader
from pyanaconda.modules.storage.disk_initialization import DiskInitializationConfig
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

    def _get_initialization_config(self):
        """Get the initialization config.

        FIXME: This is a temporary method.
        """
        config = DiskInitializationConfig()

        # Update the config.
        disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)
        config.initialization_mode = disk_init_proxy.InitializationMode
        config.drives_to_clear = disk_init_proxy.DrivesToClear
        config.devices_to_clear = disk_init_proxy.DevicesToClear
        config.initialize_labels = disk_init_proxy.InitializeLabelsEnabled
        config.format_unrecognized = disk_init_proxy.FormatUnrecognizedEnabled
        config.clear_non_existent = False

        # Update the disk label.
        disk_label = disk_init_proxy.DefaultDiskLabel

        if disk_label:
            DiskLabel.set_default_label_type(disk_label)

        return config

    def _clear_partitions(self, storage):
        """Clear partitions.

        :param storage: an instance of Blivet
        """
        # Set up the initialization config.
        config = self._get_initialization_config()

        # Sort partitions by descending partition number to minimize confusing
        # things like multiple "destroy sda5" actions due to parted renumbering
        # partitions. This can still happen through the UI but it makes sense to
        # avoid it where possible.
        partitions = sorted(storage.partitions,
                            key=lambda p: getattr(p.parted_partition, "number", 1),
                            reverse=True)
        for part in partitions:
            log.debug("Looking at partition: %s", part.name)
            if not config.can_remove(storage, part):
                continue

            storage.recursive_remove(part)
            log.debug("Partitions: %s", [p.name for p in part.disk.children])

        # Now remove any empty extended partitions.
        storage.remove_empty_extended_partitions()

        # Ensure all disks have appropriate disk labels.
        for disk in storage.disks:
            log.debug("Looking at disk: %s", disk.name)
            if config.can_remove(storage, disk):
                log.debug("Removing %s.", disk.name)
                storage.recursive_remove(disk)

            if config.can_initialize(storage, disk):
                log.debug("Initializing %s.", disk.name)
                storage.initialize_disk(disk)

        # Check the usable disks.
        if not any(d for d in storage.disks if not d.format.hidden and not d.protected):
            raise NoDisksError(_("No usable disks."))

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
