#
# Discovery tasks
#
# Copyright (C) 2018 Red Hat, Inc.
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
from blivet import blockdev

from pyanaconda.core.regexes import DASD_DEVICE_NUMBER
from pyanaconda.core.util import execWithRedirect
from pyanaconda.modules.common.errors.configuration import StorageDiscoveryError
from pyanaconda.modules.common.task import Task


class DASDDiscoverTask(Task):
    """A task for discovering a DASD by its number"""

    def __init__(self, device_number):
        super().__init__()
        self._device_number = device_number

    @property
    def name(self):
        return "Discover a DASD"

    def run(self):
        """Run the task."""
        self._check_input()
        self._sanitize_input()
        self._discover_device()

    def _check_input(self):
        """Check the input values."""
        if not DASD_DEVICE_NUMBER.match(self._device_number):
            raise StorageDiscoveryError("Incorrect format of the given device number.")

    def _sanitize_input(self):
        """Sanitize the input values."""
        # pylint: disable=try-except-raise
        try:
            self._device_number = blockdev.s390.sanitize_dev_input(self._device_number)
        except blockdev.S390Error as e:
            raise StorageDiscoveryError(str(e)) from e

    def _discover_device(self):
        """Discover the device."""
        # pylint: disable=try-except-raise
        try:
            rc = execWithRedirect("chzdev",
                                  ["--enable", "dasd", self._device_number,
                                   "--active", "--persistent",
                                   "--yes", "--no-root-update", "--force"])
        except RuntimeError as e:
            raise StorageDiscoveryError(str(e)) from e
        if rc != 0:
            raise StorageDiscoveryError(
                "Could not set the device online. It might not exist.")
