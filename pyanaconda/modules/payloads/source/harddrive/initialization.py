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
import os.path

from collections import namedtuple

from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.source.utils import find_and_mount_device, \
    find_and_mount_iso_image, verify_valid_repository
from pyanaconda.payload.utils import unmount
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

__all__ = ["SetUpHardDriveSourceTask"]


SetupHardDriveResult = namedtuple("SetupHardDriveResult", ["install_tree_path", "iso_name"])


class SetUpHardDriveSourceTask(Task):
    """Task to setup installation source."""

    def __init__(self, device_mount, iso_mount, partition, directory):
        super().__init__()
        self._device_mount = device_mount
        self._iso_mount = iso_mount
        self._partition = partition
        self._directory = directory

    @property
    def name(self):
        return "Set up Hard drive installation source"

    def run(self):
        """Run Hard drive installation source setup.

        Always sets up two mount points: First for the device, and second for the ISO image or a
        bind for unpacked ISO. These depend on each other, and must be destroyed in the correct
        order again.

        :raise: SourceSetupError
        :return: named tuple with path to the install tree and name of ISO if set or empty string
        :rtype: SetupHardDriveResult instance
        """
        log.debug("Setting up Hard drive source")

        for mount_point in [self._device_mount, self._iso_mount]:
            if os.path.ismount(mount_point):
                raise SourceSetupError("The mount point {} is already in use.".format(
                    mount_point
                ))

        if not find_and_mount_device(self._partition, self._device_mount):
            raise SourceSetupError(
                "Could not mount device specified as {}".format(self._partition)
            )

        full_path_on_mounted_device = os.path.normpath(
            "{}/{}".format(self._device_mount, self._directory)
        )

        iso_name = find_and_mount_iso_image(full_path_on_mounted_device, self._iso_mount)

        if iso_name:
            log.debug("Using the ISO '%s' mounted at '%s'.", iso_name, self._iso_mount)
            return SetupHardDriveResult(self._iso_mount, iso_name)

        if verify_valid_repository(full_path_on_mounted_device):
            log.debug("Using the directory at '%s'.", full_path_on_mounted_device)
            return SetupHardDriveResult(full_path_on_mounted_device, "")

        # nothing found unmount the existing device
        unmount(self._device_mount)
        raise SourceSetupError(
            "Nothing useful found for Hard drive ISO source at partition={} directory={}".format(
                self._partition, self._directory))
