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
from unittest.mock import Mock, patch

import pytest
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import DEFAULT_LANG
from pyanaconda.modules.boss.boss import Boss
from pyanaconda.modules.boss.boss_interface import BossInterface
from pyanaconda.modules.boss.installation import RunInstallationTask
from pyanaconda.modules.boss.module_manager.start_modules import StartModulesTask
from pyanaconda.modules.common.constants.installation import (
    InstallationErrorDialogType,
    InstallationStatus,
)
from pyanaconda.modules.common.structures.requirement import Requirement
from tests.unit_tests.pyanaconda_tests import (
    check_task_creation,
    check_task_creation_list,
    patch_dbus_get_proxy,
    patch_dbus_publish_object,
)


class BossInterfaceTestCase:
    """Test DBus interface for the Boss module."""

    @pytest.fixture(autouse=True)
    def _setup(self, anaconda_run_dir):
        self.module = Boss()
        self.interface = BossInterface(self.module)
        self._error_file = self.module._error_file

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
    def test_install_with_tasks(self, publisher):
        """Test InstallWithTasks."""
        task_paths = self.interface.InstallWithTasks()
        check_task_creation_list(task_paths, publisher, [RunInstallationTask])

    @patch_dbus_publish_object
    def test_install_with_tasks_returns_same_when_running(self, publisher):
        """Test that InstallWithTasks returns the same task when running."""
        task_paths_1 = self.interface.InstallWithTasks()
        task_proxy = check_task_creation(task_paths_1[0], publisher, RunInstallationTask)
        task = task_proxy.implementation

        with patch.object(type(task), 'is_running', new_callable=lambda: property(lambda self: True)):
            task_paths_2 = self.interface.InstallWithTasks()
            assert task_paths_1 == task_paths_2

    def test_install_with_tasks_returns_empty_after_succeeded(self):
        """Test that InstallWithTasks returns [] after a successful installation."""
        self.module.install_with_tasks()
        self.module._on_installation_started()
        self.module._on_installation_succeeded()
        self.module._on_installation_stopped()
        assert self.module.install_with_tasks() == []

    def test_install_with_tasks_returns_empty_after_failed(self):
        """Test that InstallWithTasks returns [] after a failed installation."""
        self.module.install_with_tasks()
        self.module._on_installation_started()
        self.module._on_installation_failed()
        self.module._on_installation_stopped()
        assert self.module.install_with_tasks() == []

    @patch_dbus_publish_object
    def test_active_installation_task_none(self, publisher):
        """Test ActiveInstallationTask when no task is active."""
        assert self.interface.ActiveInstallationTask == ""

    @patch_dbus_publish_object
    def test_active_installation_task_active(self, publisher):
        """Test ActiveInstallationTask when a task is running."""
        task_paths = self.interface.InstallWithTasks()
        task_proxy = check_task_creation(task_paths[0], publisher, RunInstallationTask)
        task = task_proxy.implementation

        with patch.object(type(task), 'is_running', new_callable=lambda: property(lambda self: True)):
            result = self.interface.ActiveInstallationTask
            assert result == task_paths[0]

    def test_active_installation_task_changed(self):
        """Test ActiveInstallationTaskChanged signal."""
        callback = Mock()
        self.module.active_installation_task_changed.connect(callback)

        self.module.install_with_tasks()

        self.module._on_installation_started()
        callback.assert_called()

        callback.reset_mock()

        self.module._on_installation_stopped()
        callback.assert_called()

    def test_installation_status_default(self):
        """Test that InstallationStatus defaults to NOT_STARTED."""
        assert self.interface.InstallationStatus == InstallationStatus.NOT_STARTED
        assert self.module.installation_status == InstallationStatus.NOT_STARTED

    @patch_dbus_publish_object
    def test_installation_status_running(self, publisher):
        """Test that InstallationStatus changes to RUNNING when started."""
        callback = Mock()
        self.module.installation_status_changed.connect(callback)

        task_paths = self.interface.InstallWithTasks()
        check_task_creation(task_paths[0], publisher, RunInstallationTask)

        self.module._on_installation_started()

        assert self.interface.InstallationStatus == InstallationStatus.RUNNING
        assert self.module.installation_status == InstallationStatus.RUNNING
        callback.assert_called()

    @patch_dbus_publish_object
    def test_installation_status_succeeded(self, publisher):
        """Test that InstallationStatus changes to SUCCEEDED on success."""
        callback = Mock()
        self.module.installation_status_changed.connect(callback)

        task_paths = self.interface.InstallWithTasks()
        check_task_creation(task_paths[0], publisher, RunInstallationTask)

        self.module._on_installation_started()
        callback.reset_mock()

        self.module._on_installation_succeeded()

        assert self.interface.InstallationStatus == InstallationStatus.SUCCEEDED
        assert self.module.installation_status == InstallationStatus.SUCCEEDED
        callback.assert_called()

    @pytest.mark.parametrize(
        "error_type,expected_status,expected_status_callback_count",
        [
            (InstallationErrorDialogType.FATAL_ERROR, InstallationStatus.FAILED, 1),
            (InstallationErrorDialogType.FATAL_ERROR.value, InstallationStatus.FAILED, 1),
            (InstallationErrorDialogType.YES_NO, InstallationStatus.RUNNING, 0),
        ],
    )
    @patch_dbus_publish_object
    def test_installation_status_on_error(
        self, publisher, error_type, expected_status, expected_status_callback_count
    ):
        """Test that InstallationStatus changes to FAILED on fatal error."""
        status_callback = Mock()
        self.module.installation_status_changed.connect(status_callback)

        task_paths = self.interface.InstallWithTasks()
        task_proxy = check_task_creation(task_paths[0], publisher, RunInstallationTask)
        task = task_proxy.implementation

        self.module._on_installation_started()
        status_callback.reset_mock()

        task.error_raised_signal.emit("Something went wrong", error_type)

        assert self.interface.InstallationStatus == expected_status
        assert self.module.installation_status == expected_status
        assert status_callback.call_count == expected_status_callback_count

        assert self.interface.PendingErrorMessage == "Something went wrong"
        assert self.interface.PendingErrorType == error_type

    @patch_dbus_publish_object
    def test_yesno_error_does_not_set_failed(self, publisher):
        """Test that a YES_NO error does not change status to FAILED."""
        task_paths = self.interface.InstallWithTasks()
        task_proxy = check_task_creation(task_paths[0], publisher, RunInstallationTask)
        task = task_proxy.implementation

        self.module._on_installation_started()
        task.error_raised_signal.emit("Non-fatal error", InstallationErrorDialogType.YES_NO)

        assert self.interface.PendingErrorMessage == "Non-fatal error"
        assert self.interface.PendingErrorType == InstallationErrorDialogType.YES_NO
        assert self.module.installation_status == InstallationStatus.RUNNING

    @patch_dbus_publish_object
    def test_installation_failed_via_signal(self, publisher):
        """Test that failed_signal sets status to FAILED."""
        task_paths = self.interface.InstallWithTasks()
        check_task_creation(task_paths[0], publisher, RunInstallationTask)

        self.module._on_installation_started()
        self.module._on_installation_failed()

        assert self.module.installation_status == InstallationStatus.FAILED

    @pytest.mark.parametrize("terminal_status", [
        InstallationStatus.SUCCEEDED,
        InstallationStatus.FAILED,
    ])
    def test_terminal_status_cannot_be_overwritten(self, terminal_status):
        """Test that terminal states (SUCCEEDED, FAILED) cannot be changed."""
        callback = Mock()
        self.module.installation_status_changed.connect(callback)

        self.module._set_installation_status(terminal_status)
        callback.reset_mock()

        self.module._set_installation_status(InstallationStatus.RUNNING)

        assert self.module.installation_status == terminal_status
        callback.assert_not_called()

    @pytest.mark.parametrize("terminal_handler,expected_status", [
        ("_on_installation_succeeded", InstallationStatus.SUCCEEDED),
        ("_on_installation_failed", InstallationStatus.FAILED),
    ])
    def test_stopped_preserves_terminal_status(self, terminal_handler, expected_status):
        """Test that _on_installation_stopped does not change terminal status."""
        self.module._on_installation_started()
        getattr(self.module, terminal_handler)()
        self.module._on_installation_stopped()

        assert self.module.installation_status == expected_status
        assert self.module._installation_task is None

    def test_persist_error_message_writes_file(self):
        """Test that a fatal error is persisted to disk."""
        self.module._on_installation_started()
        self.module._set_pending_error("disk full", InstallationErrorDialogType.FATAL_ERROR)

        assert self._error_file.exists()
        assert self._error_file.read_text() == "disk full"

    def test_non_fatal_error_does_not_persist(self):
        """Test that a YES_NO error is not persisted to disk."""
        self.module._on_installation_started()
        self.module._set_pending_error("ignore this?", InstallationErrorDialogType.YES_NO)

        assert not self._error_file.exists()

    def test_on_error_response_continue_clears_pending(self):
        """Test that continuing past an error clears the pending error."""
        self.module._on_installation_started()
        self.module._set_pending_error("ignore this?", InstallationErrorDialogType.YES_NO)

        callback = Mock()
        self.module.pending_error_changed.connect(callback)

        self.module._on_error_response(True)

        assert self.interface.PendingErrorMessage == ""
        assert self.interface.PendingErrorType == ""
        callback.assert_called()

    def test_on_error_response_abort_preserves_pending(self):
        """Test that aborting does not overwrite the pending error."""
        self.module._on_installation_started()
        self.module._set_pending_error("ignore this?", InstallationErrorDialogType.YES_NO)

        self.module._on_error_response(False)

        assert self.interface.PendingErrorMessage == "ignore this?"

    @patch_dbus_publish_object
    def test_error_response_signal_wired_to_boss(self, publisher):
        """Test that the task's error_response_signal is connected to Boss."""
        task_paths = self.interface.InstallWithTasks()
        task_proxy = check_task_creation(task_paths[0], publisher, RunInstallationTask)
        task = task_proxy.implementation

        self.module._on_installation_started()
        self.module._set_pending_error("ignore?", InstallationErrorDialogType.YES_NO)

        task.error_response_signal.emit(True)

        assert self.interface.PendingErrorMessage == ""

    def test_pending_error_changed_signal_emitted(self):
        """Test that pending_error_changed fires on error."""
        callback = Mock()
        self.module.pending_error_changed.connect(callback)

        self.module._on_installation_started()
        self.module._set_pending_error("boom", InstallationErrorDialogType.FATAL_ERROR)

        callback.assert_called()

    @patch_dbus_publish_object
    def test_thread_failed_callback_emits_when_no_prior_fatal(self, publisher):
        """Test that _thread_failed_callback emits error when no prior fatal."""
        task_paths = self.interface.InstallWithTasks()
        task_proxy = check_task_creation(task_paths[0], publisher, RunInstallationTask)
        task = task_proxy.implementation

        callback = Mock()
        task.error_raised_signal.connect(callback)

        task._thread_failed_callback(None, RuntimeError("unexpected crash"), None)

        callback.assert_called_once()
        msg, error_type = callback.call_args[0]
        assert "unexpected crash" in msg
        assert error_type == InstallationErrorDialogType.FATAL_ERROR

    @patch_dbus_publish_object
    def test_thread_failed_callback_suppressed_after_fatal(self, publisher):
        """Test that _thread_failed_callback skips emit if fatal already emitted."""
        task_paths = self.interface.InstallWithTasks()
        task_proxy = check_task_creation(task_paths[0], publisher, RunInstallationTask)
        task = task_proxy.implementation

        task._fatal_error_already_emitted = True

        callback = Mock()
        task.error_raised_signal.connect(callback)

        task._thread_failed_callback(None, SystemExit(0), None)

        callback.assert_not_called()

    def test_quit(self):
        """Test Quit."""
        assert self.interface.Quit() is None


def test_load_initial_state_with_error_file(anaconda_run_dir):
    """Test that Boss restores FAILED state from a persisted error file."""
    (anaconda_run_dir / Boss.ERROR_FILE_NAME).write_text("disk full")

    boss = Boss()
    interface = BossInterface(boss)

    assert boss.installation_status == InstallationStatus.FAILED
    assert interface.InstallationStatus == InstallationStatus.FAILED
    assert interface.PendingErrorMessage == "disk full"
    assert interface.PendingErrorType == InstallationErrorDialogType.FATAL_ERROR
