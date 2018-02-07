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

from pyanaconda.dbus.observer import DBusCachedObserver, PropertiesCache, DBusObjectObserver, \
    DBusObserverError, DBusObserver


class DBusObserverTestCase(unittest.TestCase):
    """Test DBus observers."""

    def _setup_observer(self, observer):
        """Set up the observer."""
        observer._service_available = Mock()
        observer._service_unavailable = Mock()
        self.assertFalse(observer.is_service_available)

    def _make_service_available(self, observer):
        """Make the service available."""
        observer._service_name_appeared_callback()
        self._test_if_service_available(observer)

    def _test_if_service_available(self, observer):
        """Test if service is available."""
        self.assertTrue(observer.is_service_available)

        observer._service_available.emit.assert_called_once_with(observer)
        observer._service_available.reset_mock()

        observer._service_unavailable.emit.assert_not_called()
        observer._service_unavailable.reset_mock()

    def _make_service_unavailable(self, observer):
        """Make the service unavailable."""
        observer._service_name_vanished_callback()
        self._test_if_service_unavailable(observer)

    def _test_if_service_unavailable(self, observer):
        """Test if service is unavailable."""
        self.assertFalse(observer.is_service_available)

        observer._service_unavailable.emit.assert_called_once_with(observer)
        observer._service_unavailable.reset_mock()

        observer._service_available.emit.assert_not_called()
        observer._service_available.reset_mock()

    def observer_test(self):
        """Test the observer."""
        observer = DBusObserver(Mock(), "SERVICE")
        self._setup_observer(observer)
        self._make_service_available(observer)
        self._make_service_unavailable(observer)

    def object_observer_test(self):
        """Test the object observer."""
        dbus = Mock()
        observer = DBusObjectObserver(dbus, "SERVICE", "OBJECT")

        # Setup the observer.
        self._setup_observer(observer)
        self.assertIsNone(observer._proxy)

        with self.assertRaises(DBusObserverError):
            observer.proxy.DoSomething()

        # Service available.
        self._make_service_available(observer)
        self.assertIsNone(observer._proxy)

        # Access the proxy.
        observer.proxy.DoSomething()
        dbus.get_proxy.assert_called_once_with("SERVICE", "OBJECT")
        self.assertIsNotNone(observer._proxy)

        # Service unavailable.
        self._make_service_unavailable(observer)
        self.assertIsNone(observer._proxy)

        with self.assertRaises(DBusObserverError):
            observer.proxy.DoSomething()

    def cache_test(self):
        """Test the properties cache."""

        cache = PropertiesCache()
        self.assertEqual(cache.properties, {})

        with self.assertRaises(AttributeError):
            getattr(cache, "a")

        with self.assertRaises(AttributeError):
            setattr(cache, "a", 1)

        cache.update({"a": 1, "b": 2, "c": 3})
        self.assertEqual(cache.properties, {"a": 1, "b": 2, "c": 3})
        self.assertEqual(cache.a, 1)
        self.assertEqual(cache.b, 2)
        self.assertEqual(cache.c, 3)

        with self.assertRaises(AttributeError):
            setattr(cache, "a", 1)

        cache.update({"a": 10, "b": 20})
        self.assertEqual(cache.properties, {"a": 10, "b": 20, "c": 3})
        self.assertEqual(cache.a, 10)
        self.assertEqual(cache.b, 20)
        self.assertEqual(cache.c, 3)

        cache.update({"d": 4})
        self.assertEqual(cache.properties, {"a": 10, "b": 20, "c": 3, "d": 4})
        self.assertEqual(cache.a, 10)
        self.assertEqual(cache.b, 20)
        self.assertEqual(cache.c, 3)
        self.assertEqual(cache.d, 4)

        cache.update({"c": 30, "d": 40})
        self.assertEqual(cache.properties, {"a": 10, "b": 20, "c": 30, "d": 40})
        self.assertEqual(cache.a, 10)
        self.assertEqual(cache.b, 20)
        self.assertEqual(cache.c, 30)
        self.assertEqual(cache.d, 40)

    def cached_observer_test(self):
        """Test the cached observer."""
        dbus = Mock()
        observer = DBusCachedObserver(dbus, "SERVICE", "OBJECT", ["I"])

        callback = Mock()
        observer.cached_properties_changed.connect(callback)

        proxy = Mock()
        proxy.GetAll.return_value = {"A": 1, "B": 2, "C": 3}
        dbus.get_proxy.return_value = proxy

        # Set up the observer.
        self._setup_observer(observer)

        # Enable service.
        self._make_service_available(observer)
        proxy.PropertiesChanged.connect.assert_called()
        callback.assert_called_once_with(observer, {"A", "B", "C"}, set())
        callback.reset_mock()

        self.assertEqual(observer.cache.A, 1)
        self.assertEqual(observer.cache.B, 2)
        self.assertEqual(observer.cache.C, 3)

        with self.assertRaises(AttributeError):
            getattr(observer.cache, "D")

        # Disable service.
        self._make_service_unavailable(observer)

    def cached_observer_advanced_test(self):
        """Advanced test for the cached observer."""
        dbus = Mock()
        observer = DBusCachedObserver(dbus, "SERVICE", "OBJECT", ["I"])

        callback = Mock()
        observer.cached_properties_changed.connect(callback)

        proxy = Mock()
        proxy.GetAll.return_value = {}
        dbus.get_proxy.return_value = proxy

        # Set up the observer.
        self._setup_observer(observer)

        # Enable service.
        self._make_service_available(observer)
        proxy.PropertiesChanged.connect.assert_called()
        callback.assert_not_called()
        callback.reset_mock()

        # Change values.
        observer._properties_changed_callback("I", {"A": 1}, [])
        callback.assert_called_once_with(observer, {"A"}, set())
        callback.reset_mock()
        self.assertEqual(observer.cache.A, 1)

        with self.assertRaises(AttributeError):
            getattr(observer.cache, "B")

        observer._properties_changed_callback("I", {"A": 10, "B": 2}, [])
        callback.assert_called_once_with(observer, {"A", "B"}, set())
        callback.reset_mock()
        self.assertEqual(observer.cache.A, 10)
        self.assertEqual(observer.cache.B, 2)

        observer._properties_changed_callback("I", {"B": 20}, ["A"])
        callback.assert_called_once_with(observer, {"B"}, {"A"})
        callback.reset_mock()
        self.assertEqual(observer.cache.A, 10)
        self.assertEqual(observer.cache.B, 20)

        observer._properties_changed_callback("I2", {"A": 200, "B": 300}, [])
        callback.assert_not_called()
        self.assertEqual(observer.cache.A, 10)
        self.assertEqual(observer.cache.B, 20)

        # Disable service.
        self._make_service_unavailable(observer)

    def connect_test(self):
        """Test observer connect."""
        dbus = Mock()
        observer = DBusObserver(dbus, "SERVICE")
        self._setup_observer(observer)

        observer.connect()
        dbus.connection.watch_name.assert_called_once()
        self._test_if_service_available(observer)

        observer.disconnect()
        dbus.connection.unwatch_name.assert_called_once()
        self._test_if_service_unavailable(observer)

    def connect_advanced_test(self):
        """Advanced test for observer connect."""
        dbus = Mock()
        observer = DBusObserver(dbus, "SERVICE")
        self._setup_observer(observer)

        observer.connect()
        dbus.connection.watch_name.assert_called_once()
        self._test_if_service_available(observer)

        observer._service_name_appeared_callback()
        self.assertTrue(observer.is_service_available)
        observer._service_available.emit.assert_not_called()  # pylint: disable=no-member
        observer._service_unavailable.emit.assert_not_called()  # pylint: disable=no-member

        observer._service_name_vanished_callback()
        self._test_if_service_unavailable(observer)

        observer.disconnect()
        dbus.connection.unwatch_name.assert_called_once()
        self.assertFalse(observer.is_service_available)
        observer._service_available.emit.assert_not_called()  # pylint: disable=no-member
        observer._service_unavailable.emit.assert_not_called()  # pylint: disable=no-member

    def connect_failed_test(self):
        """Test observer connect failed."""
        dbus = Mock()
        observer = DBusObserver(dbus, "SERVICE")
        self._setup_observer(observer)

        proxy = Mock()
        proxy.NameHasOwner.return_value = False
        dbus.get_dbus_proxy.return_value = proxy

        with self.assertRaises(DBusObserverError):
            observer.connect()
