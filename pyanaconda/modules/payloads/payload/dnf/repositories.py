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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
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
from pyanaconda.core.constants import REPO_ORIGIN_TREEINFO, URL_TYPE_BASEURL
from pyanaconda.core.path import join_paths
from pyanaconda.core.util import execWithRedirect
from pyanaconda.modules.common.structures.payload import RepoConfigurationData

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


def generate_treeinfo_repositories(repo_data: RepoConfigurationData, tree_info_metadata):
    """Generate repositories from tree metadata of the specified repository.

    :param RepoConfigurationData repo_data: a repository with metadata
    :param TreeInfoMetadata tree_info_metadata: metadata of the repository
    :return: a list of generated repo configuration data
    """
    repositories = []

    for repo_md in tree_info_metadata.repositories:
        repo = copy.deepcopy(repo_data)

        repo.origin = REPO_ORIGIN_TREEINFO
        repo.name = repo_md.name

        repo.type = URL_TYPE_BASEURL
        repo.url = repo_md.url

        repo.enabled = repo_md.enabled
        repo.installation_enabled = False

        repositories.append(repo)

    return repositories
