#
# Kickstart module for date and time settings.
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
from pyanaconda.dbus import DBus
from pyanaconda.dbus.constants import MODULE_TIMEZONE_NAME, MODULE_TIMEZONE_PATH
from pyanaconda.core.isignal import Signal
from pyanaconda.modules.base import KickstartModule
from pyanaconda.modules.timezone.timezone_interface import TimezoneInterface
from pyanaconda.modules.timezone.timezone_kickstart import TimezoneKickstartSpecification

from pyanaconda import anaconda_logging
log = anaconda_logging.get_dbus_module_logger(__name__)


class TimezoneModule(KickstartModule):
    """The Timezone module."""

    def __init__(self):
        super().__init__()
        self.timezone_changed = Signal()
        self._timezone = "America/New_York"

        self.is_utc_changed = Signal()
        self._is_utc = False

        self.ntp_enabled_changed = Signal()
        self._ntp_enabled = True

        self.ntp_servers_changed = Signal()
        self._ntp_servers = []

    def publish(self):
        """Publish the module."""
        DBus.publish_object(TimezoneInterface(self), MODULE_TIMEZONE_PATH)
        DBus.register_service(MODULE_TIMEZONE_NAME)

    @property
    def kickstart_specification(self):
        """Return the kickstart specification."""
        return TimezoneKickstartSpecification

    def process_kickstart(self, data):
        """Process the kickstart data."""
        self.set_timezone(data.timezone.timezone)
        self.set_utc(data.timezone.isUtc)
        self.set_ntp_enabled(not data.timezone.nontp)
        self.set_ntp_servers(data.timezone.ntpservers)

    def generate_kickstart(self):
        """Return the kickstart string."""
        data = self.get_kickstart_data()
        data.timezone.timezone = self.timezone
        data.timezone.isUtc = self.is_utc
        data.timezone.nontp = not self.ntp_enabled

        if self.ntp_enabled:
            data.timezone.ntpservers = list(self.ntp_servers)

        return str(data)

    @property
    def timezone(self):
        """Return the timezone."""
        return self._timezone

    def set_timezone(self, timezone):
        """Set the timezone."""
        self._timezone = timezone
        self.timezone_changed.emit()

    @property
    def is_utc(self):
        """Is the hardware clock set to UTC?"""
        return self._is_utc

    def set_utc(self, is_utc):
        """Set if the hardware clock is set to UTC."""
        self._is_utc = is_utc
        self.is_utc_changed.emit()

    @property
    def ntp_enabled(self):
        """Enable automatic starting of NTP service."""
        return self._ntp_enabled

    def set_ntp_enabled(self, ntp_enabled):
        """Enable or disable automatic starting of NTP service."""
        self._ntp_enabled = ntp_enabled
        self.ntp_enabled_changed.emit()

    @property
    def ntp_servers(self):
        """Return a list of NTP servers."""
        return self._ntp_servers

    def set_ntp_servers(self, servers):
        """Set NTP servers."""
        self._ntp_servers = list(servers)
        self.ntp_servers_changed.emit()
