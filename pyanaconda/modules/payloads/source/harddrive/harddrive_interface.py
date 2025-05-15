#
# DBus interface for payload Hard drive image source.
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from dasbus.server.interface import dbus_interface
from dasbus.server.property import emits_properties_changed
from dasbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_HARDDRIVE
from pyanaconda.modules.payloads.source.source_base_interface import (
    PayloadSourceBaseInterface,
)


@dbus_interface(PAYLOAD_SOURCE_HARDDRIVE.interface_name)
class HardDriveSourceInterface(PayloadSourceBaseInterface):
    """Interface for the payload Hard drive image source."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("Directory", self.implementation.directory_changed)
        self.watch_property("Partition", self.implementation.device_changed)

    @property
    def Directory(self) -> Str:
        """Get the path to the repository on the partition."""
        return self.implementation.directory

    @emits_properties_changed
    def SetDirectory(self, directory: Str):
        """Set the path to the repository on the partition."""
        self.implementation.set_directory(directory)

    @property
    def Partition(self) -> Str:
        """Get the partition containing the repository."""
        return self.implementation.device

    @emits_properties_changed
    def SetPartition(self, partition: Str):
        """Set the partition containing the repository."""
        self.implementation.set_device(partition)

    def GetIsoPath(self) -> Str:
        """Get path to the ISO from the partition root.

        This could be an empty string if the source is pointing to
        installation tree instead of ISO.
        """
        return self.implementation.get_iso_path()
