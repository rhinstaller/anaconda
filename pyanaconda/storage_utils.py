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
from blivet.errors import SizeParamsError
from blivet.devicefactory import DEVICE_TYPE_LVM
from blivet.devicefactory import DEVICE_TYPE_BTRFS
from blivet.devicefactory import DEVICE_TYPE_MD

import logging
log = logging.getLogger("anaconda")

# should this and the get_supported_raid_levels go to blivet.devicefactory???
SUPPORTED_RAID_LEVELS = {DEVICE_TYPE_LVM: {"none", "raid0", "raid1"},
                         DEVICE_TYPE_MD: {"raid0", "raid1", "raid4", "raid5",
                                          "raid6", "raid10"},
                         DEVICE_TYPE_BTRFS: {"none", "raid0", "raid1",
                                             "raid10"},
                         # no device type for LVM VG
                         # VG: {"none", "raid0", "raid1", "raid4",
                         #      "raid5", "raid6", "raid10"},
                        }

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
        size = Size(spec=input_str)
    except (SizeParamsError, ValueError):
        return None
    else:
        # Minimium size for ui-created partitions is 1MiB.
        if size.convertTo(spec="MiB") < 1:
            size = Size(spec="1 MiB")

    return size

def get_supported_raid_levels(device_type):
    """Get supported RAID levels for the given device type."""

    return SUPPORTED_RAID_LEVELS.get(device_type, set())

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

