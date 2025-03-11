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
from blivet.fcoe import fcoe

from pyanaconda.modules.common.errors.configuration import StorageDiscoveryError
from pyanaconda.modules.common.task import Task


class FCOEDiscoverTask(Task):
    """A task for discovering a FCoE device"""

    def __init__(self, nic, dcb, auto_vlan):
        super().__init__()
        self._nic = nic
        self._dcb = dcb
        self._auto_vlan = auto_vlan

    @property
    def name(self):
        return "Discover a FCoE"

    def run(self):
        """Run the discovery."""
        self._discover_device()

    def _discover_device(self):
        """Discover the device."""
        try:
            error_message = fcoe.add_san(self._nic, self._dcb, self._auto_vlan)
        except (IOError, OSError) as e:
            raise StorageDiscoveryError(str(e)) from e

        if error_message:
            raise StorageDiscoveryError(error_message)

        fcoe.added_nics.append(self._nic)
