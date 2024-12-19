#
# DBus structure for describing user groups.
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

from pyanaconda.core.constants import ID_MODE_USE_DEFAULT, ID_MODE_USE_VALUE

__all__ = ["GroupData"]


class GroupData(DBusData):
    """Group data."""

    def __init__(self):
        self._name = ""
        self._gid = 0
        self._gid_mode = ID_MODE_USE_DEFAULT

    @property
    def name(self) -> Str:
        """Group name."

        For example: 'wheel'

        Should comply with the usual limitations for Linux group names.

        :return: group name
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, name: Str):
        self._name = name

    @property
    def gid_mode(self) -> Str:
        """Mode of the GID.

        Contains a string describing the mode of the group's GID: Use the value or default.

        Possible values are:
        - "ID_MODE_USE_VALUE"
        - "ID_MODE_USE_DEFAULT"

        :return: the mode
        :rtype str:
        """
        return self._gid_mode

    @gid_mode.setter
    def gid_mode(self, status: Str):
        self._gid_mode = status

    @property
    def gid(self) -> UInt32:
        """The GID of the group.

        If ignored due to gid_mode, defaults to the next available non-system GID.

        For examples: 1234

        :return: group GID
        :rtype: int
        """
        return self._gid

    @gid.setter
    def gid(self, gid: UInt32):
        self._gid = gid

    def get_gid(self):
        """Return a GID value which can be a number or None.

        Prefer using this method instead of directly reading gid and gid_mode.

        :return: GID or None if not set
        :rtype: int or None
        """
        if self._gid_mode == ID_MODE_USE_DEFAULT:
            return None
        else:
            return self._gid

    def set_gid(self, new_gid):
        """Set GID value and mode from a value which can be None.

        Prefer using this method instead of directly writing gid and gid_mode.

        :param new_gid: new GID
        :type new_gid: int or None
        """
        if new_gid is not None:
            self._gid = new_gid
            self._gid_mode = ID_MODE_USE_VALUE
        else:
            self._gid = 0
            self._gid_mode = ID_MODE_USE_DEFAULT
