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
import hashlib

from requests import RequestException

from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core import util, constants
from pyanaconda.core.payload import ProxyString, ProxyStringError
from pyanaconda.core.constants import USER_AGENT

log = get_packaging_logger()

__all__ = ["RepoMDMetaHash"]


class RepoMDMetaHash(object):
    """Class that holds hash of a repomd.xml file content from a repository.
    This class can test availability of this repository by comparing hashes.
    """
    def __init__(self, repo, proxy_url):
        self._repoId = repo.id
        self._proxy_url = proxy_url
        self._ssl_verify = repo.sslverify
        self._urls = repo.baseurl
        self._repomd_hash = ""

    @property
    def repoMD_hash(self):
        """Return SHA256 hash of the repomd.xml file stored."""
        return self._repomd_hash

    @property
    def id(self):
        """Name of the repository."""
        return self._repoId

    def store_repoMD_hash(self):
        """Download and store hash of the repomd.xml file content."""
        repomd = self._download_repoMD()
        self._repomd_hash = self._calculate_hash(repomd)

    def verify_repoMD(self):
        """Download and compare with stored repomd.xml file."""
        new_repomd = self._download_repoMD()
        new_repomd_hash = self._calculate_hash(new_repomd)
        return new_repomd_hash == self._repomd_hash

    def _calculate_hash(self, data):
        m = hashlib.sha256()
        m.update(data.encode('ascii', 'backslashreplace'))
        return m.digest()

    def _download_repoMD(self):
        proxies = {}
        repomd = ""
        headers = {"user-agent": USER_AGENT}

        if self._proxy_url is not None:
            try:
                proxy = ProxyString(self._proxy_url)
                proxies = {"http": proxy.url,
                           "https": proxy.url}
            except ProxyStringError as e:
                log.info("Failed to parse proxy for test if repo available %s: %s",
                         self._proxy_url, e)

        session = util.requests_session()

        # Test all urls for this repo. If any of these is working it is enough.
        for url in self._urls:
            try:
                result = session.get("%s/repodata/repomd.xml" % url, headers=headers,
                                     proxies=proxies, verify=self._ssl_verify,
                                     timeout=constants.NETWORK_CONNECTION_TIMEOUT)
                if result.ok:
                    repomd = result.text
                    result.close()
                    break
                else:
                    log.debug("Server returned %i code when downloading repomd",
                              result.status_code)
                    result.close()
                    continue
            except RequestException as e:
                log.debug("Can't download new repomd.xml from %s with proxy: %s. Error: %s",
                          url, proxies, e)

        return repomd
