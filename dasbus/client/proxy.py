#
# Client support for DBus proxies
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
from abc import ABC, abstractmethod
from threading import Lock

from dasbus.client.handler import ClientObjectHandler
from dasbus.client.property import PropertyProxy
from dasbus.specification import DBusSpecificationError

__all__ = ["AbstractObjectProxy", "ObjectProxy", "InterfaceProxy", "get_object_path",
           "disconnect_proxy"]


def get_object_handler(proxy):
    """Get an object handler of the DBus proxy.

    :param proxy: a DBus proxy
    :return: a DBus proxy handler
    """
    if not isinstance(proxy, AbstractObjectProxy):
        raise TypeError("Invalid type of proxy: {}".format(str(type(proxy))))

    return getattr(proxy, "_handler")


def get_object_path(proxy):
    """Get an object path of the remote DBus object.

    :param proxy: a DBus proxy
    :return: a DBus path
    """
    handler = get_object_handler(proxy)
    return handler.object_path


def disconnect_proxy(proxy):
    """Disconnect the DBus proxy from the remote object.

    :param proxy: a DBus proxy
    """
    handler = get_object_handler(proxy)
    handler.disconnect_members()


class AbstractObjectProxy(ABC):
    """Abstract proxy of a remote DBus object."""

    __slots__ = ["_handler", "_members", "_lock", "__weakref__"]

    # Set of local instance attributes.
    _locals = {*__slots__}

    def __init__(self, message_bus, service_name, object_path,
                 handler_factory=ClientObjectHandler):
        """Create a new proxy.

        :param message_bus: a message bus
        :param service_name: a DBus name of the service
        :param object_path: a DBus path the object
        :param handler_factory: a factory of a DBus client object handler
        """
        self._handler = handler_factory(message_bus, service_name, object_path)
        self._members = dict()
        self._lock = Lock()

    @abstractmethod
    def _get_interface(self, member_name):
        """Get the DBus interface of the member.

        :param member_name: a member name
        :return: an interface name
        """
        pass

    def _get_member(self, *key):
        """Find a member of the DBus object.

        If the the member doesn't exist, we will acquire
        a lock and ask a handler to create it.

        This method is thread-safe.

        :param key: a member key
        :return: a member
        :raise: AttributeError if invalid
        """
        try:
            return self._members[key]
        except KeyError:
            pass

        return self._create_member(*key)

    def _create_member(self, *key):
        """Create a member of the DBus object.

        If the member doesn't exist, ask a handler
        to create it.

        This method is thread-safe.

        :param key: a member key
        :return: a member
        :raise: DBusSpecificationError if invalid
        """
        with self._lock:
            try:
                return self._members[key]
            except KeyError:
                pass

            try:
                member = self._handler.create_member(*key)
            except DBusSpecificationError as e:
                raise AttributeError(str(e)) from None

            self._members[key] = member
            return member

    def __getattr__(self, name):
        """Get the attribute.

        Called when an attribute lookup has not found
        the attribute in the usual places. Always call
        the DBus handler in this case.
        """
        member = self._get_member(self._get_interface(name), name)

        if isinstance(member, PropertyProxy):
            return member.get()

        return member

    def __setattr__(self, name, value):
        """Set the attribute.

        Called when an attribute assignment is attempted.
        Call the DBus handler if the the name is not a
        name of an instance attribute defined in _locals.
        """
        if name in self._locals:
            return super().__setattr__(name, value)

        member = self._get_member(self._get_interface(name), name)

        if isinstance(member, PropertyProxy):
            return member.set(value)

        raise AttributeError(
            "Can't set {}.{}.".format(member.interface_name, member.name)
        )


class ObjectProxy(AbstractObjectProxy):
    """Proxy of a remote DBus object."""

    __slots__ = ["_interface_names"]

    # Set of instance attributes.
    _locals = {*AbstractObjectProxy._locals, *__slots__}

    def __init__(self, *args, **kwargs):
        """Create a new proxy.

        :param handler: a DBus client object handler
        """
        super().__init__(*args, **kwargs)
        self._interface_names = None

    def _get_interface(self, member_name):
        """Get the DBus interface of the member.

        The members of standard interfaces have a priority.
        """
        if self._interface_names is None:
            members = reversed(
                self._handler.specification.members
            )
            self._interface_names = {
                m.name: m.interface_name
                for m in members
            }

        try:
            return self._interface_names[member_name]
        except KeyError:
            pass

        raise AttributeError(
            "Unknown interface of {}.".format(member_name)
        )


class InterfaceProxy(AbstractObjectProxy):
    """Proxy of a remote DBus interface."""

    __slots__ = ["_interface_name"]

    # Set of instance attributes.
    _locals = {*AbstractObjectProxy._locals, *__slots__}

    def __init__(self, message_bus, service_name, object_path, interface_name, *args, **kwargs):
        """Create a new proxy.

        :param message_bus: a message bus
        :param service_name: a DBus name of the service
        :param object_path: a DBus path the object
        :param handler: a DBus client object handler
        """
        super().__init__(message_bus, service_name, object_path, *args, **kwargs)
        self._interface_name = interface_name

    def _get_interface(self, member_name):
        """Get the DBus interface of the member."""
        return self._interface_name
