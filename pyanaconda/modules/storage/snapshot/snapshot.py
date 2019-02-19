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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pykickstart.constants import SNAPSHOT_WHEN_PRE_INSTALL, CLEARPART_TYPE_ALL
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.dbus import DBus
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import SNAPSHOT
from pyanaconda.modules.storage.snapshot.snapshot_interface import SnapshotInterface

log = get_module_logger(__name__)


class SnapshotModule(KickstartBaseModule):
    """The snapshot module."""

    def __init__(self):
        super().__init__()
        self._requests = []

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
        return data

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
