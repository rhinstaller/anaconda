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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
#  Author(s):  Vendula Poncova <vponcova@redhat.com>
#
from enum import Enum

from blivet.size import Size
from pykickstart.constants import (
    AUTOPART_TYPE_BTRFS,
    AUTOPART_TYPE_LVM,
    AUTOPART_TYPE_LVM_THINP,
    AUTOPART_TYPE_PLAIN,
)

from pyanaconda.core.configuration.base import Section
from pyanaconda.core.configuration.utils import split_name_and_attributes


class PartitioningScheme(Enum):
    """Type of the default partitioning scheme."""
    PLAIN = AUTOPART_TYPE_PLAIN
    BTRFS = AUTOPART_TYPE_BTRFS
    LVM = AUTOPART_TYPE_LVM
    LVM_THINP = AUTOPART_TYPE_LVM_THINP

    @classmethod
    def from_name(cls, value):
        """Convert the given value into a partitioning scheme."""
        try:
            member = cls.__members__[value]  # pylint: disable=unsubscriptable-object
            return member.value
        except KeyError:
            pass

        raise ValueError("'{}' is not a valid partitioning scheme".format(value))


class StorageSection(Section):
    """The Storage section."""

    @property
    def ibft(self):
        """Enable iBFT usage during the installation."""
        return self._get_option("ibft", bool)

    @property
    def multipath_friendly_names(self):
        """Use user friendly names for multipath devices.

        Tell multipathd to use user friendly names when naming devices
        during the installation.
        """
        return self._get_option("multipath_friendly_names", bool)

    @property
    def gpt_discoverable_partitions(self):
        """Use GPT discoverable partition type IDs, if possible.

        Tell Blivet to do this.
        """
        return self._get_option("gpt_discoverable_partitions", bool)

    @property
    def allow_imperfect_devices(self):
        """Do you want to allow imperfect devices?

        Imperfect devices are for example degraded mdraid arrays.
        This option should be enabled only in the rescue mode.
        """
        return self._get_option("allow_imperfect_devices", bool)

    @property
    def btrfs_compression(self):
        """BTRFS compression setting.

        Specifies the compression algorithm and level used when
        mounting Btrfs partitions. Defaults to None.

        For example: "zstd:1"
        """
        return self._get_option("btrfs_compression", str) or None

    @property
    def disk_label_type(self):
        """Default disk label type.

        Valid values:

          gpt  Prefer creation of GPT disk labels.
          mbr  Prefer creation of MBR disk labels.

        If no type is specified, we will use whatever Blivet uses by default.

        :return: a string with the disk label type
        """
        return self._get_option("disk_label_type", str)

    @property
    def file_system_type(self):
        """Default file system type.

        If no type is specified, we will use whatever Blivet uses by default.

        For example: xfs
        """
        return self._get_option("file_system_type", str)

    @property
    def default_scheme(self):
        """Default partitioning scheme.

        Valid values:

          0  PLAIN      Create standard partitions.
          1  BTRFS      Use the Btrfs scheme.
          2  LVM        Use the LVM scheme.
          3  LVM_THINP  Use LVM Thin Provisioning.

        :return: a partitioning scheme
        """
        return self._get_option("default_scheme", PartitioningScheme.from_name)

    @property
    def luks_version(self):
        """Default version of LUKS.

        Valid values:

          luks1  Use version 1 by default.
          luks2  Use version 2 by default.

        """
        value = self._get_option("luks_version", str)

        if value not in ("luks1", "luks2"):
            raise ValueError("Invalid value: {}".format(value))

        return value

    @property
    def default_partitioning(self):
        """Default partitioning.

        Returns a list of dictionaries with mount point attributes.
        The name of the mount point is represented by the attribute
        'name' in the dictionary representation.

        Valid attributes:

            name       The name of the mount point.
            size       The size of the mount point.
            min        The size will grow from min size to max size.
            max        The max size is unlimited by default.
            free       The required available space.
            btrfs      The mount point will be created only for the Btrfs scheme

        :return: a list of dictionaries with mount point attributes
        """
        return self._get_option("default_partitioning", self._convert_partitioning)

    def _convert_partitioning(self, value):
        """Convert a partitioning string into a list of dictionaries."""
        return list(map(self._convert_partitioning_line, value.strip().split("\n")))

    @classmethod
    def _convert_partitioning_line(cls, line):
        """Convert a partitioning line into a dictionary."""
        # Parse the line.
        name, raw_attrs = split_name_and_attributes(line)

        # Generate the dictionary.
        attrs = {"name": name}

        for name, value in raw_attrs.items():
            if not value and name in ("btrfs", ):
                # Handle a boolean attribute.
                attrs[name] = True
            elif value and name in ("size", "min", "max", "free"):
                # Handle a size attribute.
                attrs[name] = Size(value)
            else:
                # Handle an invalid attribute.
                raise ValueError("Invalid attribute: " + name)

        # Validate the dictionary.
        cls._validate_mount_point_attributes(attrs)

        return attrs

    @staticmethod
    def _validate_mount_point_attributes(attrs):
        """Validate the dictionary with mount point attributes."""
        if not attrs.get("name"):
            raise ValueError("The mount point is not specified.")

        if attrs.get("name") != "swap" and not attrs.get("name").startswith("/"):
            raise ValueError("The mount point is not valid.")

        if attrs.get("size") and attrs.get("min"):
            raise ValueError("Only one of the attributes 'size' and 'min' can be set.")

        if attrs.get("max") and not attrs.get("min"):
            raise ValueError("The attribute 'max' cannot be set without 'min'.")
