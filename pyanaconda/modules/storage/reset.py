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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from blivet import arch
from blivet.errors import UnusableConfigurationError
from blivet.fcoe import fcoe
from blivet.i18n import _
from blivet.iscsi import iscsi
from blivet.nvme import nvme
from blivet.zfcp import zfcp

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.modules.common.errors.storage import UnusableStorageError
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)

__all__ = ["ScanDevicesTask"]


class ScanDevicesTask(Task):
    """A task for scanning all devices.

    Scan the system's storage configuration and store it in the tree.
    This task will reset the given instance of Blivet.
    """

    def __init__(self, storage):
        """Create a new task.

        :param storage: an instance of Blivet
        """
        super().__init__()
        self._storage = storage

    @property
    def name(self):
        return "Scan all devices"

    def run(self):
        """Run the task.

        :raise: UnusableStorageError if the model is not usable
        """
        try:
            self._reload_modules()
            self._reset_storage(self._storage)
        except UnusableConfigurationError as e:
            log.exception("Failed to scan devices: %s", e)
            message = "\n\n".join([str(e), _(e.suggestion)])
            raise UnusableStorageError(message) from None

    def _reload_modules(self):
        """Reload the additional modules."""
        if conf.target.is_image:
            return

        iscsi.startup()
        fcoe.startup()
        nvme.startup()

        if arch.is_s390():
            zfcp.startup()

    def _reset_storage(self, storage):
        """Reset the storage."""
        storage.reset()
