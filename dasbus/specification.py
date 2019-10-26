#
# Support for DBus XML specification.
#
# Copyright (C) 2019
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
from collections import namedtuple

from dasbus.xml import XMLParser

__all__ = ["DBusSpecificationError", "DBusSpecification", "DBusSpecificationParser"]


class DBusSpecificationError(Exception):
    """Exception for the DBus specification errors."""
    pass


class DBusSpecification(object):
    """DBus XML specification."""

    DIRECTION_IN = "in"
    DIRECTION_OUT = "out"
    ACCESS_READ = "read"
    ACCESS_WRITE = "write"
    ACCESS_READWRITE = "readwrite"
    RETURN_PARAMETER = "return"

    STANDARD_INTERFACES = """
    <node>
        <interface name="org.freedesktop.DBus.Introspectable">
            <method name="Introspect">
            <arg type="s" name="xml_data" direction="out"/>
            </method>
        </interface>
        <interface name="org.freedesktop.DBus.Peer">
            <method name="Ping"/>
            <method name="GetMachineId">
                <arg type="s" name="machine_uuid" direction="out"/>
            </method>
       </interface>
        <interface name="org.freedesktop.DBus.Properties">
            <method name="Get">
                <arg type="s" name="interface_name" direction="in"/>
                <arg type="s" name="property_name" direction="in"/>
                <arg type="v" name="value" direction="out"/>
            </method>
            <method name="GetAll">
                <arg type="s" name="interface_name" direction="in"/>
                <arg type="a{sv}" name="properties" direction="out"/>
            </method>
            <method name="Set">
                <arg type="s" name="interface_name" direction="in"/>
                <arg type="s" name="property_name" direction="in"/>
                <arg type="v" name="value" direction="in"/>
            </method>
            <signal name="PropertiesChanged">
                <arg type="s" name="interface_name"/>
                <arg type="a{sv}" name="changed_properties"/>
                <arg type="as" name="invalidated_properties"/>
            </signal>
        </interface>
    </node>
    """

    # Representation of specification members.
    Signal = namedtuple("Signal", ["name", "interface_name", "type"])
    Method = namedtuple("Method", ["name", "interface_name", "in_type", "out_type"])
    Property = namedtuple("Property", ["name", "interface_name", "readable", "writable", "type"])

    # Specification data holders.
    __slots__ = ["_members"]

    @classmethod
    def from_xml(cls, xml):
        """Return a DBus specification for the given XML."""
        return DBusSpecificationParser.parse_specification(xml, cls)

    def __init__(self):
        """Create a new DBus specification."""
        self._members = {}

    @property
    def interfaces(self):
        """Interfaces of the DBus specification."""
        return list(dict(self._members.keys()).keys())

    @property
    def members(self):
        """Members of the DBus specification."""
        return list(self._members.values())

    def add_member(self, member):
        """Add a member of a DBus interface."""
        self._members[(member.interface_name, member.name)] = member

    def get_member(self, interface_name, member_name):
        """Get a member of a DBus interface."""
        try:
            return self._members[(interface_name, member_name)]
        except KeyError:
            pass

        raise DBusSpecificationError(
            "Unknown member {}.{}.".format(interface_name, member_name)
        )


class DBusSpecificationParser(object):
    """Class for parsing DBus XML specification."""

    # The XML parser.
    xml_parser = XMLParser

    @classmethod
    def parse_specification(cls, xml, factory=DBusSpecification):
        """Generate a representation of a DBus XML specification.

        :param xml: the XML specification to parse
        :param factory: the DBus specification factory
        :return: a representation od the DBus specification
        """
        specification = factory()
        cls._parse_xml(specification, DBusSpecification.STANDARD_INTERFACES)
        cls._parse_xml(specification, xml)
        return specification

    @classmethod
    def _parse_xml(cls, specification, xml):
        """Parse the given XML."""
        node = cls.xml_parser.xml_to_element(xml)

        # Iterate over interfaces.
        for interface_element in node:
            if not cls.xml_parser.is_interface(interface_element):
                continue

            # Parse the interface.
            cls._parse_interface(specification, interface_element)

    @classmethod
    def _parse_interface(cls, specification, interface_element):
        """Parse the interface element from the DBus specification."""
        interface_name = cls.xml_parser.get_name(interface_element)

        # Iterate over members.
        for member_element in interface_element:

            if cls.xml_parser.is_property(member_element):
                member = cls._parse_property(interface_name, member_element)

            elif cls.xml_parser.is_signal(member_element):
                member = cls._parse_signal(interface_name, member_element)

            elif cls.xml_parser.is_method(member_element):
                member = cls._parse_method(interface_name, member_element)

            else:
                continue

            # Add the member specification to the mapping.
            specification.add_member(member)

        return interface_name

    @classmethod
    def _parse_property(cls, interface_name, property_element):
        """Parse the property element from the DBus specification."""
        property_name = cls.xml_parser.get_name(property_element)
        property_type = cls.xml_parser.get_type(property_element)
        property_access = cls.xml_parser.get_access(property_element)

        readable = property_access in (
            DBusSpecification.ACCESS_READ,
            DBusSpecification.ACCESS_READWRITE
        )

        writable = property_access in (
            DBusSpecification.ACCESS_WRITE,
            DBusSpecification.ACCESS_READWRITE
        )

        return DBusSpecification.Property(
            name=property_name,
            interface_name=interface_name,
            readable=readable,
            writable=writable,
            type=property_type
        )

    @classmethod
    def _parse_signal(cls, interface_name, signal_element):
        """Parse the signal element from the DBus specification."""
        signal_name = cls.xml_parser.get_name(signal_element)
        signal_type = []

        for element in signal_element:
            if not cls.xml_parser.is_parameter(element):
                continue

            element_type = cls.xml_parser.get_type(element)
            signal_type.append(element_type)

        return DBusSpecification.Signal(
            name=signal_name,
            interface_name=interface_name,
            type=cls._get_type(signal_type)
        )

    @classmethod
    def _parse_method(cls, interface_name, method_element):
        """Parse the method element from the DBus specification."""
        method_name = cls.xml_parser.get_name(method_element)
        in_types = []
        out_types = []

        for element in method_element:
            if not cls.xml_parser.is_parameter(element):
                continue

            direction = cls.xml_parser.get_direction(element)
            element_type = cls.xml_parser.get_type(element)

            if direction == DBusSpecification.DIRECTION_IN:
                in_types.append(element_type)

            elif direction == DBusSpecification.DIRECTION_OUT:
                out_types.append(element_type)

        return DBusSpecification.Method(
            name=method_name,
            interface_name=interface_name,
            in_type=cls._get_type(in_types),
            out_type=cls._get_type(out_types)
        )

    @classmethod
    def _get_type(cls, types):
        """Join types into one value."""
        if not types:
            return None

        return "({})".format("".join(types))
