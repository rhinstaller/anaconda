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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest
import pytest
from unittest.mock import Mock, patch

from dasbus.constants import DBUS_START_REPLY_SUCCESS, DBUS_FLAG_NONE
from dasbus.error import DBusError

from pyanaconda.modules.boss.module_manager import ModuleManager
from pyanaconda.modules.boss.module_manager.start_modules import StartModulesTask
from pyanaconda.modules.common.errors.module import UnavailableModuleError


class ModuleManagerTestCase(unittest.TestCase):
    """Test the module manager of the Boss module."""

    def setUp(self):
        self._manager = ModuleManager()
        self._message_bus = Mock()
        self._message_bus.proxy.ListActivatableNames.return_value = [
            "org.fedoraproject.Anaconda.Boss",
            "org.fedoraproject.Anaconda.Addons.A",
            "org.fedoraproject.Anaconda.Addons.B",
            "org.fedoraproject.Anaconda.Addons.C",
            "org.fedoraproject.Anaconda.Modules.A",
            "org.fedoraproject.Anaconda.Modules.B",
            "org.fedoraproject.Anaconda.Modules.C",
            "org.fedoraproject.InitialSetup.Modules.A",
            "org.fedoraproject.InitialSetup.Modules.B",
            "org.fedoraproject.InitialSetup.Modules.C",
        ]

    def _check_started_modules(self, task, service_names):
        """Check the started modules."""

        def call():
            return DBUS_START_REPLY_SUCCESS

        def fake_callbacks(fake_observer):
            for observer in task._module_observers:
                observer._is_service_available = True
                task._start_service_by_name_callback(call, observer)
                task._service_available_callback(observer)

        task._callbacks.put((None, fake_callbacks))
        observers = task.run()

        assert [o.service_name for o in observers] == service_names
        return observers

    def test_start_no_modules(self):
        """Start no modules."""
        task = StartModulesTask(self._message_bus, [], [], [])
        self._check_started_modules(task, [])

    @patch("dasbus.client.observer.Gio")
    def test_start_one_module(self, gio):
        """Start one module."""
        service_names = [
            "org.fedoraproject.Anaconda.Modules.A"
        ]
        task = StartModulesTask(self._message_bus, service_names, [], [])
        (observer, ) = self._check_started_modules(task, service_names)  # pylint: disable=unbalanced-tuple-unpacking

        bus_proxy = self._message_bus.proxy
        bus_proxy.StartServiceByName.assert_called_once_with(
            "org.fedoraproject.Anaconda.Modules.A",
            DBUS_FLAG_NONE,
            callback=task._start_service_by_name_callback,
            callback_args=(observer,)
        )

        gio.bus_watch_name_on_connection.assert_called_once()
        observer.proxy.Ping.assert_called_once_with()

    @patch("dasbus.client.observer.Gio")
    def test_start_modules(self, gio):
        """Start modules."""
        service_names = [
            "org.fedoraproject.Anaconda.Modules.A",
            "org.fedoraproject.Anaconda.Modules.B",
            "org.fedoraproject.Anaconda.Modules.C",
        ]

        task = StartModulesTask(self._message_bus, service_names, [], [])
        observers = self._check_started_modules(task, service_names)

        for observer in observers:
            assert observer.is_addon is False

    @patch("dasbus.client.observer.Gio")
    def test_start_addons(self, gio):
        """Start addons."""
        service_namespaces = [
            "org.fedoraproject.Anaconda.Addons.*"
        ]
        service_names = [
            "org.fedoraproject.Anaconda.Addons.A",
            "org.fedoraproject.Anaconda.Addons.B",
            "org.fedoraproject.Anaconda.Addons.C"
        ]

        task = StartModulesTask(self._message_bus, service_namespaces, [], [])
        observers = self._check_started_modules(task, service_names)

        for observer in observers:
            assert observer.is_addon is True

    @patch("dasbus.client.observer.Gio")
    def test_start_modules_forbidden(self, gio):
        """Try to start forbidden modules."""
        service_namespaces = [
            "org.fedoraproject.Anaconda.Modules.*",
            "org.fedoraproject.Anaconda.Addons.*",
            "org.fedoraproject.InitialSetup.Modules.*",
        ]
        forbidden_names = [
            "org.fedoraproject.Anaconda.Modules.B",
            "org.fedoraproject.Anaconda.Addons.C",
            "org.fedoraproject.InitialSetup.*",
        ]
        service_names = [
            "org.fedoraproject.Anaconda.Addons.A",
            "org.fedoraproject.Anaconda.Addons.B",
            "org.fedoraproject.Anaconda.Modules.A",
            "org.fedoraproject.Anaconda.Modules.C",
        ]

        task = StartModulesTask(
            message_bus=self._message_bus,
            activatable=service_namespaces,
            forbidden=forbidden_names,
            optional=[]
        )

        self._check_started_modules(task, service_names)

    def test_start_module_failed(self):
        """Fail to start a module."""
        service_names = [
            "org.fedoraproject.Anaconda.Modules.A",
            "org.fedoraproject.Anaconda.Modules.B",
            "org.fedoraproject.Anaconda.Modules.C",
        ]

        task = StartModulesTask(self._message_bus, service_names, [], [])

        def call():
            raise DBusError("Fake error!")

        def fake_callbacks(fake_observer):
            for observer in task._module_observers:
                task._start_service_by_name_callback(call, observer)

        task._callbacks.put((None, fake_callbacks))

        with pytest.raises(UnavailableModuleError) as cm:
            task.run()

        expected = "Service org.fedoraproject.Anaconda.Modules.A has failed to start: Fake error!"
        assert str(cm.value) == expected

    @patch("dasbus.client.observer.Gio")
    def test_start_addon_failed(self, gio):
        """Fail to start an add-on."""
        service_namespaces = [
            "org.fedoraproject.Anaconda.Addons.*"
        ]
        service_names = [
            "org.fedoraproject.Anaconda.Addons.A",
            "org.fedoraproject.Anaconda.Addons.B",
            "org.fedoraproject.Anaconda.Addons.C"
        ]

        task = StartModulesTask(
            message_bus=self._message_bus,
            activatable=service_namespaces,
            optional=service_namespaces,
            forbidden=[]
        )
        self._check_started_modules(task, service_names)

        def call():
            raise DBusError("Fake error!")

        def fake_callbacks(fake_observer):
            for observer in task._module_observers:
                task._start_service_by_name_callback(call, observer)

        task._callbacks.put((None, fake_callbacks))
        assert task.run() == []

    @patch("dasbus.client.observer.Gio")
    def test_get_service_names(self, gio):
        """Get service names of running modules."""
        assert self._manager.get_service_names() == []

        service_names = [
            "org.fedoraproject.Anaconda.Modules.A",
            "org.fedoraproject.Anaconda.Modules.B",
            "org.fedoraproject.Anaconda.Modules.C",
        ]

        task = StartModulesTask(self._message_bus, service_names, [], [])
        observers = self._check_started_modules(task, service_names)

        self._manager.set_module_observers(observers)
        assert self._manager.get_service_names() == service_names
