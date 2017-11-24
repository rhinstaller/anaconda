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
from pyanaconda.constants import THREAD_DBUS_TASK
from pyanaconda.dbus import get_bus
from pyanaconda.task.task_interface import TaskInterface, TaskAlreadyRunningException, \
                                           TaskNotImplemented
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.async_utils import async_action_nowait

__all__ = ['Task', 'TaskAlreadyRunningException', 'TaskNotImplemented']


class Task(TaskInterface):
    """Base class implementing DBus Task interface."""

    _task_counter = 1

    def __init__(self):
        super().__init__()
        self._name = ""
        self._description = ""
        self._progress_steps_count = 0
        self._job_callback = None
        self._progress = (0, "")

        self.__cancel_lock = Lock()
        self.__cancel = False

        self._task_number = Task._task_counter
        Task._task_counter += 1

        self._dbus_name = ""

    def publish(self, dbus_module_name):
        """Publish task with the next available number on DBus.

        :param dbus_module_name: Module name on the DBus.
        :type dbus_module_name: str
        """
        self._dbus_name = "{}.{}".format(dbus_module_name, self._task_number)
        bus = get_bus()
        bus.publish(self._dbus_name, self)

    @property
    def dbus_name(self):
        """DBus path poiting to this task.

        :returns: str
        """
        return self._dbus_name

    @property
    def Name(self):
        """Name of this task."""
        return self._name

    def set_name(self, name):
        """Set name of this task."""
        self._name = name

    @property
    def Description(self):
        """Short description of this task."""
        return self._description

    def set_description(self, description):
        """Set short description of this task."""
        self._description = description

    @property
    def ProgressStepsCount(self):
        """Number of the steps in this task."""
        return self._progress_steps_count

    def set_progress_steps_count(self, progress_steps_count):
        """Set number of the steps in this task."""
        self._progress_steps_count = progress_steps_count

    @property
    def Progress(self):
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
        self.ProgressChanged(step, message)

    @property
    def IsRunning(self):
        """Is this task running."""
        return threadMgr.exists(THREAD_DBUS_TASK)

    def running_changed(self):
        """Notify about change when this task stops/starts."""
        self.RunningChanged(self.IsRunning)

    def Cancel(self):
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

    def Run(self):
        """Run Task job.

        Overriding of the self.run_task() method instead is recommended.

        This method will create thread which will run the self.run_task() method.
        """
        if self._job_callback is None:
            raise TaskNotImplemented("Task {} does not have any job set.".format(self.Name))
        thread_name = "{}-{}".format(THREAD_DBUS_TASK, self.Name)
        thread = AnacondaThread(thread_name, target=self._job_callback)

        if threadMgr.exists(thread_name):
            threadMgr.add(thread)
            self._running_changed()
            threadMgr.call_when_thread_terminates(thread_name, self._running_changed)
        else:
            raise TaskAlreadyRunningException("Task {} is already running".format(self.Name))

    def set_task_job_callback(self, job_callback):
        """Set job for this task.

        This must be set before calling the self.Run() method. Otherwise the exception will raise.

        :param job_callback: callback of a task without any parameters.
        """
        self._job_callback = job_callback
