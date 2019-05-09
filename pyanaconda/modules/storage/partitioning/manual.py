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
from pyanaconda.modules.common.structures.mount import MountPoint
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

        self.mount_points_changed = Signal()
        self._mount_points = list()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(
            MANUAL_PARTITIONING.object_path,
            ManualPartitioningInterface(self)
        )

    def process_kickstart(self, data):
        """Process the kickstart data."""
        if not data.mount.seen:
            self.set_mount_points(list())
            self.set_enabled(False)
            return

        mount_points = []

        for obj in data.mount.mount_points:
            mount_point = MountPoint()
            self._process_mount_data(obj, mount_point)
            mount_points.append(mount_point)

        self.set_mount_points(mount_points)
        self.set_enabled(True)

    def _process_mount_data(self, data, mount_point):
        """Process kickstart mount data.

        :param data: an instance of kickstart mount data
        :param mount_point: a new instance of MountPoint
        """
        mount_point.mount_point = data.mount_point
        mount_point.device_spec = data.device
        mount_point.reformat = data.reformat
        mount_point.format_type = data.format
        mount_point.format_options = data.mkfs_opts
        mount_point.mount_options = data.mount_opts

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        if not self.enabled:
            return

        data_list = []

        for mount_point in self.mount_points:
            mount_data = data.MountData()
            self._setup_mount_data(mount_data, mount_point)
            data_list.append(mount_data)

        data.mount.mount_points = data_list

    def _setup_mount_data(self, data, mount_point):
        """Set up kickstart mount data.

        :param data: a new instance of kickstart mount data
        :param mount_point: an instance of MountPoint
        """
        data.mount_point = mount_point.mount_point
        data.device = mount_point.device_spec
        data.reformat = mount_point.reformat
        data.format = mount_point.format_type
        data.mkfs_opts = mount_point.format_options
        data.mount_opts = mount_point.mount_options

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
    def mount_points(self):
        """A list of mount points."""
        return self._mount_points

    def set_mount_points(self, mount_points):
        """Set the list of mount points.

        :param mount_points: a list of instances of MountPoint
        """
        self._mount_points = mount_points
        self.mount_points_changed.emit()
        log.debug("Mount points are set to '%s'.", mount_points)

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
