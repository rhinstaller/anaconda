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
from unittest.mock import patch, Mock

from dasbus.constants import DBUS_FLAG_NONE
from dasbus.client.observer import DBusObserver


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

    @patch("dasbus.client.observer.Gio")
    def connect_test(self, gio):
        """Test Gio support for watching names."""
        dbus = Mock()
        observer = DBusObserver(dbus, "my.service")
        self._setup_observer(observer)

        # Connect the observer.
        observer.connect_once_available()

        # Check the call.
        gio.bus_watch_name_on_connection.assert_called_once()
        args, kwargs = gio.bus_watch_name_on_connection.call_args

        self.assertEqual(len(args), 5)
        self.assertEqual(len(kwargs), 0)
        self.assertEqual(args[0], dbus.connection)
        self.assertEqual(args[1], "my.service")
        self.assertEqual(args[2], DBUS_FLAG_NONE)

        name_appeared_closure = args[3]
        self.assertTrue(callable(name_appeared_closure))

        name_vanished_closure = args[4]
        self.assertTrue(callable(name_vanished_closure))

        # Check the subscription.
        subscription_id = gio.bus_watch_name_on_connection.return_value
        self.assertEqual(len(observer._subscriptions), 1)

        # Check the observer.
        self.assertFalse(observer.is_service_available)
        observer._service_available.emit.assert_not_called()  # pylint: disable=no-member
        observer._service_unavailable.emit.assert_not_called()  # pylint: disable=no-member

        # Call the name appeared closure.
        name_appeared_closure(dbus.connection, "my.service", "name.owner")
        self._test_if_service_available(observer)

        # Call the name vanished closure.
        name_vanished_closure(dbus.connection, "my.service")
        self._test_if_service_unavailable(observer)

        # Call the name appeared closure again.
        name_appeared_closure(dbus.connection, "my.service", "name.owner")
        self._test_if_service_available(observer)

        # Disconnect the observer.
        observer.disconnect()

        gio.bus_unwatch_name.assert_called_once_with(
            subscription_id
        )

        self._test_if_service_unavailable(observer)
        self.assertEqual(observer._subscriptions, [])
