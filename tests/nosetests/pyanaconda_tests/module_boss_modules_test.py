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
import unittest
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

    def _check_started_modules(self, task, service_names):
        """Check the started modules."""

        def call():
            return DBUS_START_REPLY_SUCCESS

        def fake_callbacks():
            for observer in task._module_observers:
                observer._is_service_available = True
                task._start_service_by_name_callback(call, observer)
                task._service_available_callback(observer)

        task._callbacks.put(fake_callbacks)
        observers = task.run()

        self.assertEqual([o.service_name for o in observers], service_names)
        return observers

    def start_no_modules_test(self):
        """Start no modules."""
        task = StartModulesTask(self._message_bus, [], addons_enabled=False)
        self._check_started_modules(task, [])

    @patch("dasbus.client.observer.Gio")
    def start_one_module_test(self, gio):
        """Start one module."""
        service_names = [
            "org.fedoraproject.Anaconda.Modules.A"
        ]

        task = StartModulesTask(self._message_bus, service_names, addons_enabled=False)
        (observer, ) = self._check_started_modules(task, service_names)

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
    def start_modules_test(self, gio):
        """Start modules."""
        service_names = [
            "org.fedoraproject.Anaconda.Modules.A",
            "org.fedoraproject.Anaconda.Modules.B",
            "org.fedoraproject.Anaconda.Modules.C",
        ]

        task = StartModulesTask(self._message_bus, service_names, addons_enabled=False)
        self._check_started_modules(task, service_names)

    @patch("dasbus.client.observer.Gio")
    def start_addons_test(self, gio):
        """Start addons."""
        service_names = [
            "org.fedoraproject.Anaconda.Addons.A",
            "org.fedoraproject.Anaconda.Addons.B",
            "org.fedoraproject.Anaconda.Addons.C"
        ]

        bus_proxy = self._message_bus.proxy
        bus_proxy.ListActivatableNames.return_value = [
            *service_names,
            "org.fedoraproject.Anaconda.D",
            "org.fedoraproject.E",
        ]

        task = StartModulesTask(self._message_bus, [], addons_enabled=True)
        self._check_started_modules(task, service_names)

    def start_failed_test(self):
        """Fail to start a module."""
        service_names = [
            "org.fedoraproject.Anaconda.Modules.A",
            "org.fedoraproject.Anaconda.Modules.B",
            "org.fedoraproject.Anaconda.Modules.C",
        ]

        task = StartModulesTask(self._message_bus, service_names, addons_enabled=False)

        def call():
            raise DBusError("Fake error!")

        def fake_callbacks():
            for observer in task._module_observers:
                task._start_service_by_name_callback(call, observer)

        task._callbacks.put(fake_callbacks)

        with self.assertRaises(UnavailableModuleError) as cm:
            task.run()

        expected = "Service org.fedoraproject.Anaconda.Modules.A has failed to start: Fake error!"
        self.assertEqual(str(cm.exception), expected)

    @patch("dasbus.client.observer.Gio")
    def get_service_names_test(self, gio):
        """Get service names of running modules."""
        self.assertEqual(self._manager.get_service_names(), [])

        service_names = [
            "org.fedoraproject.Anaconda.Modules.A",
            "org.fedoraproject.Anaconda.Modules.B",
            "org.fedoraproject.Anaconda.Modules.C",
        ]

        task = StartModulesTask(self._message_bus, service_names, addons_enabled=False)
        observers = self._check_started_modules(task, service_names)

        self._manager.set_module_observers(observers)
        self.assertEqual(self._manager.get_service_names(), service_names)
