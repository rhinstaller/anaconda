#
# Rescue tasks
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
from blivet.errors import StorageError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.errors.storage import MountFilesystemError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.storage.devicetree.root import (
    find_existing_installations,
    mount_existing_system,
)

log = get_module_logger(__name__)

__all__ = ["FindExistingSystemsTask", "MountExistingSystemTask"]


class FindExistingSystemsTask(Task):
    """A task to find existing GNU/Linux installations."""

    def __init__(self, devicetree):
        """Create a new task.

        :param devicetree: a device tree to search
        """
        super().__init__()
        self._devicetree = devicetree

    @property
    def name(self):
        return "Find existing operating systems"

    def run(self):
        """Run the task.

        :return: a list of data about found systems
        """
        return find_existing_installations(devicetree=self._devicetree)


class MountExistingSystemTask(Task):
    """A task to mount an existing GNU/Linux installation."""

    def __init__(self, storage, device, read_only):
        """Create a new task.

        :param storage: an instance of the Blivet's storage
        :param device: a root device of the system
        :param read_only: mount the system in read-only mode
        """
        super().__init__()
        self._storage = storage
        self._device = device
        self._read_only = read_only

    @property
    def name(self):
        return "Mount an existing operating system"

    def run(self):
        """Run the task.

        :raise: MountFilesystemError in case of failure
        """
        try:
            mount_existing_system(
                storage=self._storage,
                root_device=self._device,
                read_only=self._read_only
            )
        except StorageError as e:
            log.error("Failed to mount the system: %s", e)
            raise MountFilesystemError(str(e)) from e
