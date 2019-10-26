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

import gi
gi.require_version("GLib", "2.0")
from gi.repository.GLib import Variant, VariantType

__all__ = ["Bool", "Double", "Str", "Int", "Byte", "Int16", "UInt16",
           "Int32", "UInt32", "Int64", "UInt64", "File", "ObjPath",
           "Tuple", "List", "Dict", "Variant", "VariantType", "Structure",
           "get_variant", "get_variant_type", "get_native",
           "is_base_type", "get_type_arguments"]

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
# Use Variant from GLib and get_variant.
# Use Structure instead of Dict[Str, Variant].
Structure = Dict[Str, Variant]


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

    :param type_hint: a type hint or a type string
    :param value: a value of the variant
    :return: an instance of Variant
    """
    if type(type_hint) == str:
        type_string = type_hint
    else:
        type_string = get_dbus_type(type_hint)

    return Variant(type_string, value)


def get_variant_type(type_hint):
    """Return a type of a variant data type.

    :param type_hint: a type hint or a type string
    :return: an instance of VariantType
    """
    if type(type_hint) == str:
        type_string = type_hint
    else:
        type_string = get_dbus_type(type_hint)

    return VariantType.new(type_string)


def get_native(value):
    """Decompose a DBus value into a native Python object.

    This function is useful for testing, when the DBus library
    doesn't decompose arguments and return values of DBus calls.

    :param value: a DBus value
    :return: a native Python object
    """
    if isinstance(value, Variant):
        return value.unpack()

    if isinstance(value, tuple):
        return tuple(map(get_native, value))

    if isinstance(value, list):
        return list(map(get_native, value))

    if isinstance(value, dict):
        return {k: get_native(v) for k, v in value.items()}

    return value


def is_base_type(type_hint, base_type):
    """Is the given base type a base of the specified type hint?

    For example, List is a base of the type hint List[Int] and
    Int is a base of the type hint Int. A class is a base of
    itself and of every subclass of this class.

    :param type_hint: a type hint
    :param base_type: a base type
    :return: True or False
    """
    type_hint = getattr(type_hint, "__origin__", type_hint)

    if type_hint == base_type:
        return True

    try:
        return issubclass(type_hint, base_type)
    except TypeError:
        pass

    return False


def get_type_arguments(type_hint):
    """Get the arguments of the type hint.

    For example, Str and Int are arguments of the type hint Tuple(Str, Int).

    :param type_hint: a type hint
    :return: a type arguments
    """
    return getattr(type_hint, "__args__", ())


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
        # Return the container base type of the "origin" or None.
        # See: https://bugzilla.redhat.com/show_bug.cgi?id=1598574
        for base_type in DBusType._container_type_mapping:
            if is_base_type(type_hint, base_type):
                return base_type

        return None

    @staticmethod
    def _get_container_type(type_hint):
        """Return a container type."""
        basetype = DBusType._get_container_base_type(type_hint)

        # Get the arguments of the container.
        args = get_type_arguments(type_hint)

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
        key, _ = get_type_arguments(type_hint)

        if DBusType._is_container_type(key) or key == Variant:
            raise TypeError("Dictionary key cannot be of type %s." % key)
