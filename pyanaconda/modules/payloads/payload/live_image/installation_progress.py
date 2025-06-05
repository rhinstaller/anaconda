#
# Copyright (C) 2021  Red Hat, Inc.
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
import os
import time

from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import THREAD_LIVE_PROGRESS
from pyanaconda.core.i18n import _
from pyanaconda.core.path import join_paths
from pyanaconda.core.threads import thread_manager
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.common.task.cancellable import Cancellable

log = get_module_logger(__name__)

__all__ = ["InstallationProgress"]


class InstallationProgress(Cancellable):
    """Progress monitor of the image installation."""

    def __init__(self, sysroot, installation_size, callback):
        """Create a new installation progress.

        :param sysroot: a path to the system root
        :param installation_size: a size of the installed payload
        :param callback: a function for the progress reporting
        """
        super().__init__()
        self._sysroot = sysroot
        self._installation_size = installation_size
        self._callback = callback
        self._thread_name = THREAD_LIVE_PROGRESS

    def __enter__(self):
        """Start to monitor the progress."""
        # Start the thread.
        thread_manager.add_thread(
            name=self._thread_name,
            target=self._monitor_progress
        )

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Stop to monitor the progress."""
        # Cancel the progress reporting.
        self.cancel()

        # Wait for the thread to finish.
        thread_manager.wait(self._thread_name)

    def _monitor_progress(self):
        """Monitor the amount of disk space used on the target and source."""
        log.debug("Installing %s.", Size(self._installation_size))

        # Force write everything to disk.
        self._callback(_("Synchronizing writes to disk"))
        os.sync()

        # Calculate the starting size used by the system.
        mount_points = self._get_mount_points_to_count()
        starting_size = self._calculate_used_size(mount_points)
        log.debug("Used %s by %s.", Size(starting_size), ", ".join(mount_points))

        pct = 0
        last_pct = -1

        while pct < 100 and not self.check_cancel():
            # Calculate the installed size used by the system.
            current_size = self._calculate_used_size(mount_points)
            installed_size = current_size - starting_size

            # Report the progress message.
            pct = min(int(100 * installed_size / self._installation_size), 100)

            if pct != last_pct:
                log.debug("Installed %s (%s%%)", Size(installed_size), pct)
                self._callback(_("Installing software {}%").format(pct))

            last_pct = pct
            time.sleep(0.777)

    def _get_mount_points_to_count(self):
        """Get mount points in the device tree, which should be queried for capacity.

        :return: a list of mount points
        """
        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        mount_points = device_tree.GetMountPoints()

        result = []
        counted_btrfs_volumes = []

        for path, device_id in mount_points.items():
            dev_data = DeviceData.from_structure(device_tree.GetDeviceData(device_id))

            if dev_data.type != "btrfs subvolume":
                # not btrfs subvolume, so just take it as is
                result.append(join_paths(self._sysroot, path))
            else:
                # For BTRFS, add only one mount-pointed subvolume per volume.
                # That's because statvfs reports free/used as aggregate across the whole volume.
                ancestors = device_tree.GetAncestors([device_id])
                for ancestor in ancestors:
                    anc_data = DeviceData.from_structure(device_tree.GetDeviceData(ancestor))
                    if anc_data.type == "btrfs volume" and ancestor not in counted_btrfs_volumes:
                        result.append(join_paths(self._sysroot, path))
                        counted_btrfs_volumes.append(ancestor)

        return result

    def _calculate_used_size(self, mount_points):
        """Calculate the total used size of the mount points.

        :return: a size in bytes
        """
        total = 0

        for path in mount_points:
            if not os.path.exists(path):
                continue

            stat = os.statvfs(path)
            total += stat.f_frsize * (stat.f_blocks - stat.f_bfree)

        return total
