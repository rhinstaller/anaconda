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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from abc import ABC, abstractmethod

from pyanaconda.core.signal import Signal
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.core.async_utils import async_action_nowait

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ['Runnable']


class Runnable(ABC):
    """Abstract class that allows to run a task."""

    def __init__(self):
        super().__init__()
        self._started_signal = Signal()
        self._stopped_signal = Signal()
        self._failed_signal = Signal()

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
    @abstractmethod
    def _thread_name(self):
        """Generate the name of the thread."""
        pass

    @property
    def is_running(self):
        """Is the task running."""
        return threadMgr.exists(self._thread_name)

    def start(self):
        """Start the task in a new thread."""
        threadMgr.add(
            AnacondaThread(
                name=self._thread_name,
                target=self._task_run,
                target_started=self._task_started_callback,
                target_stopped=self._task_stopped_callback,
                target_failed=self._task_failed_callback,
                fatal=False
            )
        )

    def finish(self):
        """Finish the task run.

        Call this method after the task was started and stopped. If there
        was raised an exception during the task run, it will be raised here
        again.
        """
        threadMgr.raise_if_error(self._thread_name)

    @abstractmethod
    def _task_run(self):
        """Run the task."""
        pass

    @async_action_nowait
    def _task_started_callback(self):
        """Callback for a started task."""
        self._started_signal.emit()

    @async_action_nowait
    def _task_stopped_callback(self):
        """Callback for a terminated task."""
        self._stopped_signal.emit()

    @async_action_nowait
    def _task_failed_callback(self, *exc_info):
        """Callback for a failed task."""
        self._failed_signal.emit()
