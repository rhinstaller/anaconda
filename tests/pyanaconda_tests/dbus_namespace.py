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
from pyanaconda.dbus.namespace import get_dbus_name, get_dbus_path, get_namespace_from_name


class DBusNamespaceTestCase(unittest.TestCase):

    def dbus_name_test(self):
        """Test DBus path."""
        self.assertEqual(get_dbus_name(), "")
        self.assertEqual(get_dbus_name("a"), "a")
        self.assertEqual(get_dbus_name("a", "b"), "a.b")
        self.assertEqual(get_dbus_name("a", "b", "c"), "a.b.c")
        self.assertEqual(get_dbus_name("org", "freedesktop", "DBus"), "org.freedesktop.DBus")

    def dbus_path_test(self):
        """Test DBus path."""
        self.assertEqual(get_dbus_path(), "/")
        self.assertEqual(get_dbus_path("a"), "/a")
        self.assertEqual(get_dbus_path("a", "b"), "/a/b")
        self.assertEqual(get_dbus_path("a", "b", "c"), "/a/b/c")
        self.assertEqual(get_dbus_path("org", "freedesktop", "DBus"), "/org/freedesktop/DBus")

    def namespace_test(self):
        """Test namespaces."""
        self.assertEqual(get_namespace_from_name("a"), ("a",))
        self.assertEqual(get_namespace_from_name("a.b"), ("a", "b"))
        self.assertEqual(get_namespace_from_name("a.b.c"), ("a", "b", "c"))
        self.assertEqual(get_namespace_from_name("org.freedesktop.DBus"), ("org", "freedesktop", "DBus"))
