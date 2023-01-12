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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.interfaces import PAYLOAD_DNF
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData, \
    PackagesSelectionData
from pyanaconda.modules.payloads.payload.payload_base_interface import PayloadBaseInterface

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

    def GetRepoConfigurations(self) -> List[Structure]:
        """Get RepoConfigurationData structures for all attached sources.

        FIXME: This is a temporary solution. Will be removed after DNF payload logic is moved.
        """
        return RepoConfigurationData.to_structure_list(
            self.implementation.get_repo_configurations()
        )
