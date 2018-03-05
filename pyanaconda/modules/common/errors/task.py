#
# DBus errors related to tasks.
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
from pyanaconda.dbus.constants import DBUS_TASK_NAME
from pyanaconda.modules.common.errors import AnacondaError


@map_error("{}.TaskError".format(DBUS_TASK_NAME))
class TaskError(AnacondaError):
    """General exception for task errors."""
    pass


@map_error("{}.TaskAlreadyRunningError".format(DBUS_TASK_NAME))
class TaskAlreadyRunningError(TaskError):
    """Exception will be raised when starting task which is already running."""
    pass
