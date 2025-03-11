#
# The SE/HMC source module.
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceState, SourceType
from pyanaconda.modules.payloads.source.hmc.hmc_interface import HMCSourceInterface
from pyanaconda.modules.payloads.source.hmc.initialization import SetUpHMCSourceTask
from pyanaconda.modules.payloads.source.mount_tasks import TearDownMountTask
from pyanaconda.modules.payloads.source.source_base import (
    MountingSourceMixin,
    PayloadSourceBase,
    RPMSourceMixin,
)

log = get_module_logger(__name__)

__all__ = ["HMCSourceModule"]


class HMCSourceModule(PayloadSourceBase, MountingSourceMixin, RPMSourceMixin):
    """The SE/HMC source module."""

    def __repr__(self):
        return "Source(type='HMC')"

    def for_publication(self):
        """Return a DBus representation."""
        return HMCSourceInterface(self)

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.HMC

    @property
    def description(self):
        """Get description of this source."""
        return _("Local media via SE/HMC")

    @property
    def network_required(self):
        """Does the source require a network?

        :return: True or False
        """
        return False

    @property
    def required_space(self):
        """The space required for the installation.

        :return: required size in bytes
        :rtype: int
        """
        return 0

    def get_state(self):
        """Get state of this source."""
        return SourceState.from_bool(self.get_mount_state())

    def generate_repo_configuration(self):
        """Generate RepoConfigurationData structure."""
        return RepoConfigurationData.from_directory(self.mount_point)

    def set_up_with_tasks(self):
        """Set up the installation source for installation.

        :return: list of tasks required for the source setup
        :rtype: [Task]
        """
        return [SetUpHMCSourceTask(self.mount_point)]

    def tear_down_with_tasks(self):
        """Tear down the installation source.

        :return: list of tasks required for the source clean-up
        :rtype: [TearDownMountTask]
        """
        task = TearDownMountTask(self._mount_point)
        return [task]

    def process_kickstart(self, data):
        """Process the kickstart data.

        This will be empty because cdrom KS command does not have any arguments.
        """
        pass

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        data.hmc.seen = True
