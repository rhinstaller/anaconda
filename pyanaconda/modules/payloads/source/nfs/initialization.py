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
from os.path import ismount

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.payload.utils import mount, unmount
from pyanaconda.core.util import parse_nfs_url
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.common.errors.payload import SourceSetupError

log = get_module_logger(__name__)

__all__ = ["TearDownNFSSourceTask", "SetUpNFSSourceTask"]


class TearDownNFSSourceTask(Task):
    """Task to teardown the NFS source."""

    def __init__(self, target_mount):
        super().__init__()
        self._target_mount = target_mount

    @property
    def name(self):
        return "Tear down NFS installation source"

    def run(self):
        """Tear down the installation source."""
        log.debug("Unmounting NFS installation source")
        unmount(self._target_mount)


class SetUpNFSSourceTask(Task):
    """Task to set up the NFS source."""

    def __init__(self, target_mount, url):
        super().__init__()
        self._target_mount = target_mount
        self._url = url

    @property
    def name(self):
        return "Set up NFS installation source"

    def run(self):
        """Set up the installation source."""
        log.debug("Trying to mount NFS: %s", self._url)

        if ismount(self._target_mount):
            raise SourceSetupError(
                "Something is already mounted at the target {}".format(self._target_mount))

        options, host, path = parse_nfs_url(self._url)
        if not options:
            options = "nolock"
        elif "nolock" not in options:
            options += ",nolock"

        mount("{}:{}".format(host, path), self._target_mount, fstype="nfs", options=options)

        log.debug("We are ready to use NFS at %s.", self._target_mount)
