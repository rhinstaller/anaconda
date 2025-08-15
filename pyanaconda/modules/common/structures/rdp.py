#
# DBus structure for RDP UI module runtime data.
#
# Copyright (C) 2025 Red Hat, Inc.
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
from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.structures.secret import SecretData

__all__ = ["RdpData"]


class RdpData(DBusData):
    """Runtime data for the RDP UI module."""

    def __init__(self):
        self._enabled = False
        self._username = ""
        self._password = SecretData()

    @property
    def enabled(self) -> Bool:
        """Whether RDP is enabled.
        :return: True if enabled, False otherwise.
        """
        return self._enabled

    @enabled.setter
    def enabled(self, value: Bool):
        self._enabled = value

    @property
    def username(self) -> Str:
        """The RDP username.
        This is the username used to authenticate the RDP session.
        :return: a username string.
        """
        return self._username

    @username.setter
    def username(self, value: Str):
        self._username = value

    @property
    def password(self) -> SecretData:
        """The RDP password.
        This is the password required to authenticate the RDP session.
        :return: a password object.
        """
        return self._password

    @password.setter
    def password(self, value: SecretData):
        self._password = value
