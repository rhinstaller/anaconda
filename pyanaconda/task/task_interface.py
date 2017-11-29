# DBus Task interface.
#
# API specification of tasks interface.
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

from pydbus.error import map_error

from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.dbus_constants import DBUS_TASK_NAME
from pyanaconda.dbus import get_bus
from pyanaconda.dbus.typing import *
from pyanaconda.task.task import Task

__all__ = ['TaskInterface', 'TaskAlreadyRunningException', 'TaskNotImplemented']


@map_error("{}.AlreadyRunning".format(DBUS_TASK_NAME))
class TaskAlreadyRunningException(Exception):
    """Exception will be raised when starting task which is already running."""
    pass


@map_error("{}.NotImplemented".format(DBUS_TASK_NAME))
class TaskNotImplemented(Exception):
    """Exception will be raised when tasks job is not implemented."""
    pass


@dbus_interface(DBUS_TASK_NAME)
class TaskInterface(object):
    """Base class for implementing Task.

    This class has only interface of the Task. Logic will be implemented by each module.
    """

    def __init__(self, task_instance: Task):
        self._task_instance = task_instance
        self.connect_signals()

    def connect_signals(self):
        """Connect signals to the implementation."""
        self._task_instance.set_progress_changed_signal(self.ProgressChanged)
        self._task_instance.set_running_changed_signal(self.RunningChanged)

    @property
    def Name(self) -> Str:
        """Get name of this task."""
        return self._task_instance.name

    @property
    def Description(self) -> Str:
        """Get description of this task."""
        return self._task_instance.description

    @property
    def Progress(self) -> (Int, Str):
        """Get immediate progress of this task.

        :returns: Tuple with actual step count and description of this step.
        """
        return self._task_instance.progress

    def ProgressChanged(self, step: Int, message: Str):
        """Signal making progress for this task.

        :param step: Number of the actual step. Please look on the self.ProgressStepsCount to
                     calculate progress percentage.
        :param message: Short description of what is this task currently trying to do.
        """
        pass

    def ProgressStepsCount(self) -> Int:
        """Get number of steps for this task."""
        return self._task_instance.progress_steps_count

    @property
    def IsCancelable(self) -> Bool:
        """Could this task be cancelled."""
        return self._task_instance.is_cancelable

    def Cancel(self):
        """Cancel this task.

        This will do something only if the IsCancelable property will return `True`.
        """
        self._task_instance.cancel()

    @property
    def IsRunning(self) -> Bool:
        """Return True if this Task is running already."""
        return self._task_instance.is_running

    def RunningChanged(self, is_running: Bool):
        """Signal when this task stops or starts.

        :param is_running: True if the task started. False if the task stopped.
        """
        pass

    def Run(self):
        """Run the task work."""
        self._task_instance.run()

    def publish(self):
        """Publish task on DBus."""
        get_bus().publish(self._task_instance.dbus_name, self)
