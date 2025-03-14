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
import os
import shutil

import rpm

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    MULTILIB_POLICY_BEST,
    RPM_LANGUAGES_ALL,
    RPM_LANGUAGES_NONE,
)
from pyanaconda.core.i18n import _
from pyanaconda.core.path import join_paths, make_directories
from pyanaconda.modules.common.errors.installation import (
    NonCriticalInstallationError,
    PayloadInstallationError,
)
from pyanaconda.modules.common.structures.packages import PackagesConfigurationData
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.base.utils import pick_download_location
from pyanaconda.modules.payloads.payload.dnf.requirements import (
    apply_requirements,
    collect_dnf_requirements,
    collect_driver_disk_requirements,
    collect_language_requirements,
    collect_platform_requirements,
    collect_remote_requirements,
)
from pyanaconda.modules.payloads.payload.dnf.utils import (
    get_kernel_version_list,
)
from pyanaconda.modules.payloads.payload.dnf.validation import (
    CheckPackagesSelectionTask,
)

log = get_module_logger(__name__)

DNF_PACKAGE_CACHE_DIR_SUFFIX = 'dnf.package.cache'


class SetRPMMacrosTask(Task):
    """Installation task to set RPM macros."""

    def __init__(self, configuration: PackagesConfigurationData):
        """Create a task.

        :param configuration: a packages configuration data
        """
        super().__init__()
        self._data = configuration
        self._macros = []

    @property
    def name(self):
        """The name of the task."""
        return "Set RPM macros"

    def run(self):
        """Run the task."""
        self._macros = self._collect_macros(self._data)
        self._install_macros(self._macros)

    def _collect_macros(self, data: PackagesConfigurationData):
        """Collect the RPM macros."""
        macros = []

        # nofsync speeds things up at the risk of rpmdb data loss in a crash.
        # But if we crash mid-install you're boned anyway, so who cares?
        macros.append(('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'))

        if data.docs_excluded:
            macros.append(('_excludedocs', '1'))

        if data.languages == RPM_LANGUAGES_NONE:
            macros.append(('_install_langs', '%{nil}'))
        elif data.languages != RPM_LANGUAGES_ALL:
            macros.append(('_install_langs', data.languages))

        if conf.security.selinux:
            for d in ["/etc/selinux/targeted/contexts/files",
                      "/etc/security/selinux/src/policy",
                      "/etc/security/selinux"]:
                f = d + "/file_contexts"
                if os.access(f, os.R_OK):
                    macros.append(('__file_context_path', f))
                    break
        else:
            macros.append(('__file_context_path', '%{nil}'))

        return macros

    def _install_macros(self, macros):
        """Add RPM macros to the global transaction environment."""
        for name, value in macros:
            log.debug("Set '%s' to '%s'.", name, value)
            rpm.addMacro(name, value)  # pylint: disable=no-member


class ResolvePackagesTask(CheckPackagesSelectionTask):
    """Installation task to resolve the software selection."""

    def __init__(self, dnf_manager, selection, configuration):
        """Resolve packages task

        :param dnf_manager: a DNF manager
        :param selection: a package selection data
        :param configuration: a packages configuration data
        """
        super().__init__(dnf_manager, selection)
        self._dnf_manager = dnf_manager
        self._selection = selection
        self._configuration = configuration

    @property
    def name(self):
        """The name of the task."""
        return "Resolve packages"

    def run(self):
        """Run the task.

        :raise PayloadInstallationError: if the selection cannot be resolved
        :raise NonCriticalInstallationError: if the selection is resolved with warnings
        """
        report = super().run()

        if report.error_messages:
            message = "\n\n".join(report.error_messages)
            log.error("The packages couldn't be resolved:\n\n%s", message)
            raise PayloadInstallationError(message)

        if report.warning_messages:
            message = "\n\n".join(report.warning_messages)
            log.warning("The packages were resolved with warnings:\n\n%s", message)
            raise NonCriticalInstallationError(message)

    @property
    def _requirements(self):
        """Requirements for installing packages and groups.

        :return: a list of requirements
        """
        return collect_remote_requirements() \
            + collect_language_requirements(self._dnf_manager) \
            + collect_platform_requirements(self._dnf_manager) \
            + collect_dnf_requirements(self._dnf_manager, self._configuration) \
            + collect_driver_disk_requirements()

    def _collect_required_specs(self):
        """Collect specs for the required software."""
        super()._collect_required_specs()

        # Apply requirements.
        apply_requirements(self._requirements, self._include_list, self._exclude_list)


class PrepareDownloadLocationTask(Task):
    """The installation task for setting up the download location."""

    def __init__(self, dnf_manager):
        """Create a new task.

        :param dnf_manager: a DNF manager
        """
        super().__init__()
        self._dnf_manager = dnf_manager

    @property
    def name(self):
        return "Prepare the package download"

    def run(self):
        """Run the task.

        :return: a path of the download location
        """
        path = pick_download_location(self._dnf_manager.get_download_size(),
                                      self._dnf_manager.get_installation_size(),
                                      DNF_PACKAGE_CACHE_DIR_SUFFIX)

        if os.path.exists(path):
            log.info("Removing existing package download location: %s", path)
            shutil.rmtree(path)

        self._dnf_manager.set_download_location(path)
        return path


class CleanUpDownloadLocationTask(Task):
    """The installation task for cleaning up the download location."""

    def __init__(self, dnf_manager):
        """Create a new task.

        :param dnf_manager: a DNF manager
        """
        super().__init__()
        self._dnf_manager = dnf_manager

    @property
    def name(self):
        return "Remove downloaded packages"

    def run(self):
        """Run the task.

        Some installation sources, such as NFS, don't need to download packages to
        local storage, so the download location might not always exist. See the bug
        1193121 for more information.
        """
        path = self._dnf_manager.download_location

        if not os.path.exists(path):
            log.warning("The download location %s doesn't exist.", path)
            return

        log.info("Removing downloaded packages from %s.", path)
        shutil.rmtree(path)


class DownloadPackagesTask(Task):
    """The installation task for downloading the packages."""

    def __init__(self, dnf_manager):
        """Create a new task.

        :param dnf_manager: a DNF manager
        """
        super().__init__()
        self._dnf_manager = dnf_manager

    @property
    def name(self):
        return "Download packages"

    def run(self):
        self.report_progress(_("Downloading packages"))
        self._dnf_manager.download_packages(self.report_progress)


class InstallPackagesTask(Task):
    """The installation task for installing the packages."""

    def __init__(self, dnf_manager):
        """Create a new task.

        :param dnf_manager: a DNF manager
        """
        super().__init__()
        self._dnf_manager = dnf_manager

    @property
    def name(self):
        return "Install packages"

    def run(self):
        """Run the task.

        :return: a list of installed kernel versions
        """
        self.report_progress(_("Preparing transaction from installation source"))
        self._dnf_manager.install_packages(self.report_progress)
        return get_kernel_version_list()


class WriteRepositoriesTask(Task):
    """The installation task for writing repositories on the target system."""

    def __init__(self, sysroot, dnf_manager, repositories):
        """Create a new task.

        :param str sysroot: a path to the system root
        :param DNFManager dnf_manager: a DNF manager
        :param [RepoConfigurationData] repositories: a list of repo data
        """
        super().__init__()
        self._sysroot = sysroot
        self._dnf_manager = dnf_manager
        self._repositories = repositories

    @property
    def name(self):
        return "Write repositories"

    def run(self):
        """Run the task."""
        for repo in self._repositories:
            if not self._can_write_repo(repo):
                log.debug("Couldn't write %s.repo to the target system.", repo.name)
                continue

            log.info("Writing %s.repo to the target system.", repo.name)
            content = self._dnf_manager.generate_repo_file(repo)
            self._write_repo_file(repo.name, content)

    def _can_write_repo(self, repo):
        """Can we write the specified repository to the target system?

        * Skip repositories that are not allowed to be installed.
        * Skip repositories from the installation environment.
        * Support only http, https and ftp protocols.
        """
        supported_protocols = [
            "http:",
            "https:",
            "ftp:"
        ]

        if not repo.installation_enabled:
            log.debug("Installation of the repository is not allowed.")
            return False

        if not repo.name:
            log.debug("The name of the repository is not specified.")
            return False

        if not repo.url:
            log.debug("The URL of the repository is not specified.")
            return False

        if not any(repo.url.startswith(p) for p in supported_protocols):
            log.debug("The repository uses an unsupported protocol.")
            return False

        return True

    def _write_repo_file(self, repo_name, content):
        """Write the specified content into a repo file."""
        repo_dir = join_paths(
            self._sysroot,
            "etc/yum.repos.d/"
        )
        make_directories(repo_dir)

        repo_path = join_paths(
            repo_dir,
            repo_name + ".repo"
        )
        with open(repo_path, "w") as f:
            f.write(content.strip() + "\n")


class ImportRPMKeysTask(Task):
    """The installation task for import of the RPM keys."""

    def __init__(self, sysroot, gpg_keys):
        """Create a new task.

        :param sysroot: a path to the system root
        :param gpg_keys: a list of gpg keys to import
        """
        super().__init__()
        self._sysroot = sysroot
        self._gpg_keys = gpg_keys

    @property
    def name(self):
        return "Import RPM keys"

    def run(self):
        """Run the task"""
        if not self._gpg_keys:
            log.debug("No GPG keys to import.")
            return

        if not os.path.exists(self._sysroot + "/usr/bin/rpm"):
            log.error(
                "Can not import GPG keys to RPM database because "
                "the 'rpm' executable is missing on the target "
                "system. The following keys were not imported:\n%s",
                "\n".join(self._gpg_keys)
            )
            return

        # Get substitutions for variables.
        # TODO: replace the interpolation with DNF once possible
        basearch = os.uname().machine
        releasever = util.get_os_release_value("VERSION_ID", sysroot=self._sysroot) or ""

        # Import GPG keys to RPM database.
        for key in self._gpg_keys:
            key = key.replace("$releasever", releasever).replace("$basearch", basearch)

            log.info("Importing GPG key to RPM database: %s", key)
            rc = util.execWithRedirect("rpm", ["--import", key], root=self._sysroot)

            if rc:
                log.error("Failed to import the GPG key.")


class UpdateDNFConfigurationTask(Task):
    """The installation task to update the dnf.conf file."""

    def __init__(self, sysroot, configuration: PackagesConfigurationData, dnf_manager):
        """Create a new task.

        :param sysroot: a path to the system root
        :param configuration: a packages configuration data
        """
        super().__init__()
        self._sysroot = sysroot
        self._data = configuration
        self._dnf_manager = dnf_manager

    @property
    def name(self):
        return "Update DNF configuration"

    def run(self):
        """Run the task."""
        if self._data.multilib_policy != MULTILIB_POLICY_BEST:
            self._set_option("multilib_policy", self._data.multilib_policy)

    def _set_option(self, option, value):
        """Set a configuration option.

        :param option: a name of the option
        :param value: a value of the option
        """
        log.debug("Setting '%s' to '%s'.", option, value)

        cmd = "dnf"
        if self._dnf_manager.is_package_available("dnf5"):
            args = [
                "config-manager",
                "setopt",
                "{}={}".format(option, value)
            ]
        else:
            args = [
                "config-manager",
                "--save",
                "--setopt={}={}".format(option, value)
            ]

        try:
            rc = util.execWithRedirect(cmd, args, root=self._sysroot)
        except OSError as e:
            log.warning("Couldn't update the DNF configuration: %s", e)
            return

        if rc != 0:
            log.warning("Failed to update the DNF configuration (%s).", rc)
            return
