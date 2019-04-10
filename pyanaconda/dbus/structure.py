#
# DBus structures.
#
# Copyright (C) 2018  Red Hat, Inc.  All rights reserved.
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
import inspect
from abc import ABC
from typing import get_type_hints

from pyanaconda.dbus.typing import get_variant, Structure, Dict, List

__all__ = ["DBusStructureError", "generate_string_from_data", "DBusData"]


# Class attribute for DBus fields.
DBUS_FIELDS_ATTRIBUTE = "__dbus_fields__"


class DBusStructureError(Exception):
    """General exception for DBus structure errors."""
    pass


class DBusField(object):
    """Description of a field in a DBus structure."""

    def __init__(self, name, type_hint, description=""):
        """Create a description of the field.

        :param name: a name of the field
        :param type_hint: a type hint
        :param description: a description
        """
        self._name = name
        self._type_hint = type_hint
        self._description = description

    @property
    def name(self):
        """Name of the field.

        :return: a name
        """
        return self._name

    @property
    def type_hint(self):
        """Type hint of the field.

        :return: a type hint
        """
        return self._type_hint

    @property
    def description(self):
        """Description of the field.

        :return: a description
        """
        return self._description

    @property
    def data_name(self):
        """Return name of a data attribute.

        :return: a data attribute name
        """
        return self.name.replace('-', '_')

    def set_data(self, obj, value):
        """Set the data attribute.

        :param obj: a data object
        :param value: a value
        """
        setattr(obj, self.data_name, value)

    def get_data(self, obj):
        """Get the data attribute.

        :param obj: a data object
        :return: a value
        """
        return getattr(obj, self.data_name)

    def get_data_variant(self, obj):
        """Get a variant of the data attribute.

        :param obj: a data object
        :return: a variant
        """
        return get_variant(self.type_hint, self.get_data(obj))


class DBusData(ABC):
    """Object representation of data in a DBus structure.

    Classes derived from this class should represent specific types
    of DBus structures. They will support a conversion from a DBus
    structure of this type to a Python object and back.
    """

    def __init_subclass__(cls, *args, **kwargs):
        """Create a new data class."""
        super().__init_subclass__(*args, **kwargs)

        # Generate the DBus fields from the members of the class cls.
        setattr(cls, DBUS_FIELDS_ATTRIBUTE, generate_fields(cls))

    @classmethod
    def from_structure(cls, structure: Dict):
        """Convert a DBus structure to a data object.

        :param structure: a DBus structure
        :return: a data object
        """
        data = cls()
        fields = get_fields(cls)

        for name, value in structure.items():
            field = fields.get(name, None)

            if not field:
                raise DBusStructureError("Field '{}' doesn't exist.".format(name))

            field.set_data(data, value)

        return data

    @classmethod
    def to_structure(cls, data) -> Structure:
        """Convert this data object to a DBus structure.

        :return: a DBus structure
        """
        structure = {}
        fields = get_fields(cls)

        for name, field in fields.items():
            structure[name] = field.get_data_variant(data)

        return structure

    @classmethod
    def from_structure_list(cls, structures: List[Dict]):
        """Convert DBus structures to data objects.

        :param structures: a list of DBus structures
        :return: a list of data objects
        """
        return list(map(cls.from_structure, structures))

    @classmethod
    def to_structure_list(cls, objects) -> List[Structure]:
        """Convert data objects to DBus structures.

        :param objects: a list of data objects
        :return: a list of DBus structures
        """
        return list(map(cls.to_structure, objects))

    def __repr__(self):
        """Convert this data object to a string."""
        return generate_string_from_data(self)


def get_fields(obj):
    """Return DBus fields of a data object.

    :param obj: a data object
    :return: a map of DBus fields
    """
    fields = getattr(obj, DBUS_FIELDS_ATTRIBUTE, None)

    if fields is None:
        raise DBusStructureError("Fields are not defined at '{}'.".format(DBUS_FIELDS_ATTRIBUTE))

    return fields


def generate_fields(cls):
    """Generate DBus fields from properties of a class.

    Properties of the class will be used to generate a map of a DBus
    fields. The property should have a getter and a setter, otherwise
    an error is raised. The type hint of the getter is used to define
    the type of the DBus field.

    :param cls: a data class
    :return: a map of DBus fields

    :raise DBusStructureError: if the DBus fields cannot be generated
    """
    fields = {}

    for member_name, member in inspect.getmembers(cls):

        # Skip private members.
        if member_name.startswith("_"):
            continue

        # Skip all but properties.
        if not isinstance(member, property):
            continue

        # Get the type hint.
        name = member_name.replace('_', '-')

        if not member.fset:
            raise DBusStructureError("Field '{}' cannot be set.".format(name))

        if not member.fget:
            raise DBusStructureError("Field '{}' cannot be get.".format(name))

        getter_type_hints = get_type_hints(member.fget)
        type_hint = getter_type_hints.get('return', None)

        if not type_hint:
            raise DBusStructureError("Field '{}' has unknown type.".format(name))

        # Create the field.
        fields[name] = DBusField(name, type_hint)

    if not fields:
        raise DBusStructureError("No fields found.")

    return fields


def generate_string_from_data(obj, skip=None, add=None):
    """Generate a string representation of a data object.

    Set the argument 'skip' to skip attributes with sensitive data.

    Set the argument 'add' to add other values to the string
    representation. The attributes in the string representation
    will be sorted alphabetically.

    :param obj: a data object
    :param skip: a list of names that should be skipped or None
    :param add: a list of strings to add or None
    :return: a string representation of the data object
    """
    attributes = []
    skipped_names = set(skip) if skip else set()
    extra_attributes = list(add) if add else []

    for field in get_fields(obj).values():
        if field.data_name in skipped_names:
            continue

        attribute = "{}={}".format(field.data_name, repr(field.get_data(obj)))
        attributes.append(attribute)

    if extra_attributes:
        attributes.extend(extra_attributes)
        attributes.sort()

    return "{}({})".format(obj.__class__.__name__, ", ".join(attributes))
