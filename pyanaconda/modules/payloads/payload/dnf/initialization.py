#
# Copyright (C) 2020  Red Hat, Inc.
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
from collections import namedtuple

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import BASE_REPO_NAME, REPO_ORIGIN_SYSTEM
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.payloads.base.initialization import (
    SetUpSourcesTask,
    TearDownSourcesTask,
)
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.payload.dnf.dnf_manager import (
    DNFManager,
    MetadataError,
)
from pyanaconda.modules.payloads.payload.dnf.repositories import (
    create_repository,
    disable_default_repositories,
    enable_existing_repository,
    enable_updates_repositories,
    generate_source_from_repository,
    update_treeinfo_repositories,
)
from pyanaconda.modules.payloads.payload.dnf.tree_info import LoadTreeInfoMetadataTask

log = get_module_logger(__name__)


# The result of the SetUpDNFSourcesTask task.
SetUpDNFSourcesResult = namedtuple(
    "LoadTreeInfoMetadataResult", [
        "dnf_manager",
        "repositories",
        "sources",
    ]
)


class SetUpDNFSourcesTask(SetUpSourcesTask):
    """Set up all the installation source of the DNF payload."""

    def __init__(self, sources, repositories, configuration):
        """Create a new task."""
        super().__init__(sources)
        self._configuration = configuration
        self._repositories = repositories
        self._treeinfo_repositories = []
        self._release_version = None
        self._proxy = None

    @property
    def _source(self):
        return self._sources[0]

    def run(self):
        """Run the task.

        The task returns a named tuple with the following values:

            dnf_manager     a DNF manager with a configured base
            repositories    an updated list of additional repositories
            sources         a list of generated additional sources

        :return SetUpDNFSourcesResult: a result of the task
        """
        # Set up the main source.
        super().run()

        # Process the configuration of the main source.
        repository = self._process_source_metadata(self._source)

        # Process the treeinfo metadata of the main source.
        # Update the treeinfo repositories if any.
        repositories = update_treeinfo_repositories(
            self._repositories,
            self._treeinfo_repositories
        )

        # Configure the DNF manager.
        dnf_manager = self._configure_dnf_manager()

        # Generate and set up additional sources.
        sources = self._generate_additional_sources(
            repositories=repositories,
            substitute=dnf_manager.substitute
        )

        self._set_up_sources(sources)

        # Load the main source.
        self._load_source(dnf_manager, self._source, repository)

        # Load additional sources.
        self._load_additional_sources(dnf_manager, sources, repositories)

        # Check there are enabled repositories.
        self._check_enabled_repositories(dnf_manager)

        # Load repositories.
        self.report_progress(_("Loading repositories..."))
        try:
            self._load_repositories(dnf_manager)
        except MetadataError as e:
            raise SourceSetupError(str(e)) from None

        return SetUpDNFSourcesResult(
            dnf_manager=dnf_manager,
            repositories=repositories,
            sources=sources,
        )

    def _process_source_metadata(self, source):
        """Process metadata of a prepared source.

        Load treeinfo metadata of the specified source
        and process the retrieved results.

        :param source: a prepared source with metadata
        :return: a resolved repository of the source
        """
        if source.type in [SourceType.CDN, SourceType.CLOSEST_MIRROR]:
            return

        # Generate the initial repository configuration.
        repository = source.generate_repo_configuration()

        # Load and process treeinfo metadata of the source if any.
        task = LoadTreeInfoMetadataTask(repository)
        result = task.run()

        if result.repository_data:
            repository = result.repository_data

        if result.treeinfo_repositories:
            self._treeinfo_repositories = result.treeinfo_repositories

        if result.release_version:
            self._release_version = result.release_version

        # Change the default proxy configuration.
        if repository.proxy:
            self._proxy = repository.proxy

        # Rename and enable the chosen repository.
        repository.name = BASE_REPO_NAME
        repository.enabled = True
        return repository

    @staticmethod
    def _generate_additional_sources(repositories, substitute=None):
        """Generate internal sources for additional repositories.

        :param repositories: a list of additional repositories
        :param function substitute: a substitution function
        :return: a list of generated sources
        """
        return [
            generate_source_from_repository(r, substitute)
            for r in repositories
            if r.origin != REPO_ORIGIN_SYSTEM
        ]

    def _configure_dnf_manager(self):
        """Create and configure the DNF manager.

        Create a new instance of the DNF manager and configure it
        based on the provided packages configuration and loaded
        source metadata.

        :return DNFManager: a configured DNF manager
        """
        log.debug("Preparing the DNF base...")
        dnf_manager = DNFManager()
        dnf_manager.clear_cache()
        dnf_manager.configure_base(self._configuration)
        dnf_manager.configure_proxy(self._proxy)
        dnf_manager.configure_substitution(self._release_version)
        dnf_manager.setup_base()
        dnf_manager.dump_configuration()
        dnf_manager.read_system_repositories()
        return dnf_manager

    def _load_source(self, dnf_manager, source, repository=None):
        """Load the prepared source.

        Create, enable or disabled repositories based on the configuration
        of the prepared source and its resolved repository data if any.

        :param DNFManager dnf_manager: a configured DNF manager
        :param source: a prepared installation source
        :param repository: a resolved repository of the source
        """
        if source.type == SourceType.CDN:
            dnf_manager.restore_system_repositories()
            disable_default_repositories(dnf_manager)

        elif source.type == SourceType.CLOSEST_MIRROR:
            dnf_manager.restore_system_repositories()
            enable_updates_repositories(dnf_manager, source.updates_enabled)
            disable_default_repositories(dnf_manager)

        else:
            repository = repository or source.generate_repo_configuration()
            create_repository(dnf_manager, repository)

    def _load_additional_sources(self, dnf_manager, sources, repositories):
        """Load additional sources and handle system repositories.

        :param DNFManager dnf_manager: a configured DNF manager
        :param sources: a list of prepared additional sources
        :param repositories: a list of updated additional repositories
        """
        for source in sources:
            self._load_source(dnf_manager, source)

        for repository in repositories:
            if repository.origin == REPO_ORIGIN_SYSTEM:
                enable_existing_repository(dnf_manager, repository)

    @staticmethod
    def _check_enabled_repositories(dnf_manager):
        """Check there is at least one enabled repository.

        :param DNFManager dnf_manager: a configured DNF manager
        """
        if not dnf_manager.enabled_repositories:
            raise SourceSetupError(_("No repository is configured."))

    @staticmethod
    def _load_repositories(dnf_manager):
        """Load metadata of configured repositories.

        Can be called only once per each RepoSack.

        :param DNFManager dnf_manager: a configured DNF manager
        """
        dnf_manager.load_repositories()
        dnf_manager.load_repomd_hashes()


class TearDownDNFSourcesTask(TearDownSourcesTask):
    """Tear down all the installation sources of the DNF payload."""

    def __init__(self, sources, dnf_manager):
        """Create a new task."""
        super().__init__(sources)
        self._dnf_manager = dnf_manager

    def run(self):
        """Run the task."""
        try:
            # Tear down the sources.
            super().run()
        finally:
            # Close the DNF base.
            self._dnf_manager.reset_base()
