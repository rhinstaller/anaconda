#
# Known Boss errors.
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
from pydbus.error import map_error
from pyanaconda.dbus.errors import AnacondaError
from pyanaconda.dbus.objects import BOSS_ANACONDA, BOSS_INSTALLATION


@map_error("{}.SplitKickstartError".format(BOSS_ANACONDA))
class SplitKickstartError(AnacondaError):
    """Error while parsing kickstart for splitting."""
    pass


@map_error("{}.SplitKickstartSectionParsingError".format(BOSS_ANACONDA))
class SplitKickstartSectionParsingError(SplitKickstartError):
    """Error while parsing a section in kickstart."""
    pass


@map_error("{}.SplitKickstartMissingIncludeError".format(BOSS_ANACONDA))
class SplitKickstartMissingIncludeError(SplitKickstartError):
    """File included in kickstart was not found."""
    pass


@map_error("{}.InstallationNotRunning".format(BOSS_INSTALLATION))
class InstallationNotRunning(AnacondaError):
    """Exception will be raised when action requires running installation."""
    pass
