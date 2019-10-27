#
# Server support for DBus objects
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
import logging
from abc import ABC, abstractmethod
from functools import partial

from pyanaconda.core.signal import Signal
from dasbus.error import GLibErrorHandler
from dasbus.interface import get_xml
from dasbus.specification import DBusSpecification, DBusSpecificationError
from dasbus.typing import get_variant

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio

log = logging.getLogger(__name__)

__all__ = ["GLibServer", "AbstractServerObjectHandler", "ServerObjectHandler"]


class GLibServer(object):
    """The low-level DBus server library based on GLib."""

    @classmethod
    def emit_signal(cls, connection, object_path, interface_name, signal_name, parameters,
                    destination=None):
        """Emit a DBus signal."""
        connection.emit_signal(
            destination,
            object_path,
            interface_name,
            signal_name,
            parameters
        )

    @classmethod
    def register_object(cls, connection, object_path, object_xml, callback, callback_args=()):
        """Register an object on DBus."""
        node_info = Gio.DBusNodeInfo.new_for_xml(object_xml)
        method_call_closure = partial(cls._object_callback, user_data=(callback, callback_args))
        registrations = []

        if not node_info.interfaces:
            raise DBusSpecificationError("No interfaces for registration.")

        for interface_info in node_info.interfaces:
            registration_id = connection.register_object(
                object_path,
                interface_info,
                method_call_closure,
                None,
                None
            )
            registrations.append(registration_id)

        return partial(cls._unregister_object, connection, registrations)

    @classmethod
    def _unregister_object(cls, connection, registrations):
        """Unregister an object from DBus."""
        for registration_id in registrations:
            connection.unregister_object(registration_id)

    @classmethod
    def _object_callback(cls, connection, sender, object_path, interface_name, method_name,
                         parameters, invocation, user_data):
        # Prepare the user's callback.
        callback, callback_args = user_data

        # Call user's callback.
        callback(invocation, interface_name, method_name, parameters, *callback_args)

    @classmethod
    def set_call_error(cls, invocation, error_name, error_message):
        """Set the error of the DBus call.

        :param invocation: an invocation of a DBus call
        :param error_name: a DBus name of the error
        :param error_message: an error message
        """
        invocation.return_dbus_error(error_name, error_message)

    @classmethod
    def set_call_reply(cls, invocation, out_type, out_value):
        """Set the reply of the DBus call.

        :param invocation: an invocation of a DBus call
        :param out_type: a type of the reply
        :param out_value: a value of the reply
        """
        reply_value = None

        if out_type is not None:
            reply_value = get_variant(out_type, (out_value, ))

        invocation.return_value(reply_value)


class AbstractServerObjectHandler(ABC):
    """The abstract handler of a published object."""

    __slots__ = ["_message_bus", "_object_path", "_object", "_specification"]

    def __init__(self, message_bus, object_path, obj):
        """Create a new handler.

        :param message_bus: a message bus
        :param object_path: a DBus path of the object
        :param obj: a Python instance of the object
        """
        self._message_bus = message_bus
        self._object_path = object_path
        self._object = obj
        self._specification = None

    @property
    def specification(self):
        """DBus specification."""
        if not self._specification:
            self._specification = self._get_specification()

        return self._specification

    def _get_specification(self):
        """Get the DBus specification.

        :return: a DBus specification
        """
        return DBusSpecification.from_xml(self._get_xml_specification())

    @abstractmethod
    def _get_xml_specification(self):
        """Get the XML specification.

        :return: a XML specification
        """
        return ""

    @abstractmethod
    def connect_object(self):
        """Connect the object to DBus.

        Handle emitted signals of the object with the _emit_signal method
        and handle incoming DBus calls with the _handle_call method.
        """
        pass

    @abstractmethod
    def disconnect_object(self):
        """Disconnect the object from DBus.

        Unregister the object and disconnect all signals.
        """
        pass

    @abstractmethod
    def _connect_signal(self, interface_name, signal_name):
        """Connect a DBus signal.

        :param interface_name: a DBus interface name
        :param signal_name: a DBus signal name
        """
        pass

    @abstractmethod
    def _emit_signal(self, interface_name, signal_name, *parameters):
        """Handle a DBus signal.

        :param interface_name: a DBus interface name
        :param signal_name: a DBus name of the signal
        :param parameters: a signal parameters
        """
        pass

    def _handle_call(self, interface_name, method_name, *parameters):
        """Handle a DBus call.

        :param interface_name: a name of the interface
        :param method_name: a name of the called method
        :param parameters: parameters of the call
        :return: a result of the DBus call
        """
        handler = self._find_handler(interface_name, method_name)
        return handler(*parameters)

    def _find_member_spec(self, interface_name, member_name):
        """Find a specification of the DBus member.

        :param interface_name: a name of the interface
        :param member_name: a name of the member
        :return: a specification of the member
        """
        return self.specification.get_member(
            interface_name, member_name
        )

    def _find_handler(self, interface_name, member_name):
        """Find a handler of a DBus member.

        :param interface_name: a name of the interface
        :param member_name: a name of the method
        :return: a handler
        """
        handler = self._find_object_handler(interface_name, member_name) \
            or self._find_default_handler(interface_name, member_name)

        if not handler:
            raise AttributeError("The member {}.{} has no handler.".format(
                interface_name, member_name
            ))

        return handler

    def _find_object_handler(self, interface_name, member_name):
        """Get an object handler of a DBus call.

        By default, DBus interfaces with members of the same name are
        not supported, so the given interface name is not used to find
        the object handler.

        :param interface_name: a name of the interface.
        :param member_name: a name of the member
        :return: a handler or None
        """
        return getattr(self._object, member_name, None)

    @abstractmethod
    def _find_default_handler(self, interface_name, member_name):
        """Find a default handler of a DBus call.

        :param interface_name: a name of the interface
        :param member_name: a name of the member
        :return: a handler or None
        """
        pass


class ServerObjectHandler(AbstractServerObjectHandler):
    """The handler of an object published on DBus."""

    __slots__ = ["_server", "_signal_factory", "_error_handler", "_registrations"]

    def __init__(self, message_bus, object_path, obj, server=GLibServer,
                 signal_factory=Signal, error_handler=GLibErrorHandler):
        super().__init__(message_bus, object_path, obj)
        self._server = server
        self._signal_factory = signal_factory
        self._error_handler = error_handler
        self._registrations = []

    def _get_xml_specification(self):
        """Get the XML specification.

        :return: a XML specification
        """
        return get_xml(self._object)

    def connect_object(self):
        """Connect the object to DBus."""
        self._register_object()
        self._connect_signals()

    def disconnect_object(self):
        """Disconnect the object from DBus."""
        while self._registrations:
            callback = self._registrations.pop()
            callback()

    def _register_object(self):
        """Register to DBus calls.

        :return: an unregistering callback
        """
        unregister = self._server.register_object(
            self._message_bus.connection,
            self._object_path,
            self._get_xml_specification(),
            self._method_callback
        )

        self._registrations.append(unregister)

    def _connect_signals(self):
        """Connect all DBus signals."""
        for member in self.specification.members:
            if not isinstance(member, DBusSpecification.Signal):
                continue

            self._connect_signal(
                member.interface_name,
                member.name
            )

    def _connect_signal(self, interface_name, signal_name):
        """Connect a DBus signal.

        :param interface_name: a DBus interface name
        :param signal_name: a DBus signal name
        :return: a disconnecting callback
        """
        callback = self._find_emitter(interface_name, signal_name)
        signal = self._find_handler(interface_name, signal_name)
        signal.connect(callback)

        disconnect = partial(signal.disconnect, callback)
        self._registrations.append(disconnect)

    def _find_emitter(self, interface_name, signal_name):
        """Find an emitter of a DBus signal.

        :param interface_name: a DBus interface name
        :param signal_name: a DBus signal name
        :return: a callback
        """
        if interface_name == "org.freedesktop.DBus.Properties":
            if signal_name == "PropertiesChanged":
                return partial(self._emit_properties_changed)

        return partial(self._emit_signal, interface_name, signal_name)

    def _emit_signal(self, interface_name, signal_name, *parameters):
        """Handle a DBus signal.

        :param interface_name: a DBus interface name
        :param signal_name: a DBus signal name
        :param parameters: a signal parameters
        """
        member = self._find_member_spec(interface_name, signal_name)

        if not parameters:
            parameters = None

        if member.type is not None:
            parameters = get_variant(member.type, parameters)

        self._server.emit_signal(
            self._message_bus.connection,
            self._object_path,
            interface_name,
            signal_name,
            parameters
        )

    def _method_callback(self, invocation, interface_name, method_name, parameters):
        """The callback for a DBus call.

        :param invocation: an invocation of the DBus call
        :param interface_name: a DBus interface name
        :param method_name: a DBus method name
        :param parameters: a variant of DBus arguments
        """
        try:
            # Handle the method call.
            member = self._find_member_spec(interface_name, method_name)
            result = self._handle_call(interface_name, method_name, *parameters.unpack())
        except Exception as error:  # pylint: disable=broad-except
            # Log the error.
            log.warning(
                "The call %s.%s has failed with an exception:",
                interface_name, method_name, exc_info=True
            )

            # Process the error.
            self._error_handler.handle_server_error(
                self._server,
                invocation,
                error
            )
        else:
            # Process the result.
            self._server.set_call_reply(
                invocation,
                member.out_type,
                result
            )

    def _find_default_handler(self, interface_name, member_name):
        """Find a default handler of a DBus call.

        :param interface_name: a name of the interface
        :param member_name: a name of the member
        :return: a handler or None
        """
        if interface_name == "org.freedesktop.DBus.Properties":
            if member_name == "Get":
                return self._get_property
            elif member_name == "Set":
                return self._set_property
            elif member_name == "GetAll":
                return self._get_all_properties
            elif member_name == "PropertiesChanged":
                return self._properties_changed

        return None

    def _get_property(self, interface_name, property_name):
        """The default handler of the Get method.

        :param interface_name: an interface name
        :param property_name: a property name
        :return: a property value
        """
        member = self._find_member_spec(interface_name, property_name)

        if not member.readable:
            raise AttributeError("The property {}.{} is not readable.".format(
                interface_name, property_name
            ))

        value = getattr(self._object, property_name)
        return get_variant(member.type, value)

    def _set_property(self, interface_name, property_name, property_value):
        """The default handler of the Set method.

        :param interface_name: an interface name
        :param property_name: a property name
        :param property_value: a property value
        :return:
        """
        member = self._find_member_spec(interface_name, property_name)

        if not member.writable:
            raise AttributeError("The property {}.{} is not writable.".format(
                interface_name, property_name
            ))

        setattr(self._object, property_name, property_value)

    def _find_all_properties(self, interface_name):
        """Find all properties of the given interface.

        :param interface_name: an interface name
        :return: a list of property names
        """
        return [
            member.name for member in self.specification.members
            if isinstance(member, DBusSpecification.Property)
            and member.interface_name == interface_name
            and member.readable
        ]

    def _get_all_properties(self, interface_name):
        """The default handler of the GetAll method.

        :param interface_name: an interface name
        :return: a dictionary of properties
        """
        return {
            property_name: self._get_property(interface_name, property_name)
            for property_name in self._find_all_properties(interface_name)
        }

    @property
    def _properties_changed(self):
        """The default handler of the PropertiesChanged method.

        :return: a signal
        """
        return self._signal_factory()

    def _emit_properties_changed(self, interface_name, changed_properties, invalid_properties):
        """Emit the PropertiesChanged signal.

        FIXME: This is a temporary workaround, because it should be handled by the signal.

        :param interface_name: an interface name
        :param changed_properties: a dictionary of changed properties
        :param invalid_properties: a list of invalid properties
        """
        self._emit_signal(
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            interface_name,
            {
                property_name: self._get_property(interface_name, property_name)
                for property_name in changed_properties
            },
            invalid_properties
        )
