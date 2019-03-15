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
from abc import abstractmethod, ABCMeta
from blivet.errors import StorageError
from pykickstart.errors import KickstartParseError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.bootloader import BootLoaderError
from pyanaconda.modules.common.errors.configuration import StorageConfigurationError, \
    BootloaderConfigurationError
from pyanaconda.modules.common.task.task import Task

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
        except (StorageError, KickstartParseError, ValueError) as e:
            log.error("Storage configuration has failed: %s", e)
            raise StorageConfigurationError(str(e)) from e
        except BootLoaderError as e:
            log.error("Bootloader configuration has failed: %s", e)
            raise BootloaderConfigurationError(str(e)) from e

    @abstractmethod
    def _run(self, storage):
        """Do the partitioning."""
        pass
