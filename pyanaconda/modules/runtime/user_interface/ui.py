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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
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
from pyanaconda.core.product import get_product_values
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.base import KickstartBaseModule
from pyanaconda.modules.common.constants.objects import USER_INTERFACE
from pyanaconda.modules.common.structures.policy import PasswordPolicy
from pyanaconda.modules.common.structures.product import ProductData
from pyanaconda.modules.common.structures.rdp import RdpData
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

        self.rdp_changed = Signal()
        self._rdp = RdpData()

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

        rdp = RdpData()
        rdp.enabled = data.rdp.enabled
        rdp.username = data.rdp.username
        rdp.password.set_secret(data.rdp.password)
        self.set_rdp(rdp)

    def setup_kickstart(self, data):
        """Set up the kickstart data."""
        data.displaymode.displayMode = self._displayMode
        data.displaymode.nonInteractive = self._displayMode_nonInteractive
        data.rdp.enabled = self._rdp.enabled
        data.rdp.username = self._rdp.username
        data.rdp.password = self._rdp.password.value

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
    def rdp(self):
        """The RdpData.
        :return: an instance of RdpData
        """
        return self._rdp

    def set_rdp(self, rdp):
        """Set the RdpData structure.
        :param rdp: RdpData structure.
        :type rdp: object
        """
        self._rdp = rdp
        self.rdp_changed.emit()
        log.debug("RDP enabled set to: %s", rdp)

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
    def product_data(self):
        """Load the product data and convert it into the ProductData structure.

        :return: An instance of the ProductData structure containing product information.
        :rtype: ProductData
        """
        product_data = ProductData()
        product_values = get_product_values()

        product_data.is_final_release = product_values.is_final_release
        product_data.name = product_values.name
        product_data.version = product_values.version
        product_data.short_name = product_values.short_name

        return product_data
