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
from blivet.errors import InconsistentParentSectorSize, StorageError
from blivet.size import Size
from dasbus.structure import compare_data

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.errors.configuration import StorageConfigurationError
from pyanaconda.modules.common.structures.device_factory import DeviceFactoryRequest
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.storage.constants import INCONSISTENT_SECTOR_SIZES_SUGGESTIONS
from pyanaconda.modules.storage.partitioning.interactive.utils import (
    change_encryption,
    destroy_device,
    get_device_factory_arguments,
    reformat_device,
    rename_container,
    resize_device,
    revert_reformat,
    validate_label,
)

log = get_module_logger(__name__)

__all__ = ["ChangeDeviceTask"]


class ChangeDeviceTask(Task):
    """A task for changing a device in the device tree."""

    def __init__(self, storage, device, request: DeviceFactoryRequest,
                 original_request: DeviceFactoryRequest):
        """Create a task.

        FIXME: Remove device and original request from the arguments.

        :param storage: an instance of Blivet
        :param device: a device to change
        :param request: a device factory request
        :param original_request: an original device factory request
        """
        super().__init__()
        self._storage = storage
        self._device = device
        self._request = request
        self._original_request = original_request

    @property
    def name(self):
        """Name of this task."""
        return "Change a device"

    def run(self):
        """Change a device in the device tree.

        :raise: StorageConfigurationError if the device cannot be changed
        """
        log.debug("Change device: %s", self._request)

        # Nothing to do. Skip.
        if compare_data(self._request, self._original_request):
            log.debug("Nothing to change.")
            return

        try:
            # Change the container.
            self._rename_container()

            # Change or replace the device.
            if not self._device.raw_device.exists:
                self._replace_device()
            else:
                self._change_device()

        except InconsistentParentSectorSize as e:
            self._handle_storage_error(e, "\n\n".join([
                _("Failed to change a device."),
                str(e).strip(),
                _(INCONSISTENT_SECTOR_SIZES_SUGGESTIONS)
            ]))
        except StorageError as e:
            self._handle_storage_error(e, str(e))

    def _handle_storage_error(self, exception, message):
        """Handle the storage error."""
        log.error("Failed to change a device: %s", message)
        raise StorageConfigurationError(message) from exception

    def _rename_container(self):
        """Rename the existing container."""
        container_spec = self._request.container_spec
        container_name = self._request.container_name

        # Nothing to do.
        if not container_spec or container_spec == container_name:
            return

        container = self._storage.devicetree.resolve_device(container_spec)

        # Container doesn't exist.
        if not container:
            return

        log.debug("Changing container name: %s", container_name)

        try:
            rename_container(self._storage, container, container_name)
        except StorageError as e:
            log.error("Invalid container name: %s", e)
            raise StorageError(str(e)) from e

    def _replace_device(self):
        """Replace the nonexistent device with a new one.

        If something has changed but the device does not exist,
        there is no need to schedule actions on the device. It
        is only necessary to create a new device object which
        reflects the current choices.
        """
        log.debug("Replacing a nonexistent device.")
        device = self._device

        if self._should_remove_device():
            # Remove the current device.
            destroy_device(self._storage, device)

            # We don't want to pass the device if we removed it.
            self._request.device_spec = ""

        # Create a new device.
        log.debug("Creating a new device.")
        arguments = get_device_factory_arguments(self._storage, self._request)
        device = self._storage.factory_device(**arguments)

        # Update the device.
        self._device = device

    def _should_remove_device(self):
        """Should we remove the current device?"""
        new_request = self._request
        old_request = self._original_request

        # Check the device type.
        if old_request.device_type != new_request.device_type:
            return True

        # Check the container name.
        if old_request.container_name and new_request.container_name != old_request.container_name:
            return True

        return False

    def _change_device(self):
        """Change the configuration of the existing device."""
        log.debug("Modifying an existing device.")

        self._revert_device_reformat()
        self._change_device_size()

        if self._should_reformat_device():
            self._change_device_encryption()
            self._change_device_format()
        else:
            self._change_device_label()
            self._change_device_mount_point()

        self._change_device_name()

    def _revert_device_reformat(self):
        """Revert reformat of the device."""
        if self._request.reformat:
            return

        log.debug("Reverting device reformat.")
        revert_reformat(self._storage, self._device)

    def _change_device_size(self):
        """Resize the device."""
        size = Size(self._request.device_size)
        original_size = Size(self._original_request.device_size)

        if size == original_size:
            return

        log.debug("Changing device size: %s", size)
        resize_device(self._storage, self._device, size, original_size)

    def _should_reformat_device(self):
        """Should we reformat the device?

        :return: True of False
        """
        if not self._request.reformat:
            return False

        if self._device.format.exists:
            return True

        if self._original_request.device_encrypted != self._request.device_encrypted:
            return True

        if self._original_request.luks_version != self._request.luks_version:
            return True

        if self._original_request.format_type != self._request.format_type:
            return True

        return False

    def _change_device_encryption(self):
        """Change the device encryption."""
        storage = self._storage
        device = self._device
        encrypted = self._request.device_encrypted
        luks_version = self._request.luks_version

        if self._original_request.device_encrypted != encrypted:
            log.debug("Changing device encryption: %s", encrypted)
            device = change_encryption(
                storage=storage,
                device=device,
                encrypted=encrypted,
                luks_version=luks_version
            )
        elif encrypted and self._original_request.luks_version != luks_version:
            log.debug("Changing LUKS version: %s", luks_version)

            # LUKS version cannot be easily changed,
            # so remove the current LUKS device.
            device = change_encryption(
                storage=storage,
                device=device,
                encrypted=False,
                luks_version=luks_version
            )

            # And create a new one with the requested
            # LUKS version.
            device = change_encryption(
                storage=storage,
                device=device,
                encrypted=True,
                luks_version=luks_version
            )

        self._device = device

    def _change_device_format(self):
        """Change the device format."""
        log.debug("Changing device format: %s", self._request.format_type)

        reformat_device(
            storage=self._storage,
            device=self._device,
            fstype=self._request.format_type,
            mountpoint=self._request.mount_point,
            label=self._request.label
        )

    def _change_device_label(self):
        """Change the device label."""
        label = self._request.label

        if self._original_request.label == label:
            return

        if not hasattr(self._device.format, "label"):
            log.warning("Cannot set a label to the current format.")
            return

        if self._device.format.exists:
            log.warning("Cannot relabel already existing file system.")
            return

        if validate_label(label, self._device.format):
            log.warning("Cannot set an invalid label.")
            return

        log.debug("Changing device label: %s", label)
        self._device.format.label = label

    def _change_device_mount_point(self):
        """Change the device mount point."""
        mount_point = self._request.mount_point

        if not mount_point:
            return

        if self._original_request.mount_point == mount_point:
            return

        log.debug("Changing device mount point: %s", mount_point)
        self._device.format.mountpoint = mount_point

    def _change_device_name(self):
        """Change the device name."""
        name = self._request.device_name
        original_name = self._original_request.device_name

        if name == original_name:
            return

        log.debug("Changing device name: %s", name)

        try:
            self._device.raw_device.name = name
        except ValueError as e:
            log.error("Invalid device name: %s", e)
            raise StorageError(str(e)) from e
