#
# DBus interface for the device tree handler
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
from pyanaconda.modules.common.constants.interfaces import DEVICE_TREE_HANDLER

__all__ = ["DeviceTreeHandlerInterface"]


@dbus_interface(DEVICE_TREE_HANDLER.interface_name)
class DeviceTreeHandlerInterface(InterfaceTemplate):
    """DBus interface for the device tree handler."""

    def SetupDevice(self, device_name: Str):
        """Open, or set up, a device.

        :param device_name: a name of the device
        """
        self.implementation.setup_device(device_name)

    def TeardownDevice(self, device_name: Str):
        """Close, or tear down, a device.

        :param device_name: a name of the device
        """
        self.implementation.teardown_device(device_name)

    def MountDevice(self, device_name: Str, mount_point: Str):
        """Mount a filesystem on the device.

        :param device_name: a name of the device
        :param mount_point: a path to the mount point
        """
        self.implementation.mount_device(device_name, mount_point)

    def UnmountDevice(self, device_name: Str, mount_point: Str):
        """Unmount a filesystem on the device.

        :param device_name: a name of the device
        :param mount_point: a path to the mount point
        """
        self.implementation.unmount_device(device_name, mount_point)

    def UnlockDevice(self, device_name: Str, passphrase: Str) -> Bool:
        """Unlock a device.

        :param device_name: a name of the device
        :param passphrase: a passphrase
        :return: True if success, otherwise False
        """
        return self.implementation.unlock_device(device_name, passphrase)

    def FindOpticalMedia(self) -> List[Str]:
        """Find all devices with mountable optical media.

        :return: a list of device names
        """
        return self.implementation.find_optical_media()

    def FindMountablePartitions(self) -> List[Str]:
        """Find all mountable partitions.

        :return: a list of device names
        """
        return self.implementation.find_mountable_partitions()
