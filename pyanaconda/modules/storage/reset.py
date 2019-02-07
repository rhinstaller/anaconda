#
# Storage reset
#
# Copyright (C) 2019 Red Hat, Inc.
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
from blivet import arch
from blivet.fcoe import fcoe
from blivet.iscsi import iscsi
from blivet.zfcp import zfcp

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.task import Task


class StorageResetTask(Task):
    """A task for resetting the model of the storage.

    Scan the system’s storage configuration and store it in the tree.
    """

    def __init__(self, storage):
        """Create a new task.

        :param storage: an instance of Blivet
        """
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        return "Reset the model of the storage"

    def run(self):
        """Run the task."""
        self._reload_modules()
        self._reset_storage(self._storage)

    def _reload_modules(self):
        """Reload the additional modules."""
        if conf.target.is_image:
            return

        iscsi.startup()
        fcoe.startup()

        if arch.is_s390():
            zfcp.startup()

    def _reset_storage(self, storage):
        """Reset the storage."""
        storage.reset()
