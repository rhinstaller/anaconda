#
# xml.py:  support for generating XML with interface description
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
from xml.etree import ElementTree
from xml.dom import minidom


class XMLGenerator(object):
    """Class for creating XML and XML elements."""

    @staticmethod
    def element_to_xml(element):
        """Return XML of the element."""
        return ElementTree.tostring(element, method="xml", encoding="unicode")

    @staticmethod
    def xml_to_element(xml):
        return ElementTree.fromstring(xml)

    @staticmethod
    def prettify_xml(xml):
        """Return pretty printed XML."""
        # Remove newlines and extra whitespaces,
        xml_line = "".join([line.strip() for line in xml.splitlines()])

        # Generate pretty xml.
        return minidom.parseString(xml_line).toprettyxml(indent="  ")

    @staticmethod
    def add_child(parent_element, child_element):
        """Append the child element to the parent element."""
        parent_element.append(child_element)

    @staticmethod
    def add_comment(element, comment):
        element.append(ElementTree.Comment(text=comment))

    @staticmethod
    def get_node_element():
        """Create a node element called node."""
        return ElementTree.Element("node")

    @staticmethod
    def get_interface_element(name):
        """Create an interface element."""
        return ElementTree.Element("interface", {"name": name})

    @staticmethod
    def get_interfaces_from_node(node_element):
        """Return a dictionary of interfaces defined in a node element."""
        interfaces = dict()

        for element in node_element.iterfind("interface"):
            interfaces[element.attrib["name"]] = element

        return interfaces

    @staticmethod
    def get_signal_element(name):
        """Create a signal element."""
        return ElementTree.Element("signal", {"name": name})

    @staticmethod
    def get_method_element(name):
        """Create a method element."""
        return ElementTree.Element("method", {"name": name})

    @staticmethod
    def create_parameter(name, param_type, direction):
        """Create a parameter element."""
        tag = "arg"
        attr = {
            "name": name,
            "type": param_type,
            "direction": direction
        }
        return ElementTree.Element(tag, attr)

    @staticmethod
    def create_property(name, property_type, access):
        """Create a property element."""
        tag = "property"
        attr = {
            "name": name,
            "type": property_type,
            "access": access
        }
        return ElementTree.Element(tag, attr)

    @staticmethod
    def is_member(member_node):
        return member_node.tag in ("method", "signal", "property")

    @staticmethod
    def has_name(node, node_name):
        return node.attrib.get("name", "") == node_name
