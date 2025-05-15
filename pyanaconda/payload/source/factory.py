# Factory to parse source from different sources and give source objects back.
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.payload import parse_nfs_url
from pyanaconda.payload.source.sources import (
    CDRomSource,
    FileSource,
    FTPSource,
    HDDSource,
    HMCSource,
    HTTPSource,
    HTTPSSource,
    NFSSource,
)

log = get_module_logger(__name__)


class PayloadSourceTypeUnrecognized(Exception):
    pass


class SourceFactory(object):

    @classmethod
    def parse_repo_cmdline_string(cls, cmdline):
        """Parse cmdline string to source class."""
        if cls.is_cdrom(cmdline):
            return CDRomSource()
        elif cls.is_nfs(cmdline):
            nfs_options, server, path = parse_nfs_url(cmdline)
            return NFSSource(server, path, nfs_options)
        elif cls.is_harddrive(cmdline):
            url = cmdline.split(":", 1)[1]
            url_parts = url.split(":")
            device = url_parts[0]
            path = ""
            if len(url_parts) == 2:
                path = url_parts[1]
            elif len(url_parts) == 3:
                path = url_parts[2]

            return HDDSource(device, path)
        elif cls.is_http(cmdline):
            # installation source specified by bootoption
            # overrides source set from kickstart;
            # the kickstart might have specified a mirror list,
            # so we need to clear it here if plain url source is provided
            # by a bootoption, because having both url & mirror list
            # set at once is not supported and breaks dnf in
            # unpredictable ways
            return HTTPSource(cmdline)
        elif cls.is_https(cmdline):
            return HTTPSSource(cmdline)
        elif cls.is_ftp(cmdline):
            return FTPSource(cmdline)
        elif cls.is_file(cmdline):
            return FileSource(cmdline)
        elif cls.is_hmc(cmdline):
            return HMCSource()
        else:
            raise PayloadSourceTypeUnrecognized("Can't find source type for {}".format(cmdline))

    @staticmethod
    def is_cdrom(cmdline):
        """Is this cmdline parameter cdrom based payload source?"""
        return cmdline.startswith("cdrom")

    @staticmethod
    def is_harddrive(cmdline):
        """Is this cmdline parameter hdd based payload source?"""
        return cmdline.startswith("hd:")

    @staticmethod
    def is_nfs(cmdline):
        """Is this cmdline parameter nfs based payload source?"""
        return cmdline.startswith("nfs:")

    @staticmethod
    def is_http(cmdline):
        """Is this cmdline parameter http based payload source?"""
        return cmdline.startswith("http:")

    @staticmethod
    def is_https(cmdline):
        """Is this cmdline parameter https based payload source?"""
        return cmdline.startswith("https:")

    @staticmethod
    def is_ftp(cmdline):
        """Is this cmdline parameter ftp based payload source?"""
        return cmdline.startswith("ftp:")

    @staticmethod
    def is_file(cmdline):
        """Is this cmdline parameter local file based payload source?"""
        return cmdline.startswith("file:")

    @staticmethod
    def is_hmc(cmdline):
        """Is this cmdline parameter HMC based payload source?"""
        return cmdline.startswith("hmc")
