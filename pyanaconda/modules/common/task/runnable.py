#
# Copyright (C) 2018 Red Hat, Inc.
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
from abc import ABC, abstractmethod

from pyanaconda.core.async_utils import async_action_nowait
from pyanaconda.core.signal import Signal

__all__ = ['Runnable']


class Runnable(ABC):
    """Abstract class that allows to run a task."""

    def __init__(self):
        super().__init__()
        self._started_signal = Signal()
        self._stopped_signal = Signal()
        self._failed_signal = Signal()
        self._succeeded_signal = Signal()

    @property
    def started_signal(self):
        """Signal emitted when the task starts."""
        return self._started_signal

    @property
    def stopped_signal(self):
        """Signal emitted when the task stops."""
        return self._stopped_signal

    @property
    def failed_signal(self):
        """Signal emitted when the task fails."""
        return self._failed_signal

    @property
    def succeeded_signal(self):
        """Signal emitted when the task succeeds."""
        return self._succeeded_signal

    @property
    @abstractmethod
    def is_running(self):
        """Is the task running."""
        return False

    @abstractmethod
    def start(self):
        """Start the task run.

        Your task should run the following callbacks:

            self._task_started_callback
            self._task_run_callback
            self._task_failed_callback
            self._task_succeeded_callback
            self._task_stopped_callback

        Make sure that you call self._task_started_callback at the
        beginning of the task lifetime to inform that the task is
        running now. Run self._task_run_callback to do the actual
        job of the task.

        In a case of failure, call self._task_failed_callback to
        inform that the task has failed. You will still need to
        call also self._task_stopped_callback.

        In a case of success, call self._task_succeeded_callback to
        inform that the task has succeeded.

        Make sure that you always call self._task_stopped_callback
        at the end of the task lifetime to inform that the task is
        not running anymore.
        """
        pass

    @async_action_nowait
    def _task_started_callback(self):
        """Callback for a started task."""
        self._started_signal.emit()

    @abstractmethod
    def _task_run_callback(self):
        """Run the task."""
        pass

    @async_action_nowait
    def _task_failed_callback(self):
        """Callback for a failed task."""
        self._failed_signal.emit()

    @async_action_nowait
    def _task_succeeded_callback(self):
        """Callback for a successful task."""
        self._succeeded_signal.emit()

    @async_action_nowait
    def _task_stopped_callback(self):
        """Callback for a terminated task."""
        self._stopped_signal.emit()

    @abstractmethod
    def finish(self):
        """Finish the task run.

        This method should be called after the task was started and stopped.
        Re-raise any exception that was raised during the task run and wasn't
        propagated by the self.start method.
        """
        pass
