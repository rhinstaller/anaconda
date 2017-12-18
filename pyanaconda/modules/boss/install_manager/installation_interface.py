# DBus Installation interface for Boss.
#
# API specification of installation interface for Boss.
#
# This class provides installation API for UIs. It will summarize installation
# installation Tasks from modules.
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

from pyanaconda.dbus.constants import DBUS_BOSS_INSTALLATION_NAME
from pyanaconda.dbus.interface import dbus_interface, dbus_signal
from pyanaconda.dbus.template import InterfaceTemplate
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import


@map_error("{}.InstallationNotRunning".format(DBUS_BOSS_INSTALLATION_NAME))
class InstallationNotRunning(Exception):
    """Exception will be raised when action requires running installation."""
    pass


@dbus_interface(DBUS_BOSS_INSTALLATION_NAME)
class InstallationInterface(InterfaceTemplate):
    """Interface for Boss to summarize installation from modules for UIs."""

    def connect_signals(self):
        """Connect signals of this interface with the implementation."""
        self.implementation.installation_started.connect(self.InstallationStarted)
        self.implementation.installation_stopped.connect(self.InstallationStopped)
        self.implementation.task_changed_signal.connect(self.TaskChanged)
        self.implementation.progress_changed_signal.connect(self.ProgressChanged)
        self.implementation.progress_changed_float_signal.connect(self.ProgressChangedFloat)
        self.implementation.error_raised_signal.connect(self.ErrorRaised)

    @property
    def InstallationRunning(self) -> Bool:
        """Installation is running right now."""
        return self.implementation.installation_running

    @dbus_signal
    def InstallationStarted(self):
        """Signal emits when installation started."""
        pass

    @dbus_signal
    def InstallationStopped(self):
        """Signal emits when installation stopped."""
        pass

    @dbus_signal
    def TaskChanged(self, name: Str):
        """Actual installation task changed.

        :param name: Name of the new installation task.
        """
        pass

    @property
    def TaskName(self) -> Str:
        """Name of the actual installation task."""
        return self.implementation.task_name

    @property
    def TaskDescription(self) -> Str:
        """Description of the actual installation task."""
        return self.implementation.task_description

    @dbus_signal
    def ErrorRaised(self, error_description: Str):
        """Error raised in the process of installation."""
        pass

    @property
    def ProgressStepsCount(self) -> Int:
        """Sum of all steps in all Tasks in installation."""
        return self.implementation.progress_steps_count

    @property
    def Progress(self) -> Tuple[Int, Str]:
        """Get installation progress.

        :return: Tuple (step, description).
                 step - Number of the step in the whole installation process.
                 description - Description of this step.
        """
        return self.implementation.progress

    @property
    def ProgressFloat(self) -> Tuple[Double, Str]:
        """Get installation progress as float number from 0.0 to 1.0.

        :return: Tuple (step, description).
                 step - Float number of the step.
                 description - Description of this step.
        """
        return self.implementation.progress_float

    @dbus_signal
    def ProgressChanged(self, step: Int, description: Str):
        """Installation progress signal.

        :param step: Number of the step in the whole installation process.
        :param description: Description of this step.
        """
        pass

    @dbus_signal
    def ProgressChangedFloat(self, step: Double, description: Str):
        """Installation progress signal as float number from 0.0 to 1.0.

        :param step: Actual step as float number.
        :param description: Description of this step.
        """
        pass

    def StartInstallation(self):
        """Start the installation process."""
        self.implementation.start_installation()

    def Cancel(self):
        """Cancel installation process.

        Installation will be cancelled as soon as possible. The cancelling process could be blocked
        by active task.
        """
        self.implementation.cancel()
