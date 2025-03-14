#
# DBus structure for module ui module vnc data.
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
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.structures.secret import SecretData

__all__ = ["VncData"]


class VncData(DBusData):
    """Module Vnc runtime data"""

    def __init__(self):
        self._enabled = False
        self._host = ""
        self._port = ""
        self._password = SecretData()

    @property
    def enabled(self) -> Bool:
        """Whether VNC is enabled.

        :return: True if enabled, False otherwise.
        """
        return self._enabled

    @enabled.setter
    def enabled(self, value: Bool):
        self._enabled = value

    @property
    def host(self) -> Str:
        """The VNC host address.

        This could be an IP address or a hostname where the VNC server is running.

        :return: a host address.
        """
        return self._host

    @host.setter
    def host(self, value: Str):
        self._host = value

    @property
    def port(self) -> Str:
        """The VNC port number.

        This is the port on which the VNC server is listening.

        :return: a port number as a string.
        """
        return self._port

    @port.setter
    def port(self, value: Str):
        self._port = value

    @property
    def password(self) -> SecretData:
        """The VNC password.

        This is the password required to connect to the VNC server.

        :return: a password.
        """
        return self._password

    @password.setter
    def password(self, value: SecretData):
        self._password = value
