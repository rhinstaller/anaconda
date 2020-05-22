#
# Kickstart module for DNF payload.
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
from pyanaconda.modules.payloads.base.initialization import SetUpSourcesTask, TearDownSourcesTask
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase
from pyanaconda.modules.payloads.payload.dnf.dnf_interface import DNFInterface
from pyanaconda.modules.payloads.source.factory import SourceFactory

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class DNFModule(PayloadBase):
    """The DNF payload module."""

    def for_publication(self):
        """Get the interface used to publish this source."""
        return DNFInterface(self)

    @property
    def type(self):
        """Get type of this payload.

        :return: value of the payload.base.constants.PayloadType enum
        """
        return PayloadType.DNF

    @property
    def supported_source_types(self):
        """Get list of sources supported by DNF module."""
        return [
            SourceType.CDROM,
            SourceType.HDD,
            SourceType.HMC,
            SourceType.NFS,
            SourceType.REPO_FILES,
            SourceType.CLOSEST_MIRROR,
            SourceType.CDN,
            SourceType.URL
        ]

    def process_kickstart(self, data):
        """Process the kickstart data."""
        source_type = SourceFactory.get_rpm_type_for_kickstart(data)

        if source_type is None:
            return

        source = SourceFactory.create_source(source_type)
        source.process_kickstart(data)
        self.add_source(source)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        for source in self.sources:
            source.setup_kickstart(data)

    def get_repo_configurations(self):
        """Get RepoConfiguration structures for all sources.

        These structures will be used by DNF payload in the main process.

        FIXME: This is a temporary solution. Will be removed after DNF payload logic is moved.

        :return: RepoConfiguration structures for attached sources.
        :rtype: RepoConfigurationData instances
        """
        structures = []

        for source in self.sources:
            structures.append(source.generate_repo_configuration())

        return structures

    def pre_install_with_tasks(self):
        """Execute preparation steps.

        :return: list of tasks
        """
        # TODO: Implement this method
        pass

    def install_with_tasks(self):
        """Install the payload.

        :return: list of tasks
        """
        # TODO: Implement this method
        pass

    def post_install_with_tasks(self):
        """Execute post installation steps.

        :return: list of tasks
        """
        # TODO: Implement this method
        pass

    def set_up_sources_with_task(self):
        """Set up installation sources."""
        # FIXME: Move the implementation to the base class.
        return SetUpSourcesTask(self._sources)

    def tear_down_sources_with_task(self):
        """Tear down installation sources."""
        # FIXME: Move the implementation to the base class.
        return TearDownSourcesTask(self._sources)
