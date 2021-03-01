#
# General DBus errors.
#
# Copyright (C) 2020  Red Hat, Inc.  All rights reserved.
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
from dasbus.error import DBusError

from pyanaconda.core.dbus import dbus_error
from pyanaconda.modules.common.constants.namespaces import ANACONDA_NAMESPACE


@dbus_error("Error", namespace=ANACONDA_NAMESPACE)
class AnacondaError(DBusError):
    """A default Anaconda error."""
    pass


@dbus_error("InvalidValueError", namespace=ANACONDA_NAMESPACE)
class InvalidValueError(AnacondaError):
    """Invalid value passed."""
    pass


@dbus_error("UnsupportedValueError", namespace=ANACONDA_NAMESPACE)
class UnsupportedValueError(AnacondaError):
    """Value passed is not supported."""
    pass


@dbus_error("UnavailableValueError", namespace=ANACONDA_NAMESPACE)
class UnavailableValueError(AnacondaError):
    """The requested value is not available."""
    pass
