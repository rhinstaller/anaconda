#
# Copyright (C) 2019 Red Hat, Inc.
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
import os
import stat

from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.payloads.source.mount_tasks import SetUpMountTask
from pyanaconda.payload.utils import mount


class SetUpLiveOSSourceTask(SetUpMountTask):
    """Task to setup installation source."""

    def __init__(self, live_partition, target_mount):
        super().__init__(target_mount)
        self._live_partition = live_partition

    @property
    def name(self):
        return "Set up Live OS Installation Source"

    def _do_mount(self):
        """Run live installation source setup."""
        # Mount the live device and copy from it instead of the overlay at /
        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        device_name = device_tree.ResolveDevice(self._live_partition)
        if not device_name:
            raise SourceSetupError("Failed to find liveOS image!")

        device_data = DeviceData.from_structure(device_tree.GetDeviceData(device_name))

        if not stat.S_ISBLK(os.stat(device_data.path)[stat.ST_MODE]):
            raise SourceSetupError("{} is not a valid block device".format(
                self._live_partition))
        rc = mount(device_data.path, self._target_mount, fstype="auto", options="ro")
        if rc != 0:
            raise SourceSetupError("Failed to mount the install tree")

        # FIXME: This should be done by the module
        # source = os.statvfs(self._target_mount)
        # self.source_size = source.f_frsize * (source.f_blocks - source.f_bfree)
