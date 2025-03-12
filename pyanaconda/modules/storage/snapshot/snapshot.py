#
# The snapshot module.
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
from pykickstart.constants import (
    CLEARPART_TYPE_ALL,
    SNAPSHOT_WHEN_POST_INSTALL,
    SNAPSHOT_WHEN_PRE_INSTALL,
)

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.dbus import DBus
from pyanaconda.modules.common.constants.objects import SNAPSHOT
from pyanaconda.modules.storage.checker.utils import storage_checker
from pyanaconda.modules.storage.snapshot.create import SnapshotCreateTask
from pyanaconda.modules.storage.snapshot.device import get_snapshot_device
from pyanaconda.modules.storage.snapshot.snapshot_interface import SnapshotInterface
from pyanaconda.modules.storage.storage_subscriber import StorageSubscriberModule

log = get_module_logger(__name__)


class SnapshotModule(StorageSubscriberModule):
    """The snapshot module."""

    def __init__(self):
        super().__init__()
        self._requests = []

        # Register a check for the storage checker.
        storage_checker.add_check(self.verify_requests)

    def publish(self):
        """Publish the module."""
        DBus.publish_object(SNAPSHOT.object_path, SnapshotInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        # Keep the list of snapshot data.
        self._requests = data.snapshot.snapshotList

        # Cannot check the post-install snapshot data yet.
        if not self.is_requested(SNAPSHOT_WHEN_PRE_INSTALL):
            return

        # Check the pre-install snapshot data.
        if data.clearpart.devices \
                or data.clearpart.drives \
                or data.clearpart.type == CLEARPART_TYPE_ALL:
            log.warning("Snapshot: \"clearpart\" command "
                        "could erase pre-install snapshots!")

        if data.zerombr.zerombr:
            log.warning("Snapshot: \"zerombr\" command could "
                        "erase pre-install snapshots!")

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.snapshot.snapshotList = self._requests

    def is_requested(self, when):
        """Is there a snapshot request of the given type?

        :param when: a type of the requests
        :return: True or False
        """
        return bool(self.get_requests(when))

    def get_requests(self, when):
        """Get a list of snapshot requests of the given type.

        :param when: a type of the requests
        :returns: a list of requests
        """
        return [request for request in self._requests if request.when == when]

    def verify_requests(self, storage, constraints, report_error, report_warning):
        """Verify the validity of snapshot requests for the given storage.

        This is a callback for the storage checker.

        :param storage: a storage to check
        :param constraints: a dictionary of constraints
        :param report_error: a function for error reporting
        :param report_warning: a function for warning reporting
        """
        # We can verify only the post-install snapshot requests.
        requests = self.get_requests(SNAPSHOT_WHEN_POST_INSTALL)

        for request in requests:
            log.debug("Validating the snapshot request for: %s", request.name)
            try:
                get_snapshot_device(request, storage.devicetree)
            except (StorageError, ValueError) as e:
                report_error(str(e))

    def create_with_task(self, when):
        """Create ThinLV snapshots.

        PRE-INSTALL: Create a snapshot before installation starts.
        This must be done before user can change anything.

        POST-INSTALL: Create a snapshot after post section stops.
        Blivet must be reset before creation of the snapshot. This is
        required because the storage could be changed in post section.

        :param when: a type of the requests to use
        :return: a task
        """
        return SnapshotCreateTask(
            storage=self.storage,
            requests=self.get_requests(when),
            when=when
        )
