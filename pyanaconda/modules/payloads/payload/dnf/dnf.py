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
from pykickstart.constants import GROUP_REQUIRED, GROUP_ALL, KS_MISSING_IGNORE, KS_BROKEN_IGNORE, \
    GROUP_DEFAULT

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import RPM_LANGUAGES_NONE, MULTILIB_POLICY_ALL, \
    DNF_DEFAULT_TIMEOUT, DNF_DEFAULT_RETRIES, GROUP_PACKAGE_TYPES_ALL, \
    GROUP_PACKAGE_TYPES_REQUIRED, RPM_LANGUAGES_ALL
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData, \
    PackagesSelectionData
from pyanaconda.modules.payloads.constants import PayloadType, SourceType
from pyanaconda.modules.payloads.kickstart import convert_ks_repo_to_repo_data, \
    convert_repo_data_to_ks_repo
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
        self._process_kickstart_packages_selection(data)
        self._process_kickstart_packages_configuration(data)

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

    def _process_kickstart_packages_selection(self, data):
        """Process the kickstart packages selection."""
        selection = PackagesSelectionData()
        selection.core_group_enabled = not data.packages.nocore
        selection.default_environment_enabled = data.packages.default

        if data.packages.environment is not None:
            selection.environment = data.packages.environment

        selection.packages = data.packages.packageList
        selection.excluded_packages = data.packages.excludedList

        for group in data.packages.groupList:
            selection.groups.append(group.name)

            if group.include == GROUP_ALL:
                selection.groups_package_types[group.name] = GROUP_PACKAGE_TYPES_ALL

            if group.include == GROUP_REQUIRED:
                selection.groups_package_types[group.name] = GROUP_PACKAGE_TYPES_REQUIRED

        for group in data.packages.excludedGroupList:
            selection.excluded_groups.append(group.name)

        for module in data.module.dataList():
            name = module.name

            if module.stream:
                name += ":" + module.stream

            if module.enable:
                selection.modules.append(name)
            else:
                selection.disabled_modules.append(name)

        self.set_packages_selection(selection)
        self.set_packages_kickstarted(data.packages.seen)

    def _process_kickstart_packages_configuration(self, data):
        """Process the kickstart packages configuration."""
        configuration = PackagesConfigurationData()
        configuration.docs_excluded = data.packages.excludeDocs
        configuration.weakdeps_excluded = data.packages.excludeWeakdeps

        if data.packages.handleMissing == KS_MISSING_IGNORE:
            configuration.missing_ignored = True

        if data.packages.handleBroken == KS_BROKEN_IGNORE:
            configuration.broken_ignored = True

        if data.packages.instLangs == "":
            configuration.languages = RPM_LANGUAGES_NONE
        elif data.packages.instLangs is not None:
            configuration.languages = data.packages.instLangs

        if data.packages.multiLib:
            configuration.multilib_policy = MULTILIB_POLICY_ALL

        if data.packages.timeout is not None:
            configuration.timeout = data.packages.timeout

        if data.packages.retries is not None:
            configuration.retries = data.packages.retries

        self.set_packages_configuration(configuration)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""
        self._set_up_kickstart_sources(data)
        self._set_up_kickstart_repositories(data)
        self._set_up_kickstart_packages_selection(data)
        self._set_up_kickstart_packages_configuration(data)

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

    def _set_up_kickstart_packages_selection(self, data):
        """Set up the kickstart packages selection."""
        selection = self.packages_selection

        # The empty packages section won't be printed without seen set to True.
        data.packages.seen = True
        data.packages.nocore = not selection.core_group_enabled
        data.packages.default = selection.default_environment_enabled

        if selection.environment:
            data.packages.environment = selection.environment

        data.packages.packageList = selection.packages
        data.packages.excludedList = selection.excluded_packages

        for group_name in selection.groups:
            package_types = selection.groups_package_types.get(
                group_name, []
            )
            group_include = GROUP_DEFAULT

            if set(package_types) == set(GROUP_PACKAGE_TYPES_ALL):
                group_include = GROUP_ALL

            if set(package_types) == set(GROUP_PACKAGE_TYPES_REQUIRED):
                group_include = GROUP_REQUIRED

            group = data.packages.create_group(
                name=group_name,
                include=group_include
            )
            data.packages.groupList.append(group)

        for group_name in selection.excluded_groups:
            group = data.packages.create_group(
                name=group_name
            )
            data.packages.excludedGroupList.append(group)

        for name in selection.modules:
            self._set_up_kickstart_module_data(data, name)

        for name in selection.disabled_modules:
            self._set_up_kickstart_module_data(data, name, False)

    @staticmethod
    def _set_up_kickstart_module_data(data, name, enabled=True):
        """Set up the kickstart data for the module command."""
        names = name.split(":", maxsplit=1) + [""]

        module = data.ModuleData()
        module.name = names[0]
        module.stream = names[1]
        module.enable = enabled

        data.module.dataList().append(module)

    def _set_up_kickstart_packages_configuration(self, data):
        """Set up the kickstart packages configuration."""
        configuration = self.packages_configuration

        data.packages.excludeDocs = configuration.docs_excluded
        data.packages.excludeWeakdeps = configuration.weakdeps_excluded

        if configuration.missing_ignored:
            data.packages.handleMissing = KS_MISSING_IGNORE

        if configuration.broken_ignored:
            data.packages.handleBroken = KS_BROKEN_IGNORE

        if configuration.languages == RPM_LANGUAGES_NONE:
            data.packages.instLangs = ""
        elif configuration.languages != RPM_LANGUAGES_ALL:
            data.packages.instLangs = configuration.languages

        if configuration.multilib_policy == MULTILIB_POLICY_ALL:
            data.packages.multiLib = True

        if configuration.timeout != DNF_DEFAULT_TIMEOUT:
            data.packages.timeout = configuration.timeout

        if configuration.retries != DNF_DEFAULT_RETRIES:
            data.packages.retries = configuration.retries

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
