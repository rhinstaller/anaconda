#
# DBus errors related to the payload module and handlers.
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
from dasbus.error import dbus_error
from pyanaconda.modules.common.constants.namespaces import PAYLOAD_NAMESPACE
from pyanaconda.modules.common.errors import AnacondaError


@dbus_error("SourceSetupError", namespace=PAYLOAD_NAMESPACE)
class SourceSetupError(AnacondaError):
    """Error raised during the source setup."""
    pass


@dbus_error("SourceTearDownError", namespace=PAYLOAD_NAMESPACE)
class SourceTearDownError(AnacondaError):
    """Error raised during the source tear down."""

    def __init__(self, message, errors=None):
        if errors:
            message = message + "\n" + "\n".join(errors)

        super().__init__(message)


@dbus_error("IncompatibleSourceError", namespace=PAYLOAD_NAMESPACE)
class IncompatibleSourceError(AnacondaError):
    """Error raised when handler does not support given source."""
    pass


@dbus_error("InstallError", namespace=PAYLOAD_NAMESPACE)
class InstallError(AnacondaError):
    """Error raised during payload installation."""
    pass


@dbus_error("HandlerNotSetError", namespace=PAYLOAD_NAMESPACE)
class HandlerNotSetError(AnacondaError):
    """Payload handler is not set."""
    pass
