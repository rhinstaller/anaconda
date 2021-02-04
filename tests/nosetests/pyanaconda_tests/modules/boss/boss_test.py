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
import tempfile
import unittest
from unittest.mock import Mock, patch

from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import DEFAULT_LANG
from pyanaconda.modules.boss.boss import Boss
from pyanaconda.modules.boss.boss_interface import BossInterface
from pyanaconda.modules.boss.module_manager.start_modules import StartModulesTask
from pyanaconda.modules.common.structures.requirement import Requirement

from tests.nosetests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation, \
    patch_dbus_get_proxy


class BossInterfaceTestCase(unittest.TestCase):
    """Test DBus interface for the Boss module."""

    def setUp(self):
        """Set up the module."""
        self.module = Boss()
        self.interface = BossInterface(self.module)

    def _add_module(self, service_name, available=True, proxy=None):
        """Add a DBus module."""
        if proxy is None:
            proxy = Mock()

        observer = Mock(
            service_name=service_name,
            is_service_available=available,
            proxy=proxy,
        )

        module_manager = self.module._module_manager
        observers = list(module_manager.module_observers)
        observers.append(observer)

        module_manager.set_module_observers(observers)
        return observer

    def _add_module_with_requirement(self, service_name, package_name, available=True):
        """Add a DBus module with a package requirement."""
        requirement = Requirement.for_package(
            package_name=package_name,
            reason="Required by {}.".format(service_name)
        )

        module_proxy = Mock()
        module_proxy.CollectRequirements.return_value = \
            Requirement.to_structure_list([requirement])

        self._add_module(service_name, available=available, proxy=module_proxy)

    def _add_module_with_tasks(self, service_name, available=True):
        """Add a DBus module with a package requirement."""
        module_proxy = Mock()
        module_proxy.ConfigureWithTasks.return_value = ["/task/1", "/task/2"]
        module_proxy.InstallWithTasks.return_value = ["/task/3", "/task/4"]
        self._add_module(service_name, available=available, proxy=module_proxy)

    def _get_mocked_proxy(self, service_name, object_path):
        """Callback for a proxy getter."""
        object_handler = Mock()
        object_handler.service_name = service_name
        object_handler.object_path = object_path

        object_proxy = Mock()
        object_proxy.object_handler = object_handler

        return object_proxy

    def _get_mocked_handler(self, object_proxy):
        """Callback for a handler getter."""
        return object_proxy.object_handler

    def get_modules_test(self):
        """Test GetModules."""
        self.assertEqual(self.interface.GetModules(), [])

        self._add_module("org.fedoraproject.Anaconda.Modules.A")
        self._add_module("org.fedoraproject.Anaconda.Modules.B")
        self._add_module("org.fedoraproject.Anaconda.Addons.C", available=False)
        self._add_module("org.fedoraproject.Anaconda.Addons.D")

        self.assertEqual(self.interface.GetModules(), [
            "org.fedoraproject.Anaconda.Modules.A",
            "org.fedoraproject.Anaconda.Modules.B",
            "org.fedoraproject.Anaconda.Addons.D"
        ])

    @patch_dbus_publish_object
    def start_modules_with_task_test(self, publisher):
        """Test StartModulesWithTask."""
        task_path = self.interface.StartModulesWithTask()
        task_proxy = check_task_creation(self, task_path, publisher, StartModulesTask)
        task = task_proxy.implementation

        callback = Mock()
        self.module._module_manager.module_observers_changed.connect(callback)

        observers = [Mock(), Mock(), Mock()]
        task._set_result(observers)
        task.succeeded_signal.emit()
        callback.assert_called_once_with(observers)

    def read_kickstart_file_test(self):
        """Test ReadKickstartFile."""
        with tempfile.NamedTemporaryFile("r+") as f:
            report = self.interface.ReadKickstartFile(f.name)

        self.assertEqual(report, {
            "error-messages": get_variant(List[Structure], []),
            "warning-messages": get_variant(List[Structure], [])
        })

    def generate_kickstart_test(self):
        """Test GenerateKickstart."""
        self.assertEqual(self.interface.GenerateKickstart(), "")

    def set_locale_test(self):
        """Test SetLocale."""
        self.assertEqual(self.interface.SetLocale(DEFAULT_LANG), None)

    def collect_requirements_test(self):
        """Test CollectRequirements."""
        self.assertEqual(self.interface.CollectRequirements(), [])

        self._add_module_with_requirement("A", package_name="a")
        self._add_module_with_requirement("B", package_name="b")
        self._add_module_with_requirement("C", package_name="c", available=False)

        self.assertEqual(self.interface.CollectRequirements(), [
            {
                "type": get_variant(Str, "package"),
                "name": get_variant(Str, "a"),
                "reason": get_variant(Str, "Required by A.")
            },
            {
                "type": get_variant(Str, "package"),
                "name": get_variant(Str, "b"),
                "reason": get_variant(Str, "Required by B.")
            }
        ])

    @patch("pyanaconda.modules.boss.boss_interface.get_object_handler")
    @patch_dbus_get_proxy
    def collect_configure_runtime_tasks_test(self, proxy_getter, handler_getter):
        """Test CollectConfigureRuntimeTasks."""
        self.assertEqual(self.interface.CollectConfigureRuntimeTasks(), [])

        self._add_module_with_tasks("A")
        self._add_module_with_tasks("B")
        self._add_module_with_tasks("C", available=False)

        proxy_getter.side_effect = self._get_mocked_proxy
        handler_getter.side_effect = self._get_mocked_handler

        self.assertEqual(self.interface.CollectConfigureRuntimeTasks(), [
            ("A", "/task/1"),
            ("A", "/task/2"),
            ("B", "/task/1"),
            ("B", "/task/2"),
        ])

    @patch("pyanaconda.modules.boss.boss_interface.get_object_handler")
    @patch_dbus_get_proxy
    def collect_install_system_tasks_test(self, proxy_getter, handler_getter):
        """Test CollectInstallSystemTasks."""
        self.assertEqual(self.interface.CollectInstallSystemTasks(), [])

        self._add_module_with_tasks("A")
        self._add_module_with_tasks("B")
        self._add_module_with_tasks("C", available=False)

        proxy_getter.side_effect = self._get_mocked_proxy
        handler_getter.side_effect = self._get_mocked_handler

        self.assertEqual(self.interface.CollectInstallSystemTasks(), [
            ("A", "/task/3"),
            ("A", "/task/4"),
            ("B", "/task/3"),
            ("B", "/task/4"),
        ])

    def quit_test(self):
        """Test Quit."""
        self.assertEqual(self.interface.Quit(), None)
