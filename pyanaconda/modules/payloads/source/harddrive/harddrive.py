#
# Kickstart module for Hard drive payload source.
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
import os

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import URL_TYPE_BASEURL
from pyanaconda.core.payload import create_hdd_url, parse_hdd_url
from pyanaconda.core.storage import device_matches
from pyanaconda.modules.common.errors.general import InvalidValueError
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.harddrive.harddrive_interface import (
    HardDriveSourceInterface,
)
from pyanaconda.modules.payloads.source.harddrive.initialization import (
    SetupHardDriveResult,
    SetUpHardDriveSourceTask,
)
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from pyanaconda.modules.payloads.source.source_base import (
    PayloadSourceBase,
    RepositorySourceMixin,
    RPMSourceMixin,
)
from pyanaconda.modules.payloads.source.utils import MountPointGenerator

log = get_module_logger(__name__)

__all__ = ["HardDriveSourceModule"]


class HardDriveSourceModule(PayloadSourceBase, RepositorySourceMixin, RPMSourceMixin):
    """The Hard drive source payload module."""

    def __init__(self):
        super().__init__()
        self._device_mount = MountPointGenerator.generate_mount_point(
            self.type.value.lower() + "-device"
        )
        self._iso_mount = MountPointGenerator.generate_mount_point(
            self.type.value.lower() + "-iso"
        )
        self._iso_file = None

    def for_publication(self):
        """Get the interface used to publish this source."""
        return HardDriveSourceInterface(self)

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.HDD

    @property
    def description(self):
        """Get description of this source."""
        hdd = parse_hdd_url(self.configuration.url)
        return "{}:{}".format(hdd.device, hdd.path)

    @property
    def network_required(self):
        """Does the source require a network?

        :return: True or False
        """
        return False

    @property
    def required_space(self):
        """The space required for the installation.

        :return: required size in bytes
        :rtype: int
        """
        return 0

    def get_device(self):
        """Get a device that contains the installation source.

        :return str: a resolved device name
        """
        hdd = parse_hdd_url(self.configuration.url)
        devices = device_matches(hdd.device)

        if not devices:
            log.warning("Device for installation from HDD can't be found.")
            return ""

        if len(devices) > 1:
            log.warning("More than one device is found for HDD installation.")

        return devices[0]

    def get_iso_file(self):
        """Get a path to the ISO image from the device root.

        Returns an empty string if the source is pointing
        to an installation tree instead of an ISO image.

        :return str: an absolute path from the device root
        """
        return self._iso_file or ""

    def get_state(self):
        """Get state of this source."""
        return SourceState.from_bool(
            os.path.ismount(self._device_mount)
            and bool(self._repository)
        )

    def process_kickstart(self, data):
        """Process the kickstart data."""
        configuration = RepoConfigurationData()
        configuration.url = create_hdd_url(
            data.harddrive.partition,
            data.harddrive.dir
        )
        self.set_configuration(configuration)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        device, path = parse_hdd_url(self.configuration.url)
        data.harddrive.partition = device
        data.harddrive.dir = path
        data.harddrive.seen = True

    def _validate_configuration(self, configuration):
        """Validate the specified source configuration."""
        if not configuration.url.startswith("hd:"):
            raise InvalidValueError(
                "Invalid protocol of a HDD source: '{}'"
                "".format(configuration.url)
            )

        if configuration.type != URL_TYPE_BASEURL:
            raise InvalidValueError(
                "Invalid URL type of a HDD source: '{}'"
                "".format(configuration.type)
            )

    def set_up_with_tasks(self):
        """Set up the installation source.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        task = SetUpHardDriveSourceTask(
            self.configuration,
            self._device_mount,
            self._iso_mount,
        )
        task.succeeded_signal.connect(
            lambda: self._on_set_up_succeeded(task.get_result())
        )
        return [task]

    def _on_set_up_succeeded(self, result: SetupHardDriveResult):
        """Update the generated repository configuration."""
        self._set_repository(result.repository)
        self._iso_file = result.iso_file

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [Task]
        """
        tasks = [
            TearDownMountTask(self._iso_mount),
            TearDownMountTask(self._device_mount),
        ]
        return tasks

    def generate_repo_configuration(self):
        """Generate RepoConfigurationData structure."""
        return self.repository

    def __repr__(self):
        """Generate a string representation."""
        return "Source(type='HDD', url='{}')".format(self.configuration.url)
