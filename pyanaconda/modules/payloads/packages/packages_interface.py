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
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.objects import PAYLOAD_PACKAGES
from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.payloads.packages.constants import MultilibPolicy


@dbus_interface(PAYLOAD_PACKAGES.interface_name)
class PackagesInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for packages module."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("CoreGroupEnabled", self.implementation.core_group_enabled_changed)
        self.watch_property("Environment", self.implementation.environment_changed)
        self.watch_property("Groups", self.implementation.groups_changed)
        self.watch_property("Packages", self.implementation.packages_changed)
        self.watch_property("ExcludedGroups", self.implementation.excluded_groups_changed)
        self.watch_property("ExcludedPackages", self.implementation.excluded_packages_changed)
        self.watch_property("DocsExcluded", self.implementation.docs_excluded_changed)
        self.watch_property("WeakdepsExcluded", self.implementation.weakdeps_excluded_changed)
        self.watch_property("MissingIgnored", self.implementation.missing_ignored_changed)
        self.watch_property("Languages", self.implementation.languages_changed)
        self.watch_property("MultilibPolicy", self.implementation.multilib_policy_changed)
        self.watch_property("Timeout", self.implementation.timeout_changed)
        self.watch_property("Retries", self.implementation.retries_changed)

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
        """Should the default environment be pre-selected for installation?

        FIXME: This API will be removed later and the behavior will slightly change. The
        current implementation does not work as expected. See commit comment for more info.
        """
        return self.implementation.default_environment

    @property
    def Environment(self) -> Str:
        """Get environment used for installation.

        If nothing set the empty string will be returned.
        """
        return self.implementation.environment

    @emits_properties_changed
    def SetEnvironment(self, environment: Str):
        """Set environment used for installation.

        To unset the value please set the empty string.
        """
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

    @property
    def DocsExcluded(self) -> Bool:
        """Should the package documentation be excluded?"""
        return self.implementation.docs_excluded

    @emits_properties_changed
    def SetDocsExcluded(self, docs_excluded: Bool):
        """Set if the package documentation should be excluded."""
        self.implementation.set_docs_excluded(docs_excluded)

    @property
    def WeakdepsExcluded(self) -> Bool:
        """Should the package weak dependencies be excluded?"""
        return self.implementation.weakdeps_excluded

    @emits_properties_changed
    def SetWeakdepsExcluded(self, weakdeps_excluded: Bool):
        """Set if the package weak dependencies should be excluded."""
        self.implementation.set_weakdeps_excluded(weakdeps_excluded)

    @property
    def MissingIgnored(self) -> Bool:
        """Should the missing packages be ignored?"""
        return self.implementation.missing_ignored

    @emits_properties_changed
    def SetMissingIgnored(self, missing_ignored: Bool):
        """Set if the missing packages should be ignored."""
        self.implementation.set_missing_ignored(missing_ignored)

    @property
    def Languages(self) -> Str:
        """Languages marked for installation.

        This is different from the package group level selections. This setting will change rpm
        macros to avoid installation of these languages.

        Multiple languages can be specified, in that case the ',' is used in the string as
        separator.

        Possible special values are 'none' or 'all'.

        'none' - Use nil in the rpm macro.
        'all'  - Default behavior.
        """
        return self.implementation.languages

    @emits_properties_changed
    def SetLanguages(self, languages: Str):
        """Set languages marked for installation.

        In case you want to specify multiple languages use ',' in the string as separator.

        Possible special values are 'none' or 'all'.
        'none' - Use nil in the rpm macro.
        'all'  - Default behavior.
        """
        self.implementation.set_languages(languages)

    @property
    def MultilibPolicy(self) -> Str:
        """Get multilib policy value.

        Possible values are:
        'all' - to install all available packages with compatible architectures
        'best' - for the depsolver to prefer packages which best match the system’s architecture
        """
        return self.implementation.multilib_policy.value

    @emits_properties_changed
    def SetMultilibPolicy(self, multilib_policy: Str):
        """Set the multilib policy settings.

        Possible values are:
        'all' - to install all available packages with compatible architectures
        'best' - for the depsolver to prefer packages which best match the system’s architecture

        Default is 'best'.
        """
        self.implementation.set_multilib_policy(MultilibPolicy(multilib_policy))

    @property
    def Timeout(self) -> Int:
        """Number of seconds before we failed the package installation."""
        return self.implementation.timeout

    @emits_properties_changed
    def SetTimeout(self, timeout: Int):
        """Set the number of seconds before we failed the package installation."""
        self.implementation.set_timeout(timeout)

    @property
    def Retries(self) -> Int:
        """Get how many times the installer should try before failing the installation."""
        return self.implementation.retries

    @emits_properties_changed
    def SetRetries(self, retries: Int):
        """Set how many times the installer should try before failing the installation."""
        self.implementation.set_retries(retries)
