#
# Common DBus errors.
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
from pykickstart.errors import KickstartError
from pyanaconda.dbus.error import dbus_error_by_default, dbus_error
from pyanaconda.modules.common.constants.namespaces import ANACONDA_NAMESPACE


@dbus_error_by_default
class DBusError(Exception):
    """A default DBus error."""
    pass


@dbus_error("Error", namespace=ANACONDA_NAMESPACE)
class AnacondaError(Exception):
    """A default Anaconda error."""
    pass


# Define mapping for existing exceptions.
dbus_error("KickstartError", namespace=ANACONDA_NAMESPACE)(KickstartError)
