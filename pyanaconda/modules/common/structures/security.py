#
# DBus structures for the storage data.
#
# Copyright (C) 2024  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from dasbus.structure import DBusData
from dasbus.typing import *  # pylint: disable=wildcard-import

__all__ = ["CertificateData"]


class CertificateData(DBusData):
    """Structure for the certificate data."""

    def __init__(self):
        self._filename = ""
        self._cert = ""
        self._dir = ""

    @property
    def filename(self) -> Str:
        """The certificate file name."""
        return self._filename

    @filename.setter
    def filename(self, value: Str) -> None:
        self._filename = value

    @property
    def cert(self) -> Str:
        """The certificate content."""
        return self._cert

    @cert.setter
    def cert(self, value: Str) -> None:
        self._cert = value

    @property
    def dir(self) -> Str:
        """The certificate directory."""
        return self._dir

    @dir.setter
    def dir(self, value: Str) -> None:
        self._dir = value
