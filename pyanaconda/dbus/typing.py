#
# typing.py:  specified DBus types and their string representation
#
# Copyright (C) 2017
# Red Hat, Inc.  All rights reserved.
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
# Author(s):  Vendula Poncova <vponcova@redhat.com>
#
# For more info about DBus type system see:
# https://dbus.freedesktop.org/doc/dbus-specification.html#type-system.
#

from typing import Tuple, Dict, List, NewType, IO
from pydbus import Variant

__all__ = ["Bool", "Double", "Str", "Int", "Byte", "Int16", "UInt16",
           "Int32", "UInt32", "Int64", "UInt64", "File", "ObjPath",
           "Tuple", "List", "Dict", "Variant", "get_variant"]

# Basic types.
Bool = bool
Double = float
Str = str

# Default integer type: int will be treated as Int32.
Int = int

# All integer types.
Byte = NewType('Byte', int)
Int16 = NewType('Int16', int)
UInt16 = NewType('UInt16', int)
Int32 = NewType('Int32', int)
UInt32 = NewType('UInt32', int)
Int64 = NewType('Int64', int)
UInt64 = NewType('UInt64', int)

# Type of a file handler.
File = IO

# Type of an object path.
ObjPath = NewType('ObjPath', str)

# Container types.
# Use Tuple, Dict and List from typing.
# Use Variant from pydbus and get_variant.


def get_dbus_type(type_hint):
    """Return DBus representation of a type hint.

    :param type_hint: a type hint
    :return: a string with DBus representation
    """
    return DBusType.get_dbus_representation(type_hint)


def get_variant(type_hint, value):
    """Return a variant data type.

    The type of a variant is specified with
    a type hint.

    Example:
         v1 = get_variant(Bool, True)
         v2 = get_variant(List[Int], [1,2,3])

    :param type_hint: a type hint
    :param value: a value of the variant
    :return: an instance of Variant
    """
    return Variant(get_dbus_type(type_hint), value)


class DBusType(object):
    """Class for transforming type hints to DBus types."""

    # DBus representation of basic types.
    _basic_type_mapping = {
        # Basic types.
        Bool:       "b",
        Str:        "s",
        Double:     "d",
        # Default integer.
        Int:        "i",
        # Integer types.
        Byte:       "y",
        Int16:      "n",
        UInt16:     "q",
        Int32:      "i",
        UInt32:     "u",
        Int64:      "x",
        UInt64:     "t",
        # Other basic types.
        File:       "h",
        ObjPath:    "o",
        Variant:    "v"
    }

    # DBus representation of container types.
    _container_type_mapping = {
        Tuple:      "(%s)",
        List:       "a%s",
        Dict:       "a{%s}",
    }

    @staticmethod
    def get_dbus_representation(type_hint):
        """Return a DBus representation of the given type hint.

        :param type_hint: a type hint
        :return str: a DBus representation of the type hint

        :raises ValueError: for unknown types
        """
        # Try base types.
        if DBusType._is_basic_type(type_hint):
            return DBusType._get_basic_type(type_hint)

        # Try container types.
        if DBusType._is_container_type(type_hint):
            return DBusType._get_container_type(type_hint)

        # Or raise an error.
        raise TypeError("Unknown type: %s" % type_hint)

    @staticmethod
    def _is_basic_type(type_hint):
        """Is it a basic type?"""
        return type_hint in DBusType._basic_type_mapping

    @staticmethod
    def _get_basic_type(type_hint):
        """Return a basic type."""
        return DBusType._basic_type_mapping[type_hint]

    @staticmethod
    def _is_container_type(type_hint):
        """Is it a container type?"""
        return DBusType._get_container_base_type(type_hint) is not None

    @staticmethod
    def _get_container_base_type(type_hint):
        """Return a container base type."""
        # Try to get the "origin" of the hint.
        origin = getattr(type_hint, "__origin__", None)

        if not origin:
            return None

        # Return the container base type of the "origin" or None.
        # See: https://bugzilla.redhat.com/show_bug.cgi?id=1598574
        for basetype in DBusType._container_type_mapping:
            if issubclass(origin, basetype):
                return basetype

        return None

    @staticmethod
    def _get_container_type(type_hint):
        """Return a container type."""
        basetype = DBusType._get_container_base_type(type_hint)

        # Get the arguments of the container.
        args = type_hint.__args__

        # Check the typing.
        if basetype == Dict:
            DBusType._check_if_valid_dictionary(type_hint)

        # Generate string.
        container = DBusType._container_type_mapping[basetype]
        items = [DBusType.get_dbus_representation(arg) for arg in args]
        return container % "".join(items)

    @staticmethod
    def _check_if_valid_dictionary(type_hint):
        """Check the type of a dictionary.

        :raises ValueError: for invalid type
        """
        key, _ = type_hint.__args__

        if DBusType._is_container_type(key) or key == Variant:
            raise TypeError("Dictionary key cannot be of type %s." % key)
