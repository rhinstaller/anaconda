#
# Copyright (C) 2020 Red Hat, Inc.
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
from blivet import devicefactory
from blivet.errors import InconsistentParentSectorSize, StorageError
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.core.storage import DEVICE_TYPES, PARTITION_ONLY_FORMAT_TYPES
from pyanaconda.core.string import lower_ascii
from pyanaconda.modules.common.errors.configuration import StorageConfigurationError
from pyanaconda.modules.common.structures.device_factory import DeviceFactoryRequest
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.storage.constants import INCONSISTENT_SECTOR_SIZES_SUGGESTIONS
from pyanaconda.modules.storage.partitioning.interactive.utils import (
    get_container_raid_level_name,
    get_container_size_policy,
    get_device_factory_arguments,
)

log = get_module_logger(__name__)

__all__ = ["AddDeviceTask"]


class AddDeviceTask(Task):
    """A task for adding a new device to the device tree."""

    def __init__(self, storage, request: DeviceFactoryRequest):
        """Create a task.

        :param storage: an instance of Blivet
        :param request: a device factory request
        """
        super().__init__()
        self._storage = storage
        self._request = request

    @property
    def name(self):
        """Name of this task."""
        return "Add a device"

    def run(self):
        """Add a new device to the device tree.

        :raise: StorageConfigurationError if the device cannot be created
        """
        log.debug("Add device: %s", self._request)

        # Complete the device info.
        self._complete_device_factory_request(self._storage, self._request)

        try:
            # Trying to use a new container.
            self._add_device(self._storage, self._request, use_existing_container=False)
            return
        except InconsistentParentSectorSize as e:
            exception = e
            message = "\n\n".join([
                _("Failed to add a device."),
                str(e).strip(),
                _(INCONSISTENT_SECTOR_SIZES_SUGGESTIONS)
            ])
        except StorageError as e:
            exception = e
            message = str(e)

        try:
            # Trying to use an existing container.
            self._add_device(self._storage, self._request, use_existing_container=True)
            return
        except StorageError:
            # Ignore the second error.
            pass

        log.error("Failed to add a device: %s", message)
        raise StorageConfigurationError(message) from exception

    def _complete_device_factory_request(self, storage, request: DeviceFactoryRequest):
        """Complete the device factory request.

        :param storage: an instance of Blivet
        :param request: a device factory request
        """
        # Set the defaults.
        if not request.luks_version:
            request.luks_version = storage.default_luks_version

        # Set the file system type for the given mount point.
        if not request.format_type:
            request.format_type = storage.get_fstype(request.mount_point)

        # Fix the mount point.
        if lower_ascii(request.mount_point) in ("swap", "biosboot", "prepboot"):
            request.mount_point = ""

        # We should create a partition in some cases.
        # These devices should never be encrypted.
        if (request.mount_point.startswith("/boot") or
                request.format_type in PARTITION_ONLY_FORMAT_TYPES):
            request.device_type = DEVICE_TYPES.PARTITION
            request.device_encrypted = False

        # We shouldn't create swap on a thinly provisioned volume.
        if (request.format_type == "swap" and
                request.device_type == DEVICE_TYPES.LVM_THINP):
            request.device_type = DEVICE_TYPES.LVM

        # Encryption of thinly provisioned volumes isn't supported.
        if request.device_type == DEVICE_TYPES.LVM_THINP:
            request.device_encrypted = False

    def _add_device(self, storage, request: DeviceFactoryRequest, use_existing_container=False):
        """Add a device to the storage model.

        :param storage: an instance of Blivet
        :param request: a device factory request
        :param use_existing_container: should we use an existing container?
        :raise: StorageError if the device cannot be created
        """
        # Create the device factory.
        factory = devicefactory.get_device_factory(
            storage,
            device_type=request.device_type,
            size=Size(request.device_size) if request.device_size else None
        )

        # Find a container.
        container = factory.get_container(
            allow_existing=use_existing_container
        )

        if use_existing_container and not container:
            raise StorageError("No existing container found.")

        # Update the device info.
        if container:
            # Don't override user-initiated changes to a defined container.
            request.disks = [d.name for d in container.disks]
            request.container_encrypted = container.encrypted
            request.container_raid_level = get_container_raid_level_name(container)
            request.container_size_policy = get_container_size_policy(container)

            # The existing container has a name.
            if use_existing_container:
                request.container_name = container.name

            # The container is already encrypted
            if container.encrypted:
                request.device_encrypted = False

        # Create the device.
        dev_info = get_device_factory_arguments(storage, request)

        try:
            storage.factory_device(**dev_info)
        except StorageError as e:
            log.error("The device creation has failed: %s", e)
            raise
        except OverflowError as e:
            log.exception("Invalid partition size set: %s", str(e))
            raise StorageError("Invalid partition size set. Use a valid integer.") from None
