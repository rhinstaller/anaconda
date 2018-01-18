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

from threading import Event
from pyanaconda.task.task import Task
from tests.pyanaconda_tests import run_in_glib


TASK_NAME = "TestTask"
TASK_DESCRIPTION = "Short description"
TASK_PROGRESS_STEPS_COUNT = 20


class TaskTestCase(unittest.TestCase):

    def test_progress(self):
        task = TestTask()

        self.assertEqual(task.progress, (0, ""))

        step_num = 2
        step_desc = "reaching the end of the cave"
        task.progress_changed(step_num, step_desc)

        self.assertEqual(task.progress, (step_num, step_desc))
        self.assertEqual(task.progress_changed_out, (step_num, step_desc))

    def test_cancel(self):
        task = TestTask()

        self.assertFalse(task.check_cancel(clear=True))
        # check cancel again if flag clearing is working
        self.assertFalse(task.check_cancel())

        task.cancel()

        self.assertTrue(task.check_cancel(clear=False))
        # cancel flag should be still setup
        self.assertTrue(task.check_cancel())
        # now it should be false because of clear
        self.assertFalse(task.check_cancel())

    def test_run(self):
        task = TestTask()

        self.assertFalse(task.is_running)

        self._run_task(task)

        self.assertFalse(task.running_changed_out)
        self.assertFalse(task.is_running)

    @run_in_glib(1)
    def _run_task(self, task):
        task.run()
        self.assertTrue(task.is_running)
        self.assertTrue(task.running_changed_out)
        task.set_runnable_condition()

    def test_failed_run(self):
        error_message = "nuclear explosion"
        task = FailTestTask(error_message)

        self.assertIsNone(task.error)

        self._run_and_fail_task(task)

        self.assertEqual(task.error, error_message)

    @run_in_glib(1)
    def _run_and_fail_task(self, task):
        task.run()


class TestTask(Task):

    def __init__(self):
        super().__init__()

        self._run_condition = Event()

        self.timeout_reached = False

        self.progress_changed_out = None
        self.running_changed_out = None

        self.progress_changed_signal.connect(self._progress_changed_called)
        self.started_signal.connect(self._started_called)
        self.stopped_signal.connect(self._stopped_called)

    @property
    def name(self):
        return TASK_NAME

    @property
    def description(self):
        return TASK_DESCRIPTION

    @property
    def progress_steps_count(self):
        return TASK_PROGRESS_STEPS_COUNT

    def set_runnable_condition(self):
        self._run_condition.set()

    def runnable(self):
        if not self._run_condition.wait(3):
            self.timeout_reached = True

    def _progress_changed_called(self, step, msg):
        self.progress_changed_out = (step, msg)

    def _started_called(self):
        self.running_changed_out = True

    def _stopped_called(self):
        self.running_changed_out = False


class FailTestTask(TestTask):

    def __init__(self, error_message):
        super().__init__()

        self._input_error_message = error_message
        self.error = None

        self.error_raised_signal.connect(self._error_raised_called)

    def runnable(self):
        self.error_raised(self._input_error_message)

    def _error_raised_called(self, error_description):
        self.error = error_description
