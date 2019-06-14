#
# DBus interface for Live Image payload.
#
# Copyright (C) 2019 Red Hat, Inc.
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
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import

from pyanaconda.modules.common.constants.objects import LIVE_IMAGE_HANDLER
from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate


@dbus_interface(LIVE_IMAGE_HANDLER.interface_name)
class LiveImageHandlerInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for Live Image payload module."""

    def connect_signals(self):
        super().connect_signals()

        self.watch_property("Url", self.implementation.url_changed)
        self.watch_property("Proxy", self.implementation.proxy_changed)
        self.watch_property("Checksum", self.implementation.checksum_changed)
        self.watch_property("VerifySSL", self.implementation.verifyssl_changed)

    @property
    def Url(self) -> Str:
        """Get url where to obtain the live image for installation."""
        return self.implementation.url
    @property
    def Proxy(self) -> Str:
        """Get proxy setting which will be use to obtain the image."""
        return self.implementation.proxy
    @property
    def Checksum(self) -> Str:
        """Get checksum of the image for verification."""
        return self.implementation.checksum
    @property
    def VerifySSL(self) -> Bool:
        """Should the ssl verification be enabled?"""
        return self.implementation.verifyssl
