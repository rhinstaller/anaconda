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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base.base_template import InterfaceTemplate
from pyanaconda.modules.common.constants.interfaces import DEVICE_TREE_HANDLER
from pyanaconda.modules.common.containers import TaskContainer

__all__ = ["DeviceTreeHandlerInterface"]


@dbus_interface(DEVICE_TREE_HANDLER.interface_name)
class DeviceTreeHandlerInterface(InterfaceTemplate):
    """DBus interface for the device tree handler."""

    def MountDevice(self, device_id: Str, mount_point: Str, options: Str):
        """Mount a filesystem on the device.

        :param device_id: ID of the device
        :param mount_point: a path to the mount point
        :param options: a string with mount options or an empty string to use defaults
        :raise: MountFilesystemError if mount fails
        """
        self.implementation.mount_device(device_id, mount_point, options)

    def UnmountDevice(self, device_id: Str, mount_point: Str):
        """Unmount a filesystem on the device.

        :param device_id: ID of the device
        :param mount_point: a path to the mount point
        :raise: MountFilesystemError if unmount fails
        """
        self.implementation.unmount_device(device_id, mount_point)

    def UnlockDevice(self, device_id: Str, passphrase: Str) -> Bool:
        """Unlock a device.

        :param device_id: ID of the device
        :param passphrase: a passphrase
        :return: True if success, otherwise False
        """
        return self.implementation.unlock_device(device_id, passphrase)

    def FindUnconfiguredLUKS(self) -> List[Str]:
        """Find all unconfigured LUKS devices.

        Returns a list of devices that require to set up
        a passphrase to complete their configuration.

        :return: a list of device IDs
        """
        return self.implementation.find_unconfigured_luks()

    def SetDevicePassphrase(self, device_id: Str, passphrase: Str):
        """Set a passphrase of the unconfigured LUKS device.

        :param device_id: ID of the device
        :param passphrase: a passphrase
        """
        self.implementation.set_device_passphrase(device_id, passphrase)

    def GetDeviceMountOptions(self, device_id: Str) -> Str:
        """Get mount options of the specified device.

        :param device_id: ID of the device
        :return: a string with options
        """
        return self.implementation.get_device_mount_options(device_id)

    def SetDeviceMountOptions(self, device_id: Str, mount_options: Str):
        """Set mount options of the specified device.

        Specifies a free form string of options to be used when
        mounting the filesystem. This string will be copied into
        the /etc/fstab file of the installed system.

        :param device_id: ID of the device
        :param mount_options: a string with options
        """
        self.implementation.set_device_mount_options(device_id, mount_options)

    def FindDevicesWithTask(self) -> ObjPath:
        """Find new devices.

        The task will populate the device tree with new devices.

        :return: a path to the task
        """
        return TaskContainer.to_object_path(
            self.implementation.find_devices_with_task()
        )

    def FindOpticalMedia(self) -> List[Str]:
        """Find all devices with mountable optical media.

        :return: a list of device IDs
        """
        return self.implementation.find_optical_media()

    def FindMountablePartitions(self) -> List[Str]:
        """Find all mountable partitions.

        :return: a list of device IDs
        """
        return self.implementation.find_mountable_partitions()

    def FindExistingSystemsWithTask(self) -> ObjPath:
        """Find existing GNU/Linux installations.

        The task will update data about existing installations.

        :return: a path to the task
        """
        return TaskContainer.to_object_path(
            self.implementation.find_existing_systems_with_task()
        )

    def MountExistingSystemWithTask(self, device_id: Str, read_only: Bool) -> ObjPath:
        """Mount existing GNU/Linux installation.

        :param device_id: device ID of the root device
        :param read_only: mount the system in read-only mode
        :return: a path to the task
        """
        return TaskContainer.to_object_path(
            self.implementation.mount_existing_system_with_task(device_id, read_only)
        )
