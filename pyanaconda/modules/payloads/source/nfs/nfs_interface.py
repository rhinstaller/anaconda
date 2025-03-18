#
# DBus interface for the NFS source module.
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
from dasbus.server.property import emits_properties_changed
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_NFS
from pyanaconda.modules.payloads.source.source_base_interface import PayloadSourceBaseInterface

__all__ = ["NFSSourceInterface"]


@dbus_interface(PAYLOAD_SOURCE_NFS.interface_name)
class NFSSourceInterface(PayloadSourceBaseInterface):
    """DBus interface for the NFS source module."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("URL", self.implementation.url_changed)

    @property
    def URL(self) -> Str:
        """Get the URL."""
        return self.implementation.url

    @emits_properties_changed
    def SetURL(self, url: Str):
        """Set the URL."""
        self.implementation.set_url(url)
