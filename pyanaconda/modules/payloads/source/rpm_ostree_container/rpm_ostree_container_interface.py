#
# DBus interface for the RPM OSTree source module.
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

from pyanaconda.modules.common.constants.interfaces import (
    PAYLOAD_SOURCE_RPM_OSTREE_CONTAINER,
)
from pyanaconda.modules.common.structures.rpm_ostree import (
    RPMOSTreeContainerConfigurationData,
)
from pyanaconda.modules.payloads.source.source_base_interface import (
    PayloadSourceBaseInterface,
)

__all__ = ["RPMOSTreeContainerSourceInterface"]


@dbus_interface(PAYLOAD_SOURCE_RPM_OSTREE_CONTAINER.interface_name)
class RPMOSTreeContainerSourceInterface(PayloadSourceBaseInterface):
    """DBus interface for the RPM OSTree source module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property("Configuration", self.implementation.configuration_changed)

    @property
    def Configuration(self) -> Structure:
        """The source configuration.

        :return: a structure of the type RPMOSTreeConfigurationData
        """
        return RPMOSTreeContainerConfigurationData.to_structure(
            self.implementation.configuration
        )

    @Configuration.setter
    @emits_properties_changed
    def Configuration(self, data: Structure):
        """Set the source configuration.

        :param data: a structure of the type RPMOSTreeConfigurationData
        """
        self.implementation.set_configuration(
            RPMOSTreeContainerConfigurationData.from_structure(data)
        )
