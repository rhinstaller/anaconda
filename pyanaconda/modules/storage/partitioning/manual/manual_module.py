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
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.partitioning import MountPointRequest
from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.partitioning.constants import PartitioningMethod
from pyanaconda.modules.storage.partitioning.manual.manual_interface import \
    ManualPartitioningInterface
from pyanaconda.modules.storage.partitioning.manual.manual_partitioning import \
    ManualPartitioningTask
from pyanaconda.modules.storage.devicetree.utils import resolve_device

log = get_module_logger(__name__)


class ManualPartitioningModule(PartitioningModule):
    """The manual partitioning module."""

    def __init__(self):
        """Initialize the module."""
        super().__init__()
        self.requests_changed = Signal()
        self._requests = list()

    @property
    def partitioning_method(self):
        """Type of the partitioning method."""
        return PartitioningMethod.MANUAL

    def for_publication(self):
        """Return a DBus representation."""
        return ManualPartitioningInterface(self)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        requests = []

        for mount_data in data.mount.mount_points:
            request = MountPointRequest()
            request.mount_point = mount_data.mount_point
            request.device_spec = mount_data.device
            request.reformat = mount_data.reformat
            request.format_type = mount_data.format
            request.format_options = mount_data.mkfs_opts
            request.mount_options = mount_data.mount_opts
            requests.append(request)

        self.set_requests(requests)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data_list = []

        for request in self.requests:
            mount_data = data.MountData()
            mount_data.mount_point = request.mount_point
            mount_data.device = request.device_spec
            mount_data.reformat = request.reformat
            mount_data.format = request.format_type
            mount_data.mkfs_opts = request.format_options
            mount_data.mount_opts = request.mount_options
            data_list.append(mount_data)

        data.mount.mount_points = data_list

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

    def gather_requests(self):
        """Gather all mount point requests.

        Return mount point requests for all usable devices. If there is
        a defined request for the given device, we will use it. Otherwise,
        we will generate a new request.

        :return: a list of instances of MountPointRequest
        """
        available_requests = set(self.requests)
        requests = []

        for device in self._iterate_usable_devices():
            # Find an existing request.
            request = self._find_request_for_device(device, available_requests)

            # And use it only once.
            if request:
                available_requests.remove(request)
            # Otherwise, create a new request.
            else:
                request = self._create_request_for_device(device)

            # Add the request for this device.
            requests.append(request)

        return requests

    def _iterate_usable_devices(self):
        """Iterate over all usable devices.

        :return: an iterator over Blivet's devices
        """
        selected_disks = set(self._selected_disks)

        for device in self.storage.devicetree.devices:

            if not device.isleaf and not device.raw_device.type == "btrfs subvolume" and not device.raw_device.type == "btrfs volume":
                continue

            # Is the device usable?
            if device.protected or device.size == Size(0):
                continue

            # All device's disks have to be in selected disks.
            if selected_disks and not selected_disks.issuperset({d.name for d in device.disks}):
                continue

            yield device

    def _find_request_for_device(self, device, requests):
        """Find a mount point request for the given device.

        :param device: a Blivet's device object
        :param requests: a list of requests to search
        :return: an instance of MountPointRequest or None
        """
        for request in requests:
            if device is resolve_device(self.storage, request.device_spec):
                return request

        return None

    def _create_request_for_device(self, device):
        """Create a mount point request for the given device.

        :param device: a Blivet's device object
        :return: an instance of MountPointRequest
        """
        request = MountPointRequest()
        request.device_spec = self._btrfs_device_spec(device) or device.path
        request.format_type = device.format.type or ""
        request.reformat = False

        if device.format.mountable and device.format.mountpoint:
            request.mount_point = device.format.mountpoint

        return request

    def _btrfs_device_spec(self, device):
        """Get btrfs device specification of the device.

        Examples:
        'UUID=2252ec30-1fce-4f8e-bdef-c50c3a44ede4'
        'UUID=2252ec30-1fce-4f8e-bdef-c50c3a44ede4@root'

        :param device: a Blivet's device object
        :return: a btrfs device specification or None
        """
        device_spec = None
        if device.raw_device.type in ("btrfs volume", "btrfs subvolume"):

            uuid = self._get_btrfs_volume_uuid(device)
            if uuid:
                device_spec = "UUID={}".format(uuid)
            else:
                log.error("volume UUID of a btrfs device not found")

            if device.raw_device.type == "btrfs subvolume":
                device_spec = device_spec + "@{}".format(device.name)

        return device_spec

    def _get_btrfs_volume_uuid(self, device):
        """Get UUID of the volume of a btrfs device.

        :param device: a Blivet's device object
        :return: a btrfs volume UUID of the device or None
        """
        while True:
            if device.uuid is not None:
                return device.uuid
            if not device.parents:
                return None
            device = device.parents[0]
        return None

    def configure_with_task(self):
        """Schedule the partitioning actions."""
        return ManualPartitioningTask(
            self.storage,
            self.requests
        )
