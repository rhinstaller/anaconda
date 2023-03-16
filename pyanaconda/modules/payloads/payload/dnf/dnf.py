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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData, \
    PackagesSelectionData
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.kickstart import convert_ks_repo_to_repo_data, \
    convert_repo_data_to_ks_repo, convert_ks_data_to_packages_selection, \
    convert_packages_selection_to_ksdata, convert_ks_data_to_packages_configuration, \
    convert_packages_configuration_to_ksdata
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.modules.payloads.payload.dnf.validation import CheckPackagesSelectionTask, \
    VerifyRepomdHashesTask
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase
from pyanaconda.modules.payloads.payload.dnf.dnf_interface import DNFInterface
from pyanaconda.modules.payloads.source.factory import SourceFactory
from pyanaconda.modules.payloads.source.utils import has_network_protocol

log = get_module_logger(__name__)

__all__ = ["DNFModule"]


class DNFModule(PayloadBase):
    """The DNF payload module."""

    def __init__(self):
        """Create a DNF module."""
        super().__init__()
        self._dnf_manager = None

        self._repositories = []
        self.repositories_changed = Signal()

        self._packages_configuration = PackagesConfigurationData()
        self.packages_configuration_changed = Signal()

        self._packages_selection = PackagesSelectionData()
        self.packages_selection_changed = Signal()

        self._packages_kickstarted = False

    def for_publication(self):
        """Get the interface used to publish this source."""
        return DNFInterface(self)

    @property
    def type(self):
        """Type of this payload."""
        return PayloadType.DNF

    @property
    def default_source_type(self):
        """Type of the default source."""
        return SourceType(conf.payload.default_source)

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

    def is_network_required(self):
        """Do the sources and repositories require a network?

        :return: True or False
        """
        # Check sources.
        if super().is_network_required():
            return True

        # Check repositories.
        for data in self.repositories:
            if data.enabled and has_network_protocol(data.url):
                return True

        return False

    @property
    def dnf_manager(self):
        """The DNF manager of this payload."""
        if not self._dnf_manager:
            self._dnf_manager = DNFManager()

        return self._dnf_manager

    @property
    def repositories(self):
        """The configuration of repositories.

        :return [RepoConfigurationData]: a list of repo configurations
        """
        return self._repositories

    def set_repositories(self, data):
        """Set the configuration of repositories.

        :param [RepoConfigurationData] data: a list of repo configurations
        """
        self._repositories = data
        self.repositories_changed.emit()
        log.debug("Repositories are set to: %s", data)

    @property
    def packages_configuration(self):
        """The packages configuration.

        :return: an instance of PackagesConfigurationData
        """
        return self._packages_configuration

    def set_packages_configuration(self, data):
        """Set the packages configuration.

        :param data: an instance of PackagesConfigurationData
        """
        self._packages_configuration = data
        self.packages_configuration_changed.emit()
        log.debug("Packages configuration is set to '%s'.", data)

    @property
    def packages_selection(self):
        """The packages selection.

        :return: an instance of PackagesSelectionData
        """
        return self._packages_selection

    def set_packages_selection(self, data):
        """Set the packages selection.

        :param data: an instance of PackagesSelectionData
        """
        self._packages_selection = data
        self.packages_selection_changed.emit()
        log.debug("Packages selection is set to '%s'.", data)

    @property
    def packages_kickstarted(self):
        """Are the packages set from a kickstart?

        FIXME: This is a temporary property.

        :return: True or False
        """
        return self._packages_kickstarted

    def set_packages_kickstarted(self, value):
        """Are the packages set from a kickstart?"""
        self._packages_kickstarted = value
        log.debug("Are the packages set from a kickstart? %s", value)

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self._process_kickstart_sources(data)
        self._process_kickstart_repositories(data)
        self._process_kickstart_packages(data)

    def _process_kickstart_sources(self, data):
        """Process the kickstart sources."""
        source_type = SourceFactory.get_rpm_type_for_kickstart(data)

        if source_type is None:
            return

        source = SourceFactory.create_source(source_type)
        source.process_kickstart(data)
        self.add_source(source)

    def _process_kickstart_repositories(self, data):
        """Process the kickstart repositories."""
        repositories = list(map(
            convert_ks_repo_to_repo_data,
            data.repo.dataList()
        ))
        self.set_repositories(repositories)

    def _process_kickstart_packages(self, data):
        """Process the kickstart packages."""
        selection = convert_ks_data_to_packages_selection(data)
        self.set_packages_selection(selection)
        self.set_packages_kickstarted(data.packages.seen)

        configuration = convert_ks_data_to_packages_configuration(data)
        self.set_packages_configuration(configuration)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        self._set_up_kickstart_sources(data)
        self._set_up_kickstart_repositories(data)
        self._set_up_kickstart_packages(data)

    def _set_up_kickstart_sources(self, data):
        """Set up the kickstart sources."""
        for source in self.sources:
            source.setup_kickstart(data)

    def _set_up_kickstart_repositories(self, data):
        """Set up the kickstart repositories."""
        # Don't include disabled repositories.
        enabled_repositories = list(filter(
            lambda r: r.enabled, self.repositories
        ))
        data.repo.repoList = list(map(
            convert_repo_data_to_ks_repo,
            enabled_repositories
        ))

    def _set_up_kickstart_packages(self, data):
        """Set up the kickstart packages selection."""
        convert_packages_selection_to_ksdata(self.packages_selection, data)
        convert_packages_configuration_to_ksdata(self.packages_configuration, data)

    def get_available_repositories(self):
        """Get a list of available repositories.

        :return: a list with names of available repositories
        """
        return self.dnf_manager.repositories

    def get_enabled_repositories(self):
        """Get a list of enabled repositories.

        :return: a list with names of enabled repositories
        """
        return self.dnf_manager.enabled_repositories

    def get_default_environment(self):
        """Get a default environment.

        :return: an identifier of an environment or an empty string
        """
        return self.dnf_manager.default_environment or ""

    def get_environments(self):
        """Get a list of environments defined in comps.xml files.

        :return: a list with identifiers of environments
        """
        return self.dnf_manager.environments

    def resolve_environment(self, environment_spec):
        """Translate the given specification to an environment identifier.

        :param environment_spec: an environment specification
        :return: an identifier of an environment or an empty string
        """
        return self.dnf_manager.resolve_environment(environment_spec) or ""

    def get_environment_data(self, environment_spec):
        """Get data about the specified environment.

        :param environment_spec: an environment specification
        :return CompsEnvironmentData: the related environment data
        :raise UnknownCompsEnvironmentError: if the environment is unknown
        """
        return self.dnf_manager.get_environment_data(environment_spec)

    def resolve_group(self, group_spec):
        """Translate the given specification into a group identifier.

        :param group_spec: a group specification
        :return: an identifier of a group or an empty string
        """
        return self.dnf_manager.resolve_group(group_spec) or ""

    def get_group_data(self, group_spec):
        """Get data about the specified group.

        :param group_spec: a specification of a group
        :return CompsGroupData: the related group data
        :raise: UnknownCompsGroupError if the group is unknown
        """
        return self.dnf_manager.get_group_data(group_spec)

    def verify_repomd_hashes_with_task(self):
        """Verify a hash of the repomd.xml file for each enabled repository with a task.

        This method tests if URL links from active repositories can be reached.
        It is useful when network settings are changed so that we can verify if
        repositories are still reachable. The task returns a validation report.

        :return: a task
        """
        return VerifyRepomdHashesTask(self.dnf_manager)

    def validate_packages_selection_with_task(self, data):
        """Validate the specified packages selection.

        Return a task for validation of the software selection.
        The result of the task is a validation report.

        :param PackagesSelectionData data: a packages selection
        :return: a task
        """
        return CheckPackagesSelectionTask(
            dnf_manager=self.dnf_manager,
            selection=data,
        )

    def get_repo_configurations(self):
        """Get RepoConfiguration structures for all sources.

        These structures will be used by DNF payload in the main process.

        FIXME: This is a temporary solution. Will be removed after DNF payload logic is moved.

        :return: RepoConfiguration structures for attached sources.
        :rtype: RepoConfigurationData instances
        """
        return list(filter(None, [s.generate_repo_configuration() for s in self.sources]))

    def install_with_tasks(self):
        """Install the payload.

        :return: list of tasks
        """
        # TODO: Implement this method
        return []

    def post_install_with_tasks(self):
        """Execute post installation steps.

        :return: list of tasks
        """
        # TODO: Implement this method
        return []
