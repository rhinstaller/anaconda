#
# Server support for DBus properties
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
# For more info about DBus specification see:
# https://dbus.freedesktop.org/doc/dbus-specification.html#introspection-format
#
from abc import ABC
from collections import defaultdict
from functools import wraps

from dasbus.server.interface import dbus_signal, get_xml
from dasbus.specification import DBusSpecification, DBusSpecificationError
from dasbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["emits_properties_changed", "PropertiesException", "PropertiesInterface"]


def emits_properties_changed(method):
    """Decorator for emitting properties changes.

    The decorated method has to be a member of a class that
    inherits PropertiesInterface.

    :param method: a DBus method of a class that inherits PropertiesInterface
    :return: a wrapper of a DBus method that emits PropertiesChanged
    """
    @wraps(method)
    def wrapper(obj, *args, **kwargs):
        result = method(obj, *args, **kwargs)
        obj.flush_changes()
        return result

    return wrapper


class PropertiesException(Exception):
    """Exception for DBus properties."""
    pass


class PropertiesChanges(object):
    """Cache for properties changes.

    This class is useful to collect the changed properties
    and their values, before they are emitted on DBus.
    """

    def __init__(self, obj):
        """Create the cache.

        :param obj: an object with DBus properties
        """
        self._object = obj
        self._properties_names = set()
        self._properties_specs = self._find_properties_specs(obj)

    def _find_properties_specs(self, obj):
        """Find specifications of DBus properties.

        :param obj: an object with DBus properties
        :return: a map of property names and their specifications
        """
        specification = DBusSpecification.from_xml(get_xml(obj))
        properties_specs = {}

        for member in specification.members:
            if not isinstance(member, DBusSpecification.Property):
                continue

            if member.name in properties_specs:
                raise DBusSpecificationError(
                    "The property {} is defined in {} and {}.".format(
                        member.name,
                        member.interface_name,
                        properties_specs[member.name].interface_name
                    )
                )

            properties_specs[member.name] = member

        return properties_specs

    def flush(self):
        """Flush the cache.

        The content of the cache will be composed to requests
        and the cache will be cleared.

        The requests can be used to emit the PropertiesChanged
        signal. The requests are a list of tuples, that contain
        an interface name and a dictionary of properties changes.

        :return: a list of requests
        """
        content = self._properties_names
        self._properties_names = set()
        requests = defaultdict(dict)

        for property_name in content:
            # Find the property specification.
            member = self._properties_specs[property_name]

            # Get the property value.
            value = getattr(self._object, property_name)
            variant = get_variant(member.type, value)

            # Create a request.
            requests[member.interface_name][member.name] = variant

        return requests.items()

    def check_property(self, property_name):
        """Check if the property name is valid."""
        if property_name not in self._properties_specs:
            raise PropertiesException("Unknown interface of property {}."
                                      .format(property_name))

    def update(self, property_name):
        """Update the cache."""
        self.check_property(property_name)
        self._properties_names.add(property_name)


class PropertiesInterface(ABC):
    """Standard DBus interface org.freedesktop.DBus.Properties.

    DBus objects don't have to inherit this class, because the DBus library provides
    support for this interface by default. This class only extends this support.

    Report the changed property:

        self.report_changed_property('X')

    Emit all changes when the method is done:

        @emits_properties_changed
        def SetX(x: Int):
            self.set_x(x)

    """

    def __init__(self):
        """Initialize the interface."""
        self._properties_changes = PropertiesChanges(self)

    @dbus_signal
    def PropertiesChanged(self, interface: Str, changed: Dict[Str, Variant], invalid: List[Str]):
        """Standard signal properties changed.

        :param interface: a name of an interface
        :param changed: a dictionary of changed properties
        :param invalid: a list of invalidated properties
        :return:
        """
        pass

    def report_changed_property(self, property_name):
        """Reports changed DBus property.

        :param property_name: a name of a DBus property
        """
        self._properties_changes.update(property_name)

    def flush_changes(self):
        """Flush properties changes."""
        requests = self._properties_changes.flush()

        for interface, changes in requests:
            self.PropertiesChanged(interface, changes, [])
