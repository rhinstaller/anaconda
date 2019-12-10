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
from pyanaconda.modules.common.constants.services import PAYLOAD
from pyanaconda.modules.common.base import KickstartModuleInterface
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import


@dbus_interface(PAYLOAD.interface_name)
class PayloadInterface(KickstartModuleInterface):
    """DBus interface for Payload module."""

    def connect_signals(self):
        super().connect_signals()
        self.watch_property("RedHatCDNEnabled", self.implementation.red_hat_cdn_enabled_changed)

    @property
    def RedHatCDNEnabled(self) -> Bool:
        """Report if the Red Hat CDN is enabled as the installation source."""
        return self.implementation.red_hat_cdn_enabled

    @emits_properties_changed
    def SetRedHatCDNEnabled(self, cdn_enabled: Bool):
        """Set if Red Hat CDN is enabled as installation source.

        :param bool cdn_enabled: True if CDN is the installation source, False otherwise
        """
        self.implementation.set_red_hat_cdn_enabled(cdn_enabled)
