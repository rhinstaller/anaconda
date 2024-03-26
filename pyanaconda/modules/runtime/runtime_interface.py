#
# DBus interface for the runtime module.
#
# Copyright (C) 2023 Red Hat, Inc.
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

from pyanaconda.modules.common.constants.services import RUNTIME
from pyanaconda.modules.common.base import KickstartModuleInterface

__all__ = ["RuntimeInterface"]


@dbus_interface(RUNTIME.interface_name)
class RuntimeInterface(KickstartModuleInterface):
    """DBus interface for the Runtime module."""

    def connect_signals(self):
        """Connect the signals for runtime command module properties."""
        super().connect_signals()
        self.watch_property("LoggingHost", self.implementation.logging_host_changed)
        self.watch_property("LoggingPort", self.implementation.logging_port_changed)
        self.watch_property("Rescue", self.implementation.rescue_changed)
        self.watch_property("RescueNoMount", self.implementation.rescue_nomount_changed)
        self.watch_property("RescueRoMount", self.implementation.rescue_romount_changed)
        self.watch_property("EULAAgreed", self.implementation.eula_agreed_changed)

    @property
    def LoggingHost(self) -> Str:
        """The logging host for the installation process."""
        return self.implementation.logging_host

    @LoggingHost.setter
    @emits_properties_changed
    def LoggingHost(self, host: Str):
        """Set the logging host for the installation process.

        :param host: The host address as a string.
        """
        self.implementation.set_logging_host(host)

    @property
    def LoggingPort(self) -> Str:
        """The logging port number."""
        return self.implementation.logging_port

    @LoggingPort.setter
    @emits_properties_changed
    def LoggingPort(self, port: Str):
        """Set the logging port for the installation process.

        :param port: The port number as a string.
        """
        self.implementation.set_logging_port(port)

    @property
    def Rescue(self) -> Bool:
        """Flag indicating whether rescue mode is enabled."""
        return self.implementation.rescue

    @Rescue.setter
    @emits_properties_changed
    def Rescue(self, rescue: Bool):
        """Enable or disable rescue mode.

        :param rescue: A boolean value indicating rescue mode status.
        """
        self.implementation.set_rescue(rescue)

    @property
    def RescueNoMount(self) -> Bool:
        """Flag for disabling mount in rescue mode."""
        return self.implementation.rescue_nomount

    @RescueNoMount.setter
    @emits_properties_changed
    def RescueNoMount(self, nomount: Bool):
        """Set the nomount flag for rescue mode.

        :param nomount: A boolean value.
        """
        self.implementation.set_rescue_nomount(nomount)

    @property
    def RescueRoMount(self) -> Bool:
        """Flag for read-only mount in rescue mode."""
        return self.implementation.rescue_romount

    @RescueRoMount.setter
    @emits_properties_changed
    def RescueRoMount(self, romount: Bool):
        """Enable or disable read-only mount in rescue mode.

        :param romount: A boolean value.
        """
        self.implementation.set_rescue_romount(romount)

    @property
    def EULAAgreed(self) -> Bool:
        """Flag indicating whether EULA was agreed to."""
        return self.implementation.eula_agreed

    @EULAAgreed.setter
    @emits_properties_changed
    def EULAAgreed(self, agreed: Bool):
        """Set the EULA agreement flag.

        :param agreed: A boolean value.
        """
        self.implementation.set_eula_agreed(agreed)
