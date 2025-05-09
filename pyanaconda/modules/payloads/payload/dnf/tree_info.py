#
# Copyright (C) 2021  Red Hat, Inc.
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
import configparser
import copy
import os
import time
from collections import namedtuple

from productmd.treeinfo import TreeInfo
from requests import RequestException

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    DEFAULT_REPOS,
    REPO_ORIGIN_TREEINFO,
    URL_TYPE_BASEURL,
)
from pyanaconda.core.path import join_paths
from pyanaconda.core.payload import split_protocol
from pyanaconda.core.util import requests_session, xprogressive_delay
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.common.task import Task
from pyanaconda.modules.payloads.base.utils import get_downloader_for_repo_configuration

log = get_module_logger(__name__)

__all__ = [
    "InvalidTreeInfoError",
    "LoadTreeInfoMetadataResult",
    "LoadTreeInfoMetadataTask",
    "NoTreeInfoError",
    "TreeInfoMetadata",
    "TreeInfoMetadataError",
]


def generate_treeinfo_repository(repo_data: RepoConfigurationData, repo_md):
    """Generate repositories from tree metadata of the specified repository.

    :param RepoConfigurationData repo_data: a repository with the .treeinfo file
    :param TreeInfoRepoMetadata repo_md: a metadata of a treeinfo repository
    :return RepoConfigurationData: a treeinfo repository
    """
    repo = copy.deepcopy(repo_data)

    repo.origin = REPO_ORIGIN_TREEINFO
    repo.name = repo_md.name

    repo.type = URL_TYPE_BASEURL
    repo.url = repo_md.url

    repo.enabled = repo_md.enabled
    repo.installation_enabled = False

    return repo


class TreeInfoMetadataError(Exception):
    """General error for the treeinfo metadata."""
    pass


class NoTreeInfoError(TreeInfoMetadataError):
    """There is no treeinfo metadata to use."""
    pass


class InvalidTreeInfoError(TreeInfoMetadataError):
    """The treeinfo metadata is invalid."""
    pass


class TreeInfoMetadata:
    """The representation of a .treeinfo file.

    The structure of the installation root can be similar to this:

    / -
      | - .treeinfo
      | - BaseRepo -
      |            | - repodata
      |            | - Packages
      | - AddonRepo -
                    | - repodata
                    | - Packages

    The .treeinfo file contains information where repositories are placed
    from the installation root.

    The provided URL of an installation source can be an installation tree
    root or a a subdirectory in the installation root. Both options are valid:

        * If the URL points to an installation root, we need to find paths
          to repositories in the .treeinfo file.

        * If URL points directly to a subdirectory, there is no .treeinfo file
          present. We will use the URL as a path to a repository.

    """

    # Supported names of the treeinfo files.
    TREE_INFO_NAMES = [".treeinfo", "treeinfo"]

    # The number of download retries.
    MAX_TREEINFO_DOWNLOAD_RETRIES = 6

    def __init__(self):
        """Create a new instance."""
        self._release_version = ""
        self._repositories = []

    def _reset(self):
        """Reset the metadata."""
        self._release_version = ""
        self._repositories = []

    @property
    def release_version(self):
        """Release version.

        :return: a release version as a lowercase string
        """
        return self._release_version

    @property
    def repositories(self):
        """Repository metadata objects.

        :return: a list of TreeInfoRepoMetadata instances
        """
        return self._repositories

    def load_file(self, path):
        """Loads installation tree metadata from the given path.

        :param str path: a path to the installation root
        :raise: NoTreeInfoError if there is no .treeinfo file
        """
        self._reset()

        log.debug("Load treeinfo metadata for '%s'.", path)

        for name in self.TREE_INFO_NAMES:
            file_path = os.path.join(path, name)

            if os.access(file_path, os.R_OK):
                self._load_tree_info(
                    root_url="file://" + path,
                    file_path=file_path
                )
                return

        raise NoTreeInfoError("No treeinfo metadata found.")

    def _load_tree_info(self, root_url, file_path=None, file_content=None):
        """Load the treeinfo metadata.

        :param root_url: a URL of the installation root
        :param file_path: a path to a treeinfo file or None
        :param file_content: a content of a treeinfo file or None
        :raise InvalidTreeInfoError: if the metadata is invalid
        """
        try:
            # Load and validate the metadata.
            tree_info = TreeInfo()

            if file_content:
                tree_info.loads(file_content)
            else:
                tree_info.load(file_path)

            tree_info.validate()
            log.debug("Loaded treeinfo metadata:\n%s", tree_info.dumps())

            # Load the release version.
            release_version = tree_info.release.version.lower()

            # Create repositories for variants and optional variants.
            # Child variants (like addons) will be ignored.
            repo_list = []

            for name in tree_info.variants:
                log.debug("Processing the '%s' variant.", name)

                # Get the variant metadata.
                data = tree_info.variants[name]

                # Create the repo metadata.
                repo_md = TreeInfoRepoMetadata(
                    repo_name=name,
                    tree_info=data,
                    root_url=root_url,
                )

                repo_list.append(repo_md)

        except configparser.Error as e:
            log.debug("Failed to load treeinfo metadata: %s", e)
            raise InvalidTreeInfoError("Invalid metadata: {}".format(str(e))) from None

        # Update this treeinfo representation.
        self._repositories = repo_list
        self._release_version = release_version

        log.debug("The treeinfo metadata is loaded.")

    def load_data(self, data: RepoConfigurationData):
        """Loads installation tree metadata from the given data.

        param data: the repo configuration data
        :raise: NoTreeInfoError if there is no .treeinfo file
        """
        self._reset()

        if data.type != URL_TYPE_BASEURL:
            raise NoTreeInfoError("Unsupported type of URL ({}).".format(data.type))

        if not data.url:
            raise NoTreeInfoError("No URL specified.")

        # Download the metadata.
        log.debug("Load treeinfo metadata for '%s'.", data.url)

        with requests_session() as session:
            downloader = get_downloader_for_repo_configuration(session, data)
            content = self._download_metadata(downloader, data.url)

        # Process the metadata.
        self._load_tree_info(
            root_url=data.url,
            file_content=content
        )

    def _download_metadata(self, downloader, url):
        """Download metadata from the given URL."""
        # How many times should we try the download?
        retry_max = self.MAX_TREEINFO_DOWNLOAD_RETRIES

        # Don't retry to download files that returned HTTP 404 code.
        not_found = set()

        # Retry treeinfo downloads with a progressively longer pause,
        # so NetworkManager have a chance setup a network and we have
        # full connectivity before trying to download things. (#1292613)
        xdelay = xprogressive_delay()

        for retry_count in range(0, retry_max):
            # Delay if we are retrying the download.
            if retry_count > 0:
                log.info("Retrying download (%d/%d)", retry_count, retry_max - 1)
                time.sleep(next(xdelay))

            # Download the metadata file.
            for name in self.TREE_INFO_NAMES:
                file_url = "{}/{}".format(url, name)

                try:
                    with downloader(file_url) as r:
                        if r.status_code == 404:
                            not_found.add(name)

                        r.raise_for_status()
                        return r.text

                except RequestException as e:
                    log.debug("Failed to download '%s': %s", name, e)
                    continue

            if not_found == set(self.TREE_INFO_NAMES):
                raise NoTreeInfoError("No treeinfo metadata found (404).")

        raise NoTreeInfoError("Couldn't download treeinfo metadata.")

    def verify_image_base_repo(self):
        """Verify the base repository of an ISO image.

        We only check whether the repodata directory of the base repo
        exists. That doesn't have to mean that the repo is valid.

        :return: True or False
        """
        repo_md = self.get_base_repository() or self.get_root_repository()

        if not repo_md:
            log.debug("There is no usable repository available")
            return False

        if not repo_md.url.startswith("file://"):
            raise ValueError("Unexpected type of URL: {}".format(repo_md.url))

        repo_path = repo_md.url.removeprefix("file://")
        data_path = os.path.join(repo_path, "repodata")

        if not os.access(data_path, os.R_OK):
            log.debug("There is no valid repository available.")
            return False

        return True

    def get_base_repository(self):
        """Return metadata of the base repository.

        :return: an instance of TreeInfoRepoMetadata or None
        """
        for repo_md in self.repositories:
            if repo_md.name in DEFAULT_REPOS:
                return repo_md

        return None

    def get_root_repository(self):
        """Return metadata of the root repository.

        :return: an instance of TreeInfoRepoMetadata or None
        """
        for repo_md in self.repositories:
            if repo_md.relative_path == ".":
                return repo_md

        return None


class TreeInfoRepoMetadata:
    """Metadata repo object contains metadata about repository."""

    def __init__(self, repo_name, tree_info, root_url):
        """Do not instantiate this class directly.

        :param repo_name: a name of the repository
        :param tree_info: a metadata of the repository
        :param root_url: a URL of the installation source
        """
        self._name = repo_name
        self._type = tree_info.type
        self._relative_path = tree_info.paths.repository
        self._url = self._get_url(
            root_url=root_url,
            relative_path=self._relative_path
        )

    @property
    def type(self):
        """Type of the repository."""
        return self._type

    @property
    def name(self):
        """Name of the repository."""
        return self._name

    @property
    def enabled(self):
        """Is the repository enabled?

        :return: True or False
        """
        return self._type in conf.payload.enabled_repositories_from_treeinfo

    @property
    def relative_path(self):
        """Relative path of the repository.

        :return: a relative path
        """
        return self._relative_path

    @property
    def url(self):
        """URL of the repository.

        :return: a URL
        """
        return self._url

    @staticmethod
    def _get_url(root_url, relative_path):
        """Get the URL of the repository."""
        if relative_path == ".":
            return root_url

        # Get the protocol.
        protocol, root_path = split_protocol(root_url)

        # Create the absolute path.
        absolute_path = join_paths(root_path, relative_path)

        # Normalize the URL to solve problems with a relative path.
        # This is especially useful for NFS (root/path/../new_path).
        return protocol + os.path.normpath(absolute_path)


# The result of the LoadTreeInfoMetadataTask task.
LoadTreeInfoMetadataResult = namedtuple(
    "LoadTreeInfoMetadataResult", [
        "repository_data",
        "release_version",
        "treeinfo_repositories"
    ]
)


class LoadTreeInfoMetadataTask(Task):
    """Task to process treeinfo metadata of an installation source."""

    def __init__(self, data: RepoConfigurationData):
        """Create a task.

        :param RepoConfigurationData data: a repo configuration data
        """
        super().__init__()
        self._repository_data = data

    @property
    def name(self):
        """The task name."""
        return "Load treeinfo metadata"

    def run(self):
        """Run the task."""
        log.debug("Reload treeinfo metadata.")
        try:
            return self._load_treeinfo_metadata()
        except NoTreeInfoError as e:
            log.debug("No treeinfo metadata to use: %s", str(e))
        except TreeInfoMetadataError as e:
            log.warning("Couldn't use treeinfo metadata: %s", str(e))

        return self._handle_no_treeinfo_metadata()

    def _load_treeinfo_metadata(self):
        """Load treeinfo metadata if available."""
        # Load the treeinfo metadata.
        treeinfo_metadata = TreeInfoMetadata()
        treeinfo_metadata.load_data(self._repository_data)

        # Update the base repository. Use the base or root repository
        # from the treeinfo metadata if available. Otherwise, use the
        # original installation source.
        repository_md = treeinfo_metadata.get_base_repository() \
            or treeinfo_metadata.get_root_repository()

        repository_data = self._generate_repository(repository_md) \
            or self._repository_data

        # Generate the treeinfo repositories from the metadata. Skip
        # a repository that is used as a new base repository if any.
        treeinfo_repositories = [
            self._generate_repository(m)
            for m in treeinfo_metadata.repositories
            if m is not repository_md
        ]

        # Get values of substitution variables.
        release_version = treeinfo_metadata.release_version or None

        # Return the results.
        return LoadTreeInfoMetadataResult(
            repository_data=repository_data,
            treeinfo_repositories=treeinfo_repositories,
            release_version=release_version,
        )

    def _generate_repository(self, repo_md):
        """Generate a repository from q treeinfo metadata."""
        if not repo_md:
            return None

        return generate_treeinfo_repository(self._repository_data, repo_md)

    def _handle_no_treeinfo_metadata(self):
        """The treeinfo metadata couldn't be loaded."""
        return LoadTreeInfoMetadataResult(
            repository_data=None,
            treeinfo_repositories=[],
            release_version=None,
        )
