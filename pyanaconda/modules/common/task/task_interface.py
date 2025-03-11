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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_class, dbus_interface, dbus_signal
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base.base_template import InterfaceTemplate
from pyanaconda.modules.common.constants.interfaces import TASK
from pyanaconda.modules.common.errors.task import NoResultError
from pyanaconda.modules.common.structures.validation import ValidationReport

__all__ = ['TaskInterface', 'ValidationTaskInterface']


@dbus_interface(TASK.interface_name)
class TaskInterface(InterfaceTemplate):
    """Base class for implementing Task.

    This class has only interface of the Task. Logic will be implemented by each module.
    """

    def connect_signals(self):
        """Connect signals to the implementation."""
        self.implementation.progress_changed_signal.connect(self.ProgressChanged)
        self.implementation.started_signal.connect(self.Started)
        self.implementation.stopped_signal.connect(self.Stopped)
        self.implementation.failed_signal.connect(self.Failed)
        self.implementation.succeeded_signal.connect(self.Succeeded)

    @property
    def Name(self) -> Str:
        """Get the name of this task."""
        return self.implementation.name

    @property
    def Progress(self) -> Tuple[Int, Str]:
        """Get immediate progress of this task.

        :returns: Tuple with actual step count and description of this step.
        """
        return self.implementation.progress

    @dbus_signal
    def ProgressChanged(self, step: Int, message: Str):
        """Signal making progress for this task.

        :param step: Number of the actual step. Please look on the self.Steps to
                     calculate progress percentage.
        :param message: Short description of what is this task currently trying to do.
        """
        pass

    @property
    def Steps(self) -> Int:
        """Get total number of steps for this task."""
        return self.implementation.steps

    @property
    def IsRunning(self) -> Bool:
        """Return True if this Task is running already."""
        return self.implementation.is_running

    @dbus_signal
    def Started(self):
        """Signal when this task starts."""
        pass

    @dbus_signal
    def Stopped(self):
        """Signal when this task stops."""
        pass

    @dbus_signal
    def Failed(self):
        """Signal when this task fails."""
        pass

    @dbus_signal
    def Succeeded(self):
        """Signal when this task succeeds."""
        pass

    def Start(self):
        """Run the task work."""
        self.implementation.start()

    def Cancel(self):
        """Cancel the task."""
        self.implementation.cancel()

    def Finish(self):
        """Finish the task after it stopped.

        This method will raise an error if the task has failed.
        """
        self.implementation.finish()

    @staticmethod
    def convert_result(value) -> Variant:
        """Convert the value of the result.

        Convert the value into a variant.

        :param value: a value of the result
        :return: a variant with the value
        :raises: NoResultError by default
        """
        raise NoResultError("The result is not publishable.")

    def GetResult(self) -> Variant:
        """Get the result of the task if any.

        :return: a variant with the result
        :raises: NoResultError by default
        """
        result = self.implementation.get_result()
        return self.convert_result(result)


@dbus_class
class ValidationTaskInterface(TaskInterface):
    """DBus interface for a validation task."""

    @staticmethod
    def convert_result(value) -> Variant:
        """Convert the validation report.

        Convert the validation report into a variant.

        :param value: a validation report
        :return: a variant with the structure
        """
        return get_variant(Structure, ValidationReport.to_structure(value))
