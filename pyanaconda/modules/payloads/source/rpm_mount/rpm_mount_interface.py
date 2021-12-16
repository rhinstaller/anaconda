#
# DBus interface for payload RPM mount image source.
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
from dasbus.typing import *  # pylint: disable=wildcard-import
from dasbus.server.property import emits_properties_changed
from pyanaconda.modules.common.constants.interfaces import PAYLOAD_SOURCE_RPM_MOUNT
from pyanaconda.modules.payloads.source.source_base_interface import PayloadSourceBaseInterface


@dbus_interface(PAYLOAD_SOURCE_RPM_MOUNT.interface_name)
class RPMMountSourceInterface(PayloadSourceBaseInterface):
    """Interface for the payload RPM mount based source.

    This source will use existing mount point as the payload source. There will be no unmount and
    mounting involved.
    """
    def connect_signals(self):
        super().connect_signals()
        self.watch_property("Path", self.implementation.path_changed)

    @property
    def Path(self) -> Str:
        """Get the path."""
        return self.implementation.path

    @emits_properties_changed
    def SetPath(self, path: Str):
        """Set the path."""
        self.implementation.set_path(path)
