#
# DBus interface for the user interface module
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
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import DisplayModes
from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.common.constants.objects import USER_INTERFACE
from pyanaconda.modules.common.structures.policy import PasswordPolicy

__all__ = ["UIInterface"]

from pyanaconda.modules.common.structures.vnc import VncData


@dbus_interface(USER_INTERFACE.interface_name)
class UIInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the user interface module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property("PasswordPolicies", self.implementation.password_policies_changed)
        self.watch_property("DisplayMode", self.implementation.display_mode_changed)
        self.watch_property("DisplayModeNonInteractive",
                            self.implementation.display_mode_nonInteractive_changed)
        self.watch_property("Vnc", self.implementation.vnc_changed)

    @property
    def PasswordPolicies(self) -> Dict[Str, Structure]:
        """The password policies."""
        return PasswordPolicy.to_structure_dict(
            self.implementation.password_policies
        )

    @PasswordPolicies.setter
    @emits_properties_changed
    def PasswordPolicies(self, policies: Dict[Str, Structure]):
        """Set the password policies.

        Default policy names:

            root  The policy for the root password.
            user  The policy for the user password.
            luks  The policy for the LUKS passphrase.

        :param policies: a dictionary of policy names and policy data
        """
        self.implementation.set_password_policies(
            PasswordPolicy.from_structure_dict(policies)
        )

    @property
    def DisplayMode(self) -> Str:
        """The display mode for the installation.

        Possible values are "TUI", "GUI" and "cmdline".
        """
        return self.implementation.display_mode

    @DisplayMode.setter
    @emits_properties_changed
    def DisplayMode(self, mode: Str):
        """Set the display mode for the installation.

        :param mode: The display mode as a string.
        """
        self.implementation.set_display_mode(
            DisplayModes[mode]
        )

    @property
    def DisplayModeNonInteractive(self) -> Bool:
        """The non-interactive flag for display mode."""
        return self.implementation.display_mode_non_interactive

    @DisplayModeNonInteractive.setter
    @emits_properties_changed
    def DisplayModeNonInteractive(self, non_interactive: Bool):
        """Set the non-interactive flag for display mode.

        :param non_interactive: A boolean value.
        """
        self.implementation.set_display_mode_non_interactive(non_interactive)

    @property
    def Vnc(self) -> Structure:
        """Specification of the vnc configuration."""
        return VncData.to_structure(self.implementation.vnc)

    @Vnc.setter
    @emits_properties_changed
    def Vnc(self, vnc: Structure):
        """Specify of the vnc configuration.

        The DBus structure is defined by VncData.

        :param vnc: a dictionary with specification.
        """
        self.implementation.set_vnc(
            VncData.from_structure(vnc)
        )

    @property
    def IsFinal(self) -> Bool:
        """Does the installation environment declare itself as "final"?

        FIXME: This is a temporary getter. Replace it by the intended product API
        """
        return self.implementation.is_final
