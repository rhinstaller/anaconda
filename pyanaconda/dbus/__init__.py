#
# Representation of DBus connection.
#
# Copyright (C) 2017  Red Hat, Inc.  All rights reserved.
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

__all__ = ["DBus"]


class DBus(object):
    """Representation of DBus connection.

    Call DBus.get_connection to get a connection to the DBus. You can
    register a service with DBus.register_service, or publish an object
    with DBus.publish_object and get a proxy of a remote DBus object
    with DBus.get_proxy.
    """
    _connection = None
    _service_registrations = []
    _object_registrations = []

    @staticmethod
    def get_connection():
        """Returns a DBus connection."""
        if not DBus._connection:
            DBus._connection = DBus.get_new_connection()

        return DBus._connection

    @staticmethod
    def get_new_connection():
        """Get a DBus connection.

        You shouldn't create new connections unless there is a good
        reason for it. Use DBus.get_connection instead.

        Normally this method should return a connection to the system
        bus, but during testing/development a custom bus might be used.
        So just always connect to the bus specified by the environmental
        variable DBUS_STARTER_ADDRESS.
        """
        bus_address = os.environ.get("DBUS_STARTER_ADDRESS")

        if bus_address:
            log.info("Connecting to DBus at %s.", bus_address)
            return pydbus.connect(bus_address)

        log.info("Connecting to system DBus.")
        return pydbus.SystemBus()

    @staticmethod
    def register_service(service_name):
        """Register a service on DBus.

        A service can be registered by requesting its name on DBus.
        This method should be called only after all of the required
        objects of the service are published on DBus.

        :param service_name: a DBus name of a service
        """
        log.debug("Registering a service name %s.", service_name)
        obj = DBus.get_connection().request_name(service_name,
                                                 allow_replacement=True,
                                                 replace=False)
        DBus._service_registrations.append(obj)

    @staticmethod
    def unregister_all():
        """Unregister a registered service."""
        log.debug("Unregistering all service names.")
        while DBus._service_registrations:
            registration = DBus._service_registrations.pop(0)
            registration.unown()

    @staticmethod
    def publish_object(obj, object_path):
        """Publish an object on DBus.

        :param obj: an instance of @dbus_interface or @dbus_class
        :param object_path: a DBus path of an object
        """
        log.debug("Publishing an object at %s.", object_path)
        obj = DBus.get_connection().register_object(object_path, obj, None)
        DBus._object_registrations.append(obj)

    @staticmethod
    def unpublish_all():
        """Unpublish all published objects."""
        log.debug("Unpublishing all objects.")
        while DBus._object_registrations:
            registration = DBus._object_registrations.pop(0)
            registration.unregister()

    @staticmethod
    def get_dbus_proxy():
        """Returns a proxy of DBus.

        :return: a proxy object
        """
        return DBus.get_connection().dbus

    @staticmethod
    def get_proxy(service_name, object_path):
        """Returns a proxy of a remote DBus object.

        :param service_name: a DBus name of a service
        :param object_path: a DBus path an object
        :return: a proxy object
        """
        return DBus.get_connection().get(service_name, object_path)
