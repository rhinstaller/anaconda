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
import sys
import time

from dasbus.error import DBusError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.constants import IPMI_ABORTED
from pyanaconda.core.signal import Signal
from pyanaconda.errors import ERROR_RAISE, errorHandler
from pyanaconda.flags import flags
from pyanaconda.modules.common.errors.runtime import ScriptError
from pyanaconda.modules.common.task import sync_run_task

log = get_module_logger(__name__)


class BaseTask:
    """A base class for Task and TaskQueue.

    It holds shared methods, properties and signals.
    """

    def __init__(self, name):
        self._name = name
        self._parent = None
        self._elapsed_time = None
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
    def elapsed_time(self):
        """Elapsed time since the task has been started in milliseconds."""
        return self._elapsed_time

    @property
    def summary(self):
        """A description of the task - to be overridden by subclasses."""
        raise NotImplementedError

    def set_parent(self, queue):
        """Set the parent task queue."""
        self._parent = queue

    def start(self):
        """Start the task."""
        # trigger the "started" signal
        self.started.emit(self)

        # run the task
        start_timestamp = time.time()

        self._run()

        done_timestamp = time.time()
        self._elapsed_time = done_timestamp - start_timestamp

        # trigger the "completed" signal
        self.completed.emit(self)

    def _run(self):
        """Run the task - to be overridden by sub-classes."""
        raise NotImplementedError


class TaskQueue(BaseTask):
    """TaskQueue represents a queue of TaskQueues or Tasks.

    TaskQueues and Tasks can be mixed in a single TaskQueue.
    """

    def __init__(self, name, status_message=None, task_category=None):
        super().__init__(name)
        self._task_category = task_category
        self._status_message = status_message
        # the list backing this TaskQueue instance
        self._queue = []
        # triggered if a TaskQueue contained in this one was started/completed
        self.queue_started = Signal()
        self.queue_completed = Signal()
        # triggered when a task is started
        self.task_started = Signal()
        self.task_completed = Signal()

    @property
    def task_category(self):
        """A category describing the Queue is trying to achieve.

        Eq. "Converting all foo into bar."

        The current main usecase is to set the ProgressHub status message when
        a TaskQueue is started.

        :returns: a task category
        :rtype: str
        """
        return self._task_category

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
    def items(self):
        """Task and queues contained in this queue.

        :return: a list of tasks and queues
        """
        return self._queue

    @property
    def nested_items(self):
        """Tasks and queues contained in this and all nested task queues.

        :return: a list of tasks and queues
        """
        items = []

        for item in self._queue:
            items.append(item)

            if isinstance(item, TaskQueue):
                items.extend(item.nested_items)

        return items

    @property
    def queue_count(self):
        """Returns number of TaskQueues contained in this and all nested TaskQueues.

        :returns: number of queues
        :rtype: int
        """
        return len([i for i in self.nested_items if isinstance(i, TaskQueue)])

    @property
    def task_count(self):
        """Returns number of tasks contained in this and all nested TaskQueues.

        :returns: number of tasks
        :rtype: int
        """
        return len([i for i in self.nested_items if not isinstance(i, TaskQueue)])

    @property
    def summary(self):
        """Return a multi-line summary of the contents of the task queue.

        :returns: summary of task queue contents
        :rtype: str
        """
        if self._parent is None:
            message = "Top-level task queue: %s\n" % self.name
            # this is the top-level queue, so add some "global" stats
            message += "Number of task queues: %d\n" % self.queue_count
            message += "Number of tasks: %d\n" % self.task_count
            message += "Task & task group listing:\n"
        else:
            message = "Task queue: %s\n" % self.name

        for item in self._queue:
            for line in item.summary.splitlines():
                message += " %s\n" % line

        return message.strip()

    def _run(self):
        """Run the task queue."""
        for item in self._queue:
            # start the item (TaskQueue/Task)
            item.start()

    # implement the Python list "interface" and make sure parent is always
    # set to a correct value
    def append(self, item):
        item.started.connect(self.task_started.emit)
        item.completed.connect(self.task_completed.emit)

        if isinstance(item, TaskQueue):
            # connect own start/completion signal to parents queue start/completion signal
            item.started.connect(self.queue_started.emit)
            item.completed.connect(self.queue_completed.emit)

            # propagate start/completion signals from nested queues/tasks
            item.queue_started.connect(self.queue_started.emit)
            item.queue_completed.connect(self.queue_completed.emit)

        self._queue.append(item)
        item.set_parent(self)

    def append_dbus_tasks(self, service_id, dbus_tasks):
        """Append DBus Tasks from a module to the TaskQueue.

        :param service_id: DBusServiceIdentifier instance corresponding to an Anaconda DBus module
        :param dbus_tasks: list of DBus Tasks paths
        """
        for dbus_task_path in dbus_tasks:
            task_proxy = service_id.get_proxy(dbus_task_path)
            self.append(DBusTask(task_proxy))


class Task(BaseTask):
    """Task is a wrapper for a single installation related task.

    It has a name and a callable (called task), which is the actual task to execute.
    Arguments and keywoard arguments for the callable can be suplied by using
    the task_args and task_kwargs options.
    """

    def __init__(self, task_name, task_cb, task_args=None, task_kwargs=None):
        super().__init__(task_name)
        self._task_cb = task_cb
        self._task_args = task_args or []
        self._task_kwargs = task_kwargs or {}

    @property
    def summary(self):
        """A description of the task.

        :returns: a single line describing the task
        :rtype: str
        """
        return "Task: %s" % self.name

    def _run(self):
        """Runs the task (callable) assigned to this Task class instance."""
        try:
            # Run the task.
            self._task_cb(*self._task_args, **self._task_kwargs)
        except Exception as e:  # pylint: disable=broad-except
            # Handle an error.
            if errorHandler.cb(e) == ERROR_RAISE:
                raise


class DBusTask(BaseTask):
    """Wrapper for a DBus installation task."""

    def __init__(self, task_proxy):
        """Create a new task.

        :param task_proxy: a DBus proxy of the task
        """
        super().__init__(task_proxy.Name)
        self._task_proxy = task_proxy

    @property
    def summary(self):
        """A description of the task.

        :returns: a single line describing the task
        :rtype: str
        """
        return "Task: %s" % self.name

    def _run(self):
        """Run the DBus task."""
        try:
            # Report the progress messages.
            self._task_proxy.ProgressChanged.connect(self._progress_cb)

            # Run the task.
            sync_run_task(self._task_proxy)
        except DBusError as e:
            # Handle a remote error.
            if isinstance(e, ScriptError):
                flags.ksprompt = True
                errorHandler.cb(e)
                util.ipmi_report(IPMI_ABORTED)
                sys.exit(0)
            else:
                if errorHandler.cb(e) == ERROR_RAISE:
                    raise
        finally:
            # Disconnect from the signal.
            self._task_proxy.ProgressChanged.disconnect()

    def _progress_cb(self, step, message):
        """Callback for task progress reporting."""
        log.info(message)
