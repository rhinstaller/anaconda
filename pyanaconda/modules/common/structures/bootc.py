#
# DBus structures for the Bootc data.
#
# Copyright (C) 2025 Red Hat, Inc.
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
from dasbus.typing import Str

__all__ = ["BootcConfigurationData"]


class BootcConfigurationData(DBusData):
    """Structure to hold Bootc configuration."""

    def __init__(self):
        self._stateroot = ""
        self._sourceImgRef = ""
        self._targetImgRef = ""

    @property
    def stateroot(self) -> Str:
        """Management root for OS installation."""
        return self._stateroot

    @stateroot.setter
    def stateroot(self, value: Str):
        self._stateroot = value

    @property
    def sourceImgRef(self) -> Str:
        """Explicitly given installation source"""
        return self._sourceImgRef

    @sourceImgRef.setter
    def sourceImgRef(self, value: Str):
        self._sourceImgRef = value

    @property
    def targetImgRef(self) -> Str:
        """Image to fetch for subsequent updates"""
        return self._targetImgRef

    @targetImgRef.setter
    def targetImgRef(self, value: Str):
        self._targetImgRef = value
