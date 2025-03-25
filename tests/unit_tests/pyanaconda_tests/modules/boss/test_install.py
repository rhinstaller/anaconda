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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import unittest
from unittest.mock import Mock, call

from pyanaconda.modules.boss.install_manager import InstallManager
from tests.unit_tests.pyanaconda_tests import patch_dbus_get_proxy


class InstallManagerTestCase(unittest.TestCase):
    """Test the install manager."""

    def test_install_with_no_modules(self):
        """Install with no modules."""
        install_manager = InstallManager()
        install_manager.on_module_observers_changed([])
        proxies = install_manager.collect_install_system_tasks()
        assert proxies == []

    def test_install_with_no_tasks(self):
        """Install with no tasks."""
        observer = Mock()
        observer.is_service_available = True
        observer.service_name = "A"
        observer.proxy.InstallWithTasks.return_value = []

        install_manager = InstallManager()
        install_manager.on_module_observers_changed([observer])
        proxies = install_manager.collect_install_system_tasks()
        assert proxies == []

    @patch_dbus_get_proxy
    def test_install_one_task(self, proxy_getter):
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
        proxies = install_manager.collect_install_system_tasks()
        assert proxies == [task_proxy]

        proxy_getter.assert_called_once_with("A", "/A/1")

    @patch_dbus_get_proxy
    def test_install_three_tasks(self, proxy_getter):
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
        proxies = install_manager.collect_install_system_tasks()
        assert proxies == [task_proxy, task_proxy, task_proxy]

        proxy_getter.assert_has_calls([
            call("A", "/A/1"),
            call("B", "/B/1"),
            call("B", "/B/2")
        ])

    @patch_dbus_get_proxy
    def test_configure_runtime(self, proxy_getter):
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
        proxies = install_manager.collect_configure_runtime_tasks()
        assert proxies == [task_proxy, task_proxy, task_proxy]

        proxy_getter.assert_has_calls([
            call("A", "/A/1"),
            call("B", "/B/1"),
            call("B", "/B/2")
        ])
