#
# Tasks for creating snapshots.
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
from blivet.formats.fs import XFS
from pykickstart.constants import SNAPSHOT_WHEN_POST_INSTALL, SNAPSHOT_WHEN_PRE_INSTALL

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.task.task import Task
from pyanaconda.modules.storage.snapshot.device import get_snapshot_device

log = get_module_logger(__name__)

__all__ = ["SnapshotCreateTask"]


class SnapshotCreateTask(Task):
    """A task for creating snapshots."""

    def __init__(self, storage, requests, when):
        """Create a new task.

        :param storage: an instance of Blivet
        :param requests: a list of the snapshot requests
        :param when: when the snapshots are created
        """
        super().__init__()
        self._storage = storage
        self._requests = requests
        self._when = when

    @property
    def name(self):
        return "Create snapshots"

    def run(self):
        """Run the task."""
        self._create_snapshots(self._storage, self._requests, self._when)

    def _create_snapshots(self, storage, requests, when):
        """Create the snapshots.

        :param storage: an instance of Blivet
        :param requests: a list of the snapshot requests
        :param when: when the snapshots are created
        """
        if when == SNAPSHOT_WHEN_POST_INSTALL:
            self._populate_devicetree(storage)

        for request in requests:
            self._create_snapshot(storage, request)

        if when == SNAPSHOT_WHEN_PRE_INSTALL:
            self._populate_devicetree(storage)

    def _populate_devicetree(self, storage):
        """Populate a device tree of the given storage."""
        storage.devicetree.populate()
        storage.devicetree.teardown_all()

    def _create_snapshot(self, storage, request):
        """Create the ThinLV snapshot.

        :param storage: an instance of Blivet
        :param request: a snapshot request
        """
        log.debug("Snapshot: creating snapshot %s", request.name)
        device = get_snapshot_device(request, storage.devicetree)
        device.create()

        if isinstance(device.format, XFS):
            log.debug("Generating new UUID for XFS snapshot")
            device.format.reset_uuid()
