#
# Support for DBus errors
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
from dasbus.namespace import get_dbus_name

import gi
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib

__all__ = ['dbus_error', 'dbus_error_by_default', "GLibErrorHandler", "ErrorRegister"]


class ErrorRegister(object):
    """Class for mapping exceptions to DBus errors."""

    def __init__(self):
        self._default_class = None
        self._default_namespace = "not.known.Error"
        self._map = dict()
        self._reversed_map = dict()

    def set_default_namespace(self, namespace):
        """Set the namespace for names of unknown errors."""
        self._default_namespace = namespace

    def set_default_exception(self, exception_cls):
        """Set the exception class as a default."""
        self._default_class = exception_cls

    def map_exception_to_name(self, exception_cls, name):
        """Map the exception class to a DBus name."""
        self._map[name] = exception_cls
        self._reversed_map[exception_cls] = name

    def get_error_name(self, exception_cls):
        """Get the DBus name of the exception."""
        if exception_cls in self._reversed_map:
            return self._reversed_map.get(exception_cls)

        if self._default_namespace:
            return "{}.{}".format(self._default_namespace, exception_cls.__name__)

        return exception_cls.__name__

    def get_exception_class(self, name):
        """Get the exception class mapped to the DBus name."""
        return self._map.get(name, self._default_class)


class GLibErrorHandler(object):
    """Class for handling DBus errors based on GLib."""

    # Register of DBus errors.
    register = ErrorRegister()

    @classmethod
    def handle_server_error(cls, server, invocation, e):
        """Handle a local exception on the server side."""
        server.set_call_error(
            invocation,
            cls.register.get_error_name(type(e)),
            str(e)
        )

    @classmethod
    def handle_client_error(cls, client, e):
        """Handle a remote DBus error on the client side."""
        raise cls._get_exception(e)

    @classmethod
    def _get_exception(cls, e):
        """Get an exception for the remote DBus error."""
        if not isinstance(e, GLib.Error):
            return e

        if not Gio.DBusError.is_remote_error(e):
            return e

        name = Gio.DBusError.get_remote_error(e)
        if not cls._is_name_registered(name):
            return e

        message = cls._get_exception_message(name, e.message)
        return cls._create_exception(name, message, e.domain, e.code)

    @classmethod
    def _is_name_registered(cls, name):
        """Is there an exception for the given DBus name?"""
        return cls.register.get_exception_class(name) is not None

    @staticmethod
    def _get_exception_message(name, message):
        """Transform the message of the exception."""
        prefix = "{}:{}: ".format("GDBus.Error", name)

        if message.startswith(prefix):
            return message[len(prefix):]

        return message

    @classmethod
    def _create_exception(cls, name, message, domain, code):
        """Create an exception from the given parameters."""
        exception_cls = cls.register.get_exception_class(name)
        exception = exception_cls(message)
        exception.dbus_name = name
        exception.dbus_domain = domain
        exception.dbus_code = code
        return exception


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


def map_error(error_name, error_handler=GLibErrorHandler):
    """Map decorated exception class to a DBus error."""
    def decorated(cls):
        error_handler.register.map_exception_to_name(cls, error_name)
        return cls

    return decorated


def map_by_default(cls, error_handler=GLibErrorHandler):
    """Map decorated exception class to all unknown DBus errors."""
    error_handler.register.set_default_exception(cls)
    return cls
