#
# Copyright (C) 2018  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
from mock import Mock

from pyanaconda.dbus.identifier import DBusInterfaceIdentifier, DBusObjectIdentifier, \
    DBusServiceIdentifier, DBusBaseIdentifier


class DBusIdentifierTestCase(unittest.TestCase):
    """Test DBus identifiers."""

    def assert_namespace(self, obj, namespace):
        """Check the DBus namespace object."""
        self.assertEqual(obj.namespace, namespace)

    def assert_interface(self, obj, interface_name):
        """Check the DBus interface object."""
        self.assertEqual(obj.interface_name, interface_name)

    def identifier_test(self):
        """Test the DBus identifier object."""
        identifier = DBusBaseIdentifier(
            namespace=("a", "b", "c")
        )
        self.assert_namespace(identifier, ("a", "b", "c"))

        identifier = DBusBaseIdentifier(
            basename="d",
            namespace=("a", "b", "c")
        )
        self.assert_namespace(identifier, ("a", "b", "c", "d"))

    def interface_test(self):
        """Test the DBus interface object."""
        interface = DBusInterfaceIdentifier(
            namespace=("a", "b", "c")
        )
        self.assert_namespace(interface, ("a", "b", "c"))
        self.assert_interface(interface, "a.b.c")

        interface = DBusInterfaceIdentifier(
            namespace=("a", "b", "c"),
            interface_version=1
        )
        self.assert_namespace(interface, ("a", "b", "c"))
        self.assert_interface(interface, "a.b.c1")

        interface = DBusInterfaceIdentifier(
            basename="d",
            namespace=("a", "b", "c"),
            interface_version=1
        )
        self.assert_namespace(interface, ("a", "b", "c", "d"))
        self.assert_interface(interface, "a.b.c.d1")

    def assert_object(self, obj, object_path):
        """Check the DBus object."""
        self.assertEqual(obj.object_path, object_path)

    def object_test(self):
        """Test the DBus object."""
        obj = DBusObjectIdentifier(
            namespace=("a", "b", "c")
        )
        self.assert_namespace(obj, ("a", "b", "c"))
        self.assert_interface(obj, "a.b.c")
        self.assert_object(obj, "/a/b/c")

        obj = DBusObjectIdentifier(
            namespace=("a", "b", "c"),
            object_version=2,
            interface_version=4
        )
        self.assert_namespace(obj, ("a", "b", "c"))
        self.assert_interface(obj, "a.b.c4")
        self.assert_object(obj, "/a/b/c2")

        obj = DBusObjectIdentifier(
            basename="d",
            namespace=("a", "b", "c"),
            object_version=2,
            interface_version=4
        )
        self.assert_namespace(obj, ("a", "b", "c", "d"))
        self.assert_interface(obj, "a.b.c.d4")
        self.assert_object(obj, "/a/b/c/d2")

    def assert_service(self, obj, service_name):
        """Check the DBus service object."""
        self.assertEqual(obj.service_name, service_name)

    def service_test(self):
        """Test the DBus service object."""
        service = DBusServiceIdentifier(
            namespace=("a", "b", "c")
        )
        self.assert_namespace(service, ("a", "b", "c"))
        self.assert_interface(service, "a.b.c")
        self.assert_object(service, "/a/b/c")
        self.assert_service(service, "a.b.c")

        service = DBusServiceIdentifier(
            namespace=("a", "b", "c"),
            service_version=3,
            interface_version=5,
            object_version=7
        )
        self.assert_namespace(service, ("a", "b", "c"))
        self.assert_interface(service, "a.b.c5")
        self.assert_object(service, "/a/b/c7")
        self.assert_service(service, "a.b.c3")

        service = DBusServiceIdentifier(
            basename="d",
            namespace=("a", "b", "c"),
            service_version=3,
            interface_version=5,
            object_version=7
        )
        self.assert_namespace(service, ("a", "b", "c", "d"))
        self.assert_interface(service, "a.b.c.d5")
        self.assert_object(service, "/a/b/c/d7")
        self.assert_service(service, "a.b.c.d3")


class DBusServiceIdentifierTestCase(unittest.TestCase):
    """Test DBus service identifiers."""

    def get_proxy_test(self):
        """Test getting a proxy."""
        bus = Mock()
        namespace = ("a", "b", "c")

        service = DBusServiceIdentifier(
            namespace=namespace,
            message_bus=bus
        )

        obj = DBusObjectIdentifier(
            basename="object",
            namespace=namespace
        )

        service.get_proxy()
        bus.get_proxy.assert_called_with("a.b.c", "/a/b/c")
        bus.reset_mock()

        service.get_proxy(obj.object_path)
        bus.get_proxy.assert_called_with("a.b.c", "/a/b/c/object")
        bus.reset_mock()

    def get_observer_test(self):
        """Test getting an observer."""
        bus = Mock()
        namespace = ("a", "b", "c")

        service = DBusServiceIdentifier(
            namespace=namespace,
            message_bus=bus
        )

        obj = DBusObjectIdentifier(
            basename="d",
            namespace=namespace
        )

        service.get_observer()
        bus.get_observer.assert_called_with("a.b.c", "/a/b/c")
        bus.reset_mock()

        service.get_observer(obj.object_path)
        bus.get_observer.assert_called_with("a.b.c", "/a/b/c/d")
        bus.reset_mock()

    def get_cached_observer_test(self):
        """Test getting a cached observer."""
        bus = Mock()
        namespace = ("a", "b", "c")

        service = DBusServiceIdentifier(
            namespace=namespace,
            message_bus=bus
        )

        obj = DBusObjectIdentifier(
            basename="object",
            namespace=namespace
        )

        interface = DBusInterfaceIdentifier(
            basename="interface",
            namespace=namespace
        )

        service.get_cached_observer()
        bus.get_cached_observer.assert_called_with("a.b.c", "/a/b/c", ["a.b.c"])
        bus.reset_mock()

        service.get_cached_observer(obj.object_path)
        bus.get_cached_observer.assert_called_with("a.b.c", "/a/b/c/object", None)
        bus.reset_mock()

        service.get_cached_observer(interface_names=[interface.interface_name])
        bus.get_cached_observer.assert_called_with("a.b.c", "/a/b/c", ["a.b.c.interface"])
        bus.reset_mock()

        service.get_cached_observer(obj.object_path, interface_names=[interface.interface_name])
        bus.get_cached_observer.assert_called_with("a.b.c", "/a/b/c/object", ["a.b.c.interface"])
        bus.reset_mock()
