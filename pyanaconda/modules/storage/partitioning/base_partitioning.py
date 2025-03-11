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

from blivet.errors import InconsistentParentSectorSize, StorageError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.errors.configuration import (
    BootloaderConfigurationError,
    StorageConfigurationError,
)
from pyanaconda.modules.common.task.task import Task
from pyanaconda.modules.storage.bootloader import BootLoaderError
from pyanaconda.modules.storage.constants import INCONSISTENT_SECTOR_SIZES_SUGGESTIONS

log = get_module_logger(__name__)

__all__ = ["PartitioningTask"]


class PartitioningTask(Task, metaclass=ABCMeta):
    """A task for the partitioning configuration."""

    def __init__(self, storage):
        """Create a task.

        :param storage: an instance of Blivet
        """
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        """Name of this task."""
        return "Configure the partitioning"

    def run(self):
        """Do the partitioning and handle the errors."""
        try:
            self._run(self._storage)
        except InconsistentParentSectorSize as e:
            self._handle_storage_error(e, "\n\n".join([
                _("Failed to proceed with the installation."),
                str(e).strip(),
                _(INCONSISTENT_SECTOR_SIZES_SUGGESTIONS)
            ]))
        except (StorageError, ValueError) as e:
            self._handle_storage_error(e, str(e))
        except BootLoaderError as e:
            self._handle_bootloader_error(e, str(e))

    @abstractmethod
    def _run(self, storage):
        """Do the partitioning."""
        pass

    def _handle_storage_error(self, exception, message):
        """Handle the storage error.

        :param exception: an exception to handle
        :param message: an error message to use
        :raise: StorageConfigurationError
        """
        log.error("Storage configuration has failed: %s", message)

        # Reset the boot loader configuration.
        # FIXME: Handle the boot loader reset in a better way.
        self._storage.bootloader.reset()

        raise StorageConfigurationError(message) from exception

    def _handle_bootloader_error(self, exception, message):
        """Handle the bootloader error.

        :param exception: an exception to handle
        :param message: an error message to use
        :raise: BootloaderConfigurationError
        """
        log.error("Bootloader configuration has failed: %s", message)

        # Reset the boot loader configuration.
        # FIXME: Handle the boot loader reset in a better way.
        self._storage.bootloader.reset()

        raise BootloaderConfigurationError(message) from exception
