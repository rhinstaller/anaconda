#
# The user interface module
#
# Copyright (C) 2021 Red Hat, Inc.
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
from pykickstart.commands.displaymode import DISPLAY_MODE_TEXT

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import (
    PASSWORD_POLICY_LUKS,
    PASSWORD_POLICY_ROOT,
    PASSWORD_POLICY_USER,
    DisplayModes,
)
from pyanaconda.core.dbus import DBus
from pyanaconda.core.product import get_product_is_final_release
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import USER_INTERFACE
from pyanaconda.modules.common.structures.policy import PasswordPolicy
from pyanaconda.modules.common.structures.vnc import VncData
from pyanaconda.modules.runtime.user_interface.ui_interface import UIInterface

log = get_module_logger(__name__)

__all__ = ["UIModule"]


class UIModule(KickstartBaseModule):
    """The user interface module."""

    def __init__(self):
        super().__init__()
        self._password_policies = self.get_default_password_policies()
        self.password_policies_changed = Signal()

        self.display_mode_changed = Signal()
        self._displayMode = DisplayModes.TUI

        self.display_mode_nonInteractive_changed = Signal()
        self._displayMode_nonInteractive = False

        self.display_mode_text_kickstarted_changed = Signal()
        self._display_mode_text_kickstarted = False

        self.vnc_changed = Signal()
        self._vnc = VncData()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(USER_INTERFACE.object_path, UIInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self.set_display_mode(data.displaymode.displayMode)
        self.set_display_mode_non_interactive(data.displaymode.nonInteractive)
        # check if text mode was requested in kickstart
        if data.displaymode.displayMode == DISPLAY_MODE_TEXT:
            log.debug("Text mode requested by kickstart")
            self._display_mode_text_kickstarted = True
            self.display_mode_text_kickstarted_changed.emit()

        vnc = VncData()
        vnc.enabled = data.vnc.enabled
        vnc.host = data.vnc.host
        vnc.port = data.vnc.port
        vnc.password.set_secret(data.vnc.password)
        self.set_vnc(vnc)

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        data.displaymode.displayMode = self._displayMode
        data.displaymode.nonInteractive = self._displayMode_nonInteractive
        data.vnc.enabled = self.vnc.enabled
        data.vnc.host = self.vnc.host
        data.vnc.port = self.vnc.port
        data.vnc.password = self.vnc.password.value

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
        log.debug("Display mode will be: %s", display_mode)

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
        log.debug("Display mode non-interactive set to: %s", str(non_interactive))

    @property
    def display_mode_text_kickstarted(self):
        """Report if text mode was explicitely requested via kickstart.


        #NOTE: No setter as this is only set once when parsing the kickstasrt.

        :return: if text mode was requested by kickstart
        :rtype: bool
        """

        return self._display_mode_text_kickstarted

    @property
    def vnc(self):
        """The VncData.

        :return: an instance of VncData
        """
        return self._vnc

    def set_vnc(self, vnc):
        """Set the VncData structure.

        :param vnc: VncData structure.
        :type vnc: object
        """
        self._vnc = vnc
        self.vnc_changed.emit()
        log.debug("VNC enabled set to: %s", vnc)

    @property
    def password_policies(self):
        """The password policies."""
        return self._password_policies

    def set_password_policies(self, policies):
        """Set the password policies.

        Default policy names:

            root  The policy for the root password.
            user  The policy for the user password.
            luks  The policy for the LUKS passphrase.

        :param policies: a dictionary of policy names and policy data
        """
        self._password_policies = policies
        self.password_policies_changed.emit()
        log.debug("Password policies are set to '%s'.", policies)

    def get_default_password_policies(self):
        """Get the default password policies.

        :return: a dictionary of policy names and policy data
        """
        return {
            PASSWORD_POLICY_ROOT: PasswordPolicy.from_defaults(PASSWORD_POLICY_ROOT),
            PASSWORD_POLICY_USER: PasswordPolicy.from_defaults(PASSWORD_POLICY_USER),
            PASSWORD_POLICY_LUKS: PasswordPolicy.from_defaults(PASSWORD_POLICY_LUKS),
        }

    @property
    def is_final(self):
        """Does the installation environment declare itself as "final"?

        This is false for Rawhide and Beta, true for GA/Gold.

        FIXME: This is a temporary getter. Replace it by the intended product API

        :return bool: final or not
        """
        return get_product_is_final_release()
