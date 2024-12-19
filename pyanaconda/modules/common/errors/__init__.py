#
# Copyright (C) 2018  Red Hat, Inc.  All rights reserved.
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
__all__ = ["register_errors"]


def register_errors():
    """Register all Anaconda's DBus errors."""
    # pylint:disable=unused-import
    # ruff: noqa: F401
    from pyanaconda.modules.common.errors import (
        configuration,
        general,
        installation,
        module,
        payload,
        runtime,
        storage,
        task,
    )
