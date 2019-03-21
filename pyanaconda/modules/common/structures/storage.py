#
# DBus structures for the storage data.
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
from pyanaconda.dbus.structure import dbus_structure
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["DeviceData"]


@dbus_structure
class DeviceData(object):
    """Device data."""

    SUPPORTED_ATTRIBUTES = [
        "serial",
        "vendor",
        "model",
        "bus",
        "wwn",

        # DASD
        "busid",

        # ZFCP
        "fcp_lun",
        "wwpn",
        "hba_id"
    ]

    def __init__(self):
        self._type = ""
        self._name = ""
        self._path = ""
        self._size = 0
        self._is_disk = False
        self._attrs = {}

    @property
    def type(self) -> Str:
        """A type of the device.

        :return: a device type
        """
        return self._type

    @type.setter
    def type(self, value: Str):
        self._type = value

    @property
    def name(self) -> Str:
        """A name of the device

        :return: a device name
        """
        return self._name

    @name.setter
    def name(self, name: Str):
        self._name = name

    @property
    def path(self) -> Str:
        """A device node representing the device.

        :return: a path
        """
        return self._path

    @path.setter
    def path(self, value: Str):
        self._path = value

    @property
    def size(self) -> UInt64:
        """A size of the device

        :return: a size in bytes
        """
        return UInt64(self._size)

    @size.setter
    def size(self, size: UInt64):
        self._size = size

    @property
    def is_disk(self) -> Bool:
        """Is this device a disk?

        :return: True or False
        """
        return self._is_disk

    @is_disk.setter
    def is_disk(self, is_disk: Bool):
        self._is_disk = is_disk

    @property
    def attrs(self) -> Dict[Str, Str]:
        """Additional attributes.

        The supported attributes are defined by
        the list SUPPORTED_ATTRIBUTES.

        :return: a dictionary of attributes
        """
        return self._attrs

    @attrs.setter
    def attrs(self, attrs: Dict[Str, Str]):
        self._attrs = attrs
