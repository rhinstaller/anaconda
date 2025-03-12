#
# DBus interface for the firewall configuration module.
#
# Copyright (C) 2018 Red Hat, Inc.
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

from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.common.constants.objects import FIREWALL
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.network.constants import FirewallMode


@dbus_interface(FIREWALL.interface_name)
class FirewallInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the firewall module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property("FirewallMode", self.implementation.firewall_mode_changed)
        self.watch_property("EnabledPorts", self.implementation.enabled_ports_changed)
        self.watch_property("Trusts", self.implementation.trusts_changed)
        self.watch_property("EnabledServices", self.implementation.enabled_services_changed)
        self.watch_property("DisabledServices", self.implementation.disabled_services_changed)

    @property
    def FirewallMode(self) -> Int:
        """How should the firewall be configured for the target system ?.

        Allowed values:
          -1  Unset.
           0  Disabled.
           1  Enabled.
           2  Use system defaults.

        :return: a value of the Firewall setup mode
        """
        return self.implementation.firewall_mode.value

    @FirewallMode.setter
    @emits_properties_changed
    def FirewallMode(self, firewall_mode: Bool):
        """Set firewall configuration mode for the target system."""
        self.implementation.set_firewall_mode(FirewallMode(firewall_mode))

    @property
    def EnabledPorts(self) -> List[Str]:
        """List of ports to be allowed through the firewall."""
        return self.implementation.enabled_ports

    @EnabledPorts.setter
    @emits_properties_changed
    def EnabledPorts(self, enabled_ports: List[Str]):
        """Set the list of ports to be allowed thorough the firewall.

        :param enabled_ports: a list of ports to be enabled
        """
        self.implementation.set_enabled_ports(enabled_ports)

    @property
    def Trusts(self) -> List[Str]:
        """List of trusted devices to be allowed through the firewall."""
        return self.implementation.trusts

    @Trusts.setter
    @emits_properties_changed
    def Trusts(self, trusts: List[Str]):
        """Set the list of trusted devices to be allowed through the firewall.

        :param trusts: a list of trusted devices
        """
        self.implementation.set_trusts(trusts)

    @property
    def EnabledServices(self) -> List[Str]:
        """List of services to be allowed through the firewall."""
        return self.implementation.enabled_services

    @EnabledServices.setter
    @emits_properties_changed
    def EnabledServices(self, enabled_services: List[Str]):
        """Set the list of services to be allowed through the firewall.

        :param enabled_services: a list of services to be enabled
        """
        self.implementation.set_enabled_services(enabled_services)

    @property
    def DisabledServices(self) -> List[Str]:
        """List of services to be explicitly disabled on the firewall."""
        return self.implementation.disabled_services

    @DisabledServices.setter
    @emits_properties_changed
    def DisabledServices(self, disabled_services: List[Str]):
        """Set the list of services to be explicitly disabled on the firewall.

        :param disabled_services: a list of services to be enabled
        """
        self.implementation.set_disabled_services(disabled_services)

    def InstallWithTask(self) -> ObjPath:
        """Install the bootloader.

        FIXME: This is just a temporary method.

        :return: a path to a DBus task
        """
        return TaskContainer.to_object_path(
            self.implementation.install_with_task()
        )
