#
# The abstraction of the DNF base
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
import multiprocessing
import re
import shutil
import threading
import traceback

import libdnf5
from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    DNF_DEFAULT_REPO_COST,
    DNF_DEFAULT_RETRIES,
    DNF_DEFAULT_TIMEOUT,
    URL_TYPE_BASEURL,
    URL_TYPE_METALINK,
    URL_TYPE_MIRRORLIST,
)
from pyanaconda.core.path import join_paths
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.errors.payload import (
    UnknownCompsEnvironmentError,
    UnknownCompsGroupError,
    UnknownRepositoryError,
)
from pyanaconda.modules.common.structures.comps import (
    CompsEnvironmentData,
    CompsGroupData,
)
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.common.structures.validation import ValidationReport
from pyanaconda.modules.payloads.constants import DNF_REPO_DIRS
from pyanaconda.modules.payloads.payload.dnf.download_progress import DownloadProgress
from pyanaconda.modules.payloads.payload.dnf.transaction_progress import (
    TransactionProgress,
    process_transaction_progress,
)
from pyanaconda.modules.payloads.payload.dnf.utils import (
    calculate_hash,
    get_product_release_version,
    transaction_has_errors,
)

log = get_module_logger(__name__)

DNF_CACHE_DIR = '/tmp/dnf.cache'
DNF_PLUGINCONF_DIR = '/tmp/dnf.pluginconf'

# Bonus to required free space which depends on block size and
# rpm database size estimation. Every file could be aligned to
# fragment size so 4KiB * number_of_files should be a worst case
# scenario. 2KiB for RPM DB was acquired by testing.
#
#   4KiB = max default fragment size
#   2KiB = RPM DB could be taken for a header file
#   6KiB = 4KiB + 2KiB
#
DNF_EXTRA_SIZE_PER_FILE = Size("6 KiB")


class DNFManagerError(Exception):
    """General error for the DNF manager."""


class MetadataError(DNFManagerError):
    """Metadata couldn't be loaded."""


class MissingSpecsError(DNFManagerError):
    """Some packages, groups or modules are missing."""


class BrokenSpecsError(DNFManagerError):
    """Some packages, groups or modules are broken."""


class InvalidSelectionError(DNFManagerError):
    """The software selection couldn't be resolved."""


class DNFManager:
    """The abstraction of the DNF base."""

    def __init__(self):
        self.__base = None
        self.__goal = None

        # Protect access to _base.repos to ensure that the dictionary is not
        # modified while another thread is attempting to iterate over it. The
        # lock only needs to be held during operations that change the number
        # of repos or that iterate over the repos.
        self._lock = threading.RLock()

        self._transaction = None
        self._ignore_missing_packages = False
        self._ignore_broken_packages = False
        self._download_location = None
        self._md_hashes = {}
        self._enabled_system_repositories = []

    @property
    def _base(self):
        """The DNF base."""
        if self.__base is None:
            self.__base = self._create_base()

        return self.__base

    @property
    def _goal(self):
        """The DNF goal."""
        if self.__goal is None:
            self.__goal = libdnf5.base.Goal(self._base)

        return self.__goal

    @classmethod
    def _create_base(cls):
        """Create a new DNF base."""
        base = libdnf5.base.Base()
        base.load_config_from_file()

        config = base.get_config()
        config.reposdir = DNF_REPO_DIRS
        config.cachedir = DNF_CACHE_DIR
        config.pluginconfpath = DNF_PLUGINCONF_DIR
        config.logdir = '/tmp/'

        # Set installer defaults
        config.gpgcheck = False
        config.skip_if_unavailable = False

        # Set the default release version.
        base.get_vars().set("releasever", get_product_release_version())

        # Load variables from the host (rhbz#1920735).
        # Vars are now loaded during base.setup()

        # Set the installation root.
        config.installroot = conf.target.system_root
        config.persistdir = join_paths(
            conf.target.system_root,
            config.persistdir
        )

        log.debug("The DNF base has been created.")
        return base

    def setup_base(self):
        """Set up the DNF base system.

        This method performs necessary initialization based on the current configuration.
        It must be called after:
          - Configuration and variables have been updated
          - Application plugins have been applied
          - Plugins have made any pre-configuration changes

        It must be called before:
          - Any repositories are loaded
          - Any package or advisory queries are created

        :raise: RuntimeError: If called more than once
        """
        self._base.setup()

    def reset_base(self):
        """Reset the DNF base.

        * Close the current DNF base if any.
        * Reset all attributes of the DNF manager.
        * The new DNF base will be created on demand.
        """
        self.__base = None
        self.__goal = None
        self._transaction = None
        self._ignore_missing_packages = False
        self._ignore_broken_packages = False
        self._download_location = None
        self._md_hashes = {}
        self._enabled_system_repositories = []
        log.debug("The DNF base has been reset.")

    def configure_base(self, data: PackagesConfigurationData):
        """Configure the DNF base.

        :param data: a packages configuration data
        """
        config = self._base.get_config()
        config.multilib_policy = data.multilib_policy

        if data.timeout != DNF_DEFAULT_TIMEOUT:
            config.timeout = data.timeout

        if data.retries != DNF_DEFAULT_RETRIES:
            config.retries = data.retries

        self._ignore_missing_packages = data.missing_ignored
        self._ignore_broken_packages = data.broken_ignored

        # FIXME: Set up skip broken?
        # config.skip_broken = data.broken_ignored

        if self._ignore_broken_packages:
            log.warning(
                "\n***********************************************\n"
                "User has requested to skip broken packages. Using "
                "this option may result in an UNUSABLE system! "
                "\n***********************************************\n"
            )

        # Two reasons to turn this off:
        # 1. Minimal installs don't want all the extras this brings in.
        # 2. Installs aren't reproducible due to weak deps. failing silently.
        config.install_weak_deps = not data.weakdeps_excluded

    @property
    def default_environment(self):
        """Default environment.

        :return: an identifier of an environment or None
        """
        environments = self.environments

        if conf.payload.default_environment in environments:
            return conf.payload.default_environment

        if environments:
            return environments[0]

        return None

    @property
    def environments(self):
        """Environments defined in comps.xml file.

        :return: a list of ids
        """
        environments = libdnf5.comps.EnvironmentQuery(self._base)
        return [env.get_environmentid() for env in environments.list()]

    def _get_environment(self, environment_name):
        """Translate the given environment name to a DNF object.

        :param environment_name: an identifier of an environment
        :return libdnf5.comps.Environment: a DNF object or None
        """
        if not environment_name:
            return None

        environments = libdnf5.comps.EnvironmentQuery(self._base)
        environments.filter_name(environment_name)
        return next(iter(environments.list()), None)

    def resolve_environment(self, environment_name):
        """Translate the given environment name to a group ID.

        :param environment_name: an identifier of an environment
        :return: a string with the environment ID or None
        """
        env = self._get_environment(environment_name)

        if not env:
            return None

        return env.get_environmentid()

    def get_environment_data(self, environment_name) -> CompsEnvironmentData:
        """Get the data of the specified environment.

        :param environment_name: an identifier of an environment
        :return: an instance of CompsEnvironmentData
        :raise: UnknownCompsEnvironmentError if no environment is found
        """
        env = self._get_environment(environment_name)

        if not env:
            raise UnknownCompsEnvironmentError(environment_name)

        return self._get_environment_data(env)

    def _get_environment_data(self, env) -> CompsEnvironmentData:
        """Get the environment data.

        :param env: a DNF representation of the environment
        :return: an instance of CompsEnvironmentData
        """
        data = CompsEnvironmentData()
        data.id = env.get_environmentid() or ""
        data.name = env.get_translated_name() or ""
        data.description = env.get_translated_description() or ""

        available_groups = libdnf5.comps.GroupQuery(self._base)
        optional_groups = set(env.get_optional_groups())

        for group in available_groups:
            group_id = group.get_groupid()
            visible = group.get_uservisible()
            default = group.get_default()
            optional = group_id in optional_groups

            if visible:
                data.visible_groups.append(group_id)

            if optional:
                data.optional_groups.append(group_id)

            if optional and default:
                data.default_groups.append(group_id)

        return data

    @property
    def groups(self):
        """Groups defined in comps.xml file.

        :return: a list of IDs
        """
        groups = libdnf5.comps.GroupQuery(self._base)
        return [g.get_groupid() for g in groups.list()]

    def _get_group(self, group_name):
        """Translate the given group name into a DNF object.

        :param group_name: an identifier of a group
        :return libdnf5.comps.Group: a DNF object or None
        """
        groups = libdnf5.comps.GroupQuery(self._base)
        groups.filter_name(group_name)
        return next(iter(groups.list()), None)

    def resolve_group(self, group_name):
        """Translate the given group name into a group ID.

        :param group_name: an identifier of a group
        :return: a string with the group ID or None
        """
        grp = self._get_group(group_name)

        if not grp:
            return None

        return grp.get_groupid()

    def get_group_data(self, group_name) -> CompsGroupData:
        """Get the data of the specified group.

        :param group_name: an identifier of a group
        :return: an instance of CompsGroupData
        :raise: UnknownCompsGroupError if no group is found
        """
        grp = self._get_group(group_name)

        if not grp:
            raise UnknownCompsGroupError(group_name)

        return self._get_group_data(grp)

    @staticmethod
    def _get_group_data(grp) -> CompsGroupData:
        """Get the group data.

        :param grp: a DNF representation of the group
        :return: an instance of CompsGroupData
        """
        data = CompsGroupData()
        data.id = grp.get_groupid() or ""
        data.name = grp.get_translated_name() or ""
        data.description = grp.get_translated_description() or ""
        return data

    def configure_proxy(self, url):
        """Configure the proxy of the DNF base.

        :param url: a proxy URL or None
        """
        config = self._base.get_config()

        # Reset the proxy configuration.
        config.proxy = ""
        config.proxy_username = ""
        config.proxy_password = ""

        # Parse the given URL.
        proxy = self._parse_proxy(url)

        if not proxy:
            return

        # Set the proxy configuration.
        log.info("Using '%s' as a proxy.", url)
        config.proxy = proxy.noauth_url
        config.proxy_username = proxy.username or ""
        config.proxy_password = proxy.password or ""

    def _parse_proxy(self, url):
        """Parse the given proxy URL.

        :param url: a string with the proxy URL
        :return: an instance of ProxyString or None
        """
        if not url:
            return None

        try:
            return ProxyString(url)
        except ProxyStringError as e:
            log.error("Failed to parse the proxy '%s': %s", url, e)

        return None

    def dump_configuration(self):
        """Log the state of the DNF configuration."""
        log.debug(
            "DNF configuration:"
            "\n%s"
            "\nvariables = %s",
            str(self._base.get_config()),
            str(self._base.get_vars()),
        )

    def substitute(self, text):
        """Replace variables with their values.

        Currently supports $releasever and $basearch.

        :param str text: a string to do replacement on
        :return str: a string with substituted variables
        """
        if not text:
            return ""

        variables = self._base.get_vars()
        return variables.substitute(text)

    def configure_substitution(self, release_version):
        """Set up the substitution variables.

        :param release_version: a string for $releasever
        """
        if not release_version:
            return

        variables = self._base.get_vars()
        variables.set("releasever", release_version)
        log.debug("The $releasever variable is set to '%s'.", release_version)

    def get_installation_size(self):
        """Calculate the installation size.

        :return: a space required by packages
        :rtype: an instance of Size
        """
        packages_size = Size(0)
        files_number = 0

        if self._transaction is None:
            return Size("3000 MiB")

        for tspkg in self._transaction.get_transaction_packages():
            # Get a package.
            package = tspkg.get_package()
            # Space taken by all files installed by the packages.
            packages_size += package.get_install_size()
            # Number of files installed on the system.
            files_number += len(package.get_files())

        # Calculate the files size depending on number of files.
        files_size = Size(files_number * DNF_EXTRA_SIZE_PER_FILE)

        # Get the total size. Add another 10% as safeguard.
        total_space = Size((packages_size + files_size) * 1.1)

        log.info("Total install size: %s", total_space)
        return total_space

    def get_download_size(self):
        """Calculate the download size.

        :return: a space required for packages
        :rtype: an instance of Size
        """
        if self._transaction is None:
            return Size(0)

        download_size = Size(0)

        # Calculate the download size.
        for tspkg in self._transaction.get_transaction_packages():
            package = tspkg.get_package()
            download_size += package.get_download_size()

        # Get the total size. Reserve extra space.
        total_space = download_size + Size("150 MiB")

        log.info("Total download size: %s", total_space)
        return total_space

    def clear_cache(self):
        """Clear the DNF cache."""
        self.clear_selection()
        self._enabled_system_repositories = []
        shutil.rmtree(DNF_CACHE_DIR, ignore_errors=True)
        shutil.rmtree(DNF_PLUGINCONF_DIR, ignore_errors=True)

        # FIXME: Reset sacks. Should we just drop the base?
        # self._base.reset(sack=True, repos=True, goal=True)

        log.debug("The DNF cache has been cleared.")

    def is_package_available(self, package_spec):
        """Is the specified package available for the installation?

        :param package_spec: a package spec
        :return: True if the package can be installed, otherwise False
        """
        #if not self._base.sack:
        #    log.warning("There is no metadata about packages!")
        #    return False

        query = libdnf5.rpm.PackageQuery(self._base)
        query.filter_name([package_spec])
        query.filter_available()

        return bool(query)

    def match_available_packages(self, pattern):
        """Find available packages that match the specified pattern.

        :param pattern: a pattern for package names
        :return: a list of matched package names
        """
        #if not self._base.sack:
        #    log.warning("There is no metadata about packages!")
        #    return []

        query = libdnf5.rpm.PackageQuery(self._base)
        query.filter_name([pattern], libdnf5.common.QueryCmp_GLOB)
        query.filter_available()

        return [p.get_name() for p in query]

    def apply_specs(self, include_list, exclude_list):
        """Mark packages, groups and modules for installation.

        :param include_list: a list of specs for inclusion
        :param exclude_list: a list of specs for exclusion
        :raise MissingSpecsError: if there are missing specs
        :raise BrokenSpecsError: if there are broken specs
        """
        log.info("Including specs: %s", include_list)
        for spec in include_list:
            self._goal.add_install(spec)

        log.info("Excluding specs: %s", exclude_list)
        for spec in exclude_list:
            self._goal.add_remove(spec)

    def resolve_selection(self):
        """Resolve the software selection.

        :raise InvalidSelectionError: if the selection cannot be resolved
        """
        report = ValidationReport()

        log.debug("Resolving the software selection.")
        self._transaction = self._goal.resolve()

        # FIXME: Ignore missing packages. Otherwise, report as warning.
        if self._ignore_missing_packages:
            pass

        # FIXME: Ignore broken packages. Otherwise, report as error.
        if self._ignore_broken_packages:
            pass

        # FIXME: If other problems, report all as errors.
        # FIXME: If no problems, but some logs, report all as warnings.
        if self._transaction.get_problems() != libdnf5.base.GoalProblem_NO_PROBLEM:
            for message in self._transaction.get_resolve_logs_as_strings():
                report.error_messages.append(message)

        if report.is_valid():
            log.info("The software selection has been resolved (%d packages selected).",
                     len(self._transaction.get_transaction_packages()))

        log.debug("Resolving has been completed: %s", report)
        return report

    def get_flatpak_refs(self):
        """Determine what Flatpaks need to be preinstalled based on resolved transaction"""
        if self._base.transaction is None:
            return []

        refs = []
        for tsi in self._base.transaction:
            for provide in tsi.pkg.provides:
                m = re.match(r"^flatpak-preinstall\((.*)\)$", str(provide))
                if m:
                    refs.append(m.group(1))

        return refs

    def clear_selection(self):
        """Clear the software selection."""
        self.__goal = None
        self._transaction = None
        log.debug("The software selection has been cleared.")

    @property
    def download_location(self):
        """The location for the package download."""
        return self._download_location

    def set_download_location(self, path):
        """Set up the location for downloading the packages.

        :param path: a path to the package directory
        """
        # FIXME: Reimplement the assignment.
        # for repo in self._base.repos.iter_enabled():
        #    repo.pkgdir = path

        self._download_location = path

    def download_packages(self, callback):
        """Download the packages.

        :param callback: a callback for progress reporting
        :raise PayloadInstallationError: if the download fails
        """
        # Set up the download callbacks.
        progress = DownloadProgress(callback)
        self._set_download_callbacks(progress)

        # Prepare packages for download.
        downloader = libdnf5.repo.PackageDownloader(self._base)
        packages = self._get_download_packages()
        destination = self.download_location

        for package in packages:
            downloader.add(package, destination=destination)

        # Download the packages.
        log.info("Downloading packages to %s.", destination)

        try:
            downloader.download(fail_fast=True, resume=False)
        except RuntimeError as e:
            msg = "Failed to download the following packages: " + str(e)
            raise PayloadInstallationError(msg) from None

    def _set_download_callbacks(self, callbacks):
        """Set up the download callbacks."""
        self._base.set_download_callbacks(
            libdnf5.repo.DownloadCallbacksUniquePtr(callbacks)
        )

    def _get_download_packages(self):
        """Get a list of resolved packages to download."""
        if not self._transaction:
            raise RuntimeError("There is no transaction to use!")

        return [
            tspkg.get_package() for tspkg in self._transaction.get_transaction_packages()
            if libdnf5.base.transaction.transaction_item_action_is_inbound(tspkg.get_action())
        ]

    def install_packages(self, callback, timeout=20):
        """Install the packages.

        Run the DNF transaction in a separate sub-process to isolate
        DNF and RPM from the installation process. See the bug 1614511.

        :param callback: a callback for progress reporting
        :param timeout: a time out of a failed process in seconds
        :raise PayloadInstallationError: if the installation fails
        """
        # SwigPyObjects are not picklable, so force the fork method
        # On Python 3.14+, forkserver is the default (and it pickles)
        context = multiprocessing.get_context(method="fork")
        queue = context.Queue()
        progress = TransactionProgress(queue)
        process = context.Process(
            target=self._run_transaction,
            args=(self._base, progress)
        )

        # Start the transaction.
        log.debug("Starting the transaction process...")
        process.start()

        try:
            # Report the progress.
            process_transaction_progress(queue, callback)

            # Wait for the transaction to end.
            process.join()
        finally:
            # Kill the transaction after the timeout.
            process.join(timeout)
            process.kill()
            log.debug("The transaction process exited with %s.", process.exitcode)

    @staticmethod
    def _run_transaction(base, transaction, progress):
        """Run the DNF transaction.

        Execute the DNF transaction and catch any errors.

        :param base: the DNF base
        :param transaction: the DNF transaction object
        :param progress: the DNF progress-reporting object
        """
        log.debug("Running the transaction...")

        try:
            callbacks = libdnf5.rpm.TransactionCallbacksUniquePtr(progress)
            result = transaction.run(callbacks, description="", user_id=None, comment=None)
            log.debug("The transaction finished with %s", result)
            if transaction_has_errors(transaction):
                progress.error("The transaction process has ended with errors.")
        except BaseException as e:  # pylint: disable=broad-except
            progress.error("The transaction process has ended abruptly: {}\n{}".format(
                str(e), traceback.format_exc()))
        finally:
            log.debug("The transaction has ended.")
            # base.close()  # Always close this base.
            progress.quit("DNF quit")

    @property
    def repositories(self):
        """Available repositories.

        :return: a list of IDs
        """
        with self._lock:
            repositories = libdnf5.repo.RepoQuery(self._base)
            return sorted(r.get_id() for r in repositories)

    @property
    def enabled_repositories(self):
        """Enabled repositories.

        :return: a list of IDs
        """
        with self._lock:
            repositories = libdnf5.repo.RepoQuery(self._base)
            repositories.filter_enabled(True)
            return sorted(r.get_id() for r in repositories)

    def get_matching_repositories(self, pattern):
        """Get a list of repositories that match the specified pattern.

        The pattern can contain Unix shell-style wildcards.
        See: https://docs.python.org/3/library/fnmatch.html

        :param pattern: a pattern for matching the repo IDs
        :return: a list of matching IDs
        """
        with self._lock:
            repositories = libdnf5.repo.RepoQuery(self._base)
            repositories.filter_id(pattern, libdnf5.common.QueryCmp_GLOB)
            return sorted(r.get_id() for r in repositories)

    def _get_repository(self, repo_id):
        """Translate the given repository name to a DNF object.

        :param repo_id: an identifier of a repository
        :return libdnf5.repo.Repo: a DNF object
        :raise: UnknownRepositoryError if no repo is found
        """
        repositories = libdnf5.repo.RepoQuery(self._base)
        repositories.filter_id(repo_id)

        try:
            weak_repo_ref = repositories.get()
            return weak_repo_ref.get()
        except RuntimeError:
            raise UnknownRepositoryError(repo_id) from None

    def add_repository(self, data: RepoConfigurationData):
        """Add a repository.

        If the repository already exists, replace it with a new one.

        :param RepoConfigurationData data: a repo configuration
        """

        with self._lock:
            # Create a new repository.
            repo = self._create_repository(data)

            # FIXME: How to handle existing repositories?
            # Remove an existing repository.
            #
            # if repo.id in self._base.repos:
            #    self._base.repos.pop(repo.id)

            # Add the new repository.
            #self._base.repos.add(repo)

        log.info("Added the '%s' repository: %s", repo.get_id(), repo)

    def _create_repository(self, data: RepoConfigurationData):
        """Create a DNF repository.

        :param RepoConfigurationData data: a repo configuration
        return dnf.repo.Repo: a DNF repository
        """
        repo_sack = self._base.get_repo_sack()
        repo = repo_sack.create_repo(data.name)
        config = repo.get_config()

        # Disable the repo if requested.
        if not data.enabled:
            repo.disable()

        # Set up the repo location.
        url = self.substitute(data.url)

        if data.type == URL_TYPE_BASEURL:
            config.baseurl = [url]

        if data.type == URL_TYPE_MIRRORLIST:
            config.mirrorlist = url

        if data.type == URL_TYPE_METALINK:
            config.metalink = url

        # Set the proxy configuration.
        proxy = self._parse_proxy(data.proxy)

        if proxy:
            config.proxy = proxy.noauth_url
            config.proxy_username = proxy.username or ""
            config.proxy_password = proxy.password or ""

        # Set the repo configuration.
        if data.cost != DNF_DEFAULT_REPO_COST:
            config.cost = data.cost

        if data.included_packages:
            config.includepkgs = data.included_packages

        if data.excluded_packages:
            config.excludepkgs = data.excluded_packages

        # Set up the SSL configuration.
        config.sslverify = conf.payload.verify_ssl and data.ssl_verification_enabled

        if data.ssl_configuration.ca_cert_path:
            config.sslcacert = data.ssl_configuration.ca_cert_path

        if data.ssl_configuration.client_cert_path:
            config.sslclientcert = data.ssl_configuration.client_cert_path

        if data.ssl_configuration.client_key_path:
            config.sslclientkey = data.ssl_configuration.client_key_path

        return repo

    def generate_repo_file(self, data: RepoConfigurationData):
        """Generate a content of the .repo file.

        The content is generated only from the provided data.
        We don't check the configuration of the DNF objects.

        :param RepoConfigurationData data: a repo configuration
        return str: a content of a .repo file
        """
        lines = [
            "[{}]".format(data.name),
            "name = {}".format(data.name),
        ]

        if data.enabled:
            lines.append("enabled = 1")
        else:
            lines.append("enabled = 0")

        # Set up the repo location.
        if data.type == URL_TYPE_BASEURL:
            lines.append("baseurl = {}".format(data.url))

        if data.type == URL_TYPE_MIRRORLIST:
            lines.append("mirrorlist = {}".format(data.url))

        if data.type == URL_TYPE_METALINK:
            lines.append("metalink = {}".format(data.url))

        if not data.ssl_verification_enabled:
            lines.append("sslverify = 0")

        # Set the proxy configuration.
        proxy = self._parse_proxy(data.proxy)

        if proxy:
            lines.append("proxy = {}".format(proxy.noauth_url))

        if proxy and proxy.username:
            lines.append("proxy_username = {}".format(proxy.username))

        if proxy and proxy.password:
            lines.append("proxy_password = {}".format(proxy.password))

        # Set the repo configuration.
        if data.cost != DNF_DEFAULT_REPO_COST:
            lines.append("cost = {}".format(data.cost))

        if data.included_packages:
            lines.append("includepkgs = {}".format(", ".join(data.included_packages)))

        if data.excluded_packages:
            lines.append("excludepkgs = {}".format(", ".join(data.excluded_packages)))

        return "\n".join(lines)

    def set_repository_enabled(self, repo_id, enabled):
        """Enable or disable the specified repository.

        :param repo_id: an identifier of a repository
        :param enabled: True to enable, False to disable
        :raise: UnknownRepositoryError if no repo is found
        """
        repo = self._get_repository(repo_id)

        # Skip if the repository is already set to the right value.
        if repo.is_enabled() == enabled:
            return

        if enabled:
            repo.enable()
            log.info("The '%s' repository is enabled.", repo_id)
        else:
            repo.disable()
            log.info("The '%s' repository is disabled.", repo_id)

    def read_system_repositories(self):
        """Read the system repositories.

        Read all repositories from the installation environment.
        Make a note of which are enabled, and then disable them all.

        Disabled system repositories can be restored later with
        restore_system_repositories.
        """
        with self._lock:
            # Make sure that there are no repositories yet. Otherwise,
            # the code bellow will produce unexpected results.
            if self.repositories:
                raise RuntimeError("The DNF repo cache is not cleared.")

            log.debug("Read system repositories.")
            repo_sack = self._base.get_repo_sack()
            repo_sack.create_repos_from_system_configuration()

            log.debug("Disable system repositories.")
            repositories = libdnf5.repo.RepoQuery(self._base)
            repositories.filter_enabled(True)

            # Remember enabled system repositories.
            self._enabled_system_repositories = sorted(
                r.get_id() for r in repositories
            )

            # Disable all system repositories.
            for repo in repositories:
                repo.disable()

    def restore_system_repositories(self):
        """Restore the system repositories.

        Enable repositories from the installation environment that
        were disabled in read_system_repositories.
        """
        log.debug("Restore system repositories.")

        for repo_id in self._enabled_system_repositories:
            try:
                self.set_repository_enabled(repo_id, True)
            except UnknownRepositoryError:
                log.debug("There is no '%s' repository to enable.", repo_id)

    def load_repositories(self):
        """Load all enabled repositories.

        Load all enabled repositories, including system repositories, and
        process their metadata. It will update the cache that provides
        information about available packages, modules, groups and environments.

        Can be called only once per each RepoSack.
        """
        repo_sack = self._base.get_repo_sack()
        try:
            repo_sack.load_repos(False)
        except RuntimeError as e:
            log.warning(str(e))
            raise MetadataError(str(e)) from None
        log.info("Loaded repositories.")

    def load_repomd_hashes(self):
        """Load a hash of the repomd.xml file for each enabled repository."""
        self._md_hashes = self._get_repomd_hashes()

    def verify_repomd_hashes(self):
        """Verify a hash of the repomd.xml file for each enabled repository.

        This method tests if URL links from active repositories can be reached.
        It is useful when network settings are changed so that we can verify if
        repositories are still reachable.

        :return: True if files haven't changed, otherwise False
        """
        return bool(self._md_hashes and self._md_hashes == self._get_repomd_hashes())

    def _get_repomd_hashes(self):
        """Get a dictionary of repomd.xml hashes.

        :return: a dictionary of repo ids and repomd.xml hashes
        """
        repositories = libdnf5.repo.RepoQuery(self._base)
        repositories.filter_enabled(True)
        md_hashes = {}

        for repo in repositories:
            content = self._get_repomd_content(repo)
            md_hash = calculate_hash(content) if content else None
            md_hashes[repo.get_id()] = md_hash

        log.debug("Loaded repomd.xml hashes: %s", md_hashes)
        return md_hashes

    def _get_repomd_content(self, repo):
        """Get a content of a repomd.xml file.

        :param repo: a DNF repo
        :return: a content of the repomd.xml file
        """
        urls = repo.get_config().baseurl

        for url in urls:
            try:
                repomd_url = "{}/repodata/repomd.xml".format(url)

                # FIXME: Should we use is_repomd_in_sync instead?
                # with self._base.urlopen(repomd_url, repo=repo, mode="w+t") as f:
                #    return f.read()

            except OSError as e:
                log.debug("Can't download repomd.xml from: %s", str(e))
                continue

        return ""
