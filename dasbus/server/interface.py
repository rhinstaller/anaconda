#
# Server support for DBus interfaces
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

from dasbus.signal import Signal
from dasbus.specification import DBusSpecificationError, DBusSpecification
from dasbus.typing import get_dbus_type
from dasbus.xml import XMLGenerator

__all__ = ["dbus_class", "dbus_interface", "dbus_signal", "get_xml"]


# Class attribute for the XML specification.
DBUS_XML_ATTRIBUTE = "__dbus_xml__"


class dbus_signal(object):
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
    def __init__(self, definition=None, factory=Signal):
        """Create a signal descriptor.

        :param definition: a definition of the emit function
        :param factory: a signal factory
        """
        self.definition = definition
        self.factory = factory
        self.name = None

    def __set_name__(self, owner, name):
        """Set a name of the descriptor

        The descriptor has been assigned to the specified name.
        Generate a name of a private attribute that will be set
        to a signal in the __get__ method.

        For example: __dbus_signal_my_name

        :param owner: the owning class
        :param name: the descriptor name
        """
        if self.name is not None:
            return

        self.name = "__{}_{}".format(
            type(self).__name__.lower(),
            name.lower()
        )

    def __get__(self, instance, owner):
        """Get a value of the descriptor.

        If the descriptor is accessed as a class attribute,
        return the descriptor.

        If the descriptor is accessed as an instance attribute,
        return a signal created by the signal factory.

        :param instance: an instance of the owning class
        :param owner: an owning class
        :return: a value of the attribute
        """
        if instance is None:
            return self

        signal = getattr(instance, self.name, None)

        if signal is None:
            signal = self.factory()
            setattr(instance, self.name, signal)

        return signal

    def __set__(self, instance, value):
        """Set a value of the descriptor."""
        raise AttributeError("Can't set DBus signal.")


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
        Interface.__dbus_xml__
    """
    def decorated(cls):
        generator = DBusSpecificationGenerator
        xml = generator.generate_specification(cls, interface_name)
        setattr(cls, DBUS_XML_ATTRIBUTE, xml)
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
        Class.__dbus_xml__
    """
    # Get the interface decorator without a name.
    decorated = dbus_interface(None)
    # Apply the decorator on the given class.
    return decorated(cls)


def get_xml(obj):
    """Return XML specification of an object.

    :param obj: an object decorated with @dbus_interface or @dbus_class
    :return: a string with XML specification
    """
    xml_specification = getattr(obj, DBUS_XML_ATTRIBUTE, None)

    if xml_specification is None:
        raise DBusSpecificationError(
            "XML specification is not defined at '{}'.".format(DBUS_XML_ATTRIBUTE)
        )

    return xml_specification


class DBusSpecificationGenerator(object):
    """Class for generating DBus XML specification."""

    # The XML generator.
    xml_generator = XMLGenerator

    # The pattern of a DBus member name.
    NAME_PATTERN = re.compile(r'[A-Z][A-Za-z0-9]*')

    @classmethod
    def generate_specification(cls, interface_cls, interface_name=None):
        """Generates DBus XML specification for given class.

        If class defines a new interface, it will be added to
        the specification.

        :param interface_cls: class object to decorate
        :param str interface_name: name of the interface defined by class
        :return str: DBus specification in XML
        """
        # Collect all interfaces that class inherits.
        interfaces = cls._collect_interfaces(interface_cls)

        # Generate a new interface.
        if interface_name:
            all_interfaces = cls._collect_standard_interfaces()
            all_interfaces.update(interfaces)
            interface = cls._generate_interface(interface_cls, all_interfaces, interface_name)
            interfaces[interface_name] = interface

        # Generate XML specification for the given class.
        node = cls._generate_node(interface_cls, interfaces)
        return cls.xml_generator.element_to_xml(node)

    @classmethod
    def _collect_standard_interfaces(cls):
        """Collect standard interfaces.

        Standard interfaces are implemented by default.

        :return: a dictionary of standard interfaces
        """
        node = cls.xml_generator.xml_to_element(DBusSpecification.STANDARD_INTERFACES)
        return cls.xml_generator.get_interfaces_from_node(node)

    @classmethod
    def _collect_interfaces(cls, interface_cls):
        """Collect interfaces implemented by the class.

        Returns a dictionary that maps interface names
        to interface elements.

        :param interface_cls: a class object
        :return: a dictionary of implemented interfaces
        """
        interfaces = dict()

        # Visit interface_cls and base classes in reversed order.
        for member in reversed(inspect.getmro(interface_cls)):
            # Skip classes with no specification.
            member_xml = getattr(member, DBUS_XML_ATTRIBUTE, None)
            if not member_xml:
                continue

            # Update found interfaces.
            node = cls.xml_generator.xml_to_element(member_xml)
            node_interfaces = cls.xml_generator.get_interfaces_from_node(node)
            interfaces.update(node_interfaces)

        return interfaces

    @classmethod
    def _generate_interface(cls, interface_cls, interfaces, interface_name):
        """Generate interface defined by given class.

        :param interface_cls: a class object that defines the interface
        :param interfaces: a dictionary of implemented interfaces
        :param interface_name: a name of the new interface
        :return: an new interface element

        :raises DBusSpecificationError: if a class member cannot be exported
        """
        interface = cls.xml_generator.create_interface(interface_name)

        # Search class members.
        for member_name, member in inspect.getmembers(interface_cls):
            # Check it the name is exportable.
            if not cls._is_exportable(member_name):
                continue

            # Skip names already defined in implemented interfaces.
            if cls._is_defined(interfaces, member_name):
                continue

            # Generate XML element for exportable member.
            if cls._is_signal(member):
                element = cls._generate_signal(member, member_name)
            elif cls._is_property(member):
                element = cls._generate_property(member, member_name)
            elif cls._is_method(member):
                element = cls._generate_method(member, member_name)
            else:
                raise DBusSpecificationError("{}.{} cannot be exported.".format(
                    interface_cls.__name__, member_name
                ))

            # Add generated element to the interface.
            cls.xml_generator.add_child(interface, element)

        return interface

    @classmethod
    def _is_exportable(cls, member_name):
        """Is the name of a class member exportable?

        The name is exportable if it follows the DBus specification.
        Only CamelCase names are allowed.
        """
        return bool(cls.NAME_PATTERN.fullmatch(member_name))

    @classmethod
    def _is_defined(cls, interfaces, member_name):
        """Is the member name defined in given interfaces?

        :param interfaces: a dictionary of interfaces
        :param member_name: a name of the class member
        :return: True if the name is defined, otherwise False
        """
        for interface in interfaces.values():
            for member in interface:
                # Is it a signal, a property or a method?
                if not cls.xml_generator.is_member(member):
                    continue
                # Does it have the same name?
                if not cls.xml_generator.has_name(member, member_name):
                    continue
                # The member is already defined.
                return True

        return False

    @classmethod
    def _is_signal(cls, member):
        """Is the class member a DBus signal?"""
        return isinstance(member, dbus_signal)

    @classmethod
    def _generate_signal(cls, member, member_name):
        """Generate signal defined by a class member.

        :param member: a dbus_signal object.
        :param member_name: a name of the signal
        :return: a signal element

        raises DBusSpecificationError: if signal has defined return type
        """
        element = cls.xml_generator.create_signal(member_name)
        method = member.definition

        if not method:
            return element

        for name, type_hint, direction in cls._iterate_parameters(method):
            # Only input parameters can be defined.
            if direction == DBusSpecification.DIRECTION_OUT:
                raise DBusSpecificationError("Signal %s has defined return type." % member_name)

            # All parameters are exported as output parameters (see specification).
            direction = DBusSpecification.DIRECTION_OUT
            parameter = cls.xml_generator.create_parameter(name, get_dbus_type(type_hint), direction)
            cls.xml_generator.add_child(element, parameter)

        return element

    @classmethod
    def _iterate_parameters(cls, member):
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

        # Iterate over method parameters, skip cls.
        for name in list(signature.parameters)[1:]:
            # Check the kind of the parameter
            if signature.parameters[name].kind != Parameter.POSITIONAL_OR_KEYWORD:
                raise DBusSpecificationError("Only positional or keyword arguments are allowed.")

            # Check if the type is defined.
            if name not in type_hints:
                raise DBusSpecificationError("Parameter %s doesn't have defined type." % name)

            yield name, type_hints[name], DBusSpecification.DIRECTION_IN

        # Is the return type defined?
        if signature.return_annotation is signature.empty:
            return

        # Is the return type other than None?
        if signature.return_annotation is None:
            return

        yield (
            DBusSpecification.RETURN_PARAMETER,
            signature.return_annotation,
            DBusSpecification.DIRECTION_OUT
        )

    @classmethod
    def _is_property(cls, member):
        """Is the class member a DBus property?"""
        return isinstance(member, property)

    @classmethod
    def _generate_property(cls, member, member_name):
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
                [(_, type_hint, _)] = cls._iterate_parameters(member.fset)
                access = DBusSpecification.ACCESS_WRITE

            # Process the getter.
            if member.fget:
                [(_, type_hint, _)] = cls._iterate_parameters(member.fget)
                access = DBusSpecification.ACCESS_READ

        except ValueError:
            raise DBusSpecificationError("Property %s has invalid parameters." % member_name)

        # Property has both.
        if member.fget and member.fset:
            access = DBusSpecification.ACCESS_READWRITE

        if access is None:
            raise DBusSpecificationError("Property %s is not accessible." % member_name)

        return cls.xml_generator.create_property(member_name, get_dbus_type(type_hint), access)

    @classmethod
    def _is_method(cls, member):
        """Is the class member a DBus method?

        Ignore the difference between instance method and class method.

        For example:
            class Foo(object):
                def bar(cls, x):
                    pass

            inspect.isfunction(Foo.bar) # True
            inspect.isfunction(Foo().bar) # False

            inspect.ismethod(Foo.bar) # False
            inspect.ismethod(Foo().bar) # True

            _is_method(Foo.bar) # True
            _is_method(Foo().bar) # True
        """
        return inspect.ismethod(member) or inspect.isfunction(member)

    @classmethod
    def _generate_method(cls, member, member_name):
        """Generate method defined by given class member.

        :param member: a method object
        :param member_name: a name of the method
        :return: a method element
        """
        method = cls.xml_generator.create_method(member_name)

        # Process the parameters.
        for name, type_hint, direction in cls._iterate_parameters(member):
            # Create the parameter element.
            parameter = cls.xml_generator.create_parameter(name, get_dbus_type(type_hint), direction)
            # Add the element to the method element.
            cls.xml_generator.add_child(method, parameter)

        return method

    @classmethod
    def _generate_node(cls, interface_cls, interfaces):
        """Generate node element that specifies the given class.

        :param interface_cls: a class object
        :param interfaces: a dictionary of interfaces
        :return: a node element
        """
        node = cls.xml_generator.create_node()

        # Add comment about specified class.
        cls.xml_generator.add_comment(node, "Specifies %s" % interface_cls.__name__)

        # Add interfaces sorted by their names.
        for interface_name in sorted(interfaces.keys()):
            cls.xml_generator.add_child(node, interfaces[interface_name])

        return node
