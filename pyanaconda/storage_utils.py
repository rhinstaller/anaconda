#
# Copyright (C) 2014  Red Hat, Inc.
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
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

"""UI-independent storage utility functions"""

import re
import locale

from contextlib import contextmanager

from blivet.size import Size
from blivet.devicefactory import DEVICE_TYPE_LVM
from blivet.devicefactory import DEVICE_TYPE_LVM_THINP
from blivet.devicefactory import DEVICE_TYPE_BTRFS
from blivet.devicefactory import DEVICE_TYPE_MD
from blivet.devicefactory import DEVICE_TYPE_PARTITION
from blivet.devicefactory import DEVICE_TYPE_DISK

from pyanaconda.i18n import N_
from pykickstart.constants import AUTOPART_TYPE_PLAIN, AUTOPART_TYPE_BTRFS
from pykickstart.constants import AUTOPART_TYPE_LVM, AUTOPART_TYPE_LVM_THINP

import logging
log = logging.getLogger("anaconda")

# should this and the get_supported_raid_levels go to blivet.devicefactory???
SUPPORTED_RAID_LEVELS = {DEVICE_TYPE_LVM: {"none", "raid0", "raid1"},
                         DEVICE_TYPE_LVM_THINP: {"none", "raid0", "raid1"},
                         DEVICE_TYPE_MD: {"raid0", "raid1", "raid4", "raid5",
                                          "raid6", "raid10"},
                         DEVICE_TYPE_BTRFS: {"none", "raid0", "raid1",
                                             "raid10"},
                         # no device type for LVM VG
                         # VG: {"none", "raid0", "raid1", "raid4",
                         #      "raid5", "raid6", "raid10"},
                        }

# TODO: all those constants and mappings should go to blivet
DEVICE_TEXT_LVM = N_("LVM")
DEVICE_TEXT_LVM_THINP = N_("LVM Thin Provisioning")
DEVICE_TEXT_MD = N_("RAID")
DEVICE_TEXT_PARTITION = N_("Standard Partition")
DEVICE_TEXT_BTRFS = N_("BTRFS")
DEVICE_TEXT_DISK = N_("Disk")

DEVICE_TEXT_MAP = {DEVICE_TYPE_LVM: DEVICE_TEXT_LVM,
                   DEVICE_TYPE_MD: DEVICE_TEXT_MD,
                   DEVICE_TYPE_PARTITION: DEVICE_TEXT_PARTITION,
                   DEVICE_TYPE_BTRFS: DEVICE_TEXT_BTRFS,
                   DEVICE_TYPE_LVM_THINP: DEVICE_TEXT_LVM_THINP,
                   DEVICE_TYPE_DISK: DEVICE_TEXT_DISK}

PARTITION_ONLY_FORMAT_TYPES = ("efi", "macefi", "prepboot", "biosboot", "appleboot")

MOUNTPOINT_DESCRIPTIONS = {"Swap": N_("The 'swap' area on your computer is used by the operating\n"
                                      "system when running low on memory."),
                           "Boot": N_("The 'boot' area on your computer is where files needed\n"
                                      "to start the operating system are stored."),
                           "Root": N_("The 'root' area on your computer is where core system\n"
                                      "files and applications are stored."),
                           "Home": N_("The 'home' area on your computer is where all your personal\n"
                                      "data is stored."),
                           "BIOS Boot": N_("The BIOS boot partition is required to enable booting\n"
                                           "from GPT-partitioned disks on BIOS hardware."),
                           "PReP Boot": N_("The PReP boot partition is required as part of the\n"
                                           "bootloader configuration on some PPC platforms.")
                            }

AUTOPART_CHOICES = ((N_("Standard Partition"), AUTOPART_TYPE_PLAIN),
                    (N_("BTRFS"), AUTOPART_TYPE_BTRFS),
                    (N_("LVM"), AUTOPART_TYPE_LVM),
                    (N_("LVM Thin Provisioning"), AUTOPART_TYPE_LVM_THINP))

AUTOPART_DEVICE_TYPES = {AUTOPART_TYPE_LVM: DEVICE_TYPE_LVM,
                         AUTOPART_TYPE_LVM_THINP: DEVICE_TYPE_LVM_THINP,
                         AUTOPART_TYPE_PLAIN: DEVICE_TYPE_PARTITION,
                         AUTOPART_TYPE_BTRFS: DEVICE_TYPE_BTRFS}

NAMED_DEVICE_TYPES = (DEVICE_TYPE_BTRFS, DEVICE_TYPE_LVM, DEVICE_TYPE_MD, DEVICE_TYPE_LVM_THINP)
CONTAINER_DEVICE_TYPES = (DEVICE_TYPE_LVM, DEVICE_TYPE_BTRFS, DEVICE_TYPE_LVM_THINP)

def size_from_input(input_str):
    """Get size from user's input"""

    if not input_str:
        # Nothing to parse
        return None

    # if no unit was specified, default to MiB. Assume that a string
    # ending with anything other than a digit has a unit suffix
    if re.search(r'[\d.%s]$' % locale.nl_langinfo(locale.RADIXCHAR), input_str):
        input_str += "MiB"

    try:
        size = Size(input_str)
    except ValueError:
        return None
    else:
        # Minimium size for ui-created partitions is 1MiB.
        if size.convertTo(spec="MiB") < 1:
            size = Size("1 MiB")

    return size

def get_supported_raid_levels(device_type):
    """Get supported RAID levels for the given device type."""

    return SUPPORTED_RAID_LEVELS.get(device_type, set())

def device_type_from_autopart(autopart_type):
    """Get device type matching the given autopart type."""

    return AUTOPART_DEVICE_TYPES.get(autopart_type, None)

class UIStorageFilter(logging.Filter):
    """Logging filter for UI storage events"""

    def filter(self, record):
        record.name = "storage.ui"
        return True

@contextmanager
def ui_storage_logger():
    """Context manager that applies the UIStorageFilter for its block"""

    storage_log = logging.getLogger("blivet")
    storage_filter = UIStorageFilter()
    storage_log.addFilter(storage_filter)
    yield
    storage_log.removeFilter(storage_filter)
