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
from blivet.errors import StorageError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import PARTITIONING_METHOD_AUTOMATIC, BOOTLOADER_DRIVE_UNSET
from pyanaconda.errors import errorHandler as error_handler, ERROR_RAISE
from pyanaconda.modules.common.constants.objects import DISK_SELECTION, BOOTLOADER, DEVICE_TREE, \
    DISK_INITIALIZATION
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.task import sync_run_task
from pyanaconda.storage.utils import filter_disks_by_names

log = get_module_logger(__name__)


def find_partitioning():
    """Find a partitioning to use or create a new one.

    :return: a proxy of a partitioning module
    """
    storage_proxy = STORAGE.get_proxy()
    object_paths = storage_proxy.CreatedPartitioning

    if object_paths:
        # Choose the last created partitioning.
        object_path = object_paths[-1]
    else:
        # Or create the automatic partitioning.
        object_path = storage_proxy.CreatePartitioning(
            PARTITIONING_METHOD_AUTOMATIC
        )

    return STORAGE.get_proxy(object_path)


def reset_storage(scan_all=False, retry=True):
    """Reset the storage model.

    :param scan_all: should we scan all devices in the system?
    :param retry: should we allow to retry the reset?
    """
    # Clear the exclusive disks to scan all devices in the system.
    if scan_all:
        disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
        disk_select_proxy.SetExclusiveDisks([])

    # Scan the devices.
    storage_proxy = STORAGE.get_proxy()

    while True:
        try:
            task_path = storage_proxy.ScanDevicesWithTask()
            task_proxy = STORAGE.get_proxy(task_path)
            sync_run_task(task_proxy)
        except StorageError as e:
            # Is the retry allowed?
            if not retry:
                raise
            # Does the user want to retry?
            elif error_handler.cb(e) == ERROR_RAISE:
                raise
            # Retry the storage reset.
            else:
                continue
        else:
            # No need to retry.
            break

    # Reset the partitioning.
    storage_proxy.ResetPartitioning()


def reset_bootloader():
    """Reset the bootloader."""
    bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)
    bootloader_proxy.SetDrive(BOOTLOADER_DRIVE_UNSET)


def select_all_disks_by_default():
    """Select all disks for the partitioning by default.

    It will select all disks for the partitioning if there are
    no disks selected. Kickstart uses all the disks by default.

    :return: a list of selected disks
    """
    disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
    selected_disks = disk_select_proxy.SelectedDisks
    ignored_disks = disk_select_proxy.IgnoredDisks

    if not selected_disks:
        # Get all disks.
        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        all_disks = device_tree.GetDisks()

        # Select all disks.
        selected_disks = [d for d in all_disks if d not in ignored_disks]
        disk_select_proxy.SetSelectedDisks(selected_disks)
        log.debug("Selecting all disks by default: %s", ",".join(selected_disks))

    return selected_disks


def apply_disk_selection(selected_names):
    """Apply the disks selection.

    :param selected_names: a list of selected disk names
    """
    device_tree = STORAGE.get_proxy(DEVICE_TREE)

    # Get disks.
    disks = set(device_tree.GetDisks())
    selected_disks = filter_disks_by_names(disks, selected_names)

    # Get ancestors.
    ancestors_names = device_tree.GetAncestors(selected_disks)
    ancestors_disks = filter_disks_by_names(disks, ancestors_names)

    # Set the disks to select.
    disk_select_proxy = STORAGE.get_proxy(DISK_SELECTION)
    disk_select_proxy.SetSelectedDisks(selected_names + ancestors_disks)

    # Set the drives to clear.
    disk_init_proxy = STORAGE.get_proxy(DISK_INITIALIZATION)
    disk_init_proxy.SetDrivesToClear(selected_names)
