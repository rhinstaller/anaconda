#
# DBus structures for the packages data.
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
from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.core.constants import (
    DNF_DEFAULT_RETRIES,
    DNF_DEFAULT_TIMEOUT,
    MULTILIB_POLICY_BEST,
    RPM_LANGUAGES_ALL,
)

__all__ = ["PackagesConfigurationData", "PackagesSelectionData"]


class PackagesSelectionData(DBusData):
    """Structure for the selection of packages."""

    def __init__(self):
        self._core_group_enabled = True
        self._default_environment_enabled = False
        self._environment = ""
        self._groups = []
        self._groups_package_types = {}
        self._excluded_groups = []
        self._packages = []
        self._excluded_packages = []
        self._modules = []
        self._disabled_modules = []

    @property
    def core_group_enabled(self) -> Bool:
        """Should the core group be installed?

        :return: True if the core group should be installed
        :rtype: bool
        """
        return self._core_group_enabled

    @core_group_enabled.setter
    def core_group_enabled(self, value: Bool):
        self._core_group_enabled = value

    @property
    def default_environment_enabled(self) -> Bool:
        """Should a default environment be installed?

        :return: True if the default package set should be installed
        :rtype: bool
        """
        return self._default_environment_enabled

    @default_environment_enabled.setter
    def default_environment_enabled(self, value: Bool):
        self._default_environment_enabled = value

    @property
    def environment(self) -> Str:
        """The environment marked for installation.

        Examples of environments:

            Fedora Server Edition
            workstation-product-environment

        :return: a full environment name (as given in the comps.xml file)
        :rtype: str
        """
        return self._environment

    @environment.setter
    def environment(self, value: Str):
        self._environment = value

    @property
    def groups(self) -> List[Str]:
        """A list of groups and modules marked for installation.

        Examples of groups:

            Administration Tools
            3d-printing

        Examples of modules:

            django:1.6
            postgresql:9.6/server

        :return: a list of groups and modules
        :rtype: [str]
        """
        return self._groups

    @groups.setter
    def groups(self, value: List[Str]):
        self._groups = value

    @property
    def groups_package_types(self) -> Dict[Str, List[Str]]:
        """Types of packages in the groups that should be installed.

        Supported package types:

            mandatory
            default
            conditional
            optional

        :return: a dictionary that maps groups to package types
        :rtype: {str: [str]}
        """
        return self._groups_package_types

    @groups_package_types.setter
    def groups_package_types(self, value: Dict[Str, List[Str]]):
        self._groups_package_types = value

    @property
    def excluded_groups(self) -> List[Str]:
        """A list of groups and modules excluded from the installation.

        :return: a list of excluded groups and modules
        :rtype: [str]
        """
        return self._excluded_groups

    @excluded_groups.setter
    def excluded_groups(self, value: List[Str]):
        self._excluded_groups = value

    @property
    def packages(self) -> List[Str]:
        """A list of packages marked for installation.

        Examples of packages:

            vim
            kde-i18n-*

        :return: a list of packages
        :rtype: [str]
        """
        return self._packages

    @packages.setter
    def packages(self, value: List[Str]):
        self._packages = value

    @property
    def excluded_packages(self) -> List[Str]:
        """A list of packages excluded from the installation.

        :return: a list of excluded packages
        :rtype: [str]
        """
        return self._excluded_packages

    @excluded_packages.setter
    def excluded_packages(self, value: List[Str]):
        self._excluded_packages = value

    @property
    def modules(self) -> List[Str]:
        """A list of modules to enable.

        Supported format of values:

            NAME         Specify the module name.
            NAME:STREAM  Specify the module and stream names.

        :return: a list of modules
        :rtype: [str]
        """
        return self._modules

    @modules.setter
    def modules(self, value: List[Str]):
        self._modules = value

    @property
    def disabled_modules(self) -> List[Str]:
        """A list of modules to disable.

        Supported format of values:

            NAME         Specify the module name.
            NAME:STREAM  Specify the module and stream names.

        :return: a list of modules
        :rtype: [str]
        """
        return self._disabled_modules

    @disabled_modules.setter
    def disabled_modules(self, value: List[Str]):
        self._disabled_modules = value


class PackagesConfigurationData(DBusData):
    """Structure for the configuration of packages."""

    def __init__(self):
        self._docs_excluded = False
        self._weakdeps_excluded = False
        self._missing_ignored = False
        self._broken_ignored = False
        self._languages = RPM_LANGUAGES_ALL
        self._multilib_policy = MULTILIB_POLICY_BEST
        self._timeout = DNF_DEFAULT_TIMEOUT
        self._retries = DNF_DEFAULT_RETRIES

    @property
    def docs_excluded(self) -> Bool:
        """Should the documentation be excluded during the installation?

        :return: True if packages documentation shouldn't be installed
        :rtype: bool
        """
        return self._docs_excluded

    @docs_excluded.setter
    def docs_excluded(self, value: Bool):
        self._docs_excluded = value

    @property
    def weakdeps_excluded(self) -> Bool:
        """Should the packages weak dependencies be excluded from the installation?

        :return: True if the weak dependencies should be excluded
        :rtype: bool
        """
        return self._weakdeps_excluded

    @weakdeps_excluded.setter
    def weakdeps_excluded(self, value: Bool):
        self._weakdeps_excluded = value

    @property
    def missing_ignored(self) -> Bool:
        """Ignore packages that are missing from the repositories.

        :return: True if missing packages should be ignored
        :rtype: bool
        """
        return self._missing_ignored

    @missing_ignored.setter
    def missing_ignored(self, value: Bool):
        self._missing_ignored = value

    @property
    def broken_ignored(self) -> Bool:
        """Ignore packages that have conflicts with other packages.

        :return: True if broken packages should be ignored
        :rtype: bool
        """
        return self._broken_ignored

    @broken_ignored.setter
    def broken_ignored(self, value: Bool):
        self._broken_ignored = value

    @property
    def languages(self) -> Str:
        """Languages marked for installation.

        This option does not specify what package groups should
        be installed. Instead, it controls which translation files
        from individual packages should be installed by setting
        RPM macros.

        There are special values for this property supported:

            none  - Use 'nil' in the rpm macro.
            all   - Do not change the default settings.

        In case multiple languages are specified they are separated
        by ':' in the string returned. See the `%_install_langs`
        macro at https://github.com/rpm-software-management/rpm.

        :return: 'none' or 'all' or a list of languages separated by ':'
        :rtype: str
        """
        return self._languages

    @languages.setter
    def languages(self, value: Str):
        """Languages marked for installation."""
        self._languages = value

    @property
    def multilib_policy(self) -> Str:
        """The multilib policy.

        Supported values:

            all     Install all available packages with compatible
                    architectures.
            best    Prefer packages which best match the system's
                    architecture.

        :return: 'all' or 'best'
        :rtype: str
        """
        return self._multilib_policy

    @multilib_policy.setter
    def multilib_policy(self, value: Str):
        self._multilib_policy = value

    @property
    def timeout(self) -> Int:
        """Timeout how long to try before failing during the package installation.

        :return: a number of seconds to wait (or -1 by default)
        :rtype: int
        """
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        self._timeout = value

    @property
    def retries(self) -> Int:
        """How many times to try before failing during the package installation.

        :return: a number of how many times to try (or -1 by default)
        :rtype: int
        """
        return self._retries

    @retries.setter
    def retries(self, value: Int):
        self._retries = value
