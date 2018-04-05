#
# DBus errors related to a kickstart file.
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
from pyanaconda.dbus.error import dbus_error
from pyanaconda.modules.common.constants.namespaces import BOSS_NAMESPACE
from pyanaconda.modules.common.errors import AnacondaError


@dbus_error("SplitKickstartError", namespace=BOSS_NAMESPACE)
class SplitKickstartError(AnacondaError):
    """Error while parsing kickstart for splitting."""
    pass


@dbus_error("SplitKickstartSectionParsingError", namespace=BOSS_NAMESPACE)
class SplitKickstartSectionParsingError(SplitKickstartError):
    """Error while parsing a section in kickstart."""
    pass


@dbus_error("SplitKickstartMissingIncludeError", namespace=BOSS_NAMESPACE)
class SplitKickstartMissingIncludeError(SplitKickstartError):
    """File included in kickstart was not found."""
    pass
