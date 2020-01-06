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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.constants.interfaces import DEVICE_TREE_SCHEDULER
from pyanaconda.modules.common.structures.partitioning import DeviceFactoryRequest
from pyanaconda.modules.common.structures.storage import OSData
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.modules.storage.devicetree.devicetree_interface import DeviceTreeInterface

__all__ = ["DeviceTreeSchedulerInterface"]


@dbus_interface(DEVICE_TREE_SCHEDULER.interface_name)
class DeviceTreeSchedulerInterface(DeviceTreeInterface):
    """DBus interface for the device tree scheduler."""

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

    def GenerateDeviceFactoryRequest(self, device_name: Str) -> Structure:
        """Generate a device factory request for the given device.

        The request will reflect the current state of the device.
        It can be modified and used to change the device.

        :param device_name: a device name
        :return: a device factory request
        """
        return DeviceFactoryRequest.to_structure(
            self.implementation.generate_device_factory_request(device_name)
        )

    def GetPartitioned(self) -> List[Str]:
        """Get all partitioned devices in the device tree.

        :return: a list of device names
        """
        return self.implementation.get_partitioned()

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

    def CollectBootLoaderDevices(self, boot_drive: Str):
        """Collect the boot loader devices.

        FIXME: Remove the boot drive option.

        :param boot_drive: a name of the boot drive
        :return: a list of device names
        """
        return self.implementation.collect_boot_loader_devices(boot_drive)

    def CollectSupportedSystems(self) -> List[Structure]:
        """Collect supported existing or new installations.

        :return: a list of data about found installations
        """
        return OSData.to_structure_list(
            self.implementation.collect_supported_systems()
        )

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

    def AddDevice(self, request: Structure):
        """Add a new device to the storage model.

        :param request: a device factory request
        :raise: StorageError if the device cannot be created
        """
        self.implementation.add_device(
            DeviceFactoryRequest.from_structure(request)
        )
