#
# Completeness related constants.
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
from enum import StrEnum


class IncompletenessKind(StrEnum):
    """Kind of a reason why a module is not ready to install.

    BUSY is transient: the module is still working and waiting will
    resolve it. UNCONFIGURED and INVALID will not resolve on their own,
    so an automated driver must abort rather than wait when it sees
    either of them.
    """

    BUSY = "busy"
    UNCONFIGURED = "unconfigured"
    INVALID = "invalid"
