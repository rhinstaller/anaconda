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
from unittest.mock import MagicMock, patch

from pyanaconda.dbus.observer import DBusObjectObserver
from pyanaconda.modules.boss.install_manager.install_manager import InstallManager
from pyanaconda.modules.boss.install_manager.installation_interface import InstallationNotRunning


def _get_proxy(dbus_module_path, task_instance):
    if task_instance is None:
        return dbus_module_path

    return task_instance


@patch("pyanaconda.modules.boss.install_manager.install_manager.DBus.get_proxy", new=_get_proxy)
class InstallManagerTestCase(unittest.TestCase):

    def setUp(self):
        self._running_changed = None
        self._task_changed = None

    def _set_installation_started(self):
        self._running_changed = True

    def _set_installation_stopped(self):
        self._running_changed = False

    def _set_task_changed(self, name):
        self._task_changed = name

    def _connect_manager(self, manager):
        manager.installation_started.connect(self._set_installation_started)
        manager.installation_stopped.connect(self._set_installation_stopped)
        manager.task_changed_signal.connect(self._set_task_changed)

    def test_install_no_tasks(self):
        manager = InstallManager()

        self.assertFalse(manager.installation_running)

        # default values are returned - no exception raised
        name = manager.task_name  # pylint: disable=unused-variable
        description = manager.task_description  # pylint: disable=unused-variable
        steps_sum = manager.progress_steps_count  # pylint: disable=unused-variable
        progress = manager.progress  # pylint: disable=unused-variable
        progressFloat = manager.progress_float  # pylint: disable=unused-variable

        with self.assertRaises(InstallationNotRunning):
            manager.cancel()

    def test_start_installation_with_one_task(self):
        manager = InstallManager()
        self._connect_manager(manager)

        task = TestTask()
        module_mock = TestModule(bus_name="1", task_instance=task)
        module_observer = TestModuleObserver("1", "1", module_mock)

        manager.module_observers = [module_observer]
        manager.start_installation()

        self.assertTrue(manager.installation_running)
        self.assertEqual(manager.task_name, TestTask.NAME)
        self.assertEqual(manager.task_description, TestTask.DESCRIPTION)
        steps_count_sum = TestTask.PROGRESS_STEPS_COUNT
        self.assertEqual(manager.progress_steps_count, steps_count_sum)
        self.assertEqual(manager.progress, TestTask.PROGRESS)
        expected_progress_float = manager.progress[0] / steps_count_sum
        expected_progress_tuple = (expected_progress_float, TestTask.PROGRESS[1])
        self.assertAlmostEqual(manager.progress_float, expected_progress_tuple, delta=0.01)

        # test signals
        self.assertTrue(self._running_changed)
        self.assertEqual(self._task_changed, TestTask.NAME)

        # test task calls
        self.assertTrue(task.is_running)
        self.assertTrue(task.progress_changed_connected)
        self.assertTrue(task.started_connected)
        self.assertTrue(task.stopped_connected)
        self.assertTrue(task.error_raised_connected)

        manager.cancel()

        self.assertTrue(task.cancelled)


class TestModuleObserver(DBusObjectObserver):

    def __init__(self, service_name, object_path, test_module):
        super().__init__(service_name, object_path)
        self._proxy = test_module
        self._is_service_available = True


class TestModule(object):

    def __init__(self, task_instance, bus_name="module"):
        self._task_instance = task_instance
        self._bus_name = bus_name

    @property
    def dbus_name(self):
        """Return instance instead of DBus path."""
        return self._bus_name

    @property
    def AvailableTasks(self):
        return [("TaskName", self._task_instance)]


class TestTask(object):

    NAME = "TestTask"
    DESCRIPTION = "TestTask description"
    PROGRESS_STEPS_COUNT = 2
    PROGRESS = (1, "step 1")

    def __init__(self):
        super().__init__()
        self.progress_changed_connected = False
        self.started_connected = False
        self.stopped_connected = False
        self.error_raised_connected = False

        self.cancelled = False
        self.is_running = False

        self.name = TestTask.NAME
        self.description = TestTask.DESCRIPTION
        self.progress = TestTask.PROGRESS
        self.progress_steps_count = TestTask.PROGRESS_STEPS_COUNT

    @property
    def Name(self):
        return self.name

    @property
    def Description(self):
        return self.description

    @property
    def ProgressStepsCount(self):
        return self.progress_steps_count

    @property
    def Progress(self):
        return self.progress

    @property
    def ProgressChanged(self):
        mock = MagicMock()
        mock.connect = MagicMock()
        mock.connect.side_effect = self._progress_changed_signal
        return mock

    def _progress_changed_signal(self, callback):
        self.progress_changed_connected = True

    @property
    def Started(self):
        mock = MagicMock()
        mock.connect = MagicMock()
        mock.connect.side_effect = self._started_changed_signal
        return mock

    @property
    def Stopped(self):
        mock = MagicMock()
        mock.connect = MagicMock()
        mock.connect.side_effect = self._stopped_changed_signal
        return mock

    def _started_changed_signal(self, callback):
        self.started_connected = True

    def _stopped_changed_signal(self, callback):
        self.stopped_connected = True

    @property
    def ErrorRaised(self):
        mock = MagicMock()
        mock.connect = MagicMock()
        mock.connect.side_effect = self._error_raised_signal
        return mock

    def _error_raised_signal(self, callback):
        self.error_raised_connected = True

    @property
    def IsCancelable(self):
        return True

    def Cancel(self):
        self.cancelled = True

    @property
    def IsRunning(self):
        return self.is_running

    def Start(self):
        self.is_running = True
