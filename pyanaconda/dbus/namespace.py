#
# Identification of DBus objects and services.
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
from pydbus.auto_names import auto_object_path

from pyanaconda.dbus import DBus


def get_object_path(service_name):
    """Return an object path of the service."""
    return auto_object_path(service_name)


class DBusNamespace(object):
    """Namespace for DBus objects and services."""

    def __init__(self, *name, namespace=None):
        """Create a new namespace.

        :param name: a namespace sequence
        :type name: a sequence of strings
        :param namespace: a namespace prefix
        :type namespace: an instance of DBusNamespace
        """
        self._sequence = namespace.get_sequence() + name if namespace else name

    def get_sequence(self):
        """Returns the namespace sequence."""
        return self._sequence

    @property
    def namespace(self):
        """DBus name specified by the namespace."""
        return ".".join(self._sequence)

    @property
    def pathspace(self):
        """DBus path specified by the namespace."""
        return "/" + "/".join(self._sequence)

    def __str__(self):
        """Return the string representation."""
        return self.namespace


class DBusInterfaceIdentifier(DBusNamespace):
    """Identifier of a DBus interface."""

    def __init__(self, *name, namespace=None, interface_version=None):
        """Describe a DBus interface.

        :param name: a namespace sequence
        :param namespace: a namespace prefix
        :param interface_version: a version of the DBus interface
        """
        super().__init__(*name, namespace=namespace)
        self._interface_version = interface_version

    @staticmethod
    def version_to_string(version):
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
        return self.namespace + self.version_to_string(self._interface_version)


class DBusObjectIdentifier(DBusInterfaceIdentifier):
    """Identifier of a DBus object."""

    def __init__(self, *name, namespace=None, interface_version=None, object_version=None):
        """Describe a DBus object.

        :param name: a namespace sequence
        :param namespace: a namespace prefix
        :param interface_version: a version of the DBus interface
        :param object_version: a version of the DBus object
        """
        super().__init__(*name, namespace=namespace, interface_version=interface_version)
        self._object_version = object_version

    @property
    def object_path(self):
        """Full path of the DBus object."""
        return self.pathspace + self.version_to_string(self._object_version)


class DBusServiceIdentifier(DBusObjectIdentifier):
    """Identifier of a DBus service."""

    def __init__(self, *name, namespace=None, interface_version=None, object_version=None,
                 service_version=None, message_bus=DBus):
        """Describe a DBus service.

        :param name: a namespace sequence
        :param namespace: a namespace prefix
        :param interface_version: a version of the DBus interface
        :param object_version: a version of the DBus object
        :param service_version: a version of the DBus service
        :param message_bus: a message bus
        """
        super().__init__(*name,
                         namespace=namespace,
                         interface_version=interface_version,
                         object_version=object_version)

        self._service_version = service_version
        self._message_bus = message_bus

    @property
    def service_name(self):
        """Full name of a DBus service."""
        return self.namespace + self.version_to_string(self._service_version)

    def get_proxy(self, object_path=None):
        """Returns a proxy of the DBus object.

        :param object_path: a DBus path an object
        :return: a proxy object
        """
        if object_path is None:
            object_path = self.object_path

        return self._message_bus.get_proxy(self.service_name, object_path)

    def get_observer(self, object_path=None):
        """Returns an observer of the DBus object.

        :param object_path: a DBus path of an object
        :return: an observer object
        """
        if object_path is None:
            object_path = self.object_path

        return self._message_bus.get_observer(self.service_name, object_path)

    def get_cached_observer(self, object_path=None, interface_names=None):
        """Returns a cached observer of the DBus object.

        :param object_path: a DBus path of an object
        :param interface_names: a list of interface names
        :return: an observer object
        """
        if object_path is None:
            object_path = self.object_path

            if interface_names is None:
                interface_names = [self.interface_name]

        return self._message_bus.get_cached_observer(
            self.service_name, object_path, interface_names
        )
