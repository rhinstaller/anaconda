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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import traceback
from abc import abstractmethod

from dasbus.server.publishable import Publishable

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import THREAD_DBUS_TASK
from pyanaconda.core.threads import thread_manager
from pyanaconda.modules.common.errors.task import NoResultError
from pyanaconda.modules.common.task.cancellable import Cancellable
from pyanaconda.modules.common.task.progress import ProgressReporter
from pyanaconda.modules.common.task.result import ResultProvider
from pyanaconda.modules.common.task.runnable import Runnable
from pyanaconda.modules.common.task.task_interface import (
    TaskInterface,
    ValidationTaskInterface,
)

log = get_module_logger(__name__)

__all__ = ['AbstractTask', 'Task', 'ValidationTask']


class AbstractTask(Runnable, Cancellable, Publishable, ProgressReporter, ResultProvider):
    """Abstract class for running a long-term task."""

    @property
    @abstractmethod
    def name(self):
        """Name of this task.

        For example: "Install the payload"

        :returns: string with the task name
        """
        return ""

    def for_publication(self):
        """Return a DBus representation."""
        return TaskInterface(self)


class Task(AbstractTask):
    """Abstract class for running a long-term task in a thread."""

    _thread_counter = 0

    def __init__(self):
        super().__init__()
        self._thread_name = self._generate_thread_name()

    @property
    def steps(self):
        """Total number of steps."""
        return 1

    @property
    def is_running(self):
        """Is the task running."""
        return thread_manager.exists(self._thread_name)

    def start(self):
        """Start the task in a new thread."""
        thread_manager.add_thread(
            name=self._thread_name,
            target=self._thread_run_callback,
            target_started=self._task_started_callback,
            target_stopped=self._task_stopped_callback,
            target_failed=self._thread_failed_callback,
            fatal=False
        )

    def _thread_run_callback(self):
        """Run a task and report the success."""
        self._task_run_callback()
        self._task_succeeded_callback()

    def _task_run_callback(self):
        """Report the first step and run the task.
.
        Don't run the task if the task was canceled.
        """
        if self.check_cancel():
            log.info("'%s' is canceled.", self.name)
            return

        log.info(self.name)
        self._set_result(self.run())

    def _task_succeeded_callback(self):
        """Callback for a successful task.

        Don't report the success if the task was canceled.
        """
        if not self.check_cancel():
            super()._task_succeeded_callback()

    def _thread_failed_callback(self, *exc_info):
        """Log the error and report the failure."""
        # pylint: disable=no-value-for-parameter
        formatted_info = "".join(traceback.format_exception(*exc_info))
        log.error("Thread %s has failed: %s", self._thread_name, formatted_info)
        self._task_failed_callback()

    def run_with_signals(self):
        """Run the task in the current thread with enabled signals.

        Call this method to run the task synchronously in the current
        thread. It will emit all signals in the same order as the start
        method.

        :raise: an error if the task fails
        :return: a result of the task if the task succeeds
        """
        try:
            self._task_started_callback()
            self._task_run_callback()
        except Exception:  # pylint: disable=broad-except
            self._task_failed_callback()
            raise
        else:
            self._task_succeeded_callback()
        finally:
            self._task_stopped_callback()

        try:
            return self.get_result()
        except NoResultError:
            return None

    @abstractmethod
    def run(self):
        """The task implementation.

        Report the progress of the task with the self.report_progress
        method.

        Call self.check_cancel to check if the task should be canceled
        and terminate the task immediately if it returns True.

        Return a result of the task or None if the task doesn't provide
        a result.

        :return: a result of the task
        """
        return None

    def finish(self):
        """Finish the task run.

        Call this method after the task has stopped. If there was raised
        an exception during the task run, it will be raised here again.
        """
        thread_manager.raise_if_error(self._thread_name)

    @classmethod
    def _generate_thread_name(cls):
        """Generate the name of the thread."""
        cls._thread_counter += 1

        return "{}-{}-{}".format(
            THREAD_DBUS_TASK,
            cls.__name__,
            cls._thread_counter
        )


class ValidationTask(Task):
    """Abstract class for running a validation task."""

    def for_publication(self):
        """Return a DBus representation."""
        return ValidationTaskInterface(self)

    @abstractmethod
    def run(self):
        """The validation implementation.

        Run the validation and return an validation report
        with error and warning messages.

        :return: an instance of ValidationReport
        """
        return None
