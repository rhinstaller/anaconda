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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from blivet.devices import PartitionDevice
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.errors.storage import ProtectedDeviceError
from pyanaconda.modules.storage.devicetree import DeviceTreeModule
from pyanaconda.modules.storage.partitioning.automatic.resizable_interface import \
    ResizableDeviceTreeInterface

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

    def is_device_resizable(self, device_name):
        """Is the specified device resizable?

        :param device_name: a name of the device
        :return: True or False
        """
        device = self._get_device(device_name)
        return device.resizable

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
            if isinstance(d, PartitionDevice)
            and not (d.is_extended and d.format.logical_partitions)
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

        if device.protected:
            raise ProtectedDeviceError(device_name)

        # The device size is small enough.
        if device.size <= size:
            log.debug("The size of %s is already %s.", device_name, device.size)
            return

        # Resize the device.
        log.debug("Shrinking a size of %s to %s.", device_name, size)
        aligned_size = device.align_target_size(size)
        self.storage.resize_device(device, aligned_size)

    def remove_device(self, device_name):
        """Remove a device after removing its dependent devices.

        If the device is protected, do nothing. If the device has
        protected children, just remove the unprotected ones.

        :param device_name: a name of the device
        """
        device = self._get_device(device_name)

        if device.protected:
            raise ProtectedDeviceError(device_name)

        # Only remove unprotected children if any protected.
        if any(d.protected for d in device.children):
            log.debug("Removing unprotected children of %s.", device_name)

            for child in (d for d in device.children if not d.protected):
                self.storage.recursive_remove(child)

            return

        # No protected children, remove the device
        log.debug("Removing device %s.", device_name)
        self.storage.recursive_remove(device)
