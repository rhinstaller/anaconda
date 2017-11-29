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

from pyanaconda.dbus.dbus_constants import DBUS_BOSS_INSTALLATION_NAME
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.typing import *

from pyanaconda.modules.boss.install_manager.install_manager import InstallManager


@map_error("{}.InstallatioNotRunning")
class InstallationNotRunning(Exception):
    """Exception will be raised when action requires running installation."""
    pass


@dbus_interface(DBUS_BOSS_INSTALLATION_NAME)
class Installation(object):
    """Interface for Boss to summarize installation from modules for UIs."""

    def __init__(self, installation_instance: InstallManager):
        """Create installation interface.

        :param installation_instance: Manager for handling the installation process.
        """
        self._instance = installation_instance
        self.connect_signals()

    def connect_signals(self):
        """Connect signals of this interface with the implementation."""
        self._instance.set_installation_running_changed_signal(self.InstallationRunningChanged)
        self._instance.set_task_changed_signal(self.TaskChanged)
        self._instance.set_progress_changed_signal(self.ProgressChanged)
        self._instance.set_progress_float_changed_signal(self.ProgressChangedFloat)

    @property
    def InstallationRunning(self) -> Bool:
        """Installation is running right now."""
        return self._instance.installation_running

    def InstallationRunningChanged(self, is_running: Bool):
        """Installation state changed.

        :param is_running: If True than installation just started otherwise it ended.
        """
        pass

    def TaskChanged(self, name: Str):
        """Actual installation task changed.

        :param name: Name of the new installation task.
        """
        pass

    @property
    def TaskName(self) -> Str:
        """Name of the actual installation task."""
        return self._instance.task_name

    @property
    def TaskDescription(self) -> Str:
        """Description of the actual installation task."""
        return self._instance.task_description

    @property
    def Progress(self) -> (Int, Str):
        """Get installation progress.

        :return: Tuple (step, description).
                 step - Number of the step in the whole installation process.
                 description - Description of this step.
        """
        return self._instance.progress

    @property
    def ProgressFloat(self) -> (Double, Str):
        """Get installation progress as float number from 0.0 to 1.0.

        :return: Tuple (step, description).
                 step - Float number of the step.
                 description - Description of this step.
        """
        return self._instance.progress_float

    def ProgressChanged(self, step: Int, description: Str):
        """Installation progress signal.

        :param step: Number of the step in the whole installation process.
        :param description: Description of this step.
        """
        pass

    def ProgressChangedFloat(self, step: Double, description: Str):
        """Installation progress signal as float number from 0.0 to 1.0.

        :param step: Actual step as float number.
        :param description: Description of this step.
        """
        pass

    def Cancel(self):
        """Cancel installation process.

        Installation will be cancelled as soon as possible. The cancelling process could be blocked
        by active task.
        """
        self._instance.cancel()
