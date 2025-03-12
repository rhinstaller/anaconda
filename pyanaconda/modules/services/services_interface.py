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
from pyanaconda.modules.common.constants.services import SERVICES
from pyanaconda.modules.services.constants import SetupOnBootAction


@dbus_interface(SERVICES.interface_name)
class ServicesInterface(KickstartModuleInterface):
    """DBus interface for Services module."""

    def connect_signals(self):
        """Connect signals to the implementation."""
        super().connect_signals()
        self.watch_property("EnabledServices", self.implementation.enabled_services_changed)
        self.watch_property("DisabledServices", self.implementation.disabled_services_changed)
        self.watch_property("DefaultTarget", self.implementation.default_target_changed)
        self.watch_property("DefaultDesktop", self.implementation.default_desktop_changed)
        self.watch_property("SetupOnBoot", self.implementation.setup_on_boot_changed)
        self.watch_property("PostInstallToolsEnabled",
                            self.implementation.post_install_tools_enabled_changed)

    @property
    def DisabledServices(self) -> List[Str]:
        """List of disabled services."""
        return self.implementation.disabled_services

    @DisabledServices.setter
    @emits_properties_changed
    def DisabledServices(self, services: List[Str]):
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

    @EnabledServices.setter
    @emits_properties_changed
    def EnabledServices(self, services: List[Str]):
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

    @DefaultTarget.setter
    @emits_properties_changed
    def DefaultTarget(self, target: Str):
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

    @DefaultDesktop.setter
    @emits_properties_changed
    def DefaultDesktop(self, desktop: Str):
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
        return self.implementation.setup_on_boot.value

    @SetupOnBoot.setter
    @emits_properties_changed
    def SetupOnBoot(self, value: Int):
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
        self.implementation.set_setup_on_boot(SetupOnBootAction(value))

    @property
    def PostInstallToolsEnabled(self) -> Bool:
        """Disable post installation setup tools.

        This option tells post installation tools
        if they should start after the installation.

        :return: True to start post install tools, False otherwise
        :rtype: bool
        """
        return self.implementation.post_install_tools_enabled

    @PostInstallToolsEnabled.setter
    @emits_properties_changed
    def PostInstallToolsEnabled(self, post_install_tools_enabled: Bool):
        """Set if post installation tools should be disabled.

        Setting this value to False will result in the post_install_tools_disabled
        key being written to the user interaction config file with the value of 1.

        Setting this value to True (the default value) will not result in the
        post_install_tools_disabled key being written into th user interaction config file.

        :param post_install_tools_enabled: set to False to disable post installation tools
        """
        self.implementation.set_post_install_tools_enabled(post_install_tools_enabled)
