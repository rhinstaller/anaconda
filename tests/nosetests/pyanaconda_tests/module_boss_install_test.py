#
# Copyright (C) 2017  Red Hat, Inc.
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
from unittest.mock import Mock, call

from pyanaconda.modules.boss.install_manager import InstallManager
from pyanaconda.modules.common.task import DBusMetaTask
from tests.nosetests.pyanaconda_tests import patch_dbus_get_proxy


class InstallManagerTestCase(unittest.TestCase):
    """Test the install manager."""

    def install_with_no_modules_test(self):
        """Install with no modules."""
        install_manager = InstallManager()
        install_manager.on_module_observers_changed([])
        main_task = install_manager.install_system_with_task()
        self.assertIsInstance(main_task, DBusMetaTask)
        self.assertEqual(main_task.name, "Install the system")
        self.assertEqual(main_task._subtasks, [])

    def install_with_no_tasks_test(self):
        """Install with no tasks."""
        observer = Mock()
        observer.is_service_available = True
        observer.service_name = "A"
        observer.proxy.InstallWithTasks.return_value = []

        install_manager = InstallManager()
        install_manager.on_module_observers_changed([observer])
        main_task = install_manager.install_system_with_task()

        self.assertIsInstance(main_task, DBusMetaTask)
        self.assertEqual(main_task.name, "Install the system")
        self.assertEqual(main_task._subtasks, [])

    @patch_dbus_get_proxy
    def install_one_task_test(self, proxy_getter):
        """Install with one task."""
        observer = Mock()
        observer.is_service_available = True
        observer.service_name = "A"
        observer.proxy.InstallWithTasks.return_value = ["/A/1"]

        task_proxy = Mock()
        task_proxy.Steps = 1
        proxy_getter.return_value = task_proxy

        install_manager = InstallManager()
        install_manager.on_module_observers_changed([observer])
        main_task = install_manager.install_system_with_task()

        proxy_getter.assert_called_once_with("A", "/A/1")
        self.assertIsInstance(main_task, DBusMetaTask)
        self.assertEqual(main_task.name, "Install the system")
        self.assertEqual(main_task._subtasks, [task_proxy])

    @patch_dbus_get_proxy
    def install_three_tasks_test(self, proxy_getter):
        """Install with three tasks."""
        observers = []

        observer = Mock()
        observer.is_service_available = True
        observer.service_name = "A"
        observer.proxy.InstallWithTasks.return_value = ["/A/1"]

        observers.append(observer)

        observer = Mock()
        observer.is_service_available = True
        observer.service_name = "B"
        observer.proxy.InstallWithTasks.return_value = ["/B/1", "/B/2"]

        observers.append(observer)

        task_proxy = Mock()
        task_proxy.Steps = 1
        proxy_getter.return_value = task_proxy

        install_manager = InstallManager()
        install_manager.on_module_observers_changed(observers)
        main_task = install_manager.install_system_with_task()

        proxy_getter.assert_has_calls([
            call("A", "/A/1"),
            call("B", "/B/1"),
            call("B", "/B/2")
        ])
        self.assertIsInstance(main_task, DBusMetaTask)
        self.assertEqual(main_task.name, "Install the system")
        self.assertEqual(main_task._subtasks, [task_proxy, task_proxy, task_proxy])

    @patch_dbus_get_proxy
    def configure_runtime_test(self, proxy_getter):
        """Configure the runtime system with three tasks."""
        observers = []

        observer = Mock()
        observer.is_service_available = True
        observer.service_name = "A"
        observer.proxy.ConfigureWithTasks.return_value = ["/A/1"]

        observers.append(observer)

        observer = Mock()
        observer.is_service_available = True
        observer.service_name = "B"
        observer.proxy.ConfigureWithTasks.return_value = ["/B/1", "/B/2"]

        observers.append(observer)

        task_proxy = Mock()
        task_proxy.Steps = 1
        proxy_getter.return_value = task_proxy

        install_manager = InstallManager()
        install_manager.on_module_observers_changed(observers)
        main_task = install_manager.configure_runtime_with_task()

        proxy_getter.assert_has_calls([
            call("A", "/A/1"),
            call("B", "/B/1"),
            call("B", "/B/2")
        ])
        self.assertIsInstance(main_task, DBusMetaTask)
        self.assertEqual(main_task.name, "Configure the runtime system")
        self.assertEqual(main_task._subtasks, [task_proxy, task_proxy, task_proxy])
