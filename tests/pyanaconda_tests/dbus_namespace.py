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

from pyanaconda.dbus.namespace import DBusNamespace, DBusInterfaceIdentifier, \
    DBusObjectIdentifier, DBusServiceIdentifier


class DBusNamespaceTestCase(unittest.TestCase):
    """Test DBus namespaces."""

    def assert_namespace(self, obj, namespace, pathspace):
        """Check the DBus namespace object."""
        self.assertEqual(str(obj), namespace)
        self.assertEqual(obj.namespace, namespace)
        self.assertEqual(obj.pathspace, pathspace)

    def namespace_test(self):
        """Test the DBus namespace object."""
        namespace = DBusNamespace("a")
        self.assert_namespace(namespace, "a", "/a")

        namespace = DBusNamespace("a", "b", "c")
        self.assert_namespace(namespace, "a.b.c", "/a/b/c")

        namespace = DBusNamespace("aa", "bb", "cc")
        self.assert_namespace(namespace, "aa.bb.cc", "/aa/bb/cc")

        namespace_ab = DBusNamespace("a", "b")
        self.assert_namespace(namespace_ab, "a.b", "/a/b")

        namespace_cd = DBusNamespace("c", "d", namespace=namespace_ab)
        self.assert_namespace(namespace_cd, "a.b.c.d", "/a/b/c/d")

        namespace_1 = DBusNamespace("1")
        self.assert_namespace(namespace_1, "1", "/1")

        namespace_2 = DBusNamespace("2", namespace=namespace_1)
        self.assert_namespace(namespace_2, "1.2", "/1/2")

        namespace_3 = DBusNamespace("3", namespace=namespace_2)
        self.assert_namespace(namespace_3, "1.2.3", "/1/2/3")

    def assert_interface(self, obj, interface_name):
        """Check the DBus interface object."""
        self.assertEqual(obj.interface_name, interface_name)

    def interface_test(self):
        """Test the DBus interface object."""
        interface = DBusInterfaceIdentifier("interface")
        self.assert_namespace(interface, "interface", "/interface")
        self.assert_interface(interface, "interface")

        interface = DBusInterfaceIdentifier("interface", interface_version=1)
        self.assert_namespace(interface, "interface", "/interface")
        self.assert_interface(interface, "interface1")

        namespace = DBusNamespace("a", "b", "c")
        interface = DBusInterfaceIdentifier("interface", interface_version=1, namespace=namespace)
        self.assert_namespace(interface, "a.b.c.interface", "/a/b/c/interface")
        self.assert_interface(interface, "a.b.c.interface1")

    def assert_object(self, obj, object_path):
        """Check the DBus object."""
        self.assertEqual(obj.object_path, object_path)

    def object_test(self):
        """Test the DBus object."""
        obj = DBusObjectIdentifier("object")
        self.assert_namespace(obj, "object", "/object")
        self.assert_interface(obj, "object")
        self.assert_object(obj, "/object")

        obj = DBusObjectIdentifier("object", object_version=2)
        self.assert_namespace(obj, "object", "/object")
        self.assert_interface(obj, "object")
        self.assert_object(obj, "/object2")

        obj = DBusObjectIdentifier("object", object_version=2, interface_version=4)
        self.assert_namespace(obj, "object", "/object")
        self.assert_interface(obj, "object4")
        self.assert_object(obj, "/object2")

        namespace = DBusNamespace("a", "b", "c")
        obj = DBusObjectIdentifier("object", object_version=2, interface_version=4, namespace=namespace)
        self.assert_namespace(obj, "a.b.c.object", "/a/b/c/object")
        self.assert_interface(obj, "a.b.c.object4")
        self.assert_object(obj, "/a/b/c/object2")

    def assert_service(self, obj, service_name):
        """Check the DBus service object."""
        self.assertEqual(obj.service_name, service_name)

    def service_test(self):
        """Test the DBus service object."""
        service = DBusServiceIdentifier("service")
        self.assert_namespace(service, "service", "/service")
        self.assert_interface(service, "service")
        self.assert_object(service, "/service")
        self.assert_service(service, "service")

        service = DBusServiceIdentifier("service",
                                        service_version=3)

        self.assert_namespace(service, "service", "/service")
        self.assert_interface(service, "service")
        self.assert_object(service, "/service")
        self.assert_service(service, "service3")

        service = DBusServiceIdentifier("service",
                                        service_version=3,
                                        interface_version=5,
                                        object_version=7)

        self.assert_namespace(service, "service", "/service")
        self.assert_interface(service, "service5")
        self.assert_object(service, "/service7")
        self.assert_service(service, "service3")

        namespace = DBusNamespace("a", "b", "c")
        service = DBusServiceIdentifier("service",
                                        service_version=3,
                                        interface_version=5,
                                        object_version=7,
                                        namespace=namespace)

        self.assert_namespace(service, "a.b.c.service", "/a/b/c/service")
        self.assert_interface(service, "a.b.c.service5")
        self.assert_object(service, "/a/b/c/service7")
        self.assert_service(service, "a.b.c.service3")


class DBusServiceTestCase(unittest.TestCase):
    """Test DBus services."""

    def get_proxy_test(self):
        """Test getting a proxy."""
        bus = Mock()
        service = DBusServiceIdentifier("x", message_bus=bus)
        obj = DBusObjectIdentifier("y", namespace=service)

        service.get_proxy()
        bus.get_proxy.assert_called_with("x", "/x")
        bus.reset_mock()

        service.get_proxy(obj.object_path)
        bus.get_proxy.assert_called_with("x", "/x/y")
        bus.reset_mock()

    def get_observer_test(self):
        """Test getting an observer."""
        bus = Mock()
        service = DBusServiceIdentifier("x", message_bus=bus)
        obj = DBusObjectIdentifier("y", namespace=service)

        service.get_observer()
        bus.get_observer.assert_called_with("x", "/x")
        bus.reset_mock()

        service.get_observer(obj.object_path)
        bus.get_observer.assert_called_with("x", "/x/y")
        bus.reset_mock()

    def get_cached_observer_test(self):
        """Test getting a cached observer."""
        bus = Mock()
        service = DBusServiceIdentifier("x", message_bus=bus)
        obj = DBusObjectIdentifier("y", namespace=service)
        interface = DBusInterfaceIdentifier("z", namespace=service)

        service.get_cached_observer()
        bus.get_cached_observer.assert_called_with("x", "/x", ["x"])
        bus.reset_mock()

        service.get_cached_observer(obj.object_path)
        bus.get_cached_observer.assert_called_with("x", "/x/y", None)
        bus.reset_mock()

        service.get_cached_observer(interface_names=[interface.interface_name])
        bus.get_cached_observer.assert_called_with("x", "/x", ["x.z"])
        bus.reset_mock()

        service.get_cached_observer(obj.object_path, interface_names=[interface.interface_name])
        bus.get_cached_observer.assert_called_with("x", "/x/y", ["x.z"])
        bus.reset_mock()
