#
# Copyright (C) 2019  Red Hat, Inc.
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

from blivet.formats.disklabel import DiskLabel

from pyanaconda.bootloader.execution import BootloaderExecutor
from pyanaconda.modules.common.constants.objects import DISK_INITIALIZATION, AUTO_PARTITIONING, \
    MANUAL_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.storage.partitioning.automatic_execution import \
    AutomaticPartitioningExecutor
from pyanaconda.modules.storage.partitioning.custom_execution import CustomPartitioningExecutor
from pyanaconda.modules.storage.partitioning.manual_execution import ManualPartitioningExecutor

log = get_module_logger(__name__)

__all__ = ["do_kickstart_storage"]


def do_kickstart_storage(storage, data=None, partitioning=None):
    """Setup storage state from the kickstart data.

    :param storage: an instance of the Blivet's storage object
    :param data: an instance of kickstart data or None
    :param partitioning: an instance of the partitioning executor or None
    """
    log.debug("Setting up the storage from the kickstart data.")

    # Clear partitions.
    clear_partitions(storage)

    if not any(d for d in storage.disks
               if not d.format.hidden and not d.protected):
        return

    # Snapshot free space now, so that we know how much we had available.
    storage.create_free_space_snapshot()

    # Prepare the boot loader.
    BootloaderExecutor().execute(storage, dry_run=True)

    # Execute the partitioning.
    if not partitioning:
        partitioning = get_partitioning_executor(data)

    partitioning.execute(storage)

    # Set up the boot loader.
    storage.set_up_bootloader()


def get_partitioning_executor(data):
    """Get the executor of the enabled partitioning.

    :param data: an instance of kickstart data
    :return: an partitioning executor
    """
    if STORAGE.get_proxy(AUTO_PARTITIONING).Enabled:
        return AutomaticPartitioningExecutor()
    elif STORAGE.get_proxy(MANUAL_PARTITIONING).Enabled:
        return ManualPartitioningExecutor()
    else:
        return CustomPartitioningExecutor(data)


def clear_partitions(storage):
    """Clear partitions.

    :param storage: instance of the Blivet's storage object
    """
    disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)
    storage.config.clear_part_type = disk_init_proxy.InitializationMode
    storage.config.clear_part_disks = disk_init_proxy.DrivesToClear
    storage.config.clear_part_devices = disk_init_proxy.DevicesToClear
    storage.config.initialize_disks = disk_init_proxy.InitializeLabelsEnabled

    disk_label = disk_init_proxy.DefaultDiskLabel

    if disk_label and not DiskLabel.set_default_label_type(disk_label):
        log.warning("%s is not a supported disklabel type on this platform. "
                    "Using default disklabel %s instead.", disk_label,
                    DiskLabel.get_platform_label_types()[0])

    storage.clear_partitions()
