#
# DBus interface for packaging.
#
# Copyright (C) 2018 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.modules.common.containers import PayloadSourceContainer
from pyanaconda.modules.common.constants.services import PAYLOAD
from pyanaconda.modules.payload.constants import HandlerType, SourceType


@dbus_interface(PAYLOAD.interface_name)
class PayloadInterface(KickstartModuleInterface):
    """DBus interface for Payload module."""

    def GetActiveHandlerPath(self) -> ObjPath:
        """Get path to the payload which is used now."""
        return self.implementation.get_active_handler_path()

    def IsHandlerSet(self) -> Bool:
        """Test if any handler is set and used."""
        return self.implementation.is_handler_set()

    def CreateHandler(self, handler_type: Str) -> ObjPath:
        """Create payload handler and publish it on DBus.

        handler_type could contain these values:
         - DNF
         - LIVE_OS
         - LIVE_IMAGE
        """
        return self.implementation.create_handler(HandlerType(handler_type))

    def CreateSource(self, source_type: Str) -> ObjPath:
        """Create payload source and publish it on DBus.

        source_type could contain these values:
         - LIVE_OS_IMAGE
        """

        return PayloadSourceContainer.to_object_path(
            self.implementation.create_source(SourceType(source_type))
        )
