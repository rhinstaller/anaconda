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

from pyanaconda.core.signal import Signal
from pyanaconda.core.constants import THREAD_DBUS_TASK
from pyanaconda.task.task_interface import TaskAlreadyRunningException
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.core.async_utils import async_action_nowait

__all__ = ['Task', 'TaskAlreadyRunningException']


class Task(ABC):
    """Base class implementing DBus Task interface."""

    def __init__(self):
        super().__init__()
        self._progress = (0, "")

        self.__cancel_lock = Lock()
        self.__cancel = False

        self._started_signal = Signal()
        self._stopped_signal = Signal()
        self._progress_changed_signal = Signal()
        self._error_raised_signal = Signal()

        self._thread_name = "{}-{}".format(THREAD_DBUS_TASK, self.name)

    @property
    def started_signal(self):
        """Signal emitted when this tasks starts."""
        return self._started_signal

    @property
    def stopped_signal(self):
        """Signal emitted when this task stops."""
        return self._stopped_signal

    @property
    def progress_changed_signal(self):
        """Signal emits when the progress of this task will change."""
        return self._progress_changed_signal

    @property
    def error_raised_signal(self):
        """Signal emits if error is raised during installation."""
        return self._error_raised_signal

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

    @property
    def is_running(self):
        """Is this task running."""
        return threadMgr.exists(self._thread_name)

    @property
    def is_cancelable(self):
        """Can this task be cancelled?

        :returns: bool.
        """
        return False

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
        self._progress_changed_signal.emit(step, message)

    @async_action_nowait
    def error_raised(self, error_message):
        self._error_raised_signal.emit(error_message)

    @async_action_nowait
    def running_changed(self):
        """Notify about change when this task stops/starts."""
        if self.is_running:
            self._started_signal.emit()
        else:
            self._stopped_signal.emit()

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
        thread = AnacondaThread(name=self._thread_name, target=self.runnable)

        if not threadMgr.exists(self._thread_name):
            threadMgr.add(thread)
            self.running_changed()
            threadMgr.call_when_thread_terminates(self._thread_name, self.running_changed)
        else:
            raise TaskAlreadyRunningException("Task {} is already running".format(self.name))

    @abstractmethod
    def runnable(self):
        """Tasks job implementation.

        This will run in separate thread by calling the self.run() method.

        To report progress change use the self.progress_changed() method.
        To report fatal error use the self.error_raised() method.
        If this Task can be cancelled check the self.check_cancel() method.
        """
        pass
