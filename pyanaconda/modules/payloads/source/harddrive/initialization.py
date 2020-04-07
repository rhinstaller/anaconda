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
import os.path

from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.source.utils import find_and_mount_device, \
    find_and_mount_iso_image

from pyanaconda.payload.utils import unmount
from pyanaconda.payload.image import verify_valid_installtree

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["SetUpHardDriveSourceTask", "TearDownHardDriveSourceTask"]


class TearDownHardDriveSourceTask(Task):
    """Task to teardown installation source."""

    def __init__(self, device_mount, iso_mount):
        super().__init__()
        self._device_mount = device_mount
        self._iso_mount = iso_mount

    @property
    def name(self):
        return "Tear down Hard drive installation source"

    def run(self):
        """Run live installation source un-setup."""
        log.debug("Unmounting Hard drive installation source")
        unmount(self._iso_mount)
        unmount(self._device_mount)


class SetUpHardDriveSourceTask(Task):
    """Task to setup installation source."""

    def __init__(self, device_mount, iso_mount, partition, directory):
        # TODO need better name for target_mount
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

        :return: path to the install tree
        :rtype: str
        """
        log.debug("Setting up Hard drive source")

        if not find_and_mount_device(self._partition, self._device_mount):
            raise SourceSetupError(
                "Could not mount device specified as {}".format(self._partition)
            )

        full_path_on_mounted_device = os.path.normpath(
            "{}/{}".format(self._device_mount, self._directory)
        )

        if find_and_mount_iso_image(full_path_on_mounted_device, self._iso_mount):
            return self._iso_mount
        elif verify_valid_installtree(full_path_on_mounted_device):
            return full_path_on_mounted_device

        raise SourceSetupError(
            "Nothing useful found for Hard drive ISO source at partition={} directory={}".format(
                self._partition, self._directory))
