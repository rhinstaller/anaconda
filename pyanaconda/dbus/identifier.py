#
# Identification of DBus objects, interfaces and services.
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
from pyanaconda.dbus import DBus
from pyanaconda.dbus.namespace import get_dbus_path, get_dbus_name

__all__ = ['DBusInterfaceIdentifier', 'DBusObjectIdentifier', 'DBusServiceIdentifier']


class DBusBaseIdentifier(object):
    """A base identifier."""

    def __init__(self, namespace, basename=None):
        """Create an identifier.

        :param namespace: a sequence of strings
        :param basename: a string with the base name or None
        """
        if basename:
            namespace = (*namespace, basename)

        self._namespace = namespace
        self._name = get_dbus_name(*namespace)
        self._path = get_dbus_path(*namespace)

    @property
    def namespace(self):
        """DBus namespace of this object."""
        return self._namespace

    def __str__(self):
        """Return the string representation."""
        return self._name


class DBusInterfaceIdentifier(DBusBaseIdentifier):
    """Identifier of a DBus interface."""

    def __init__(self, namespace, basename=None, interface_version=None):
        """Describe a DBus interface.

        :param namespace: a sequence of strings
        :param basename: a string with the base name or None
        :param interface_version: a version of the interface
        """
        super().__init__(namespace, basename=basename)
        self._interface_version = interface_version

    def _version_to_string(self, version):
        """Convert version to a string.

        :param version: a number or None
        :return: a string
        """
        if version is None:
            return ""

        return str(version)

    @property
    def interface_name(self):
        """Full name of the DBus interface."""
        return self._name + self._version_to_string(self._interface_version)

    def __str__(self):
        """Return the string representation."""
        return self.interface_name


class DBusObjectIdentifier(DBusInterfaceIdentifier):
    """Identifier of a DBus object."""

    def __init__(self, namespace, basename=None, interface_version=None, object_version=None):
        """Describe a DBus object.

        :param namespace: a sequence of strings
        :param basename: a string with the base name or None
        :param interface_version: a version of the DBus interface
        :param object_version: a version of the DBus object
        """
        super().__init__(namespace, basename=basename, interface_version=interface_version)
        self._object_version = object_version

    @property
    def object_path(self):
        """Full path of the DBus object."""
        return self._path + self._version_to_string(self._object_version)

    def __str__(self):
        """Return the string representation."""
        return self.object_path


class DBusServiceIdentifier(DBusObjectIdentifier):
    """Identifier of a DBus service."""

    def __init__(self, namespace, basename=None, interface_version=None, object_version=None,
                 service_version=None, message_bus=DBus):
        """Describe a DBus service.

        :param namespace: a sequence of strings
        :param basename: a string with the base name or None
        :param interface_version: a version of the DBus interface
        :param object_version: a version of the DBus object
        :param service_version: a version of the DBus service
        :param message_bus: a message bus
        """
        super().__init__(namespace, basename=basename,
                         interface_version=interface_version,
                         object_version=object_version)

        self._service_version = service_version
        self._message_bus = message_bus

    @property
    def service_name(self):
        """Full name of a DBus service."""
        return self._name + self._version_to_string(self._service_version)

    def __str__(self):
        """Return the string representation."""
        return self.service_name

    def _choose_object_path(self, object_path):
        """Choose an object path."""
        if object_path is None:
            return self.object_path

        if isinstance(object_path, DBusObjectIdentifier):
            return object_path.object_path

        return object_path

    def _choose_interface_names(self, object_path, interface_names):
        """Choose interface names."""
        if object_path is None and interface_names is None:
            return [self.interface_name]

        return interface_names

    def get_proxy(self, object_path=None):
        """Returns a proxy of the DBus object.

        :param object_path: a DBus path an object or None
        :return: a proxy object
        """
        object_path = self._choose_object_path(object_path)
        return self._message_bus.get_proxy(self.service_name, object_path)

    def get_observer(self, object_path=None):
        """Returns an observer of the DBus object.

        :param object_path: a DBus path of an object or None
        :return: an observer object
        """
        object_path = self._choose_object_path(object_path)
        return self._message_bus.get_observer(self.service_name, object_path)

    def get_cached_observer(self, object_path=None, interface_names=None):
        """Returns a cached observer of the DBus object.

        :param object_path: a DBus path of an object or None
        :param interface_names: a list of interface names or None
        :return: an observer object
        """
        interface_names = self._choose_interface_names(object_path, interface_names)
        object_path = self._choose_object_path(object_path)

        return self._message_bus.get_cached_observer(
            self.service_name, object_path, interface_names
        )
