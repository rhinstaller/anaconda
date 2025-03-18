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

from pyanaconda.core.constants import CLEAR_PARTITIONS_NONE, CLEAR_PARTITIONS_ALL, \
    CLEAR_PARTITIONS_LIST, CLEAR_PARTITIONS_LINUX, CLEAR_PARTITIONS_DEFAULT, BOOTLOADER_DISABLED, \
    BOOTLOADER_ENABLED, BOOTLOADER_SKIPPED, ISCSI_INTERFACE_UNSET, ISCSI_INTERFACE_DEFAULT,\
    ISCSI_INTERFACE_IFACENAME
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
    "Volume: partition pv.1 --ondisk=..'.\n"
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
