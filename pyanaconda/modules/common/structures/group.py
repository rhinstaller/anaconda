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
from pyanaconda.dbus.structure import dbus_structure
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["GroupData"]


@dbus_structure
class GroupData(object):
    """Group data."""

    def __init__(self):
        self._name = ""
        self._gid = -1

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
    def gid(self) -> Int:
        """The GID of the group.

        If not provided, defaults to the next available non-system GID.

        GID equal to -1 means that a valid GID has not been set.

        For examples: 1234

        :return: group GID
        :rtype: int
        """
        return self._gid

    @gid.setter
    def gid(self, gid: Int):
        self._gid = gid
