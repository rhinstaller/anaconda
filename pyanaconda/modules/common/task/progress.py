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
from threading import Lock

from pyanaconda.core.async_utils import async_action_nowait
from pyanaconda.core.signal import Signal

__all__ = ['ProgressReporter']


class ProgressReporter(ABC):
    """Abstract class that allows to report a progress of a task."""

    def __init__(self):
        super().__init__()
        self._progress_changed_signal = Signal()
        self._category_changed_signal = Signal()

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
    @abstractmethod
    def steps(self):
        """Number of progress steps in the task."""
        return 0

    @property
    def progress_changed_signal(self):
        """Signal emits when the progress of the task changes."""
        return self._progress_changed_signal

    @property
    def category_changed_signal(self):
        """Signal emits when the category of the task changes."""
        return self._category_changed_signal

    @async_action_nowait
    def report_category(self, category):
        if category is None:
            return
        else:
            self._category_changed_signal.emit(category)


    @async_action_nowait
    def report_progress(self, message, step_number=None, step_size=None):
        """Report a progress change.

        Update the progress and emit the progress changed signal. The next
        step will never be higher then self.steps and lower then the current
        step. By default, the step doesn't change.

        This is a thread safe method.

        :param message: Short description of the actual step.
        :type message: str
        :param step_number: The number of the next step.
        :type step_number: int or None
        :param step_size: The size of the next step.
        :type step_size: int or None
        """
        with self.__progress_lock:
            current_step = self.__progress_step
            max_step = self.steps
            step = current_step

            if step_number is not None:
                step = step_number

            if step_size is not None:
                step += step_size

            step = max(step, current_step)
            step = min(step, max_step)

            self.__progress_step = step
            self.__progress_msg = message

        self._progress_changed_signal.emit(step, message)
