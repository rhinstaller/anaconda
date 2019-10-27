#
# Client support for DBus properties
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
__all__ = ["PropertyProxy"]


class PropertyProxy(object):
    """Proxy of a remote DBus property.

    It can be used to define instance attributes.
    """

    __slots__ = ["_getter", "_setter"]

    def __init__(self, getter, setter):
        """Create a new proxy of the DBus property."""
        self._getter = getter
        self._setter = setter

    def get(self):
        """Get the value of the DBus property."""
        return self.__get__(None, None)

    def __get__(self, instance, owner):
        if instance is None and owner:
            return self

        if not self._getter:
            raise AttributeError("Can't read attribute.")

        return self._getter()

    def set(self, value):
        """Set the value of the DBus property."""
        return self.__set__(None, value)

    def __set__(self, instance, value):
        if not self._setter:
            raise AttributeError("Can't set attribute.")

        return self._setter(value)
