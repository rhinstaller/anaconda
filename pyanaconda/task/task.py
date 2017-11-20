# DBus Task interface.
#
# Base class of tasks.
# Task is used by modules to implement asynchronous time consuming installation
# or configuration tasks.
#
# Copyright (C) 2017 Red Hat, Inc.
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

from threading import Lock
from abc import ABC, abstractmethod
from pyanaconda.constants import THREAD_DBUS_TASK
from pyanaconda.task.task_interface import TaskAlreadyRunningException, TaskInterface
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.async_utils import async_action_nowait

__all__ = ['Task', 'TaskContainer', 'TaskAlreadyRunningException']


class Task(ABC):
    """Base class implementing DBus Task interface."""

    _task_counter = 1

    def __init__(self, dbus_modul_path):
        super().__init__()
        self._progress = (0, "")

        self.__cancel_lock = Lock()
        self.__cancel = False

        self._task_number = Task._task_counter
        Task._task_counter += 1

        self._running_changed_signal = None
        self._progress_changed_signal = None

        self._dbus_name = "{}.{}".format(dbus_modul_path, self._task_number)

    @property
    def dbus_name(self):
        """DBus path poiting to this task.

        :returns: str
        """
        return self._dbus_name

    @property
    @abstractmethod
    def name(self):
        """Name of this task."""
        pass

    @property
    @abstractmethod
    def description(self):
        """Short description of this task."""
        pass

    @property
    @abstractmethod
    def progress_steps_count(self):
        """Number of the steps in this task."""
        pass

    @property
    def progress(self):
        """Actual progress of this task.

        :returns: tuple (step, description).
        """
        return self._progress

    @async_action_nowait
    def progress_changed(self, step, message):
        """Update actual progress.

        Thread safe method. Can be used from the self.run_task() method.

        Signal change of the progress and update Progress DBus property.

        :param step: Number of the actual step.
        :type step: int

        :param message: Short description of the actual step.
        :type message: str
        """
        self._progress = (step, message)
        self._progress_changed_signal(step, message)

    def set_progress_changed_signal(self, progress_changed):
        """Set progress changed signal.

        :param progress_changed: Signal to emit when the progress of this task will change.
        :type progress_changed: Function with 2 params step and short description of the step
                                func(step: int, description: str).
        """
        self._progress_changed_signal = progress_changed

    @property
    def is_running(self):
        """Is this task running."""
        return threadMgr.exists(THREAD_DBUS_TASK)

    def running_changed(self):
        """Notify about change when this task stops/starts."""
        self._running_changed_signal(self.is_running)

    def set_running_changed_signal(self, running_changed):
        """Set running changed signal.

        :param running_changed: Signal to emit when this tasks starts/stops.
        :type running_changed: Function with bool param func(is_running: bool).
        """
        self._running_changed_signal = running_changed

    @property
    def is_cancelable(self):
        """Can this task be cancelled?

        :returns: bool.
        """
        return False

    def cancel(self):
        """Cancel this task.

        This will do something only if the IsCancelable property will return `True`.
        """
        with self.__cancel_lock:
            self.__cancel = True

    def check_cancel(self, clear=True):
        """Check if Task should be canceled and clear the cancel flag.

        :param clear: Clear the flag.
        :returns: bool
        """
        with self.__cancel_lock:
            if self.__cancel:
                if clear:
                    self.__cancel = False
                return True

        return False

    def run(self):
        """Run Task job.

        Overriding of the self.run_task() method instead is recommended.

        This method will create thread which will run the self.run_task() method.
        """
        thread_name = "{}-{}".format(THREAD_DBUS_TASK, self.name)
        thread = AnacondaThread(thread_name, target=self.runnable)

        if threadMgr.exists(thread_name):
            threadMgr.add(thread)
            self.running_changed()
            threadMgr.call_when_thread_terminates(thread_name, self.running_changed)
        else:
            raise TaskAlreadyRunningException("Task {} is already running".format(self.name))

    @abstractmethod
    def runnable(self):
        """Tasks job implementation.

        This will run in separate thread by calling the self.run() method.
        """
        pass


class TaskContainer(object):

    def __init__(self, task_implementation: Task):
        """Store interface next to implementation for Tasks.

        Also get base information from the objects directly.
        """
        self._task = task_implementation
        self._interface = TaskInterface(self._task)

    @property
    def interface(self):
        """Get interface object of the task."""
        return self._interface

    @property
    def task(self):
        """Get the implementation of the interface."""
        return self._task

    @property
    def name(self):
        """Name of this task."""
        return self.task.name

    @property
    def dbus_name(self):
        """Get dbus name of this task."""
        return self._task.dbus_name

    @property
    def description(self):
        """Short description of this task."""
        return self._task.description

    def publish(self):
        """Publish this task to the DBus."""
        self._interface.publish()
