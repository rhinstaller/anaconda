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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
import pytest
from unittest.mock import Mock

from dasbus.client.observer import DBusObserverError
from pyanaconda.modules.boss.module_manager.module_observer import ModuleObserver


class ModuleObserverTestCase(unittest.TestCase):
    """Test DBus module observers."""

    def _setup_observer(self, observer):
        """Set up the observer."""
        observer._service_available = Mock()
        observer._service_unavailable = Mock()
        assert not observer.is_service_available

    def _make_service_available(self, observer):
        """Make the service available."""
        observer._service_name_appeared_callback()
        self._test_if_service_available(observer)

    def _test_if_service_available(self, observer):
        """Test if service is available."""
        assert observer.is_service_available

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
        assert not observer.is_service_available

        observer._service_unavailable.emit.assert_called_once_with(observer)
        observer._service_unavailable.reset_mock()

        observer._service_available.emit.assert_not_called()
        observer._service_available.reset_mock()

    def test_module_observer(self):
        """Test the module observer."""
        dbus = Mock()
        observer = ModuleObserver(dbus, "my.test.module")

        # Setup the observer.
        self._setup_observer(observer)
        assert observer._proxy is None

        with pytest.raises(DBusObserverError):
            observer.proxy.DoSomething()

        # Service available.
        self._make_service_available(observer)
        assert observer._proxy is None

        # Access the proxy.
        observer.proxy.DoSomething()
        dbus.get_proxy.assert_called_once_with("my.test.module", "/my/test/module")
        assert observer._proxy is not None

        # Service unavailable.

        self._make_service_unavailable(observer)
        assert observer._proxy is None

        with pytest.raises(DBusObserverError):
            observer.proxy.DoSomething()
