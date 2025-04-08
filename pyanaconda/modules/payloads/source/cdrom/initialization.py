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
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.storage import DeviceData
from pyanaconda.modules.payloads.source.mount_tasks import SetUpMountTask
from pyanaconda.modules.payloads.source.utils import is_valid_install_disk
from pyanaconda.payload.source.factory import SourceFactory, PayloadSourceTypeUnrecognized
from pyanaconda.payload.utils import mount, unmount, PayloadSetupError

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["SetUpCdromSourceTask"]


class SetUpCdromSourceTask(SetUpMountTask):
    """Task to setup installation source."""

    @property
    def name(self):
        return "Set up CD-ROM Installation Source"

    def _do_mount(self):
        """Run CD-ROM installation source setup.

        Try to discover installation media and mount that. Device used for booting (inst.stage2)
        has a priority.
        """
        log.debug("Trying to detect CD-ROM automatically")
        device_tree = STORAGE.get_proxy(DEVICE_TREE)

        device_candidates = self._get_device_candidate_list(device_tree)
        device_name = self._choose_installation_device(device_tree, device_candidates)

        if not device_name:
            raise SourceSetupError("Found no CD-ROM")

        return device_name

    def _get_device_candidate_list(self, device_tree):
        stage2_device = self._probe_stage2_for_cdrom(device_tree)
        device_candidates = device_tree.FindOpticalMedia()

        if stage2_device in device_candidates:
            device_candidates = [stage2_device] + device_candidates

        return device_candidates

    @staticmethod
    def _probe_stage2_for_cdrom(device_tree):
        # TODO: This is temporary method which should be moved closer to the inst.repo logic
        log.debug("Testing if inst.stage2 is a CDROM device")
        stage2_string = kernel_arguments.get("stage2")

        if not stage2_string:
            return None

        try:
            source = SourceFactory.parse_repo_cmdline_string(stage2_string)
        except PayloadSourceTypeUnrecognized:
            log.warning("Unknown stage2 method: %s", stage2_string)
            return None

        # We have HDD here because DVD ISO has inst.stage2=hd:LABEL=....
        # TODO: Let's return back support of inst.cdrom=<device> which should work based on the
        # documentation and use that as inst.stage2 parameter for Pungi
        if not source.is_harddrive:
            log.debug("Stage2 can't be used as source %s", stage2_string)
            return None

        # We can ignore source.path here because DVD ISOs are not using that.
        stage2_device = device_tree.ResolveDevice(source.partition)
        log.debug("Found possible stage2 default installation source %s", stage2_device)
        return stage2_device

    def _choose_installation_device(self, device_tree, devices_candidates):
        device_name = ""

        for dev_name in devices_candidates:
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

        return device_name
