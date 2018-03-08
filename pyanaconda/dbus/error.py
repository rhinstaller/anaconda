#
# DBus errors.
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
from pydbus.error import map_error, map_by_default
from pyanaconda.dbus.namespace import get_dbus_name

__all__ = ['dbus_error', 'dbus_error_by_default']


def dbus_error(error_name, namespace):
    """Define decorated class as a DBus error.

    The decorated exception class will be mapped to a DBus error.

    :param error_name: a DBus name of the error
    :param namespace: a sequence of strings
    :return: a decorator
    """
    return map_error(get_dbus_name(*namespace, error_name))


def dbus_error_by_default(cls):
    """Define a default DBus error.

    The decorated exception class will be mapped to all unknown DBus errors.

    :param cls: an exception class
    :return: a decorated class
    """
    return map_by_default(cls)
