#
# DBus interface for the Services module.
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.constants.services import SERVICES


@dbus_interface(SERVICES.interface_name)
class ServicesInterface(KickstartModuleInterface):
    """DBus interface for Services module."""

    def connect_signals(self):
        """Connect signals to the implementation."""
        super().connect_signals()
        self.implementation.enabled_services_changed.connect(self.changed("EnabledServices"))
        self.implementation.disabled_services_changed.connect(self.changed("DisabledServices"))
        self.implementation.default_target_changed.connect(self.changed("DefaultTarget"))
        self.implementation.default_desktop_changed.connect(self.changed("DefaultDesktop"))
        self.implementation.setup_on_boot_changed.connect(self.changed("SetupOnBoot"))

    @property
    def DisabledServices(self) -> List[Str]:
        """List of disabled services."""
        return self.implementation.disabled_services

    @emits_properties_changed
    def SetDisabledServices(self, services: List[Str]):
        """Set the disabled services.

        Modifies the default set of services that will run under the default runlevel.
        The services listed in the disabled list will be disabled before the services
        listed in the enabled list are enabled.

        :param services: a list of service names.
        """
        self.implementation.set_disabled_services(services)

    @property
    def EnabledServices(self) -> List[Str]:
        """List of enabled services."""
        return self.implementation.enabled_services

    @emits_properties_changed
    def SetEnabledServices(self, services: List[Str]):
        """Set the enabled services.

        Modifies the default set of services that will run under the default runlevel.
        The services listed in the disabled list will be disabled before the services
        listed in the enabled list are enabled.

        :param services: a list of service names
        """
        self.implementation.set_enabled_services(services)

    @property
    def DefaultTarget(self) -> Str:
        """Default target of the installed system."""
        return self.implementation.default_target

    @emits_properties_changed
    def SetDefaultTarget(self, target: Str):
        """Set the default target of the installed system.

        Supported values are:
            multi-user.target
            graphical.target

        :param target: a string with the target
        """
        self.implementation.set_default_target(target)

    @property
    def DefaultDesktop(self) -> Str:
        """Default desktop of the installed system."""
        return self.implementation.default_desktop

    @emits_properties_changed
    def SetDefaultDesktop(self, desktop: Str):
        """Set the default desktop of the installed system.

        Supported values are:
            GNOME
            KDE

        :param desktop: a string with the desktop
        """
        self.implementation.set_default_desktop(desktop)

    @property
    def SetupOnBoot(self) -> Int:
        """Set up the installed system on the first boot."""
        return self.implementation.setup_on_boot

    @emits_properties_changed
    def SetSetupOnBoot(self, value: Int):
        """Set up the installed system on the first boot.

        Determine whether the Setup Agent starts the first
        time the system is booted.

        Allowed values:
            -1 Default.
             0 Disable.
             1 Enable.
             2 Enable in the reconfiguration mode.

        :param value: a number of the action
        """
        self.implementation.set_setup_on_boot(value)
