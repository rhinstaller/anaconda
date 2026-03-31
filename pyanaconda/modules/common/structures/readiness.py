#
# DBus structures for installation readiness.
#
# Copyright (C) 2026  Red Hat, Inc.  All rights reserved.
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

__all__ = ["InstallationReadinessReport"]


class InstallationReadinessReport(DBusData):
    """The installation readiness report."""

    def __init__(self):
        self._can_reach_install = True
        self._blocking_errors = []
        self._warnings = []
        self._reasons_by_module = {}

    @property
    def can_reach_install(self) -> Bool:
        """Can the installation continue to the install phase?"""
        return self._can_reach_install

    @can_reach_install.setter
    def can_reach_install(self, value: Bool):
        self._can_reach_install = bool(value)

    @property
    def blocking_errors(self) -> List[Str]:
        """Blocking errors that prevent the installation from continuing."""
        return self._blocking_errors

    @blocking_errors.setter
    def blocking_errors(self, errors: List[Str]):
        self._blocking_errors = list(errors)

    @property
    def warnings(self) -> List[Str]:
        """Non-blocking warnings."""
        return self._warnings

    @warnings.setter
    def warnings(self, warnings: List[Str]):
        self._warnings = list(warnings)

    @property
    def reasons_by_module(self) -> Dict[Str, Structure]:
        """Validation reasons grouped by module name."""
        return self._reasons_by_module

    @reasons_by_module.setter
    def reasons_by_module(self, reasons: Dict[Str, Structure]):
        self._reasons_by_module = dict(reasons)
