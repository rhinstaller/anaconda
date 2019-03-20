#
# DBus interface for packaging section.
#
# Copyright (C) 2019 Red Hat, Inc.
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
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.objects import DNF_PACKAGES
from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate


@dbus_interface(DNF_PACKAGES.interface_name)
class PackagesHandlerInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for DNF packages sub-module."""

    def connect_signals(self):
        super().connect_signals()

        self.implementation.core_group_enabled_changed.connect(self.changed("CoreGroupEnabled"))
        self.implementation.environment_changed.connect(self.changed("Environment"))
        self.implementation.groups_changed.connect(self.changed("Groups"))
        self.implementation.packages_changed.connect(self.changed("Packages"))
        self.implementation.excluded_groups_changed.connect(self.changed("ExcludedGroups"))
        self.implementation.excluded_packages_changed.connect(self.changed("ExcludedPackages"))

    @property
    def CoreGroupEnabled(self) -> Bool:
        """Should the core package group be installed?"""
        return self.implementation.core_group_enabled

    @emits_properties_changed
    def SetCoreGroupEnabled(self, core_group_enabled: Bool):
        """Set if the core package group should be installed."""
        self.implementation.set_core_group_enabled(core_group_enabled)

    @property
    def DefaultEnvironment(self) -> Bool:
        """Should the default environment be pre-selected for installation?"""
        return self.implementation.default_environment

    @property
    def Environment(self) -> Str:
        """Get environment used for installation."""
        return self.implementation.environment

    @emits_properties_changed
    def SetEnvironment(self, environment: Str):
        """Set environment used for installation."""
        self.implementation.set_environment(environment)

    @property
    def Groups(self) -> List[Str]:
        """Get list of groups marked for installation."""
        return self.implementation.groups

    @emits_properties_changed
    def SetGroups(self, groups: List[Str]):
        """Set list of groups which will be used for installation."""
        self.implementation.set_groups(groups)

    @property
    def Packages(self) -> List[Str]:
        """Get list of packages marked for installation."""
        return self.implementation.packages

    @emits_properties_changed
    def SetPackages(self, packages: List[Str]):
        """Set list of packages which will be used for installation."""
        self.implementation.set_packages(packages)

    @property
    def ExcludedGroups(self) -> List[Str]:
        """Get list of excluded groups from the installation."""
        return self.implementation.excluded_groups

    @emits_properties_changed
    def SetExcludedGroups(self, excluded_groups: List[Str]):
        """Set list of the excluded groups for the installation."""
        self.implementation.set_excluded_groups(excluded_groups)

    @property
    def ExcludedPackages(self) -> List[Str]:
        """Get list of packages excluded from the installation."""
        return self.implementation.excluded_packages

    @emits_properties_changed
    def SetExcludedPackages(self, excluded_packages: List[Str]):
        """Set list of packages which will be excluded from the installation."""
        self.implementation.set_excluded_packages(excluded_packages)
