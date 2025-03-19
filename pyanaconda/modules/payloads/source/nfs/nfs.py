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

from pyanaconda.core.i18n import _
from pyanaconda.core.payload import create_nfs_url, parse_nfs_url
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceType, SourceState
from pyanaconda.modules.payloads.source.nfs.nfs_interface import NFSSourceInterface
from pyanaconda.modules.payloads.source.nfs.initialization import SetUpNFSSourceTask
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from pyanaconda.modules.payloads.source.source_base import PayloadSourceBase, RPMSourceMixin
from pyanaconda.modules.payloads.source.utils import MountPointGenerator

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["NFSSourceModule"]


class NFSSourceModule(PayloadSourceBase, RPMSourceMixin):
    """The NFS source module.

    TODO: Merge code from HardDriveSourceModule and this one.
    TODO: Add install_tree_path property.
    """

    def __init__(self):
        super().__init__()
        self._url = ""
        self.url_changed = Signal()
        self._install_tree_path = ""
        self._device_mount = MountPointGenerator.generate_mount_point(
            self.type.value.lower() + "-device"
        )
        self._iso_mount = MountPointGenerator.generate_mount_point(
            self.type.value.lower() + "-iso"
        )

    def __repr__(self):
        return "Source(type='NFS', url='{}')".format(self.url)

    def for_publication(self):
        """Return a DBus representation."""
        return NFSSourceInterface(self)

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.NFS

    @property
    def description(self):
        """Get description of this source."""
        return _("NFS server {}").format(self.url)

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
        res = os.path.ismount(self._device_mount) and bool(self._install_tree_path)
        return SourceState.from_bool(res)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        nfs_url = create_nfs_url(data.nfs.server, data.nfs.dir, data.nfs.opts)
        self.set_url(nfs_url)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        (opts, host, path) = parse_nfs_url(self.url)

        data.nfs.server = host
        data.nfs.dir = path
        data.nfs.opts = opts
        data.nfs.seen = True

    def generate_repo_configuration(self):
        """Generate RepoConfigurationData structure."""
        return RepoConfigurationData.from_directory(self.install_tree_path)

    @property
    def url(self):
        """URL for mounting.

        Combines server address, path, and options.

        :rtype: str
        """
        return self._url

    def set_url(self, url):
        """Set all NFS values with a valid URL.

        Fires all signals.

        :param url: URL
        :type url: str
        """
        self._url = url
        self.url_changed.emit()
        log.debug("NFS URL is set to %s", self._url)

    @property
    def install_tree_path(self):
        """Path to the install tree.

        Read only, and available only after the setup task finishes successfully.

        :rtype: str
        """
        return self._install_tree_path

    def set_up_with_tasks(self):
        """Set up the installation source for installation.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        task = SetUpNFSSourceTask(self._device_mount, self._iso_mount, self._url)
        task.succeeded_signal.connect(lambda: self._handle_setup_task_result(task))
        return [task]

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

    def _handle_setup_task_result(self, task):
        result = task.get_result()
        self._install_tree_path = result
        log.debug("NFS install tree path is set to '%s'", self._install_tree_path)
