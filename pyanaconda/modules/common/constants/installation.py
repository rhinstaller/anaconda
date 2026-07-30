#
# Installation related constants.
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
from enum import IntEnum, StrEnum


class InstallationStatus(IntEnum):
    """Status of the installation process tracked by the Boss module."""

    # Values start at 1 so that all valid states are truthy — syntactic
    # sugar for UI clients to distinguish "status loaded" from "not yet
    # fetched" (null/undefined), e.g. ``if (status) { /* ready */ }``.
    NOT_STARTED = 1
    RUNNING = 2
    SUCCEEDED = 3
    FAILED = 4


class InstallationErrorDialogType(StrEnum):
    """Dialog types for installation errors forwarded from Boss to the UI."""

    YES_NO = "yesno"
    FATAL_ERROR = "error"
