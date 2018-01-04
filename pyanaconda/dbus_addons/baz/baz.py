# baz.py
# Example DBUS addon.
#
# Copyright (C) 2017 Red Hat, Inc.
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
from pyanaconda.dbus import DBus
from pyanaconda.dbus.constants import ADDON_BAZ_NAME, ADDON_BAZ_PATH
from pyanaconda.dbus_addons.baz.baz_interface import BazInterface
from pyanaconda.modules.base import KickstartModule

from pyanaconda import anaconda_logging
log = anaconda_logging.get_dbus_module_logger(__name__)


class Baz(KickstartModule):
    """The Baz module."""

    def publish(self):
        """Publish the module."""
        DBus.publish_object(BazInterface(self), ADDON_BAZ_PATH)
        DBus.register_service(ADDON_BAZ_NAME)
