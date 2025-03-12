#
# DBus structure for module runtime logging data.
#
# Copyright (C) 2024 Red Hat, Inc.
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
from dasbus.typing import Str

__all__ = ["LoggingData"]


class LoggingData(DBusData):
    """Module Logging configuration data."""

    def __init__(self):
        self._host = ""
        self._port = ""

    @property
    def host(self) -> Str:
        """The logging server's host address.

        This could be an IP address or a hostname where the logging server is accessible.

        :return: a host address.
        """
        return self._host

    @host.setter
    def host(self, value: Str):
        self._host = value

    @property
    def port(self) -> Str:
        """The logging server's port number.

        This is the port on which the logging server is listening.

        :return: a port number as a string.
        """
        return self._port

    @port.setter
    def port(self, value: Str):
        self._port = value
