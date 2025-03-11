#
# DBus interface for payload CD-ROM image source.
#
# Copyright (C) 2020 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_interface
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_CDROM
from pyanaconda.modules.payloads.source.source_base_interface import (
    PayloadSourceBaseInterface,
)


@dbus_interface(PAYLOAD_SOURCE_CDROM.interface_name)
class CdromSourceInterface(PayloadSourceBaseInterface):
    """Interface for the payload CD-ROM image source.

    This source will try to automatically detect installation source. First it tries to look only
    stage2 device used to boot the environment then it will use first valid iso9660 media with a
    valid structure.
    """

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("DeviceID", self.implementation.device_id_changed)

    @property
    def DeviceID(self) -> Str:
        """Get device ID of the cdrom found."""
        return self.implementation.device_id
