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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.constants.services import RUNTIME

__all__ = ["RuntimeInterface"]

from pyanaconda.modules.common.structures.logging import LoggingData
from pyanaconda.modules.common.structures.reboot import RebootData
from pyanaconda.modules.common.structures.rescue import RescueData


@dbus_interface(RUNTIME.interface_name)
class RuntimeInterface(KickstartModuleInterface):
    """DBus interface for the Runtime module."""

    def connect_signals(self):
        """Connect the signals for runtime command module properties."""
        super().connect_signals()
        self.watch_property("Logging", self.implementation.logging_changed)
        self.watch_property("Rescue", self.implementation.rescue_changed)
        self.watch_property("EULAAgreed", self.implementation.eula_agreed_changed)

    @property
    def Logging(self) -> Structure:
        """Specification of the logging configuration"""
        return LoggingData.to_structure(self.implementation.logging)

    @Logging.setter
    @emits_properties_changed
    def Logging(self, logging: Structure):
        """Specify of the logging configuration.

        The DBus structure is defined by LoggingData.

        :param logging: a dictionary with specification.
        """
        self.implementation.set_logging(LoggingData.from_structure(logging))

    @property
    def Rescue(self) -> Structure:
        """Specification of the rescue configuration."""
        return RescueData.to_structure(self.implementation.rescue)

    @Rescue.setter
    @emits_properties_changed
    def Rescue(self, rescue: Structure):
        """Specify of the rescue configuration.

        The DBus structure is defined by RescueData.

        :param rescue: a dictionary with specification.
        """
        self.implementation.set_rescue(RescueData.from_structure(rescue))

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

    @property
    def Reboot(self) -> Structure:
        """Specification of the reboot/poweroff/halt/shutdown configuration."""
        return RebootData.to_structure(self.implementation.reboot)

    @Reboot.setter
    @emits_properties_changed
    def Reboot(self, reboot: Structure):
        """Specify the reboot configuration.

        The DBus structure is defined by RebootData.
        """
        self.implementation.set_reboot(RebootData.from_structure(reboot))

    def Exit(self):
        """Perform cleanup and reboot/poweroff/halt."""
        self.implementation.exit()
