#
# DBus structures for the timezone data.
#
# Copyright (C) 2020  Red Hat, Inc.  All rights reserved.
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

from pyanaconda.core.constants import TIME_SOURCE_SERVER

__all__ = ["GeolocationData", "TimeSourceData"]


class TimeSourceData(DBusData):
    """Data for a time source."""

    def __init__(self):
        self._type = TIME_SOURCE_SERVER
        self._hostname = ""
        self._options = []

    @property
    def type(self) -> Str:
        """Type of the time source.

        Supported values:

            SERVER  A single NTP server
            POOL    A pool of NTP servers

        :return: a type of the time source
        """
        return self._type

    @type.setter
    def type(self, value: Str):
        self._type = value

    @property
    def hostname(self) -> Str:
        """Name of the time server.

        For example:

            ntp.cesnet.cz

        :return: a host name
        """
        return self._hostname

    @hostname.setter
    def hostname(self, value: Str):
        self._hostname = value

    @property
    def options(self) -> List[Str]:
        """Options of the time source.

        For example:

            nts, ntsport 1234, iburst

        See ``man chrony.conf``.

        :return: a list of options
        """
        return self._options

    @options.setter
    def options(self, value):
        self._options = value


class GeolocationData(DBusData):
    """Encapsulates the result from geolocation lookup."""

    def __init__(self):
        self._territory = ""
        self._timezone = ""

    @classmethod
    def from_values(cls, territory="", timezone=""):
        """
        :param str territory: the territory code from GeoIP lookup
        :param str timezone: the time zone from GeoIP lookup
        """
        instance = cls()
        instance.territory = territory
        instance.timezone = timezone
        return instance

    @property
    def territory(self) -> Str:
        """Territory code

        For example: CZ, JP, UA
        """
        return self._territory

    @territory.setter
    def territory(self, value: Str):
        self._territory = value

    @property
    def timezone(self) -> Str:
        """Timezone

        For example: Africa/Cairo
        """
        return self._timezone

    @timezone.setter
    def timezone(self, value: Str):
        self._timezone = value

    def is_empty(self):
        """Is the structure empty?"""
        return not bool(self._territory) and not bool(self._timezone)
