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
import copy
import os.path
from collections import namedtuple

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.path import join_paths
from pyanaconda.core.payload import parse_hdd_url
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.source.utils import (
    find_and_mount_device,
    find_and_mount_iso_image,
    verify_valid_repository,
)
from pyanaconda.payload.utils import unmount

__all__ = ["SetUpHardDriveSourceTask", "SetupHardDriveResult"]

log = get_module_logger(__name__)

SetupHardDriveResult = namedtuple(
    "SetupHardDriveResult",
    ["repository", "iso_file"]
)


class SetUpHardDriveSourceTask(Task):
    """Task to set up the hard drive installation source."""

    def __init__(self, configuration, device_mount, iso_mount):
        """Create a new task.

        :param RepoConfigurationData configuration: a source data
        :param device_mount: a mount point for a device
        :param iso_mount: a mount point for an iso
        """
        super().__init__()
        self._configuration = configuration
        self._device_mount = device_mount
        self._iso_mount = iso_mount

    @property
    def name(self):
        return "Set up a hard drive source"

    def run(self):
        """Set up an installation source.

        Always sets up two mount points: First for the device, and second for the ISO image or a
        bind for unpacked ISO. These depend on each other, and must be destroyed in the correct
        order again.

        :return SetupHardDriveResult: a result data
        :raise SourceSetupError: if the source fails to set up
        """
        log.debug("Setting up a hard drive source...")

        # Set up the HDD source.
        install_tree_path, iso_file = self._set_up_source()

        # Generate a valid repository configuration.
        repository = copy.deepcopy(self._configuration)
        repository.url = "file://" + install_tree_path

        return SetupHardDriveResult(
            repository=repository,
            iso_file=iso_file,
        )

    def _set_up_source(self):
        """Set up the HDD source and return a path to a valid repository and an ISO if any."""
        # Parse the URL.
        partition, directory = parse_hdd_url(self._configuration.url)

        # Check the mount points.
        for mount_point in [self._device_mount, self._iso_mount]:
            if os.path.ismount(mount_point):
                raise SourceSetupError(
                    "The mount point {} is already in use.".format(mount_point)
                )

        # Mount the hard drive.
        if not find_and_mount_device(partition, self._device_mount):
            raise SourceSetupError(
                "Failed to mount the '{}' HDD source.".format(partition)
            )

        # Mount an ISO if any.
        full_path_on_mounted_device = join_paths(self._device_mount, directory)
        iso_name = find_and_mount_iso_image(full_path_on_mounted_device, self._iso_mount)

        if iso_name:
            log.debug("Using the ISO '%s' mounted at '%s'.", iso_name, self._iso_mount)
            return self._iso_mount, join_paths("/", directory, iso_name)

        if verify_valid_repository(full_path_on_mounted_device):
            log.debug("Using the directory at '%s'.", full_path_on_mounted_device)
            return full_path_on_mounted_device, None

        # Nothing found.
        unmount(self._device_mount)

        raise SourceSetupError(
            "Nothing useful found for the HDD source at '{}:{}'."
            "".format(partition, directory)
        )
