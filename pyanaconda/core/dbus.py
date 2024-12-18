#
# DBus connections
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
import os

from dasbus.connection import MessageBus, SessionMessageBus, SystemMessageBus
from dasbus.constants import DBUS_STARTER_ADDRESS
from dasbus.error import AbstractErrorRule, ErrorMapper, get_error_decorator

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import (
    ANACONDA_BUS_ADDR_FILE,
    DBUS_ANACONDA_SESSION_ADDRESS,
)
from pyanaconda.modules.common.errors import register_errors

log = get_module_logger(__name__)

__all__ = ["DBus", "SessionBus", "SystemBus", "dbus_error", "error_mapper"]


class AnacondaMessageBus(MessageBus):
    """Representation of an Anaconda bus connection."""

    @property
    def address(self):
        """The bus address."""
        return self._find_bus_address()

    def _get_connection(self):
        """Get a connection to a bus at the specified address."""
        bus_address = self._find_bus_address()

        log.info("Connecting to the Anaconda bus at %s.", bus_address)
        return self._provider.get_addressed_bus_connection(bus_address)

    def _find_bus_address(self):
        """Get the address of the Anaconda bus."""
        if DBUS_ANACONDA_SESSION_ADDRESS in os.environ:
            return os.environ.get(DBUS_ANACONDA_SESSION_ADDRESS)

        if os.path.exists(ANACONDA_BUS_ADDR_FILE):
            with open(ANACONDA_BUS_ADDR_FILE, 'rt') as f:
                return f.read().strip()

        raise ConnectionError("Can't find Anaconda bus address!")


class DefaultMessageBus(AnacondaMessageBus):
    """Representation of a default bus connection."""

    def _find_bus_address(self):
        """Get the address of the default bus.

        Connect to the bus specified by the environmental variable
        DBUS_STARTER_ADDRESS. If it is not specified, connect to
        the Anaconda bus.
        """
        if DBUS_STARTER_ADDRESS in os.environ:
            return os.environ.get(DBUS_STARTER_ADDRESS)

        return super()._find_bus_address()


class AnacondaErrorMapper(ErrorMapper):
    """Map Anaconda exceptions to DBus errors."""

    def reset_rules(self):
        """Reset rules in the error mapper."""
        super().reset_rules()
        self.add_rule(DefaultNameErrorRule(
            "org.fedoraproject.Anaconda.Error"
        ))


class DefaultNameErrorRule(AbstractErrorRule):
    """Default rule for mapping an unknown exception to a DBus error name."""

    def __init__(self, default_name):
        """Create a new rule.

        :param default_name: a default name of a DBus error
        """
        self._default_name = default_name

    def match_type(self, _exception_type):
        """Match every Python exception raised on the server side."""
        return True

    def get_name(self, _exception_type):
        """Return a default error name for every matched exception."""
        return self._default_name

    def match_name(self, _error_name):
        """Don't apply this rule on the client side."""
        return False

    def get_type(self, _error_name):
        """There is no default error type in this rule."""

# System bus.
SystemBus = SystemMessageBus()

# Session bus.
SessionBus = SessionMessageBus()

# The mapper of DBus errors.
error_mapper = AnacondaErrorMapper()

# The decorator for DBus errors.
dbus_error = get_error_decorator(error_mapper)

# Register all DBus errors.
register_errors()

# Default bus. Anaconda uses this connection.
DBus = DefaultMessageBus(
    error_mapper=error_mapper
)
