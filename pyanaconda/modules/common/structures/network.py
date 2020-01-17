#
# DBus structures for network device configuration.
#
# Copyright (C) 2019  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["NetworkDeviceConfiguration", "NetworkDeviceInfo"]


class NetworkDeviceConfiguration(DBusData):
    """Holds reference to persistent configuration of a network device.

    Binds device name and NM connection (by its uuid).

    Device type is additional information useful for clients.
    """

    DEVICE_TYPE_UNKNOWN = 0

    def __init__(self):
        self._device_name = ""
        self._connection_uuid = ""
        self._device_type = self.DEVICE_TYPE_UNKNOWN

    @property
    def device_name(self) -> Str:
        """Name of the network device."""
        return self._device_name

    @device_name.setter
    def device_name(self, device_name: Str):
        self._device_name = device_name

    @property
    def connection_uuid(self) -> Str:
        """UUID of NetworkManager persistent connection."""
        return self._connection_uuid

    @connection_uuid.setter
    def connection_uuid(self, connection_uuid: Str):
        self._connection_uuid = connection_uuid

    @property
    def device_type(self) -> Int:
        """Device type specification (NM_DEVICE_TYPE)."""
        return self._device_type

    @device_type.setter
    def device_type(self, device_type: Int):
        self._device_type = device_type

    def __eq__(self, other):
        return (self._device_name == other.device_name
                and self._connection_uuid == other.connection_uuid)


class NetworkDeviceInfo(DBusData):
    """Holds information about network device."""

    DEVICE_TYPE_UNKNOWN = 0

    def __init__(self):
        self._device_name = ""
        self._hw_address = ""
        self._device_type = self.DEVICE_TYPE_UNKNOWN

    @property
    def device_name(self) -> Str:
        """Name of the network device."""
        return self._device_name

    @device_name.setter
    def device_name(self, device_name: Str):
        self._device_name = device_name

    @property
    def hw_address(self) -> Str:
        """Hardware address of the network device."""
        return self._hw_address

    @hw_address.setter
    def hw_address(self, hw_address: Str):
        self._hw_address = hw_address

    @property
    def device_type(self) -> Int:
        """Device type specification (NM_DEVICE_TYPE)."""
        return self._device_type

    @device_type.setter
    def device_type(self, device_type: Int):
        self._device_type = device_type

    def set_from_nm_device(self, device):
        """Set the object from NetworkManager Device object.

        :param device: NetworkManager device object
        :type device: NMDevice
        """
        self._device_name = device.get_iface() or ""
        self._device_type = device.get_device_type() or self.DEVICE_TYPE_UNKNOWN
        try:
            perm_hw_address = device.get_permanent_hw_address()
        except AttributeError:
            perm_hw_address = None
        self.hw_address = perm_hw_address or device.get_hw_address() or ""
