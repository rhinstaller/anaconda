#
# Populate tasks
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
from blivet.errors import UnusableConfigurationError
from blivet.i18n import _

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.errors.storage import UnusableStorageError
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)

__all__ = ["FindDevicesTask"]


class FindDevicesTask(Task):
    """A task to find new devices."""

    def __init__(self, devicetree):
        """Create a new task.

        :param devicetree: a device tree to populate
        """
        super().__init__()
        self._devicetree = devicetree

    @property
    def name(self):
        return "Find new devices"

    def run(self):
        """Run the task.

        :raise: UnusableStorageError if the model is not usable
        """
        try:
            self._devicetree.populate()
            self._devicetree.teardown_all()
        except UnusableConfigurationError as e:
            log.error("Failed to find devices: %s", e)
            message = "\n\n".join([str(e), _(e.suggestion)])
            raise UnusableStorageError(message) from None
