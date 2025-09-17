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
from blivet.errors import StorageError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.modules.storage.partitioning.automatic.noninteractive_partitioning import (
    NonInteractivePartitioningTask,
)
from pyanaconda.modules.storage.partitioning.manual.utils import reformat_device

log = get_module_logger(__name__)

__all__ = ["ManualPartitioningTask"]


class ManualPartitioningTask(NonInteractivePartitioningTask):
    """A task for the manual partitioning configuration."""

    def __init__(self, storage, requests):
        """Create a task.

        :param storage: an instance of Blivet
        :param requests: a list of requests
        """
        super().__init__(storage)
        self._requests = requests

    def _configure_partitioning(self, storage):
        """Configure the partitioning.

        :param storage: an instance of Blivet
        """
        log.debug("Setting up the mount points.")
        for mount_data in self._requests:
            self._setup_mount_point(storage, mount_data)

    def _setup_mount_point(self, storage, mount_data):
        """Set up a mount point.

        :param storage: an instance of the Blivet's storage object
        :param mount_data: an instance of MountPointRequest
        """
        device_spec = mount_data.device_spec
        reformat = mount_data.reformat
        format_type = mount_data.format_type
        mount_point = mount_data.mount_point

        if not reformat and not mount_point:
            # XXX empty request, ignore
            return

        if device_spec:
            device = storage.devicetree.get_device_by_device_id(device_spec)
        else:
            device = storage.devicetree.resolve_device(mount_data.ks_spec)
            if device:
                device_spec = device.device_id

        if device is None:
            raise StorageError(
                _("Unknown or invalid device '{}' specified").format(device_spec)
            )

        if reformat:
            requested_devices = dict(((req.device_spec, req.mount_point)
                                      for req in self._requests))
            device, mount_options = reformat_device(storage,
                                                    device,
                                                    format_type,
                                                    dependencies=requested_devices)
            if mount_options is not None:
                mount_data.mount_options = mount_options

        # add "mounted" swaps to fstab
        if device.format.type == "swap" and mount_point == "none":
            storage.add_fstab_swap(device)

        # only set mount points for mountable formats
        if device.format.mountable and mount_point and mount_point != "none":
            device.format.mountpoint = mount_point

        device.format.create_options = mount_data.format_options
        device.format.options = mount_data.mount_options
