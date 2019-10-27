#
# Representation of DBus connection.
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
import logging
import threading
from abc import ABC, abstractmethod

from dasbus.client import ObjectProxy
from dasbus.constants import DBUS_NAME_FLAG_ALLOW_REPLACEMENT, DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER
from dasbus.server import ServerObjectHandler

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio

log = logging.getLogger(__name__)

__all__ = ["GLibConnection", "MessageBus", "SystemMessageBus", "SessionMessageBus",
           "AddressedMessageBus"]


class GLibConnection(object):
    """The low-level DBus connection library based on GLib."""

    DEFAULT_FLAGS = (
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
        Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
    )

    @staticmethod
    def get_system_bus_connection(cancellable=None):
        """Get a system bus connection."""
        log.info("Connecting to the system bus.")
        return Gio.bus_get_sync(
            Gio.BusType.SYSTEM,
            cancellable
        )

    @staticmethod
    def get_session_bus_connection(cancellable=None):
        """Get a session bus connection."""
        log.info("Connecting to the session bus.")
        return Gio.bus_get_sync(
            Gio.BusType.SESSION,
            cancellable
        )

    @staticmethod
    def get_addressed_bus_connection(bus_address, flags=DEFAULT_FLAGS, observer=None,
                                     cancellable=None):
        """Get a connection to a bus at the specified address."""
        return Gio.DBusConnection.new_for_address_sync(
            bus_address,
            flags,
            observer,
            cancellable
        )


class AbstractMessageBus(ABC):
    """Abstract representation of a message bus.

    The property connection represents a connection to the bus. You can
    register a service name with register_service, or publish an object
    with publish_object and get a proxy of a remote object with get_proxy.
    """

    @property
    @abstractmethod
    def connection(self):
        """The DBus connection."""
        return None

    def check_connection(self):
        """Check if the connection is set up.

        :return: True if the connection is set up otherwise False
        """
        try:
            return self.connection is not None
        except Exception as e:  # pylint: disable=broad-except
            log.warning("Connection can't be created:\n%s", e)
            return False

    @abstractmethod
    def get_proxy(self, service_name, object_path, **kwargs):
        """Returns a proxy of a remote DBus object.

        :param service_name: a DBus name of a service
        :param object_path: a DBus path an object
        :return: a proxy object
        """
        pass

    @abstractmethod
    def register_service(self, service_name, **kwargs):
        """Register a service on DBus.

        A service can be registered by requesting its name on DBus.
        This method should be called only after all of the required
        objects of the service are published on DBus.

        :param service_name: a DBus name of a service
        """
        pass

    @abstractmethod
    def publish_object(self, object_path, obj, **kwargs):
        """Publish an object on DBus.

        :param object_path: a DBus path of an object
        :param obj: an instance of @dbus_interface or @dbus_class
        """
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from DBus."""
        pass


class MessageBus(AbstractMessageBus):
    """Representation of a message bus based on D-Bus."""

    def __init__(self, provider=GLibConnection):
        """Create a new message bus.

        :param provider: a provider of DBus connections
        """
        super().__init__()
        self._provider = provider
        self._connection = None
        self._proxy = None
        self._registrations = []
        self._requested_names = set()

    @property
    def connection(self):
        """The DBus connection."""
        if not self._connection:
            self._connection = self._get_connection()

        return self._connection

    @abstractmethod
    def _get_connection(self):
        """Return a DBus connection."""
        pass

    @property
    def proxy(self):
        """The proxy of DBus."""
        if not self._proxy:
            self._proxy = self.get_proxy(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus"
            )

        return self._proxy

    # pylint: disable=arguments-differ
    def get_proxy(self, service_name, object_path, proxy_factory=ObjectProxy, **proxy_arguments):
        """Returns a proxy of a remote DBus object.

        :param service_name: a DBus name of a service
        :param object_path: a DBus path an object
        :param proxy_factory: a factory of a DBus object proxy
        :param proxy_arguments: additional arguments for the proxy factory
        :return: a proxy object
        """
        self._check_service_access(service_name)
        return proxy_factory(self, service_name, object_path, **proxy_arguments)

    def _check_service_access(self, service_name):
        """Check if we can access a DBus service.

        FIXME: This is a temporary check that should be later removed.

        This is useful during the transition of the Anaconda code from
        UI to DBus modules. This check prevents a deadlock in case that
        a DBus module tries to access a service, that it provides, from
        the main thread.

        :param service_name: a DBus name of a service
        :raises: RuntimeError if the service cannot be accessed
        """
        if service_name not in self._requested_names:
            # We don't provide this service.
            return

        if threading.current_thread() is not threading.main_thread():
            # We don't try to access this service from the main thread.
            return

        raise RuntimeError("Cannot access {} from the main thread.".format(service_name))

    # pylint: disable=arguments-differ
    def register_service(self, service_name, flags=DBUS_NAME_FLAG_ALLOW_REPLACEMENT):
        """Register a service on DBus.

        :param service_name: a DBus name of a service
        :param flags: the flags argument of the RequestName DBus method
        """
        log.debug("Registering a service name %s.", service_name)
        result = self.proxy.RequestName(service_name, flags)

        if result != DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER:
            raise ConnectionError("Name request has failed: {}".format(result))

        self._requested_names.add(service_name)
        self._registrations.append(lambda: self.proxy.ReleaseName(service_name))

    # pylint: disable=arguments-differ
    def publish_object(self, object_path, obj, server_factory=ServerObjectHandler):
        """Publish an object on DBus.

        :param object_path: a DBus path of an object
        :param obj: an instance of @dbus_interface or @dbus_class
        :param server_factory: a factory of a DBus server object handler
        """
        log.debug("Publishing an object at %s.", object_path)
        object_handler = server_factory(self, object_path, obj)
        object_handler.connect_object()

        self._registrations.append(object_handler.disconnect_object)

    def disconnect(self):
        """Disconnect from DBus."""
        log.debug("Disconnecting from the bus.")

        while self._registrations:
            callback = self._registrations.pop()
            callback()

        self._connection = None
        self._requested_names = set()


class SystemMessageBus(MessageBus):
    """Representation of a system bus connection."""

    def _get_connection(self):
        """Get a system DBus connection."""
        log.info("Connecting to the system bus.")
        return self._provider.get_system_bus_connection()


class SessionMessageBus(MessageBus):
    """Representation of a session bus connection."""

    def _get_connection(self):
        """Get a session DBus connection."""
        log.info("Connecting to the session bus.")
        return self._provider.get_session_bus_connection()


class AddressedMessageBus(MessageBus):
    """Representation of a connection for the specified address."""

    def __init__(self, address):
        """Create a new representation of a connection.

        :param address: a bus address
        """
        super().__init__()
        self._address = address

    @property
    def address(self):
        """The bus address."""
        return self._address

    def _get_connection(self):
        """Get a connection to a bus at the specified address."""
        log.info("Connecting to a bus at %s.", self._address)
        return self._provider.get_addressed_bus_connection(self._address)
