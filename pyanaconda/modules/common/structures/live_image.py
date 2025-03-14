#
# DBus structures for the live image data.
#
# Copyright (C) 2020 Red Hat, Inc.
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
from dasbus.structure import DBusData
from dasbus.typing import Bool, Str

__all__ = ["LiveImageConfigurationData"]


class LiveImageConfigurationData(DBusData):
    """Structure to hold the live image configuration."""

    def __init__(self):
        self._url = ""
        self._proxy = ""
        self._checksum = ""
        self._ssl_verification_enabled = True

    @property
    def url(self) -> Str:
        """The URL to the image.

        Supported protocols:

            http
            https
            ftp
            file

        :return: a URL
        """
        return self._url

    @url.setter
    def url(self, url: Str):
        self._url = url

    @property
    def proxy(self) -> Str:
        """The proxy URL to use while performing the installation.

        :return: a proxy URL
        """
        return self._proxy

    @proxy.setter
    def proxy(self, proxy: Str):
        self._proxy = proxy

    @property
    def checksum(self) -> Str:
        """The sha256 checksum of the image file.

        :return: a string with the checksum
        """
        return self._checksum

    @checksum.setter
    def checksum(self, value: Str):
        self._checksum = value

    @property
    def ssl_verification_enabled(self) -> Bool:
        """Is ssl verification enabled?

        You can disable SSL verification to reach server with certificate
        which is not part of installation environment.

        :return: True or False
        """
        return self._ssl_verification_enabled

    @ssl_verification_enabled.setter
    def ssl_verification_enabled(self, ssl_verification_enabled: Bool):
        self._ssl_verification_enabled = ssl_verification_enabled
