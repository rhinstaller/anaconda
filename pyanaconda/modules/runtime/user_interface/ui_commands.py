#
# Copyright (C) 2024  Red Hat, Inc.
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
from pyanaconda.core.constants import DisplayModes
from pyanaconda.core.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartBaseModule

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.modules.common.constants.objects import USER_INTERFACE
from pyanaconda.modules.runtime.user_interface.ui_interface import UIInterface

log = get_module_logger(__name__)

__all__ = ["UICommandsModule"]


class UICommandsModule(KickstartBaseModule):
    """The UI-only commands module."""

    def __init__(self):
        super().__init__()
        self.display_mode_changed = Signal()
        self._displayMode = DisplayModes.TUI

        self.display_mode_nonInteractive_changed = Signal()
        self._displayMode_nonInteractive = False

        self.vnc_enabled_changed = Signal()
        self._vnc_enabled = False

        self.vnc_password_changed = Signal()
        self._vnc_password = ""

    def publish(self):
        """Publish the module."""
        DBus.publish_object(USER_INTERFACE.object_path, UIInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self.set_display_mode(data.displaymode.displayMode)
        self.set_display_mode_non_interactive(data.displaymode.nonInteractive)
        self.set_vnc_enabled(data.vnc.enabled)
        self.set_vnc_password(data.vnc.password)


    def setup_kickstart(self, data):
            """Set up the kickstart data."""
            data.displaymode.displayMode = self._displayMode
            data.displaymode.nonInteractive = self._displayMode_nonInteractive
            data.vnc.enabled = self._vnc_enabled
            data.vnc.password = self._vnc_password

    @property
    def display_mode(self):
        """DisplayMode mode for the installation.

        :return: the displayMode mode for the installation
        :rtype: DisplayModes enum
        """
        return self._displayMode

    def set_display_mode(self, display_mode):
        """Set displayMode mode for the installation.

        :param display_mode: the displayMode mode for the installation
        :type display_mode: DisplayModes enum
        """
        self._displayMode = display_mode
        self.display_mode_changed.emit()
        log.debug("Firewall mode will be: %s", display_mode)

    @property
    def display_mode_non_interactive(self):
        """Non-interactive flag for display mode.

        :return: the non-interactive flag for display mode
        :rtype: bool
        """
        return self._displayMode_nonInteractive

    def set_display_mode_non_interactive(self, non_interactive):
        """Set the non-interactive flag for display mode.

        :param non_interactive: the non-interactive flag for display mode.
        :type non_interactive: bool
        """
        self._displayMode_nonInteractive = non_interactive
        self.display_mode_nonInteractive_changed.emit()
        log.debug("Display mode non-interactive set to: %s", non_interactive)

    @property
    def vnc_enabled(self):
        """Check if VNC is enabled.

        :return: True if VNC is enabled, False otherwise
        :rtype: bool
        """
        return self._vnc_enabled

    def set_vnc_enabled(self, enabled):
        """Enable or disable VNC.

        :param enabled: True to enable VNC, False to disable
        :type enabled: bool
        """
        self._vnc_enabled = enabled
        self.vnc_enabled_changed.emit()
        log.debug("VNC enabled set to: %s", enabled)

    @property
    def vnc_password(self):
        """The VNC password.

        :return: VNC password
        :rtype: str
        """
        return self._vnc_password

    def set_vnc_password(self, password):
        """Set the VNC password.

        :param password: The password for VNC
        :type password: str
        """
        self._vnc_password = password
        self.vnc_password_changed.emit()
        log.debug("VNC password set.")
