#
# DBus structures for the device factory data.
#
# Copyright (C) 2020 Red Hat, Inc.
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

from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["DeviceFactoryPermissions", "DeviceFactoryRequest"]


class DeviceFactoryRequest(DBusData):
    """Device factory request data."""

    def __init__(self):
        self._device_type = 0
        self._device_spec = ""
        self._disks = []

        self._mount_point = ""
        self._reformat = False
        self._format_type = ""
        self._label = ""
        self._luks_version = ""

        self._device_name = ""
        self._device_size = 0
        self._device_raid_level = ""
        self._device_encrypted = False

        self._container_spec = ""
        self._container_name = ""
        self._container_size_policy = 0
        self._container_raid_level = ""
        self._container_encrypted = False

    @property
    def device_type(self) -> Int:
        """Type of the device.

        Supported values:
            0  LVM
            1  RAID
            2  Standard Partition
            3  Btrfs
            4  Disk
            5  LVM Thin Provisioning

        :return: a number of the type
        """
        return self._device_type

    @device_type.setter
    def device_type(self, value):
        self._device_type = value

    @property
    def device_spec(self) -> Str:
        """Device to use for adjustment.

        :return: a device specification
        """
        return self._device_spec

    @device_spec.setter
    def device_spec(self, spec: Str):
        self._device_spec = spec

    @property
    def disks(self) -> List[Str]:
        """Disks to use for allocation.

        :return: a list of disk names
        """
        return self._disks

    @disks.setter
    def disks(self, names):
        self._disks = names

    @property
    def mount_point(self) -> Str:
        """Mount point.

        Set where the device will be mounted.
        For example: '/', '/home', 'none'

        :return: a path to a mount point or 'none'
        """
        return self._mount_point

    @mount_point.setter
    def mount_point(self, mount_point: Str):
        self._mount_point = mount_point

    @property
    def reformat(self) -> Bool:
        """Should the device be reformatted?

        :return: True or False
        """
        return self._reformat

    @reformat.setter
    def reformat(self, reformat: Bool):
        self._reformat = reformat

    @property
    def format_type(self) -> Str:
        """Format of the device.

        For example: 'xfs'

        :return: a specification of the format
        """
        return self._format_type

    @format_type.setter
    def format_type(self, format_type: Str):
        self._format_type = format_type

    @property
    def label(self) -> Str:
        """Label of the file system.

        :return: a string
        """
        return self._label

    @label.setter
    def label(self, label: Str):
        self._label = label

    @property
    def luks_version(self) -> Str:
        """LUKS format version.

         Supported values:
            luks1
            luks2

        :return: a name of the version
        """
        return self._luks_version

    @luks_version.setter
    def luks_version(self, value: Str):
        self._luks_version = value

    @property
    def device_name(self) -> Str:
        """Name of the device.

        :return: a string
        """
        return self._device_name

    @device_name.setter
    def device_name(self, value):
        self._device_name = value

    @property
    def device_size(self) -> UInt64:
        """Size of the device

        :return: a size in bytes
        """
        return UInt64(self._device_size)

    @device_size.setter
    def device_size(self, size: UInt64):
        self._device_size = size

    @property
    def device_raid_level(self) -> Str:
        """RAID level of the device.

        For example: raid0

        :return: a string
        """
        return self._device_raid_level

    @device_raid_level.setter
    def device_raid_level(self, value):
        self._device_raid_level = value

    @property
    def device_encrypted(self) -> Bool:
        """Encrypt the device.

        :return: True or False
        """
        return self._device_encrypted

    @device_encrypted.setter
    def device_encrypted(self, value):
        self._device_encrypted = value

    @property
    def container_spec(self) -> Str:
        """Container to use for adjustment.

        :return: a container specification
        """
        return self._container_spec

    @container_spec.setter
    def container_spec(self, spec: Str):
        self._container_spec = spec

    @property
    def container_name(self) -> Str:
        """Name of the container.

        :return: a string
        """
        return self._container_name

    @container_name.setter
    def container_name(self, value):
        self._container_name = value

    @property
    def container_size_policy(self) -> Int64:
        """The container size policy.

        Supported values:
            -1  As large as possible
             0  Automatic size
            >0  Fixed size in bytes

        :return: a size policy
        """
        return Int64(self._container_size_policy)

    @container_size_policy.setter
    def container_size_policy(self, value):
        self._container_size_policy = value

    @property
    def container_raid_level(self) -> Str:
        """RAID level of the container.

        For example: raid0

        :return: a string
        """
        return self._container_raid_level

    @container_raid_level.setter
    def container_raid_level(self, value):
        self._container_raid_level = value

    @property
    def container_encrypted(self) -> Bool:
        """Encrypt the container.

        :return: True or False
        """
        return self._container_encrypted

    @container_encrypted.setter
    def container_encrypted(self, value):
        self._container_encrypted = value

    def reset_container_data(self):
        """Reset all container data."""
        self.container_spec = ""
        self.container_name = ""
        self.container_size_policy = 0
        self.container_raid_level = ""

        if self.container_encrypted:
            self.luks_version = ""

        self.container_encrypted = False


class DeviceFactoryPermissions(DBusData):
    """Device factory permissions."""

    def __init__(self):
        self._device_type = False
        self._disks = False

        self._mount_point = False
        self._reformat = False
        self._format_type = False
        self._label = False

        self._device_name = False
        self._device_size = False
        self._device_raid_level = False
        self._device_encrypted = False

        self._container_spec = False
        self._container_name = False
        self._container_size_policy = False
        self._container_raid_level = False
        self._container_encrypted = False

    @property
    def device_type(self) -> Bool:
        """Can the device type be changed?

        :return: True or False
        """
        return self._device_type

    @device_type.setter
    def device_type(self, permission):
        self._device_type = permission

    @property
    def disks(self) -> Bool:
        """Can the list of disks be changed?"""
        return self._disks

    @disks.setter
    def disks(self, permission):
        self._disks = permission

    @property
    def mount_point(self) -> Bool:
        """Can the mount point be changed?

        :return: True or False
        """
        return self._mount_point

    @mount_point.setter
    def mount_point(self, permission):
        self._mount_point = permission

    @property
    def reformat(self) -> Bool:
        """Can the device format be changed?

        :return: True or False
        """
        return self._reformat

    @reformat.setter
    def reformat(self, permission):
        self._reformat = permission

    @property
    def format_type(self) -> Bool:
        """Can the device format type be changed?

        :return: True or False
        """
        return self._format_type

    @format_type.setter
    def format_type(self, permission):
        self._format_type = permission

    @property
    def label(self) -> Bool:
        """Can the device label be changed?

        :return: True or False
        """
        return self._label

    @label.setter
    def label(self, permission):
        self._label = permission

    @property
    def device_name(self) -> Bool:
        """Can the device name be changed?

        :return: True or False
        """
        return self._device_name

    @device_name.setter
    def device_name(self, permission):
        self._device_name = permission

    @property
    def device_size(self) -> Bool:
        """Can the device size be changed?

        :return: True or False
        """
        return self._device_size

    @device_size.setter
    def device_size(self, permission):
        self._device_size = permission

    @property
    def device_raid_level(self) -> Bool:
        """Can the RAID level be changed?

        :return: True or False
        """
        return self._device_raid_level

    @device_raid_level.setter
    def device_raid_level(self, permission):
        self._device_raid_level = permission

    @property
    def device_encrypted(self) -> Bool:
        """Can the device encryption be changed?

        :return: True or False
        """
        return self._device_encrypted

    @device_encrypted.setter
    def device_encrypted(self, permission):
        self._device_encrypted = permission

    @property
    def container_spec(self) -> Bool:
        """Can the container be replaced?

        :return: True or False
        """
        return self._container_spec

    @container_spec.setter
    def container_spec(self, permission):
        self._container_spec = permission

    @property
    def container_name(self) -> Bool:
        """Can the container name be changed?

        :return: True or False
        """
        return self._container_name

    @container_name.setter
    def container_name(self, permission):
        self._container_name = permission

    @property
    def container_size_policy(self) -> Bool:
        """Can the container size policy be changed?

        :return: True or False
        """
        return self._container_size_policy

    @container_size_policy.setter
    def container_size_policy(self, permission):
        self._container_size_policy = permission

    @property
    def container_raid_level(self) -> Bool:
        """Can the container RAID level be changed?

        :return: True or False
        """
        return self._container_raid_level

    @container_raid_level.setter
    def container_raid_level(self, permission):
        self._container_raid_level = permission

    @property
    def container_encrypted(self) -> Bool:
        """Can the container encryption be changed?

        :return: True or False
        """
        return self._container_encrypted

    @container_encrypted.setter
    def container_encrypted(self, permission):
        self._container_encrypted = permission

    def can_replace_container(self):
        """Can we use a different container?"""
        return self._container_spec

    def can_modify_container(self):
        """Can we modify the current container?"""
        return self.container_name \
            or self.container_size_policy \
            or self.container_raid_level \
            or self.container_encrypted
