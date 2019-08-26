#
# DBus structures for the partitioning data.
#
# Copyright (C) 2018 Red Hat, Inc.
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

from pyanaconda.core.constants import DEFAULT_AUTOPART_TYPE
from pyanaconda.dbus.structure import DBusData, generate_string_from_data
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["PartitioningRequest", "MountPointRequest", "DeviceFactoryRequest"]


class PartitioningRequest(DBusData):
    """Partitioning request data."""

    def __init__(self):
        self._partitioning_scheme = DEFAULT_AUTOPART_TYPE
        self._file_system_type = ""
        self._excluded_mount_points = []

        self._encrypted = False
        self._passphrase = ""
        self._cipher = ""
        self._luks_version = ""

        self._pbkdf = ""
        self._pbkdf_memory = 0
        self._pbkdf_time = 0
        self._pbkdf_iterations = 0

        self._escrow_certificate = ""
        self._backup_passphrase_enabled = False

    @property
    def partitioning_scheme(self) -> Int:
        """The partitioning scheme.

        Allowed values:
            0  Create regular partitions.
            1  Use the btrfs scheme.
            2  Use the lvm scheme.
            3  Use the lvm thinp scheme.

        :return: an number of the partitioning scheme
        """
        return self._partitioning_scheme

    @partitioning_scheme.setter
    def partitioning_scheme(self, scheme: Int):
        self._partitioning_scheme = scheme

    @property
    def file_system_type(self) -> Str:
        """Type of a file system used on the partitions.

        For example: ext4

        :return: a name of a file system type
        """
        return self._file_system_type

    @file_system_type.setter
    def file_system_type(self, value: Str):
        self._file_system_type = value

    @property
    def excluded_mount_points(self) -> List[Str]:
        """Excluded mount points.

        Don't create partitions for the excluded
        mount points during the partitioning.

        For example: /home, /boot, swap

        :return: a list of mount points
        """
        return self._excluded_mount_points

    @excluded_mount_points.setter
    def excluded_mount_points(self, mount_points: List[Str]):
        self._excluded_mount_points = mount_points

    @property
    def encrypted(self) -> Bool:
        """Should devices be encrypted?

        :return: True or False
        """
        return self._encrypted

    @encrypted.setter
    def encrypted(self, encrypted: Bool):
        self._encrypted = encrypted

    @property
    def passphrase(self) -> Str:
        """Passphrase for all encrypted devices.

        :return: a string with the passphrase
        """
        return self._passphrase

    @passphrase.setter
    def passphrase(self, value: Str):
        self._passphrase = value

    @property
    def cipher(self) -> Str:
        """Encryption algorithm used to encrypt the filesystem.

        For example: aes-xts-plain64

        :return: a name of an algorithm
        """
        return self._cipher

    @cipher.setter
    def cipher(self, cipher: Str):
        self._cipher = cipher

    @property
    def luks_version(self) -> Str:
        """Version of LUKS.

        Allowed values:
            luks1  Use the version 1.
            luks2  Use the version 2.

        :return: a string with the LUKS version
        """
        return self._luks_version

    @luks_version.setter
    def luks_version(self, version: Str):
        self._luks_version = version

    @property
    def pbkdf(self) -> Str:
        """The PBKDF algorithm.

        Set Password-Based Key Derivation Function (PBKDF)
        algorithm for LUKS keyslot.

        Example: 'argon2i'

        :return: a name of the algorithm
        """
        return self._pbkdf

    @pbkdf.setter
    def pbkdf(self, pbkdf: Str):
        self._pbkdf = pbkdf

    @property
    def pbkdf_memory(self) -> Int:
        """The memory cost for PBKDF."""
        return self._pbkdf_memory

    @pbkdf_memory.setter
    def pbkdf_memory(self, memory: Int):
        """Set the memory cost for PBKDF.

        :param memory: the memory cost in kilobytes
        """
        self._pbkdf_memory = memory

    @property
    def pbkdf_time(self) -> Int:
        """The time to spend with PBKDF processing.

        Sets the number of milliseconds to spend with PBKDF
        passphrase processing.

        :return: a number of milliseconds
        """
        return self._pbkdf_time

    @pbkdf_time.setter
    def pbkdf_time(self, time_ms: Int):
        self._pbkdf_time = time_ms

    @property
    def pbkdf_iterations(self) -> Int:
        """The number of iterations for PBKDF.

        Avoid PBKDF benchmark and set time cost (iterations) directly.

        :return: a number of iterations
        """
        return self._pbkdf_iterations

    @pbkdf_iterations.setter
    def pbkdf_iterations(self, iterations: Int):
        self._pbkdf_iterations = iterations

    @property
    def escrow_certificate(self) -> Str:
        """URL of an X.509 certificate.

        Store the data encryption keys of all encrypted volumes created during
        installation, encrypted using the certificate, as files in /root.

        :return: URL of an X.509 certificate
        """
        return self._escrow_certificate

    @escrow_certificate.setter
    def escrow_certificate(self, url: Str):
        self._escrow_certificate = url

    @property
    def backup_passphrase_enabled(self) -> Bool:
        """Is the backup passphrase enabled?

        In addition to storing the data encryption keys, generate a backup passphrase
        and add it to all encrypted volumes created during installation. Then store the
        passphrase, encrypted using the specified certificate as files in /root.

        :return: True or False
        """
        return self._backup_passphrase_enabled

    @backup_passphrase_enabled.setter
    def backup_passphrase_enabled(self, enabled: Bool):
        self._backup_passphrase_enabled = enabled

    def __repr__(self):
        """Generate a string representation."""
        return generate_string_from_data(
            self,
            skip=["passphrase"],
            add={"passphrase_set": bool(self.passphrase)}
        )


class MountPointRequest(DBusData):
    """Mount point request data."""

    def __init__(self):
        self._device_spec = ""
        self._mount_point = ""
        self._mount_options = ""
        self._reformat = False
        self._format_type = ""
        self._format_options = ""

    @property
    def device_spec(self) -> Str:
        """The block device to mount.

        :return: a device specification
        """
        return self._device_spec

    @device_spec.setter
    def device_spec(self, spec: Str):
        """Set the block device to mount."""
        self._device_spec = spec

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
    def mount_options(self) -> Str:
        """Mount options for /etc/fstab.

        Specifies a free form string of options to be used when
        mounting the filesystem. This string will be copied into
        the /etc/fstab file of the installed system.

        :return: a string with options
        """
        return self._mount_options

    @mount_options.setter
    def mount_options(self, options: Str):
        self._mount_options = options

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
        """New format of the device.

        For example: 'xfs'

        :return: a specification of the format
        """
        return self._format_type

    @format_type.setter
    def format_type(self, format_type: Str):
        self._format_type = format_type

    @property
    def format_options(self) -> Str:
        """Additional format options.

        Specifies additional parameters to be passed to the mkfs
        program that makes a filesystem on this partition.

        :return: a string with options
        """
        return self._format_options

    @format_options.setter
    def format_options(self, options: Str):
        self._format_options = options


class DeviceFactoryRequest(DBusData):
    """Device factory request data."""

    def __init__(self):
        self._device_type = 0
        self._device_spec = ""
        self._disks = []

        self._mount_point = ""
        self._format_type = ""
        self._label = ""
        self._luks_version = ""

        self._device_name = ""
        self._device_size = 0
        self._device_raid_level = ""
        self._device_encrypted = False

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
