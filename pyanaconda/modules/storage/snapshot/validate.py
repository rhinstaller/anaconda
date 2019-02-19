#
# Validation tasks
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.task.task import Task
from pyanaconda.modules.storage.snapshot.device import get_snapshot_device

log = get_module_logger(__name__)

__all__ = ["SnapshotValidateTask"]


class SnapshotValidateTask(Task):
    """A task for validating snapshot requests."""

    def __init__(self, storage, requests, when):
        """Create a new task.

        :param storage: an instance of Blivet
        :param requests: a list of the snapshot requests
        :param when: when the snapshots will be created
        """
        super().__init__()
        self._storage = storage
        self._requests = requests
        self._when = when

    @property
    def name(self):
        return "Validate snapshot requests"

    def run(self):
        """Run the validation."""
        for request in self._requests:
            log.debug("Snapshot: validating the request for %s", request.name)
            self._validate_request(self._storage, request)

    def _validate_request(self, storage, request):
        """Validate a snapshot request.

        :param storage: an instance of Blivet
        :param request: a snapshot request
        :raise: KickstartParseError if not valid
        """
        # Try to create the model of the device.
        get_snapshot_device(request, storage.devicetree)
