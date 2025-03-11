#
# DBus structure for module runtime rescue data.
#
# Copyright (C) 2024 Red Hat, Inc.
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
from dasbus.typing import Bool

__all__ = ["RescueData"]


class RescueData(DBusData):
    """Module Rescue mode configuration data."""

    def __init__(self):
        self._rescue = False
        self._nomount = False
        self._romount = False

    @property
    def rescue(self) -> Bool:
        """Whether Rescue mode is enabled.

        Indicates if the system should boot into Rescue mode.

        :return: True if Rescue mode is enabled, False otherwise.
        """
        return self._rescue

    @rescue.setter
    def rescue(self, value: Bool):
        self._rescue = value

    @property
    def nomount(self) -> Bool:
        """Whether mounting is disabled in Rescue mode.

        If True, the filesystems will not be mounted automatically in Rescue mode.

        :return: True if automatic mounting is disabled, False otherwise.
        """
        return self._nomount

    @nomount.setter
    def nomount(self, value: Bool):
        self._nomount = value

    @property
    def romount(self) -> Bool:
        """Whether filesystems should be mounted read-only in Rescue mode.

        If True, the filesystems will be mounted in read-only mode during Rescue mode.

        :return: True if filesystems are to be mounted read-only, False otherwise.
        """
        return self._romount

    @romount.setter
    def romount(self, value: Bool):
        self._romount = value
