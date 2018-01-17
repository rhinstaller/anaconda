#
# DBus interface for the network module.
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

from pyanaconda.dbus.constants import MODULE_NETWORK_NAME
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.base_interface import KickstartModuleInterface
from pyanaconda.dbus.interface import dbus_interface


@dbus_interface(MODULE_NETWORK_NAME)
class NetworkInterface(KickstartModuleInterface):
    """DBus interface for Network module."""

    def connect_signals(self):
        super().connect_signals()
        self.implementation.hostname_changed.connect(self.changed("Hostname"))

    @property
    def Hostname(self) -> Str:
        """Hostname the system will use."""
        return self.implementation.hostname

    @emits_properties_changed
    def SetHostname(self, hostname: Str):
        """Set the hostname.

        Sets the hostname of installed system.

        param hostname: a string with a hostname
        """
        self.implementation.set_hostname(hostname)
