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
from time import sleep
from mock import Mock, call

from pyanaconda.modules.boss.install_manager.installation import SystemInstallationTask
from pyanaconda.modules.common.task import Task, TaskInterface, publish_task, sync_run_task, \
    async_run_task
from tests.nosetests.pyanaconda_tests import run_in_glib


class TaskFailedException(Exception):
    """Task has failed."""
    pass


class TaskInterfaceTestCase(unittest.TestCase):
    """Test base classes for module tasks."""

    TIMEOUT = 3

    def setUp(self):
        self.task = None
        self.task_interface = None
        self.progress_changed_callback = Mock()
        self.task_life_cycle = []

    def _set_up_task(self, task):
        self.task = task
        self.task_interface = TaskInterface(task)

        # Connect callbacks.
        # pylint: disable=no-member
        self.task_interface.ProgressChanged.connect(self.progress_changed_callback)
        # pylint: disable=no-member
        self.task_interface.Started.connect(lambda: self.task_life_cycle.append("started"))
        # pylint: disable=no-member
        self.task_interface.Stopped.connect(lambda: self.task_life_cycle.append("stopped"))
        # pylint: disable=no-member
        self.task_interface.Failed.connect(lambda: self.task_life_cycle.append("failed"))

        # Check the initial state.
        self.assertEqual(self.task_interface.Progress, (0, ""))
        self.assertEqual(self.task_life_cycle, [])

    def _check_steps(self, steps=1):
        self.assertEqual(self.task_interface.Steps, steps)

    def _check_task_signals(self, started=True, failed=False, stopped=True):
        # Check the life cycle of the task.
        expected = []

        if started:
            expected.append("started")
        if failed:
            expected.append("failed")
        if stopped:
            expected.append("stopped")

        self.assertListEqual(expected, self.task_life_cycle)

    def _check_progress_changed(self, step, msg, changed=True):
        # Check the Progress property.
        self.assertEqual(self.task_interface.Progress, (step, msg))

        # Check the ProgressChanged signal.
        if changed:
            self.progress_changed_callback.assert_called_once_with(step, msg)
            self.progress_changed_callback.reset_mock()
        else:
            self.progress_changed_callback.assert_not_called()

    class SimpleTask(Task):

        @property
        def name(self):
            return "Simple Task"

        def run(self):
            pass

    def properties_test(self):
        """Test task properties."""
        self._set_up_task(self.SimpleTask())
        self.assertEqual(self.task_interface.Name, "Simple Task")
        self.assertEqual(self.task_interface.IsRunning, False)
        self.assertEqual(self.task_interface.Steps, 1)
        self.assertEqual(self.task_interface.Progress, (0, ""))

    def publish_test(self):
        """Test task publishing."""
        TaskInterface._task_counter = 1
        message_bus = Mock()

        object_path = publish_task(message_bus, ("A", "B", "C"), self.SimpleTask())
        self.assertEqual("/A/B/C/Tasks/1", object_path)
        message_bus.publish_object.called_once()
        message_bus.reset_mock()

        object_path = publish_task(message_bus, ("A", "B", "C"), self.SimpleTask())
        self.assertEqual("/A/B/C/Tasks/2", object_path)
        message_bus.publish_object.called_once()
        message_bus.reset_mock()

        object_path = publish_task(message_bus, ("A", "B", "C"), self.SimpleTask())
        self.assertEqual("/A/B/C/Tasks/3", object_path)
        message_bus.publish_object.called_once()
        message_bus.reset_mock()

    def simple_progress_reporting_test(self):
        """Test simple progress reporting."""
        self._set_up_task(self.SimpleTask())

        # Step 1
        self.task.report_progress("A", step_size=1)
        self._check_progress_changed(1, "A")

        self.task.report_progress("B")
        self._check_progress_changed(1, "B")

        self.task.report_progress("C")
        self._check_progress_changed(1, "C")

        self.task.report_progress("D")
        self._check_progress_changed(1, "D")

        self.task.report_progress("E")
        self._check_progress_changed(1, "E")

        self.task.report_progress("F")
        self._check_progress_changed(1, "F")

    def invalid_progress_reporting_test(self):
        """Test invalid progress reporting."""
        self._set_up_task(self.SimpleTask())

        # Step 1
        self.task.report_progress("A", step_size=1)
        self._check_progress_changed(1, "A")

        # Invalid step size:

        # Cannot go to step 2
        self.task.report_progress("B", step_size=1)
        self._check_progress_changed(1, "B")

        # Cannot go to step 11
        self.task.report_progress("C", step_size=10)
        self._check_progress_changed(1, "C")

        # Cannot go to step 0
        self.task.report_progress("D", step_size=-1)
        self._check_progress_changed(1, "D")

        # Invalid step number:

        # Cannot go to step 2
        self.task.report_progress("E", step_number=2)
        self._check_progress_changed(1, "E")

        # Cannot go to step 11
        self.task.report_progress("F", step_number=11)
        self._check_progress_changed(1, "F")

        # Cannot do to step 0
        self.task.report_progress("G", step_number=0)
        self._check_progress_changed(1, "G")

    def thread_name_test(self):
        """Test the thread name of the task."""
        self.SimpleTask._thread_counter = 0

        task = self.SimpleTask()
        self.assertEqual(task._thread_name, "AnaTaskThread-SimpleTask-1")

        task = self.SimpleTask()
        self.assertEqual(task._thread_name, "AnaTaskThread-SimpleTask-2")

        task = self.SimpleTask()
        self.assertEqual(task._thread_name, "AnaTaskThread-SimpleTask-3")

    class MultiStepTask(Task):

        @property
        def name(self):
            return "Multi Step Task"

        @property
        def steps(self):
            return 20

        def run(self):
            pass

    def multistep_progress_reporting_test(self):
        """Test multistep progress reporting."""
        self._set_up_task(self.MultiStepTask())
        self._check_steps(20)

        # Step 1
        self.task.report_progress("A", step_size=1)
        self._check_progress_changed(1, "A")

        # Step 2
        self.task.report_progress("B", step_size=1)
        self._check_progress_changed(2, "B")

        # Step 3
        self.task.report_progress("C", step_size=1)
        self._check_progress_changed(3, "C")

        # Step 10
        self.task.report_progress("D", step_size=7)
        self._check_progress_changed(10, "D")

        # Step 11
        self.task.report_progress("E", step_number=11)
        self._check_progress_changed(11, "E")

        # Step 15
        self.task.report_progress("F", step_number=15)
        self._check_progress_changed(15, "F")

        # Step 20
        self.task.report_progress("G", step_number=20)
        self._check_progress_changed(20, "G")

    class RunningTask(Task):

        @property
        def name(self):
            return "Running Task"

        def run(self):
            if not self.is_running:
                raise AssertionError("The is_running property should be True.")

            if self.check_cancel():
                raise AssertionError("The cancel flag should be False.")

    def simple_run_test(self):
        """Run a simple task."""
        self._set_up_task(self.RunningTask())
        self._run_task()
        self._finish_task()
        self._check_progress_changed(1, "Running Task")

    @run_in_glib(TIMEOUT)
    def _run_task(self):
        """Start the task."""
        self.task_interface.Start()

        while self.task_interface.IsRunning:
            sleep(1)

    def _finish_task(self):
        """Finish a task."""
        self.task_interface.Finish()
        self._check_task_signals()

    class FailingTask(Task):

        @property
        def name(self):
            return "Failing Task"

        def run(self):
            raise TaskFailedException()

    def failed_run_test(self):
        """Run a failing task."""
        self._set_up_task(self.FailingTask())
        self._run_task()
        self._finish_failed_task()
        self._check_progress_changed(1, "Failing Task")

    def _finish_failed_task(self):
        """Finish a task."""
        with self.assertRaises(TaskFailedException):
            self.task_interface.Finish()

        self._check_task_signals(failed=True)

    class CanceledTask(Task):

        @property
        def name(self):
            return "Canceled Task"

        def run(self):

            for _time in range(0, 3):
                # Cancel the task.
                if self.check_cancel():
                    return

                sleep(1)

            # Or raise the timeout error.
            raise TimeoutError()

    def canceled_run_test(self):
        """Run a canceled task."""
        self._set_up_task(self.CanceledTask())
        self._run_and_cancel_task()
        self._finish_task()
        self._check_progress_changed(1, "Canceled Task")

    @run_in_glib(TIMEOUT)
    def _run_and_cancel_task(self):
        """Cancel a task."""
        self.task_interface.Start()
        self.task_interface.Cancel()

        while self.task_interface.IsRunning:
            sleep(1)

    def sync_run_test(self):
        """Run a task synchronously."""
        self._set_up_task(self.FailingTask())
        self._sync_run_test()

    @run_in_glib(TIMEOUT)
    def _sync_run_test(self):
        with self.assertRaises(TaskFailedException):
            sync_run_task(self.task_interface)

    def async_run_test(self):
        """Run a task asynchronously."""
        self._set_up_task(self.FailingTask())
        self._async_run_test()

    @run_in_glib(TIMEOUT)
    def _async_run_test(self):
        async_run_task(self.task_interface, self._async_callback)

    def _async_callback(self, task_proxy):
        with self.assertRaises(TaskFailedException):
            task_proxy.Finish()

    def install_with_no_tasks_test(self):
        """Install with no tasks."""
        self._set_up_task(SystemInstallationTask([]))
        self._check_steps(0)
        self._run_task()
        self._finish_task()

    def install_with_one_task_test(self):
        """Install with one task."""
        self._set_up_task(
            SystemInstallationTask([
                TaskInterface(self.SimpleTask())
            ])
        )
        self._check_steps(1)
        self._run_task()
        self._finish_task()
        self._check_progress_changed(1, "Simple Task")

    def install_with_failing_task_test(self):
        """Install with one failing task."""
        self._set_up_task(
            SystemInstallationTask([
                TaskInterface(self.FailingTask())
            ])
        )
        self._check_steps(1)
        self._run_task()
        self._finish_failed_task()
        self._check_progress_changed(1, "Failing Task")

    def install_with_canceled_task_test(self):
        """Install with one canceled task."""
        self._set_up_task(
            SystemInstallationTask([
                TaskInterface(self.CanceledTask())
            ])
        )
        self._check_steps(1)
        self._run_and_cancel_task()
        self._finish_task()
        self._check_progress_changed(1, "Canceled Task")

    class InstallationTaskA(Task):

        @property
        def name(self):
            return "Install A"

        def run(self):
            pass

    class InstallationTaskB(Task):

        @property
        def name(self):
            return "Install B"

        def run(self):
            pass

    class InstallationTaskC(Task):

        @property
        def name(self):
            return "Install C"

        def run(self):
            pass

    def install_with_three_tasks_test(self):
        """Install with three tasks."""
        self._set_up_task(
            SystemInstallationTask([
                TaskInterface(self.InstallationTaskA()),
                TaskInterface(self.InstallationTaskB()),
                TaskInterface(self.InstallationTaskC())
            ])
        )
        self._check_steps(3)
        self._run_task()
        self._finish_task()

        self.progress_changed_callback.assert_has_calls([
            call(1, "Install A"),
            call(2, "Install B"),
            call(3, "Install C")
        ])

    class IncompleteTask(Task):

        @property
        def steps(self):
            return 5

        @property
        def name(self):
            return "Install incomplete task"

        def run(self):
            pass

    def install_with_incomplete_tasks_test(self):
        """Install with incomplete tasks."""
        self._set_up_task(
            SystemInstallationTask([
                TaskInterface(self.InstallationTaskA()),
                TaskInterface(self.IncompleteTask()),
                TaskInterface(self.InstallationTaskB()),
                TaskInterface(self.InstallationTaskC())
            ])
        )
        self._check_steps(8)
        self._run_task()
        self._finish_task()

        self.progress_changed_callback.assert_has_calls([
            call(1, "Install A"),
            call(2, "Install incomplete task"),  # plus 5
            call(7, "Install B"),
            call(8, "Install C")
        ])
