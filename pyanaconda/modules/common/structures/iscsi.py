#
# DBus structures for iSCSI.
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

__all__ = ["Target", "Credentials"]


@dbus_structure
class Target(object):
    """Data for iSCSI target."""

    def __init__(self):
        self._initiator = ""
        self._ip_address = ""
        self._port = "3260"
        self._bind = False

    @property
    def initiator(self) -> Str:
        """iSCSI initiator name.

        :return: a string with a name
        """
        return self._initiator

    @initiator.setter
    def initiator(self, initiator: Str):
        self._initiator = initiator

    @property
    def ip_address(self) -> Str:
        """IP address.

        :return: a string with an IP address
        """
        return self._ip_address

    @ip_address.setter
    def ip_address(self, address: Str):
        self._ip_address = address

    @property
    def port(self) -> Str:
        """Port.

        :return: a string with the port
        """
        return self._port

    @port.setter
    def port(self, port: Str):
        self._port = port

    @property
    def bind(self) -> Bool:
        """Bind targets to network interfaces?

        :return: True or False
        """
        return self._bind

    @bind.setter
    def bind(self, value: Bool):
        self._bind = value


@dbus_structure
class Credentials(object):
    """Data for iSCSI credentials."""

    def __init__(self):
        self._username = ""
        self._password = ""
        self._reverse_username = ""
        self._reverse_password = ""

    @property
    def username(self) -> Str:
        """CHAP user name.

        :return: a string with a name
        """
        return self._username

    @username.setter
    def username(self, name: Str):
        self._username = name

    @property
    def password(self) -> Str:
        """CHAP password.

        :return: a string with a password
        """
        return self._password

    @password.setter
    def password(self, password: Str):
        self._password = password

    @property
    def reverse_username(self) -> Str:
        """Reverse CHAP user name.

        :return: a string with a name
        """
        return self._reverse_username

    @reverse_username.setter
    def reverse_username(self, name: Str):
        self._reverse_username = name

    @property
    def reverse_password(self) -> Str:
        """Reverse CHAP password.

        :return: a string with a password
        """
        return self._reverse_password

    @reverse_password.setter
    def reverse_password(self, password: Str):
        self._reverse_password = password


@dbus_structure
class Node(object):
    """Data for iSCSI node."""

    def __init__(self):
        self._name = ""
        self._address = ""
        self._port = ""
        self._interface = ""

    @property
    def name(self) -> Str:
        """Name.

        :return: a string with a name
        """
        return self._name

    @name.setter
    def name(self, name: Str):
        self._name = name

    @property
    def address(self) -> Str:
        """Address.

        :return: a string with an address
        """
        return self._address

    @address.setter
    def address(self, address: Str):
        self._address = address

    @property
    def port(self) -> Str:
        """Port.

        :return: a string with a port
        """
        return self._port

    @port.setter
    def port(self, port: Str):
        self._port = port

    @property
    def interface(self) -> Str:
        """Interface.

        :return: a string with an interface
        """
        return self._interface

    @interface.setter
    def interface(self, interface: Str):
        self._interface = interface
