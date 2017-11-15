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

from abc import ABC, abstractmethod
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.dbus_constants import DBUS_TASK_NAME
from pydbus.error import map_error

from pyanaconda.dbus.typing import *

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
class TaskInterface(ABC):
    """Base class for implementing Task.

    This class has only interface of the Task. Logic will be implemented by each module.
    """

    @property
    @abstractmethod
    def Name(self) -> Str:
        """Get name of this task."""
        pass

    @property
    @abstractmethod
    def Description(self) -> Str:
        """Get description of this task."""
        pass

    @property
    @abstractmethod
    def Progress(self) -> (Int, Str):
        """Get immediate progress of this task.

        :returns: Tuple with actual step count and description of this step.
        """
        pass

    def ProgressChanged(self, step: Int, message: Str):
        """Signal making progress for this task.

        :param step: Number of the actual step. Please look on the self.ProgressStepsCount to
                     calculate progress percentage.
        :param message: Short description of what is this task currently trying to do.
        """
        pass

    @abstractmethod
    def ProgressStepsCount(self) -> Int:
        """Get number of steps for this task."""
        pass

    @property
    def IsCancelable(self) -> Bool:
        """Could this task be cancelled."""
        return False

    def Cancel(self):
        """Cancel this task.

        This will do something only if the IsCancelable property will return `True`.
        """
        pass

    @property
    @abstractmethod
    def IsRunning(self) -> Bool:
        """Return True if this Task is running already."""
        pass

    def RunningChanged(self, is_running: Bool):
        """Signal when this task stops or starts.

        :param is_running: True if the task started. False if the task stopped.
        """
        pass

    @abstractmethod
    def Run(self):
        """Run the task work."""
        pass
