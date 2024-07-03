#
# DBus errors related to the runtime modules.
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
from pyanaconda.core.dbus import dbus_error
from pyanaconda.modules.common.constants.namespaces import RUNTIME_NAMESPACE
from pyanaconda.modules.common.errors.general import AnacondaError


@dbus_error("ScriptError", namespace=RUNTIME_NAMESPACE)
class ScriptError(AnacondaError):
    """error raised during kickstart script processing."""
    def __init__(self, message):
        super().__init__(message)
        lines = message.split("\n", 1)
        self.lineno = lines[0]
        self.details = lines[1].strip() if len(lines) > 1 else ""
