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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.packages import (
    PackagesConfigurationData,
    PackagesSelectionData,
)
from pyanaconda.modules.payloads.base.utils import calculate_required_space
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.kickstart import (
    convert_ks_data_to_packages_configuration,
    convert_ks_data_to_packages_selection,
    convert_ks_repo_to_repo_data,
    convert_packages_configuration_to_ksdata,
    convert_packages_selection_to_ksdata,
    convert_repo_data_to_ks_repo,
)
from pyanaconda.modules.payloads.payload.dnf.dnf_interface import DNFInterface
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import DNFManager
from pyanaconda.modules.payloads.payload.dnf.initialization import (
    SetUpDNFSourcesResult,
    SetUpDNFSourcesTask,
    TearDownDNFSourcesTask,
)
from pyanaconda.modules.payloads.payload.dnf.installation import (
    CleanUpDownloadLocationTask,
    DownloadPackagesTask,
    ImportRPMKeysTask,
    InstallPackagesTask,
    PrepareDownloadLocationTask,
    ResolvePackagesTask,
    SetRPMMacrosTask,
    UpdateDNFConfigurationTask,
    WriteRepositoriesTask,
)
from pyanaconda.modules.payloads.payload.dnf.tear_down import ResetDNFManagerTask
from pyanaconda.modules.payloads.payload.dnf.utils import (
    collect_installation_devices,
    protect_installation_devices,
)
from pyanaconda.modules.payloads.payload.dnf.validation import (
    CheckPackagesSelectionTask,
    VerifyRepomdHashesTask,
)
from pyanaconda.modules.payloads.payload.payload_base import PayloadBase
from pyanaconda.modules.payloads.source.factory import SourceFactory
from pyanaconda.modules.payloads.source.utils import has_network_protocol

# Set up the modules logger.
log = get_module_logger(__name__)

__all__ = ["DNFModule"]


class DNFModule(PayloadBase):
    """The DNF payload module."""

    def __init__(self):
        """Create a DNF module."""
        super().__init__()
        self._dnf_manager = DNFManager()
        self._internal_sources = []

        self._repositories = []
        self.repositories_changed = Signal()

        self._packages_configuration = PackagesConfigurationData()
        self.packages_configuration_changed = Signal()

        self._packages_selection = PackagesSelectionData()
        self.packages_selection_changed = Signal()

        self._packages_kickstarted = False

        # Protect installation sources.
        self._protected_devices = set()
        self.sources_changed.connect(self._update_protected_devices)
        self.repositories_changed.connect(self._update_protected_devices)

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
            SourceType.REPO_PATH,
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
        return self._dnf_manager

    def _set_dnf_manager(self, dnf_manager):
        """Set the DNF manager of this payload."""
        self._dnf_manager = dnf_manager
        log.debug("The DNF manager is set.")

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

    def _update_protected_devices(self):
        """Protect devices specified by installation sources."""
        previous_devices = self._protected_devices
        current_devices = collect_installation_devices(
            self.sources,
            self.repositories,
        )
        protect_installation_devices(
            previous_devices,
            current_devices,
        )
        self._protected_devices = current_devices

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

    def _refresh_side_payload_selection(self):
        """Set new resolved software selection to side payload."""
        if self.side_payload and self.side_payload.type == PayloadType.FLATPAK:
            self.side_payload.set_sources(self.sources)
            self.side_payload.set_flatpak_refs(self.get_flatpak_refs())

    def validate_packages_selection_with_task(self, data):
        """Validate the specified packages selection.

        Return a task for validation of the software selection.
        The result of the task is a validation report.

        :param PackagesSelectionData data: a packages selection
        :return: a task
        """
        task = CheckPackagesSelectionTask(
            dnf_manager=self.dnf_manager,
            selection=data,
        )
        task.succeeded_signal.connect(self._refresh_side_payload_selection)
        return task

    def calculate_required_space(self):
        """Calculate space required for the installation.

        :return: required size in bytes
        :rtype: int
        """
        required_space = calculate_required_space(self._dnf_manager.get_download_size(),
                                                  self._dnf_manager.get_installation_size())
        return required_space.get_bytes()

    def needs_flatpak_side_payload(self):
        return True

    def get_flatpak_refs(self):
        """Get the list of Flatpak refs to install.

        :return: list of Flatpak refs
        """
        return self._dnf_manager.get_flatpak_refs()

    def get_repo_configurations(self):
        """Get RepoConfiguration structures for all sources.

        These structures will be used by DNF payload in the main process.

        FIXME: This is a temporary solution. Will be removed after DNF payload logic is moved.

        :return: RepoConfiguration structures for attached sources.
        :rtype: RepoConfigurationData instances
        """
        return list(filter(None, [s.generate_repo_configuration() for s in self.sources]))

    def set_up_sources_with_task(self):
        """Set up installation sources."""
        task = SetUpDNFSourcesTask(
            sources=self.sources,
            repositories=self.repositories,
            configuration=self.packages_configuration,
        )
        task.succeeded_signal.connect(
            lambda: self._set_up_sources_on_success(task.get_result())
        )
        return task

    def _set_up_sources_on_success(self, result: SetUpDNFSourcesResult):
        """Update the module based on the configured sources."""
        self._set_dnf_manager(result.dnf_manager)
        self.set_repositories(result.repositories)
        self._internal_sources += result.sources

    def tear_down_sources_with_task(self):
        """Tear down installation sources."""
        return TearDownDNFSourcesTask(
            dnf_manager=self.dnf_manager,
            sources=self._internal_sources + self.sources
        )

    def install_with_tasks(self):
        """Install the payload.

        :return: list of tasks
        """
        tasks = [
            SetRPMMacrosTask(
                configuration=self.packages_configuration
            ),
            ResolvePackagesTask(
                dnf_manager=self.dnf_manager,
                selection=self.packages_selection,
                configuration=self.packages_configuration,
            ),
            PrepareDownloadLocationTask(
                dnf_manager=self.dnf_manager,
            ),
            DownloadPackagesTask(
                dnf_manager=self.dnf_manager,
            ),
            InstallPackagesTask(
                dnf_manager=self.dnf_manager,
            ),
            CleanUpDownloadLocationTask(
                dnf_manager=self.dnf_manager,
            ),
        ]

        self._collect_kernels_on_success(InstallPackagesTask, tasks)
        return tasks

    def _collect_kernels_on_success(self, task_class, tasks):
        """Collect kernel version lists from a task specified by its class.

        Find an instance of the specified task class that should return
        a kernel version list if successful. Connect to its signal and
        update the kernel version list of the module when the task is
        finished.

        :param task_class: a class of a scheduled task
        :param tasks: a list of scheduled tasks
        """
        for task in tasks:
            if isinstance(task, task_class):
                task.succeeded_signal.connect(
                    lambda t=task: self.set_kernel_version_list(t.get_result())
                )

    def post_install_with_tasks(self):
        """Execute post installation steps.

        :return: list of tasks
        """
        return [
            WriteRepositoriesTask(
                sysroot=conf.target.system_root,
                dnf_manager=self.dnf_manager,
                repositories=self.repositories,
            ),
            ImportRPMKeysTask(
                sysroot=conf.target.system_root,
                gpg_keys=conf.payload.default_rpm_gpg_keys
            ),
            UpdateDNFConfigurationTask(
                sysroot=conf.target.system_root,
                configuration=self.packages_configuration,
                dnf_manager=self.dnf_manager,
            ),
            ResetDNFManagerTask(
                dnf_manager=self.dnf_manager
            )
        ]

    def match_available_packages(self, pattern):
        """Find available packages that match the specified pattern.

        :param pattern: a pattern for package names
        :return: a list of matched package names
        """
        return self.dnf_manager.match_available_packages(pattern)
