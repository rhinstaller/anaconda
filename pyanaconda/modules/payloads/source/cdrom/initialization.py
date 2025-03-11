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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.payloads.source.mount_tasks import SetUpMountTask
from pyanaconda.modules.payloads.source.utils import is_valid_install_disk
from pyanaconda.payload.utils import mount, unmount

log = get_module_logger(__name__)

__all__ = ["SetUpCdromSourceTask"]


class SetUpCdromSourceTask(SetUpMountTask):
    """Task to set up a CD-ROM source."""

    @property
    def name(self):
        return "Set up a CD-ROM source"

    def _do_mount(self):
        """Set up an installation source.

        Try to discover installation media and mount that. Device used for booting (inst.stage2)
        has a priority.
        """
        log.debug("Trying to detect CD-ROM automatically")
        device_tree = STORAGE.get_proxy(DEVICE_TREE)

        device_candidates = self._get_device_candidate_list(device_tree)
        device_id = self._choose_installation_device(device_tree, device_candidates)

        if not device_id:
            raise SourceSetupError("Found no CD-ROM")

        return device_id

    def _get_device_candidate_list(self, device_tree):
        return device_tree.FindOpticalMedia()

    def _choose_installation_device(self, device_tree, devices_candidates):
        device_id = ""

        for dev_id in devices_candidates:
            try:
                device_data = DeviceData.from_structure(device_tree.GetDeviceData(dev_id))
                mount(device_data.path, self._target_mount, "iso9660", "ro")
            except OSError as e:
                log.debug("Failed to mount %s: %s", device_data.path, str(e))
                continue

            if is_valid_install_disk(self._target_mount):
                device_id = dev_id
                log.info("using CD-ROM device %s mounted at %s",
                         device_data.name, self._target_mount)
                break
            else:
                unmount(self._target_mount)

        return device_id
