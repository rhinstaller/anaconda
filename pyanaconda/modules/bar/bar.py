# bar.py
# Example DBUS module
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
from pyanaconda.dbus.constants import MODULE_BAR_PATH, MODULE_BAR_NAME, MODULE_TIMEZONE_NAME, \
    MODULE_TIMEZONE_PATH
from pyanaconda.dbus.observer import DBusCachedObserver
from pyanaconda.modules.bar.bar_kickstart import BarKickstartSpecification
from pyanaconda.modules.base import KickstartModule
from pyanaconda.modules.bar.bar_interface import BarInterface
from pyanaconda.modules.bar.tasks.bar_task import BarTask

from pyanaconda import anaconda_logging
log = anaconda_logging.get_dbus_module_logger(__name__)


class Bar(KickstartModule):
    """The Bar module."""

    def __init__(self):
        super().__init__()
        self._data = None
        self._timezone_module = DBusCachedObserver(MODULE_TIMEZONE_NAME,
                                                   MODULE_TIMEZONE_PATH,
                                                   [MODULE_TIMEZONE_NAME])

    def publish(self):
        """Publish the module."""
        # Publish bar.
        DBus.publish_object(BarInterface(self), MODULE_BAR_PATH)
        self.publish_task(BarTask(), MODULE_BAR_PATH)
        DBus.register_service(MODULE_BAR_NAME)

        # Start to watch the timezone module.
        self._timezone_module.cached_properties_changed.connect(self._timezone_callback)
        self._timezone_module.connect_once_available()

    @property
    def kickstart_specification(self):
        return BarKickstartSpecification

    def process_kickstart(self, data):
        log.debug(data)
        self._data = data

    def generate_kickstart(self):
        return str(self._data)

    def _timezone_debug(self):
        log.debug("Timezone values: %s (cache), %s (proxy)",
                  self._timezone_module.cache.Timezone,
                  self._timezone_module.proxy.Timezone)

    def _timezone_callback(self, observer, names, invalid):
        log.debug("Timezone changes: %s, %s, %s", observer, names, invalid)
        self._timezone_debug()

    def set_timezone(self, timezone):
        log.debug("Timezone set to: %s", timezone)
        self._timezone_module.proxy.SetTimezone(timezone)
        self._timezone_debug()
