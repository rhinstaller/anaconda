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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import multiprocessing
import shutil
import traceback

import dnf
import dnf.exceptions
import dnf.module.module_base
import dnf.subject
import libdnf.conf

from blivet.size import Size

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import DNF_DEFAULT_TIMEOUT, DNF_DEFAULT_RETRIES
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.core.util import get_os_release_value
from pyanaconda.modules.common.errors.installation import PayloadInstallationError
from pyanaconda.modules.common.errors.payload import UnknownCompsEnvironmentError, \
    UnknownCompsGroupError
from pyanaconda.modules.common.structures.comps import CompsEnvironmentData, CompsGroupData
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData
from pyanaconda.modules.payloads.constants import DNF_REPO_DIRS
from pyanaconda.modules.payloads.payload.dnf.download_progress import DownloadProgress
from pyanaconda.modules.payloads.payload.dnf.transaction_progress import TransactionProgress, \
    process_transaction_progress
from pyanaconda.modules.payloads.payload.dnf.utils import get_product_release_version

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


class DNFManager(object):
    """The abstraction of the DNF base."""

    def __init__(self):
        self.__base = None
        self._ignore_missing_packages = False
        self._ignore_broken_packages = False
        self._download_location = None

    @property
    def _base(self):
        """The DNF base."""
        if self.__base is None:
            self.__base = self._create_base()

        return self.__base

    @staticmethod
    def _create_base():
        """Create a new DNF base."""
        base = dnf.Base()
        base.conf.cachedir = DNF_CACHE_DIR
        base.conf.pluginconfpath = DNF_PLUGINCONF_DIR
        base.conf.logdir = '/tmp/'
        base.conf.releasever = get_product_release_version()
        base.conf.installroot = conf.target.system_root
        base.conf.prepend_installroot('persistdir')
        # Load variables substitutions configuration (rhbz#1920735)
        base.conf.substitutions.update_from_etc("/")

        # Set the platform id based on the /os/release present
        # in the installation environment.
        platform_id = get_os_release_value("PLATFORM_ID")

        if platform_id is not None:
            base.conf.module_platform_id = platform_id

        # Start with an empty comps so we can go ahead and use
        # the environment and group properties. Unset reposdir
        # to ensure dnf has nothing it can check automatically.
        base.conf.reposdir = []
        base.read_comps(arch_filter=True)
        base.conf.reposdir = DNF_REPO_DIRS

        log.debug("The DNF base has been created.")
        return base

    def reset_base(self):
        """Reset the DNF base."""
        self.__base = None
        self._ignore_missing_packages = False
        self._ignore_broken_packages = False
        self._download_location = None
        log.debug("The DNF base has been reset.")

    def configure_base(self, data: PackagesConfigurationData):
        """Configure the DNF base.

        :param data: a packages configuration data
        """
        base = self._base
        base.conf.multilib_policy = data.multilib_policy

        if data.timeout != DNF_DEFAULT_TIMEOUT:
            base.conf.timeout = data.timeout

        if data.retries != DNF_DEFAULT_RETRIES:
            base.conf.retries = data.retries

        self._ignore_missing_packages = data.missing_ignored
        self._ignore_broken_packages = data.broken_ignored

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
        base.conf.install_weak_deps = not data.weakdeps_excluded

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
        return [env.id for env in self._base.comps.environments]

    def _get_environment(self, environment_name):
        """Translate the given environment name to a DNF object.

        :param environment_name: an identifier of an environment
        :return: a DNF object or None
        """
        if not environment_name:
            return None

        return self._base.comps.environment_by_pattern(environment_name)

    def resolve_environment(self, environment_name):
        """Translate the given environment name to a group ID.

        :param environment_name: an identifier of an environment
        :return: a string with the environment ID or None
        """
        env = self._get_environment(environment_name)

        if not env:
            return None

        return env.id

    def is_environment_valid(self, environment_name):
        """Is the given environment valid?

        FIXME: Could we use the resolve_environment method instead?

        :param environment_name: an identifier of an environment
        :return: True or False
        """
        environment_id = self.resolve_environment(environment_name)
        return environment_id in self.environments

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
        data.id = env.id or ""
        data.name = env.ui_name or ""
        data.description = env.ui_description or ""

        optional = {i.name for i in env.option_ids}
        default = {i.name for i in env.option_ids if i.default}

        for grp in self._base.comps.groups:

            if grp.id in optional:
                data.optional_groups.append(grp.id)

            if grp.visible:
                data.visible_groups.append(grp.id)

            if grp.id in default:
                data.default_groups.append(grp.id)

        return data

    @property
    def groups(self):
        """Groups defined in comps.xml file.

        :return: a list of IDs
        """
        return [g.id for g in self._base.comps.groups]

    def _get_group(self, group_name):
        """Translate the given group name into a DNF object.

        :param group_name: an identifier of a group
        :return: a DNF object or None
        """
        return self._base.comps.group_by_pattern(group_name)

    def resolve_group(self, group_name):
        """Translate the given group name into a group ID.

        :param group_name: an identifier of a group
        :return: a string with the group ID or None
        """
        grp = self._get_group(group_name)

        if not grp:
            return None

        return grp.id

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
        data.id = grp.id or ""
        data.name = grp.ui_name or ""
        data.description = grp.ui_description or ""
        return data

    def configure_proxy(self, url):
        """Configure the proxy of the DNF base.

        :param url: a proxy URL or None
        """
        base = self._base

        # Reset the proxy configuration.
        base.conf.proxy = ""
        base.conf.proxy_username = ""
        base.conf.proxy_password = ""

        # No URL is provided.
        if not url:
            return

        # Parse the given URL.
        try:
            proxy = ProxyString(url)
        except ProxyStringError as e:
            log.error("Failed to parse the proxy '%s': %s", url, e)
            return

        # Set the proxy configuration.
        log.info("Using '%s' as a proxy.", url)
        base.conf.proxy = proxy.noauth_url
        base.conf.proxy_username = proxy.username or ""
        base.conf.proxy_password = proxy.password or ""

    def dump_configuration(self):
        """Log the state of the DNF configuration."""
        log.debug("DNF configuration:\n%s", self._base.conf.dump())

    def substitute(self, text):
        """Replace variables with their values.

        Currently supports $releasever and $basearch.

        :param str text: a string to do replacement on
        :return str: a string with substituted variables
        """
        if not text:
            return ""

        return libdnf.conf.ConfigParser.substitute(
            text, self._base.conf.substitutions
        )

    def get_installation_size(self):
        """Calculate the installation size.

        :return: a space required by packages
        :rtype: an instance of Size
        """
        packages_size = Size(0)
        files_number = 0

        if self._base.transaction is None:
            return Size("3000 MiB")

        for tsi in self._base.transaction:
            # Space taken by all files installed by the packages.
            packages_size += tsi.pkg.installsize
            # Number of files installed on the system.
            files_number += len(tsi.pkg.files)

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
        if self._base.transaction is None:
            return Size(0)

        download_size = Size(0)

        # Calculate the download size.
        for tsi in self._base.transaction:
            download_size += tsi.pkg.downloadsize

        # Get the total size. Reserve extra space.
        total_space = download_size + Size("150 MiB")

        log.info("Total download size: %s", total_space)
        return total_space

    def clear_cache(self):
        """Clear the DNF cache."""
        shutil.rmtree(DNF_CACHE_DIR, ignore_errors=True)
        shutil.rmtree(DNF_PLUGINCONF_DIR, ignore_errors=True)
        self._base.reset(sack=True, repos=True)
        log.debug("The DNF cache has been cleared.")

    def is_package_available(self, package_spec):
        """Is the specified package available for the installation?

        :param package_spec: a package spec
        :return: True if the package can be installed, otherwise False
        """
        if not self._base.sack:
            log.warning("There is no metadata about packages!")
            return False

        subject = dnf.subject.Subject(package_spec)
        return bool(subject.get_best_query(self._base.sack))

    def enable_modules(self, module_specs):
        """Mark module streams for enabling.

        Mark module streams matching the module_specs list and also
        all required modular dependencies for enabling. For specs
        that do not specify the stream, the default stream is used.

        :param module_specs: a list of specs
        """
        log.debug("Enabling modules: %s", module_specs)

        try:
            module_base = dnf.module.module_base.ModuleBase(self._base)
            module_base.enable(module_specs)
        except dnf.exceptions.MarkingErrors as e:
            log.debug("Some packages, groups or modules are missing or broken:\n%s", e)
            raise

    def disable_modules(self, module_specs):
        """Mark modules for disabling.

        Mark modules matching the module_specs list for disabling.
        Only the name part of the module specification is relevant.

        :param module_specs: a list of specs to disable
        """
        log.debug("Disabling modules: %s", module_specs)
        try:
            module_base = dnf.module.module_base.ModuleBase(self._base)
            module_base.disable(module_specs)
        except dnf.exceptions.MarkingErrors as e:
            log.debug("Some packages, groups or modules are missing or broken:\n%s", e)
            raise

    def apply_specs(self, include_list, exclude_list):
        """Mark packages, groups and modules for installation.

        :param include_list: a list of specs for inclusion
        :param exclude_list: a list of specs for exclusion
        """
        log.debug("Transaction include list:\n%s", include_list)
        log.debug("Transaction exclude list:\n%s", exclude_list)

        try:
            self._base.install_specs(
                install=include_list,
                exclude=exclude_list,
                strict=not self._ignore_broken_packages
            )
        except dnf.exceptions.MarkingErrors as e:
            log.debug("Some packages, groups or modules are missing or broken:\n%s", e)

            # The transaction is broken. Raise the exception.
            if self._is_transaction_broken(e):
                raise

            # There are some missing specs, but we cannot ignore them.
            if not self._ignore_missing_packages:
                raise

            # Ignore the missing specs.
            log.info("Ignoring missing packages, groups or modules.")

    def _is_transaction_broken(self, exception):
        """Is the DNF transaction broken?

        :param exception: an MarkingErrors exception
        :return: True or False
        """
        return exception.error_group_specs \
            or exception.error_pkg_specs \
            or exception.module_depsolv_errors

    @property
    def download_location(self):
        """The location for the package download."""
        return self._download_location

    def set_download_location(self, path):
        """Set up the location for downloading the packages.

        :param path: a path to the package directory
        """
        for repo in self._base.repos.iter_enabled():
            repo.pkgdir = path

        self._download_location = path

    def download_packages(self, callback):
        """Download the packages.

        :param callback: a callback for progress reporting
        :raise PayloadInstallationError: if the download fails
        """
        packages = self._base.transaction.install_set
        progress = DownloadProgress(callback=callback)

        log.info("Downloading packages to %s.", self.download_location)

        try:
            self._base.download_packages(packages, progress)
        except dnf.exceptions.DownloadError as e:
            msg = "Failed to download the following packages: " + str(e)
            raise PayloadInstallationError(msg) from None

    def install_packages(self, callback, timeout=20):
        """Install the packages.

        :param callback: a callback for progress reporting
        :param timeout: a time out of a failed process in seconds
        :raise PayloadInstallationError: if the installation fails
        """
        queue = multiprocessing.Queue()
        display = TransactionProgress(queue)
        process = multiprocessing.Process(
            target=self._run_transaction,
            args=(self._base, display)
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
    def _run_transaction(base, display):
        """Run the DNF transaction.

        Execute the DNF transaction and catch any errors. An error
        doesn't always raise a BaseException, so presence of 'quit'
        without a preceding 'done' message also indicates a problem.

        :param base: the DNF base
        :param display: the DNF progress-reporting object
        """
        log.debug("Running the transaction...")
        exit_reason = None

        try:
            base.do_transaction(display)
            exit_reason = "DNF done"
        except BaseException as e:  # pylint: disable=broad-except
            log.error("The transaction has ended abruptly: %s", str(e))
            exit_reason = str(e) + traceback.format_exc()
        finally:
            log.debug("The transaction has ended.")
            base.close()  # Always close this base.
            display.quit(exit_reason or "DNF quit")
