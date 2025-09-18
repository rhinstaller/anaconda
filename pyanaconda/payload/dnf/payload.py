# DNF/rpm software payload management.
#
# Copyright (C) 2019  Red Hat, Inc.
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
from dasbus.typing import unwrap_variant

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    DRACUT_REPO_DIR,
    MULTILIB_POLICY_ALL,
    PAYLOAD_TYPE_DNF,
    SOURCE_TYPE_CDROM,
    SOURCE_TYPE_HDD,
    SOURCE_TYPE_HMC,
    SOURCE_TYPE_NFS,
    SOURCE_TYPE_REPO_PATH,
    SOURCE_TYPE_URL,
)
from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.modules.common.errors.payload import SourceSetupError
from pyanaconda.modules.common.structures.packages import (
    PackagesConfigurationData,
    PackagesSelectionData,
)
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.modules.common.task import sync_run_task
from pyanaconda.modules.payloads.payload.dnf.repositories import (
    generate_driver_disk_repositories,
)
from pyanaconda.modules.payloads.source.utils import verify_valid_repository
from pyanaconda.payload.manager import NonCriticalSourceSetupError
from pyanaconda.payload.manager import payloadMgr as payload_manager
from pyanaconda.payload.migrated import MigratedDBusPayload
from pyanaconda.ui.lib.payload import (
    create_source,
    set_source,
    set_up_sources,
    tear_down_sources,
)

__all__ = ["DNFPayload"]

log = get_module_logger(__name__)


class DNFPayload(MigratedDBusPayload):
    """The DNF payload class."""

    def __init__(self, data):
        super().__init__()
        self._software_validation_required = True

    @property
    def type(self):
        """The DBus type of the payload."""
        return PAYLOAD_TYPE_DNF

    def set_from_opts(self, opts):
        """Set the payload from the Anaconda cmdline options.

        :param opts: a namespace of options
        """
        self._set_default_source(opts)
        self._set_source_configuration_from_opts(opts)
        self._set_additional_repos_from_opts(opts)
        self._generate_driver_disk_repositories()
        self._set_packages_from_opts(opts)

    def _set_default_source(self, opts):
        """Set the default source.

        Set the source based on opts.method if it isn't already set
        - opts.method is currently set by command line/boot options.

        Otherwise, use the source provided at a specific mount point
        by Dracut if there is any.

        Otherwise, use the default source specified in the Anaconda
        configuration files as a fallback.

        In summary, the installer chooses a default source of the DNF
        payload based on data processed in this order:

        1. Kickstart file
        2. Boot options or command line options
        3. Installation image mounted by Dracut
        4. Anaconda configuration file

        """
        if self.proxy.Sources:
            log.debug("The DNF source is already set.")

        elif opts.method:
            log.debug("Use the DNF source from opts.")
            source_proxy = self._create_source_from_url(opts.method)
            set_source(self.proxy, source_proxy)

        elif verify_valid_repository(DRACUT_REPO_DIR):
            log.debug("Use the DNF source from Dracut.")
            source_proxy = create_source(SOURCE_TYPE_REPO_PATH)
            source_proxy.Path = DRACUT_REPO_DIR
            set_source(self.proxy, source_proxy)

        else:
            log.debug("Use the DNF source from the Anaconda configuration file.")
            source_proxy = create_source(conf.payload.default_source)
            set_source(self.proxy, source_proxy)

    @staticmethod
    def _create_source_from_url(url):
        """Create a new source for the specified URL.

        :param str url: the URL of the source
        :return: a DBus proxy of the new source
        :raise ValueError: if the URL is unsupported
        """
        if url.startswith("cdrom"):
            return create_source(SOURCE_TYPE_CDROM)

        if url.startswith("hmc"):
            return create_source(SOURCE_TYPE_HMC)

        if url.startswith("nfs:"):
            source_proxy = create_source(SOURCE_TYPE_NFS)

            source_proxy.Configuration = \
                RepoConfigurationData.to_structure(
                    RepoConfigurationData.from_url(url)
                )

            return source_proxy

        if url.startswith("hd:"):
            source_proxy = create_source(SOURCE_TYPE_HDD)

            source_proxy.Configuration = \
                RepoConfigurationData.to_structure(
                    RepoConfigurationData.from_url(url)
                )

            return source_proxy

        if any(map(url.startswith, ["http:", "https:", "ftp:", "file:"])):
            source_proxy = create_source(SOURCE_TYPE_URL)

            source_proxy.Configuration = \
                RepoConfigurationData.to_structure(
                    RepoConfigurationData.from_url(url)
                )

            return source_proxy

        raise ValueError("Unknown type of the installation source: {}".format(url))

    def _set_source_configuration_from_opts(self, opts):
        """Configure the source based on the Anaconda options."""
        source_proxy = self.get_source_proxy()

        if source_proxy.Type == SOURCE_TYPE_URL:
            # Get the repo configuration.
            repo_configuration = RepoConfigurationData.from_structure(
                source_proxy.Configuration
            )

            if opts.proxy:
                repo_configuration.proxy = opts.proxy

            if not conf.payload.verify_ssl:
                repo_configuration.ssl_verification_enabled = conf.payload.verify_ssl

            # Update the repo configuration.
            source_proxy.Configuration = \
                RepoConfigurationData.to_structure(repo_configuration)

    def _set_additional_repos_from_opts(self, opts):
        """Set additional repositories based on the Anaconda options."""
        repositories = self.get_repo_configurations()
        existing_names = {r.name for r in repositories}
        additional_repositories = []

        for repo_name, repo_url in opts.addRepo:
            # Check the name of the repository.
            is_unique = repo_name not in existing_names

            if not is_unique:
                log.warning("Repository name %s is not unique. Only the first repo will "
                            "be used!", repo_name)
                continue

            # Generate the configuration data for the new repository.
            data = RepoConfigurationData()
            data.name = repo_name
            data.url = repo_url

            existing_names.add(data.name)
            additional_repositories.append(data)

        if not additional_repositories:
            return

        repositories.extend(additional_repositories)
        self.set_repo_configurations(repositories)

    def _generate_driver_disk_repositories(self):
        """Append generated driver disk repositories."""
        dd_repositories = generate_driver_disk_repositories()

        if not dd_repositories:
            return

        repositories = self.get_repo_configurations()
        repositories.extend(dd_repositories)
        self.set_repo_configurations(repositories)

    def _set_packages_from_opts(self, opts):
        """Configure packages based on the Anaconda options."""
        if opts.multiLib:
            configuration = self.get_packages_configuration()
            configuration.multilib_policy = MULTILIB_POLICY_ALL
            self.set_packages_configuration(configuration)

    def get_repo_configurations(self) -> [RepoConfigurationData]:
        """Get a list of DBus repo configurations."""
        return RepoConfigurationData.from_structure_list(
            self.proxy.Repositories
        )

    def set_repo_configurations(self, data_list: [RepoConfigurationData]):
        """Set a list of DBus repo configurations."""
        self.proxy.Repositories = \
            RepoConfigurationData.to_structure_list(data_list)

    def get_packages_configuration(self) -> PackagesConfigurationData:
        """Get the DBus data with the packages configuration."""
        return PackagesConfigurationData.from_structure(
            self.proxy.PackagesConfiguration
        )

    def set_packages_configuration(self, data: PackagesConfigurationData):
        """Set the DBus data with the packages configuration."""
        self.proxy.PackagesConfiguration = \
            PackagesConfigurationData.to_structure(data)

    def get_packages_selection(self) -> PackagesSelectionData:
        """Get the DBus data with the packages selection."""
        return PackagesSelectionData.from_structure(
            self.proxy.PackagesSelection
        )

    def set_packages_selection(self, data: PackagesSelectionData):
        """Set the DBus data with the packages selection."""
        self.proxy.PackagesSelection = \
            PackagesSelectionData.to_structure(data)

    def is_ready(self):
        """Is the payload ready?"""
        if payload_manager.is_running:
            return False

        return bool(self.proxy.GetEnabledRepositories())

    # pylint: disable=arguments-differ
    def setup(self, report_progress, only_on_change=False):
        """Set up the payload.

        :param function report_progress: a callback for a progress reporting
        :param bool only_on_change: restart thread only if existing repositories changed
        """
        # Skip the setup if possible.
        if self._skip_if_no_changed_repositories(only_on_change):
            return

        # It will be necessary to validate the software selection again.
        self._software_validation_required = True

        try:
            log.debug("Tearing down sources")
            tear_down_sources(self.proxy)

            log.debug("Setting up sources")
            set_up_sources(self.proxy)

        except SourceSetupError as e:
            # Errors of the DNF payload can be handled in the UI.
            raise NonCriticalSourceSetupError(str(e)) from e

    def _skip_if_no_changed_repositories(self, only_on_change):
        """Have the repositories changed since the last setup?

        If the repositories haven't changed and we are allowed
        to skip the payload setup, return True. Otherwise,
        return False.
        """
        if not only_on_change:
            return False

        # Run the validation task.
        log.debug("Testing repositories availability")
        task_path = self.proxy.VerifyRepomdHashesWithTask()
        task_proxy = PAYLOADS.get_proxy(task_path)
        sync_run_task(task_proxy)

        # Get the validation report.
        result = unwrap_variant(task_proxy.GetResult())
        report = ValidationReport.from_structure(result)

        if not report.is_valid():
            return False

        log.debug("Payload won't be restarted, repositories are still available.")
        return True

    @property
    def software_validation_required(self):
        """Is it necessary to validate the software selection?"""
        return self._software_validation_required

    def check_software_selection(self, selection):
        """Check the software selection.

        :param selection: a packages selection data
        :return ValidationReport: a validation report
        """
        log.debug("Checking the software selection...")

        # Run the validation task.
        task_path = self.proxy.ValidatePackagesSelectionWithTask(
            PackagesSelectionData.to_structure(selection)
        )
        task_proxy = PAYLOADS.get_proxy(task_path)
        sync_run_task(task_proxy)

        # Get the validation report.
        result = unwrap_variant(task_proxy.GetResult())
        report = ValidationReport.from_structure(result)

        # Start side payload processing if report is valid
        if report.is_valid():
            side_payload_path = self.proxy.SidePayload
            if side_payload_path:
                side_payload = PAYLOADS.get_proxy(side_payload_path)
                side_task_proxy = PAYLOADS.get_proxy(side_payload.CalculateSizeWithTask())
                sync_run_task(side_task_proxy)

        # This validation is no longer required.
        self._software_validation_required = False

        log.debug("The selection has been checked: %s", report)
        return report
