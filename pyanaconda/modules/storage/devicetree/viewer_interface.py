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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.template import InterfaceTemplate
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.dbus.structure import get_structure
from pyanaconda.modules.common.constants.interfaces import DEVICE_TREE_VIEWER

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

        :return: a list of device names
        """
        return self.implementation.get_devices()

    def GetDisks(self) -> List[Str]:
        """Get all disks in the device tree.

        Ignored disks are excluded, as are disks with no media present.

        :return: a list of device names
        """
        return self.implementation.get_disks()

    def GetMountPoints(self) -> Dict[Str, Str]:
        """Get all mount points in the device tree.

        :return: a dictionary of mount points and device names
        """
        return self.implementation.get_mount_points()

    def GetDeviceData(self, name: Str) -> Structure:
        """Get the device data.

        :param name: a device name
        :return: a structure with device data
        :raise: UnknownDeviceError if the device is not found
        """
        return get_structure(self.implementation.get_device_data(name))

    def GetActions(self) -> List[Structure]:
        """Get the device actions.

        :return: a list of structures with device action data
        """
        return list(map(get_structure, self.implementation.get_actions()))

    def GetRequiredDeviceSize(self, required_space: UInt64) -> UInt64:
        """Get device size we need to get the required space on the device.

        :param required_space: a required space in bytes
        :return: a required device size in bytes
        """
        return self.implementation.get_required_device_size(required_space)

    def GetFileSystemFreeSpace(self,  mount_points: List[Str]) -> UInt64:
        """Get total file system free space on the given mount points.

        :param mount_points: a list of mount points
        :return: a total size in bytes
        """
        return self.implementation.get_file_system_free_space(mount_points)

    def GetDiskFreeSpace(self, disk_names: List[Str]) -> UInt64:
        """Get total free space on the given disks.

        Calculates free space available for use.

        :param disk_names: a list of disk names
        :return: a total size in bytes
        """
        return self.implementation.get_disk_free_space(disk_names)

    def GetDiskReclaimableSpace(self, disk_names: List[Str]) -> UInt64:
        """Get total reclaimable space on the given disks.

        Calculates free space unavailable but reclaimable
        from existing partitions.

        :param disk_names: a list of disk names
        :return: a total size in bytes
        """
        return self.implementation.get_disk_reclaimable_space(disk_names)
