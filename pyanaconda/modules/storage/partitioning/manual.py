#
# Manual partitioning module.
#
# Copyright (C) 2018 Red Hat, Inc.
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
from pyanaconda.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.constants.objects import MANUAL_PARTITIONING
from pyanaconda.modules.common.structures.partitioning import MountPointRequest
from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.partitioning.manual_interface import ManualPartitioningInterface
from pyanaconda.modules.storage.partitioning.manual_partitioning import ManualPartitioningTask
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask

log = get_module_logger(__name__)


class ManualPartitioningModule(PartitioningModule):
    """The manual partitioning module."""

    def __init__(self):
        """Initialize the module."""
        super().__init__()

        self.enabled_changed = Signal()
        self._enabled = False

        self.requests_changed = Signal()
        self._requests = list()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(
            MANUAL_PARTITIONING.object_path,
            ManualPartitioningInterface(self)
        )

    def process_kickstart(self, data):
        """Process the kickstart data."""
        if not data.mount.seen:
            self.set_requests(list())
            self.set_enabled(False)
            return

        requests = []

        for obj in data.mount.mount_points:
            request = MountPointRequest()
            self._process_mount_data(obj, request)
            requests.append(request)

        self.set_requests(requests)
        self.set_enabled(True)

    def _process_mount_data(self, data, request):
        """Process kickstart mount data.

        :param data: an instance of kickstart mount data
        :param request: a new instance of MountPointRequest
        """
        request.mount_point = data.mount_point
        request.device_spec = data.device
        request.reformat = data.reformat
        request.format_type = data.format
        request.format_options = data.mkfs_opts
        request.mount_options = data.mount_opts

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        if not self.enabled:
            return

        data_list = []

        for request in self.requests:
            mount_data = data.MountData()
            self._setup_mount_data(mount_data, request)
            data_list.append(mount_data)

        data.mount.mount_points = data_list

    def _setup_mount_data(self, data, request):
        """Set up kickstart mount data.

        :param data: a new instance of kickstart mount data
        :param request: an instance of MountPointRequest
        """
        data.mount_point = request.mount_point
        data.device = request.device_spec
        data.reformat = request.reformat
        data.format = request.format_type
        data.mkfs_opts = request.format_options
        data.mount_opts = request.mount_options

    @property
    def enabled(self):
        """Is the auto partitioning enabled?"""
        return self._enabled

    def set_enabled(self, enabled):
        """Is the auto partitioning enabled?

        :param enabled: a boolean value
        """
        self._enabled = enabled
        self.enabled_changed.emit()
        log.debug("Enabled is set to '%s'.", enabled)

    @property
    def requests(self):
        """A list of mount point requests."""
        return self._requests

    def set_requests(self, requests):
        """Set the list of mount point requests.

        :param requests: a list of instances of MountPointRequest
        """
        self._requests = requests
        self.requests_changed.emit()
        log.debug("Requests are set to '%s'.", requests)

    def configure_with_task(self):
        """Schedule the partitioning actions."""
        task = ManualPartitioningTask(self.storage)
        path = self.publish_task(MANUAL_PARTITIONING.namespace, task)
        return path

    def validate_with_task(self):
        """Validate the scheduled partitions."""
        task = StorageValidateTask(self.storage)
        path = self.publish_task(MANUAL_PARTITIONING.namespace, task)
        return path
