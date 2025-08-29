#
# DBus interface for the device tree viewer
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

from pyanaconda.modules.common.base.base_template import InterfaceTemplate
from pyanaconda.modules.common.constants.interfaces import DEVICE_TREE_VIEWER
from pyanaconda.modules.common.structures.storage import (
    DeviceActionData,
    DeviceData,
    DeviceFormatData,
    MountPointConstraintsData,
    OSData,
)

__all__ = ["DeviceTreeViewerInterface"]


@dbus_interface(DEVICE_TREE_VIEWER.interface_name)
class DeviceTreeViewerInterface(InterfaceTemplate):
    """DBus interface for the device tree viewer."""

    def GetRootDevice(self) -> Str:
        """Get the root device.

        :return: a name of the root device if any
        """
        return self.implementation.get_root_device()

    def GetDevices(self) -> List[Str]:
        """Get all devices in the device tree.

        :return: a list of device IDs
        """
        return self.implementation.get_devices()

    def GetDisks(self) -> List[Str]:
        """Get all disks in the device tree.

        Ignored disks are excluded, as are disks with no media present.

        :return: a list of device IDs
        """
        return self.implementation.get_disks()

    def GetMountPoints(self) -> Dict[Str, Str]:
        """Get all mount points in the device tree.

        :return: a dictionary of mount points and device IDs
        """
        return self.implementation.get_mount_points()

    def GetDeviceData(self, device_id: Str) -> Structure:
        """Get the device data.

        :param device_id: device ID
        :return: a structure with device data
        :raise: UnknownDeviceError if the device is not found
        """
        return DeviceData.to_structure(self.implementation.get_device_data(device_id))

    def GetFormatData(self, device_id: Str) -> Structure:
        """Get the device format data.

        Return data about a format of the specified device.

        For example: sda1

        :param device_id: ID of the device
        :return: a structure with format data
        """
        return DeviceFormatData.to_structure(self.implementation.get_format_data(device_id))

    def GetFormatTypeData(self, name: Str) -> Structure:
        """Get the format type data.

        Return data about the specified format type.

        For example: ext4

        :param name: a name of the format type
        :return: a structure with format data
        """
        return DeviceFormatData.to_structure(self.implementation.get_format_type_data(name))

    def GetActions(self) -> List[Structure]:
        """Get the device actions.

        :return: a list of structures with device action data
        """
        return DeviceActionData.to_structure_list(self.implementation.get_actions())

    def ResolveDevice(self, dev_spec: Str) -> Str:
        """Get the device matching the provided device specification.

        The spec can be anything from a device name (eg: 'sda3') to a
        device node path (eg: '/dev/mapper/fedora-root') to something
        like 'UUID=xyz-tuv-qrs' or 'LABEL=rootfs'.

        If no device is found, return an empty string.

        :param dev_spec: a string describing a block device
        :return: a device ID or an empty string
        """
        return self.implementation.resolve_device(dev_spec)

    def GetAncestors(self, device_ids: List[Str]) -> List[Str]:
        """Collect ancestors of the specified devices.

        Ancestors of a device don't include the device itself.
        The list is sorted by IDs of the devices.

        :param device_ids: a list of device names
        :return: a list of device IDs
        """
        return self.implementation.get_ancestors(device_ids)

    def GetSupportedFileSystems(self) -> List[Str]:
        """Get the supported types of filesystems.

        :return: a list of filesystem names
        """
        return self.implementation.get_supported_file_systems()

    def GetRequiredDeviceSize(self, required_space: UInt64) -> UInt64:
        """Get device size we need to get the required space on the device.

        :param required_space: a required space in bytes
        :return: a required device size in bytes
        """
        return self.implementation.get_required_device_size(required_space)

    def GetFileSystemFreeSpace(self, mount_points: List[Str]) -> UInt64:
        """Get total file system free space on the given mount points.

        :param mount_points: a list of mount points
        :return: a total size in bytes
        """
        return self.implementation.get_file_system_free_space(mount_points)

    def GetFreeSpaceForSystem(self, mount_points: List[Str]) -> UInt64:
        """Get total space available for system on the given mount points.

        Counts the free space available on empty formatted devices.

        :param mount_points: a list of mount points
        :return: a total size
        """
        return self.implementation.get_free_space_for_system(mount_points)

    def GetDiskFreeSpace(self, disk_ids: List[Str]) -> UInt64:
        """Get total free space on the given disks.

        Calculates free space available for use.

        :param disk_ids: a list of disk IDs
        :return: a total size in bytes
        """
        return self.implementation.get_disk_free_space(disk_ids)

    def GetDiskReclaimableSpace(self, disk_ids: List[Str]) -> UInt64:
        """Get total reclaimable space on the given disks.

        Calculates free space unavailable but reclaimable
        from existing partitions.

        :param disk_ids: a list of disk IDs
        :return: a total size in bytes
        """
        return self.implementation.get_disk_reclaimable_space(disk_ids)

    def GetDiskTotalSpace(self, disk_ids: List[Str]) -> UInt64:
        """Get total space on the given disks.

        :param disk_ids: a list of disk IDs
        :return: a total size in bytes
        """
        return self.implementation.get_disk_total_space(disk_ids)

    def GetFstabSpec(self, device_id: Str) -> Str:
        """Get the device specifier for use in /etc/fstab.

        :param device_id: ID of the device
        :return: a device specifier for /etc/fstab
        """
        return self.implementation.get_fstab_spec(device_id)

    def GetExistingSystems(self) -> List[Structure]:
        """Get existing GNU/Linux installations.

        :return: a list of data about found installations
        """
        return OSData.to_structure_list(self.implementation.get_existing_systems())

    def GetMountPointConstraints(self, disk_ids: List[Str]) -> List[Structure]:
        """Get list of constraints on mountpoints for the current platform

        Also provides hints if the partition is required or recommended.

        This includes mount points required to boot (e.g. /boot/efi, /boot)
        and the / partition which is always considered to be required.

        :param disk_ids: a list of disk IDs
        :return: a list of mount points with its constraints
        """
        return MountPointConstraintsData.to_structure_list(
            self.implementation.get_mount_point_constraints(disk_ids))
