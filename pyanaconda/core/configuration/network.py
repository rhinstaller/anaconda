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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
#  Author(s):  Vendula Poncova <vponcova@redhat.com>
#
from enum import Enum

from pyanaconda.core.configuration.base import Section


class NetworkOnBoot(Enum):
    """Network device to be activated on boot if none was configured so."""
    NONE = "NONE"
    DEFAULT_ROUTE_DEVICE = "DEFAULT_ROUTE_DEVICE"
    FIRST_WIRED_WITH_LINK = "FIRST_WIRED_WITH_LINK"


class NetworkSection(Section):
    """The Network section."""

    @property
    def default_on_boot(self):
        """Network device to be activated on boot if none was configured so.

        Valid values:

          NONE                   No device
          DEFAULT_ROUTE_DEVICE   A default route device
          FIRST_WIRED_WITH_LINK  The first wired device with link

        :return: an instance of NetworkOnBoot
        """
        return self._get_option("default_on_boot", NetworkOnBoot)
