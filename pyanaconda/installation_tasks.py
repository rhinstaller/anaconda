# installation_tasks.py
# Container classes for running of installation tasks.
#
# Copyright (C) 2016  Red Hat, Inc.
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
from threading import RLock

from dasbus.error import DBusError
from pyanaconda.core.signal import Signal
from pyanaconda.core.util import synchronized
from pyanaconda.errors import errorHandler, ERROR_RAISE
from pyanaconda.modules.common.task import sync_run_task
import time

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.progress import progress_message

log = get_module_logger(__name__)


class BaseTask(object):
    """A base class for Task and TaskQueue.

    It holds shared methods, properties and signals.
    """

    def __init__(self, name):
        self._name = name
        self._done = False
        self._running = False
        self._lock = RLock()
        self._parent = None
        self._start_timestamp = None
        self._done_timestamp = None
        self.started = Signal()
        self.completed = Signal()

    @property
    def name(self):
        """Task name.

        :returns: task name
        :rtype: str
        """
        return self._name

    @property
    @synchronized
    def running(self):
        """Reports if the task is currently running.

        :reports: if the task is running
        :rtype: bool
        """
        return self._running

    @property
    @synchronized
    def elapsed_time(self):
        """Elapsed time since the task has been started in milliseconds."""
        if self._start_timestamp:
            if self._done_timestamp:
                return self._done_timestamp - self._start_timestamp
            else:
                return time.time() - self._start_timestamp
        else:
            return None

    @property
    @synchronized
    def done(self):
        """Reports if the task has finished processing.

        :reports: if the task is done
        :rtype: bool
        """
        return self._done

    @property
    def summary(self):
        """A description of the task - to be overridden by subclasses."""
        raise NotImplementedError

    def start(self):
        """Start the task - to be overridden by sub-classes."""
        raise NotImplementedError


class TaskQueue(BaseTask):
    """TaskQueue represents a queue of TaskQueues or Tasks.

    TaskQueues and Tasks can be mixed in a single TaskQueue.
    """

    def __init__(self, name, status_message=None):
        super().__init__(name=name)
        self._status_message = status_message
        self._current_task_number = None
        self._current_queue_number = None
        # the list backing this TaskQueue instance
        self._list = []
        # triggered if a TaskQueue contained in this one was started/completed
        self.queue_started = Signal()
        self.queue_completed = Signal()
        # triggered when a task is started
        self.task_started = Signal()
        self.task_completed = Signal()

        # connect to the task & queue started signals for
        # progress reporting purposes
        self.queue_started.connect(self._queue_started_cb)
        self.task_started.connect(self._task_started_cb)

    @synchronized
    def _queue_started_cb(self, *args):
        self._current_queue_number += 1

    @synchronized
    def _task_started_cb(self, *args):
        self._current_task_number += 1

    @property
    def status_message(self):
        """A status message describing the Queue is trying to achieve.

        Eq. "Converting all foo into bar."

        The current main usecase is to set the ProgressHub status message when
        a TaskQueue is started.

        :returns: a status message
        :rtype: str
        """
        return self._status_message

    @property
    @synchronized
    def queue_count(self):
        """Returns number of TaskQueues contained in this and all nested TaskQueues.

        :returns: number of queues
        :rtype: int
        """
        queue_count = 0
        for item in self:
            # count only queues
            if isinstance(item, TaskQueue):
                # count the queue itself
                queue_count += 1
                # and its contents
                queue_count += item.queue_count
        return queue_count

    @property
    @synchronized
    def task_count(self):
        """Returns number of tasks contained in this and all nested TaskQueues.

        :returns: number of tasks
        :rtype: int
        """
        task_count = 0
        for item in self:
            if isinstance(item, Task):
                # count tasks
                task_count += 1
            elif isinstance(item, TaskQueue):
                # count tasks in nested queues
                task_count += item.task_count
        return task_count

    @property
    @synchronized
    def current_task_number(self):
        """Number of the currently running task (if any).

        :returns: number of the currently running task (if any)
        :rtype: int or None if no task is currently running
        """
        return self._current_task_number

    @property
    @synchronized
    def current_queue_number(self):
        """Number of the currently running task queue (if any).

        :returns: number of the currently running task queue (if any)
        :rtype: int or None if no task queue is currently running
        """
        return self._current_queue_number

    @property
    @synchronized
    def progress(self):
        """Task queue processing progress.

        The progress is reported as a floating point number from 0.0 to 1.0.
        :returns: task queue processing progress
        :rtype: float
        """
        if self.current_task_number:
            return self.task_count / self.current_task_number
        else:
            return 0.0

    @property
    @synchronized
    def summary(self):
        """Return a multi-line summary of the contents of the task queue.

        :returns: summary of task queue contents
        :rtype: str
        """
        if self.parent is None:
            message = "Top-level task queue: %s\n" % self.name
            # this is the top-level queue, so add some "global" stats
            message += "Number of task queues: %d\n" % self.queue_count
            message += "Number of tasks: %d\n" % self.task_count
            message += "Task & task group listing:\n"
        else:
            message = "Task queue: %s\n" % self.name
        for item in self:
            for line in item.summary.splitlines():
                message += " %s\n" % line
        # remove trailing newlines from the top level message
        if self.parent is None and message[-1] == "\n":
            message = message.rstrip("\n")
        return message

    @property
    @synchronized
    def parent(self):
        """The parent task queue of this task queue (if any).

        :returns: parent of this task queue (if any)
        :rtype: TaskQueue instance or None
        """
        return self._parent

    @parent.setter
    @synchronized
    def parent(self, parent_item):
        # check if a parent is already set
        if self._parent is not None:
            # disconnect from the previous parent first
            self.started.disconnect(self._parent.queue_started.emit)
            self.completed.disconnect(self._parent.queue_completed.emit)
            self.queue_started.disconnect(self._parent.queue_started.emit)
            self.queue_completed.disconnect(self._parent.queue_completed.emit)
            self.task_started.disconnect(self._parent.task_started.emit)
            self.task_completed.disconnect(self._parent.task_completed.emit)
        # set the parent
        self._parent = parent_item
        # Connect own signals "up" to the parent,
        # so that it is possible to monitor how all nested TaskQueues and Tasks
        # are running from the top-level element.

        # connect own start/completion signal to parents queue start/completion signal
        self.started.connect(self._parent.queue_started.emit)
        self.completed.connect(self._parent.queue_completed.emit)

        # propagate start/completion signals from nested queues/tasks
        self.queue_started.connect(self._parent.queue_started.emit)
        self.queue_completed.connect(self._parent.queue_completed.emit)
        self.task_started.connect(self._parent.task_started.emit)
        self.task_completed.connect(self._parent.task_completed.emit)

    def start(self):
        """Start processing of the task queue."""
        do_start = False
        with self._lock:
            # the task queue can only be started once
            if self.running or self.done:
                if self.running:
                    # attempt to start a task that is already running
                    log.error("Can't start task queue %s - already running.")
                else:
                    # attempt to start a task that an already finished task
                    log.error("Can't start task queue %s - already done.")
            else:
                do_start = True
                self._running = True
                if self.task_count:
                    # only set the initial task number if we have some tasks
                    self._current_task_number = 0
                    self._current_queue_number = 0
                else:
                    log.warning("Attempting to start an empty task queue (%s).", self.name)

        if do_start:
            # go over all task groups and their tasks in order
            self.started.emit(self)
            if len(self) == 0:
                log.warning("The task group %s is empty.", self.name)
            for item in self:
                # start the item (TaskQueue/Task)
                item.start()

            # we are done, set the task queue state accordingly
            with self._lock:
                self._running = False
                self._done = True
                # also set the current task variables accordingly as we no longer process a task
                self._current_task_number = None
                self._current_queue_number = None

            # trigger the "completed" signals
            self.completed.emit(self)

    # implement the Python list "interface" and make sure parent is always
    # set to a correct value
    @synchronized
    def append(self, item):
        item.parent = self
        self._list.append(item)

    @synchronized
    def append_dbus_tasks(self, service_id, dbus_tasks):
        """Append DBus Tasks from a module to the TaskQueue.

        :param service_id: DBusServiceIdentifier instance corresponding to an Anaconda DBus module
        :param dbus_tasks: list of DBus Tasks paths
        """
        for dbus_task_path in dbus_tasks:
            task_proxy = service_id.get_proxy(dbus_task_path)
            self.append(DBusTask(task_proxy))

    @synchronized
    def insert(self, index, item):
        item.parent = self
        self._list.insert(index, item)

    @synchronized
    def __setitem__(self, index, item):
        item.parent = self
        return self._list.__setitem__(index, item)

    @synchronized
    def __len__(self):
        return self._list.__len__()

    @synchronized
    def count(self):
        return self._list.count()

    @synchronized
    def __getitem__(self, ii):
        return self._list[ii]

    @synchronized
    def __delitem__(self, index):
        self._list[index].parent = None
        del self._list[index]

    @synchronized
    def pop(self):
        item = self._list.pop()
        item.parent = None
        return item

    @synchronized
    def clear(self):
        for item in self._list:
            item.parent = None
        self._list.clear()

    # what we don't implement on purpose:
    # - reverse() and sort() - we don't support reordering the task queues
    # - extend() -> you can't extend a task queue by another one (at least for now)
    #            -> the name/status_message and general non-list state of the resulting queue
    #               would be undefined
    # - __add__(), __radd__() - same as above


class Task(BaseTask):
    """Task is a wrapper for a single installation related task.

    It has a name and a callable (called task), which is the actual task to execute.
    Arguments and keywoard arguments for the callable can be suplied by using
    the task_args and task_kwargs options.

    The Task class also some state variables to check if the task is running or
    if it is already done.

    A Task can be started by running the start() method. This can be done
    only once, further attempts will result in an error being logged.
    If you want to run a task multiple times, just schedule multiple
    Task instances to run.
    """

    def __init__(self, name, task=None, task_args=None, task_kwargs=None):
        super().__init__(name=name)
        self._task = task
        if task_args is None:
            task_args = []
        self._task_args = task_args
        if task_kwargs is None:
            task_kwargs = dict()
        self._task_kwargs = task_kwargs

    @property
    def summary(self):
        """A description of the task.

        :returns: a single line describing the task
        :rtype: str
        """
        return "Task: %s" % self.name

    @property
    @synchronized
    def parent(self):
        """The parent task queue of this task (if any).

        :returns: parent of this task (if any)
        :rtype: TaskQueue instance or None
        """
        return self._parent

    @parent.setter
    @synchronized
    def parent(self, parent_item):
        # check if a parent has already been set
        if self._parent is not None:
            # disconnect signals from the previous parent first
            self.started.disconnect(self._parent.task_started.emit)
            self.completed.disconnect(self._parent.task_completed.emit)
        # set the parent
        self._parent = parent_item
        # Connect own signals "up" to the parent
        self.started.connect(self._parent.task_started.emit)
        self.completed.connect(self._parent.task_completed.emit)

    def run_task(self):
        """Runs the task (callable) assigned to this Task class instance.

        This method is mainly aimed at lightweight Task subclassing, without the
        need to reimplement the full start() method with all the signal triggers and
        related machinery.
        """
        if self._task:
            try:
                # Run the task.
                self._task(*self._task_args, **self._task_kwargs)
            except Exception as e:  # pylint: disable=broad-except
                # Handle an error.
                if errorHandler.cb(e) == ERROR_RAISE:
                    raise
        else:
            log.error("Task %s callable not set.", self.name)

    def start(self):
        """Start the task.

        Once started and until completed the running property will be True.
        Once the task finishes it's run, the running property will switch to False
        and the completed property will be True.

        Also note that a Task can be started only once - it can't be started again
        once it is running or completed. Attempt's to do so will only result in an
        error being logged.
        """
        do_start = False
        with self._lock:
            # the task can only be started once
            if self.running or self.done:
                if self.running:
                    # attempt to start a task that is already running
                    log.error("Can't start task %s - already running.")
                else:
                    # attempt to start a task that an already finished task
                    log.error("Can't start task %s - already done.")
            else:
                do_start = True
                self._running = True
                self._start_timestamp = time.time()

        if do_start:
            # trigger the "started" signal
            self.started.emit(self)
            # run the task
            self.run_task()
            # trigger the "completed" signal
            self.completed.emit(self)
            # the task should be done, set the task state accordingly
            with self._lock:
                self._running = False
                self._done = True
                self._done_timestamp = time.time()


class DBusTask(Task):
    """Wrapper for a DBus installation task."""

    def __init__(self, task_proxy):
        """Create a new task.

        :param task_proxy: a DBus proxy of the task
        """
        super().__init__(task_proxy.Name)
        self._task_proxy = task_proxy
        self._msg_counter = 0

    def run_task(self):
        """Run the DBus task."""
        try:
            # Report the progress messages.
            self._task_proxy.ProgressChanged.connect(
                self._show_message
            )

            # Run the task.
            sync_run_task(self._task_proxy)
        except DBusError as e:
            # Handle a remote error.
            if errorHandler.cb(e) == ERROR_RAISE:
                raise
        finally:
            # Disconnect from the signal.
            self._task_proxy.ProgressChanged.disconnect()

    def _show_message(self, step, msg):
        """Show a progress message.

        Always drop the first message, because it is the same
        as the name of the DBus task, so it was probably already
        reported.

        FIXME: Drop the ugly workaround for the first message.
        """
        self._msg_counter += 1

        if self._msg_counter > 1:
            progress_message(msg)
