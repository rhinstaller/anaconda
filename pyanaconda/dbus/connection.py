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
import os
import pydbus

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["DBusConnection", "DBusSystemConnection", "DBusSessionConnection"]


class DBusConnection(object):
    """Representation of a default DBus connection.

    It will connect to the bus specified by the environmental variable
    DBUS_STARTER_ADDRESS.

    Call DBus.get_connection to get a connection to the DBus. You can
    register a service with DBus.register_service, or publish an object
    with DBus.publish_object and get a proxy of a remote DBus object
    with DBus.get_proxy.
    """

    def __init__(self):
        self._connection = None
        self._service_registrations = []
        self._object_registrations = []

    @property
    def connection(self):
        """Returns a DBus connection."""
        if not self._connection:
            self._connection = self.get_new_connection()

        return self._connection

    def get_new_connection(self):
        """Get a DBus connection.

        You shouldn't create new connections unless there is a good
        reason for it. Use DBus.get_connection instead.

        Connect to the bus specified by the environmental variable
        DBUS_STARTER_ADDRESS. If it is not specified, connect to
        the system bus.
        """
        bus_address = os.environ.get("DBUS_STARTER_ADDRESS")

        if bus_address:
            log.info("Connecting to DBus at %s.", bus_address)
            return pydbus.connect(bus_address)

        # FIXME: We should raise an exception instead.
        log.info("DBUS_STARTER_ADDRESS is not specified, "
                 "connecting to the system DBus.")
        return pydbus.SystemBus()

    def register_service(self, service_name):
        """Register a service on DBus.

        A service can be registered by requesting its name on DBus.
        This method should be called only after all of the required
        objects of the service are published on DBus.

        :param service_name: a DBus name of a service
        """
        log.debug("Registering a service name %s.", service_name)
        reg = self.connection.request_name(service_name,
                                           allow_replacement=True,
                                           replace=False)
        self._service_registrations.append(reg)

    def publish_object(self, obj, object_path):
        """Publish an object on DBus.

        :param obj: an instance of @dbus_interface or @dbus_class
        :param object_path: a DBus path of an object
        """
        log.debug("Publishing an object at %s.", object_path)
        reg = self.connection.register_object(object_path, obj, None)
        self._object_registrations.append(reg)

    def get_dbus_proxy(self):
        """Returns a proxy of DBus.

        :return: a proxy object
        """
        return self.connection.dbus

    def get_proxy(self, service_name, object_path):
        """Returns a proxy of a remote DBus object.

        :param service_name: a DBus name of a service
        :param object_path: a DBus path an object
        :return: a proxy object
        """
        return self.connection.get(service_name, object_path)

    def get_observer(self, service_name, object_path):
        """Returns an observer of a remote DBus object.

        :param service_name: a DBus name of a service
        :param object_path: a DBus path an object
        :return: an instance of DBusObjectObserver
        """
        from pyanaconda.dbus.observer import DBusObjectObserver
        return DBusObjectObserver(service_name, object_path, message_bus=self)

    def get_cached_observer(self, service_name, object_path, interface_names):
        """Returns a cached observer of a remote DBus object.

        :param service_name: a DBus name of a service
        :param object_path: a DBus path an object
        :param interface_names: a list of interface names
        :return: an instance of DBusCachedObserver
        """
        from pyanaconda.dbus.observer import DBusCachedObserver
        return DBusCachedObserver(service_name, object_path, interface_names, message_bus=self)

    def disconnect(self):
        """Disconnect from DBus."""
        log.debug("Disconnecting from DBus.")

        while self._object_registrations:
            registration = self._object_registrations.pop()
            registration.unregister()

        while self._service_registrations:
            registration = self._service_registrations.pop()
            registration.unown()

        self._connection = None


class DBusSystemConnection(DBusConnection):
    """Representation of a system bus connection."""

    def get_new_connection(self):
        """Get a system DBus connection."""
        log.info("Connecting to the system DBus.")
        return pydbus.SystemBus()


class DBusSessionConnection(DBusConnection):
    """Representation of a session bus connection."""

    def get_new_connection(self):
        """Get a session DBus connection."""
        log.info("Connecting to the session DBus.")
        return pydbus.SessionBus()
