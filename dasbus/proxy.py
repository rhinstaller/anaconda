#
# Support for object proxies
#
# Copyright (C) 2019  Red Hat, Inc.  All rights reserved.
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
from dasbus.client import AbstractObjectProxy

__all__ = ["get_object_path"]


def get_object_path(proxy):
    """Get an object path of the remote DBus object.

    :param proxy: a DBus proxy
    :return: a DBus path
    """
    if not isinstance(proxy, AbstractObjectProxy):
        raise TypeError("Invalid type of proxy: {}".format(str(type(proxy))))

    handler = getattr(proxy, "_handler")
    return getattr(handler, "_object_path")
