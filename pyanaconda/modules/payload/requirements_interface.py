#
# DBus interface for Payload requirements.
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
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.objects import REQUIREMENTS
from pyanaconda.modules.common.base import ModuleInterfaceTemplate
from pyanaconda.modules.common.structures.payload import Requirement


@dbus_interface(REQUIREMENTS.interface_name)
class RequirementsInterface(ModuleInterfaceTemplate):
    """DBus interface for Requirements payload module."""

    def AddPackages(self, package_ids: List[Str], reason: Str, strong: Bool):
        """Add packages required for the reason.

        If a package is already required, the new reason will be
        added and the strength of the requirement will be updated.

        :param package_ids: names of packages to be added
        :param reason: description of reason for adding the packages
        :param strong: is the requirement strong (ie is not satisfying it fatal?)
        """
        self.implementation.add_packages(package_ids, reason, strong)

    def AddGroups(self, group_ids: List[Str], reason: Str, strong: Bool):
        """Add groups required for the reason.

        If a group is already required, the new reason will be
        added and the strength of the requirement will be updated.

        :param group_ids: ids of groups to be added
        :param reason: descripiton of reason for adding the groups
        :param strong: is the requirement strong
        """
        self.implementation.add_groups(group_ids, reason, strong)

    @property
    def Packages(self) -> List[Structure]:
        """List of package requirements.

        return: list of package requirements
        rtype: list of Requirement
        """
        requirements = self.implementation.packages
        return Requirement.to_structure_list(requirements)

    @property
    def Groups(self) -> List[Structure]:
        """List of group requirements.

        return: list of group requirements
        rtype: list of Requirement
        """
        requirements = self.implementation.groups
        return Requirement.to_structure_list(requirements)

    @property
    def Empty(self) -> Bool:
        """Are requirements empty?

        return: True if there are no requirements, else False
        """
        return self.implementation.empty
