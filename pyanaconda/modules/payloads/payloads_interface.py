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
from pyanaconda.modules.common.containers import PayloadSourceContainer, PayloadContainer
from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.modules.payloads.constants import PayloadType, SourceType


@dbus_interface(PAYLOADS.interface_name)
class PayloadsInterface(KickstartModuleInterface):
    """DBus interface for Payload module."""

    def GetActivePayload(self) -> ObjPath:
        """Get active payload.

        :raise: PayloadNotSetError if payload is not set
        """
        return PayloadContainer.to_object_path(
            self.implementation.get_active_payload()
        )

    def IsPayloadSet(self) -> Bool:
        """Test if any payload is set and used."""
        return self.implementation.is_payload_set()

    def CreatePayload(self, payload_type: Str) -> ObjPath:
        """Create payload and publish it on DBus.

        payload_type could contain these values:
         - DNF
         - LIVE_OS
         - LIVE_IMAGE
        """
        return PayloadContainer.to_object_path(
            self.implementation.create_payload(PayloadType(payload_type))
        )

    def CreateSource(self, source_type: Str) -> ObjPath:
        """Create payload source and publish it on DBus.

        source_type could contain these values:
         - LIVE_OS_IMAGE
        """
        return PayloadSourceContainer.to_object_path(
            self.implementation.create_source(SourceType(source_type))
        )
