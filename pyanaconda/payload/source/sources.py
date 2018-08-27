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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from enum import Enum


class SourceType(Enum):
    CDROM = "cdrom"
    HARDDRIVE = "harddrive"
    NFS = "nfs"
    HTTP = "http"
    HTTPS = "https"
    FTP = "ftp"
    FILE = "file"
    LIVECD = "livecd"
    HMC = "hmc"
    UNKNOWN = "unknown"


class BasePayloadSource(object):
    """Base object for payload source.

    Implements common methods for payload source.
    """
    def __init__(self, source_type: SourceType, method_type: str):
        super().__init__()

        self._source_type = source_type
        self._method_type = method_type

    @property
    def source_type(self) -> SourceType:
        """Get source type.

        :rtype: SourceType enum.
        """
        return self._source_type

    @property
    def method_type(self) -> str:
        """Get method type string

        :rtype: str
        """
        return self._method_type

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
    def is_livecd(self):
        """Is this livecd source?

        :rtype bool
        """
        return self._source_type == SourceType.LIVECD

    @property
    def is_hmc(self):
        """Is this hmc source?

        :rtype bool
        """
        return self._source_type == SourceType.HMC


class CDRomSource(BasePayloadSource):
    """Source object for CDrom sources."""

    def __init__(self):
        super().__init__(SourceType.CDROM, "cdrom")


class NFSSource(BasePayloadSource):
    """Source object for NFS sources."""

    def __init__(self, server, path, opts):
        super().__init__(SourceType.NFS, "nfs")
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


class HDDSource(BasePayloadSource):
    """Source object for hard drive source."""

    def __init__(self, partition, path):
        super().__init__(SourceType.HARDDRIVE, "harddrive")

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


class URLBasedSource(BasePayloadSource):
    """Base class for URL based sources."""

    def __init__(self, source_type, url, mirrorlist=False, metalink=False):
        super().__init__(source_type, "url")

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
        super().__init__(SourceType.FILE, "url")

        self._path = path

    @property
    def path(self):
        """Path to the file source.

        :rtype: str
        """
        return self._path


class LiveSource(BasePayloadSource):
    """Source object for live image sources."""

    def __init__(self, partition):
        super().__init__(SourceType.LIVECD, "harddrive")

        self._partition = partition

    @property
    def partition(self):
        """Partition with live image.

        :rtype: str
        """
        return self._partition


class HMCSource(BasePayloadSource):
    """Source object for HMC sources.

    S390 cdrom like device.
    """

    def __init__(self):
        super().__init__(SourceType.HMC, "hmc")
