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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.payload.utils import mount
from pyanaconda.core.payload import parse_nfs_url
from pyanaconda.modules.payloads.source.mount_tasks import SetUpMountTask

log = get_module_logger(__name__)

__all__ = ["SetUpNFSSourceTask"]


class SetUpNFSSourceTask(SetUpMountTask):
    """Task to set up the NFS source."""

    def __init__(self, target_mount, url):
        super().__init__(target_mount)
        self._url = url

    @property
    def name(self):
        return "Set up NFS installation source"

    def _do_mount(self):
        """Set up the installation source."""
        log.debug("Trying to mount NFS: %s", self._url)

        options, host, path = parse_nfs_url(self._url)
        if not options:
            options = "nolock"
        elif "nolock" not in options:
            options += ",nolock"

        mount("{}:{}".format(host, path), self._target_mount, fstype="nfs", options=options)

        log.debug("We are ready to use NFS at %s.", self._target_mount)
