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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from enum import Enum, unique

from pykickstart.constants import AUTOPART_TYPE_PLAIN, AUTOPART_TYPE_BTRFS, AUTOPART_TYPE_LVM, \
    AUTOPART_TYPE_LVM_THINP

from pyanaconda.core.constants import CLEAR_PARTITIONS_NONE, CLEAR_PARTITIONS_ALL, \
    CLEAR_PARTITIONS_LIST, CLEAR_PARTITIONS_LINUX, CLEAR_PARTITIONS_DEFAULT, BOOTLOADER_DISABLED, \
    BOOTLOADER_ENABLED, BOOTLOADER_SKIPPED, BOOTLOADER_TYPE_DEFAULT, BOOTLOADER_TYPE_EXTLINUX


@unique
class AutoPartitioningType(Enum):
    """The auto partitioning type."""
    PLAIN = AUTOPART_TYPE_PLAIN
    BTRFS = AUTOPART_TYPE_BTRFS
    LVM = AUTOPART_TYPE_LVM
    LVM_THINP = AUTOPART_TYPE_LVM_THINP


@unique
class BootloaderMode(Enum):
    """The bootloader mode."""
    DISABLED = BOOTLOADER_DISABLED
    ENABLED = BOOTLOADER_ENABLED
    SKIPPED = BOOTLOADER_SKIPPED


@unique
class BootloaderType(Enum):
    """The type of bootloader."""
    DEFAULT = BOOTLOADER_TYPE_DEFAULT
    EXTLINUX = BOOTLOADER_TYPE_EXTLINUX


@unique
class InitializationMode(Enum):
    """The disks initialization mode."""
    DEFAULT = CLEAR_PARTITIONS_DEFAULT
    CLEAR_NONE = CLEAR_PARTITIONS_NONE
    CLEAR_ALL = CLEAR_PARTITIONS_ALL
    CLEAR_LIST = CLEAR_PARTITIONS_LIST
    CLEAR_LINUX = CLEAR_PARTITIONS_LINUX
