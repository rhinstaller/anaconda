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
from abc import ABC, abstractmethod

from pyanaconda.core.constants import THREAD_DBUS_TASK
from pyanaconda.modules.common.task.cancellable import Cancellable
from pyanaconda.modules.common.task.progressible import Progressible
from pyanaconda.modules.common.task.runnable import Runnable

__all__ = ['Task']


class Task(Runnable, Progressible, Cancellable, ABC):
    """Abstract class for running a long-term task."""

    @property
    @abstractmethod
    def id(self):
        """Identification of this task.

        The id will be used to create the thread name.

        :returns: string with the id
        """
        return ""

    @property
    @abstractmethod
    def description(self):
        """Short description of this task.

        The description can be shown to the user in UI,
        so it should be translated.

        :returns: string with the description
        """
        return ""

    @abstractmethod
    def run(self):
        """The task implementation.

        Report the progress of the task with the self.report_progress method.

        Call self.check_cancel to check if the task should be canceled and
        terminate the task immediately if it returns True.
        """
        pass

    @property
    def _thread_name(self):
        """Name of the thread."""
        return "{}-{}".format(THREAD_DBUS_TASK, self.id)

    def _task_run(self):
        """Report the progress and run the task."""
        self.report_progress(self.description)
        self.run()
