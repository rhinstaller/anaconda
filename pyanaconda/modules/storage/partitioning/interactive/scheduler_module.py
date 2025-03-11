#
# The device tree scheduler
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
from blivet import devicefactory
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.modules.storage.devicetree import DeviceTreeModule
from pyanaconda.modules.storage.partitioning.interactive import utils
from pyanaconda.modules.storage.partitioning.interactive.add_device import AddDeviceTask
from pyanaconda.modules.storage.partitioning.interactive.change_device import (
    ChangeDeviceTask,
)
from pyanaconda.modules.storage.partitioning.interactive.interactive_partitioning import (
    InteractiveAutoPartitioningTask,
)
from pyanaconda.modules.storage.partitioning.interactive.scheduler_interface import (
    DeviceTreeSchedulerInterface,
)

log = get_module_logger(__name__)

__all__ = ["DeviceTreeSchedulerModule"]


class DeviceTreeSchedulerModule(DeviceTreeModule):
    """The device tree scheduler."""

    def for_publication(self):
        """Return a DBus representation."""
        return DeviceTreeSchedulerInterface(self)

    def is_device(self, device_id):
        """Is the specified device in the device tree?

        It can recognize also hidden and incomplete devices.

        :param device_id: ID of the device
        :return: True or False
        """
        device = self.storage.devicetree.get_device_by_device_id(
            device_id, hidden=True, incomplete=True
        )

        return device is not None

    def is_device_locked(self, device_id):
        """Is the specified device locked?

        :param device_id: ID of the device
        :return: True or False
        """
        device = self._get_device(device_id)
        return device.format.type == "luks" and device.format.exists and not device.children

    def is_device_editable(self, device_id):
        """Is the specified device editable?

        :param device_id: ID of the device
        :return: True or False
        """
        device = self._get_device(device_id)
        return devicefactory.get_device_type(device) is not None

    def check_completeness(self, device_id):
        """Check that the specified device is complete.

        :param device_id: ID of the device
        :return: a validation report
        """
        report = ValidationReport()
        device = self._get_device(device_id)
        message = utils.check_device_completeness(device)

        if message:
            report.error_messages.append(message)

        return report

    def get_default_file_system(self):
        """Get the default type of a filesystem.

        :return: a filesystem name
        """
        return self.storage.default_fstype

    def get_default_luks_version(self):
        """Get the default version of LUKS.

        :return: a version of LUKS
        """
        return self.storage.default_luks_version

    def get_container_free_space(self, container_id):
        """Get total free space in the specified container.

        :param container_id: a device ID of the container
        :return: a size in bytes
        """
        container = self._get_device(container_id)
        return Size(getattr(container, "free_space", 0)).get_bytes()

    def generate_system_name(self):
        """Generate a name of the new installation.

        :return: a translated string
        """
        return utils.get_new_root_name()

    def generate_system_data(self, boot_drive):
        """Generate the new installation data.

        :param boot_drive: a name of the boot drive
        :return: an instance of OSData
        """
        root = utils.create_new_root(self.storage, boot_drive)
        return self._get_os_data(root)

    def generate_device_name(self, mount_point, format_type):
        """Get a suggestion for a device name.

        :param mount_point: a mount point
        :param format_type: a format type
        :return: a generated device name
        """
        return self.storage.suggest_device_name(
            mountpoint=mount_point,
            swap=bool(format_type == "swap")
        )

    def generate_container_name(self):
        """Get a suggestion for a container name.

        :return: a generated container name
        """
        return self._storage.suggest_container_name()

    def generate_device_factory_request(self, device_id):
        """Generate a device factory request for the given device.

        The request will reflect the current state of the device.
        It can be modified and used to change the device.

        :param device_id: a device ID
        :return: a device factory request
        """
        device = self._get_device(device_id)
        return utils.generate_device_factory_request(self.storage, device)

    def generate_device_factory_permissions(self, request):
        """Generate device factory permissions for the given request.

        The permissions will reflect which device attributes we are allowed
        to change in the requested device.

        :param request: a device factory request
        :return: device factory permissions
        """
        return utils.generate_device_factory_permissions(self.storage, request)

    def generate_container_data(self, request):
        """Generate the container data for the device factory request.

        :param request: a device factory request
        """
        utils.generate_container_data(self.storage, request)

    def update_container_data(self, request, container_name):
        """Update the container data in the device factory request.

        :param request: a device factory request
        :param container_name: a container name
        """
        utils.update_container_data(self.storage, request, container_name)

    def collect_new_devices(self, boot_drive):
        """Get all new devices in the device tree.

        FIXME: Remove the boot drive option.

        :param boot_drive: a name of the boot drive
        :return: a list of device IDs
        """
        return [d.device_id for d in utils.collect_new_devices(self.storage, boot_drive)]

    def collect_unused_devices(self):
        """Collect all devices that are not used in existing or new installations.

        :return: a list of device IDs
        """
        return [d.device_id for d in utils.collect_unused_devices(self.storage)]

    def collect_unused_mount_points(self):
        """Collect mount points that can be assigned to a device.

        :return: a list of mount points
        """
        return [m for m in utils.collect_mount_points() if m not in self.storage.mountpoints]

    def collect_containers(self, device_type):
        """Collect containers of the given type.

        :param device_type: a device type
        :return: a list of container IDs
        """
        return [c.device_id for c in utils.collect_containers(self.storage, device_type)]

    def collect_supported_systems(self):
        """Collect supported existing or new installations.

        :return: a list of data about found installations
        """
        return list(map(self._get_os_data, utils.collect_roots(self.storage)))

    def get_device_types_for_device(self, device_id):
        """Collect supported device types for the given device.

        :param device_id: a device ID
        :return: a list of device types
        """
        device = self._get_device(device_id)
        return utils.collect_device_types(device)

    def get_file_systems_for_device(self, device_id):
        """Get supported file system types for the given device.

        :param device_id: a device ID
        :return: a list of file system names
        """
        device = self._get_device(device_id)
        return utils.collect_file_system_types(device)

    def get_supported_raid_levels(self, device_type):
        """Get RAID levels for the specified device type.

        :param device_type: a type of the device
        :return: a list of RAID level names
        """
        return sorted([level.name for level in utils.get_supported_raid_levels(device_type)])

    def validate_mount_point(self, mount_point):
        """Validate the given mount point.

        :param mount_point: a path to a mount point
        :return: a validation report
        """
        report = ValidationReport()
        mount_points = self.storage.mountpoints.keys()
        error = utils.validate_mount_point(mount_point, mount_points)

        if error:
            report.error_messages.append(error)

        return report

    def validate_raid_level(self, raid_level, num_members):
        """Validate the given RAID level.

        :param raid_level: a RAID level name
        :param num_members: a number of members
        :return: a validation report
        """
        report = ValidationReport()
        raid_level = utils.get_raid_level_by_name(raid_level)
        error = utils.validate_raid_level(raid_level, num_members)

        if error:
            report.error_messages.append(error)

        return report

    def validate_container_name(self, name):
        """Validate the given container name.

        :param name: a container name
        :return: a validation report
        """
        report = ValidationReport()
        error = utils.validate_container_name(self.storage, name)

        if error:
            report.error_messages.append(error)

        return report

    def validate_device_factory_request(self, request):
        """Validate the given device factory request.

        :param request: a device factory request
        :return: a validation report
        """
        report = ValidationReport()
        error = utils.validate_device_factory_request(self.storage, request)

        if error:
            report.error_messages.append(error)

        return report

    def add_device(self, request):
        """Add a new device to the storage model.

        :param request: a device factory request
        :raise: StorageConfigurationError if the device cannot be created
        """
        task = AddDeviceTask(self.storage, request)
        task.run()

    def change_device(self, request, original_request):
        """Change a device in the storage model.

        FIXME: Remove the original request from the arguments.

        :param request: a device factory request
        :param original_request: an original device factory request
        :raise: StorageConfigurationError if the device cannot be changed
        """
        device = self._get_device(request.device_spec)
        task = ChangeDeviceTask(self.storage, device, request, original_request)
        task.run()

    def reset_device(self, device_id):
        """Reset the specified device in the storage model.

        FIXME: Merge with destroy_device.

        :param device_id: ID of the device
        :raise: StorageConfigurationError in case of failure
        """
        device = self._get_device(device_id)
        utils.reset_device(self.storage, device)

    def destroy_device(self, device_id):
        """Destroy the specified device in the storage model.

        :param device_id: ID of the device
        :raise: StorageConfigurationError in case of failure
        """
        device = self._get_device(device_id)
        utils.destroy_device(self.storage, device)

    def schedule_partitions_with_task(self, request):
        """Schedule the partitioning actions.

        Generate the automatic partitioning configuration
        using the given request.

        :param: a partitioning request
        :return: a task
        """
        return InteractiveAutoPartitioningTask(self.storage, request)
