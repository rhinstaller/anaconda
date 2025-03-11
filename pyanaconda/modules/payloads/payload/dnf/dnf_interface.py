#
# DBus interface for DNF payload.
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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.interfaces import PAYLOAD_DNF
from pyanaconda.modules.common.containers import TaskContainer
from pyanaconda.modules.common.structures.comps import (
    CompsEnvironmentData,
    CompsGroupData,
)
from pyanaconda.modules.common.structures.packages import (
    PackagesConfigurationData,
    PackagesSelectionData,
)
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.payload.payload_base_interface import (
    PayloadBaseInterface,
)

__all__ = ["DNFInterface"]


@dbus_interface(PAYLOAD_DNF.interface_name)
class DNFInterface(PayloadBaseInterface):
    """DBus interface for DNF payload module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()
        self.watch_property(
            "Repositories",
            self.implementation.repositories_changed
        )
        self.watch_property(
            "PackagesConfiguration",
            self.implementation.packages_configuration_changed
        )
        self.watch_property(
            "PackagesSelection",
            self.implementation.packages_selection_changed
        )

    @property
    def Repositories(self) -> List[Structure]:
        """The configuration of repositories.

        :return: a list of structures of the type RepoConfigurationData
        """
        return RepoConfigurationData.to_structure_list(
            self.implementation.repositories
        )

    @Repositories.setter
    @emits_properties_changed
    def Repositories(self, data: List[Structure]):
        """Set the configuration of repositories.

        :param data: a list of structures of the type RepoConfigurationData
        """
        self.implementation.set_repositories(
            RepoConfigurationData.from_structure_list(data)
        )

    @property
    def PackagesConfiguration(self) -> Structure:
        """The packages configuration.

        :return: a structure of the type PackagesConfigurationData
        """
        return PackagesConfigurationData.to_structure(
            self.implementation.packages_configuration
        )

    @PackagesConfiguration.setter
    @emits_properties_changed
    def PackagesConfiguration(self, data: Structure):
        """Set the packages configuration.

        :param data: a structure of the type PackagesConfigurationData
        """
        self.implementation.set_packages_configuration(
            PackagesConfigurationData.from_structure(data)
        )

    @property
    def PackagesSelection(self) -> Structure:
        """The packages selection.

        :return: a structure of the type PackagesSelectionData
        """
        return PackagesSelectionData.to_structure(
            self.implementation.packages_selection
        )

    @PackagesSelection.setter
    @emits_properties_changed
    def PackagesSelection(self, data: Structure):
        """Set the packages selection.

        :param: a structure of the type PackagesSelectionData
        """
        self.implementation.set_packages_selection(
            PackagesSelectionData.from_structure(data)
        )

    @property
    def PackagesKickstarted(self) -> Bool:
        """Are the packages set from a kickstart?

        FIXME: This is a temporary property.

        :return: True or False
        """
        return self.implementation.packages_kickstarted

    def GetAvailableRepositories(self) -> List[Str]:
        """Get a list of available repositories.

        :return: a list with names of available repositories
        """
        return self.implementation.get_available_repositories()

    def GetEnabledRepositories(self) -> List[Str]:
        """Get a list of enabled repositories.

        :return: a list with names of enabled repositories
        """
        return self.implementation.get_enabled_repositories()

    def GetDefaultEnvironment(self) -> Str:
        """Get a default environment.

        :return: an identifier of an environment or an empty string
        """
        return self.implementation.get_default_environment()

    def GetEnvironments(self) -> List[Str]:
        """Get a list of environments defined in comps.xml files.

        :return: a list with identifiers of environments
        """
        return self.implementation.get_environments()

    def ResolveEnvironment(self, environment_spec: Str) -> Str:
        """Translate the given specification to an environment identifier.

        :param environment_spec: an environment specification
        :return: an identifier of an environment or an empty string
        """
        return self.implementation.resolve_environment(environment_spec) or ""

    def GetEnvironmentData(self, environment_spec: Str) -> Structure:
        """Get data about the specified environment.

        :param environment_spec: an environment specification
        :return: a data structure defined by CompsEnvironmentData
        :raise UnknownCompsEnvironmentError: if the environment is unknown
        """
        return CompsEnvironmentData.to_structure(
            self.implementation.get_environment_data(environment_spec)
        )

    def ResolveGroup(self, group_spec: Str) -> Str:
        """Translate the given specification into a group identifier.

        :param group_spec: a group specification
        :return: an identifier of a group or an empty string
        """
        return self.implementation.resolve_group(group_spec) or ""

    def GetGroupData(self, group_spec: Str) -> Structure:
        """Get data about the specified group.

        :param group_spec: a group specification
        :return: a data structure defined by CompsGroupData
        :raise UnknownCompsGroupError: if the group is unknown
        """
        return CompsGroupData.to_structure(
            self.implementation.get_group_data(group_spec)
        )

    def VerifyRepomdHashesWithTask(self) -> ObjPath:
        """Verify a hash of the repomd.xml file for each enabled repository with a task.

        This task tests if URL links from active repositories can be reached.
        It is useful when network settings are changed so that we can verify if
        repositories are still reachable. The task returns a validation report.

        :return: a DBus path of the task
        """
        return TaskContainer.to_object_path(
            self.implementation.verify_repomd_hashes_with_task()
        )

    def ValidatePackagesSelectionWithTask(self, data: Structure) -> ObjPath:
        """Validate the specified packages selection.

        Return a task for validation of the software selection.
        The result of the task is a validation report.

        :param data: a structure of the type PackagesSelectionData
        :return: a DBus path of a task
        """
        return TaskContainer.to_object_path(
            self.implementation.validate_packages_selection_with_task(
                PackagesSelectionData.from_structure(data))
        )

    def GetRepoConfigurations(self) -> List[Structure]:
        """Get RepoConfigurationData structures for all attached sources.

        FIXME: This is a temporary solution. Will be removed after DNF payload logic is moved.
        """
        return RepoConfigurationData.to_structure_list(
            self.implementation.get_repo_configurations()
        )

    def MatchAvailablePackages(self, pattern: Str) -> List[Str]:
        """Find available packages that match the specified pattern.

        :param pattern: a pattern for package names
        :return: a list of matched package names
        """
        return self.implementation.match_available_packages(pattern)
