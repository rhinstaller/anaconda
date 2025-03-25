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
import tempfile
import unittest
from unittest.mock import Mock, patch

from dasbus.typing import *  # pylint: disable=wildcard-import
from pykickstart.base import KickstartHandler

from pyanaconda.core.constants import DEFAULT_LANG
from pyanaconda.installation import RunInstallationTask
from pyanaconda.modules.boss.boss import Boss
from pyanaconda.modules.boss.boss_interface import BossInterface
from pyanaconda.modules.boss.installation import CopyLogsTask, SetContextsTask
from pyanaconda.modules.boss.module_manager.start_modules import StartModulesTask
from pyanaconda.modules.common.structures.requirement import Requirement
from pyanaconda.payload.migrated import ActiveDBusPayload

from tests.unit_tests.pyanaconda_tests import patch_dbus_publish_object, check_task_creation, \
    patch_dbus_get_proxy, check_task_creation_list


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
        module_proxy.ConfigureBootloaderWithTasks.return_value = ["/task/5", "/task/6"]
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

    def test_get_modules(self):
        """Test GetModules."""
        assert self.interface.GetModules() == []

        self._add_module("org.fedoraproject.Anaconda.Modules.A")
        self._add_module("org.fedoraproject.Anaconda.Modules.B")
        self._add_module("org.fedoraproject.Anaconda.Addons.C", available=False)
        self._add_module("org.fedoraproject.Anaconda.Addons.D")

        assert self.interface.GetModules() == [
            "org.fedoraproject.Anaconda.Modules.A",
            "org.fedoraproject.Anaconda.Modules.B",
            "org.fedoraproject.Anaconda.Addons.D"
        ]

    @patch_dbus_publish_object
    def test_start_modules_with_task(self, publisher):
        """Test StartModulesWithTask."""
        task_path = self.interface.StartModulesWithTask()
        task_proxy = check_task_creation(task_path, publisher, StartModulesTask)
        task = task_proxy.implementation

        callback = Mock()
        self.module._module_manager.module_observers_changed.connect(callback)

        observers = [Mock(), Mock(), Mock()]
        task._set_result(observers)
        task.succeeded_signal.emit()
        callback.assert_called_once_with(observers)

    def test_read_kickstart_file(self):
        """Test ReadKickstartFile."""
        with tempfile.NamedTemporaryFile("r+") as f:
            report = self.interface.ReadKickstartFile(f.name)

        assert report == {
            "error-messages": get_variant(List[Structure], []),
            "warning-messages": get_variant(List[Structure], [])
        }

    def test_generate_kickstart(self):
        """Test GenerateKickstart."""
        assert self.interface.GenerateKickstart() == ""

    def test_set_locale(self):
        """Test SetLocale."""
        assert self.interface.SetLocale(DEFAULT_LANG) is None

    def test_collect_requirements(self):
        """Test CollectRequirements."""
        assert self.interface.CollectRequirements() == []

        self._add_module_with_requirement("A", package_name="a")
        self._add_module_with_requirement("B", package_name="b")
        self._add_module_with_requirement("C", package_name="c", available=False)

        assert self.interface.CollectRequirements() == [
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
        ]

    @patch_dbus_publish_object
    @patch_dbus_get_proxy
    def test_install_with_tasks(self, proxy_getter, publisher):
        """Test InstallWithTasks."""
        task_paths = self.interface.InstallWithTasks()
        task_proxies = check_task_creation_list(task_paths, publisher, [RunInstallationTask])
        task = task_proxies[0].implementation

        assert isinstance(task._payload, ActiveDBusPayload)
        assert isinstance(task._ksdata, KickstartHandler)

    @patch("pyanaconda.modules.boss.boss_interface.get_object_handler")
    @patch_dbus_get_proxy
    def test_collect_configure_runtime_tasks(self, proxy_getter, handler_getter):
        """Test CollectConfigureRuntimeTasks."""
        assert self.interface.CollectConfigureRuntimeTasks() == []

        self._add_module_with_tasks("A")
        self._add_module_with_tasks("B")
        self._add_module_with_tasks("C", available=False)

        proxy_getter.side_effect = self._get_mocked_proxy
        handler_getter.side_effect = self._get_mocked_handler

        assert self.interface.CollectConfigureRuntimeTasks() == [
            ("A", "/task/1"),
            ("A", "/task/2"),
            ("B", "/task/1"),
            ("B", "/task/2"),
        ]

    @patch("pyanaconda.modules.boss.boss_interface.get_object_handler")
    @patch_dbus_get_proxy
    def test_collect_configure_bootloader_tasks(self, proxy_getter, handler_getter):
        """Test CollectConfigureBootloaderTasks."""
        version = "4.17.7-200.fc28.x86_64"
        assert self.interface.CollectConfigureBootloaderTasks([version]) == []

        self._add_module_with_tasks("A")
        self._add_module_with_tasks("B")
        self._add_module_with_tasks("C", available=False)

        proxy_getter.side_effect = self._get_mocked_proxy
        handler_getter.side_effect = self._get_mocked_handler

        assert self.interface.CollectConfigureBootloaderTasks([version]) == [
            ("A", "/task/5"),
            ("A", "/task/6"),
            ("B", "/task/5"),
            ("B", "/task/6"),
        ]

    @patch("pyanaconda.modules.boss.boss_interface.get_object_handler")
    @patch_dbus_get_proxy
    def test_collect_install_system_tasks(self, proxy_getter, handler_getter):
        """Test CollectInstallSystemTasks."""
        assert self.interface.CollectInstallSystemTasks() == []

        self._add_module_with_tasks("A")
        self._add_module_with_tasks("B")
        self._add_module_with_tasks("C", available=False)

        proxy_getter.side_effect = self._get_mocked_proxy
        handler_getter.side_effect = self._get_mocked_handler

        assert self.interface.CollectInstallSystemTasks() == [
            ("A", "/task/3"),
            ("A", "/task/4"),
            ("B", "/task/3"),
            ("B", "/task/4"),
        ]

    @patch_dbus_publish_object
    def test_finish_installation_with_tasks(self, publisher):
        """Test FinishInstallationWithTasks."""
        task_list = self.interface.FinishInstallationWithTasks()

        assert len(task_list) == 2

        task_path = task_list[0]
        task_proxy = check_task_creation(task_path, publisher, SetContextsTask, 0)
        task = task_proxy.implementation
        assert task.name == "Set file contexts"

        task_path = task_list[1]
        task_proxy = check_task_creation(task_path, publisher, CopyLogsTask, 1)
        task = task_proxy.implementation
        assert task.name == "Copy installation logs"

    def test_quit(self):
        """Test Quit."""
        assert self.interface.Quit() is None
