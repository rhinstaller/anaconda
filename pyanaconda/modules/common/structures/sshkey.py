#
# DBus structure for describing SSH keys.
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

__all__ = ["SshKeyData"]


class SshKeyData(DBusData):
    """SSH key data."""

    def __init__(self):
        self._key = ""
        self._username = ""

    @property
    def key(self) -> Str:
        """The content of the SSH key to install.

        For example: 'ajadsfhskjdlhfsldkhfjkh'

        :return: content of an SSH key
        :rtype: str
        """
        return self._key

    @key.setter
    def key(self, key: Str):
        self._key = key

    @property
    def username(self) -> Str:
        """User name for which to install the specified key."

        For example: 'user1'

        :return: user name
        :rtype: str
        """
        return self._username

    @username.setter
    def username(self, username: Str):
        self._username = username
