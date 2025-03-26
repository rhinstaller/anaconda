#
# Private constants of the storage module.
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
from enum import Enum, unique

from pyanaconda.core.constants import (
    BOOTLOADER_DISABLED,
    BOOTLOADER_ENABLED,
    BOOTLOADER_SKIPPED,
    CLEAR_PARTITIONS_ALL,
    CLEAR_PARTITIONS_DEFAULT,
    CLEAR_PARTITIONS_LINUX,
    CLEAR_PARTITIONS_LIST,
    CLEAR_PARTITIONS_NONE,
    ISCSI_INTERFACE_DEFAULT,
    ISCSI_INTERFACE_IFACENAME,
    ISCSI_INTERFACE_UNSET,
)
from pyanaconda.core.i18n import N_

INCONSISTENT_SECTOR_SIZES_SUGGESTIONS = N_(
    "Workarounds for manual installations:\n"
    "* Select only the disks with the same sector size during manual "
    "installation in graphical or text mode.\n"
    "* When disks with inconsistent sector size are selected for "
    "the installation, restrict each created LVM Volume Group to use "
    "Physical Volumes with the same sector size. This can only be "
    "done in graphical mode in the Custom partitioning spoke.\n"
    "\n"
    "Workarounds for kickstart installations:\n"
    "* Restrict what disks are used for the partitioning by specifying "
    "'ignoredisk --drives=..' or 'ignoredisk --only-use=..'.\n"
    "* Specify what disks should be used for each created LVM Physical "
    "Volume: 'partition pv.1 --ondisk=..'.\n"
    "\n"
    "General workarounds:\n"
    "* Plain partitioning scheme can be used instead of LVM.\n"
    "* Some drives support re-configuration of sector sizes, for example "
    "by running 'hdparm --set-sector-size=<SIZE> <DEVICE>'.\n"
)


@unique
class BootloaderMode(Enum):
    """The bootloader mode."""
    DISABLED = BOOTLOADER_DISABLED
    ENABLED = BOOTLOADER_ENABLED
    SKIPPED = BOOTLOADER_SKIPPED


@unique
class InitializationMode(Enum):
    """The disks initialization mode."""
    DEFAULT = CLEAR_PARTITIONS_DEFAULT
    CLEAR_NONE = CLEAR_PARTITIONS_NONE
    CLEAR_ALL = CLEAR_PARTITIONS_ALL
    CLEAR_LIST = CLEAR_PARTITIONS_LIST
    CLEAR_LINUX = CLEAR_PARTITIONS_LINUX


@unique
class IscsiInterfacesMode(Enum):
    """The mode of interface used for iSCSI connections."""
    UNSET = ISCSI_INTERFACE_UNSET
    DEFAULT = ISCSI_INTERFACE_DEFAULT
    IFACENAME = ISCSI_INTERFACE_IFACENAME


class ZIPLSecureBoot(Enum):
    """The ZIPL Secure Boot options."""
    DISABLED = "0"
    ENABLED = "1"
    AUTO = "auto"


WINDOWS_PARTITION_TYPES = [
    "e3c9e316-0b5c-4db8-817d-f92df00215ae",  # Microsoft Reserved Partition
    "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7",  # Microsoft Basic Data
    "de94bba4-06d1-4d40-a16a-bfd50179d6ac",  # Windows Recovery Environment
    "af9b60a0-1431-4f62-bc68-3311714a69ad",  # Logical Disk Manager Data Partition
]
WINDOWS_PARTITION_TYPES_EXPECTED_FS = {
    "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7": ["ntfs", "refs"]
}

MACOS_PARTITION_TYPES = [
    "48465300-0000-11aa-aa11-00306543ecac",  # Apple HFS/HFS+
    "7c3457ef-0000-11aa-aa11-00306543ecac",  # Apple APFS
    "426f6f74-0000-11aa-aa11-00306543ecac",  # Apple Boot
]

EFI_PARTITION_TYPE = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
