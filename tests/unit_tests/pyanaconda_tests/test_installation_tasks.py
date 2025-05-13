#
# Martin Kolman <mkolman@redhat.com>
#
# Copyright 2016 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.  Any Red Hat
# trademarks that are incorporated in the source code or documentation are not
# subject to the GNU General Public License and may only be used or replicated
# with the express permission of Red Hat, Inc.
#
import unittest
from textwrap import dedent

from pyanaconda.installation_tasks import Task, TaskQueue


class InstallTasksTestCase(unittest.TestCase):

    def setUp(self):
        self._test_variable1 = 0
        self._test_variable2 = 0
        self._test_variable4 = None
        self._test_variable5 = None
        self._test_variable6 = None
        self._task_started_count = 0
        self._task_completed_count = 0
        self._queue_started_count = 0
        self._queue_completed_count = 0

    def _increment_var1(self):
        self._test_variable1 += 1

    def _increment_var2(self):
        self._test_variable2 += 1

    def _set_var_4(self, value):
        self._test_variable4 = value

    def _set_var_5(self, value):
        self._test_variable5 = value

    def _set_var_6(self, value):
        self._test_variable6 = value

    def test_task(self):
        """Check that task works correctly."""
        task = Task("foo", self._set_var_5, ("anaconda",))
        assert task.name == "foo"
        assert task.summary == "Task: foo"
        assert task._parent is None
        assert task.elapsed_time is None

        # check initial state of the testing variables
        assert self._test_variable4 is None
        assert self._test_variable5 is None
        assert self._test_variable6 is None

        # connect callbacks
        task.started.connect(self._set_var_4)
        task.completed.connect(self._set_var_6)

        # check if the task is executed correctly
        task.start()

        assert self._test_variable5 == "anaconda"
        assert self._test_variable4 is task
        assert self._test_variable6 is task

    def test_task_with_args_and_kwargs(self):
        """Check that works correctly with args and kwargs."""
        def custom_function(arg1, foo=None):
            self._set_var_5((arg1, foo))

        task = Task("foo", custom_function, task_args=("anaconda",), task_kwargs={"foo": "bar"})
        assert task.name == "foo"
        assert task.summary == "Task: foo"
        assert task._parent is None
        assert task.elapsed_time is None

        # check initial state of the testing variables
        assert self._test_variable4 is None
        assert self._test_variable5 is None
        assert self._test_variable6 is None

        # connect callbacks
        task.started.connect(self._set_var_4)
        task.completed.connect(self._set_var_6)

        # check if the task is executed correctly
        task.start()

        assert self._test_variable5 == ("anaconda", "bar")
        assert self._test_variable4 is task
        assert self._test_variable6 is task

    def test_task_with_no_args(self):
        """Check if task with no arguments works correctly."""
        task = Task("foo", self._increment_var1)
        assert task.name == "foo"
        assert task.summary == "Task: foo"
        assert task._parent is None
        assert task.elapsed_time is None

        # check initial state of the testing variables
        assert self._test_variable1 == 0
        assert self._test_variable4 is None
        assert self._test_variable5 is None
        assert self._test_variable6 is None

        # connect callbacks
        task.started.connect(self._set_var_4)
        task.completed.connect(self._set_var_6)

        # check if the task is executed correctly
        task.start()

        assert self._test_variable1 == 1
        assert self._test_variable4 is task
        assert self._test_variable6 is task

    def test_empty_task_queue(self):
        """Check that an empty task queue works correctly."""
        # first check if empty task queue works correctly
        task_queue = TaskQueue("foo", status_message="foo status message",
                               task_category="foo category")
        assert task_queue.name == "foo"
        assert task_queue.status_message == "foo status message"
        assert task_queue.task_category == "foo category"
        assert task_queue.task_count == 0
        assert task_queue.queue_count == 0
        assert task_queue.summary == dedent("""
            Top-level task queue: foo
            Number of task queues: 0
            Number of tasks: 0
            Task & task group listing:
        """).strip()

        # connect started/completed callbacks
        task_queue.started.connect(self._set_var_4)
        task_queue.completed.connect(self._set_var_5)

        # it should be possible to start an empty task queue
        task_queue.start()

        # check state after the run
        assert task_queue.task_count == 0
        assert task_queue.queue_count == 0

        # started/completed signals should still be triggered, even
        # if the queue is empty
        assert self._test_variable4 is task_queue
        assert self._test_variable5 is task_queue

        # the nested queue/task signals should not be triggered if
        # the queue is empty
        assert self._test_variable6 is None

    def test_task_queue_processing(self):
        """Check that task queue processing works correctly."""
        # callback counting functions
        def task_started_cb(*args):
            self._task_started_count += 1

        def task_completed_cb(*args):
            self._task_completed_count += 1

        def queue_started_cb(*args):
            self._queue_started_count += 1

        def queue_completed_cb(*args):
            self._queue_completed_count += 1

        # verify initial content of callback counters
        assert self._task_started_count == 0
        assert self._task_completed_count == 0
        assert self._queue_started_count == 0
        assert self._queue_completed_count == 0

        # create the group 1
        group1 = TaskQueue(name="group1", status_message="processing group1",
                           task_category="group1 category")
        task1 = Task("increment var 1", self._increment_var1)
        group1.append(task1)

        # create the group 2
        group2 = TaskQueue(name="group2", status_message="processing group2",
                           task_category="group2 category")
        task2a = Task("increment var 2", self._increment_var2)
        group2.append(task2a)

        task2b = Task("increment var 2", self._increment_var2)
        group2.append(task2b)

        # create the group 3
        group3 = TaskQueue(name="group3", status_message="processing group3 (empty)",
                           task_category="group3 category")

        # create the top level queue
        queue1 = TaskQueue(name="queue1")
        queue1.task_started.connect(task_started_cb)
        queue1.task_completed.connect(task_completed_cb)
        queue1.queue_started.connect(queue_started_cb)
        queue1.queue_completed.connect(queue_completed_cb)

        # add the nested queues
        queue1.append(group1)
        queue1.append(group2)
        queue1.append(group3)  # an empty group should be also processed correctly

        # and one top-level task
        task4 = Task("increment var 1", self._increment_var1)
        queue1.append(task4)

        # check that the groups have been added correctly
        assert queue1.items == [
            group1,
            group2,
            group3,
            task4,
        ]
        assert queue1.nested_items == [
            group1,
            task1,
            group2,
            task2a,
            task2b,
            group3,
            task4,
        ]
        assert queue1.queue_count == 3
        assert queue1.task_count == 4
        assert queue1.summary == dedent("""
        Top-level task queue: queue1
        Number of task queues: 3
        Number of tasks: 4
        Task & task group listing:
         Task queue: group1
          Task: increment var 1
         Task queue: group2
          Task: increment var 2
          Task: increment var 2
         Task queue: group3
         Task: increment var 1
        """).strip()

        # start the queue
        queue1.start()

        # check if the tasks were correctly executed
        assert self._test_variable1 == 2
        assert self._test_variable2 == 2

        # check that the task & queue signals were triggered correctly
        assert self._task_started_count == 4
        assert self._task_completed_count == 4
        assert self._queue_started_count == 3
        assert self._queue_completed_count == 3
