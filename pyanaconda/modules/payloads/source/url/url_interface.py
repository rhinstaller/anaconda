#
# DBus interface for payload URL source.
#
# Copyright (C) 2020 Red Hat, Inc.
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
from dasbus.typing import *  # pylint: disable=wildcard-import
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed

from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_URL
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.source.source_base_interface import PayloadSourceBaseInterface


@dbus_interface(PAYLOAD_SOURCE_URL.interface_name)
class URLSourceInterface(PayloadSourceBaseInterface):
    """Interface for the payload URL source."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("RepoConfiguration", self.implementation.repo_configuration_changed)
        self.watch_property("InstallRepoEnabled", self.implementation.install_repo_enabled_changed)

    @property
    def RepoConfiguration(self) -> Structure:
        """Get this repository configuration.

        :rtype: RepoConfigurationData data structure
        """
        return RepoConfigurationData.to_structure(
            self.implementation.repo_configuration
        )

    @emits_properties_changed
    def SetRepoConfiguration(self, repo_configuration: Structure):
        """Set this repository configuration.

        :param repo_configuration: configuration structure of this repository
        :type repo_configuration: RepoConfigurationData structure
        """
        self.implementation.set_repo_configuration(
            RepoConfigurationData.from_structure(repo_configuration)
        )

    @property
    def InstallRepoEnabled(self) -> Bool:
        """Get if the repository should be installed to the target system."""
        return self.implementation.install_repo_enabled

    @emits_properties_changed
    def SetInstallRepoEnabled(self, install_repo_enabled: Bool):
        """Set if the repository should be installed to the target system."""
        self.implementation.set_install_repo_enabled(install_repo_enabled)
