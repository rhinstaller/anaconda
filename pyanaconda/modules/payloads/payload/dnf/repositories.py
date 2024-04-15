#
# Copyright (C) 2022  Red Hat, Inc.
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
import copy
import os
from glob import glob
from itertools import count

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import REPO_ORIGIN_SYSTEM, REPO_ORIGIN_TREEINFO
from pyanaconda.core.i18n import _
from pyanaconda.core.path import join_paths
from pyanaconda.core.product import get_product_is_final_release
from pyanaconda.core.util import execWithRedirect
from pyanaconda.modules.common.errors.payload import (
    SourceSetupError,
    UnknownRepositoryError,
)
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.factory import SourceFactory

log = get_module_logger(__name__)


def generate_driver_disk_repositories(path="/run/install"):
    """Generate driver disk repositories.

    Drivers are loaded by anaconda-dracut. Their repos are copied
    into /run/install/DD-X where X is a number starting at 1.

    :param path: a path to the file with a package list
    :return: a list of repo configuration data
    """
    repositories = []

    if not conf.system.can_use_driver_disks:
        log.info("Skipping driver disk repository generation.")
        return repositories

    # Iterate over all driver disk repositories.
    for i in count(start=1):
        repo_name = "DD-{}".format(i)
        repo_path = join_paths(path, repo_name)

        # Is there a directory of this name?
        if not os.path.isdir(repo_path):
            break

        # Are there RPMs in this directory?
        if not glob(repo_path + "/*rpm"):
            continue

        # Create a repository if there are no repodata.
        if not os.path.isdir(join_paths(repo_path, "repodata")):
            log.info("Running createrepo on %s", repo_path)
            execWithRedirect("createrepo_c", [repo_path])

        # Generate a repo configuration.
        repo = RepoConfigurationData()
        repo.name = repo_name
        repo.url = "file://" + repo_path
        repositories.append(repo)

    return repositories


def update_treeinfo_repositories(repositories, treeinfo_repositories):
    """Update the treeinfo repositories.

    :param [RepoConfigurationData] repositories: a list of repositories to update
    :param [RepoConfigurationData] treeinfo_repositories: a list of treeinfo repositories
    :return [RepoConfigurationData]: an updated list of repositories
    """
    log.debug("Update treeinfo repositories...")

    # Find treeinfo repositories that were previously disabled and
    # disable newly generated treeinfo repositories of the same name.
    disabled = {
        r.name for r in repositories
        if r.origin == REPO_ORIGIN_TREEINFO and not r.enabled
    }

    for r in treeinfo_repositories:
        if r.name in disabled:
            r.enabled = False

    # Exclude every treeinfo repository with the same url as a repository
    # specified by a user. We don't want to create duplicate sources.
    existing = {
        r.url for r in repositories
        if r.origin != REPO_ORIGIN_TREEINFO and r.url
    }

    treeinfo_repositories = [
        r for r in treeinfo_repositories
        if r.url not in existing
    ]

    # Update the list of repositories. Remove all previous treeinfo
    # repositories and append the newly generated treeinfo repositories.
    log.debug("Remove all treeinfo repositories.")

    repositories = [
        r for r in repositories
        if r.origin != REPO_ORIGIN_TREEINFO
    ]

    for r in treeinfo_repositories:
        log.debug("Add the '%s' treeinfo repository: %s", r.name, r)
        repositories.append(r)

    # Return the updated list of repositories.
    return repositories


def generate_source_from_repository(repository, substitute=None):
    """Generate an installation source from the specified repository.

    :param RepoConfigurationData repository: an additional repository
    :param function substitute: a substitution function for urls
    :return PayloadSourceBase: a generated installation source
    """
    repository = copy.deepcopy(repository)
    substitute = substitute or (lambda x: x)

    if repository.origin == REPO_ORIGIN_SYSTEM:
        msg = "Unsupported origin of the '{name}' repository: {origin}"
        raise ValueError(msg.format(name=repository.name, origin=repository.origin))

    if not repository.url:
        msg = _("The '{name}' repository has no mirror, baseurl or metalink set.")
        raise SourceSetupError(msg.format(name=repository.name))

    if any(repository.url.startswith(p) for p in ["file:", "http:", "https:", "ftp:"]):
        source = SourceFactory.create_source(SourceType.URL)
        source.set_configuration(repository)
        return source

    if repository.url.startswith("nfs:"):
        source = SourceFactory.create_source(SourceType.NFS)
        repository.url = substitute(repository.url)
        source.set_configuration(repository)
        return source

    if repository.url.startswith("hd:"):
        source = SourceFactory.create_source(SourceType.HDD)
        source.set_configuration(repository)
        return source

    msg = _("The '{name}' repository uses an unsupported protocol.")
    raise SourceSetupError(msg.format(name=repository.name))


def enable_updates_repositories(dnf_manager, enabled):
    """Enable or disable updates repositories.

    :param DNFManager dnf_manager: a configured DNF manager
    :param bool enabled: True to enable the updates repositories, otherwise False
    """
    log.debug("Enable or disable updates repositories.")
    enable_matching_repositories(dnf_manager, conf.payload.updates_repositories, enabled)


def disable_default_repositories(dnf_manager):
    """Disable some repositories by default.

    Some repositories should be disabled by default based on
    the Anaconda configuration file and the current product.

    :param DNFManager dnf_manager: a configured DNF manager
    """
    log.debug("Disable repositories based on the Anaconda configuration file.")
    enable_matching_repositories(dnf_manager, conf.payload.disabled_repositories, False)

    if not get_product_is_final_release():
        return

    log.debug("Disable rawhide repositories.")
    enable_matching_repositories(dnf_manager, ["*rawhide*"], False)


def enable_matching_repositories(dnf_manager, patterns, enabled=True):
    """Enable or disable matching repositories.

    :param DNFManager dnf_manager: a configured DNF manager
    :param patterns: a list of patterns to match the repo ids
    :param enabled: True to enable, False to disable
    """
    names = set()

    for pattern in patterns:
        names.update(dnf_manager.get_matching_repositories(pattern))

    for name in sorted(names):
        dnf_manager.set_repository_enabled(name, enabled)


def create_repository(dnf_manager, repository):
    """Create a new repository.

    :param DNFManager dnf_manager: a configured DNF manager
    :param RepoConfigurationData repository: a resolved repository data
    """
    log.debug("Add the '%s' repository (%s).", repository.name, repository)
    dnf_manager.add_repository(repository)


def enable_existing_repository(dnf_manager, repository):
    """Enable or disable an existing repository.

    Users can try to do "repo --name=updates" in a kickstart file. We can
    only enable or disable the already existing on-disk repo configuration.

    :param DNFManager dnf_manager: a configured DNF manager
    :param RepoConfigurationData repository: a system repository data
    :raise: SourceSetupError if the system repository is not available
    """
    try:
        dnf_manager.set_repository_enabled(repository.name, repository.enabled)
    except UnknownRepositoryError:
        msg = _("The '{}' repository is not one of the pre-defined repositories.")
        raise SourceSetupError(msg.format(repository.name)) from None
