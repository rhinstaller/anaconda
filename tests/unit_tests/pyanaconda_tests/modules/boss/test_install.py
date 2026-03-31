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
from unittest.mock import Mock, call, patch

from pyanaconda.modules.common.structures.validation import ValidationReport
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

    @patch("pyanaconda.modules.boss.install_manager.install_manager.USERS.get_proxy")
    @patch("pyanaconda.modules.boss.install_manager.install_manager.PAYLOADS.get_proxy")
    def test_collect_installation_readiness_success(self, payloads_get_proxy, users_get_proxy):
        """Test successful collection of global readiness."""
        validation_report = ValidationReport()
        payloads_service_proxy = Mock(ValidationReport=ValidationReport.to_structure(validation_report))

        payloads_get_proxy.return_value = payloads_service_proxy
        users_get_proxy.return_value = Mock(ValidationReport=ValidationReport.to_structure(ValidationReport()))

        install_manager = InstallManager()
        report = install_manager.collect_installation_readiness()

        assert report.can_reach_install is True
        assert report.blocking_errors == []
        assert report.reasons_by_module.keys() == {"payload", "users"}

    @patch("pyanaconda.modules.boss.install_manager.install_manager.USERS.get_proxy")
    @patch("pyanaconda.modules.boss.install_manager.install_manager.PAYLOADS.get_proxy")
    def test_collect_installation_readiness_failures(self, payloads_get_proxy, users_get_proxy):
        """Test readiness errors are aggregated."""
        payloads_get_proxy.return_value = Mock(ActivePayload="")
        users_report = ValidationReport()
        users_report.error_messages = ["No administrator account is configured."]
        users_get_proxy.return_value = Mock(ValidationReport=ValidationReport.to_structure(users_report))

        install_manager = InstallManager()
        report = install_manager.collect_installation_readiness()

        assert report.can_reach_install is False
        assert "No active payload is configured." in report.blocking_errors
        assert "No administrator account is configured." in report.blocking_errors

    @patch("pyanaconda.modules.boss.install_manager.install_manager.USERS.get_proxy")
    @patch("pyanaconda.modules.boss.install_manager.install_manager.PAYLOADS.get_proxy")
    def test_collect_installation_readiness_payload_check_error(self, payloads_get_proxy, users_get_proxy):
        """Test payload validation property error is propagated."""
        class BrokenPayloadsProxy:
            @property
            def ValidationReport(self):
                raise RuntimeError("task failed")

        payloads_get_proxy.return_value = BrokenPayloadsProxy()
        users_get_proxy.return_value = Mock(ValidationReport=ValidationReport.to_structure(ValidationReport()))

        install_manager = InstallManager()
        with self.assertRaisesRegex(RuntimeError, "task failed"):
            install_manager.collect_installation_readiness()
