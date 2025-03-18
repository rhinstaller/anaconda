# Gather and provides metadata about installation tree.
#
# Copyright (C) 2018  Red Hat, Inc.
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

import time
import requests
import os

from productmd.treeinfo import TreeInfo
from pyanaconda.core import util, constants
from pyanaconda.core.payload import split_protocol

from pyanaconda.anaconda_loggers import get_packaging_logger
log = get_packaging_logger()

MAX_TREEINFO_DOWNLOAD_RETRIES = 6


class InstallTreeMetadata(object):
    # TODO: Add tests for InstallTreeMetadata class

    def __init__(self):
        self._tree_info = TreeInfo()
        self._meta_repos = []
        self._path = ""

    def load_file(self, root_path):
        """Loads installation tree metadata from root path.

        :param root_path: Path to the installation root.
        :type root_path: str
        :returns: True if the metadata were loaded, False otherwise.
        """
        self._clear()
        self._path = root_path

        if os.access(os.path.join(root_path, ".treeinfo"), os.R_OK):
            self._tree_info.load(os.path.join(root_path, ".treeinfo"))
        elif os.access(os.path.join(root_path, "treeinfo"), os.R_OK):
            self._tree_info.load(os.path.join(root_path, "treeinfo"))
        else:
            return False

        return True

    def load_url(self, url, proxies, sslverify, sslcert, headers):
        """Load URL link.

        This can be also to local file.

        Parameters here are passed to requests object so make them compatible with requests.

        :param url: URL poiting to the installation tree.
        :param proxies: Proxy used for the request.
        :param sslverify: sslverify object which will be used in request.
        :param headers: Additional headers of the request.
        :returns: True if the install tree repo metadata was successfully loaded. False otherwise.

        :raise: IOError is thrown in case of immediate failure.
        """
        # Retry treeinfo downloads with a progressively longer pause,
        # so NetworkManager have a chance setup a network and we have
        # full connectivity before trying to download things. (#1292613)
        self._clear()

        xdelay = util.xprogressive_delay()
        response = None
        ret_code = [None, None]
        session = util.requests_session()

        for retry_count in range(0, MAX_TREEINFO_DOWNLOAD_RETRIES + 1):
            if retry_count > 0:
                time.sleep(next(xdelay))
            # Downloading .treeinfo
            log.info("Trying to download '.treeinfo'")
            (response, ret_code[0]) = self._download_treeinfo_file(session, url, ".treeinfo",
                                                                   headers, proxies,
                                                                   sslverify, sslcert)
            if response:
                break

            # Downloading treeinfo
            log.info("Trying to download 'treeinfo'")
            (response, ret_code[1]) = self._download_treeinfo_file(session, url, "treeinfo",
                                                                   headers, proxies,
                                                                   sslverify, sslcert)
            if response:
                break

            # The [.]treeinfo wasn't downloaded. Try it again if [.]treeinfo
            # is on the server.
            #
            # Server returned HTTP 404 code -> no need to try again
            if (ret_code[0] is not None and ret_code[0] == 404
                    and ret_code[1] is not None and ret_code[1] == 404):
                response = None
                log.error("Got HTTP 404 Error when downloading [.]treeinfo files")
                break
            if retry_count < MAX_TREEINFO_DOWNLOAD_RETRIES:
                # retry
                log.info("Retrying repo info download for %s, retrying (%d/%d)",
                         url, retry_count + 1, MAX_TREEINFO_DOWNLOAD_RETRIES)
            else:
                # run out of retries
                err_msg = ("Repo info download for %s failed after %d retries" %
                           (url, retry_count))
                log.error(err_msg)
                raise IOError("Can't get .treeinfo file from the url {}".format(url))

        if response:
            # get the treeinfo contents
            self._tree_info.loads(response)
            self._path = url
            return True

        return False

    @staticmethod
    def _download_treeinfo_file(session, url, file_name, headers, proxies, verify, cert):
        try:
            result = session.get("%s/%s" % (url, file_name), headers=headers,
                                 proxies=proxies, verify=verify, cert=cert,
                                 timeout=constants.NETWORK_CONNECTION_TIMEOUT)

            status_code = result.status_code

            # Server returned HTTP 4XX or 5XX codes
            if 400 <= status_code < 600:
                log.info("Server returned %i code", status_code)
                result_text = None
            else:
                result_text = result.text

            result.close()
        except requests.exceptions.RequestException as e:
            log.info("Error downloading '%s': %s", file_name, e)
            return None, None

        log.debug("Retrieved '%s' from %s", file_name, url)
        return result_text, status_code

    def _clear(self):
        """Clear metadata repositories."""
        self._tree_info = TreeInfo()
        self._meta_repos = []
        self._path = ""

    def get_release_version(self):
        """Get release version from the repository.

        :returns: Version as lowercase string.
        :raises: ValueError if version is not present.
        """
        version = self._tree_info.release.version

        if not version:
            raise ValueError("Can't read release version from the .treeinfo file! "
                             "Is the .treeinfo file corrupted?")

        return version.lower()

    def get_metadata_repos(self):
        """Get all repository metadata objects."""
        if not self._meta_repos:
            self._read_variants()

        return self._meta_repos

    def get_base_repo_metadata(self, additional_names=None):
        """Get repo metadata about base repository."""
        repos = constants.DEFAULT_REPOS

        if additional_names:
            repos.extend(additional_names)

        for repo_md in self.get_metadata_repos():
            if repo_md.name in repos:
                return repo_md

        return None

    def get_treeinfo_for(self, variant_name):
        """Return the productmd.Variant object for variant_name."""
        return self._tree_info.variants[variant_name]

    def _read_variants(self):
        for variant_name in self._tree_info.variants:
            variant_object = self._tree_info.variants[variant_name]
            self._meta_repos.append(RepoMetadata(variant_name, variant_object, self._path))


class RepoMetadata(object):
    """Metadata repo object contains metadata about repository."""

    def __init__(self, name, obj, root_path):
        """Do not instantiate this class directly.
        Use InstallTreeMetadata to instantiate this class.
        """
        self._name = name
        self._obj = obj
        self._root_path = root_path

    @property
    def name(self):
        """Get name of this repository."""
        return self._name

    @property
    def relative_path(self):
        """Get relative repository root path."""
        return self._obj.paths.repository

    @property
    def path(self):
        """Get absolute repository root path."""
        if self.relative_path == ".":
            return self._root_path
        else:
            protocol, url = split_protocol(os.path.join(self._root_path, self.relative_path))
            # resolve problems with relative path especially useful for NFS (root/path/../new_path)
            url = os.path.normpath(url)
            return protocol + url

    def is_valid(self):
        """Quick check if the repo is a valid repository.

        This is only check if the repository is invalid. If success it doesn't mean it is valid.

        :returns: True if repository is not invalid, False otherwise."""
        return os.access(os.path.join(self.path, "repodata"), os.R_OK)
