#
# DBus interface for the device tree scheduler
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
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.interfaces import DEVICE_TREE_SCHEDULER
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.device_factory import (
    DeviceFactoryPermissions,
    DeviceFactoryRequest,
)
from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.modules.common.structures.storage import OSData
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.modules.storage.devicetree.devicetree_interface import (
    DeviceTreeInterface,
)

__all__ = ["DeviceTreeSchedulerInterface"]


@dbus_interface(DEVICE_TREE_SCHEDULER.interface_name)
class DeviceTreeSchedulerInterface(DeviceTreeInterface):
    """DBus interface for the device tree scheduler."""

    def IsDevice(self, device_id: Str) -> Bool:
        """Is the specified device in the device tree?

        It can recognize also hidden and incomplete devices.

        :param device_id: ID of the device
        :return: True or False
        """
        return self.implementation.is_device(device_id)

    def IsDeviceLocked(self, device_id: Str) -> Bool:
        """Is the specified device locked?

        :param device_id: ID of the device
        :return: True or False
        """
        return self.implementation.is_device_locked(device_id)

    def IsDeviceEditable(self, device_id: Str) -> Bool:
        """Is the specified device editable?

        :param device_id: ID of the device
        :return: True or False
        """
        return self.implementation.is_device_editable(device_id)

    def CheckCompleteness(self, device_id: Str) -> Structure:
        """Check that the specified device is complete.

        :param device_id: ID of the device
        :return: a validation report
        """
        return ValidationReport.to_structure(
            self.implementation.check_completeness(device_id)
        )

    def GetDefaultFileSystem(self) -> Str:
        """Get the default type of a filesystem.

        :return: a filesystem name
        """
        return self.implementation.get_default_file_system()

    def GetDefaultLUKSVersion(self) -> Str:
        """Get the default version of LUKS.

        :return: a version of LUKS
        """
        return self.implementation.get_default_luks_version()

    def GetContainerFreeSpace(self, container_name: Str) -> UInt64:
        """Get total free space in the specified container.

        :param container_name: device ID of the container
        :return: a size in bytes
        """
        return self.implementation.get_container_free_space(container_name)

    def GenerateSystemName(self) -> Str:
        """Generate a name of the new installation.

        :return: a translated string
        """
        return self.implementation.generate_system_name()

    def GenerateSystemData(self, boot_drive: Str) -> Structure:
        """Generate the new installation data.

        :param boot_drive: a name of the boot drive
        :return: a structure with data about the new installation
        """
        return OSData.to_structure(
            self.implementation.generate_system_data(boot_drive)
        )

    def GenerateDeviceName(self, mount_point: Str, format_type: Str) -> Str:
        """Get a suggestion for a device name.

        :param mount_point: a mount point
        :param format_type: a format type
        :return: a generated device name
        """
        return self.implementation.generate_device_name(mount_point, format_type)

    def GenerateContainerName(self) -> Str:
        """Get a suggestion for a container name.

        :return: a generated container name
        """
        return self.implementation.generate_container_name()

    def GenerateDeviceFactoryRequest(self, device_id: Str) -> Structure:
        """Generate a device factory request for the given device.

        The request will reflect the current state of the device.
        It can be modified and used to change the device.

        :param device_id: a device ID
        :return: a device factory request
        """
        return DeviceFactoryRequest.to_structure(
            self.implementation.generate_device_factory_request(device_id)
        )

    def GenerateDeviceFactoryPermissions(self, request: Structure) -> Structure:
        """Generate device factory permissions for the given request.

        The permissions will reflect which device attributes we are allowed
        to change in the requested device.

        :param request: a device factory request
        :return: device factory permissions
        """
        request = DeviceFactoryRequest.from_structure(request)
        permissions = self.implementation.generate_device_factory_permissions(request)
        return DeviceFactoryPermissions.to_structure(permissions)

    def GenerateContainerData(self, request: Structure) -> Structure:
        """Generate the container data for the device factory request.

        :param request: a device factory request
        :return: a device factory request
        """
        request = DeviceFactoryRequest.from_structure(request)
        self.implementation.generate_container_data(request)
        return DeviceFactoryRequest.to_structure(request)

    def UpdateContainerData(self, request: Structure, container_name: Str) -> Structure:
        """Update the container data in the device factory request.

        :param request: a device factory request
        :param container_name: a container name
        :return: a device factory request
        """
        request = DeviceFactoryRequest.from_structure(request)
        self.implementation.update_container_data(request, container_name)
        return DeviceFactoryRequest.to_structure(request)

    def CollectNewDevices(self, boot_drive: Str) -> List[Str]:
        """Get all new devices in the device tree.

        FIXME: Remove the boot drive option.

        :param boot_drive: a name of the boot drive
        :return: a list of device names
        """
        return self.implementation.collect_new_devices(boot_drive)

    def CollectUnusedDevices(self) -> List[Str]:
        """Collect all devices that are not used in existing or new installations.

        :return: a list of device names
        """
        return self.implementation.collect_unused_devices()

    def CollectUnusedMountPoints(self) -> List[Str]:
        """Collect mount points that can be assigned to a device.

        :return: a list of mount points
        """
        return self.implementation.collect_unused_mount_points()

    def CollectContainers(self, device_type: Int) -> List[Str]:
        """Collect containers of the given type.

        :param device_type: a device type
        :return: a list of container names
        """
        return self.implementation.collect_containers(device_type)

    def CollectSupportedSystems(self) -> List[Structure]:
        """Collect supported existing or new installations.

        :return: a list of data about found installations
        """
        return OSData.to_structure_list(
            self.implementation.collect_supported_systems()
        )

    def GetDeviceTypesForDevice(self, device_id: Str) -> List[Int]:
        """Collect supported device types for the given device.

        :param device_id: a device ID
        :return: a list of device types
        """
        return self.implementation.get_device_types_for_device(device_id)

    def GetFileSystemsForDevice(self, device_id: Str) -> List[Str]:
        """Get supported file system types for the given device.

        :param device_id: a device ID
        :return: a list of file system names
        """
        return self.implementation.get_file_systems_for_device(device_id)

    def GetSupportedRaidLevels(self, device_type: Int) -> List[Str]:
        """Get RAID levels for the specified device type.

        :param device_type: a type of the device
        :return: a list of RAID level names
        """
        return self.implementation.get_supported_raid_levels(device_type)

    def ValidateMountPoint(self, mount_point: Str) -> Structure:
        """Validate the given mount point.

        :param mount_point: a path to a mount point
        :return: a validation report
        """
        return ValidationReport.to_structure(
            self.implementation.validate_mount_point(mount_point)
        )

    def ValidateRaidLevel(self, raid_level: Str, num_members: Int) -> Structure:
        """Validate the given RAID level.

        :param raid_level: a RAID level name
        :param num_members: a number of members
        :return: a validation report
        """
        return ValidationReport.to_structure(
            self.implementation.validate_raid_level(raid_level, num_members)
        )

    def ValidateContainerName(self, name: Str) -> Structure:
        """Validate the given container name.

        :param name: a container name
        :return: a validation report
        """
        return ValidationReport.to_structure(
            self.implementation.validate_container_name(name)
        )

    def ValidateDeviceFactoryRequest(self, request: Structure) -> Structure:
        """Validate the given device factory request.

        :param request: a device factory request
        :return: a validation report
        """
        request = DeviceFactoryRequest.from_structure(request)
        report = self.implementation.validate_device_factory_request(request)
        return ValidationReport.to_structure(report)

    def AddDevice(self, request: Structure):
        """Add a new device to the storage model.

        :param request: a device factory request
        :raise: StorageConfigurationError if the device cannot be created
        """
        self.implementation.add_device(
            DeviceFactoryRequest.from_structure(request)
        )

    def ChangeDevice(self, request: Structure, original_request: Structure):
        """Change a device in the storage model.

        FIXME: Remove the original request from the arguments.

        :param request: a device factory request
        :param original_request: an original device factory request
        :raise: StorageConfigurationError if the device cannot be changed
        """
        self.implementation.change_device(
            DeviceFactoryRequest.from_structure(request),
            DeviceFactoryRequest.from_structure(original_request)
        )

    def ResetDevice(self, device_id: Str):
        """Reset the specified device in the storage model.

        FIXME: Merge with DestroyDevice.

        :param device_id: ID of the device
        :raise: StorageConfigurationError in case of failure
        """
        self.implementation.reset_device(device_id)

    def DestroyDevice(self, device_id: Str):
        """Destroy the specified device in the storage model.

        :param device_id: ID of the device
        :raise: StorageConfigurationError in case of failure
        """
        self.implementation.destroy_device(device_id)

    def SchedulePartitionsWithTask(self, request: Structure) -> ObjPath:
        """Schedule the partitioning actions.

        Generate the automatic partitioning configuration
        using the given request.

        :param: a partitioning request
        :return: a DBus path to a task
        """
        return TaskContainer.to_object_path(
            self.implementation.schedule_partitions_with_task(
                PartitioningRequest.from_structure(request)
            )
        )
