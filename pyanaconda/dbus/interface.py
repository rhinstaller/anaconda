#
# interface.py:  support for generating XML with interface description
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
import inspect
import re

from inspect import Parameter
from typing import get_type_hints
from pydbus.generic import signal

from pyanaconda.dbus.typing import get_dbus_type
from pyanaconda.dbus.xml import XMLGenerator

__all__ = ["dbus_class", "dbus_interface", "dbus_signal"]


class dbus_signal(signal):
    """DBus signal.

    Can be used as:
        Signal = dbus_signal()

    Or as a method decorator:

        @dbus_signal
        def Signal(x: Int, y: Double):
            pass

    Signal is defined by the type hints of a decorated method.
    This method is accessible as: signal.definition

    If the signal is not defined by a method, it is expected to
    have no arguments and signal.definition is equal to None.
    """
    def __init__(self, method=None):
        super(dbus_signal, self).__init__()
        self.definition = method


def dbus_interface(interface_name):
    """DBus interface.

    A new DBus interface can be defined as:

        @dbus_interface
        class Interface():
            ...

    The interface will be generated from the given class cls
    with a name interface_name and added to the DBus XML
    specification of the class.

    The XML specification is accessible as:
        Interface.dbus
    """
    def decorated(cls):
        generator = DBusSpecification()
        cls.dbus = generator.generate_specification(cls, interface_name)
        return cls
    return decorated


def dbus_class(cls):
    """DBus class.

    A new DBus class can be defined as:

        @dbus_class
        class Class(Interface):
            ...

    DBus class can implement DBus interfaces, but it cannot
    define a new interface.

    The DBus XML specification will be generated from
    implemented interfaces (inherited) and it will be
    accessible as:
        Class.dbus
    """
    # Get the interface decorator without a name.
    decorated = dbus_interface(None)
    # Apply the decorator on the given class.
    return decorated(cls)


class DBusSpecificationError(Exception):
    pass


class DBusSpecification(object):
    """Class for generating DBus XML specification."""

    DIRECTION_IN = "in"
    DIRECTION_OUT = "out"

    ACCESS_READ = "read"
    ACCESS_WRITE = "write"
    ACCESS_READWRITE = "readwrite"

    RETURN_PARAMETER = "return"

    NAME_PATTERN = re.compile(r'[A-Z][A-Za-z0-9]*')

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

    def __init__(self, xml_generator=XMLGenerator()):
        self.xml_generator = xml_generator

    def generate_specification(self, cls, interface_name=None):
        """Generates DBus XML specification for given class.

        If class defines a new interface, it will be added to
        the specification.

        :param cls: class object to decorate
        :param str interface_name: name of the interface defined by class
        :return str: DBus specification in XML
        """
        # Collect all interfaces that class inherits.
        interfaces = self._collect_interfaces(cls)

        # Generate a new interface.
        if interface_name:
            all_interfaces = self._collect_standard_interfaces()
            all_interfaces.update(interfaces)
            interface = self._generate_interface(cls, all_interfaces, interface_name)
            interfaces[interface_name] = interface

        # Generate XML specification for the given class.
        node = self._generate_node(cls, interfaces)
        return self.xml_generator.element_to_xml(node)

    def generate_properties_mapping(self, specification):
        """Generates mapping of properties to interfaces.

        The map can be used to detect the interface the property
        belongs to. We assume that the specification cannot contain
        interfaces with same property names.

        :param specification: DBus specification in XML
        :return: a mapping of property names to interface names
        """
        node = self.xml_generator.xml_to_element(specification)
        interfaces = self.xml_generator.get_interfaces_from_node(node)

        mapping = {}

        for interface_name, element in interfaces.items():
            properties = self.xml_generator.get_properties_from_interface(element)

            for property_name in properties:
                if property_name in mapping:
                    msg = "Property {} from {} is already defined in {}.".format(
                        property_name, interface_name, mapping[property_name]
                    )
                    raise DBusSpecificationError(msg)

                mapping[property_name] = interface_name

        return mapping

    def _collect_standard_interfaces(self):
        """Collect standard interfaces.

        Standard interfaces are implemented by default.

        :return: a dictionary of standard interfaces
        """
        node = self.xml_generator.xml_to_element(self.STANDARD_INTERFACES)
        return self.xml_generator.get_interfaces_from_node(node)

    def _collect_interfaces(self, cls):
        """Collect interfaces implemented by the class.

        Returns a dictionary that maps interface names
        to interface elements.

        :param cls: a class object
        :return: a dictionary of implemented interfaces
        """
        interfaces = dict()

        # Visit cls and base classes in reversed order.
        for member in reversed(inspect.getmro(cls)):
            # Skip classes with no specification.
            if not getattr(member, "dbus", None):
                continue

            # Update found interfaces.
            node = self.xml_generator.xml_to_element(member.dbus)
            node_interfaces = self.xml_generator.get_interfaces_from_node(node)
            interfaces.update(node_interfaces)

        return interfaces

    def _generate_interface(self, cls, interfaces, interface_name):
        """Generate interface defined by given class.

        :param cls: a class object that defines the interface
        :param interfaces: a dictionary of implemented interfaces
        :param interface_name: a name of the new interface
        :return: an new interface element

        :raises DBusSpecificationError: if a class member cannot be exported
        """
        interface = self.xml_generator.get_interface_element(interface_name)

        # Search class members.
        for member_name, member in inspect.getmembers(cls):
            # Check it the name is exportable.
            if not self._is_exportable(member_name):
                continue

            # Skip names already defined in implemented interfaces.
            if self._is_defined(interfaces, member_name):
                continue

            # Generate XML element for exportable member.
            if self._is_signal(member):
                element = self._generate_signal(member, member_name)
            elif self._is_property(member):
                element = self._generate_property(member, member_name)
            elif self._is_method(member):
                element = self._generate_method(member, member_name)
            else:
                raise DBusSpecificationError("%s.%s cannot be exported."
                                             % (cls.__name__, member_name))

            # Add generated element to the interface.
            self.xml_generator.add_child(interface, element)

        return interface

    def _is_exportable(self, member_name):
        """Is the name of a class member exportable?

        The name is exportable if it follows the DBus specification.
        Only CamelCase names are allowed.
        """
        return bool(self.NAME_PATTERN.fullmatch(member_name))

    def _is_defined(self, interfaces, member_name):
        """Is the member name defined in given interfaces?

        :param interfaces: a dictionary of interfaces
        :param member_name: a name of the class member
        :return: True if the name is defined, otherwise False
        """
        for interface in interfaces.values():
            for member in interface:
                # Is it a signal, a property or a method?
                if not self.xml_generator.is_member(member):
                    continue
                # Does it have the same name?
                if not self.xml_generator.has_name(member, member_name):
                    continue
                # The member is already defined.
                return True

        return False

    def _is_signal(self, member):
        """Is the class member a DBus signal?"""
        return isinstance(member, dbus_signal)

    def _generate_signal(self, member, member_name):
        """Generate signal defined by a class member.

        :param member: a dbus_signal object.
        :param member_name: a name of the signal
        :return: a signal element

        raises DBusSpecificationError: if signal has defined return type
        """
        element = self.xml_generator.get_signal_element(member_name)
        method = member.definition

        if not method:
            return element

        for name, type_hint, direction in self._iterate_parameters(method):
            # Only input parameters can be defined.
            if direction == self.DIRECTION_OUT:
                raise DBusSpecificationError("Signal %s has defined return type." % member_name)

            # All parameters are exported as output parameters (see specification).
            direction = self.DIRECTION_OUT
            parameter = self.xml_generator.create_parameter(name, get_dbus_type(type_hint), direction)
            self.xml_generator.add_child(element, parameter)

        return element

    def _iterate_parameters(self, member):
        """Iterate over method parameters.

        For every parameter returns its name, a type hint and a direction.

        :param member: a method object
        :return: an iterator

        raises DBusSpecificationError: if parameters are invalid
        """
        # Get type hints for parameters.
        type_hints = get_type_hints(member)

        # Get method signature.
        signature = inspect.signature(member)

        # Iterate over method parameters, skip self.
        for name in list(signature.parameters)[1:]:
            # Check the kind of the parameter
            if signature.parameters[name].kind != Parameter.POSITIONAL_OR_KEYWORD:
                raise DBusSpecificationError("Only positional or keyword arguments are allowed.")

            # Check if the type is defined.
            if name not in type_hints:
                raise DBusSpecificationError("Parameter %s doesn't have defined type." % name)

            yield name, type_hints[name], self.DIRECTION_IN

        # Is the return type defined?
        if signature.return_annotation is signature.empty:
            return

        # Is the return type other than None?
        if signature.return_annotation is None:
            return

        yield self.RETURN_PARAMETER, signature.return_annotation, self.DIRECTION_OUT

    def _is_property(self, member):
        """Is the class member a DBus property?"""
        return isinstance(member, property)

    def _generate_property(self, member, member_name):
        """Generate DBus property defined by class member.

        :param member: a property object
        :param member_name: a property name
        :return: a property element

        raises DBusSpecificationError: if the property is invalid
        """
        access = None
        type_hint = None

        try:
            # Process the setter.
            if member.fset:
                [(_, type_hint, _)] = self._iterate_parameters(member.fset)
                access = self.ACCESS_WRITE

            # Process the getter.
            if member.fget:
                [(_, type_hint, _)] = self._iterate_parameters(member.fget)
                access = self.ACCESS_READ

        except ValueError:
            raise DBusSpecificationError("Property %s has invalid parameters." % member_name)

        # Property has both.
        if member.fget and member.fset:
            access = self.ACCESS_READWRITE

        if access is None:
            raise DBusSpecificationError("Property %s is not accessible." % member_name)

        return self.xml_generator.create_property(member_name, get_dbus_type(type_hint), access)

    def _is_method(self, member):
        """Is the class member a DBus method?

        Ignore the difference between instance method and class method.

        For example:
            class Foo(object):
                def bar(self, x):
                    pass

            inspect.isfunction(Foo.bar) # True
            inspect.isfunction(Foo().bar) # False

            inspect.ismethod(Foo.bar) # False
            inspect.ismethod(Foo().bar) # True

            _is_method(Foo.bar) # True
            _is_method(Foo().bar) # True
        """
        return inspect.ismethod(member) or inspect.isfunction(member)

    def _generate_method(self, member, member_name):
        """Generate method defined by given class member.

        :param member: a method object
        :param member_name: a name of the method
        :return: a method element
        """
        method = self.xml_generator.get_method_element(member_name)

        # Process the parameters.
        for name, type_hint, direction in self._iterate_parameters(member):
            # Create the parameter element.
            parameter = self.xml_generator.create_parameter(name, get_dbus_type(type_hint), direction)
            # Add the element to the method element.
            self.xml_generator.add_child(method, parameter)

        return method

    def _generate_node(self, cls, interfaces):
        """Generate node element that specifies the given class.

        :param cls: a class object
        :param interfaces: a dictionary of interfaces
        :return: a node element
        """
        node = self.xml_generator.get_node_element()

        # Add comment about specified class.
        self.xml_generator.add_comment(node, "Specifies %s" % cls.__name__)

        # Add interfaces sorted by their names.
        for interface_name in sorted(interfaces.keys()):
            self.xml_generator.add_child(node, interfaces[interface_name])

        return node
