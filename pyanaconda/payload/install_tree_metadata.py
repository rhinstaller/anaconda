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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import time
import requests

from productmd.treeinfo import TreeInfo
from pyanaconda.core import util, constants

from pyanaconda.anaconda_loggers import get_packaging_logger
log = get_packaging_logger()

MAX_TREEINFO_DOWNLOAD_RETRIES = 6


class InstallTreeMetadata(object):

    def __init__(self):
        self._tree_info = TreeInfo()
        self._meta_repos = []

    def load_text(self, text):
        """Loads .treeinfo content."""
        self._tree_info.loads(text)

    def load_file(self, path):
        """Loads installation tree metadata from root path."""
        self._clear()
        self._tree_info.load(path)

    def load_url(self, url, proxies, sslverify, headers):
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
        xdelay = util.xprogressive_delay()
        response = None
        ret_code = [None, None]
        session = util.requests_session()

        self._clear()

        for retry_count in range(0, MAX_TREEINFO_DOWNLOAD_RETRIES + 1):
            if retry_count > 0:
                time.sleep(next(xdelay))
            # Downloading .treeinfo
            log.info("Trying to download '.treeinfo'")
            (response, ret_code[0]) = self._download_treeinfo_file(session, url, ".treeinfo",
                                                                   headers, proxies, sslverify)
            if response:
                break
            # Downloading treeinfo
            log.info("Trying to download 'treeinfo'")
            (response, ret_code[1]) = self._download_treeinfo_file(session, url, "treeinfo",
                                                                   headers, proxies, sslverify)
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
            text = response.text

            response.close()

            self.load_text(text)
            return True

        return False

    @staticmethod
    def _download_treeinfo_file(session, url, file_name, headers, proxies, verify):
        try:
            result = session.get("%s/%s" % (url, file_name), headers=headers,
                                 proxies=proxies, verify=verify)
            # Server returned HTTP 4XX or 5XX codes
            if 400 <= result.status_code < 600:
                log.info("Server returned %i code", result.status_code)
                return None, result.status_code
            log.debug("Retrieved '%s' from %s", file_name, url)
        except requests.exceptions.RequestException as e:
            log.info("Error downloading '%s': %s", file_name, e)
            return (None, None)
        return result, result.status_code

    def _clear(self):
        """Clear metadata repositories."""
        self._tree_info = TreeInfo()
        self._meta_repos = []

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

    def get_repos_metadata(self):
        """Get all repository metadata objects."""
        if not self._meta_repos:
            self._read_variants()

        return self._meta_repos

    def get_repo_metadata_by_name(self, name):
        """Get repository metadata object with given name.

        :param name: Name of the variant to return.
        :rtype name: VariantRepo object or None.
        """
        for variant in self.get_repos_metadata():
            if name == variant.name:
                return variant

        return None

    def get_base_repo_metadata(self, additional_names):
        """Get repo metadata about base repository."""
        repos = additional_names + constants.DEFAULT_REPOS

        for repo_md in self.get_repos_metadata():
            if repo_md.name in repos:
                return repo_md

        return None

    def _read_variants(self):
        for variant_name in self._tree_info.variants:
            variant_object = self._tree_info.variants[variant_name]
            self._meta_repos.append(RepoMetadata(variant_name, variant_object))


class RepoMetadata(object):
    """Metadata repo object contains metadata about repository."""

    def __init__(self, name, obj):
        """Do not instantiate this class directly.
        Use InstallTreeMetadata to instantiate this class.
        """
        self._name = name
        self._obj = obj

    @property
    def name(self):
        """Get name of this repository."""
        return self._name

    @property
    def path(self):
        """Get relative repository root path."""
        return self._obj.paths.repository
