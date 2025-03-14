#
# DBus interface for the resizable device tree
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

from pyanaconda.modules.common.constants.interfaces import DEVICE_TREE_RESIZABLE
from pyanaconda.modules.storage.devicetree.devicetree_interface import (
    DeviceTreeInterface,
)

__all__ = ["ResizableDeviceTreeInterface"]


@dbus_interface(DEVICE_TREE_RESIZABLE.interface_name)
class ResizableDeviceTreeInterface(DeviceTreeInterface):
    """DBus interface for the resizable device tree."""

    def IsDevicePartitioned(self, device_id: Str) -> Bool:
        """Is the specified device partitioned?

        :param device_id: device ID of the device
        :return: True or False
        """
        return self.implementation.is_device_partitioned(device_id)

    def IsDeviceShrinkable(self, device_id: Str) -> Bool:
        """Is the specified device shrinkable?

        :param device_id: device ID of the device
        :return: True or False
        """
        return self.implementation.is_device_shrinkable(device_id)

    def GetDevicePartitions(self, device_id: Str) -> List[Str]:
        """Get partitions of the specified device.

        :param device_id: device ID of the device
        :return: a list of device IDs
        """
        return self.implementation.get_device_partitions(device_id)

    def GetDeviceSizeLimits(self, device_id: Str) -> Tuple[UInt64, UInt64]:
        """Get size limits of the given device.

        :param device_id: device ID of the device
        :return: a tuple of min and max sizes in bytes
        """
        return self.implementation.get_device_size_limits(device_id)

    def ShrinkDevice(self, device_id: Str, size: UInt64):
        """Shrink the size of the device.

        :param device_id: device ID of the device
        :param size: a new size in bytes
        """
        self.implementation.shrink_device(device_id, size)

    def RemoveDevice(self, device_id: Str):
        """Remove a device after removing its dependent devices.

        If the device is protected, do nothing. If the device has
        protected children, just remove the unprotected ones.

        :param device_id: device ID of the device
        """
        self.implementation.remove_device(device_id)
