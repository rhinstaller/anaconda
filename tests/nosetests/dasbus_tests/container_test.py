#
# Copyright (C) 2019  Red Hat, Inc.
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

from dasbus.server.container import DBusContainer, DBusContainerError
from dasbus.server.interface import dbus_interface
from dasbus.server.publishable import Publishable
from dasbus.server.template import BasicInterfaceTemplate
from dasbus.typing import Str, ObjPath


@dbus_interface("org.Project.Object")
class MyInterface(BasicInterfaceTemplate):

    def HelloWorld(self) -> Str:
        return self.implementation.hello_world()


class MyObject(Publishable):

    def for_publication(self):
        return MyInterface(self)

    def hello_world(self):
        return "Hello World!"


class MyUnpublishable(object):
    pass


class DBusContainerTestCase(unittest.TestCase):
    """Test DBus containers."""

    def setUp(self):
        self.message_bus = Mock()
        self.container = DBusContainer(
            namespace=("org", "Project"),
            basename="Object",
            message_bus=self.message_bus
        )

    def set_namespace_test(self):
        """Test set_namespace."""
        self.container.set_namespace(("org", "Another", "Project"))

        path = self.container.to_object_path(MyObject())
        self.assertEqual(path, "/org/Another/Project/Object/1")

        path = self.container.to_object_path(MyObject())
        self.assertEqual(path, "/org/Another/Project/Object/2")

    def to_object_path_failed_test(self):
        """Test failed to_object_path."""
        with self.assertRaises(TypeError):
            self.container.to_object_path(MyUnpublishable())

        with self.assertRaises(DBusContainerError):
            self.container._find_object_path(MyObject())

    def to_object_path_test(self):
        """Test to_object_path."""
        obj = MyObject()
        path = self.container.to_object_path(obj)

        self.message_bus.publish_object.assert_called_once()
        published_path, published_obj = self.message_bus.publish_object.call_args[0]

        self.assertEqual(path, "/org/Project/Object/1")
        self.assertEqual(path, published_path)
        self.assertIsInstance(published_obj, MyInterface)
        self.assertEqual(obj, published_obj.implementation)

        self.message_bus.reset_mock()

        self.assertEqual(self.container.to_object_path(obj), path)
        self.message_bus.publish_object.assert_not_called()

        self.assertEqual(self.container.to_object_path(obj), path)
        self.message_bus.publish_object.assert_not_called()

    def to_object_path_list_test(self):
        """Test to_object_path_list."""
        objects = [MyObject(), MyObject(), MyObject()]
        paths = self.container.to_object_path_list(objects)

        self.assertEqual(self.message_bus.publish_object.call_count, 3)

        self.assertEqual(paths, [
            "/org/Project/Object/1",
            "/org/Project/Object/2",
            "/org/Project/Object/3"
        ])

        self.message_bus.reset_mock()

        self.assertEqual(paths, self.container.to_object_path_list(objects))
        self.message_bus.publish_object.assert_not_called()

        self.assertEqual(paths, self.container.to_object_path_list(objects))
        self.message_bus.publish_object.assert_not_called()

    def from_object_path_failed_test(self):
        """Test failures."""
        with self.assertRaises(DBusContainerError):
            self.container.from_object_path(ObjPath("/org/Project/Object/1"))

    def from_object_path_test(self):
        """Test from_object_path."""
        obj = MyObject()
        path = self.container.to_object_path(obj)

        self.assertEqual(obj, self.container.from_object_path(path))
        self.assertEqual(path, self.container.to_object_path(obj))

        self.assertEqual(obj, self.container.from_object_path(path))
        self.assertEqual(path, self.container.to_object_path(obj))

    def from_object_path_list_test(self):
        """Test from_object_path_list."""
        objects = [MyObject(), MyObject(), MyObject()]
        paths = self.container.to_object_path_list(objects)

        self.assertEqual(objects, self.container.from_object_path_list(paths))
        self.assertEqual(paths, self.container.to_object_path_list(objects))

        self.assertEqual(objects, self.container.from_object_path_list(paths))
        self.assertEqual(paths, self.container.to_object_path_list(objects))

    def multiple_objects_test(self):
        """Test multiple objects."""
        obj = MyObject()
        path = self.container.to_object_path(obj)
        self.assertEqual(path, "/org/Project/Object/1")
        self.assertEqual(obj, self.container.from_object_path(path))
        self.message_bus.publish_object.assert_called_once()
        self.message_bus.reset_mock()

        obj = MyObject()
        path = self.container.to_object_path(obj)
        self.assertEqual(path, "/org/Project/Object/2")
        self.assertEqual(obj, self.container.from_object_path(path))
        self.message_bus.publish_object.assert_called_once()
        self.message_bus.reset_mock()

        obj = MyObject()
        path = self.container.to_object_path(obj)
        self.assertEqual(path, "/org/Project/Object/3")
        self.assertEqual(obj, self.container.from_object_path(path))
        self.message_bus.publish_object.assert_called_once()
        self.message_bus.reset_mock()
