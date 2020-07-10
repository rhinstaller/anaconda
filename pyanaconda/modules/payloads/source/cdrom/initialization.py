#
# Copyright (C) 2020 Red Hat, Inc.
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
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payloads.source.mount_tasks import SetUpMountTask
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.payload.utils import mount, unmount, PayloadSetupError
from pyanaconda.modules.payloads.source.utils import is_valid_install_disk

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["SetUpCdromSourceTask"]


class SetUpCdromSourceTask(SetUpMountTask):
    """Task to setup installation source."""

    @property
    def name(self):
        return "Set up CD-ROM Installation Source"

    def _do_mount(self):
        """Run CD-ROM installation source setup."""
        log.debug("Trying to detect CD-ROM automatically")

        device_tree = STORAGE.get_proxy(DEVICE_TREE)
        device_name = ""

        for dev_name in device_tree.FindOpticalMedia():
            try:
                device_data = DeviceData.from_structure(device_tree.GetDeviceData(dev_name))
                mount(device_data.path, self._target_mount, "iso9660", "ro")
            except PayloadSetupError as e:
                log.debug("Failed to mount %s: %s", dev_name, str(e))
                continue

            if is_valid_install_disk(self._target_mount):
                device_name = dev_name
                log.info("using CD-ROM device %s mounted at %s", dev_name, self._target_mount)
                break
            else:
                unmount(self._target_mount)

        if not device_name:
            raise SourceSetupError("Found no CD-ROM")

        return device_name
