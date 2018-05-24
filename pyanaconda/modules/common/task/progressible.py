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
from abc import ABC
from threading import Lock

from pyanaconda.core.signal import Signal
from pyanaconda.core.async_utils import async_action_nowait

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ['Progressible']


class Progressible(ABC):
    """Abstract class that allows to report a progress of a task."""

    def __init__(self):
        super().__init__()
        self._progress_changed_signal = Signal()

        self.__progress_lock = Lock()
        self.__progress_step = 0
        self.__progress_msg = ""

    @property
    def progress(self):
        """Current progress of the task.

        :returns: tuple (step, description).
        """
        with self.__progress_lock:
            return self.__progress_step, self.__progress_msg

    @property
    def progress_steps_count(self):
        """Number of progress steps in the task."""
        return 0

    @property
    def progress_changed_signal(self):
        """Signal emits when the progress of the task changes."""
        return self._progress_changed_signal

    @async_action_nowait
    def report_progress(self, message, do_step=False, step_size=1):
        """Report a progress change.

        It will emit the progress changed signal with the current
        step and a message. If the current step is larger then the
        total number of steps claimed in self.progress_steps_count,
        it will be set to the self.progress_steps_count value.

        This is a thread safe method.

        :param message: Short description of the actual step.
        :type message: str
        :param do_step: Should we increment current step?
        :type do_step: bool
        :param step_size: The size of the next step.
        :type step_size: int
        """
        with self.__progress_lock:
            step = self.__progress_step

            if do_step:
                step += step_size

            if step > self.progress_steps_count:
                step = self.progress_steps_count

            self.__progress_step = step
            self.__progress_msg = message

        self._progress_changed_signal.emit(step, message)
