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

from pyanaconda.installation_tasks import Task, TaskQueue


class InstallTasksTestCase(unittest.TestCase):

    def setUp(self):
        self._test_variable1 = 0
        self._test_variable2 = 0
        self._test_variable3 = 0
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

    def _increment_var3(self):
        self._test_variable3 += 1

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
        assert task.parent is None
        assert task.elapsed_time is None
        # check initial state of the testing variables
        assert self._test_variable4 is None
        assert self._test_variable5 is None
        assert self._test_variable6 is None
        # check task state
        assert not task.done
        assert not task.running
        # connect callbacks
        task.started.connect(self._set_var_4)
        task.completed.connect(self._set_var_6)
        # check if the task is executed correctly
        task.start()
        assert task.done
        assert not task.running
        assert self._test_variable5 == "anaconda"
        assert self._test_variable4 is task
        assert self._test_variable6 is task
        # it should be possible to execute the task only once
        task.start()
        assert task.done
        assert not task.running
        assert task.elapsed_time is not None
        assert self._test_variable5 == "anaconda"
        assert self._test_variable4 is task
        assert self._test_variable6 is task

    def test_task_kwargs(self):
        """Check that works correctly with kwargs."""
        def custom_function(arg1, foo=None):
            self._set_var_5((arg1, foo))

        task = Task("foo", custom_function, task_args=("anaconda",), task_kwargs={"foo": "bar"})
        assert task.name == "foo"
        assert task.summary == "Task: foo"
        assert task.parent is None
        assert task.elapsed_time is None
        # check initial state of the testing variables
        assert self._test_variable4 is None
        assert self._test_variable5 is None
        assert self._test_variable6 is None
        # check task state
        assert not task.done
        assert not task.running
        # connect callbacks
        task.started.connect(self._set_var_4)
        task.completed.connect(self._set_var_6)
        # check if the task is executed correctly
        task.start()
        assert task.done
        assert not task.running
        assert self._test_variable5 == ("anaconda", "bar")
        assert self._test_variable4 is task
        assert self._test_variable6 is task
        # it should be possible to execute the task only once
        task.start()
        assert task.done
        assert not task.running
        assert task.elapsed_time is not None
        assert self._test_variable5 == ("anaconda", "bar")
        assert self._test_variable4 is task
        assert self._test_variable6 is task

    def test_task_no_args(self):
        """Check if task with no arguments works correctly."""
        task = Task("foo", self._increment_var1)
        assert task.name == "foo"
        assert task.summary == "Task: foo"
        assert task.parent is None
        assert task.elapsed_time is None
        # check initial state of the testing variables
        assert self._test_variable1 == 0
        assert self._test_variable4 is None
        assert self._test_variable5 is None
        assert self._test_variable6 is None
        # check task state
        assert not task.done
        assert not task.running
        # connect callbacks
        task.started.connect(self._set_var_4)
        task.completed.connect(self._set_var_6)
        # check if the task is executed correctly
        task.start()
        assert task.done
        assert not task.running
        assert self._test_variable1 == 1
        assert self._test_variable4 is task
        assert self._test_variable6 is task
        # it should be possible to execute the task only once
        task.start()
        assert task.done
        assert not task.running
        assert task.elapsed_time is not None
        assert self._test_variable1 == 1
        assert self._test_variable4 is task
        assert self._test_variable6 is task

    def test_task_subclass_light(self):
        """Check if a Task subclass with custom run_task() method works."""
        class CustomPayloadTask(Task):
            def __init__(self, name):
                super(CustomPayloadTask, self).__init__(name, task=None, task_args=[])
                self.var1 = 0
                self.var2 = None

            # We define a custom run_task method and override it with our own "payload",
            # as this is more lightweight than overriding the full start() method and
            # we get all the locking and signal triggering for free.
            def run_task(self):
                self.var1 += 1
                self.var1 += 1
                self.var2 = "anaconda"

        task = CustomPayloadTask("custom payload task")
        # connect callbacks
        task.started.connect(self._set_var_4)
        task.completed.connect(self._set_var_6)
        # verify initial state
        assert task.var1 == 0
        assert task.var2 is None
        # run the custom task
        task.start()
        # verify that the custom payload was run
        assert task.var1 == 2
        assert task.var2 == "anaconda"
        # verify that the started/completed signals were triggered
        assert self._test_variable4 is task
        assert self._test_variable6 is task

    def test_task_subclass_heavy(self):
        """Check if a Task subclass with custom start() method works."""
        class CustomStartTask(Task):
            def __init__(self, name):
                super(CustomStartTask, self).__init__(name, task=None, task_args=[])
                self.var1 = 0
                self.var2 = None

            # We define a custom start method and override it with our own "payload".
            # This is more "heavy" than overriding just run_task() method and
            # we generally need to implement all the locking and signal triggering.
            # On the other hand it can potentially provide more fine-grained control
            # over how the task is processed.
            def start(self):
                self.var1 += 1
                self.var1 += 1
                self.var2 = "anaconda"

        task = CustomStartTask("custom payload task")
        # connect callbacks
        task.started.connect(self._set_var_4)
        task.completed.connect(self._set_var_6)
        # verify initial state
        assert task.var1 == 0
        assert task.var2 is None
        # run the custom task
        task.start()
        # verify that the custom payload was run
        assert task.var1 == 2
        assert task.var2 == "anaconda"
        # verify that the started/completed signals were *not* triggered
        # (as they are not called by the reimplemented start() method)
        assert self._test_variable4 is None
        assert self._test_variable6 is None

    def test_task_subclass_kwargs(self):
        """Check if kwarg passing works for Task subclasses."""

        class TestTask(Task):
            def __init__(self, name, task, task_args, custom_option="foo"):
                super(TestTask, self).__init__(name, task, task_args)
                self._custom_option = custom_option

            @property
            def custom_option(self):
                return self._custom_option

        # check that the kwarg has been propagated correctly
        task = TestTask("foo", self._set_var_5, ("anaconda",))
        assert task.custom_option == "foo"
        # also check that the task still works as expected
        task.start()
        assert self._test_variable5 == "anaconda"

    def test_empty_task_queue(self):
        """Check that an empty task queue works correctly."""
        # first check if empty task queue works correctly
        task_queue = TaskQueue("foo", status_message="foo status message")
        assert task_queue.name == "foo"
        assert task_queue.status_message == "foo status message"
        assert task_queue.task_count == 0
        assert task_queue.queue_count == 0
        assert task_queue.current_task_number is None
        assert task_queue.current_queue_number is None
        assert task_queue.progress == 0.0
        assert not task_queue.running
        assert not task_queue.done
        assert len(task_queue.summary) > 0
        # connect started/completed callbacks

        # these should be triggered
        task_queue.started.connect(self._set_var_4)
        task_queue.completed.connect(self._set_var_5)
        # these should not
        should_not_run = lambda x: self._set_var_6("anaconda")
        task_queue.task_started.connect(should_not_run)
        task_queue.task_completed.connect(should_not_run)
        task_queue.queue_started.connect(should_not_run)
        task_queue.queue_completed.connect(should_not_run)

        # it should be possible to start an empty task queue
        task_queue.start()
        # check state after the run
        assert not task_queue.running
        assert task_queue.done
        assert task_queue.current_queue_number is None
        assert task_queue.current_task_number is None
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
        # create some groups
        group1 = TaskQueue(name="group1", status_message="processing group1")
        group1.append(Task("increment var 1", self._increment_var1))
        group2 = TaskQueue(name="group2", status_message="processing group2")
        group2.append(Task("increment var 2", self._increment_var2))
        group2.append(Task("increment var 2", self._increment_var2))
        group3 = TaskQueue(name="group3", status_message="processing group3 (empty)")
        # create the top level queue
        queue1 = TaskQueue(name="queue1")
        # connect to it's top-level callbacks
        queue1.task_started.connect(task_started_cb)
        queue1.task_completed.connect(task_completed_cb)
        queue1.queue_started.connect(queue_started_cb)
        queue1.queue_completed.connect(queue_completed_cb)
        # add the nested queues
        queue1.append(group1)
        queue1.append(group2)
        queue1.append(group3)  # an empty group should be also processed correctly
        # and one top-level task
        queue1.append(Task("increment var 1", self._increment_var1))
        # check that the groups have been added correctly
        assert len(queue1) == 4
        assert queue1[0].name == "group1"
        assert len(queue1[0]) == 1
        assert queue1[1].name == "group2"
        assert len(queue1[1]) == 2
        assert queue1[2].name == "group3"
        assert len(queue1[2]) == 0
        assert queue1.queue_count == 3
        assert queue1.task_count == 4
        # summary is generated recursively
        assert bool(queue1.summary)
        # start the queue
        queue1.start()
        # check if the tasks were correctly executed
        assert self._test_variable1 == 2
        assert self._test_variable2 == 2
        assert self._test_variable3 == 0
        # check that the task & queue signals were triggered correctly
        assert self._task_started_count == 4
        assert self._task_completed_count == 4
        assert self._queue_started_count == 3
        assert self._queue_completed_count == 3
        # check queue state after execution
        assert not queue1.running
        assert queue1.done
        assert queue1.current_task_number is None
        assert queue1.current_queue_number is None
        # create another queue and add some task groups and tasks to it
        group4 = TaskQueue(name="group 4", status_message="processing group4")
        group4.append(Task("increment var 1", self._increment_var1))
        group5 = TaskQueue(name="group 5", status_message="processing group5")
        group5.append(Task("increment var 3", self._increment_var3))
        queue2 = TaskQueue(name="queue2")
        queue2.append(group4)
        queue2.append(group5)
        # start the second queue
        queue2.start()
        # check the tasks also properly executed
        assert self._test_variable1 == 3
        assert self._test_variable2 == 2
        assert self._test_variable3 == 1
