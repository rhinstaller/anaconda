#
# DBus interface for the auto partitioning module.
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING
from pyanaconda.modules.common.structures.partitioning import PartitioningRequest
from pyanaconda.modules.storage.partitioning.base_interface import PartitioningInterface


@dbus_interface(AUTO_PARTITIONING.interface_name)
class AutoPartitioningInterface(PartitioningInterface):
    """DBus interface for the auto partitioning module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property("Request", self.implementation.request_changed)

    @property
    def Request(self) -> Structure:
        """The partitioning request."""
        return PartitioningRequest.to_structure(self.implementation.request)

    @emits_properties_changed
    def SetRequest(self, request: Structure):
        """Set the partitioning request.

        :param request: a request
        """
        self.implementation.set_request(PartitioningRequest.from_structure(request))

    def RequiresPassphrase(self) -> Bool:
        """Is the default passphrase required?

        :return: True or False
        """
        return self.implementation.requires_passphrase()

    @emits_properties_changed
    def SetPassphrase(self, passphrase: Str):
        """Set a default passphrase for all encrypted devices.

        :param passphrase: a string with a passphrase
        """
        self.implementation.set_passphrase(passphrase)

    def RemoveDevice(self, device_name: Str):
        """Remove a device after removing its dependent devices.

        If the device is protected, do nothing. If the device has
        protected children, just remove the unprotected ones.

        :param device_name: a name of the device
        """
        self.implementation.remove_device(device_name)

    def ShrinkDevice(self, device_name: Str, size: UInt64):
        """Shrink the size of the device.

        :param device_name: a name of the device
        :param size: a new size in bytes
        """
        self.implementation.shrink_device(device_name, size)
