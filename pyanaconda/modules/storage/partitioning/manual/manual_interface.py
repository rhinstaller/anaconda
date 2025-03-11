#
# DBus interface for the manual partitioning module.
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
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.objects import MANUAL_PARTITIONING
from pyanaconda.modules.common.structures.partitioning import MountPointRequest
from pyanaconda.modules.storage.partitioning.base_interface import PartitioningInterface


@dbus_interface(MANUAL_PARTITIONING.interface_name)
class ManualPartitioningInterface(PartitioningInterface):
    """DBus interface for the manual partitioning module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property("Requests", self.implementation.requests_changed)

    @property
    def Requests(self) -> List[Structure]:
        """List of mount point requests."""
        return MountPointRequest.to_structure_list(self.implementation.requests)

    @Requests.setter
    @emits_properties_changed
    def Requests(self, requests: List[Structure]):
        """Set the mount point requests.

        :param requests: a list of requests
        """
        self.implementation.set_requests(MountPointRequest.from_structure_list(requests))

    def GatherRequests(self) -> List[Structure]:
        """Gather all mount point requests.

        Return mount point requests for all usable devices. If there is
        a defined request for the given device, we will use it. Otherwise,
        we will generate a new request.

        :return: a list of requests
        """
        return MountPointRequest.to_structure_list(self.implementation.gather_requests())
