#
# DBus structures for subscription related data.
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

__all__ = ["SystemPurposeData"]


class SystemPurposeData(DBusData):
    """System purpose data."""

    def __init__(self):
        self._role = ""
        self._sla = ""
        self._usage = ""
        self._addons = []

    @property
    def role(self) -> Str:
        """Return the System Purpose role (if any).

        :return: system purpose role
        """
        return self._role

    @role.setter
    def role(self, role: Str):
        self._role = role

    @property
    def sla(self) -> Str:
        """Return the System Purpose SLA (if any).

        :return: system purpose SLA
        """
        return self._sla

    @sla.setter
    def sla(self, sla: Str):
        self._sla = sla

    @property
    def usage(self) -> Str:
        """Return the System Purpose usage (if any).

        :return: system purpose usage
        """
        return self._usage

    @usage.setter
    def usage(self, usage: Str):
        self._usage = usage

    @property
    def addons(self) -> List[Str]:
        """Return list of additional layered products or features (if any).

        :return: system purpose addons
        """
        return self._addons

    @addons.setter
    def addons(self, addons: List[Str]):
        self._addons = addons
