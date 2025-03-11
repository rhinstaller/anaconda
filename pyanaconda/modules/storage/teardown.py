#
# Storage teardown.
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
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.task import Task

__all__ = ["TeardownDiskImagesTask", "UnmountFilesystemsTask"]


class UnmountFilesystemsTask(Task):
    """A task for unmounting the filesystems."""

    def __init__(self, storage):
        """Create a new task."""
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        return "Unmount filesystems"

    def run(self):
        """Run the task."""
        if conf.target.is_hardware:
            return

        self._storage.umount_filesystems(swapoff=False)


class TeardownDiskImagesTask(Task):
    """A task for teardown of disk images."""

    def __init__(self, storage):
        """Create a new task.

        :param storage: an instance of Blivet
        """
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        return "Tear down disk images"

    def run(self):
        """Run the task."""
        if not conf.target.is_image:
            return

        self._storage.devicetree.teardown_disk_images()
