#
# The NFS source module.
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

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import URL_TYPE_BASEURL
from pyanaconda.core.i18n import _
from pyanaconda.core.payload import create_nfs_url, parse_nfs_url
from pyanaconda.modules.common.errors.general import InvalidValueError
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from pyanaconda.modules.payloads.source.nfs.initialization import (
    SetUpNFSSourceResult,
    SetUpNFSSourceTask,
)
from pyanaconda.modules.payloads.source.source_base import (
    PayloadSourceBase,
    RepositorySourceMixin,
    RPMSourceMixin,
)
from pyanaconda.modules.payloads.source.source_base_interface import (
    RepositorySourceInterface,
)
from pyanaconda.modules.payloads.source.utils import MountPointGenerator

log = get_module_logger(__name__)

__all__ = ["NFSSourceModule"]


class NFSSourceModule(PayloadSourceBase, RepositorySourceMixin, RPMSourceMixin):
    """The NFS source module."""

    def __init__(self):
        """Create a new source."""
        super().__init__()
        self._device_mount = MountPointGenerator.generate_mount_point(
            self.type.value.lower() + "-device"
        )
        self._iso_mount = MountPointGenerator.generate_mount_point(
            self.type.value.lower() + "-iso"
        )

    def for_publication(self):
        """Return a DBus representation."""
        return RepositorySourceInterface(self)

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.NFS

    @property
    def description(self):
        """Get description of this source."""
        nfs = parse_nfs_url(self.configuration.url)
        url = "{}:{}".format(nfs.host, nfs.path)
        return _("NFS server {}").format(url)

    @property
    def network_required(self):
        """Does the source require a network?

        :return: True or False
        """
        return True

    @property
    def required_space(self):
        """The space required for the installation.

        :return: required size in bytes
        :rtype: int
        """
        return 0

    def get_state(self):
        """Get state of this source."""
        return SourceState.from_bool(
            os.path.ismount(self._device_mount)
            and bool(self._repository)
        )

    def process_kickstart(self, data):
        """Process the kickstart data."""
        configuration = RepoConfigurationData()
        configuration.url = create_nfs_url(
            data.nfs.server,
            data.nfs.dir,
            data.nfs.opts
        )
        self.set_configuration(configuration)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        opts, host, path = parse_nfs_url(self.configuration.url)

        data.nfs.server = host
        data.nfs.dir = path
        data.nfs.opts = opts
        data.nfs.seen = True

    def _validate_configuration(self, configuration):
        """Validate the specified source configuration."""
        if not configuration.url.startswith("nfs:"):
            raise InvalidValueError(
                "Invalid protocol of an NFS source: '{}'"
                "".format(configuration.url)
            )

        if configuration.type != URL_TYPE_BASEURL:
            raise InvalidValueError(
                "Invalid URL type of an NFS source: '{}'"
                "".format(configuration.type)
            )

    def set_up_with_tasks(self):
        """Set up the installation source for installation.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        task = SetUpNFSSourceTask(
            self.configuration,
            self._device_mount,
            self._iso_mount,
        )
        task.succeeded_signal.connect(
            lambda: self._on_set_up_succeeded(task.get_result())
        )
        return [task]

    def _on_set_up_succeeded(self, result: SetUpNFSSourceResult):
        """Update the generated repository configuration."""
        self._set_repository(result.repository)

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [TearDownMountTask]
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
        return "Source(type='NFS', url='{}')".format(self.configuration.url)
