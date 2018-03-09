#
# DBus names and paths.
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

__all__ = ['get_dbus_name', 'get_dbus_path', 'get_namespace_from_name']


def get_dbus_name(*namespace):
    """Create a DBus name from the given names.

    :param namespace: a sequence of names
    :return: a DBus name
    """
    return ".".join(namespace)


def get_dbus_path(*namespace):
    """Create a DBus path from the given names.

    :param namespace: a sequence of names
    :return: a DBus path
    """
    return "/" + "/".join(namespace)


def get_namespace_from_name(name):
    """Return a namespace of the DBus name.

    :param name: a DBus name
    :return: a sequence of names
    """
    return tuple(name.split("."))
