#
# The resizable device tree
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
from blivet.devices import PartitionDevice
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.storage.devicetree import DeviceTreeModule
from pyanaconda.modules.storage.partitioning.automatic.resizable_interface import \
    ResizableDeviceTreeInterface
from pyanaconda.modules.storage.partitioning.automatic.utils import shrink_device, remove_device

log = get_module_logger(__name__)

__all__ = ["ResizableDeviceTreeModule"]


class ResizableDeviceTreeModule(DeviceTreeModule):
    """The resizable device tree."""

    def for_publication(self):
        """Return a DBus representation."""
        return ResizableDeviceTreeInterface(self)

    def is_device_partitioned(self, device_name):
        """Is the specified device partitioned?

        :param device_name: a name of the device
        :return: True or False
        """
        device = self._get_device(device_name)
        return self._is_device_partitioned(device)

    @staticmethod
    def _is_device_partitioned(device):
        """Is the specified device partitioned?"""
        return device.is_disk and device.partitioned and device.format.supported

    def is_device_shrinkable(self, device_name):
        """Is the specified device shrinkable?

        :param device_name: a name of the device
        :return: True or False
        """
        device = self._get_device(device_name)
        return device.resizable and device.min_size < device.size

    def get_device_partitions(self, device_name):
        """Get partitions of the specified device.

        :param device_name: a name of the device
        :return: a list of device names
        """
        device = self._get_device(device_name)

        if not self._is_device_partitioned(device):
            return []

        return [
            d.name for d in device.children
            if not (
                isinstance(d, PartitionDevice)
                and d.is_extended
                and device.format.logical_partitions
            )
        ]

    def get_device_size_limits(self, device_name):
        """Get size limits of the given device.

        :param device_name: a name of the device
        :return: a tuple of min and max sizes in bytes
        """
        device = self._get_device(device_name)
        return device.min_size.get_bytes(), device.max_size.get_bytes()

    def shrink_device(self, device_name, size):
        """Shrink the size of the device.

        :param device_name: a name of the device
        :param size: a new size in bytes
        """
        size = Size(size)
        device = self._get_device(device_name)
        shrink_device(self.storage, device, size)

    def remove_device(self, device_name):
        """Remove a device after removing its dependent devices.

        If the device is protected, do nothing. If the device has
        protected children, just remove the unprotected ones.

        :param device_name: a name of the device
        """
        device = self._get_device(device_name)
        remove_device(self.storage, device)
