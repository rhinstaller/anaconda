# Sources used in payloads.
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
from abc import abstractmethod, ABC
from enum import Enum

from pyanaconda.core.constants import SOURCE_TYPE_CDROM, SOURCE_TYPE_NFS, SOURCE_TYPE_HDD, \
    SOURCE_TYPE_URL, SOURCE_TYPE_HMC, URL_TYPE_BASEURL, URL_TYPE_MIRRORLIST, URL_TYPE_METALINK
from pyanaconda.core.payload import create_nfs_url
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.ui.lib.payload import create_source


class SourceType(Enum):
    CDROM = "cdrom"
    HARDDRIVE = "harddrive"
    NFS = "nfs"
    HTTP = "http"
    HTTPS = "https"
    FTP = "ftp"
    FILE = "file"
    HMC = "hmc"


class BasePayloadSource(ABC):
    """Base object for payload source.

    Implements common methods for payload source.
    """
    def __init__(self, source_type: SourceType):
        super().__init__()
        self._source_type = source_type

    @property
    def source_type(self) -> SourceType:
        """Get source type.

        :rtype: SourceType enum.
        """
        return self._source_type

    @abstractmethod
    def create_proxy(self):
        """Create and set up a DBus source.

        :return: a DBus proxy of a source
        """
        pass

    @property
    def is_cdrom(self):
        """Is this cdrom source?

        :rtype: bool
        """
        return self._source_type == SourceType.CDROM

    @property
    def is_harddrive(self):
        """Is this hard drive source?

        :rtype bool
        """
        return self._source_type == SourceType.HARDDRIVE

    @property
    def is_nfs(self):
        """Is this nfs source?

        :rtype bool
        """
        return self._source_type == SourceType.NFS

    @property
    def is_http(self):
        """Is this http source?

        :rtype bool
        """
        return self._source_type == SourceType.HTTP

    @property
    def is_https(self):
        """Is this https source?

        :rtype bool
        """
        return self._source_type == SourceType.HTTPS

    @property
    def is_ftp(self):
        """Is this ftp source?

        :rtype bool
        """
        return self._source_type == SourceType.FTP

    @property
    def is_file(self):
        """Is this file:// based source?

        :rtype bool
        """
        return self._source_type == SourceType.FILE

    @property
    def is_hmc(self):
        """Is this hmc source?

        :rtype bool
        """
        return self._source_type == SourceType.HMC


class CDRomSource(BasePayloadSource):
    """Source object for CDrom sources."""

    def __init__(self):
        super().__init__(SourceType.CDROM)

    def create_proxy(self):
        """Create and set up a DBus source.

        :return: a DBus proxy of a source
        """
        return create_source(SOURCE_TYPE_CDROM)


class NFSSource(BasePayloadSource):
    """Source object for NFS sources."""

    def __init__(self, server, path, opts):
        super().__init__(SourceType.NFS)
        self._server = server
        self._path = path
        self._opts = opts

    @property
    def server(self):
        """Get server.

        :rtype: str
        """
        return self._server

    @property
    def path(self):
        """Get server path.

        :rtype: str
        """
        return self._path

    @property
    def options(self):
        """Get nfs mount options.

        :rtype: str
        """
        return self._opts

    def create_proxy(self):
        """Create and set up a DBus source.

        :return: a DBus proxy of a source
        """
        source_proxy = create_source(SOURCE_TYPE_NFS)
        source_url = create_nfs_url(self.server, self.path, self.options)
        source_proxy.SetURL(source_url)
        return source_proxy


class HDDSource(BasePayloadSource):
    """Source object for hard drive source."""

    def __init__(self, partition, path):
        super().__init__(SourceType.HARDDRIVE)

        self._partition = partition
        self._path = path

    @property
    def partition(self):
        """Partition with the source.

        :rtype: str
        """
        return self._partition

    @property
    def path(self):
        """Path to a source on the partition.

        :rtype: str
        """
        return self._path

    def create_proxy(self):
        """Create and set up a DBus source.

        :return: a DBus proxy of a source
        """
        source_proxy = create_source(SOURCE_TYPE_HDD)
        source_proxy.SetPartition(self.partition)
        source_proxy.SetDirectory(self.path)
        return source_proxy


class URLBasedSource(BasePayloadSource):
    """Base class for URL based sources."""

    def __init__(self, source_type, url, mirrorlist=False, metalink=False):
        super().__init__(source_type)

        if mirrorlist and metalink:
            raise KeyError("Can't have one link both mirrorlist and metalink!")

        self._url = url
        self._mirrorlist = mirrorlist
        self._metalink = metalink

    @property
    def url(self):
        """Get url link.

        :rtype: str
        """
        return self._url

    @property
    def url_type(self):
        """Get url type.

        :rtype: str
        """
        if self.is_mirrorlist:
            return URL_TYPE_MIRRORLIST
        elif self.is_metalink:
            return URL_TYPE_METALINK
        else:
            return URL_TYPE_BASEURL

    @property
    def is_mirrorlist(self):
        """Is mirrorlist url?

        :rtype: bool
        """
        return self._mirrorlist

    @property
    def is_metalink(self):
        """Is metalink url?

        :rtype: bool
        """
        return self._metalink

    def create_proxy(self):
        """Create and set up a DBus source.

        :return: a DBus proxy of a source
        """
        source_proxy = create_source(SOURCE_TYPE_URL)

        repo_configuration = RepoConfigurationData()
        repo_configuration.type = self.url_type
        repo_configuration.url = self.url

        source_proxy.SetRepoConfiguration(
            RepoConfigurationData.to_structure(repo_configuration)
        )

        return source_proxy


class HTTPSource(URLBasedSource):
    """Source object for HTTP sources."""

    def __init__(self, url, mirrorlist=False, metalink=False):
        super().__init__(SourceType.HTTP, url, mirrorlist, metalink)


class HTTPSSource(URLBasedSource):
    """Source object for HTTPS sources."""

    def __init__(self, url, mirrorlist=False, metalink=False):
        super().__init__(SourceType.HTTPS, url, mirrorlist, metalink)


class FTPSource(URLBasedSource):
    """Source object for FTP sources."""

    def __init__(self, url, mirrorlist=False, metalink=False):
        super().__init__(SourceType.FTP, url, mirrorlist, metalink)


class FileSource(BasePayloadSource):
    """Source object for file:// based sources."""

    def __init__(self, path):
        super().__init__(SourceType.FILE)

        self._path = path

    @property
    def path(self):
        """Path to the file source.

        :rtype: str
        """
        return self._path

    def create_proxy(self):
        """Create and set up a DBus source.

        :return: a DBus proxy of a source
        """
        source_proxy = create_source(SOURCE_TYPE_URL)

        repo_configuration = RepoConfigurationData()
        repo_configuration.type = URL_TYPE_BASEURL
        repo_configuration.url = self.path

        source_proxy.SetRepoConfiguration(
            RepoConfigurationData.to_structure(repo_configuration)
        )

        return source_proxy


class HMCSource(BasePayloadSource):
    """Source object for HMC sources.

    S390 cdrom like device.
    """

    def __init__(self):
        super().__init__(SourceType.HMC)

    def create_proxy(self):
        """Create and set up a DBus source.

        :return: a DBus proxy of a source
        """
        return create_source(SOURCE_TYPE_HMC)
