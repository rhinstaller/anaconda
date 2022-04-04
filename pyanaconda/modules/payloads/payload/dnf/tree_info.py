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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import configparser
import os
import time

from functools import partial
from productmd.treeinfo import TreeInfo
from requests import RequestException

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import URL_TYPE_BASEURL, NETWORK_CONNECTION_TIMEOUT, \
    DEFAULT_REPOS, USER_AGENT
from pyanaconda.core.payload import split_protocol, ProxyString, ProxyStringError
from pyanaconda.core.util import requests_session, xprogressive_delay
from pyanaconda.modules.common.structures.payload import RepoConfigurationData

log = get_module_logger(__name__)

__all__ = [
    "TreeInfoMetadataError",
    "NoTreeInfoError",
    "InvalidTreeInfoError",
    "TreeInfoMetadata",
]


class TreeInfoMetadataError(Exception):
    """General error for the treeinfo metadata."""
    pass


class NoTreeInfoError(TreeInfoMetadataError):
    """There is no treeinfo metadata to use."""
    pass


class InvalidTreeInfoError(TreeInfoMetadataError):
    """The treeinfo metadata is invalid."""
    pass


class TreeInfoMetadata(object):
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
        self._root_path = ""
        self._release_version = ""
        self._repositories = []

    def _reset(self):
        """Reset the metadata."""
        self._root_path = ""
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
                    root_path=path,
                    file_path=file_path
                )
                return

        raise NoTreeInfoError("No treeinfo metadata found.")

    def _load_tree_info(self, root_path, file_path=None, file_content=None):
        """Load the treeinfo metadata.

        :param root_path: a path to the installation root
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

            # Load the repositories.
            repo_list = []

            for name in tree_info.variants:
                log.debug("Processing the '%s' variant.", name)

                # Get the variant metadata.
                data = tree_info.variants[name]

                # Create the repo metadata.
                repo_md = TreeInfoRepoMetadata(
                    repo_name=name,
                    tree_info=data,
                    root_path=root_path,
                )

                repo_list.append(repo_md)

        except configparser.Error as e:
            log.debug("Failed to load treeinfo metadata: %s", e)
            raise InvalidTreeInfoError("Invalid metadata: {}".format(str(e))) from None

        # Update this treeinfo representation.
        self._root_path = root_path
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
            downloader = self._get_downloader(session, data)
            content = self._download_metadata(downloader, data.url)

        # Process the metadata.
        self._load_tree_info(
            root_path=data.url,
            file_content=content
        )

    def _get_downloader(self, session, data):
        """Get a configured session.get method.

        :return: a partial function
        """
        # Prepare the SSL configuration.
        ssl_enabled = conf.payload.verify_ssl and data.ssl_verification_enabled

        # ssl_verify can be:
        #   - the path to a cert file
        #   - True, to use the system's certificates
        #   - False, to not verify
        ssl_verify = data.ssl_configuration.ca_cert_path or ssl_enabled

        # ssl_cert can be:
        #   - a tuple of paths to a client cert file and a client key file
        #   - None
        ssl_client_cert = data.ssl_configuration.client_cert_path or None
        ssl_client_key = data.ssl_configuration.client_key_path or None
        ssl_cert = (ssl_client_cert, ssl_client_key) if ssl_client_cert else None

        # Prepare the proxy configuration.
        proxy_url = data.proxy or None
        proxies = {}

        if proxy_url:
            try:
                proxy = ProxyString(proxy_url)
                proxies = {
                    "http": proxy.url,
                    "https": proxy.url
                }
            except ProxyStringError as e:
                log.debug("Failed to parse the proxy '%s': %s", proxy_url, e)

        # Prepare headers.
        headers = {"user-agent": USER_AGENT}

        # Return a partial function.
        return partial(
            session.get,
            headers=headers,
            proxies=proxies,
            verify=ssl_verify,
            cert=ssl_cert,
            timeout=NETWORK_CONNECTION_TIMEOUT
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

        :return: True or False
        """
        repo_md = self._get_base_repository() or self._get_root_repository()

        if not repo_md:
            log.debug("There is no usable repository available")
            return False

        if not repo_md.valid:
            log.debug("There is no valid repository available.")
            return False

        return True

    def get_base_repo_url(self):
        """Return an URL of the base repository.

        :return: an URL of the base repo
        """
        repo_md = self._get_base_repository()

        if repo_md:
            log.debug("The treeinfo defines a base repository at: %s", repo_md.absolute_path)
            return repo_md.absolute_path

        log.debug("No base repository found in the treeinfo. Using installation tree root.")
        return self._root_path

    def _get_base_repository(self):
        """Return metadata of the base repository.

        :return: an instance of TreeInfoRepoMetadata or None
        """
        for repo_md in self.repositories:
            if repo_md.name in DEFAULT_REPOS:
                return repo_md

        return None

    def _get_root_repository(self):
        """Return metadata of the root repository.

        :return: an instance of TreeInfoRepoMetadata or None
        """
        for repo_md in self.repositories:
            if repo_md.relative_path == ".":
                return repo_md

        return None


class TreeInfoRepoMetadata(object):
    """Metadata repo object contains metadata about repository."""

    def __init__(self, repo_name, tree_info, root_path):
        """Do not instantiate this class directly.

        :param repo_name: a name of the repository
        :param tree_info: a metadata of the repository
        :param root_path: a root path of the installation source
        """
        self._name = repo_name
        self._type = tree_info.type
        self._root_path = root_path
        self._relative_path = tree_info.paths.repository
        self._absolute_path = self._get_absolute_path(
            root_path=root_path,
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
    def valid(self):
        """Is the repository valid?

        We only check whether the repodata directory exists.
        That doesn't have to mean that the repo is valid.

        :return: True or False
        """
        return os.access(os.path.join(self.absolute_path, "repodata"), os.R_OK)

    @property
    def relative_path(self):
        """Relative path of the repository."""
        return self._relative_path

    @property
    def absolute_path(self):
        """Absolute path of the repository."""
        return self._absolute_path

    @staticmethod
    def _get_absolute_path(root_path, relative_path):
        """Get the absolute path of the repository."""
        if relative_path == ".":
            return root_path

        # Create the absolute path.
        full_path = os.path.join(root_path, relative_path)
        protocol, url = split_protocol(full_path)

        # Normalize the URL to solve problems with a relative path.
        # This is especially useful for NFS (root/path/../new_path).
        url = os.path.normpath(url)

        return protocol + url
